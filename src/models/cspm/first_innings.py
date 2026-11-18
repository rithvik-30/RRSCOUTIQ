"""
First-Innings Pressure Engine
Phase 4.4 Controlled Shadow-Mode Pilot

Computes first-innings Par-Deficit Risk (BPS) and Bowler Par-Protection Score (BoPS):
BPS_t = 100 * Phi((S_par - S_hat_final,t) / sigma_rem,t)
BoPS_t = 100 - BPS_t
"""

from typing import Dict, Any, Optional, Union
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingRegressor

from src.models.cspm.config import (
    SIGMA_0,
    MIN_UNCERTAINTY,
    MAX_BALLS,
    PRESSURE_TIER_BOUNDS
)


class FirstInningsPressureEngine:
    """
    Evaluates batting distress and bowling control in the 1st innings under
    the Par-Deficit Risk framework.
    
    Semantic Grounding:
    - BPS (Batter Pressure Score): Probability of finishing below venue par: P(S_final < S_par).
      Represents batting distress and par shortfall danger. It is NOT match-win probability.
    - BoPS (Bowler Pressure Score): Complementary par-relative bowling pressure score (100 - BPS).
      Represents the bowling side's pressure to restrict the batting team below par.
    """

    def __init__(
        self,
        sigma_0: float = SIGMA_0,
        min_uncertainty: float = MIN_UNCERTAINTY,
        regressor: Optional[HistGradientBoostingRegressor] = None
    ):
        self.sigma_0 = float(sigma_0)
        self.min_uncertainty = float(min_uncertainty)
        if regressor is not None:
            self.model = regressor
        else:
            self.model = HistGradientBoostingRegressor(
                max_iter=150,
                min_samples_leaf=50,
                random_state=42
            )
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "FirstInningsPressureEngine":
        """
        Fits the score-projection regressor.
        
        Features: [balls_rem, wkts_in_hand, curr_score, crr, venue_par]
        Target: actual runs scored in remainder of innings
        """
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def compute_uncertainty(self, balls_rem: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Square-root residual uncertainty scaling:
        sigma_rem(B) = max(min_uncertainty, sigma_0 * sqrt(B / 120))
        """
        b_clipped = np.clip(balls_rem, 0.0, float(MAX_BALLS))
        return np.maximum(self.min_uncertainty, self.sigma_0 * np.sqrt(b_clipped / float(MAX_BALLS)))

    def predict_runs_remaining(self, X: np.ndarray) -> np.ndarray:
        """Predicts expected remaining runs."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before calling predict.")
        return np.maximum(0.0, self.model.predict(X))

    def evaluate_delivery(
        self,
        balls_rem: float,
        wkts_in_hand: int,
        curr_score: int,
        crr: float,
        venue_par: float
    ) -> Dict[str, Any]:
        """
        Evaluates a single delivery state in the first innings.
        """
        b_rem = float(np.clip(balls_rem, 0.0, float(MAX_BALLS)))
        w_in_hand = int(np.clip(wkts_in_hand, 0, 10))
        c_score = float(curr_score)
        c_crr = float(np.clip(crr, 0.0, 36.0))
        v_par = float(venue_par)

        x_feat = np.array([[b_rem, w_in_hand, c_score, c_crr, v_par]])
        pred_rem = float(self.predict_runs_remaining(x_feat)[0])
        pred_final = c_score + pred_rem
        sigma_rem = float(self.compute_uncertainty(b_rem))

        # Par-Deficit Risk
        z = (v_par - pred_final) / sigma_rem
        bps = float(np.clip(100.0 * norm.cdf(z), 0.0, 100.0))
        bops = float(np.clip(100.0 - bps, 0.0, 100.0))

        # Assign pressure tier
        if bps < PRESSURE_TIER_BOUNDS["Medium"]:
            tier = "Low"
        elif bps < PRESSURE_TIER_BOUNDS["High"]:
            tier = "Medium"
        elif bps < PRESSURE_TIER_BOUNDS["Extreme"]:
            tier = "High"
        else:
            tier = "Extreme"

        return {
            "predicted_runs_rem": pred_rem,
            "projected_final_score": pred_final,
            "residual_uncertainty_sigma": sigma_rem,
            "first_innings_par_deficit_risk_bps": bps,
            "bowler_pressure_score_bops": bops,
            "pressure_tier": tier
        }

    def evaluate_batch(
        self,
        balls_rem: np.ndarray,
        wkts_in_hand: np.ndarray,
        curr_score: np.ndarray,
        crr: np.ndarray,
        venue_par: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Batch vector evaluation across delivery arrays.
        """
        b_rem = np.clip(balls_rem, 0.0, float(MAX_BALLS))
        w_in_hand = np.clip(wkts_in_hand, 0, 10)
        c_score = np.array(curr_score, dtype=float)
        c_crr = np.clip(crr, 0.0, 36.0)
        v_par = np.array(venue_par, dtype=float)

        X = np.column_stack([b_rem, w_in_hand, c_score, c_crr, v_par])
        pred_rem = self.predict_runs_remaining(X)
        pred_final = c_score + pred_rem
        sigma_rem = self.compute_uncertainty(b_rem)

        z = (v_par - pred_final) / sigma_rem
        bps = np.clip(100.0 * norm.cdf(z), 0.0, 100.0)
        bops = np.clip(100.0 - bps, 0.0, 100.0)

        tiers = np.empty(len(bps), dtype=object)
        tiers[bps < PRESSURE_TIER_BOUNDS["Medium"]] = "Low"
        tiers[(bps >= PRESSURE_TIER_BOUNDS["Medium"]) & (bps < PRESSURE_TIER_BOUNDS["High"])] = "Medium"
        tiers[(bps >= PRESSURE_TIER_BOUNDS["High"]) & (bps < PRESSURE_TIER_BOUNDS["Extreme"])] = "High"
        tiers[bps >= PRESSURE_TIER_BOUNDS["Extreme"]] = "Extreme"

        return {
            "predicted_runs_rem": pred_rem,
            "projected_final_score": pred_final,
            "residual_uncertainty_sigma": sigma_rem,
            "first_innings_par_deficit_risk_bps": bps,
            "bowler_pressure_score_bops": bops,
            "pressure_tier": tiers
        }
