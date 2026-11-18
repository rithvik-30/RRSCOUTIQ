"""
Unit Tests for Expected Leverage Engine
Phase 4.4 Controlled Shadow-Mode Pilot
"""

import pytest
import numpy as np
from src.models.cspm.chase_win_probability import ChaseWinProbabilityModel
from src.models.cspm.outcome_model import ConditionalOutcomeModel
from src.models.cspm.leverage_engine import ExpectedLeverageEngine


@pytest.fixture
def leverage_engine():
    wp_model = ChaseWinProbabilityModel()
    # Mock classifier: sigmoid( (100 - runs_req) / 50 )
    class SimpleClassifier:
        def predict_proba(self, X):
            # Column 0 is runs_req
            r = X[:, 0]
            p = 1.0 / (1.0 + np.exp((r - 50.0) / 20.0))
            return np.column_stack([1.0 - p, p])
    wp_model.scaler.fit(np.random.randn(20, 8))
    wp_model.model = SimpleClassifier()
    wp_model.is_fitted = True

    outcome_model = ConditionalOutcomeModel()
    return ExpectedLeverageEngine(wp_model, outcome_model)


def test_leverage_state_transitions():
    """
    Verifies that state transitions obey physical cricket laws:
    - Dot: B decrements, R unchanged, W unchanged.
    - Single: B decrements, R decrements by 1, W unchanged.
    - Boundary Four: B decrements, R decrements by 4, W unchanged.
    - Wicket: B decrements, R unchanged, W decrements by 1.
    - Wide / No-ball: B preserves its value (re-bowled).
    """
    engine = ExpectedLeverageEngine(None, None)

    # 1. Dot
    r, b, w, c = engine.get_next_state("dot", runs_req=20, balls_rem=15, wkts_in_hand=5, crr=8.0)
    assert r == 20 and b == 14 and w == 5

    # 2. Single
    r, b, w, c = engine.get_next_state("one", runs_req=20, balls_rem=15, wkts_in_hand=5, crr=8.0)
    assert r == 19 and b == 14 and w == 5

    # 3. Four
    r, b, w, c = engine.get_next_state("four", runs_req=20, balls_rem=15, wkts_in_hand=5, crr=8.0)
    assert r == 16 and b == 14 and w == 5

    # 4. Wicket
    r, b, w, c = engine.get_next_state("wicket", runs_req=20, balls_rem=15, wkts_in_hand=5, crr=8.0)
    assert r == 20 and b == 14 and w == 4

    # 5. Wide (Illegal delivery: B does not decrement)
    r, b, w, c = engine.get_next_state("wide", runs_req=20, balls_rem=15, wkts_in_hand=5, crr=8.0)
    assert r == 19 and b == 15 and w == 5


def test_leverage_non_negativity(leverage_engine):
    """
    Expected leverage must be strictly non-negative.
    """
    res = leverage_engine.calculate_chase_leverage(runs_req=30, balls_rem=18, wkts_in_hand=6, crr=8.5)
    assert res["expected_leverage"] >= 0.0
    assert 0.0 <= res["current_wp"] <= 1.0


def test_terminal_state_zero_leverage(leverage_engine):
    """
    In terminal states, expected leverage must be strictly 0.0.
    """
    # 0 balls remaining
    res_b0 = leverage_engine.calculate_chase_leverage(runs_req=10, balls_rem=0, wkts_in_hand=4, crr=8.0)
    assert res_b0["expected_leverage"] == 0.0

    # 0 runs required (won)
    res_won = leverage_engine.calculate_chase_leverage(runs_req=0, balls_rem=12, wkts_in_hand=5, crr=8.0)
    assert res_won["expected_leverage"] == 0.0

    # 0 wickets in hand (all out)
    res_out = leverage_engine.calculate_chase_leverage(runs_req=15, balls_rem=24, wkts_in_hand=0, crr=7.0)
    assert res_out["expected_leverage"] == 0.0
