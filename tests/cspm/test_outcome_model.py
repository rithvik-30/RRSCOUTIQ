"""
Unit Tests for Conditional Outcome Simplex Model
Phase 4.4 Controlled Shadow-Mode Pilot
"""

import pytest
import numpy as np
from src.models.cspm.outcome_model import ConditionalOutcomeModel
from src.models.cspm.config import OUTCOME_CATEGORIES


def test_simplex_unit_sum_invariant():
    """
    Every predicted conditional outcome distribution must sum strictly to 1.0 (tol 1e-9).
    """
    model = ConditionalOutcomeModel()
    # Test unfitted fallback and fitted predictions
    probs_dict = model.predict_probabilities(balls_rem=48, wkts_in_hand=6, runs_req=65, crr=8.0)

    total_prob = sum(probs_dict.values())
    assert abs(total_prob - 1.0) < 1e-9, f"Simplex sum was {total_prob}, violated 1e-9 tolerance!"
    for cat, p in probs_dict.items():
        assert p >= 0.0, f"Negative probability found for {cat}: {p}"


def test_batch_simplex_unit_sum():
    """
    Batch evaluation row sums must strictly equal 1.0.
    """
    model = ConditionalOutcomeModel()
    b = np.array([12, 36, 60, 90, 114])
    w = np.array([2, 5, 7, 9, 10])
    r = np.array([25, 50, 75, 120, 160])
    c = np.array([7.5, 8.0, 8.5, 9.0, 6.0])

    P = model.predict_batch_probabilities(b, w, r, c)
    assert P.shape == (5, len(OUTCOME_CATEGORIES))
    row_sums = P.sum(axis=1)
    np.testing.assert_allclose(row_sums, 1.0, atol=1e-9)


def test_impossible_transitions():
    """
    When match has terminated, transitions to scoring runs or wickets are impossible.
    """
    model = ConditionalOutcomeModel()
    # Target reached: runs_req = 0
    p_term = model.predict_probabilities(balls_rem=24, wkts_in_hand=6, runs_req=0, crr=8.5)
    assert p_term["dot"] == 1.0
    assert p_term["four"] == 0.0
    assert p_term["wicket"] == 0.0
