"""
Unit Tests for Unified CricketStatePressureEngine
Phase 4.4 Controlled Shadow-Mode Pilot
"""

import pytest
import pandas as pd
import numpy as np

from src.models.cspm.venue_par import ChronologicalVenueParEstimator
from src.models.cspm.first_innings import FirstInningsPressureEngine
from src.models.cspm.chase_win_probability import ChaseWinProbabilityModel
from src.models.cspm.outcome_model import ConditionalOutcomeModel
from src.models.cspm.leverage_engine import ExpectedLeverageEngine
from src.models.cspm.pressure_engine import CricketStatePressureEngine
from src.models.cspm.config import SUPER_OVER_FIXED_SCORE


@pytest.fixture
def unified_engine():
    # Setup mock components
    v_estimator = ChronologicalVenueParEstimator()
    sample_df = pd.DataFrame([
        {"match_id": 1, "match_date": "2024-01-01", "venue_id": 10, "comp_id": 1, "first_innings_runs": 170.0, "is_complete_first_innings": True}
    ])
    v_estimator.fit_database(sample_df)

    class Mock1st:
        def evaluate_delivery(self, balls_rem, wkts_in_hand, curr_score, crr, venue_par):
            return {
                "projected_final_score": curr_score + balls_rem * 1.3,
                "residual_uncertainty_sigma": 20.0,
                "first_innings_par_deficit_risk_bps": 45.0,
                "bowler_pressure_score_bops": 55.0,
                "pressure_tier": "Medium"
            }
        def compute_uncertainty(self, b):
            return 20.0

    class MockChase:
        def evaluate_delivery(self, runs_req, balls_rem, wkts_in_hand, crr):
            return {
                "batting_win_probability": 0.60,
                "chase_loss_risk_bps": 40.0,
                "bowler_pressure_score_bops": 60.0,
                "pressure_tier": "Medium"
            }
        def predict_win_probability(self, r, b, w, c):
            return 0.60

    first_inn = Mock1st()
    chase = MockChase()
    outcome = ConditionalOutcomeModel()
    leverage = ExpectedLeverageEngine(chase, outcome)

    return CricketStatePressureEngine(
        venue_par_estimator=v_estimator,
        first_innings_engine=first_inn,
        chase_wp_model=chase,
        outcome_model=outcome,
        leverage_engine=leverage
    )


def test_unified_super_over_handling(unified_engine):
    """
    Super Overs must strictly return fixed 75.0 / 75.0 terminal crunch.
    """
    res = unified_engine.evaluate_delivery(
        innings=1,
        balls_rem=6,
        wkts_in_hand=2,
        curr_score=10,
        crr=10.0,
        is_super_over=True
    )
    assert res["is_super_over"] is True
    assert res["bps"] == SUPER_OVER_FIXED_SCORE
    assert res["bops"] == SUPER_OVER_FIXED_SCORE
    assert res["pressure_tier"] == "High"


def test_unified_innings_routing(unified_engine):
    """
    Innings 1 must route to First-Innings engine; Innings 2 must route to Chase engine.
    """
    # 1st Innings
    res1 = unified_engine.evaluate_delivery(
        innings=1,
        balls_rem=60,
        wkts_in_hand=8,
        curr_score=80,
        crr=8.0,
        venue_id=10,
        comp_id=1
    )
    assert res1["innings"] == 1
    assert "projected_final_score" in res1
    assert res1["bps"] == 45.0

    # 2nd Innings
    res2 = unified_engine.evaluate_delivery(
        innings=2,
        balls_rem=40,
        wkts_in_hand=6,
        curr_score=90,
        crr=8.0,
        runs_req=55
    )
    assert res2["innings"] == 2
    assert "win_probability" in res2
    assert res2["bps"] == 40.0
