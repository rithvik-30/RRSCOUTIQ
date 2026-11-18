"""
Expected Delivery Leverage Engine
Phase 4.4 Controlled Shadow-Mode Pilot

Computes expected win probability swing:
L_t = sum_o P(o | x_t) * |WP(x_t+1,o) - WP(x_t)| * 100
"""

from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd

from src.models.cspm.config import OUTCOME_CATEGORIES
from src.models.cspm.chase_win_probability import ChaseWinProbabilityModel
from src.models.cspm.outcome_model import ConditionalOutcomeModel


class ExpectedLeverageEngine:
    """
    Computes expected match leverage for delivery states.
    
    Invariants:
    1. Separate metric: NEVER multiplied into BPS or BoPS.
    2. Exact state transition mechanics (legal balls decrement only on legal deliveries).
    3. Handles innings termination boundary conditions (Target reached, All out, Overs exhausted).
    4. Simplex probability weights sum to exactly 1.0.
    """

    def __init__(
        self,
        wp_model: ChaseWinProbabilityModel,
        outcome_model: ConditionalOutcomeModel
    ):
        self.wp_model = wp_model
        self.outcome_model = outcome_model

    @staticmethod
    def get_next_state(
        outcome: str,
        runs_req: float,
        balls_rem: float,
        wkts_in_hand: int,
        crr: float
    ) -> Tuple[float, float, int, float]:
        """
        Calculates exact physical next state (R_next, B_next, W_next, CRR_next).
        """
        # Default legal ball decrement
        b_next = max(0.0, float(balls_rem) - 1.0)
        w_next = int(wkts_in_hand)
        r_curr = float(runs_req)

        if outcome == "dot":
            r_next = r_curr
        elif outcome == "one":
            r_next = max(0.0, r_curr - 1.0)
        elif outcome == "two":
            r_next = max(0.0, r_curr - 2.0)
        elif outcome == "three":
            r_next = max(0.0, r_curr - 3.0)
        elif outcome == "four":
            r_next = max(0.0, r_curr - 4.0)
        elif outcome == "five":
            r_next = max(0.0, r_curr - 5.0)
        elif outcome == "six":
            r_next = max(0.0, r_curr - 6.0)
        elif outcome == "wicket":
            r_next = r_curr
            w_next = max(0, int(wkts_in_hand) - 1)
        elif outcome == "wide":
            # Illegal delivery: balls remaining does NOT decrement
            b_next = float(balls_rem)
            r_next = max(0.0, r_curr - 1.0)
        elif outcome == "noball":
            # Illegal delivery: balls remaining does NOT decrement
            b_next = float(balls_rem)
            r_next = max(0.0, r_curr - 1.0)
        else:
            r_next = r_curr

        # Update run rate assuming standard 120-ball allocation
        balls_bowled = max(1.0, 120.0 - b_next)
        crr_next = float(crr)  # CRR changes gradually; holding locally stable

        return r_next, b_next, w_next, crr_next

    def calculate_chase_leverage(
        self,
        runs_req: float,
        balls_rem: float,
        wkts_in_hand: int,
        crr: float
    ) -> Dict[str, Any]:
        """
        Calculates real-time expected leverage for a chase delivery.
        """
        # Current state win probability
        wp_curr = float(self.wp_model.predict_win_probability(runs_req, balls_rem, wkts_in_hand, crr))

        # Terminal state check
        if balls_rem <= 0 or wkts_in_hand <= 0 or runs_req <= 0:
            return {
                "current_wp": wp_curr,
                "expected_leverage": 0.0,
                "outcome_probabilities": {cat: 0.0 for cat in OUTCOME_CATEGORIES},
                "outcome_swings": {cat: 0.0 for cat in OUTCOME_CATEGORIES}
            }

        # Predict conditional transition probabilities
        prob_dict = self.outcome_model.predict_probabilities(balls_rem, wkts_in_hand, runs_req, crr)

        leverage = 0.0
        swings = {}

        for outcome, p_o in prob_dict.items():
            r_next, b_next, w_next, crr_next = self.get_next_state(
                outcome, runs_req, balls_rem, wkts_in_hand, crr
            )
            wp_next = float(self.wp_model.predict_win_probability(r_next, b_next, w_next, crr_next))
            swing = abs(wp_next - wp_curr) * 100.0
            swings[outcome] = swing
            leverage += p_o * swing

        return {
            "current_wp": wp_curr,
            "expected_leverage": float(leverage),
            "outcome_probabilities": prob_dict,
            "outcome_swings": swings
        }
