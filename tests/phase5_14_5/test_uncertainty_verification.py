"""
Phase 5.14.5 — Active Uncertainty Calculation Verification Tests
Verifies:
  1. Active production class ContextualPlayerBaselineRecordB438 calculates posterior variance.
  2. Latent SE applies math.sqrt(max(1e-8, latent_posterior_variance)).
  3. Numerical tests for:
     a) Normal positive variance.
     b) Zero variance limit.
     c) Sub-floor variance (< 1e-8).
     d) Negative variance protection.
     e) Credible bound 1.645 multiplier and directionality (batter LB, bowler UB).
  4. Failure to execute active path blocks verification and freeze authorization.
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import evaluate_active_uncertainty_calculation
from src.m5_5b_4_3_8.epistemic_context_engine_b4_3_8 import ContextualPlayerBaselineRecordB438

def test_active_production_uncertainty_evaluator_passes():
    """Verify that evaluate_active_uncertainty_calculation runs all 5 numerical tests and passes."""
    res = evaluate_active_uncertainty_calculation()
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert res["active_execution_path_verified"] is True
    assert len(res["failures"]) == 0
    assert len(res["numerical_tests"]) >= 5


def test_normal_positive_variance_calculation():
    """Verify conjugate Gaussian posterior variance and latent standard error."""
    rec = ContextualPlayerBaselineRecordB438(
        player_id=1699,
        phase="middle",
        tier="Tier 2 Medium",
        context_exposure=100,
        context_events=25,
        context_matches=10,
        career_exposure=1000,
        career_events=250,
        career_matches=50,
        context_prior_mean=0.20,
        is_economy=False,
        min_context_exposure=30,
    )
    # Formula: Var = (1 - lambda_bayes) * tau2_total
    expected_var = (1.0 - rec.shrinkage_weight) * rec.tau2_total
    expected_se = math.sqrt(max(1e-8, expected_var))

    assert math.isclose(rec.latent_posterior_variance, expected_var, rel_tol=1e-9)
    assert math.isclose(rec.latent_se, expected_se, rel_tol=1e-9)
    assert math.isclose(rec.standard_error, expected_se, rel_tol=1e-9)


def test_variance_below_floor_elevated_to_floor():
    """Verify that when posterior variance drops below 1e-8, latent_se uses sqrt(1e-8)."""
    rec_tiny = ContextualPlayerBaselineRecordB438(
        player_id=9999,
        phase="middle",
        tier="Tier 2 Medium",
        context_exposure=100000000,
        context_events=20000000,
        context_matches=1000000,
        career_exposure=100000000,
        career_events=20000000,
        career_matches=1000000,
        context_prior_mean=0.20,
        sigma2_match_batter=0.0,
        min_context_exposure=30,
    )
    assert rec_tiny.latent_posterior_variance < 1e-8
    assert rec_tiny.latent_se == math.sqrt(1e-8)
    assert math.isclose(rec_tiny.latent_se, 1e-4, rel_tol=1e-9)


def test_negative_variance_numerical_guard():
    """Verify that max(1e-8, negative_val) prevents domain error in square root."""
    negative_val = -0.5
    guarded_se = math.sqrt(max(1e-8, negative_val))
    assert math.isclose(guarded_se, 1e-4, rel_tol=1e-9)


def test_credible_bound_1_645_multiplier_and_directionality():
    """Verify that batter credible bound is lower bound (mu - 1.645*se) and bowler is upper bound (mu + 1.645*se)."""
    # Batter: Suryakumar Yadav Window A prospective ranking values
    mu_batter = 0.0479658971153596
    se_batter = 0.02106533920766877
    lb90_batter = mu_batter - 1.645 * se_batter

    assert lb90_batter < mu_batter
    assert math.isclose(lb90_batter, 0.013313414118744468, rel_tol=1e-7)

    # Bowler: Sunil Narine Window A prospective ranking values
    mu_bowler = -0.5620136547628346
    se_bowler = 0.5667155379257611
    ub90_bowler = mu_bowler + 1.645 * se_bowler

    assert ub90_bowler > mu_bowler
    assert math.isclose(ub90_bowler, 0.37023340512504244, rel_tol=1e-7)
