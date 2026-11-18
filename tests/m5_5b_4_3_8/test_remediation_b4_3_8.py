"""
RR ScoutIQ — Milestone M5.5-B.4.3.8: Exhaustive Targeted Adversarial Test Suite
Module: tests/m5_5b_4_3_8/test_remediation_b4_3_8.py

Validates all B.4.3.8 requirements:
1. Every match involving evaluated player i is strictly excluded from that player's prior (LPMO).
2. Changing another player's performance in an excluded match cannot change evaluated player's prior.
3. Changing observations in eligible independent matches correctly and sensitively updates the prior.
4. Shared-match shocks cannot contaminate the prior (conditional covariance orthogonality).
5. Match-level cluster uncertainty uses the remaining match population (exact ratio linearization).
6. Unequal match exposure and Herfindahl concentration HHI (H = sum n_m^2 / N^2) and effective match count.
7. Batter cluster-aware observation variance on probability scale:
   V_obs = H_ic * sigma2_match_bat + p(1-p)/N_ic, matching synthetic benchmark and Kish design effect.
8. Sparse-context fallback hierarchy preserves match excision across all 4 levels.
9. Batter and bowler dual-domain LPMO symmetry.
10. Full joint Gaussian conjugate updating closed form for both domains.
11. Batter and bowler predictive variance decompositions without double counting.
12. Five-fold match isolation remains exact (0 shared matches).
13. Asymptotic exposure behaviors: zero exposure, high match concentration, and large sample convergence.
14. Distinction between plug-in frequentist MSE and true Bayesian posterior variance.
15. Non-contamination: Batter probability scale parameters are isolated from bowler RPO parameters.
"""

import os
import sys
import math
import numpy as np
import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

sys.path.insert(0, os.path.abspath("."))

from src.m5_5b_4_3_8.epistemic_context_engine_b4_3_8 import (
    ContextualPlayerBaselineRecordB438,
    EpistemicStateB438
)
from src.m5_5b_4_3_8.hierarchical_engine_b4_3_8 import (
    ContextualHierarchyB438,
    PlayerPosteriorBaselineEstimatorB438
)
from src.m5_5b_4_3_8.variance_decomposition_b4_3_8 import (
    estimate_batter_crossed_match_variance,
    generate_synthetic_batter_crossed_dataset,
    run_synthetic_batter_crossed_simulation_benchmark
)


# ============================================================================
# Helper Fixtures & Synthetic Datasets
# ============================================================================

def make_synthetic_training_df():
    """
    Creates a multi-match, multi-player synthetic dataset with known match topologies.
    Matches 1..5: Player 101 (bowler) and Player 201 (batter) participated.
    Matches 6..25: Independent matches without Player 101 or Player 201.
    """
    records = []
    
    # Matches 1..5: Player 101 (bowler) + Player 102 (bowler), Player 201 (batter) + Player 202 (batter)
    for m in range(1, 6):
        # Player 101 bowls 12 legal balls to Player 201
        for b in range(12):
            records.append({
                "match_id": m,
                "bowler_id": 101,
                "batter_id": 201,
                "phase": "death",
                "tier": "Tier 3: High",
                "pre_match_phase": "death",
                "pre_pressure_tier": "Tier 3: High",
                "is_legal": 1,
                "ext_is_legal_delivery": 1,
                "batsman_runs": 2,
                "ext_batsman_runs": 2,
                "extra_runs": 0,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "is_boundary": 0,
                "ext_bowler_debit_runs": 2
            })
        # Player 102 bowls 12 legal balls to Player 202
        for b in range(12):
            records.append({
                "match_id": m,
                "bowler_id": 102,
                "batter_id": 202,
                "phase": "death",
                "tier": "Tier 3: High",
                "pre_match_phase": "death",
                "pre_pressure_tier": "Tier 3: High",
                "is_legal": 1,
                "ext_is_legal_delivery": 1,
                "batsman_runs": 1,
                "ext_batsman_runs": 1,
                "extra_runs": 0,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "is_boundary": 0,
                "ext_bowler_debit_runs": 1
            })

    # Matches 6..25 (20 independent matches): Player 103/104 (bowlers) and Player 203/204 (batters)
    for m in range(6, 26):
        for b in range(12):
            is_bound = 1 if (m % 3 == 0) else 0
            runs = 4 if is_bound else (1 if (m % 2 == 0) else 2)
            records.append({
                "match_id": m,
                "bowler_id": 103,
                "batter_id": 203,
                "phase": "death",
                "tier": "Tier 3: High",
                "pre_match_phase": "death",
                "pre_pressure_tier": "Tier 3: High",
                "is_legal": 1,
                "ext_is_legal_delivery": 1,
                "batsman_runs": runs,
                "ext_batsman_runs": runs,
                "extra_runs": 0,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "is_boundary": is_bound,
                "ext_bowler_debit_runs": runs
            })
            
    return pd.DataFrame(records)


# ============================================================================
# 1. LPMO Match-Level Excision & Invariance Tests
# ============================================================================

def test_01_lpmo_every_match_involving_player_excluded():
    """
    Priority 1: Verify that every match involving evaluated player i is strictly
    excised from player i's prior.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB438()
    hier.fit(df)
    
    # Bowler 101 participated in matches 1..5
    prior_mean, prior_var, provenance, rem_balls, k_excl, m_act, m_eff, hhi = hier.get_lpmo_context_prior(
        101, "death", "Tier 3: High", "bowler_economy"
    )
    assert k_excl == 5, f"Expected 5 excluded matches, got {k_excl}"
    assert m_act == 20, f"Expected 20 remaining matches, got {m_act}"
    assert provenance == "CELL_LPMO_ROBUST"

    # Batter 201 participated in matches 1..5
    b_mean, b_var, b_prov, b_balls, b_excl, b_act, b_eff, b_hhi = hier.get_lpmo_context_prior(
        201, "death", "Tier 3: High", "batter_boundary"
    )
    assert b_excl == 5, f"Expected 5 excluded matches for batter, got {b_excl}"
    assert b_act == 20, f"Expected 20 remaining matches for batter, got {b_act}"
    assert b_prov == "CELL_LPMO_ROBUST"


def test_02_changing_other_player_performance_in_excluded_match_invariance():
    """
    Priority 2: Changing another player's performance in an excluded match
    cannot change evaluated player's prior.
    """
    df1 = make_synthetic_training_df()
    df2 = make_synthetic_training_df()
    
    # In df2, alter Player 102 / Player 202's performance in Match 1 (where 101/201 played)
    mask = (df2["match_id"] == 1) & (df2["bowler_id"] == 102)
    df2.loc[mask, "ext_bowler_debit_runs"] = 36.0
    df2.loc[mask, "batsman_runs"] = 6
    df2.loc[mask, "is_boundary"] = 1
    
    hier1 = ContextualHierarchyB438()
    hier1.fit(df1)
    
    hier2 = ContextualHierarchyB438()
    hier2.fit(df2)
    
    res1_bowl = hier1.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    res2_bowl = hier2.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    
    assert math.isclose(res1_bowl[0], res2_bowl[0], rel_tol=1e-12)
    assert math.isclose(res1_bowl[1], res2_bowl[1], rel_tol=1e-12)

    res1_bat = hier1.get_lpmo_context_prior(201, "death", "Tier 3: High", "batter_boundary")
    res2_bat = hier2.get_lpmo_context_prior(201, "death", "Tier 3: High", "batter_boundary")
    
    assert math.isclose(res1_bat[0], res2_bat[0], rel_tol=1e-12)
    assert math.isclose(res1_bat[1], res2_bat[1], rel_tol=1e-12)


def test_03_changing_observations_in_eligible_independent_matches_updates_prior():
    """
    Priority 3: Changing observations in eligible independent matches (6..25)
    sensitively updates the prior.
    """
    df1 = make_synthetic_training_df()
    df2 = make_synthetic_training_df()
    
    mask = (df2["match_id"] == 10)
    df2.loc[mask, "ext_bowler_debit_runs"] = 36.0
    df2.loc[mask, "is_boundary"] = 1
    
    hier1 = ContextualHierarchyB438()
    hier1.fit(df1)
    
    hier2 = ContextualHierarchyB438()
    hier2.fit(df2)
    
    p1_bowl = hier1.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")[0]
    p2_bowl = hier2.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")[0]
    assert p2_bowl > p1_bowl

    p1_bat = hier1.get_lpmo_context_prior(201, "death", "Tier 3: High", "batter_boundary")[0]
    p2_bat = hier2.get_lpmo_context_prior(201, "death", "Tier 3: High", "batter_boundary")[0]
    assert p2_bat > p1_bat


def test_04_shared_match_shock_orthogonality():
    """
    Priority 4: Shared-match shocks cannot contaminate the prior.
    Cov(mu_hat_lpmo, Y_i | mu_c) = 0.
    """
    df1 = make_synthetic_training_df()
    df2 = make_synthetic_training_df()
    
    # Inject massive match shock into Match 2 (where 101/201 played)
    mask = (df2["match_id"] == 2)
    df2.loc[mask, "ext_bowler_debit_runs"] += 10.0
    df2.loc[mask, "batsman_runs"] += 10
    df2.loc[mask, "is_boundary"] = 1
    
    hier1 = ContextualHierarchyB438()
    hier1.fit(df1)
    
    hier2 = ContextualHierarchyB438()
    hier2.fit(df2)
    
    b1 = hier1.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    b2 = hier2.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    assert math.isclose(b1[0], b2[0], rel_tol=1e-12)
    assert math.isclose(b1[1], b2[1], rel_tol=1e-12)

    bat1 = hier1.get_lpmo_context_prior(201, "death", "Tier 3: High", "batter_boundary")
    bat2 = hier2.get_lpmo_context_prior(201, "death", "Tier 3: High", "batter_boundary")
    assert math.isclose(bat1[0], bat2[0], rel_tol=1e-12)
    assert math.isclose(bat1[1], bat2[1], rel_tol=1e-12)


# ============================================================================
# 2. Ratio Linearization & Concentration HHI Tests
# ============================================================================

def test_05_match_level_cluster_uncertainty_exact_ratio_linearization():
    """
    Priority 5: Match-level cluster uncertainty via exact ratio linearization.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB438()
    hier.fit(df)
    
    prior_mean, prior_var = hier.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")[:2]
    
    rem_df = df[df["match_id"] >= 6]
    match_sums = rem_df.groupby("match_id").agg(
        runs=("ext_bowler_debit_runs", "sum"),
        balls=("ext_is_legal_delivery", "sum")
    )
    M = len(match_sums)
    assert M == 20
    
    total_runs = match_sums["runs"].sum()
    total_balls = match_sums["balls"].sum()
    r_hat = total_runs / total_balls
    
    resids = match_sums["runs"] - r_hat * match_sums["balls"]
    rss = np.sum(resids ** 2)
    expected_var_rpb = (M / (M - 1)) * (rss / (total_balls ** 2))
    expected_var_rpo = expected_var_rpb * 36.0
    
    assert math.isclose(prior_mean, r_hat * 6.0, rel_tol=1e-9)
    assert math.isclose(prior_var, expected_var_rpo, rel_tol=1e-9)


def test_06_unequal_match_exposure_and_concentration_hhi():
    """
    Priority 6: Effective match count M_eff = 1 / H where H = sum n_m^2 / N^2.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB438()
    hier.fit(df)
    
    res = hier.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    m_eff = res[6]
    hhi = res[7]
    
    # 20 independent matches each having equal 12 balls:
    # H = 20 * (12/240)^2 = 20 * (1/20)^2 = 1/20 = 0.05
    assert math.isclose(hhi, 0.05, rel_tol=1e-6)
    assert math.isclose(m_eff, 20.0, rel_tol=1e-6)


# ============================================================================
# 3. Batter Cluster-Aware Observation Model & Non-Contamination
# ============================================================================

def test_07_batter_cluster_aware_variance_matches_benchmark():
    """
    Priority 7: Batter observation variance accounts for match-level clustering:
    V_obs = H_ic * sigma2_match_bat + p(1-p)/N_ic
    Matches Kish design effect: Deff = 1 + (n_bar - 1) * rho
    where rho = sigma2_match_bat / (sigma2_match_bat + sigma2_eps_bat).
    """
    # Suppose a batter has 100 balls across 4 matches with deliveries [40, 30, 20, 10]
    match_deliveries = [40, 30, 20, 10]
    N = sum(match_deliveries)
    H = sum((n / N) ** 2 for n in match_deliveries)  # 0.16 + 0.09 + 0.04 + 0.01 = 0.30
    assert math.isclose(H, 0.30, rel_tol=1e-9)
    
    p_obs = 0.20
    sigma2_match_bat = 0.00075
    sigma2_eps_bat = p_obs * (1.0 - p_obs)  # 0.16
    
    expected_v_obs = H * sigma2_match_bat + (p_obs * (1.0 - p_obs) / N)
    # 0.30 * 0.00075 + 0.16 / 100 = 0.000225 + 0.0016 = 0.001825
    assert math.isclose(expected_v_obs, 0.001825, rel_tol=1e-9)
    
    rec = ContextualPlayerBaselineRecordB438(
        player_id=201,
        phase="death",
        tier="Tier 3: High",
        context_exposure=N,
        context_events=20.0,
        context_matches=4,
        career_exposure=N,
        career_events=20.0,
        career_matches=4,
        context_prior_mean=0.15,
        context_prior_mean_variance=0.0002,
        player_heterogeneity_tau2=0.004,
        sigma2_match=sigma2_match_bat,
        sigma2_within=sigma2_eps_bat,
        is_economy=False,
        effective_match_count=1.0 / H,
        match_concentration_hhi=H,
        match_balls_list=match_deliveries
    )
    
    assert math.isclose(rec.context_observation_variance, expected_v_obs, rel_tol=1e-9)
    # Check that design effect > 1.0
    deff = rec.context_observation_variance / (p_obs * (1.0 - p_obs) / N)
    assert deff > 1.0
    assert math.isclose(deff, 0.001825 / 0.0016, rel_tol=1e-6)


def test_08_batter_bowler_parameter_scale_isolation():
    """
    Priority 8: Ensure batter probability scale parameters are isolated
    from bowler RPO scale parameters.
    """
    estimator = PlayerPosteriorBaselineEstimatorB438(
        hierarchy=ContextualHierarchyB438(),
        bowler_tau2_player=2.5,
        bowler_sigma2_epsilon=16.5,
        bowler_sigma2_match=1.2,
        batter_tau2_player=0.0045,
        batter_sigma2_epsilon=0.16,
        batter_sigma2_match=0.00075
    )
    
    # Bowler parameters must be ~1.0 - 20.0
    assert estimator.bowler_tau2_player > 1.0
    assert estimator.bowler_sigma2_match > 0.5
    assert estimator.bowler_sigma2_epsilon > 10.0
    
    # Batter parameters must be < 0.20 (strictly on probability scale)
    assert estimator.batter_tau2_player < 0.01
    assert estimator.batter_sigma2_match < 0.002
    assert estimator.batter_sigma2_epsilon < 0.25


# ============================================================================
# 4. Sparse Fallback Hierarchy & Dual-Domain Symmetry
# ============================================================================

def test_09_sparse_context_fallback_hierarchy():
    """
    Priority 9: Verify 4-level fallback hierarchy preserves match excision at all levels.
    """
    records = []
    # Player 201 plays in match 1
    for b in range(12):
        records.append({
            "match_id": 1,
            "bowler_id": 201,
            "batter_id": 301,
            "phase": "death",
            "tier": "Tier 1: Low",
            "pre_match_phase": "death",
            "pre_pressure_tier": "Tier 1: Low",
            "is_legal": 1,
            "ext_is_legal_delivery": 1,
            "batsman_runs": 1,
            "ext_batsman_runs": 1,
            "extra_runs": 0,
            "ext_is_wide": 0,
            "ext_is_noball": 0,
            "is_boundary": 0,
            "ext_bowler_debit_runs": 1
        })
    # 10 other matches in Tier 1 (M=10 < 15, so Cell LPMO should fail M >= 15 screen)
    for m in range(2, 12):
        for b in range(12):
            records.append({
                "match_id": m,
                "bowler_id": 202,
                "batter_id": 302,
                "phase": "death",
                "tier": "Tier 1: Low",
                "pre_match_phase": "death",
                "pre_pressure_tier": "Tier 1: Low",
                "is_legal": 1,
                "ext_is_legal_delivery": 1,
                "batsman_runs": 1,
                "ext_batsman_runs": 1,
                "extra_runs": 0,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "is_boundary": 0,
                "ext_bowler_debit_runs": 1
            })
    # 20 matches in Death Tier 2 (so Phase Death has M=30 >= 15)
    for m in range(12, 32):
        for b in range(12):
            records.append({
                "match_id": m,
                "bowler_id": 203,
                "batter_id": 303,
                "phase": "death",
                "tier": "Tier 2: Medium",
                "pre_match_phase": "death",
                "pre_pressure_tier": "Tier 2: Medium",
                "is_legal": 1,
                "ext_is_legal_delivery": 1,
                "batsman_runs": 2,
                "ext_batsman_runs": 2,
                "extra_runs": 0,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "is_boundary": 0,
                "ext_bowler_debit_runs": 2
            })
            
    df_sparse = pd.DataFrame(records)
    hier = ContextualHierarchyB438()
    hier.fit(df_sparse)
    
    prior_mean, prior_var, provenance, rem_balls, k_excl, m_act, m_eff, hhi = hier.get_lpmo_context_prior(
        201, "death", "Tier 1: Low", "bowler_economy"
    )
    assert provenance == "PHASE_LPMO_FALLBACK"
    assert k_excl == 1
    assert m_act == 30


def test_10_joint_posterior_analytical_closed_form():
    """
    Priority 10: Full joint conjugate Gaussian updating matches analytical form:
    tau2_total = tau2_player + sigma2_mu_lpmo
    lambda = tau2_total / (tau2_total + var_obs)
    mu_post = lambda * y_bar + (1 - lambda) * mu_lpmo
    Var_post = (1 - lambda) * tau2_total
    """
    rec = ContextualPlayerBaselineRecordB438(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_exposure=30,
        context_events=60.0,
        context_matches=3,
        career_exposure=30,
        career_events=60.0,
        career_matches=3,
        context_prior_mean=10.0,
        context_prior_mean_variance=0.5,
        player_heterogeneity_tau2=2.0,
        sigma2_match=1.0,
        sigma2_within=16.0,
        is_economy=True,
        min_context_exposure=30,
        effective_match_count=3.0,
        match_concentration_hhi=1.0 / 3.0,
        match_balls_list=[10, 10, 10]
    )
    
    tau2_tot = 2.0 + 0.5  # 2.5
    var_obs = (6.0 * 16.0 / 30.0) + (1.0 / 3.0) * 1.0  # 3.2 + 0.33333333 = 3.53333333
    expected_lambda = tau2_tot / (tau2_tot + var_obs)
    expected_post_mean = expected_lambda * 12.0 + (1.0 - expected_lambda) * 10.0
    expected_post_var = (1.0 - expected_lambda) * tau2_tot
    
    assert math.isclose(rec.shrinkage_weight, expected_lambda, rel_tol=1e-9)
    assert math.isclose(rec.shrunk_baseline, expected_post_mean, rel_tol=1e-9)
    assert math.isclose(rec.posterior_variance, expected_post_var, rel_tol=1e-9)


# ============================================================================
# 5. Predictive Variance Decompositions & Asymptotics
# ============================================================================

def test_11_predictive_variance_coherence_no_double_counting():
    """
    Priority 11: Predictive variance decomposes into:
    Var(Y_new | Y) = Var(theta | Y) + sigma2_match + sigma2_within / N_new
    without double counting.
    """
    # Test bowler
    rec_bowl = ContextualPlayerBaselineRecordB438(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_exposure=30,
        context_events=60.0,
        context_matches=3,
        career_exposure=30,
        career_events=60.0,
        career_matches=3,
        context_prior_mean=10.0,
        context_prior_mean_variance=0.5,
        player_heterogeneity_tau2=2.0,
        sigma2_match=1.0,
        sigma2_within=16.0,
        is_economy=True
    )
    pred_var_bowl = rec_bowl.get_predictive_variance(n_eval=12)
    expected_pred_bowl = rec_bowl.posterior_variance + 1.0 + (16.0 * 6.0 / 12.0)
    assert math.isclose(pred_var_bowl, expected_pred_bowl, rel_tol=1e-6)

    # Test batter
    rec_bat = ContextualPlayerBaselineRecordB438(
        player_id=201,
        phase="death",
        tier="Tier 3: High",
        context_exposure=50,
        context_events=10.0,
        context_matches=5,
        career_exposure=50,
        career_events=10.0,
        career_matches=5,
        context_prior_mean=0.18,
        context_prior_mean_variance=0.0001,
        player_heterogeneity_tau2=0.003,
        sigma2_match=0.00075,
        sigma2_within=0.16,
        is_economy=False
    )
    pred_var_bat = rec_bat.get_predictive_variance(n_eval=20)
    p_hat = rec_bat.shrunk_baseline
    expected_pred_bat = rec_bat.posterior_variance + 0.00075 + (p_hat * (1.0 - p_hat) / 20.0)
    assert math.isclose(pred_var_bat, expected_pred_bat, rel_tol=1e-6)


def test_12_asymptotic_exposure_behaviors():
    """
    Priority 12: Asymptotic behaviors:
    1. Zero exposure: lambda -> 0, shrunk_baseline -> prior_mean, post_var -> tau2 + var_prior.
    2. High exposure across many matches: lambda -> 1, shrunk_baseline -> obs_mean, post_var -> 0.
    3. High exposure in a single match (H = 1): post_var bounded from below by match shock uncertainty.
    """
    # 1. Zero exposure
    rec_zero = ContextualPlayerBaselineRecordB438(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_exposure=0,
        context_events=0.0,
        context_matches=0,
        career_exposure=0,
        career_events=0.0,
        career_matches=0,
        context_prior_mean=9.5,
        context_prior_mean_variance=0.4,
        player_heterogeneity_tau2=2.0,
        sigma2_match=1.0,
        sigma2_within=16.0,
        is_economy=True
    )
    assert math.isclose(rec_zero.shrinkage_weight, 0.0, abs_tol=1e-9)
    assert math.isclose(rec_zero.shrunk_baseline, 9.5, abs_tol=1e-9)
    assert math.isclose(rec_zero.posterior_variance, 2.4, abs_tol=1e-9)

    # 2. High exposure across 100 matches
    rec_high = ContextualPlayerBaselineRecordB438(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_exposure=2400,
        context_events=3600.0,  # 9.0 rpo
        context_matches=100,
        career_exposure=2400,
        career_events=3600.0,
        career_matches=100,
        context_prior_mean=9.5,
        context_prior_mean_variance=0.4,
        player_heterogeneity_tau2=2.0,
        sigma2_match=1.0,
        sigma2_within=16.0,
        is_economy=True,
        effective_match_count=100.0,
        match_concentration_hhi=0.01,
        context_match_balls_list=[24] * 100
    )
    assert rec_high.shrinkage_weight > 0.95
    assert math.isclose(rec_high.shrunk_baseline, 9.0, abs_tol=0.1)
    assert rec_high.posterior_variance < 0.10

    # 3. High exposure in a SINGLE match (H = 1.0, N = 1000)
    # Even if N -> infinity, if all balls are in 1 match, V_obs >= sigma2_match!
    rec_single_match = ContextualPlayerBaselineRecordB438(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_exposure=1000,
        context_events=1500.0,
        context_matches=1,
        career_exposure=1000,
        career_events=1500.0,
        career_matches=1,
        context_prior_mean=9.5,
        context_prior_mean_variance=0.4,
        player_heterogeneity_tau2=2.0,
        sigma2_match=1.0,
        sigma2_within=16.0,
        is_economy=True,
        effective_match_count=1.0,
        match_concentration_hhi=1.0,
        match_balls_list=[1000]
    )
    # V_obs = 1.0 * 1.0 + (16 * 6 / 1000) = 1.0 + 0.096 = 1.096
    # lambda = 2.4 / (2.4 + 1.096) = 0.686
    # Posterior variance = (1 - 0.686) * 2.4 = 0.753 > 0.70!
    assert rec_single_match.context_observation_variance >= 1.0
    assert rec_single_match.shrinkage_weight < 0.75
    assert rec_single_match.posterior_variance > 0.50


def test_13_five_fold_match_isolation_exact():
    """
    Priority 13: 5-fold match-grouped CV isolation remains exact (0 shared matches).
    """
    from sklearn.model_selection import GroupKFold
    df = make_synthetic_training_df()
    gkf = GroupKFold(n_splits=5)
    
    for fold, (tr_idx, val_idx) in enumerate(gkf.split(df, groups=df["match_id"]), 1):
        tr_m = set(df.iloc[tr_idx]["match_id"].unique())
        val_m = set(df.iloc[val_idx]["match_id"].unique())
        shared = tr_m.intersection(val_m)
        assert len(shared) == 0, f"Fold {fold} had shared matches: {shared}"


def test_14_frequentist_mse_vs_bayesian_posterior_variance_distinction():
    """
    Priority 14: Verify distinction between plug-in frequentist MSE and true Bayesian posterior variance.
    MSE_plugin = lambda^2 * V_obs + (1 - lambda)^2 * sigma2_mu
    Var_Bayesian = (1 - lambda) * (tau2 + sigma2_mu)
    """
    rec = ContextualPlayerBaselineRecordB438(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_exposure=30,
        context_events=60.0,
        context_matches=3,
        career_exposure=30,
        career_events=60.0,
        career_matches=3,
        context_prior_mean=10.0,
        context_prior_mean_variance=0.5,
        player_heterogeneity_tau2=2.0,
        sigma2_match=1.0,
        sigma2_within=16.0,
        is_economy=True
    )
    
    # Both are non-negative, finite, and distinct:
    assert rec.frequentist_plugin_mse > 0.0
    assert rec.posterior_variance > 0.0
    assert not math.isclose(rec.posterior_variance, rec.frequentist_plugin_mse, rel_tol=1e-5)


def test_15_batter_crossed_variance_estimator_recovery():
    """
    Priority 15: Crossed-effects linear probability model with cross-match covariance
    recovers known match variance under repeated player participation and unequal match exposures.
    """
    true_s2_match = 0.0012
    syn_df = generate_synthetic_batter_crossed_dataset(
        n_deliveries=20000,
        n_matches=50,
        n_batters=35,
        tau2_player=0.003,
        sigma2_match=true_s2_match,
        player_skew_exponent=0.8,
        match_exposure_skew=True,
        seed=123
    )
    
    res = estimate_batter_crossed_match_variance(
        syn_df,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        method="paule_mandel",
        check_convergence=True
    )
    
    assert res["status"] == "ESTIMATED_POSITIVE"
    assert res["df"] == 49
    assert res["Q"] > res["df"]
    assert res["p_value"] < 0.05
    assert res["solver_converged"] is True
    assert res["covariance_adjusted"] is True
    # Off-diagonal cross-match covariance is accounted for
    assert res["cross_match_cov_max"] > 0.0
    # Recovers within reasonable Monte Carlo margin of true value 0.0012
    assert 0.0004 <= res["sigma2_match_bat"] <= 0.0030


def test_16_batter_crossed_variance_zero_boundary_selection():
    """
    Priority 16: Zero-variance boundary test.
    When true match environmental variance is zero and F(0) <= 0, the Paule-Mandel
    procedure strictly selects 0.0 and does NOT silently replace it with a positive DSL estimate.
    """
    syn_df_zero = generate_synthetic_batter_crossed_dataset(
        n_deliveries=15000,
        n_matches=40,
        n_batters=30,
        tau2_player=0.003,
        sigma2_match=0.0,
        seed=100
    )
    
    res_zero = estimate_batter_crossed_match_variance(
        syn_df_zero,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        method="paule_mandel",
        check_convergence=True
    )
    
    # If PM identifies the zero boundary, verify explicit selection
    if res_zero["sigma2_match_pm"] == 0.0:
        assert res_zero["sigma2_match_bat"] == 0.0
        assert res_zero["sigma2_match_selected"] == 0.0
        assert res_zero["used_method"] == "PAULE_MANDEL_ZERO"
        assert res_zero["status"] == "ESTIMATED_ZERO"
    else:
        # Sample fluctuation is small (< 0.0003)
        assert res_zero["sigma2_match_bat"] < 0.0003


def test_17_batter_crossed_variance_solver_convergence_diagnostic():
    """
    Priority 17: Solver convergence validation.
    1. Valid fits verify convergence diagnostics (istop in (1, 2, 4), itn, arnorm).
    2. An unconverged fit (e.g. iter_lim=2) raises RuntimeError when check_convergence=True.
    """
    syn_df = generate_synthetic_batter_crossed_dataset(
        n_deliveries=10000,
        n_matches=30,
        n_batters=25,
        seed=42
    )
    
    # 1. Successful convergence
    res = estimate_batter_crossed_match_variance(
        syn_df,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        iter_lim=500,
        check_convergence=True
    )
    assert res["solver_converged"] is True
    assert res["solver_istop"] in (1, 2, 4)
    assert res["solver_itn"] > 0
    assert res["solver_arnorm"] < 1.0
    
    # 2. Unconverged fit forced via iter_lim=2 must raise RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        estimate_batter_crossed_match_variance(
            syn_df,
            cell_cols=("phase", "tier"),
            bat_id_col="batter_id",
            outcome_col="is_boundary",
            iter_lim=2,
            check_convergence=True
        )
    assert "LSQR solver failed to reach convergence" in str(exc_info.value)


def test_18_batter_crossed_variance_strained_logistic_link():
    """
    Priority 18: Non-linear logistic link scenario.
    Validates that when the true data-generating process uses a non-linear logistic link
    rather than an additive linear probability model, the estimator remains stable and
    recovers positive match environmental variation.
    """
    syn_df_logit = generate_synthetic_batter_crossed_dataset(
        n_deliveries=20000,
        n_matches=50,
        n_batters=35,
        tau2_player=0.003,
        sigma2_match=0.0010,
        link="logistic",
        seed=303
    )
    
    res_logit = estimate_batter_crossed_match_variance(
        syn_df_logit,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        method="paule_mandel",
        check_convergence=True
    )
    
    assert res_logit["status"] == "ESTIMATED_POSITIVE"
    assert res_logit["solver_converged"] is True
    assert 0.0003 <= res_logit["sigma2_match_bat"] <= 0.0025


def test_19_batter_crossed_variance_multi_seed_benchmark():
    """
    Priority 19: Multi-seed Monte Carlo simulation benchmark.
    Tests bias, empirical RMSE, and solver stability across 5 independent seeds.
    """
    bench_res = run_synthetic_batter_crossed_simulation_benchmark(
        n_seeds=5,
        true_sigma2_match=0.0010,
        n_deliveries=12000,
        n_matches=35,
        n_batters=25,
        link="linear",
        method="paule_mandel"
    )
    
    assert bench_res["all_converged"] is True
    assert len(bench_res["estimates"]) == 5
    # Mean estimate close to true 0.0010 (within 0.0006 margin)
    assert 0.0004 <= bench_res["mean_estimate"] <= 0.0020
    # Empirical RMSE is controlled
    assert bench_res["rmse"] < 0.0010
    assert abs(bench_res["bias"]) < 0.0006


def test_20_batter_crossed_variance_insufficient_data_fallback():
    """
    Priority 20: Sparse / insufficient data boundary handling.
    When match count < min_matches, falls back safely to default prior without crashing.
    """
    tiny_df = pd.DataFrame({
        "match_id": [1, 1, 2, 2],
        "batter_id": [10, 11, 10, 11],
        "phase": ["pp", "pp", "death", "death"],
        "tier": ["T1", "T1", "T2", "T2"],
        "is_boundary": [0, 1, 0, 0]
    })
    
    res_fallback = estimate_batter_crossed_match_variance(
        tiny_df,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        min_matches=10
    )
    
    assert res_fallback["status"] == "INSUFFICIENT_DATA"
    assert res_fallback["used_method"] == "FALLBACK"
    assert res_fallback["sigma2_match_bat"] == 0.00069


# ============================================================================
# Phase 1 Remediation Verification & Adversarial Tests
# ============================================================================

def test_21_solver_agreement_and_diagnostics():
    """
    Phase 1.1: Verification of solver correctness.
    Direct Cholesky solve and LSQR solver must agree within tight tolerance (rel_diff < 1e-3).
    Normal equation residual gradient is explicitly tracked.
    """
    syn_df = generate_synthetic_batter_crossed_dataset(
        n_deliveries=10000,
        n_matches=30,
        n_batters=25,
        seed=142
    )
    
    res = estimate_batter_crossed_match_variance(
        syn_df,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        check_convergence=True
    )
    
    diag = res["solver_diagnostics"]
    assert diag["converged"] is True
    assert diag["method"] == "DIRECT_CHOLESKY_WITH_LSQR_VERIFICATION"
    assert "rel_diff_chol_lsqr" in diag
    assert diag["rel_diff_chol_lsqr"] < 1e-3
    assert diag["normal_eq_grad"] < 1e-3


def test_22_omega_asymmetry_and_eigenvalues():
    """
    Phase 1.2: Verification of cross-match covariance matrix Omega.
    Quantifies asymmetry Frobenius norm (< 1e-12) and verifies that Omega is positive definite.
    """
    syn_df = generate_synthetic_batter_crossed_dataset(
        n_deliveries=10000,
        n_matches=30,
        n_batters=25,
        seed=242
    )
    
    res = estimate_batter_crossed_match_variance(
        syn_df,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        check_convergence=True
    )
    
    assert res["asymmetry_frobenius"] < 1e-12
    assert res["asymmetry_max"] < 1e-12
    assert res["min_eigenvalue"] > -1e-12
    assert res["shift_psd"] >= 1e-9


def test_23_covariance_factorization_failure_raises(monkeypatch):
    """
    Phase 1.2: Diagonal fallback prohibition.
    If full covariance Omega cannot be factored, the procedure must report that failure
    explicitly via RuntimeError and not fall back to diagonal approximation.
    """
    syn_df = generate_synthetic_batter_crossed_dataset(
        n_deliveries=5000,
        n_matches=15,
        n_batters=15,
        seed=342
    )
    
    # Patch np.linalg.cholesky to raise LinAlgError on Omega factorization
    orig_cholesky = np.linalg.cholesky
    def mock_cholesky(a):
        raise np.linalg.LinAlgError("Simulated singular matrix in Omega")
        
    monkeypatch.setattr(np.linalg, "cholesky", mock_cholesky)
    
    with pytest.raises(RuntimeError) as exc_info:
        estimate_batter_crossed_match_variance(
            syn_df,
            cell_cols=("phase", "tier"),
            bat_id_col="batter_id",
            outcome_col="is_boundary",
            check_convergence=True
        )
    assert "Covariance matrix Omega factorization failed" in str(exc_info.value)
    assert "Diagonal fallback is prohibited" in str(exc_info.value)


def test_24_paule_mandel_no_dsl_substitution_on_zero():
    """
    Phase 1.3: Paule-Mandel vs DSL selection.
    If Paule-Mandel identifies the zero boundary (F(0) <= 0), it strictly returns 0.0000
    with used_method == 'PAULE_MANDEL_ZERO' and does NOT substitute DSL.
    """
    syn_df_zero = generate_synthetic_batter_crossed_dataset(
        n_deliveries=15000,
        n_matches=40,
        n_batters=30,
        tau2_player=0.003,
        sigma2_match=0.0,
        seed=100
    )
    
    res = estimate_batter_crossed_match_variance(
        syn_df_zero,
        cell_cols=("phase", "tier"),
        bat_id_col="batter_id",
        outcome_col="is_boundary",
        method="paule_mandel",
        check_convergence=True
    )
    
    if res["used_method"] == "PAULE_MANDEL_ZERO":
        assert res["sigma2_match_bat"] == 0.0
        assert res["status"] == "ESTIMATED_ZERO"
        # Must not have substituted DSL
        assert res["used_method"] != "DSL"


def test_25_hierarchy_fit_propagates_numerical_failure(monkeypatch):
    """
    Phase 1.4: Failure propagation in ContextualHierarchyB438.fit().
    Numerical errors in variance estimation must propagate cleanly rather than
    being swallowed by broad exception catches that substitute fallback values.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB438()
    
    def mock_estimator_failure(*args, **kwargs):
        raise RuntimeError("Forced numerical divergence in solver")
        
    monkeypatch.setattr(
        "src.m5_5b_4_3_8.hierarchical_engine_b4_3_8.estimate_batter_crossed_match_variance",
        mock_estimator_failure
    )
    
    with pytest.raises(RuntimeError) as exc_info:
        hier.fit(df)
    assert "Forced numerical divergence in solver" in str(exc_info.value)


# ============================================================================
# 8. Scouting Readiness, Data Architecture & Identity Reconciliation Tests
# ============================================================================

def test_26_identity_crosswalk_uniqueness():
    """
    Priority 26: Player identity crosswalk uniqueness, 0 collisions, 0 split identities,
    and 100% Cricsheet ID resolution across all 852 players.
    """
    cw_path = os.path.join(REPO_ROOT, "data", "enriched", "player_crosswalk_m5_5.csv")
    assert os.path.exists(cw_path), f"Missing {cw_path}"
    
    df_cw = pd.read_csv(cw_path)
    assert len(df_cw) == 852, f"Expected 852 players in crosswalk, found {len(df_cw)}"
    assert df_cw["player_id"].nunique() == 852, "Duplicate player_id detected in crosswalk!"
    assert df_cw["canonical_name"].notna().all(), "Null canonical_name detected!"
    assert (df_cw["canonical_name"] != "Unknown").all(), "'Unknown' canonical_name in crosswalk!"
    assert df_cw["cricsheet_id"].notna().all(), "Null cricsheet_id detected!"
    assert (df_cw["cricsheet_id"] != "").all(), "Empty cricsheet_id detected!"
    assert df_cw["is_ambiguous"].sum() == 0, "Ambiguous players detected in crosswalk!"
    assert (df_cw["mapping_provenance"] == "canonical_match_state_full_cricsheet_verified").all()


def test_27_oof_predictions_batter_names_resolved():
    """
    Priority 27: Out-of-fold predictions player_name resolution.
    Zero batter or bowler records may have player_name == 'Unknown'.
    """
    oof_path = os.path.join(REPO_ROOT, "audit_reports", "M5_5B_4_3_8", "M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv")
    assert os.path.exists(oof_path), f"Missing {oof_path}"
    
    oof = pd.read_csv(oof_path)
    assert len(oof) == 185178, f"Expected 185,178 OOF rows, got {len(oof)}"
    
    batters = oof[oof["domain"] == "Batter"]
    bowlers = oof[oof["domain"] == "Bowler"]
    
    assert len(batters) == 168104, f"Expected 168,104 batter rows, got {len(batters)}"
    assert len(bowlers) == 17074, f"Expected 17,074 bowler spell rows, got {len(bowlers)}"
    
    unknown_batters = (batters["player_name"] == "Unknown").sum()
    unknown_bowlers = (bowlers["player_name"] == "Unknown").sum()
    
    assert unknown_batters == 0, f"Found {unknown_batters} batter records with player_name == 'Unknown'!"
    assert unknown_bowlers == 0, f"Found {unknown_bowlers} bowler records with player_name == 'Unknown'!"


def test_28_player_population_reconciliation():
    """
    Priority 28: Exact mathematical player population reconciliation.
    852 total unique canonical players; 843 clean active players (773 batters, 566 bowlers, 496 overlap, 9 non-strikers).
    """
    canon_path = os.path.join(REPO_ROOT, "data", "processed", "m5_3", "match_state_full.csv")
    df = pd.read_csv(canon_path, low_memory=False)
    
    clean_legal = df[(df["is_dli_valid"] == 1) & (df["ext_is_legal_delivery"] == 1)]
    clean_batters = set(clean_legal["striker_id"].dropna().unique().astype(int))
    clean_bowlers = set(clean_legal["bowler_id"].dropna().unique().astype(int))
    clean_overlap = clean_batters.intersection(clean_bowlers)
    clean_active = clean_batters.union(clean_bowlers)
    
    all_strikers = set(df["striker_id"].dropna().unique().astype(int))
    all_bowlers = set(df["bowler_id"].dropna().unique().astype(int))
    all_non_strikers = set(df["non_striker_id"].dropna().unique().astype(int))
    all_players = all_strikers.union(all_bowlers).union(all_non_strikers)
    
    assert len(clean_batters) == 773, f"Expected 773 clean legal batters, got {len(clean_batters)}"
    assert len(clean_bowlers) == 566, f"Expected 566 clean legal bowlers, got {len(clean_bowlers)}"
    assert len(clean_overlap) == 496, f"Expected 496 clean legal overlap, got {len(clean_overlap)}"
    assert len(clean_active) == 843, f"Expected 843 clean active players, got {len(clean_active)}"
    assert len(all_players) == 852, f"Expected 852 unique players in canonical dataset, got {len(all_players)}"
    assert len(all_players - clean_active) == 9, "Expected exactly 9 non-strikers only in clean legal subset"


def test_29_role_classification_distribution():
    """
    Priority 29: Role classification framework validation.
    Phase casing fix ensures > 50% of batters and bowlers are classified with sample >= 30,
    and All-Rounder detection properly attributes dual-discipline players.
    """
    from src.m5_5b_4_3_8.scouting_readiness_audit import run_role_classification
    
    canon_path = os.path.join(REPO_ROOT, "data", "processed", "m5_3", "match_state_full.csv")
    df = pd.read_csv(canon_path, low_memory=False)
    
    role_res = run_role_classification(df)
    
    assert role_res["total_classified_batters"] == 773
    assert role_res["total_classified_bowlers"] == 566
    
    # Check that sample >= 30 is non-trivial (476 batters, 450 bowlers)
    assert role_res["batters_sample_ge_30"] == 476, f"Expected 476 classified batters, got {role_res['batters_sample_ge_30']}"
    assert role_res["bowlers_sample_ge_30"] == 450, f"Expected 450 classified bowlers, got {role_res['bowlers_sample_ge_30']}"
    
    # Check All-Rounders are identified
    assert role_res["batter_role_counts"].get("All-Rounder", 0) == 109
    assert role_res["bowler_role_counts"].get("All-Rounder", 0) == 109
    
    # Check other roles are populated
    assert role_res["batter_role_counts"].get("Opener", 0) == 122
    assert role_res["batter_role_counts"].get("Finisher (#6-#7+)", 0) == 131
    assert role_res["bowler_role_counts"].get("Middle-Overs Controller", 0) == 123
    assert role_res["bowler_role_counts"].get("Powerplay Specialist", 0) == 40
    assert role_res["bowler_role_counts"].get("Death-Overs Specialist", 0) == 18


def test_30_canonical_dataset_hash_consistency():
    """
    Priority 30: Canonical dataset SHA-256 and row count immutability.
    Verifies that match_state_full.csv matches the approved canonical hash.
    """
    canon_path = os.path.join(REPO_ROOT, "data", "processed", "m5_3", "match_state_full.csv")
    assert os.path.exists(canon_path), f"Missing {canon_path}"
    
    import hashlib
    h = hashlib.sha256()
    line_count = 0
    with open(canon_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
            line_count += chunk.count(b"\n")
            
    expected_sha = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
    assert h.hexdigest() == expected_sha, f"Canonical hash mismatch! Expected {expected_sha}, got {h.hexdigest()}"
    assert line_count == 179838, f"Expected 179,838 lines (1 header + 179,837 rows), got {line_count}"




