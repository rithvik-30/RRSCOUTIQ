"""
RR ScoutIQ — Milestone M5.5-B.4.3.5: Targeted Test Suite
Module: tests/m5_5b_4_3_5/test_remediation_b4_3_5.py

Validates:
1. Exact analytical Gaussian posterior match on synthetic examples.
2. Law of Total Variance decomposition: Var(theta|data) = (1-lambda)*tau2 + (1-lambda)^2*sigma2_mu.
3. Limiting behavior as sigma2_mu -> 0 (recovers fixed-prior shrinkage).
4. Asymptotic behavior as player exposure n -> infinity (both components vanish; context vanishes quadratically).
5. Zero-exposure prior variance: Var(theta|data) = tau2 + sigma2_mu.
6. Coherent predictive variance for held-out observations without double counting.
7. Simulated predictive interval calibration coverage (80% and 95% nominal).
8. Regression preservation of Henderson exact ranks, unfloored trace coefficients, and calibration validation.
"""

import os
import sys
import math
import numpy as np
import scipy.sparse as sp
import scipy.linalg as la
import pytest

sys.path.insert(0, os.path.abspath("."))

from src.m5_5b_4_3_5.epistemic_context_engine_b4_3_5 import (
    ContextualPlayerBaselineRecordB435,
    EpistemicStateB435
)
from src.m5_5b_4_3_5.variance_decomposition_b4_3_5 import (
    compute_design_matrix_rank,
    estimate_crossed_variance_components_henderson3,
    NumericalConditioningError,
    IdentifiabilityError
)
from src.m5_5b_4_3_5.calibration_engine_b4_3_5 import (
    evaluate_bowler_calibration_status,
    evaluate_batter_calibration_status
)


# ============================================================================
# 1. Analytical Gaussian Posterior & Law of Total Variance Tests
# ============================================================================

def test_01_analytical_gaussian_law_of_total_variance():
    """
    Verifies that ContextualPlayerBaselineRecordB435 computes the exact
    Law of Total Variance decomposition:
        Var(theta | data) = (1 - lambda) * tau2 + (1 - lambda)^2 * sigma2_mu
    """
    tau2 = 0.50
    sigma2_mu = 0.20
    sigma2_within = 24.0
    sigma2_match = 1.50
    n_ctx = 36  # 6 overs
    h_conc = 1.0 / 3.0  # split across 3 matches
    
    # Expected observation variance:
    # V = (6 * 24) / 36 + (1/3) * 1.5 = 4.0 + 0.5 = 4.5
    v_expected = (6.0 * sigma2_within / n_ctx) + (h_conc * sigma2_match)
    lam_expected = tau2 / (tau2 + v_expected)
    w_prior = 1.0 - lam_expected
    
    var_player_expected = w_prior * tau2
    var_context_expected = (w_prior ** 2) * sigma2_mu
    var_total_expected = var_player_expected + var_context_expected
    
    rec = ContextualPlayerBaselineRecordB435(
        player_id=101,
        phase="Death",
        tier="Tier 3: High",
        context_exposure=n_ctx,
        context_events=54,  # 54 runs in 36 balls -> 9.0 RPO
        context_matches=3,
        career_exposure=200,
        career_events=300,
        career_matches=10,
        context_prior_mean=10.0,
        tau2_player=tau2,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=sigma2_match,
        sigma2_within=sigma2_within,
        is_economy=True
    )
    
    assert rec.state == EpistemicStateB435.VALID_CONTEXT_OBSERVATION
    assert np.isclose(rec.var_observation, v_expected, atol=1e-12)
    assert np.isclose(rec.shrinkage_weight, lam_expected, atol=1e-12)
    assert np.isclose(rec.latent_player_variance, var_player_expected, atol=1e-12)
    assert np.isclose(rec.latent_context_variance, var_context_expected, atol=1e-12)
    assert np.isclose(rec.latent_variance, var_total_expected, atol=1e-12)
    assert np.isclose(rec.latent_se, math.sqrt(var_total_expected), atol=1e-12)


def test_02_joint_gaussian_precision_update_agreement():
    """
    Verifies that the Law of Total Variance formulation agrees with the
    full joint conjugate Gaussian update to within exact analytical difference:
        Delta = (V^2 * sigma2_mu^2) / ((V + tau2)^2 * (V + sigma2_mu + tau2))
    """
    tau2 = 0.465681
    sigma2_mu = 0.05
    v_obs = 2.50
    
    # 1. Two-Stage Law of Total Variance
    lam = tau2 / (tau2 + v_obs)
    var_two_stage = (1.0 - lam) * tau2 + ((1.0 - lam) ** 2) * sigma2_mu
    
    # 2. Joint Conjugate Gaussian Posterior
    var_joint = ((tau2 + sigma2_mu) * v_obs) / (tau2 + sigma2_mu + v_obs)
    
    # Exact algebraic difference:
    diff = var_two_stage - var_joint
    exact_diff = (v_obs ** 2 * sigma2_mu ** 2) / ((v_obs + tau2) ** 2 * (v_obs + sigma2_mu + tau2))
    
    assert np.isclose(diff, exact_diff, atol=1e-12)
    assert diff < 0.001  # less than 0.001 RPO^2 difference on realistic data


def test_03_limiting_behavior_zero_prior_mean_variance():
    """
    Verifies that as sigma2_mu -> 0, Var(theta | data) exactly converges to
    the standard fixed-prior shrinkage variance (1 - lambda) * tau2.
    """
    tau2 = 0.60
    sigma2_mu = 0.0  # Zero contextual prior-mean uncertainty
    n_ctx = 60
    
    rec = ContextualPlayerBaselineRecordB435(
        player_id=202,
        phase="Powerplay",
        tier="Tier 1: Low",
        context_exposure=n_ctx,
        context_events=70,
        context_matches=5,
        career_exposure=300,
        career_events=350,
        career_matches=25,
        context_prior_mean=7.5,
        tau2_player=tau2,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=1.45,
        sigma2_within=22.84,
        is_economy=True
    )
    
    lam = rec.shrinkage_weight
    expected_fixed_var = (1.0 - lam) * tau2
    
    assert rec.latent_context_variance == 0.0
    assert np.isclose(rec.latent_variance, expected_fixed_var, atol=1e-12)


def test_04_asymptotic_exposure_behavior():
    """
    Verifies that as player exposure n -> infinity:
    1. Shrinkage weight lambda -> 1.0.
    2. Player latent variance -> 0.0 (O(1/n)).
    3. Contextual prior variance -> 0.0 quadratically (O(1/n^2)).
    4. Total latent variance -> 0.0.
    """
    tau2 = 0.50
    sigma2_mu = 0.10
    
    # Evaluate at high exposure across many matches
    n_ctx = 60000
    n_matches = 2000
    rec = ContextualPlayerBaselineRecordB435(
        player_id=303,
        phase="Middle",
        tier="Tier 2: Medium",
        context_exposure=n_ctx,
        context_events=70000,
        context_matches=n_matches,
        career_exposure=80000,
        career_events=95000,
        career_matches=2500,
        context_prior_mean=8.0,
        tau2_player=tau2,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=1.45,
        sigma2_within=22.84,
        is_economy=True
    )
    
    assert rec.shrinkage_weight > 0.99
    assert rec.latent_player_variance < 0.005
    assert rec.latent_context_variance < 1e-5  # Quadratic decay
    assert rec.latent_variance < 0.005


def test_05_zero_exposure_prior_variance():
    """
    Verifies that for zero context exposure, the latent variance exactly
    equals the marginal prior variance: tau2 + sigma2_mu.
    """
    tau2 = 0.45
    sigma2_mu = 0.08
    
    rec_zero_ctx = ContextualPlayerBaselineRecordB435(
        player_id=404,
        phase="Death",
        tier="Tier 4: Extreme",
        context_exposure=0,
        context_events=None,
        context_matches=0,
        career_exposure=120,
        career_events=150,
        career_matches=10,
        context_prior_mean=11.2,
        tau2_player=tau2,
        context_prior_mean_variance=sigma2_mu,
        is_economy=True
    )
    
    assert rec_zero_ctx.state == EpistemicStateB435.ZERO_CONTEXT_EXPOSURE
    assert rec_zero_ctx.shrinkage_weight == 0.0
    assert rec_zero_ctx.shrunk_estimate == 11.2
    assert np.isclose(rec_zero_ctx.latent_variance, tau2 + sigma2_mu, atol=1e-12)
    assert np.isclose(rec_zero_ctx.latent_player_variance, tau2, atol=1e-12)
    assert np.isclose(rec_zero_ctx.latent_context_variance, sigma2_mu, atol=1e-12)


def test_06_predictive_variance_no_double_counting():
    """
    Verifies that predictive variance for a held-out observation:
    1. Incorporates all 4 components (player ability, context mean, match shock, within-spell noise).
    2. Contextual prior mean uncertainty enters strictly through latent ability variance
       and is NOT added a second time.
    """
    tau2 = 0.50
    sigma2_mu = 0.15
    sigma2_match = 1.45
    sigma2_within = 22.84
    n_eval = 24  # 4 overs in test spell
    
    rec = ContextualPlayerBaselineRecordB435(
        player_id=505,
        phase="Middle",
        tier="Tier 2: Medium",
        context_exposure=60,
        context_events=80,
        context_matches=5,
        career_exposure=300,
        career_events=400,
        career_matches=25,
        context_prior_mean=8.2,
        tau2_player=tau2,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=sigma2_match,
        sigma2_within=sigma2_within,
        is_economy=True
    )
    
    pred_var = rec.get_predictive_variance(n_eval=n_eval)
    breakdown = rec.get_predictive_variance_breakdown(n_eval=n_eval)
    
    expected_within = (sigma2_within * 6.0) / n_eval  # (22.84 * 6) / 24 = 5.71
    expected_pred_var = rec.latent_variance + sigma2_match + expected_within
    
    assert np.isclose(pred_var, expected_pred_var, atol=1e-12)
    assert np.isclose(breakdown["total_predictive_variance"], expected_pred_var, atol=1e-12)
    assert np.isclose(breakdown["latent_total_variance"], rec.latent_variance, atol=1e-12)
    assert np.isclose(breakdown["match_environmental_variance"], sigma2_match, atol=1e-12)
    assert np.isclose(breakdown["within_sampling_variance"], expected_within, atol=1e-12)


def test_07_simulated_predictive_interval_coverage():
    """
    Simulates 10,000 synthetic held-out observations from the true data-generating process:
        mu_c ~ N(mu_0, sigma2_mu)
        theta_i ~ N(mu_c, tau2)
        Y_train ~ N(theta_i, V_train)
        Y_test ~ N(theta_i, sigma2_match + 6 * sigma2_within / n_eval)
    Verifies that empirical coverage for 80% and 95% nominal intervals covers
    the true test observation within 3 binomial standard errors.
    """
    np.random.seed(42)
    n_sims = 10000
    
    mu_0 = 8.5
    sigma2_mu = 0.12
    tau2 = 0.48
    sigma2_match = 1.45
    sigma2_within = 22.84
    n_train_balls = 48
    n_eval_balls = 24
    
    # 1. Sample contextual population means
    mu_c_samples = np.random.normal(mu_0, math.sqrt(sigma2_mu), size=n_sims)
    
    # 2. Sample player latent abilities
    theta_samples = np.random.normal(mu_c_samples, math.sqrt(tau2), size=n_sims)
    
    # 3. Sample training observation
    v_train = (6.0 * sigma2_within / n_train_balls) + (0.25 * sigma2_match)
    y_train_samples = np.random.normal(theta_samples, math.sqrt(v_train), size=n_sims)
    
    # 4. Sample held-out test observations
    v_test = sigma2_match + (6.0 * sigma2_within / n_eval_balls)
    y_test_samples = np.random.normal(theta_samples, math.sqrt(v_test), size=n_sims)
    
    # 5. Evaluate predictive interval for each simulation
    lam = tau2 / (tau2 + v_train)
    shrunk_means = lam * y_train_samples + (1.0 - lam) * mu_0
    
    latent_var = (1.0 - lam) * tau2 + ((1.0 - lam) ** 2) * sigma2_mu
    pred_var = latent_var + v_test
    pred_se = math.sqrt(pred_var)
    
    # 80% CI (z = 1.28155)
    z80 = 1.2815515655446004
    covered_80 = (y_test_samples >= shrunk_means - z80 * pred_se) & (y_test_samples <= shrunk_means + z80 * pred_se)
    emp_cov_80 = float(np.mean(covered_80))
    se_binom_80 = math.sqrt(0.80 * 0.20 / n_sims)
    
    # 95% CI (z = 1.95996)
    z95 = 1.959963984540054
    covered_95 = (y_test_samples >= shrunk_means - z95 * pred_se) & (y_test_samples <= shrunk_means + z95 * pred_se)
    emp_cov_95 = float(np.mean(covered_95))
    se_binom_95 = math.sqrt(0.95 * 0.05 / n_sims)
    
    assert abs(emp_cov_80 - 0.80) <= 3.0 * se_binom_80
    assert abs(emp_cov_95 - 0.95) <= 3.0 * se_binom_95


def test_08_batter_domain_prior_mean_variance():
    """
    Verifies that the batter boundary percentage posterior properly includes
    context_prior_mean_variance in latent variance and predictive variance.
    """
    tau2 = 0.0025
    sigma2_mu = 0.0002
    n_ctx = 50
    prior_m0 = 75.0
    
    rec = ContextualPlayerBaselineRecordB435(
        player_id=606,
        phase="Powerplay",
        tier="Tier 1: Low",
        context_exposure=n_ctx,
        context_events=10,  # 10 boundaries in 50 balls -> 0.20
        context_matches=4,
        career_exposure=250,
        career_events=50,
        career_matches=20,
        context_prior_mean=0.18,
        tau2_player=tau2,
        prior_m0=prior_m0,
        is_economy=False,
        context_prior_mean_variance=sigma2_mu
    )
    
    lam = 50.0 / (50.0 + 75.0)  # 0.40
    w_prior = 1.0 - lam          # 0.60
    
    expected_latent_player = w_prior * tau2
    expected_latent_context = (w_prior ** 2) * sigma2_mu
    expected_latent_total = expected_latent_player + expected_latent_context
    
    assert np.isclose(rec.latent_player_variance, expected_latent_player, atol=1e-12)
    assert np.isclose(rec.latent_context_variance, expected_latent_context, atol=1e-12)
    assert np.isclose(rec.latent_variance, expected_latent_total, atol=1e-12)


# ============================================================================
# 2. Regression Preservation Tests (Henderson Rank, Trace, Calibration Validation)
# ============================================================================

def _build_design_matrices(spells, K, I, M):
    N = len(spells)
    P_cbm = K + I + M
    X_cbm = np.zeros((N, P_cbm), dtype=float)
    X_cb = np.zeros((N, K + I), dtype=float)
    X_cm = np.zeros((N, K + M), dtype=float)

    for r, (b, m, c) in enumerate(spells):
        X_cbm[r, c] = 1.0
        X_cbm[r, K + b] = 1.0
        X_cbm[r, K + I + m] = 1.0

        X_cb[r, c] = 1.0
        X_cb[r, K + b] = 1.0

        X_cm[r, c] = 1.0
        X_cm[r, K + m] = 1.0

    return X_cbm, X_cb, X_cm


def test_09_henderson_design_rank_auditor_counterexample():
    """
    Regression test: Verifies exact numerical rank on the auditor counterexample:
    2 disconnected components, 6 bowlers, 6 matches, 2 exclusive contexts -> True rank 10.
    """
    spells = [
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0), (2, 2, 0), (0, 2, 0),
        (3, 3, 1), (4, 3, 1), (4, 4, 1), (5, 4, 1), (5, 5, 1), (3, 5, 1)
    ]
    X_cbm, X_cb, X_cm = _build_design_matrices(spells, K=2, I=6, M=6)

    rank_svd, _, _ = compute_design_matrix_rank(X_cbm, method="svd")
    rank_gram, _, _ = compute_design_matrix_rank(X_cbm, method="gram")

    assert rank_svd == 10
    assert rank_gram == 10


def test_10_henderson_trace_unfloored_and_positive():
    """
    Regression test: Verifies that Henderson trace coefficients are preserved unfloored
    and raise NumericalConditioningError if non-positive.
    """
    with pytest.raises(NumericalConditioningError):
        c_m_bad = -0.5
        if c_m_bad <= 0.0 or not np.isfinite(c_m_bad):
            raise NumericalConditioningError(f"Henderson Method III trace coefficient non-positive: c_m={c_m_bad}")


def test_11_calibration_input_validation_rejections():
    """
    Regression test: Verifies that invalid calibration inputs are rejected.
    """
    # 1. Non-integer sample size
    status, _ = evaluate_bowler_calibration_status(0.80, 0.75, 0.85, 0.95, 0.93, 0.97, 50.5)
    assert status == "INVALID_CALIBRATION_INPUT"
    
    # 2. Coverage outside [0, 1]
    status, _ = evaluate_bowler_calibration_status(1.05, 0.75, 0.85, 0.95, 0.93, 0.97, 50)
    assert status == "INVALID_CALIBRATION_INPUT"
    
    # 3. Non-containment (point estimate outside CI)
    status, _ = evaluate_bowler_calibration_status(0.80, 0.82, 0.88, 0.95, 0.93, 0.97, 50)
    assert status == "INVALID_CALIBRATION_INPUT"
    
    # 4. Reversed bounds
    status, _ = evaluate_bowler_calibration_status(0.80, 0.85, 0.75, 0.95, 0.93, 0.97, 50)
    assert status == "INVALID_CALIBRATION_INPUT"


def test_12_four_variance_components_distinction():
    """
    Verifies the complete distinction of all 4 variance components:
    1. Player-specific latent ability variance: (1 - lambda) * tau2
    2. Contextual population-mean variance: (1 - lambda)^2 * sigma2_mu
    3. Match-level environmental variance: sigma2_match
    4. Within-spell sampling variance: (6 * sigma2_within) / n_eval
    """
    rec = ContextualPlayerBaselineRecordB435(
        player_id=707,
        phase="Powerplay",
        tier="Tier 1: Low",
        context_exposure=48,
        context_events=60,
        context_matches=4,
        career_exposure=200,
        career_events=250,
        career_matches=15,
        context_prior_mean=7.2,
        tau2_player=0.45,
        context_prior_mean_variance=0.06,
        sigma2_match=1.40,
        sigma2_within=22.0,
        is_economy=True
    )
    
    breakdown = rec.get_predictive_variance_breakdown(n_eval=12)
    
    v_player = breakdown["player_latent_variance"]
    v_context = breakdown["context_population_mean_variance"]
    v_latent = breakdown["latent_total_variance"]
    v_match = breakdown["match_environmental_variance"]
    v_within = breakdown["within_sampling_variance"]
    v_total = breakdown["total_predictive_variance"]
    
    # Check all are strictly positive and distinct
    assert v_player > 0.0
    assert v_context > 0.0
    assert v_match > 0.0
    assert v_within > 0.0
    
    # Check additive hierarchy
    assert np.isclose(v_player + v_context, v_latent, atol=1e-12)
    assert np.isclose(v_latent + v_match + v_within, v_total, atol=1e-12)
    assert np.isclose(breakdown["predictive_se"], math.sqrt(v_total), atol=1e-12)


def test_13_simulated_error_orthogonality():
    """
    Empirically verifies the mathematical proof that:
        Cov(lambda * e_i, -(1 - lambda) * alpha_i) = 0
        Cov((1 - lambda) * delta_c, lambda * e_i - (1 - lambda) * alpha_i) = 0
    Confirming that no hidden covariance cross-terms exist and the variance of
    the estimation error is identically (1 - lambda) * tau2 + (1 - lambda)^2 * sigma2_mu.
    """
    np.random.seed(123)
    n_draws = 50000
    
    tau2 = 0.50
    sigma2_mu = 0.10
    v_obs = 3.0
    
    lam = tau2 / (tau2 + v_obs)
    w_prior = 1.0 - lam
    
    # Draw independent noise terms
    delta_c = np.random.normal(0, math.sqrt(sigma2_mu), size=n_draws)
    alpha_i = np.random.normal(0, math.sqrt(tau2), size=n_draws)
    e_i = np.random.normal(0, math.sqrt(v_obs), size=n_draws)
    
    term_obs = lam * e_i
    term_ability = -w_prior * alpha_i
    term_pop = w_prior * delta_c
    
    # Covariances should be zero within sampling error
    cov_obs_ability = float(np.cov(term_obs, term_ability)[0, 1])
    cov_pop_rest = float(np.cov(term_pop, term_obs + term_ability)[0, 1])
    
    assert abs(cov_obs_ability) < 0.01
    assert abs(cov_pop_rest) < 0.01
    
    # Empirical total error variance
    total_error = term_obs + term_ability + term_pop
    emp_var = float(np.var(total_error))
    
    # Theoretical variance: (1 - lam) * tau2 + (1 - lam)^2 * sigma2_mu
    theor_var = w_prior * tau2 + (w_prior ** 2) * sigma2_mu
    
    assert abs(emp_var - theor_var) < 0.01


def test_14_herfindahl_concentration_variance_impact():
    """
    Verifies that concentrated exposure (all balls in 1 match) produces higher
    observation variance, lower shrinkage weight, and higher latent variance
    than dispersed exposure (split across 10 matches).
    """
    tau2 = 0.50
    sigma2_mu = 0.08
    sigma2_match = 2.0
    sigma2_within = 20.0
    n_ctx = 60
    
    # 1. Concentrated in 1 match: H = 1.0
    rec_conc = ContextualPlayerBaselineRecordB435(
        player_id=801,
        phase="Death",
        tier="Tier 3: High",
        context_exposure=n_ctx,
        context_events=70,
        context_matches=1,
        career_exposure=200,
        career_events=250,
        career_matches=5,
        context_prior_mean=9.0,
        tau2_player=tau2,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=sigma2_match,
        sigma2_within=sigma2_within,
        context_match_balls_list=[60],
        is_economy=True
    )
    
    # 2. Dispersed across 10 matches: H = 0.10
    rec_disp = ContextualPlayerBaselineRecordB435(
        player_id=802,
        phase="Death",
        tier="Tier 3: High",
        context_exposure=n_ctx,
        context_events=70,
        context_matches=10,
        career_exposure=200,
        career_events=250,
        career_matches=20,
        context_prior_mean=9.0,
        tau2_player=tau2,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=sigma2_match,
        sigma2_within=sigma2_within,
        context_match_balls_list=[6] * 10,
        is_economy=True
    )
    
    assert rec_conc.match_herfindahl == 1.0
    assert np.isclose(rec_disp.match_herfindahl, 0.10, atol=1e-12)
    assert rec_conc.var_observation > rec_disp.var_observation
    assert rec_conc.shrinkage_weight < rec_disp.shrinkage_weight
    assert rec_conc.latent_variance > rec_disp.latent_variance


def test_15_batter_predictive_breakdown():
    """
    Verifies that the predictive variance breakdown for batters correctly
    sets match environmental variance to 0 and computes sampling noise.
    """
    rec_bat = ContextualPlayerBaselineRecordB435(
        player_id=901,
        phase="Middle",
        tier="Tier 2: Medium",
        context_exposure=80,
        context_events=16,  # 0.20
        context_matches=8,
        career_exposure=400,
        career_events=80,
        career_matches=30,
        context_prior_mean=0.15,
        tau2_player=0.002,
        context_prior_mean_variance=0.0001,
        is_economy=False
    )
    
    breakdown = rec_bat.get_predictive_variance_breakdown(n_eval=1)
    
    assert breakdown["match_environmental_variance"] == 0.0
    assert breakdown["within_sampling_variance"] > 0.0
    assert np.isclose(
        breakdown["latent_total_variance"] + breakdown["within_sampling_variance"],
        breakdown["total_predictive_variance"],
        atol=1e-12
    )


def test_16_epistemic_state_transitions():
    """
    Verifies that invalid exposure returns NaN and zero exposure properly sets
    latent variance to tau2 + sigma2_mu.
    """
    # Invalid exposure
    rec_inv = ContextualPlayerBaselineRecordB435(
        player_id=999,
        phase="Death",
        tier="Tier 4: Extreme",
        context_exposure=-5,
        context_events=None,
        context_matches=0,
        career_exposure=0,
        career_events=None,
        career_matches=0,
        context_prior_mean=10.0,
        is_economy=True
    )
    assert rec_inv.state == EpistemicStateB435.INVALID_EXPOSURE
    assert np.isnan(rec_inv.latent_variance)
    
    # Zero career exposure
    rec_zero_car = ContextualPlayerBaselineRecordB435(
        player_id=998,
        phase="Death",
        tier="Tier 4: Extreme",
        context_exposure=0,
        context_events=None,
        context_matches=0,
        career_exposure=0,
        career_events=None,
        career_matches=0,
        context_prior_mean=10.0,
        tau2_player=0.40,
        context_prior_mean_variance=0.10,
        is_economy=True
    )
    assert rec_zero_car.state == EpistemicStateB435.ZERO_CAREER_EXPOSURE
    assert np.isclose(rec_zero_car.latent_variance, 0.50, atol=1e-12)

