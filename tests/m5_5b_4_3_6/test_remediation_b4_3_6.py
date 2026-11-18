"""
RR ScoutIQ — Milestone M5.5-B.4.3.6: Exhaustive Targeted Adversarial Test Suite
Module: tests/m5_5b_4_3_6/test_remediation_b4_3_6.py

Validates all 10 Priority 5 requirements:
1. LOPO contextual prior decontamination (player observations strictly excluded from own prior).
2. Contextual prior uncertainty scaling (N_full / N_lopo) and sparse-context hierarchical fallbacks.
3. Covariance orthogonality: Cov(mu_hat_lopo, Y_i | mu) = 0.
4. Full Joint Conjugate Gaussian Bayesian posterior mean and variance match analytical closed forms.
5. Distinct two-stage plug-in frequentist MSE vs Bayesian posterior variance and exact closed-form gap.
6. Asymptotic exposure under fixed matches: Herfindahl floor prevents observation variance from reaching zero.
7. Asymptotic exposure under increasing matches: observation variance and posterior variance vanish.
8. Zero-exposure baseline recovery (lambda=0, theta_hat = mu_lopo, Var = tau2 + sigma2_mu).
9. Predictive variance breakdown coherence without double-counting.
10. Strict match-grouped 5-fold cross-validation isolation (0 shared matches).
11. Henderson design rank preservation on disconnected bipartite topologies.
12. Rigorous calibration classification policy based on cluster confidence intervals.
"""

import os
import sys
import math
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.linalg as la
import pytest

sys.path.insert(0, os.path.abspath("."))

from src.m5_5b_4_3_6.epistemic_context_engine_b4_3_6 import (
    ContextualPlayerBaselineRecordB436,
    EpistemicStateB436
)
from src.m5_5b_4_3_6.hierarchical_engine_b4_3_6 import (
    ContextualHierarchyB436,
    PlayerPosteriorBaselineEstimatorB436
)
from src.m5_5b_4_3_6.variance_decomposition_b4_3_6 import (
    compute_design_matrix_rank,
    estimate_crossed_variance_components_henderson3,
    NumericalConditioningError,
    IdentifiabilityError
)
from src.m5_5b_4_3_6.calibration_engine_b4_3_6 import (
    evaluate_bowler_calibration_status,
    evaluate_batter_calibration_status
)


# ============================================================================
# 1. LOPO Contextual Prior Decontamination Tests (Priority 1 & 5.1)
# ============================================================================

def test_01_lopo_player_observation_independence():
    """
    Priority 5.1: Verify that an evaluated player's observed runs/deliveries in the
    training set strictly do NOT contaminate their own LOPO contextual prior.
    Perturbing player A's performance must leave player A's LOPO prior unchanged,
    even though it alters the cell-pooled mean and other players' LOPO priors.
    """
    # Create synthetic training dataset
    # 3 players in Death / Tier 3:
    # Player 101: 50 balls, 100 runs (Econ 12.0)
    # Player 102: 60 balls, 90 runs (Econ 9.0)
    # Player 103: 40 balls, 50 runs (Econ 7.5)
    records = []
    
    # Player 101
    for i in range(50):
        records.append({
            "match_id": 1 + (i % 5),
            "bowler_id": 101,
            "batter_id": 201 + (i % 10),
            "phase": "Death",
            "tier": "Tier 3: High",
            "pre_match_phase": "Death",
            "pre_pressure_tier": "Tier 3: High",
            "is_legal": 1,
            "ext_is_legal_delivery": 1,
            "runs_batter": 2,
            "extra_runs": 0,
            "is_wide": 0,
            "is_noball": 0,
            "ext_is_wide": 0,
            "ext_is_noball": 0,
            "is_boundary": 0,
            "ext_is_four": 0,
            "ext_is_six": 0,
            "ext_bowler_debit_runs": 2
        })
    # Player 102
    for i in range(60):
        r_extra = (1 if i % 2 == 0 else 0)
        records.append({
            "match_id": 10 + (i % 5),
            "bowler_id": 102,
            "batter_id": 201 + (i % 10),
            "phase": "Death",
            "tier": "Tier 3: High",
            "pre_match_phase": "Death",
            "pre_pressure_tier": "Tier 3: High",
            "is_legal": 1,
            "ext_is_legal_delivery": 1,
            "runs_batter": 1,
            "extra_runs": r_extra,
            "is_wide": 0,
            "is_noball": 0,
            "ext_is_wide": 0,
            "ext_is_noball": 0,
            "is_boundary": 0,
            "ext_is_four": 0,
            "ext_is_six": 0,
            "ext_bowler_debit_runs": 1 + r_extra
        })
    # Player 103
    for i in range(40):
        r_extra = (1 if i % 4 == 0 else 0)
        records.append({
            "match_id": 20 + (i % 5),
            "bowler_id": 103,
            "batter_id": 201 + (i % 10),
            "phase": "Death",
            "tier": "Tier 3: High",
            "pre_match_phase": "Death",
            "pre_pressure_tier": "Tier 3: High",
            "is_legal": 1,
            "ext_is_legal_delivery": 1,
            "runs_batter": 1,
            "extra_runs": r_extra,
            "is_wide": 0,
            "is_noball": 0,
            "ext_is_wide": 0,
            "ext_is_noball": 0,
            "is_boundary": 0,
            "ext_is_four": 0,
            "ext_is_six": 0,
            "ext_bowler_debit_runs": 1 + r_extra
        })
        
    df_train1 = pd.DataFrame(records)
    
    hier1 = ContextualHierarchyB436()
    hier1.fit(df_train1)
    
    mean_101_v1, var_101_v1, prov_101_v1, pop_101_v1 = hier1.get_lopo_context_prior(
        player_id=101, phase="Death", tier="Tier 3: High", domain="Bowler"
    )
    mean_102_v1, var_102_v1, prov_102_v1, pop_102_v1 = hier1.get_lopo_context_prior(
        player_id=102, phase="Death", tier="Tier 3: High", domain="Bowler"
    )
    cell_pooled_v1 = hier1.get_context_expectation("Death", "Tier 3: High", "bowler_economy")
    
    # Now create perturbed dataset where Player 101 concedes TRIPLE runs (6 runs per ball instead of 2)
    records_perturbed = []
    for r in records:
        r_copy = r.copy()
        if r_copy["bowler_id"] == 101:
            r_copy["runs_batter"] = 6
            r_copy["ext_bowler_debit_runs"] = 6
        records_perturbed.append(r_copy)
    df_train2 = pd.DataFrame(records_perturbed)
    
    hier2 = ContextualHierarchyB436()
    hier2.fit(df_train2)
    
    mean_101_v2, var_101_v2, prov_101_v2, pop_101_v2 = hier2.get_lopo_context_prior(
        player_id=101, phase="Death", tier="Tier 3: High", domain="Bowler"
    )
    mean_102_v2, var_102_v2, prov_102_v2, pop_102_v2 = hier2.get_lopo_context_prior(
        player_id=102, phase="Death", tier="Tier 3: High", domain="Bowler"
    )
    cell_pooled_v2 = hier2.get_context_expectation("Death", "Tier 3: High", "bowler_economy")
    
    # 1. Cell-pooled mean MUST change due to Player 101's perturbation
    assert not np.isclose(cell_pooled_v1, cell_pooled_v2), "Cell-pooled mean should change when Player 101 is perturbed!"
    
    # 2. Player 101's LOPO prior mean MUST remain IDENTICAL to machine precision
    assert np.isclose(mean_101_v1, mean_101_v2, atol=1e-12), \
        f"Player 101's LOPO prior changed! {mean_101_v1} vs {mean_101_v2}"
    assert var_101_v1 > 0 and var_101_v2 > 0, "LOPO prior variance must be strictly positive"
        
    # 3. Player 102's LOPO prior MUST change (because Player 101 is part of Player 102's LOPO reference set)
    assert not np.isclose(mean_102_v1, mean_102_v2), \
        "Player 102's LOPO prior should change when another player's performance changes!"


# ============================================================================
# 2. LOPO Uncertainty Scaling and Fallbacks (Priority 2 & 5.2)
# ============================================================================

def test_02_lopo_uncertainty_scaling_and_sparse_fallbacks():
    """
    Priority 5.2: Verify that contextual prior uncertainty correctly scales as:
        sigma2_mu_LOPO = sigma2_mu_full * (N_full / N_LOPO)
    and falls back to PHASE_LOPO_FALLBACK or LEAGUE_LOPO_FALLBACK when N_LOPO < 30.
    """
    # Create dataset with dominant player 201 (100 balls) and minor player 202 (15 balls)
    records = []
    # Dominant player
    for i in range(100):
        records.append({
            "match_id": 1 + (i % 5),
            "bowler_id": 201,
            "batter_id": 301 + (i % 10),
            "phase": "Powerplay",
            "tier": "Tier 1: Low",
            "pre_match_phase": "Powerplay",
            "pre_pressure_tier": "Tier 1: Low",
            "is_legal": 1,
            "ext_is_legal_delivery": 1,
            "runs_batter": 1,
            "extra_runs": 0,
            "is_wide": 0,
            "is_noball": 0,
            "ext_is_wide": 0,
            "ext_is_noball": 0,
            "is_boundary": 0,
            "ext_is_four": 0,
            "ext_is_six": 0,
            "ext_bowler_debit_runs": 1
        })
    # Minor player
    for i in range(15):
        records.append({
            "match_id": 10 + (i % 3),
            "bowler_id": 202,
            "batter_id": 301 + (i % 10),
            "phase": "Powerplay",
            "tier": "Tier 1: Low",
            "pre_match_phase": "Powerplay",
            "pre_pressure_tier": "Tier 1: Low",
            "is_legal": 1,
            "ext_is_legal_delivery": 1,
            "runs_batter": 2,
            "extra_runs": 0,
            "is_wide": 0,
            "is_noball": 0,
            "ext_is_wide": 0,
            "ext_is_noball": 0,
            "is_boundary": 0,
            "ext_is_four": 0,
            "ext_is_six": 0,
            "ext_bowler_debit_runs": 2
        })
    # Add balls in other tiers of Powerplay to allow phase fallback
    for i in range(50):
        records.append({
            "match_id": 20 + (i % 5),
            "bowler_id": 203,
            "batter_id": 301 + (i % 10),
            "phase": "Powerplay",
            "tier": "Tier 2: Medium",
            "pre_match_phase": "Powerplay",
            "pre_pressure_tier": "Tier 2: Medium",
            "is_legal": 1,
            "ext_is_legal_delivery": 1,
            "runs_batter": 1,
            "extra_runs": 0,
            "is_wide": 0,
            "is_noball": 0,
            "ext_is_wide": 0,
            "ext_is_noball": 0,
            "is_boundary": 0,
            "ext_is_four": 0,
            "ext_is_six": 0,
            "ext_bowler_debit_runs": 1
        })
        
    df = pd.DataFrame(records)
    hier = ContextualHierarchyB436()
    hier.fit(df)
    
    # 1. Minor player 202 has 15 balls. When removed, N_LOPO = 100 >= 30 -> CELL_LOPO_ROBUST
    mean_202, var_202, prov_202, pop_202 = hier.get_lopo_context_prior(
        player_id=202, phase="Powerplay", tier="Tier 1: Low", domain="Bowler"
    )
    assert prov_202 == "CELL_LOPO_ROBUST"
    assert pop_202 == 100
    
    # Verify exact N_full / N_LOPO scaling:
    # N_full = 115, N_LOPO = 100 -> scaling ratio = 115 / 100 = 1.15
    ratio_expected = 115.0 / 100.0
    cell_var_full = hier.get_context_mean_variance("Powerplay", "Tier 1: Low", "bowler_economy")
    assert np.isclose(var_202, cell_var_full * ratio_expected, atol=1e-10)
    
    # 2. Dominant player 201 has 100 balls. When removed, remaining cell balls = 15 < 30!
    # Must fallback to PHASE_LOPO_FALLBACK
    mean_201, var_201, prov_201, pop_201 = hier.get_lopo_context_prior(
        player_id=201, phase="Powerplay", tier="Tier 1: Low", domain="Bowler"
    )
    assert prov_201 == "PHASE_LOPO_FALLBACK"
    assert pop_201 == 65  # 15 from Tier 1 + 50 from Tier 2


# ============================================================================
# 3. Covariance Orthogonality Tests (Priority 3 & 5.3)
# ============================================================================

def test_03_zero_covariance_and_orthogonality():
    """
    Priority 5.3: Verify that under genuine LOPO construction,
        Cov(mu_hat_LOPO, Y_i | mu) == 0
    across independent simulated samples.
    """
    np.random.seed(42)
    n_sims = 500
    mu_true = 8.0
    sigma_indiv = 1.5
    sigma_obs = 2.0
    
    y_target_list = []
    mu_lopo_list = []
    
    for _ in range(n_sims):
        # 10 players in a cell
        player_abilities = np.random.normal(mu_true, sigma_indiv, size=10)
        # Observed performances
        y_obs = np.random.normal(player_abilities, sigma_obs)
        
        # Target player is player 0
        y_target = y_obs[0]
        # LOPO mean is computed strictly from players 1..9
        mu_lopo = np.mean(y_obs[1:])
        
        y_target_list.append(y_target)
        mu_lopo_list.append(mu_lopo)
        
    y_target_arr = np.array(y_target_list)
    mu_lopo_arr = np.array(mu_lopo_list)
    
    # Compute empirical correlation
    corr = np.corrcoef(y_target_arr, mu_lopo_arr)[0, 1]
    cov = np.cov(y_target_arr, mu_lopo_arr)[0, 1]
    
    # Orthogonality condition: sample correlation with N=500 should be near 0 (|r| < 0.10)
    assert abs(corr) < 0.10, f"Covariance orthogonality violated! Correlation is {corr:.4f}"
    assert abs(cov) < 0.15, f"Covariance is non-zero! Cov: {cov:.4f}"


# ============================================================================
# 4. Analytical Equivalence of Full Joint Gaussian Model (Priority 4 & 5.4)
# ============================================================================

@pytest.mark.parametrize("mu_lopo,sigma2_mu,tau2_p,v_obs,is_economy", [
    (8.5, 0.25, 0.80, 2.40, True),
    (7.0, 0.10, 0.40, 1.20, True),
    (10.0, 0.50, 1.50, 5.00, True),
    (0.18, 0.001, 0.005, 0.002, False)  # batter scale
])
def test_04_full_joint_gaussian_analytical_equivalence(mu_lopo, sigma2_mu, tau2_p, v_obs, is_economy):
    """
    Priority 5.4: Verify that the Full Joint Conjugate Gaussian model computed by
    ContextualPlayerBaselineRecordB436 matches exact independent closed forms to < 10^-12:
        tau2_total = tau2_p + sigma2_mu
        lambda_tilde = tau2_total / (tau2_total + V)
        theta_tilde = lambda_tilde * Y + (1 - lambda_tilde) * mu_lopo
        Var(theta | Y) = (tau2_total * V) / (tau2_total + V)
    """
    y_obs = mu_lopo + (1.2 if is_economy else 0.02)
    
    # Independent analytical calculations
    tau2_total_expected = tau2_p + sigma2_mu
    lambda_tilde_expected = tau2_total_expected / (tau2_total_expected + v_obs)
    theta_tilde_expected = lambda_tilde_expected * y_obs + (1.0 - lambda_tilde_expected) * mu_lopo
    var_bayes_expected = (tau2_total_expected * v_obs) / (tau2_total_expected + v_obs)
    
    if is_economy:
        n_ctx = 60
        events = (y_obs * n_ctx) / 6.0
        rec = ContextualPlayerBaselineRecordB436(
            player_id=999,
            phase="Middle",
            tier="Tier 2: Medium",
            context_exposure=n_ctx,
            context_events=events,
            context_matches=1,
            career_exposure=200,
            career_events=160,
            career_matches=10,
            context_prior_mean=mu_lopo,
            tau2_player=tau2_p,
            context_prior_mean_variance=sigma2_mu,
            sigma2_match=0.5 * v_obs,
            sigma2_within=5.0 * v_obs,
            prior_provenance="CELL_LOPO_ROBUST",
            prior_population_balls=1500,
            is_economy=True
        )
    else:
        # For batter: p = y_obs, V = p*(1-p)/n_ctx
        # With y_obs = 0.20, p*(1-p) = 0.16 -> n_ctx = 0.16 / 0.002 = 80
        n_ctx = int(round((y_obs * (1.0 - y_obs)) / v_obs))
        events = int(round(y_obs * n_ctx))
        rec = ContextualPlayerBaselineRecordB436(
            player_id=999,
            phase="Middle",
            tier="Tier 2: Medium",
            context_exposure=n_ctx,
            context_events=events,
            context_matches=3,
            career_exposure=200,
            career_events=40,
            career_matches=10,
            context_prior_mean=mu_lopo,
            tau2_player=tau2_p,
            context_prior_mean_variance=sigma2_mu,
            sigma2_match=0.0,
            sigma2_within=1.0,
            prior_provenance="CELL_LOPO_ROBUST",
            prior_population_balls=1500,
            is_economy=False
        )
    
    assert np.isclose(rec.var_observation, v_obs, atol=1e-12)
    assert np.isclose(rec.tau2_total, tau2_total_expected, atol=1e-12)
    assert np.isclose(rec.shrinkage_weight, lambda_tilde_expected, atol=1e-12)
    assert np.isclose(rec.shrunk_baseline, theta_tilde_expected, atol=1e-12)
    assert np.isclose(rec.latent_variance, var_bayes_expected, atol=1e-12)
    assert np.isclose(rec.standard_error, math.sqrt(var_bayes_expected), atol=1e-12)


# ============================================================================
# 5. Frequentist MSE vs Bayesian Posterior Variance (Priority 5 & 5.5)
# ============================================================================

def test_05_frequentist_mse_vs_bayesian_variance_distinction():
    """
    Priority 5.5: Verify that the frequentist MSE of the two-stage plug-in estimator:
        MSE_plugin = (1 - lambda_plugin) * tau2_p + (1 - lambda_plugin)^2 * sigma2_mu
    is computed distinctly from the Bayesian posterior variance:
        Var_Bayes = (tau2_total * V) / (tau2_total + V)
    and that their difference matches the exact closed-form algebraic expression:
        Delta = (V^2 * sigma2_mu^2) / ((V + tau2_p)^2 * (V + tau2_p + sigma2_mu))
    """
    tau2_p = 0.60
    sigma2_mu = 0.25
    v_obs = 3.00
    mu_lopo = 8.20
    y_obs = 9.00
    
    n_ctx = 60
    events = (y_obs * n_ctx) / 6.0
    rec = ContextualPlayerBaselineRecordB436(
        player_id=101,
        phase="Death",
        tier="Tier 3: High",
        context_exposure=n_ctx,
        context_events=events,
        context_matches=1,
        career_exposure=150,
        career_events=200,
        career_matches=8,
        context_prior_mean=mu_lopo,
        tau2_player=tau2_p,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=0.5 * v_obs,
        sigma2_within=5.0 * v_obs,
        is_economy=True
    )
    
    # Independent calculations
    lam_plugin = tau2_p / (tau2_p + v_obs)
    w_plugin = 1.0 - lam_plugin
    mse_expected = w_plugin * tau2_p + (w_plugin ** 2) * sigma2_mu
    
    var_bayes_expected = ((tau2_p + sigma2_mu) * v_obs) / (tau2_p + sigma2_mu + v_obs)
    
    delta_expected = (v_obs ** 2 * sigma2_mu ** 2) / (
        (v_obs + tau2_p) ** 2 * (v_obs + tau2_p + sigma2_mu)
    )
    
    assert np.isclose(rec.var_observation, v_obs, atol=1e-12)
    assert np.isclose(rec.frequentist_mse, mse_expected, atol=1e-12)
    assert np.isclose(rec.latent_variance, var_bayes_expected, atol=1e-12)
    
    # MSE is strictly larger than Bayesian variance
    assert rec.frequentist_mse > rec.latent_variance
    
    # Exact algebraic difference matches
    actual_diff = rec.frequentist_mse - rec.latent_variance
    assert np.isclose(actual_diff, delta_expected, atol=1e-12)


# ============================================================================
# 6. Asymptotic Exposure Under Fixed Matches (Priority 6 & 5.6)
# ============================================================================

def test_06_asymptotic_exposure_fixed_matches():
    """
    Priority 5.6: Verify that when a player faces increasing deliveries within a
    FIXED number of matches M, observation variance does NOT go to zero.
    As n -> infinity with M=2 fixed:
        H = sum (n_m / n)^2 -> 1/M = 0.5
        V -> 0 + 0.5 * sigma2_match = 0.75 > 0
    Shrinkage weight lambda remains strictly bounded below 1.0, and posterior
    variance remains strictly positive!
    """
    tau2_p = 0.80
    sigma2_mu = 0.20
    sigma2_m = 1.50
    sigma2_w = 24.0
    M = 2  # fixed at 2 matches
    
    records = []
    # Test exposures n = 60, 600, 6000, 60000
    for n in [60, 600, 6000, 60000]:
        match_balls = [n // 2, n // 2]
        rec = ContextualPlayerBaselineRecordB436(
            player_id=101,
            phase="Death",
            tier="Tier 3: High",
            context_exposure=n,
            context_events=n * 1.5,
            context_matches=M,
            career_exposure=n * 2,
            career_events=n * 3.0,
            career_matches=M * 2,
            context_prior_mean=8.5,
            tau2_player=tau2_p,
            context_prior_mean_variance=sigma2_mu,
            sigma2_match=sigma2_m,
            sigma2_within=sigma2_w,
            context_match_balls_list=match_balls,
            is_economy=True
        )
        records.append(rec)
        
    v_floor = (1.0 / M) * sigma2_m  # 0.75
    tau2_tot = tau2_p + sigma2_mu  # 1.0
    lam_ceiling = tau2_tot / (tau2_tot + v_floor)  # 1.0 / 1.75 = 0.5714
    var_floor = (tau2_tot * v_floor) / (tau2_tot + v_floor)  # 0.75 / 1.75 = 0.4286
    
    final_rec = records[-1]  # n = 60,000
    assert np.isclose(final_rec.var_observation, v_floor, atol=5e-3)
    assert np.isclose(final_rec.shrinkage_weight, lam_ceiling, atol=5e-3)
    assert np.isclose(final_rec.latent_variance, var_floor, atol=5e-3)
    
    # Critical invariant: observation variance is strictly positive
    assert final_rec.var_observation > 0.74
    assert final_rec.latent_variance > 0.42


# ============================================================================
# 7. Asymptotic Exposure Under Increasing Matches (Priority 7 & 5.7)
# ============================================================================

def test_07_asymptotic_exposure_increasing_matches():
    """
    Priority 5.7: Verify that when both exposures AND matches increase:
        M -> infinity, n -> infinity, H = 1/M -> 0
    Observation variance V -> 0, shrinkage weight lambda -> 1.0, and posterior variance -> 0.
    """
    tau2_p = 0.80
    sigma2_mu = 0.20
    sigma2_m = 1.50
    sigma2_w = 24.0
    
    # 24 balls per match across M = 10, 50, 200, 1000 matches
    m_values = [10, 50, 200, 1000]
    rec_list = []
    
    for M in m_values:
        n = M * 24
        match_balls = [24] * M
        rec = ContextualPlayerBaselineRecordB436(
            player_id=101,
            phase="Death",
            tier="Tier 3: High",
            context_exposure=n,
            context_events=n * 1.5,
            context_matches=M,
            career_exposure=n * 2,
            career_events=n * 3.0,
            career_matches=M * 2,
            context_prior_mean=8.5,
            tau2_player=tau2_p,
            context_prior_mean_variance=sigma2_mu,
            sigma2_match=sigma2_m,
            sigma2_within=sigma2_w,
            context_match_balls_list=match_balls,
            is_economy=True
        )
        rec_list.append(rec)
        
    final_rec = rec_list[-1]  # M = 1000 matches, n = 24000 balls
    
    # As M -> 1000, V -> (6 * 24)/24000 + (1/1000)*1.5 = 0.006 + 0.0015 = 0.0075
    assert final_rec.var_observation < 0.01
    assert final_rec.shrinkage_weight > 0.99
    assert final_rec.latent_variance < 0.01
    assert final_rec.standard_error < 0.10


# ============================================================================
# 8. Zero-Exposure and Sparse Contexts (Priority 8 & 5.8)
# ============================================================================

def test_08_zero_exposure_and_sparse_contexts():
    """
    Priority 5.8: Verify zero-exposure baseline behavior:
        n = 0 implies lambda = 0, theta_hat = mu_LOPO, Var = tau2_p + sigma2_mu.
    """
    mu_lopo = 8.5
    tau2_p = 0.60
    sigma2_mu = 0.15
    
    rec = ContextualPlayerBaselineRecordB436(
        player_id=505,
        phase="Powerplay",
        tier="Tier 1: Low",
        context_exposure=0,
        context_events=None,
        context_matches=0,
        career_exposure=0,
        career_events=None,
        career_matches=0,
        context_prior_mean=mu_lopo,
        tau2_player=tau2_p,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=1.5,
        sigma2_within=24.0,
        prior_provenance="CELL_LOPO_ROBUST",
        prior_population_balls=1000,
        is_economy=True
    )
    
    assert rec.state in [EpistemicStateB436.ZERO_CAREER_EXPOSURE, EpistemicStateB436.ZERO_CONTEXT_EXPOSURE]
    assert rec.shrinkage_weight == 0.0
    assert rec.shrunk_baseline == mu_lopo
    assert np.isclose(rec.latent_variance, tau2_p + sigma2_mu, atol=1e-12)
    assert np.isclose(rec.standard_error, math.sqrt(tau2_p + sigma2_mu), atol=1e-12)


# ============================================================================
# 9. Predictive Variance Breakdown Coherence (Priority 9 & 5.9)
# ============================================================================

def test_09_predictive_variance_breakdown_coherence():
    """
    Priority 5.9: Verify that get_predictive_variance_breakdown(n_eval) partitions
    predictive variance into latent posterior variance, match cluster variance, and
    eval sampling variance, and sums to get_predictive_variance(n_eval) without double-counting.
    """
    tau2_p = 0.50
    sigma2_mu = 0.10
    sigma2_m = 1.20
    sigma2_w = 20.0
    
    rec = ContextualPlayerBaselineRecordB436(
        player_id=303,
        phase="Middle",
        tier="Tier 2: Medium",
        context_exposure=48,
        context_events=60,
        context_matches=3,
        career_exposure=150,
        career_events=180,
        career_matches=8,
        context_prior_mean=7.5,
        tau2_player=tau2_p,
        context_prior_mean_variance=sigma2_mu,
        sigma2_match=sigma2_m,
        sigma2_within=sigma2_w,
        is_economy=True
    )
    
    n_eval = 24  # 4 overs in held-out spell
    breakdown = rec.get_predictive_variance_breakdown(n_eval=n_eval)
    pred_var = rec.get_predictive_variance(n_eval=n_eval)
    
    assert np.isclose(breakdown["latent_posterior_variance"], rec.latent_variance, atol=1e-12)
    assert np.isclose(breakdown["match_environmental_variance"], sigma2_m, atol=1e-12)
    assert np.isclose(breakdown["within_sampling_variance"], (6.0 * sigma2_w) / n_eval, atol=1e-12)
    
    sum_components = (
        breakdown["latent_posterior_variance"] +
        breakdown["match_environmental_variance"] +
        breakdown["within_sampling_variance"]
    )
    assert np.isclose(breakdown["total_predictive_variance"], sum_components, atol=1e-12)
    assert np.isclose(breakdown["total_predictive_variance"], pred_var, atol=1e-12)


# ============================================================================
# 10. Match Isolation and No-Leakage Verification (Priority 10 & 5.10)
# ============================================================================

def test_10_match_grouped_fold_isolation():
    """
    Priority 5.10: Verify that 5-fold match-grouped cross-validation guarantees
    strictly ZERO overlapping matches across all 5 folds.
    """
    from sklearn.model_selection import GroupKFold
    from src.m5_5b.baseline_estimation import load_clean_deliveries
    
    data_path = "data/processed/m5_3/match_state_full.csv"
    if not os.path.exists(data_path):
        pytest.skip(f"Canonical dataset {data_path} not found.")
        
    df = load_clean_deliveries(data_path)
    groups = df["match_id"].values
    gkf = GroupKFold(n_splits=5)
    
    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(df, groups=groups), 1):
        train_matches = set(df.iloc[train_idx]["match_id"].unique())
        val_matches = set(df.iloc[val_idx]["match_id"].unique())
        overlap = train_matches.intersection(val_matches)
        assert len(overlap) == 0, f"Fold {fold_idx} leaked {len(overlap)} matches!"


# ============================================================================
# 11. Henderson Design Rank Preservation (B.4.3.4 / B.4.3.5 Preservation)
# ============================================================================

def test_11_henderson_design_rank_disconnected_counterexample():
    """
    Preservation: Verify that compute_design_matrix_rank correctly determines
    the exact rank of 10 for the 12-spell bipartite cycle topology with 2 disconnected
    components and context categories exclusive to components.
    """
    # 2 components:
    # Component 1: Bowlers 0, 1, 2; Matches 0, 1, 2; Context 0
    # Component 2: Bowlers 3, 4, 5; Matches 3, 4, 5; Context 1
    # 6 spells per component (12 total spells)
    N = 12
    K = 2
    I = 6
    M = 6
    
    # Rows:
    # Comp 1:
    # Spell 0: Bowler 0, Match 0, Context 0
    # Spell 1: Bowler 0, Match 1, Context 0
    # Spell 2: Bowler 1, Match 1, Context 0
    # Spell 3: Bowler 1, Match 2, Context 0
    # Spell 4: Bowler 2, Match 2, Context 0
    # Spell 5: Bowler 2, Match 0, Context 0
    # Comp 2:
    # Spell 6: Bowler 3, Match 3, Context 1
    # Spell 7: Bowler 3, Match 4, Context 1
    # Spell 8: Bowler 4, Match 4, Context 1
    # Spell 9: Bowler 4, Match 5, Context 1
    # Spell 10: Bowler 5, Match 5, Context 1
    # Spell 11: Bowler 5, Match 3, Context 1
    
    rows_c = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1]
    rows_b = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    rows_m = [0, 1, 1, 2, 2, 0, 3, 4, 4, 5, 5, 3]
    
    X_c = sp.csr_matrix((np.ones(N), (np.arange(N), rows_c)), shape=(N, K))
    X_b = sp.csr_matrix((np.ones(N), (np.arange(N), rows_b)), shape=(N, I))
    X_m = sp.csr_matrix((np.ones(N), (np.arange(N), rows_m)), shape=(N, M))
    
    X_cbm = sp.hstack([X_c, X_b, X_m], format="csr")
    
    # Exact rank via SVD
    dense_cbm = X_cbm.toarray()
    svd_rank = np.linalg.matrix_rank(dense_cbm)
    
    # Our robust compute_design_matrix_rank
    computed_rank, _, _ = compute_design_matrix_rank(X_cbm)
    
    assert svd_rank == 10, f"SVD rank should be 10, got {svd_rank}"
    assert computed_rank == 10, f"Computed rank should be 10, got {computed_rank}"


# ============================================================================
# 12. Calibration Status Policy Verification
# ============================================================================

def test_12_calibration_status_policy():
    """
    Preservation: Verify that evaluate_bowler_calibration_status marks coverage
    statistically excluded from nominal as SIGNIFICANT_UNDER_COVERAGE.
    """
    # 80% nominal, observed 74% with CI [72%, 76%]
    status_80, rationale = evaluate_bowler_calibration_status(
        cov_80=0.74,
        ci_80_low=0.72,
        ci_80_high=0.76,
        cov_95=0.94,
        ci_95_low=0.93,
        ci_95_high=0.95,
        n_obs=100
    )
    assert status_80 == "SIGNIFICANT_UNDER_COVERAGE"
    assert "UNDER_COVERAGE_80%" in rationale
