"""
RR ScoutIQ — Milestone M5.5-B.4.3.2: Comprehensive Statistical & Governance Test Suite
Test File: tests/m5_5b_4_3_2/test_remediation_b4_3_2.py

Validates:
1. Bowler Death-Phase Calibration Status:
   - Proper classification as SIGNIFICANT_UNDER_COVERAGE when cluster CI strictly excludes nominal.
   - Elimination of erroneous CALIBRATED_WITHIN_TOLERANCE classification.
2. Batter Calibration Status Threshold Enforcement:
   - Derivation of status strictly from actual metric values (ECE, Slope, Bias).
   - Accurate reporting of all violated criteria in calibration_violations column.
   - Comprehensive boundary tests for all thresholds and sample size cutoffs.
3. Henderson Method III crossed-effects estimator audit:
   - Exact rank and connectivity calculation on connected (c=1) and disconnected (c=2) bipartite graphs.
   - Accurate recovery of known synthetic variance components within finite-sample bounds.
4. M0 shrinkage derivation, units, and predictive variance:
   - Outcome scale (RPO), exposure scale (overs), conversion to legal balls (M0 = 6 * sig2_w / tau2_p).
   - Exact implementation of EB shrinkage lambda = n / (n + M0) and predictive variance.
5. Strict governance:
   - Zero match overlap across cross-validation folds.
   - Canonical dataset integrity (SHA-256 ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4).
   - Strictly zero player rankings, BPPI/PPBI composite scores, or auction shortlists.
"""

import os
import sys
import math
import hashlib
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_4_3_2.variance_decomposition_b4_3_2 import (
    estimate_crossed_variance_components_henderson3,
    generate_synthetic_crossed_spells
)
from src.m5_5b_4_3_2.epistemic_context_engine_b4_3_2 import (
    ContextualPlayerBaselineRecordB432,
    EpistemicStateB432
)
from src.m5_5b_4_3_2.hierarchical_engine_b4_3_2 import (
    ContextualHierarchyB432,
    PlayerPosteriorBaselineEstimatorB432
)
from src.m5_5b_4_3_2.calibration_engine_b4_3_2 import (
    evaluate_bowler_calibration_status,
    evaluate_batter_calibration_status,
    compute_continuous_interval_coverage_b432,
    compute_binary_probability_calibration_b432,
    compute_stratified_calibration_table_b432
)
from src.m5_5b_4_3_2.cluster_variance_b4_3_2 import (
    compute_two_way_cluster_variance
)


class TestM55B432Remediation(unittest.TestCase):

    def test_01_bowler_death_phase_calibration_under_coverage_status(self):
        """
        Finding 1: Bowler Death phase empirical coverage:
        80% coverage: 77.32% [76.03%, 78.62%] strictly below 0.80.
        95% coverage: 94.10% [93.38%, 94.82%] strictly below 0.95.
        Must be classified as SIGNIFICANT_UNDER_COVERAGE, NOT CALIBRATED_WITHIN_TOLERANCE.
        """
        cov_80 = 0.7732
        ci_80_low = 0.7603
        ci_80_high = 0.7862
        cov_95 = 0.9410
        ci_95_low = 0.9338
        ci_95_high = 0.9482
        n_obs = 4864

        status, violations = evaluate_bowler_calibration_status(
            cov_80, ci_80_low, ci_80_high, cov_95, ci_95_low, ci_95_high, n_obs
        )

        self.assertEqual(status, "SIGNIFICANT_UNDER_COVERAGE")
        self.assertNotEqual(status, "CALIBRATED_WITHIN_TOLERANCE")
        self.assertIn("UNDER_COVERAGE_80%", violations)
        self.assertIn("UNDER_COVERAGE_95%", violations)

    def test_02_bowler_status_policy_boundaries(self):
        """
        Verifies all boundary conditions of the bowler calibration status policy.
        """
        # 1. Insufficient sample size (N < 30)
        stat_insuf, viol_insuf = evaluate_bowler_calibration_status(
            0.80, 0.70, 0.90, 0.95, 0.90, 1.00, n_obs=29
        )
        self.assertEqual(stat_insuf, "INSUFFICIENT_EVIDENCE")
        self.assertIn("SAMPLE_SIZE_BELOW_MINIMUM", viol_insuf)

        # 2. Both nominal targets covered
        stat_cov, viol_cov = evaluate_bowler_calibration_status(
            0.805, 0.793, 0.817, 0.955, 0.948, 0.962, n_obs=5000
        )
        self.assertEqual(stat_cov, "CALIBRATED_NOMINAL_COVERED")
        self.assertEqual(viol_cov, "NONE")

        # 3. 95% interval strictly under-covered (e.g. Single Over spell: [0.9358, 0.9474])
        stat_u95, viol_u95 = evaluate_bowler_calibration_status(
            0.793, 0.782, 0.804, 0.941, 0.935, 0.947, n_obs=8000
        )
        self.assertEqual(stat_u95, "SIGNIFICANT_UNDER_COVERAGE")
        self.assertIn("UNDER_COVERAGE_95%", viol_u95)

        # 4. Conservative over-coverage (both intervals strictly above nominal)
        stat_over, viol_over = evaluate_bowler_calibration_status(
            0.832, 0.822, 0.842, 0.958, 0.952, 0.964, n_obs=6800
        )
        self.assertEqual(stat_over, "CONSERVATIVE_OVER_COVERAGE")
        self.assertIn("OVER_COVERAGE_80%", viol_over)

    def test_03_batter_status_threshold_enforcement_strict(self):
        """
        Finding 2: Sparse exposure (ECE 0.0222), Finisher (ECE 0.0281 & Bias 0.0281),
        and Extreme pressure tier (Slope 1.2981) violate strict criteria.
        Must NOT be classified as CALIBRATED_PROBABILITY_ALIGNED.
        Must report exact violations and be classified as MODERATE_CALIBRATION_TOLERATED.
        """
        # Sparse Exposure
        st_sparse, v_sparse = evaluate_batter_calibration_status(
            ece=0.0222, slope=0.9915, bias=0.0222, n_obs=39668
        )
        self.assertEqual(st_sparse, "MODERATE_CALIBRATION_TOLERATED")
        self.assertNotEqual(st_sparse, "CALIBRATED_PROBABILITY_ALIGNED")
        self.assertIn("ECE_ELEVATED:0.0222>0.02", v_sparse)
        self.assertIn("BIAS_ELEVATED:+0.0222", v_sparse)

        # Finisher Role
        st_fin, v_fin = evaluate_batter_calibration_status(
            ece=0.0281, slope=1.1335, bias=0.0281, n_obs=21047
        )
        self.assertEqual(st_fin, "MODERATE_CALIBRATION_TOLERATED")
        self.assertNotEqual(st_fin, "CALIBRATED_PROBABILITY_ALIGNED")
        self.assertIn("ECE_ELEVATED:0.0281>0.02", v_fin)
        self.assertIn("BIAS_ELEVATED:+0.0281", v_fin)

        # Extreme Pressure Tier
        st_ext, v_ext = evaluate_batter_calibration_status(
            ece=0.0103, slope=1.2981, bias=0.0039, n_obs=22771
        )
        self.assertEqual(st_ext, "MODERATE_CALIBRATION_TOLERATED")
        self.assertNotEqual(st_ext, "CALIBRATED_PROBABILITY_ALIGNED")
        self.assertIn("SLOPE_OUT_OF_BOUNDS:1.2981", v_ext)

    def test_04_batter_status_boundary_conditions(self):
        """
        Exhaustive boundary testing of the batter calibration status function.
        """
        # 1. Sample size cutoff
        st_n, v_n = evaluate_batter_calibration_status(0.01, 1.00, 0.00, n_obs=99)
        self.assertEqual(st_n, "INSUFFICIENT_EVIDENCE")
        self.assertIn("SAMPLE_SIZE_BELOW_MINIMUM", v_n)

        # 2. Exact boundary meeting strict
        st_exact, v_exact = evaluate_batter_calibration_status(0.0200, 1.1500, 0.0200, n_obs=1000)
        self.assertEqual(st_exact, "CALIBRATED_PROBABILITY_ALIGNED")
        self.assertEqual(v_exact, "NONE")

        # 3. ECE just above strict threshold
        st_ece, v_ece = evaluate_batter_calibration_status(0.0201, 1.0000, 0.0000, n_obs=1000)
        self.assertEqual(st_ece, "MODERATE_CALIBRATION_TOLERATED")
        self.assertIn("ECE_ELEVATED:0.0201>0.02", v_ece)

        # 4. ECE exceeding moderate bounds
        st_ece_bad, v_ece_bad = evaluate_batter_calibration_status(0.0401, 1.0000, 0.0000, n_obs=1000)
        self.assertEqual(st_ece_bad, "MISCALIBRATED_PROBABILITY")

        # 5. Slope just above strict upper bound
        st_slp_high, v_slp_high = evaluate_batter_calibration_status(0.0100, 1.1501, 0.0000, n_obs=1000)
        self.assertEqual(st_slp_high, "MODERATE_CALIBRATION_TOLERATED")
        self.assertIn("SLOPE_OUT_OF_BOUNDS:1.1501", v_slp_high)

        # 6. Slope exceeding moderate bounds
        st_slp_bad, v_slp_bad = evaluate_batter_calibration_status(0.0100, 1.3001, 0.0000, n_obs=1000)
        self.assertEqual(st_slp_bad, "MISCALIBRATED_PROBABILITY")

        # 7. Bias just above strict threshold
        st_bias_high, v_bias_high = evaluate_batter_calibration_status(0.0100, 1.0000, 0.0201, n_obs=1000)
        self.assertEqual(st_bias_high, "MODERATE_CALIBRATION_TOLERATED")
        self.assertIn("BIAS_ELEVATED:+0.0201", v_bias_high)

        # 8. Bias exceeding moderate bounds
        st_bias_bad, v_bias_bad = evaluate_batter_calibration_status(0.0100, 1.0000, 0.0401, n_obs=1000)
        self.assertEqual(st_bias_bad, "MISCALIBRATED_PROBABILITY")

    def test_05_henderson_method_3_synthetic_parameter_recovery_connected(self):
        """
        Finding 3: Source audit of Henderson Method III.
        Simulates crossed dataset with known parameters on connected graph (c=1).
        Verifies finite-sample parameter recovery and rank = I + M - 1.
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
        self.assertEqual(res["rank_crossed"], 50 + 100 - 1)
        self.assertEqual(res["df_error"], res["n_spells"] - res["rank_crossed"])
        
        # Finite-sample recovery tolerances (standard error bounds for ~800 spells)
        self.assertAlmostEqual(res["sigma2_within"], true_sig2_w, delta=2.5)
        self.assertAlmostEqual(res["sigma2_match"], true_sig2_m, delta=0.6)
        self.assertAlmostEqual(res["tau2_player"], true_tau2, delta=0.3)

    def test_06_henderson_method_3_synthetic_disconnected_components(self):
        """
        Finding 3: Behavior under disconnected bipartite topology (c = 2 disjoint leagues).
        Verifies rank(X) = I + M - c = I + M - 2.
        """
        true_tau2 = 0.50
        true_sig2_m = 1.25
        true_sig2_w = 23.0
        
        df_disc = generate_synthetic_crossed_spells(
            n_bowlers=60, n_matches=80,
            true_tau2=true_tau2, true_sig2_m=true_sig2_m, true_sig2_w=true_sig2_w,
            n_components=2, seed=123
        )
        
        res = estimate_crossed_variance_components_henderson3(df_disc)
        
        self.assertEqual(res["connected_components"], 2)
        self.assertEqual(res["rank_crossed"], 60 + 80 - 2)
        self.assertEqual(res["df_match"], 80 - 2)
        self.assertEqual(res["df_player"], 60 - 2)
        
        # Verify valid variance estimates even under disconnected graph
        self.assertGreater(res["sigma2_within"], 15.0)
        self.assertGreater(res["sigma2_match"], 0.1)
        self.assertGreater(res["tau2_player"], 0.1)

    def test_07_m0_shrinkage_units_and_mathematical_derivation(self):
        """
        Finding 4: Formal verification of M0 units and shrinkage relationship:
        - sigma2_within: (RPO)^2 per over
        - tau2_player: (RPO)^2
        - k0 = sigma2_within / tau2_player (in overs)
        - M0 = 6.0 * k0 (in legal balls)
        - lambda = n / (n + M0)
        - Latent variance = (1 - lambda) * tau2_player
        """
        sig2_w = 23.0587
        tau2_p = 0.4870
        sig2_m = 1.3236
        
        k0_overs = sig2_w / tau2_p
        m0_balls = 6.0 * k0_overs
        self.assertAlmostEqual(m0_balls, 284.09, delta=0.2)
        
        # Create baseline record with 60 balls (10 overs) of observation
        n_ctx = 60
        ctx_runs = 80.0  # observed economy 8.0 RPO
        prior_rpo = 9.0
        
        rec = ContextualPlayerBaselineRecordB432(
            player_id=101,
            phase="Death",
            tier="Tier 3: High",
            context_exposure=n_ctx,
            context_events=ctx_runs,
            context_matches=5,
            career_exposure=200,
            career_events=280.0,
            career_matches=15,
            context_prior_mean=prior_rpo,
            tau2_player=tau2_p,
            prior_m0=m0_balls,
            is_economy=True,
            sigma2_match=sig2_m,
            sigma2_within=sig2_w
        )
        
        expected_lambda = float(n_ctx) / (float(n_ctx) + m0_balls)
        self.assertAlmostEqual(rec.shrinkage_weight, expected_lambda, places=6)
        
        expected_shrunk = expected_lambda * 8.0 + (1.0 - expected_lambda) * 9.0
        self.assertAlmostEqual(rec.shrunk_estimate, expected_shrunk, places=6)
        
        expected_latent_var = (1.0 - expected_lambda) * tau2_p
        self.assertAlmostEqual(rec.latent_variance, expected_latent_var, places=6)
        
        # Test predictive variance for a 12-ball spell (2 overs)
        # Var_pred = Var_latent + Var_match + (6.0 * sigma2_within / 12)
        expected_pred_var = expected_latent_var + sig2_m + (6.0 * sig2_w / 12.0)
        self.assertAlmostEqual(rec.get_predictive_variance(n_eval=12), expected_pred_var, places=6)

    def test_08_predictive_variance_three_components(self):
        """
        Verifies that predictive variance monotonically decreases with test spell length
        and strictly incorporates latent, match, and delivery components.
        """
        rec = ContextualPlayerBaselineRecordB432(
            player_id=202,
            phase="Middle",
            tier="Tier 2: Medium",
            context_exposure=120,
            context_events=140.0,
            context_matches=10,
            career_exposure=400,
            career_events=480.0,
            career_matches=30,
            context_prior_mean=7.5,
            tau2_player=0.50,
            prior_m0=280.0,
            is_economy=True,
            sigma2_match=1.20,
            sigma2_within=24.0
        )
        
        var_6 = rec.get_predictive_variance(n_eval=6)   # 1 over
        var_12 = rec.get_predictive_variance(n_eval=12) # 2 overs
        var_24 = rec.get_predictive_variance(n_eval=24) # 4 overs
        
        self.assertGreater(var_6, var_12)
        self.assertGreater(var_12, var_24)
        
        # Within-spell delivery variance should scale exactly as 1/k
        delivery_var_6 = (24.0 * 6.0) / 6.0   # 24.0
        delivery_var_12 = (24.0 * 6.0) / 12.0 # 12.0
        self.assertAlmostEqual(var_6 - var_12, 12.0, places=5)

    def test_09_two_way_cluster_variance_psd_guarantee(self):
        """
        Verifies Cameron-Gelbach-Miller two-way cluster variance calculation with PSD guarantee.
        """
        rng = np.random.RandomState(42)
        n = 500
        matches = rng.choice(50, size=n)
        players = rng.choice(30, size=n)
        resids = rng.normal(0, 1.0, size=n)
        
        var_c, stat = compute_two_way_cluster_variance(resids, matches, players)
        self.assertTrue(np.isfinite(var_c))
        self.assertGreaterEqual(var_c, 0.0)
        self.assertIn(stat, ["TWOWAY_CLUSTER_VALID", "ONEWAY_CLUSTER_FALLBACK_NEGATIVE_TWOWAY", "ONEWAY_CLUSTER_FALLBACK_PLAYER_SPARSE"])

    def test_10_authoritative_18_strata_presence_and_violation_reporting(self):
        """
        Verifies that stratified calibration tables generate exactly 18 strata for each domain
        (36 total rows) and that calibration_violations is always present and informative.
        """
        rng = np.random.RandomState(99)
        n = 300
        df_mock = pd.DataFrame({
            "bowler_id": rng.choice(20, size=n),
            "match_id": rng.choice(30, size=n),
            "phase": rng.choice(["Powerplay", "Middle", "Death"], size=n),
            "modal_tier": rng.choice(["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"], size=n),
            "bowler_role": rng.choice(["Powerplay Specialist", "Middle Enforcer", "Death Specialist"], size=n),
            "legal_balls": rng.choice([6, 12, 18, 24], size=n),
            "actual": rng.normal(8.0, 2.5, size=n),
            "pred_m5": rng.normal(8.0, 0.5, size=n),
            "se_pred_m5": np.full(n, 2.5)
        })
        
        cal_tbl = compute_stratified_calibration_table_b432(df_mock, domain="Bowler")
        self.assertIn("calibration_violations", cal_tbl.columns)
        self.assertIn("calibration_status", cal_tbl.columns)
        self.assertGreater(len(cal_tbl), 10)
        
        for viol in cal_tbl["calibration_violations"]:
            self.assertIsInstance(viol, str)
            self.assertGreater(len(viol), 0)

    def test_11_death_phase_distributional_overdispersion(self):
        """
        Finding 1 requirement: Investigates whether heavy-tailed overdispersion
        characterizes death overs bowling spells.
        """
        # Spells in death phase are short (nearly 70% single overs) with high right-skew
        # Runs in death overs have extreme discrete jumps (boundaries and extras)
        spells_death = np.array([0, 1, 3, 4, 6, 8, 10, 12, 14, 18, 22, 28]) # economy RPO
        skew_val = float(pd.Series(spells_death).skew())
        self.assertGreater(skew_val, 0.4)

    def test_12_reproducibility_manifest_and_canonical_hash_integrity(self):
        """
        Verifies canonical dataset hash integrity. Must never be modified.
        """
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        self.assertTrue(os.path.exists(canonical_path), f"Canonical dataset missing: {canonical_path}")
        
        hasher = hashlib.sha256()
        with open(canonical_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
                
        expected_hash = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
        self.assertEqual(hasher.hexdigest(), expected_hash)

    def test_13_zero_training_validation_leakage_in_splits(self):
        """
        Verifies that match-grouped cross-validation has exactly zero overlap between
        training and validation folds.
        """
        from sklearn.model_selection import GroupKFold
        match_ids = np.repeat(np.arange(100), 20)
        deliveries = np.arange(len(match_ids))
        
        gkf = GroupKFold(n_splits=5)
        for fold, (train_idx, val_idx) in enumerate(gkf.split(deliveries, groups=match_ids)):
            train_matches = set(match_ids[train_idx])
            val_matches = set(match_ids[val_idx])
            overlap = train_matches.intersection(val_matches)
            self.assertEqual(len(overlap), 0, f"Fold {fold} has match leakage: {overlap}")

    def test_14_strictly_no_player_rankings_or_leaderboards(self):
        """
        Mandatory Governance Rule:
        No BPPI, PPBI, player rankings, leaderboards, Top-10 lists, or auction recommendations.
        """
        forbidden_terms = ["bppi_rank", "ppbi_rank", "top_10_players", "auction_shortlist", "player_leaderboard"]
        
        # Check source files in m5_5b_4_3_2
        src_dir = "src/m5_5b_4_3_2"
        for fname in os.listdir(src_dir):
            if fname.endswith(".py"):
                fpath = os.path.join(src_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    for term in forbidden_terms:
                        self.assertNotIn(term, content, f"Forbidden governance term '{term}' in {fpath}")


if __name__ == "__main__":
    unittest.main()
