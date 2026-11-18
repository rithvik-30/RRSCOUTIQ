"""
Chase Win Probability Model
Phase 4.4 Controlled Shadow-Mode Pilot

Implements the validated 8-feature Logistic Win Probability model:
WP(x_t) = P(Batting Team Wins | R, B, W, RRR, CRR)
BPS = 100 * (1 - WP)
BoPS = 100 * WP
"""

from typing import Dict, Any, Optional, List, Union
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.models.cspm.config import (
    CHASE_FEATURE_COLS,
    PRESSURE_TIER_BOUNDS,
    MAX_BALLS
)


class ChaseWinProbabilityModel:
    """
    Computes real-time win probability during the 2nd-innings chase.
    
    Guarantees:
    - Target achieved (R <= 0) => WP = 1.0.
    - All out (W <= 0 and R > 0) or balls exhausted (B <= 0 and R > 0) => WP = 0.0.
    - Features scaled strictly with training-fit StandardScaler.
    - Out-of-bounds clipping strictly in [0.0, 1.0].
    """

    def __init__(
        self,
        classifier: Optional[LogisticRegression] = None,
        scaler: Optional[StandardScaler] = None
    ):
        self.feature_cols: List[str] = list(CHASE_FEATURE_COLS)
        self.model = classifier if classifier is not None else LogisticRegression(
            max_iter=1000,
            C=0.5,
            random_state=42
        )
        self.scaler = scaler if scaler is not None else StandardScaler()
        self.is_fitted = False

    @staticmethod
    def construct_features(
        runs_req: Union[float, np.ndarray],
        balls_rem: Union[float, np.ndarray],
        wkts_in_hand: Union[float, np.ndarray],
        crr: Union[float, np.ndarray]
    ) -> np.ndarray:
        """
        Derives the 8 validated chase features from raw state inputs.
        """
        r = np.maximum(1.0, np.array(runs_req, dtype=float))
        b = np.maximum(1.0, np.array(balls_rem, dtype=float))
        w = np.clip(np.array(wkts_in_hand, dtype=float), 0.0, 10.0)
        c_crr = np.clip(np.array(crr, dtype=float), 0.0, 36.0)

        rrr = np.clip(r / (b / 6.0), 0.0, 36.0)
        rrr_minus_crr = rrr - c_crr
        balls_per_wicket = np.clip(b / (w + 1.0), 0.0, 60.0)
        runs_per_wicket = np.clip(r / (w + 1.0), 0.0, 100.0)

        return np.column_stack([
            r,
            b,
            w,
            rrr,
            c_crr,
            rrr_minus_crr,
            balls_per_wicket,
            runs_per_wicket
        ])

    def fit(self, X: np.ndarray, y: np.ndarray) -> "ChaseWinProbabilityModel":
        """
        Fits StandardScaler and Logistic Regression on training features.
        """
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_fitted = True
        return self

    def predict_win_probability(
        self,
        runs_req: Union[float, np.ndarray],
        balls_rem: Union[float, np.ndarray],
        wkts_in_hand: Union[float, np.ndarray],
        crr: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """
        Calculates calibrated win probability for single values or arrays.
        Enforces physical boundary invariants.
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict_win_probability.")

        is_scalar = np.isscalar(runs_req)
        r = np.atleast_1d(runs_req)
        b = np.atleast_1d(balls_rem)
        w = np.atleast_1d(wkts_in_hand)
        c = np.atleast_1d(crr)

        X = self.construct_features(r, b, w, c)
        X_s = self.scaler.transform(X)
        probs = self.model.predict_proba(X_s)[:, 1]

        # Enforce exact physical boundaries
        probs[r <= 0] = 1.0
        probs[(w <= 0) & (r > 0)] = 0.0
        probs[(b <= 0) & (r > 0)] = 0.0

        probs = np.clip(probs, 0.0, 1.0)
        return float(probs[0]) if is_scalar else probs

    def evaluate_delivery(
        self,
        runs_req: float,
        balls_rem: float,
        wkts_in_hand: int,
        crr: float
    ) -> Dict[str, Any]:
        """
        Evaluates a single delivery state in the 2nd innings.
        """
        wp = float(self.predict_win_probability(runs_req, balls_rem, wkts_in_hand, crr))
        bps = float(np.clip(100.0 * (1.0 - wp), 0.0, 100.0))
        bops = float(np.clip(100.0 * wp, 0.0, 100.0))

        if bps < PRESSURE_TIER_BOUNDS["Medium"]:
            tier = "Low"
        elif bps < PRESSURE_TIER_BOUNDS["High"]:
            tier = "Medium"
        elif bps < PRESSURE_TIER_BOUNDS["Extreme"]:
            tier = "High"
        else:
            tier = "Extreme"

        return {
            "batting_win_probability": wp,
            "chase_loss_risk_bps": bps,
            "bowler_pressure_score_bops": bops,
            "pressure_tier": tier
        }
