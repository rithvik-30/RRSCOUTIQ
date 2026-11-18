"""
RR ScoutIQ — Milestone M5.5-B.4.3.7: Exhaustive Targeted Adversarial Test Suite
Module: tests/m5_5b_4_3_7/test_remediation_b4_3_7.py

Validates all 12 Priority 5 requirements:
1. Every match involving evaluated player i is strictly excluded from that player's prior.
2. Changing another player's performance in an excluded match cannot change evaluated player's prior.
3. Changing observations in eligible independent matches correctly changes the prior.
4. Shared-match shocks cannot contaminate the prior (conditional covariance orthogonality).
5. Match-level cluster uncertainty uses the remaining match population (exact ratio linearization).
6. Unequal match exposure and concentration HHI / effective match count handled correctly.
7. Sparse phase-tier contexts use valid uncontaminated fallbacks (retaining match excision).
8. Batter and bowler implementations both obey LPMO.
9. Joint posterior calculations remain analytically correct under Full Conjugate Gaussian updating.
10. Production OOF predictions use LPMO rather than the old LOPO calculation.
11. Five-fold match isolation remains exact (0 shared matches).
12. Predictive variance does not double-count uncertainty.
"""

import os
import sys
import math
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath("."))

from src.m5_5b_4_3_7.epistemic_context_engine_b4_3_7 import (
    ContextualPlayerBaselineRecordB437,
    EpistemicStateB437
)
from src.m5_5b_4_3_7.hierarchical_engine_b4_3_7 import (
    ContextualHierarchyB437,
    PlayerPosteriorBaselineEstimatorB437
)


# ============================================================================
# Helper Fixtures & Synthetic Datasets
# ============================================================================

def make_synthetic_training_df():
    """
    Creates a multi-match, multi-player synthetic dataset with known match topologies.
    Matches 1..5: Player 101 participated (with other players).
    Matches 6..25: Independent matches without Player 101.
    """
    records = []
    
    # Matches 1..5: Player 101 (evaluated) + Player 102 (other bowler)
    for m in range(1, 6):
        # Player 101 bowls 12 legal balls in match m, conceding 24 runs (econ 12.0)
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
        # Player 102 bowls 12 legal balls in match m, conceding 12 runs (econ 6.0)
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

    # Matches 6..25 (20 independent matches): Player 103 and Player 104
    for m in range(6, 26):
        for b in range(12):
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
                "batsman_runs": 1 if (m % 2 == 0) else 2,
                "ext_batsman_runs": 1 if (m % 2 == 0) else 2,
                "extra_runs": 0,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "is_boundary": 1 if (m % 3 == 0) else 0,
                "ext_bowler_debit_runs": 1 if (m % 2 == 0) else 2
            })
            
    return pd.DataFrame(records)


# ============================================================================
# 1. LPMO Match-Level Excision Tests (Priorities 1, 2, 3, 4)
# ============================================================================

def test_01_lpmo_every_match_involving_player_excluded():
    """
    Priority 5.1: Verify that every match involving evaluated player i is strictly
    excised from player i's prior.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB437()
    hier.fit(df)
    
    # Player 101 participated in matches 1..5
    prior_mean, prior_var, provenance, rem_balls, k_excl, m_act, m_eff, hhi = hier.get_lpmo_context_prior(
        101, "death", "Tier 3: High", "bowler_economy"
    )
    
    # 5 matches should be excluded
    assert k_excl == 5, f"Expected 5 excluded matches, got {k_excl}"
    # 20 matches should remain (matches 6..25)
    assert m_act == 20, f"Expected 20 remaining matches, got {m_act}"
    assert provenance == "CELL_LPMO_ROBUST"


def test_02_changing_other_player_performance_in_excluded_match_invariance():
    """
    Priority 5.2: Changing another player's performance in an excluded match
    cannot change evaluated player's prior.
    """
    df1 = make_synthetic_training_df()
    df2 = make_synthetic_training_df()
    
    # In df2, alter Player 102's performance in Match 1 (where Player 101 also played)
    mask = (df2["match_id"] == 1) & (df2["bowler_id"] == 102)
    df2.loc[mask, "ext_bowler_debit_runs"] = 36.0
    df2.loc[mask, "batsman_runs"] = 6
    df2.loc[mask, "is_boundary"] = 1
    
    hier1 = ContextualHierarchyB437()
    hier1.fit(df1)
    
    hier2 = ContextualHierarchyB437()
    hier2.fit(df2)
    
    res1 = hier1.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    res2 = hier2.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    
    # Player 101's prior MUST be perfectly invariant to Player 102's change in Match 1
    assert math.isclose(res1[0], res2[0], rel_tol=1e-12), (
        f"LPMO violation: changing other player in shared match altered prior: {res1[0]} vs {res2[0]}"
    )
    assert math.isclose(res1[1], res2[1], rel_tol=1e-12), (
        f"LPMO violation: changing other player in shared match altered prior variance: {res1[1]} vs {res2[1]}"
    )


def test_03_changing_observations_in_eligible_independent_matches_changes_prior():
    """
    Priority 5.3: Changing observations in eligible independent matches (matches 6..25)
    correctly and sensitively updates player i's prior.
    """
    df1 = make_synthetic_training_df()
    df2 = make_synthetic_training_df()
    
    # In df2, alter Match 10 (an independent match not involving Player 101)
    mask = (df2["match_id"] == 10)
    df2.loc[mask, "ext_bowler_debit_runs"] = 36.0
    
    hier1 = ContextualHierarchyB437()
    hier1.fit(df1)
    
    hier2 = ContextualHierarchyB437()
    hier2.fit(df2)
    
    prior_mean1 = hier1.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")[0]
    prior_mean2 = hier2.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")[0]
    
    assert prior_mean2 > prior_mean1, f"Expected prior_mean2 > prior_mean1, got {prior_mean2} <= {prior_mean1}"


def test_04_shared_match_shock_orthogonality():
    """
    Priority 5.4: Shared match shocks cannot contaminate the prior.
    Injecting a match shock beta_m into Match 2 (where Player 101 played)
    leaves Cov(mu_hat_lpmo, Y_101 | mu_c) = 0.
    """
    df1 = make_synthetic_training_df()
    df2 = make_synthetic_training_df()
    
    # In df2, add an environmental pitch shock (+3 runs per ball to ALL deliveries in Match 2)
    mask_m2 = (df2["match_id"] == 2)
    df2.loc[mask_m2, "ext_bowler_debit_runs"] += 3.0
    df2.loc[mask_m2, "batsman_runs"] += 3
    
    hier1 = ContextualHierarchyB437()
    hier1.fit(df1)
    
    hier2 = ContextualHierarchyB437()
    hier2.fit(df2)
    
    res1 = hier1.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    res2 = hier2.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    
    assert math.isclose(res1[0], res2[0], rel_tol=1e-12), "Shared match shock contaminated player prior!"


def test_05_match_level_cluster_uncertainty_uses_remaining_matches():
    """
    Priority 5.5: Match-level cluster uncertainty uses the remaining match population
    via exact ratio linearization:
    Var(r) = [M / (M - 1)] * sum_{m in M_rem} (y_m - r*x_m)^2 / (sum x_m)^2
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB437()
    hier.fit(df)
    
    prior_mean, prior_var = hier.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")[:2]
    
    # Verify manually on matches 6..25
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
    Priority 5.6: Effective match count M_eff = 1/H where H = sum n_m^2 / (sum n_m)^2.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB437()
    hier.fit(df)
    
    res = hier.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    m_eff = res[6]
    hhi = res[7]
    
    assert math.isclose(hhi, 0.05, rel_tol=1e-6)
    assert math.isclose(m_eff, 20.0, rel_tol=1e-6)


def test_07_sparse_context_fallback_hierarchy():
    """
    Priority 5.7: Verify that sparse phase-tier contexts use valid uncontaminated fallbacks:
    Level 1: Cell LPMO (M >= 15, N >= 30)
    Level 2: Phase LPMO (M >= 15, N >= 30)
    Level 3: League LPMO (M >= 15, N >= 30)
    Level 4: UNRELIABLE_SPARSE_MATCHES
    And that match excision is preserved at EVERY fallback level.
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
    hier = ContextualHierarchyB437()
    hier.fit(df_sparse)
    
    # For Player 201 in Tier 1:
    # Cell has only 10 remaining matches (M < 15) -> falls back to Phase Death!
    prior_mean, prior_var, provenance, rem_balls, k_excl, m_act, m_eff, hhi = hier.get_lpmo_context_prior(
        201, "death", "Tier 1: Low", "bowler_economy"
    )
    assert provenance == "PHASE_LPMO_FALLBACK"
    assert k_excl == 1
    assert m_act == 30  # 10 (Tier 1) + 20 (Tier 2)


def test_08_batter_and_bowler_both_obey_lpmo():
    """
    Priority 5.8: Both batter boundary% and bowler economy prior implementations obey LPMO.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB437()
    hier.fit(df)
    
    # Batter 201 played in matches 1..5
    b_res = hier.get_lpmo_context_prior(201, "death", "Tier 3: High", "batter_boundary")
    assert b_res[4] == 5  # excluded matches
    assert b_res[5] == 20 # remaining matches
    assert 0.0 <= b_res[0] <= 1.0
    assert b_res[1] >= 0.0
    
    # Bowler 101 played in matches 1..5
    bw_res = hier.get_lpmo_context_prior(101, "death", "Tier 3: High", "bowler_economy")
    assert bw_res[4] == 5  # excluded matches
    assert bw_res[5] == 20 # remaining matches
    assert bw_res[0] > 0.0
    assert bw_res[1] >= 0.0


def test_09_joint_posterior_analytical_closed_form():
    """
    Priority 5.9: Joint conjugate Gaussian posterior mean and posterior variance
    match analytical closed form:
    tau2_total = tau2_player + sigma2_mu_lpmo
    lambda = tau2_total / (tau2_total + var_obs)
    mu_post = lambda * y_bar + (1 - lambda) * mu_lpmo
    Var_post = (1 - lambda) * tau2_total
    """
    rec = ContextualPlayerBaselineRecordB437(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_exposure=30,
        context_events=60.0,  # 60 runs / 30 balls = 2.0 rpb = 12.0 rpo
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
        effective_match_count=20.0,
        match_concentration_hhi=0.05
    )
    
    tau2_tot = 2.0 + 0.5  # 2.5
    # For 3 equal matches: H = 1/3
    # var_obs = (6.0 * sigma2_within / n_ctx) + H * sigma2_match
    #         = (6.0 * 16.0 / 30.0) + (1.0 / 3.0 * 1.0) = 3.2 + 0.33333333 = 3.53333333
    var_obs = (6.0 * 16.0 / 30.0) + (1.0 / 3.0) * 1.0
    expected_lambda = tau2_tot / (tau2_tot + var_obs)
    expected_post_mean = expected_lambda * 12.0 + (1.0 - expected_lambda) * 10.0
    expected_post_var = (1.0 - expected_lambda) * tau2_tot
    
    assert math.isclose(rec.shrinkage_weight, expected_lambda, rel_tol=1e-9)
    assert math.isclose(rec.shrunk_baseline, expected_post_mean, rel_tol=1e-9)
    assert math.isclose(rec.posterior_variance, expected_post_var, rel_tol=1e-9)


def test_10_production_oof_predictions_use_lpmo():
    """
    Priority 5.10: Production OOF predictions use LPMO rather than the old LOPO calculation.
    Checks that PlayerPosteriorBaselineEstimator produces records tagged with LPMO provenance.
    """
    df = make_synthetic_training_df()
    hier = ContextualHierarchyB437()
    hier.fit(df)
    
    estimator = PlayerPosteriorBaselineEstimatorB437(
        hierarchy=hier,
        bowler_tau2_player=2.0,
        bowler_sigma2_epsilon=16.0,
        bowler_sigma2_match=1.0,
        batter_tau2_player=0.005,
        batter_sigma2_epsilon=0.15,
        batter_sigma2_match=0.002
    )
    
    rec = estimator.estimate_bowler_economy_posterior(
        player_id=101,
        phase="death",
        tier="Tier 3: High",
        context_legal_balls=60,
        context_debit_runs=120.0,
        context_matches=5
    )
    
    assert "LPMO" in rec.prior_provenance
    assert rec.excluded_match_count == 5
    assert rec.remaining_match_count == 20
    assert rec.effective_match_count > 0.0


def test_11_five_fold_match_isolation_exact():
    """
    Priority 5.11: 5-fold match-grouped CV isolation remains exact (0 shared matches).
    """
    from sklearn.model_selection import GroupKFold
    df = make_synthetic_training_df()
    gkf = GroupKFold(n_splits=5)
    
    for fold, (tr_idx, val_idx) in enumerate(gkf.split(df, groups=df["match_id"]), 1):
        tr_m = set(df.iloc[tr_idx]["match_id"].unique())
        val_m = set(df.iloc[val_idx]["match_id"].unique())
        shared = tr_m.intersection(val_m)
        assert len(shared) == 0, f"Fold {fold} had shared matches: {shared}"


def test_12_predictive_variance_coherence_no_double_counting():
    """
    Priority 5.12: Predictive variance does not double-count uncertainty.
    Var(Y_new | Y) = Var(theta | Y) + sigma2_match + (sigma2_eps * 6.0 / N_new).
    """
    rec = ContextualPlayerBaselineRecordB437(
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
        min_context_exposure=30
    )
    
    post_var = rec.posterior_variance
    # For a spell with N_new = 12 legal balls in 1 new match (M_new = 1)
    # v_match = 1.0
    # v_within = 16.0 * 6.0 / 12.0 = 8.0
    pred_var = rec.get_predictive_variance(n_eval=12)
    expected_pred_var = post_var + 1.0 + (16.0 * 6.0 / 12.0)
    
    assert math.isclose(pred_var, expected_pred_var, rel_tol=1e-6)
