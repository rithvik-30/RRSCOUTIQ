"""
Chronological Venue Par Estimator
Phase 4.4 Controlled Shadow-Mode Pilot

Provides leakage-free, walk-forward hierarchical venue par estimation:
S_venue -> S_competition -> S_global.
"""

from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import numpy as np

from src.models.cspm.config import (
    VENUE_SHRINKAGE_M,
    VENUE_MIN_MATCHES,
    COMP_MIN_MATCHES,
    GLOBAL_PAR_DEFAULT
)


class ChronologicalVenueParEstimator:
    """
    Chronological Walk-Forward Venue Par Estimator.
    
    Guarantees:
    1. Zero future-match leakage: venue par for match t uses only completed
       1st innings played strictly before match t's date.
    2. Excludes the evaluated match t itself, preventing circularity.
    3. Excludes truncated/abandoned mid-innings fixtures.
    4. Applies Bayesian shrinkage to venue and competition levels.
    """

    def __init__(
        self,
        m_shrunk: float = VENUE_SHRINKAGE_M,
        min_venue_matches: int = VENUE_MIN_MATCHES,
        min_comp_matches: int = COMP_MIN_MATCHES,
        global_default: float = GLOBAL_PAR_DEFAULT
    ):
        self.m_shrunk = float(m_shrunk)
        self.min_venue_matches = int(min_venue_matches)
        self.min_comp_matches = int(min_comp_matches)
        self.global_default = float(global_default)
        self.db: Optional[pd.DataFrame] = None

    def fit_database(self, historical_matches_df: pd.DataFrame) -> "ChronologicalVenueParEstimator":
        """
        Registers candidate historical matches into the lookup database.
        
        Expected columns:
        - match_id (int)
        - match_date (datetime)
        - venue_id (int)
        - comp_id (int)
        - first_innings_runs (float/int)
        - is_complete_first_innings (bool)
        """
        required_cols = [
            "match_id",
            "match_date",
            "venue_id",
            "comp_id",
            "first_innings_runs",
            "is_complete_first_innings"
        ]
        for col in required_cols:
            if col not in historical_matches_df.columns:
                raise ValueError(f"Missing required column in historical matches: {col}")

        # Keep only eligible completed first innings
        valid_df = historical_matches_df[
            historical_matches_df["is_complete_first_innings"] &
            historical_matches_df["first_innings_runs"].notna()
        ].copy()

        valid_df["match_date"] = pd.to_datetime(valid_df["match_date"])
        valid_df = valid_df.sort_values("match_date").reset_index(drop=True)
        self.db = valid_df[required_cols]
        return self

    def estimate_par(
        self,
        match_date: pd.Timestamp,
        venue_id: int,
        comp_id: int,
        current_match_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Estimates the venue par score available at the exact moment before match_date.
        """
        if self.db is None or len(self.db) == 0:
            return {
                "venue_par": self.global_default,
                "source": "global_cold_start",
                "prior_matches_count": 0,
                "venue_matches_count": 0,
                "comp_matches_count": 0
            }

        m_date = pd.to_datetime(match_date)

        # Strictly prior matches; exclude evaluated match if present
        mask = self.db["match_date"] < m_date
        if current_match_id is not None:
            mask = mask & (self.db["match_id"] != current_match_id)

        priors = self.db[mask]
        n_priors = len(priors)

        global_prior_mean = float(priors["first_innings_runs"].mean()) if n_priors > 0 else self.global_default
        venue_priors = priors[priors["venue_id"] == venue_id]
        comp_priors = priors[priors["comp_id"] == comp_id]
        n_venue = len(venue_priors)
        n_comp = len(comp_priors)

        if n_priors < 10:
            par_val = self.global_default if n_priors == 0 else global_prior_mean
            return {
                "venue_par": float(par_val),
                "source": "global_cold_start",
                "prior_matches_count": n_priors,
                "venue_matches_count": n_venue,
                "comp_matches_count": n_comp
            }

        # 1. Venue-level shrinkage
        if n_venue >= self.min_venue_matches:
            v_mean = float(venue_priors["first_innings_runs"].mean())
            shrunk_par = (n_venue * v_mean + self.m_shrunk * global_prior_mean) / (n_venue + self.m_shrunk)
            return {
                "venue_par": float(shrunk_par),
                "source": "venue",
                "prior_matches_count": n_priors,
                "venue_matches_count": n_venue,
                "comp_matches_count": n_comp
            }

        # 2. Competition-level fallback
        if n_comp >= self.min_comp_matches:
            c_mean = float(comp_priors["first_innings_runs"].mean())
            shrunk_par = (n_comp * c_mean + self.m_shrunk * global_prior_mean) / (n_comp + self.m_shrunk)
            return {
                "venue_par": float(shrunk_par),
                "source": "competition",
                "prior_matches_count": n_priors,
                "venue_matches_count": n_venue,
                "comp_matches_count": n_comp
            }

        # 3. Global historical prior fallback
        return {
            "venue_par": float(global_prior_mean),
            "source": "global",
            "prior_matches_count": n_priors,
            "venue_matches_count": n_venue,
            "comp_matches_count": n_comp
        }
