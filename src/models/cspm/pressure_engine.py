"""
Unified Cricket State Pressure Model (CSPM) Engine
Phase 4.4 Controlled Shadow-Mode Pilot

Provides a unified interface across 1st innings, 2nd innings, and Super Overs:
- Evaluates BPS (Batter Pressure Score)
- Evaluates BoPS (Bowler Pressure Score)
- Assigns probabilistic pressure tiers
- Calculates Expected Delivery Leverage (L_t)
"""

from typing import Dict, Any, Optional, List, Union
import numpy as np
import pandas as pd

from src.models.cspm.config import (
    SUPER_OVER_FIXED_SCORE,
    PRESSURE_TIER_BOUNDS,
    OFFICIAL_SCOUTING_PRESSURE_CUTOFF
)
from src.models.cspm.venue_par import ChronologicalVenueParEstimator
from src.models.cspm.first_innings import FirstInningsPressureEngine
from src.models.cspm.chase_win_probability import ChaseWinProbabilityModel
from src.models.cspm.outcome_model import ConditionalOutcomeModel
from src.models.cspm.leverage_engine import ExpectedLeverageEngine


class CricketStatePressureEngine:
    """
    Unified multi-innings Pressure and Leverage engine.
    """

    def __init__(
        self,
        venue_par_estimator: ChronologicalVenueParEstimator,
        first_innings_engine: FirstInningsPressureEngine,
        chase_wp_model: ChaseWinProbabilityModel,
        outcome_model: ConditionalOutcomeModel,
        leverage_engine: ExpectedLeverageEngine
    ):
        self.venue_par_estimator = venue_par_estimator
        self.first_innings_engine = first_innings_engine
        self.chase_wp_model = chase_wp_model
        self.outcome_model = outcome_model
        self.leverage_engine = leverage_engine

    def evaluate_delivery(
        self,
        innings: int,
        balls_rem: float,
        wkts_in_hand: int,
        curr_score: int,
        crr: float,
        runs_req: Optional[float] = None,
        match_date: Optional[pd.Timestamp] = None,
        venue_id: Optional[int] = None,
        comp_id: Optional[int] = None,
        current_match_id: Optional[int] = None,
        is_super_over: bool = False
    ) -> Dict[str, Any]:
        """
        Unified delivery evaluation.
        """
        # 1. Super Over Edge Case
        if is_super_over:
            return {
                "innings": innings,
                "is_super_over": True,
                "bps": float(SUPER_OVER_FIXED_SCORE),
                "bops": float(SUPER_OVER_FIXED_SCORE),
                "pressure_tier": "High",
                "expected_leverage": 25.0,  # Elevated tiebreaker leverage
                "venue_par": None,
                "venue_par_source": "super_over",
                "win_probability": 0.50
            }

        # 2. First-Innings Evaluation (Par-Deficit Risk)
        if innings == 1:
            par_info = self.venue_par_estimator.estimate_par(
                match_date=match_date or pd.Timestamp("2026-01-01"),
                venue_id=venue_id or 0,
                comp_id=comp_id or 0,
                current_match_id=current_match_id
            )
            v_par = par_info["venue_par"]
            v_source = par_info["source"]

            eval_res = self.first_innings_engine.evaluate_delivery(
                balls_rem=balls_rem,
                wkts_in_hand=wkts_in_hand,
                curr_score=curr_score,
                crr=crr,
                venue_par=v_par
            )
            bps = eval_res["first_innings_par_deficit_risk_bps"]
            bops = eval_res["bowler_pressure_score_bops"]
            tier = eval_res["pressure_tier"]

            # First-innings leverage proxy (expected runs swing scaled)
            leverage = float(self.first_innings_engine.compute_uncertainty(balls_rem) / 5.0)

            return {
                "innings": 1,
                "is_super_over": False,
                "bps": bps,
                "bops": bops,
                "pressure_tier": tier,
                "expected_leverage": leverage,
                "venue_par": v_par,
                "venue_par_source": v_source,
                "projected_final_score": eval_res["projected_final_score"],
                "residual_uncertainty_sigma": eval_res["residual_uncertainty_sigma"]
            }

        # 3. Second-Innings Evaluation (Chase Win Probability)
        r_req = float(runs_req) if runs_req is not None else 1.0
        chase_eval = self.chase_wp_model.evaluate_delivery(
            runs_req=r_req,
            balls_rem=balls_rem,
            wkts_in_hand=wkts_in_hand,
            crr=crr
        )
        wp = chase_eval["batting_win_probability"]
        bps = chase_eval["chase_loss_risk_bps"]
        bops = chase_eval["bowler_pressure_score_bops"]
        tier = chase_eval["pressure_tier"]

        # Expected leverage via 8-outcome transition simplex
        lev_res = self.leverage_engine.calculate_chase_leverage(
            runs_req=r_req,
            balls_rem=balls_rem,
            wkts_in_hand=wkts_in_hand,
            crr=crr
        )
        leverage = lev_res["expected_leverage"]

        return {
            "innings": 2,
            "is_super_over": False,
            "bps": bps,
            "bops": bops,
            "pressure_tier": tier,
            "expected_leverage": leverage,
            "win_probability": wp,
            "venue_par": None,
            "venue_par_source": "chase_state",
            "outcome_probabilities": lev_res.get("outcome_probabilities", {}),
            "outcome_swings": lev_res.get("outcome_swings", {})
        }
