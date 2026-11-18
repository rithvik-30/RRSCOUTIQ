"""
Unit Tests for Chase Win Probability Model
Phase 4.4 Controlled Shadow-Mode Pilot
"""

import pytest
import numpy as np
from src.models.cspm.chase_win_probability import ChaseWinProbabilityModel


class MockClassifier:
    """Mock logistic classifier for win probability."""
    def predict_proba(self, X):
        # Higher wickets and lower RRR yield higher WP
        # Simple sigmoid approximation
        scores = 0.5 + 0.05 * X[:, 2] - 0.02 * X[:, 3]
        scores = np.clip(scores, 0.01, 0.99)
        return np.column_stack([1.0 - scores, scores])


@pytest.fixture
def fitted_chase_model():
    model = ChaseWinProbabilityModel()
    # Mock fitting
    X_dummy = np.random.randn(20, 8)
    y_dummy = np.random.randint(0, 2, size=20)
    model.scaler.fit(X_dummy)
    model.model = MockClassifier()
    model.is_fitted = True
    return model


def test_chase_boundary_conditions(fitted_chase_model):
    """
    Physical boundary conditions must be strictly preserved:
    - Target achieved (runs_req <= 0) => WP = 1.0
    - All out (wkts_in_hand <= 0 and runs_req > 0) => WP = 0.0
    - Balls exhausted (balls_rem <= 0 and runs_req > 0) => WP = 0.0
    """
    # 1. Target reached
    wp_won = fitted_chase_model.predict_win_probability(runs_req=0, balls_rem=24, wkts_in_hand=6, crr=8.5)
    assert wp_won == 1.0

    # 2. All out
    wp_allout = fitted_chase_model.predict_win_probability(runs_req=15, balls_rem=18, wkts_in_hand=0, crr=7.0)
    assert wp_allout == 0.0

    # 3. Balls exhausted
    wp_overs_done = fitted_chase_model.predict_win_probability(runs_req=10, balls_rem=0, wkts_in_hand=4, crr=8.0)
    assert wp_overs_done == 0.0


def test_chase_bps_bops_complementarity(fitted_chase_model):
    """
    In the chase, BPS = 100*(1-WP) and BoPS = 100*WP, summing to 100.0.
    """
    res = fitted_chase_model.evaluate_delivery(runs_req=45, balls_rem=30, wkts_in_hand=5, crr=8.0)
    bps = res["chase_loss_risk_bps"]
    bops = res["bowler_pressure_score_bops"]
    wp = res["batting_win_probability"]

    assert abs((bps + bops) - 100.0) < 1e-6
    assert abs(bops - wp * 100.0) < 1e-6
    assert 0.0 <= wp <= 1.0


def test_monotonicity_required_runs(fitted_chase_model):
    """
    Requiring more runs with fixed balls and wickets must reduce batting WP.
    """
    wp_easy = fitted_chase_model.predict_win_probability(runs_req=20, balls_rem=30, wkts_in_hand=6, crr=8.0)
    wp_hard = fitted_chase_model.predict_win_probability(runs_req=70, balls_rem=30, wkts_in_hand=6, crr=8.0)

    assert wp_easy > wp_hard, "Win probability did not decrease when required runs increased!"
