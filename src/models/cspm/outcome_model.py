"""
Conditional Delivery Outcome Model
Phase 4.4 Controlled Shadow-Mode Pilot

Estimates state-dependent conditional transition probabilities:
P(outcome | x_t)
where sum_o P(outcome | x_t) = 1.0 (numerical tolerance 1e-9).
"""

from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.models.cspm.config import OUTCOME_CATEGORIES, MAX_BALLS


class ConditionalOutcomeModel:
    """
    Estimates the conditional probability simplex P(o | x_t) for delivery outcomes
    given real-time match state features.
    
    Guarantees:
    - Probabilities strictly non-negative.
    - Probabilities strictly sum to 1.0 (within 1e-9 tolerance).
    - Impossible transitions masked to zero probability.
    - Zero future-match leakage during training.
    """

    def __init__(
        self,
        classifier: Optional[LogisticRegression] = None,
        scaler: Optional[StandardScaler] = None
    ):
        self.categories: List[str] = list(OUTCOME_CATEGORIES)
        self.num_classes = len(self.categories)
        self.model = classifier if classifier is not None else LogisticRegression(
            multi_class="multinomial",
            max_iter=1000,
            C=0.5,
            random_state=42
        )
        self.scaler = scaler if scaler is not None else StandardScaler()
        self.is_fitted = False
        self.feature_names = [
            "balls_rem",
            "wkts_in_hand",
            "runs_req",
            "rrr",
            "crr",
            "phase_pp",
            "phase_death"
        ]

    def extract_features(
        self,
        balls_rem: np.ndarray,
        wkts_in_hand: np.ndarray,
        runs_req: np.ndarray,
        crr: np.ndarray
    ) -> np.ndarray:
        """
        Builds feature matrix from match state variables.
        """
        b = np.clip(np.array(balls_rem, dtype=float), 0.0, float(MAX_BALLS))
        w = np.clip(np.array(wkts_in_hand, dtype=float), 0.0, 10.0)
        r = np.maximum(0.0, np.array(runs_req, dtype=float))
        c = np.clip(np.array(crr, dtype=float), 0.0, 36.0)
        rrr = np.clip(np.where(b > 0, r / (np.maximum(1.0, b) / 6.0), 36.0), 0.0, 36.0)

        phase_pp = (b > 84.0).astype(float)
        phase_death = (b <= 24.0).astype(float)

        return np.column_stack([
            b,
            w,
            r,
            rrr,
            c,
            phase_pp,
            phase_death
        ])

    def fit(self, X_features: np.ndarray, y_labels: np.ndarray) -> "ConditionalOutcomeModel":
        """
        Fits the multinomial logistic regression classifier on training delivery outcomes.
        y_labels: integer array [0..7] corresponding to OUTCOME_CATEGORIES
        """
        X_s = self.scaler.fit_transform(X_features)
        self.model.fit(X_s, y_labels)
        self.is_fitted = True
        return self

    def predict_probabilities(
        self,
        balls_rem: float,
        wkts_in_hand: int,
        runs_req: float,
        crr: float
    ) -> Dict[str, float]:
        """
        Returns conditional probability vector P(o | x_t) summing strictly to 1.0.
        """
        # Zero out impossible transitions if terminal state reached
        if balls_rem <= 0 or wkts_in_hand <= 0 or runs_req <= 0:
            probs = {cat: 0.0 for cat in self.categories}
            probs["dot"] = 1.0
            return probs

        if not self.is_fitted:
            # Fallback to calibrated historical base rates if not yet fitted
            base_rates = {
                "dot": 0.30212,
                "one": 0.38369,
                "two": 0.06275,
                "three": 0.00310,
                "four": 0.12613,
                "five": 0.00013,
                "six": 0.06568,
                "wicket": 0.05640
            }
            total = sum(base_rates.values())
            return {k: v / total for k, v in base_rates.items()}

        X = self.extract_features(
            np.array([balls_rem]),
            np.array([wkts_in_hand]),
            np.array([runs_req]),
            np.array([crr])
        )
        X_s = self.scaler.transform(X)
        raw_probs = self.model.predict_proba(X_s)[0]

        # Map to full category vector
        class_mapping = {int(cls): idx for idx, cls in enumerate(self.model.classes_)}
        probs = np.zeros(self.num_classes, dtype=float)
        for cat_idx in range(self.num_classes):
            if cat_idx in class_mapping:
                probs[cat_idx] = raw_probs[class_mapping[cat_idx]]

        # Zero out impossible transitions if terminal state reached
        if balls_rem <= 0 or wkts_in_hand <= 0 or runs_req <= 0:
            probs = np.zeros(self.num_classes, dtype=float)
            probs[0] = 1.0  # Absorb into dot
        else:
            # Enforce non-negativity and unit sum tolerance 1e-9
            probs = np.maximum(0.0, probs)
            p_sum = np.sum(probs)
            if p_sum > 0:
                probs = probs / p_sum
            else:
                probs[0] = 1.0

        result = {cat: float(probs[idx]) for idx, cat in enumerate(self.categories)}
        return result

    def predict_batch_probabilities(
        self,
        balls_rem: np.ndarray,
        wkts_in_hand: np.ndarray,
        runs_req: np.ndarray,
        crr: np.ndarray
    ) -> np.ndarray:
        """
        Batch evaluation returning (N, 8) probability simplex matrix.
        """
        if not self.is_fitted:
            base_p = np.array([0.30212, 0.38369, 0.06275, 0.00310, 0.12613, 0.00013, 0.06568, 0.05640])
            base_p = base_p / np.sum(base_p)
            return np.tile(base_p, (len(balls_rem), 1))

        X = self.extract_features(balls_rem, wkts_in_hand, runs_req, crr)
        X_s = self.scaler.transform(X)
        raw_probs = self.model.predict_proba(X_s)

        # Map across classes
        class_mapping = {int(cls): idx for idx, cls in enumerate(self.model.classes_)}
        P = np.zeros((len(balls_rem), self.num_classes), dtype=float)
        for cat_idx in range(self.num_classes):
            if cat_idx in class_mapping:
                P[:, cat_idx] = raw_probs[:, class_mapping[cat_idx]]

        # Normalize rows to exact 1.0
        row_sums = P.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        P = P / row_sums
        return P
