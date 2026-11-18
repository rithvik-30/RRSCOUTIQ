"""
Unit Tests for First-Innings Pressure Engine
Phase 4.4 Controlled Shadow-Mode Pilot
"""

import pytest
import numpy as np
from src.models.cspm.first_innings import FirstInningsPressureEngine
from src.models.cspm.config import SIGMA_0, MIN_UNCERTAINTY


class MockRegressor:
    """Mock regressor predicting remaining runs based on a simple linear formula."""
    def fit(self, X, y):
        pass
    def predict(self, X):
        # Remaining runs = balls_rem * 1.35
        return X[:, 0] * 1.35


@pytest.fixture
def fitted_engine():
    engine = FirstInningsPressureEngine(sigma_0=34.0, min_uncertainty=5.0, regressor=MockRegressor())
    # Mock fit
    engine.is_fitted = True
    return engine


def test_bps_bops_complementarity(fitted_engine):
    """
    BPS and BoPS must sum to exactly 100.0 across all deliveries.
    """
    test_cases = [
        {"balls_rem": 120, "wkts_in_hand": 10, "curr_score": 0, "crr": 0.0, "venue_par": 170.0},
        {"balls_rem": 60, "wkts_in_hand": 7, "curr_score": 85, "crr": 8.5, "venue_par": 175.0},
        {"balls_rem": 12, "wkts_in_hand": 3, "curr_score": 110, "crr": 6.1, "venue_par": 165.0},
        {"balls_rem": 0, "wkts_in_hand": 5, "curr_score": 190, "crr": 9.5, "venue_par": 170.0},
    ]

    for tc in test_cases:
        res = fitted_engine.evaluate_delivery(**tc)
        bps = res["first_innings_par_deficit_risk_bps"]
        bops = res["bowler_pressure_score_bops"]
        assert abs((bps + bops) - 100.0) < 1e-6, f"Failed complementarity on case {tc}"
        assert 0.0 <= bps <= 100.0
        assert 0.0 <= bops <= 100.0


def test_monotonicity_score_vs_pressure(fitted_engine):
    """
    Higher current score with fixed balls and wickets must produce LOWER BPS.
    """
    res_low_score = fitted_engine.evaluate_delivery(balls_rem=30, wkts_in_hand=6, curr_score=100, crr=6.67, venue_par=175.0)
    res_high_score = fitted_engine.evaluate_delivery(balls_rem=30, wkts_in_hand=6, curr_score=150, crr=10.0, venue_par=175.0)

    assert res_low_score["first_innings_par_deficit_risk_bps"] > res_high_score["first_innings_par_deficit_risk_bps"], \
        "BPS did not decrease when batting side was further ahead of par!"


def test_uncertainty_clamping(fitted_engine):
    """
    Uncertainty sigma_rem must never drop below MIN_UNCERTAINTY (5.0).
    """
    sig_zero = fitted_engine.compute_uncertainty(0.0)
    sig_one = fitted_engine.compute_uncertainty(1.0)
    sig_120 = fitted_engine.compute_uncertainty(120.0)

    assert sig_zero == 5.0
    assert sig_one >= 5.0
    assert sig_120 == pytest.approx(34.0, abs=1e-5)


def test_pressure_tiers(fitted_engine):
    """
    Verifies proper assignment of pressure tiers (Low, Medium, High, Extreme).
    """
    # Crushing lead: curr_score = 220 at ball 30 => BPS ~ 0.0 => Low
    res_lead = fitted_engine.evaluate_delivery(balls_rem=30, wkts_in_hand=9, curr_score=220, crr=14.0, venue_par=170.0)
    assert res_lead["pressure_tier"] == "Low"

    # Severe collapse: curr_score = 50 at ball 30 => BPS ~ 100.0 => Extreme
    res_collapse = fitted_engine.evaluate_delivery(balls_rem=30, wkts_in_hand=2, curr_score=50, crr=3.3, venue_par=180.0)
    assert res_collapse["pressure_tier"] == "Extreme"
