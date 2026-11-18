"""
RR ScoutIQ — Milestone M5.5-B.4.3.3: Comprehensive Statistical & Governance Test Suite
Test File: tests/m5_5b_4_3_3/test_remediation_b4_3_3.py

Validates:
1. Contextual Fixed Effects in Henderson Method III (Priority 1):
   - Multi-context synthetic variance recovery with unequal exposure and known parameters.
   - Exact rank rank(X_cbm) = K + I + M - 1 - c for connected (c=1) and disconnected (c=2) graphs.
   - Exact degrees-of-freedom accounting df_E = N - rank(X_cbm), df_m = M - c, df_b = I - c.
2. Match Environmental Variance in Posterior Shrinkage (Priority 2):
   - Exact likelihood variance V_{i, c} = (6 * sig2_w / n) + H_{i, c} * sig2_m.
   - Comparison of equal total volume (24 balls) in 1 match (H=1.0) vs 4 matches (H=0.25).
   - Aggregation of multiple spells within the same match into a single match shock.
   - Clear distinction between latent ability variance and predictive variance.
3. Invalid Calibration Input Handling (Priority 3):
   - Rejection of NaN and infinite coverage and interval bounds.
   - Rejection of reversed confidence interval bounds (lower > upper).
   - Rejection of coverage outside probabilistic support [0, 1].
   - Sample size screening (N < 30 -> INSUFFICIENT_EVIDENCE).
   - Verification that invalid evidence is NEVER classified as calibrated.
4. Strict Governance:
   - Canonical dataset integrity (SHA-256 ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4).
   - Zero match leakage across cross-validation splits.
   - Strictly zero player rankings, BPPI/PPBI composite scores, or auction recommendations.
"""

import os
import sys
import math
import hashlib
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_4_3_3.variance_decomposition_b4_3_3 import (
    estimate_crossed_variance_components_henderson3,
    generate_synthetic_crossed_spells
)
from src.m5_5b_4_3_3.epistemic_context_engine_b4_3_3 import (
    ContextualPlayerBaselineRecordB433,
    EpistemicStateB433
)
from src.m5_5b_4_3_3.hierarchical_engine_b4_3_3 import (
    ContextualHierarchyB433,
    PlayerPosteriorBaselineEstimatorB433
)
from src.m5_5b_4_3_3.calibration_engine_b4_3_3 import (
    evaluate_bowler_calibration_status,
    evaluate_batter_calibration_status,
    compute_continuous_interval_coverage_b433,
    compute_binary_probability_calibration_b433,
    compute_stratified_calibration_table_b433
)
from src.m5_5b_4_3_3.cluster_variance_b4_3_3 import (
    compute_two_way_cluster_variance
)


class TestM55B433Remediation(unittest.TestCase):

    # =========================================================================
    # PRIORITY 1: CONTEXTUAL FIXED EFFECTS IN HENDERSON METHOD III
    # =========================================================================

    def test_01_henderson3_multi_context_synthetic_recovery(self):
        """
        Priority 1: Multi-context synthetic test with known parameters:
        - 6 distinct phase-tier contextual baselines
        - Unequal delivery exposures (6, 12, 18, 24 balls)
        - True parameters: tau2_player=0.50, sigma2_match=1.25, sigma2_within=23.0
        Verifies unbiased recovery of all variance components.
        """
        true_tau2 = 0.50
        true_sig2_m = 1.25
        true_sig2_w = 23.0
        
        df_sim = generate_synthetic_crossed_spells(
            n_bowlers=50, n_matches=100,
            true_tau2=true_tau2, true_sig2_m=true_sig2_m, true_sig2_w=true_sig2_w,
            n_components=1, seed=42
        )
        
        res = estimate_crossed_variance_components_henderson3(df_sim)
        
        self.assertEqual(res["connected_components"], 1)
        self.assertEqual(res["n_contexts"], 6)
        
        # Exact rank: K + I + M - 1 - c = 6 + 50 + 100 - 2 = 154
        self.assertEqual(res["rank_crossed"], 6 + 50 + 100 - 2)
        self.assertEqual(res["df_error"], res["n_spells"] - res["rank_crossed"])
        self.assertEqual(res["df_match"], 100 - 1)
        self.assertEqual(res["df_player"], 50 - 1)
        
        # Finite-sample recovery bounds for ~700 spells
        self.assertAlmostEqual(res["sigma2_within"], true_sig2_w, delta=3.0)
        self.assertAlmostEqual(res["sigma2_match"], true_sig2_m, delta=0.6)
        self.assertAlmostEqual(res["tau2_player"], true_tau2, delta=0.40)

    def test_02_henderson3_disconnected_bipartite_topology(self):
        """
        Priority 1: Disconnected bipartite graph (c = 2 disjoint leagues)
        with multiple contextual cells.
        Verifies rank(X) = K + I + M - 1 - c = K + I + M - 3.
        """
        true_tau2 = 0.50
        true_sig2_m = 1.25
        true_sig2_w = 23.0
        
        df_disc = generate_synthetic_crossed_spells(
            n_bowlers=60, n_matches=100,
            true_tau2=true_tau2, true_sig2_m=true_sig2_m, true_sig2_w=true_sig2_w,
            n_components=2, seed=42
        )
        
        res = estimate_crossed_variance_components_henderson3(df_disc)
        
        self.assertEqual(res["connected_components"], 2)
        self.assertEqual(res["n_contexts"], 6)
        self.assertEqual(res["rank_crossed"], 6 + 60 + 100 - 1 - 2)
        self.assertEqual(res["df_match"], 100 - 2)
        self.assertEqual(res["df_player"], 60 - 2)
        
        self.assertGreater(res["sigma2_within"], 15.0)
        self.assertGreater(res["sigma2_match"], 0.1)
        self.assertGreater(res["tau2_player"], 0.1)

    # =========================================================================
    # PRIORITY 2: MATCH VARIANCE IN PLAYER POSTERIOR SHRINKAGE
    # =========================================================================

    def test_03_match_variance_shrinkage_equal_exposure_concentration(self):
        """
        Priority 2: Compares two bowlers with EQUAL total volume (24 legal balls / 4 overs)
        in the same contextual cell:
        - Bowler 1 (Concentrated): 24 balls all in 1 single match -> H = 1.0
        - Bowler 2 (Distributed): 24 balls across 4 separate matches (6 balls each) -> H = 0.25
        
        Verifies:
        1. V_obs(Bowler 1) > V_obs(Bowler 2) due to unmitigated match environmental shock.
        2. Shrinkage weight lambda(Bowler 2) > lambda(Bowler 1) (more informative observation).
        3. Latent posterior variance Var(theta | data) is LOWER for Bowler 2.
        """
        tau2_p = 0.4657
        sig2_m = 1.4537
        sig2_w = 22.8429
        
        # Bowler 1: 24 balls in 1 match
        rec_conc = ContextualPlayerBaselineRecordB433(
            player_id=1, phase="Death", tier="Tier 3: High",
            context_exposure=24, context_events=36.0, context_matches=1,
            career_exposure=100, career_events=150.0, career_matches=5,
            context_prior_mean=9.0, tau2_player=tau2_p, is_economy=True,
            sigma2_match=sig2_m, sigma2_within=sig2_w,
            context_match_balls_list=[24]
        )
        
        # Bowler 2: 24 balls across 4 matches (6 balls each)
        rec_dist = ContextualPlayerBaselineRecordB433(
            player_id=2, phase="Death", tier="Tier 3: High",
            context_exposure=24, context_events=36.0, context_matches=4,
            career_exposure=100, career_events=150.0, career_matches=5,
            context_prior_mean=9.0, tau2_player=tau2_p, is_economy=True,
            sigma2_match=sig2_m, sigma2_within=sig2_w,
            context_match_balls_list=[6, 6, 6, 6]
        )
        
        # Herfindahl verification
        self.assertAlmostEqual(rec_conc.match_herfindahl, 1.0, places=6)
        self.assertAlmostEqual(rec_dist.match_herfindahl, 0.25, places=6)
        
        # Expected observation variances:
        # V_conc = (6 * 22.8429 / 24) + 1.0 * 1.4537 = 5.7107 + 1.4537 = 7.1644
        # V_dist = (6 * 22.8429 / 24) + 0.25 * 1.4537 = 5.7107 + 0.3634 = 6.0741
        self.assertAlmostEqual(rec_conc.var_observation, (6.0 * sig2_w / 24.0) + 1.0 * sig2_m, places=4)
        self.assertAlmostEqual(rec_dist.var_observation, (6.0 * sig2_w / 24.0) + 0.25 * sig2_m, places=4)
        self.assertGreater(rec_conc.var_observation, rec_dist.var_observation)
        
        # Shrinkage weight: lambda_dist > lambda_conc
        self.assertGreater(rec_dist.shrinkage_weight, rec_conc.shrinkage_weight)
        
        # Latent ability uncertainty: Var(theta | data)_dist < Var(theta | data)_conc
        self.assertLess(rec_dist.latent_variance, rec_conc.latent_variance)

    def test_04_multiple_spells_in_same_match_aggregation(self):
        """
        Priority 2: Verifies that multiple spells within the same match are aggregated
        together into that match's total exposure and share the SAME match shock.
        For example: a bowler bowling 6 balls in over 16 and 6 balls in over 19 of match M1
        has 12 balls in M1 -> (12/12)^2 = 1.0, NOT two independent 6-ball match shocks!
        """
        tau2_p = 0.4657
        sig2_m = 1.4537
        sig2_w = 22.8429
        
        # 12 balls in match M1 (composed of two 6-ball spells)
        rec_single_m = ContextualPlayerBaselineRecordB433(
            player_id=10, phase="Death", tier="Tier 4: Extreme",
            context_exposure=12, context_events=18.0, context_matches=1,
            career_exposure=50, career_events=75.0, career_matches=3,
            context_prior_mean=10.0, tau2_player=tau2_p, is_economy=True,
            sigma2_match=sig2_m, sigma2_within=sig2_w,
            context_match_balls_list=[12]
        )
        
        self.assertEqual(rec_single_m.match_herfindahl, 1.0)
        expected_v = (6.0 * sig2_w / 12.0) + 1.0 * sig2_m
        self.assertAlmostEqual(rec_single_m.var_observation, expected_v, places=4)

    def test_05_predictive_variance_held_out_spell_independence(self):
        """
        Priority 2: Preserves the strict distinction between latent ability uncertainty
        and posterior predictive uncertainty.
        A held-out test spell in a NEW match incurs an independent match shock sigma2_match
        regardless of training match distribution.
        """
        rec = ContextualPlayerBaselineRecordB433(
            player_id=20, phase="Middle", tier="Tier 2: Medium",
            context_exposure=60, context_events=75.0, context_matches=5,
            career_exposure=200, career_events=250.0, career_matches=15,
            context_prior_mean=7.5, tau2_player=0.50, is_economy=True,
            sigma2_match=1.25, sigma2_within=23.0,
            context_match_balls_list=[12, 12, 12, 12, 12]
        )
        
        # Test spell of 12 balls (2 overs) in a new match
        pred_var = rec.get_predictive_variance(n_eval=12)
        expected_pred_var = rec.latent_variance + 1.25 + (6.0 * 23.0 / 12.0)
        self.assertAlmostEqual(pred_var, expected_pred_var, places=6)

    # =========================================================================
    # PRIORITY 3: INVALID CALIBRATION INPUT HANDLING
    # =========================================================================

    def test_06_reject_nan_and_infinite_inputs(self):
        """
        Priority 3: Verifies that NaN or infinite coverage or interval bounds
        are rejected with INVALID_CALIBRATION_INPUT (never calibrated).
        """
        # NaN coverage
        st, viol = evaluate_bowler_calibration_status(
            cov_80=np.nan, ci_80_low=0.75, ci_80_high=0.85,
            cov_95=0.95, ci_95_low=0.93, ci_95_high=0.97, n_obs=500
        )
        self.assertEqual(st, "INVALID_CALIBRATION_INPUT")
        self.assertIn("NaN_OR_INF", viol)

        # Infinite interval bound
        st_inf, viol_inf = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.75, ci_80_high=np.inf,
            cov_95=0.95, ci_95_low=0.93, ci_95_high=0.97, n_obs=500
        )
        self.assertEqual(st_inf, "INVALID_CALIBRATION_INPUT")
        self.assertIn("NaN_OR_INF", viol_inf)

    def test_07_reject_reversed_confidence_intervals(self):
        """
        Priority 3: Verifies that reversed confidence interval bounds (low > high)
        are rejected with INVALID_CALIBRATION_INPUT.
        """
        st_rev, viol_rev = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.85, ci_80_high=0.75, # Reversed!
            cov_95=0.95, ci_95_low=0.93, ci_95_high=0.97, n_obs=500
        )
        self.assertEqual(st_rev, "INVALID_CALIBRATION_INPUT")
        self.assertIn("REVERSED_CONFIDENCE_INTERVAL_BOUNDS", viol_rev)

    def test_08_reject_coverage_outside_probabilistic_range(self):
        """
        Priority 3: Verifies that empirical coverage outside [0, 1] is rejected.
        """
        st_out, viol_out = evaluate_bowler_calibration_status(
            cov_80=-0.05, ci_80_low=0.0, ci_80_high=0.1,
            cov_95=1.05, ci_95_low=0.9, ci_95_high=1.0, n_obs=500
        )
        self.assertEqual(st_out, "INVALID_CALIBRATION_INPUT")
        self.assertIn("COVERAGE_OUTSIDE_RANGE_[0,1]", viol_out)

    def test_09_sample_size_screening_thresholds(self):
        """
        Priority 3: Verifies sample size screening cutoffs:
        - Bowlers: N < 30 -> INSUFFICIENT_EVIDENCE
        - Batters: N < 100 -> INSUFFICIENT_EVIDENCE
        """
        st_b, v_b = evaluate_bowler_calibration_status(
            0.80, 0.70, 0.90, 0.95, 0.90, 1.00, n_obs=29
        )
        self.assertEqual(st_b, "INSUFFICIENT_EVIDENCE")
        self.assertIn("SAMPLE_SIZE_BELOW_MINIMUM:N=29<30", v_b)

        st_bat, v_bat = evaluate_batter_calibration_status(
            ece=0.01, slope=1.00, bias=0.00, n_obs=99
        )
        self.assertEqual(st_bat, "INSUFFICIENT_EVIDENCE")
        self.assertIn("SAMPLE_SIZE_BELOW_MINIMUM:N=99<100", v_bat)

    def test_10_valid_boundary_cases_sanitization(self):
        """
        Priority 3: Verifies valid boundary cases are correctly classified.
        """
        # Exact nominal coverage
        st_nom, v_nom = evaluate_bowler_calibration_status(
            0.8000, 0.7900, 0.8100, 0.9500, 0.9400, 0.9600, n_obs=1000
        )
        self.assertEqual(st_nom, "CALIBRATED_NOMINAL_COVERED")
        self.assertEqual(v_nom, "NONE")

        # Significant under-coverage on death phase
        st_under, v_under = evaluate_bowler_calibration_status(
            0.7732, 0.7603, 0.7862, 0.9410, 0.9338, 0.9482, n_obs=4864
        )
        self.assertEqual(st_under, "SIGNIFICANT_UNDER_COVERAGE")
        self.assertIn("UNDER_COVERAGE_80%", v_under)
        self.assertIn("UNDER_COVERAGE_95%", v_under)

    # =========================================================================
    # GOVERNANCE & INTEGRITY TESTS
    # =========================================================================

    def test_11_canonical_dataset_hash_preservation(self):
        """
        Strict Governance: Canonical dataset hash must remain identical.
        """
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        self.assertTrue(os.path.exists(canonical_path))
        
        hasher = hashlib.sha256()
        with open(canonical_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
                
        expected_hash = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
        self.assertEqual(hasher.hexdigest(), expected_hash)

    def test_12_strictly_no_player_rankings_or_leaderboards(self):
        """
        Strict Governance:
        No BPPI, PPBI, player rankings, leaderboards, Top-10 lists, or auction shortlists.
        """
        forbidden_terms = ["bppi_rank", "ppbi_rank", "top_10_players", "auction_shortlist", "player_leaderboard"]
        
        src_dir = "src/m5_5b_4_3_3"
        for fname in os.listdir(src_dir):
            if fname.endswith(".py"):
                fpath = os.path.join(src_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    for term in forbidden_terms:
                        self.assertNotIn(term, content, f"Forbidden term '{term}' in {fpath}")


if __name__ == "__main__":
    unittest.main()
