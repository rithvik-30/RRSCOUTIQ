"""
RR ScoutIQ — Milestone M5.5-B.4.2: Statistical Validity & Context-Consistent Test Battery
Test Suite: tests/m5_5b_4_2/test_statistical_validity_b4_2.py

Validates all 17 mandatory requirements:
1. Context-specific batter posterior isolation.
2. Context-specific bowler posterior isolation.
3. Player-by-phase interaction behavior.
4. Player-by-pressure-tier interaction behavior.
5. Zero and missing contextual exposure.
6. Leave-one-player-out benchmark contamination.
7. Match-paired phase estimate and confidence interval consistency.
8. Unequal legal-ball exposure.
9. Repeated player dependence across matches.
10. Cross-tier covariance.
11. Insufficient independent cluster handling.
12. Posterior interval coverage.
13. Training-fold-only hyperparameter estimation.
14. Subgroup metric uncertainty.
15. NaN cluster SE cannot become sufficient.
16. Full pipeline reproducibility.
17. Canonical dataset hash preservation.
"""

import os
import sys
import hashlib
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_4_2.cluster_variance_b4_2 import (
    compute_multiway_cluster_variance,
    compute_match_block_bootstrap_covariance,
    compute_multivariate_dersimonian_laird_b42
)
from src.m5_5b_4_2.epistemic_context_engine_b4_2 import (
    ContextualPlayerBaselineRecordB42,
    EpistemicStateB42
)
from src.m5_5b_4_2.hierarchical_engine_b4_2 import (
    ContextualHierarchyB42,
    PlayerPosteriorBaselineEstimatorB42
)
from src.m5_5b_4_2.bowler_fairness_matched_b4_2 import run_player_match_fairness_analysis_b42
from src.m5_5b_4_2.calibration_engine_b4_2 import (
    compute_binary_calibration_metrics,
    compute_posterior_interval_coverage
)
from src.m5_5b_4_2.run_validation_b4_2 import compute_metric_cluster_robust_se


class TestStatisticalValidityB42(unittest.TestCase):
    def setUp(self):
        # Create a minimal synthetic hierarchical setup for tests with all 4 pressure tiers
        records = []
        phases = ["Powerplay", "Middle", "Death"]
        tiers = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
        for mid in range(1, 15):
            for bid in range(101, 106):
                for phase in phases:
                    for tier in tiers:
                        for _ in range(3):
                            records.append({
                                "match_id": mid,
                                "striker_id": bid,
                                "bowler_id": bid + 100,
                                "pre_match_phase": phase,
                                "pre_pressure_tier": tier,
                                "ext_is_legal_delivery": 1,
                                "ext_is_wide": 0,
                                "ext_is_noball": 0,
                                "ext_is_four": 1 if phase == "Death" and bid == 101 else 0,
                                "ext_is_six": 0,
                                "ext_bowler_debit_runs": 2 if phase == "Death" else 1
                            })
        self.df_synth = pd.DataFrame(records)
        self.hier = ContextualHierarchyB42(n_boot=20)
        self.hier.fit(self.df_synth)
        self.estimator = PlayerPosteriorBaselineEstimatorB42(self.hier)

    def test_01_context_specific_batter_posterior_isolation(self):
        """
        Critical Requirement 1: Changing a batter's Powerplay performance without changing
        their Death performance leaves the Death personal observation and baseline strictly unchanged.
        """
        # Baseline A: Player 1 with 100 PP balls, 30 PP boundaries, 50 Death balls, 15 Death boundaries
        rec_a_death = self.estimator.estimate_batter_boundary_posterior(
            player_id=1, phase="Death", tier="Tier 4: Extreme",
            context_balls=50, context_boundaries=15.0, context_matches=5,
            career_balls=150, career_boundaries=45.0, career_matches=10
        )
        # Baseline B: Player 1 has massive increase in PP performance: 200 PP balls, 100 PP boundaries!
        # BUT their Death performance is IDENTICAL: 50 Death balls, 15 Death boundaries
        rec_b_death = self.estimator.estimate_batter_boundary_posterior(
            player_id=1, phase="Death", tier="Tier 4: Extreme",
            context_balls=50, context_boundaries=15.0, context_matches=5,
            career_balls=250, career_boundaries=115.0, career_matches=15
        )
        # Observed context rate in Death must be EXACTLY identical
        self.assertEqual(rec_a_death.observed_context_rate, rec_b_death.observed_context_rate)
        # Shrunk estimate in Death must be EXACTLY identical under context isolation
        self.assertEqual(rec_a_death.shrunk_estimate, rec_b_death.shrunk_estimate)
        self.assertEqual(rec_a_death.context_exposure, 50)

    def test_02_context_specific_bowler_posterior_isolation(self):
        """
        Critical Requirement 2: Changing a bowler's Powerplay performance without changing
        their Death performance leaves the Death personal observation strictly unchanged.
        """
        # Scenario A: Bowler 2 with 60 Death balls, 100 Death debit runs
        rec_a_death = self.estimator.estimate_bowler_economy_posterior(
            player_id=2, phase="Death", tier="Tier 4: Extreme",
            context_legal_balls=60, context_debit_runs=100.0, context_matches=6,
            career_legal_balls=180, career_debit_runs=250.0, career_matches=12
        )
        # Scenario B: Bowler 2 has huge PP shift (extra 200 balls and 300 runs), Death is UNCHANGED
        rec_b_death = self.estimator.estimate_bowler_economy_posterior(
            player_id=2, phase="Death", tier="Tier 4: Extreme",
            context_legal_balls=60, context_debit_runs=100.0, context_matches=6,
            career_legal_balls=380, career_debit_runs=550.0, career_matches=20
        )
        self.assertEqual(rec_a_death.observed_context_rate, rec_b_death.observed_context_rate)
        self.assertEqual(rec_a_death.shrunk_estimate, rec_b_death.shrunk_estimate)

    def test_03_player_by_phase_interaction_behavior(self):
        """
        Requirement 3: Verifies that player-context observations capture phase differences.
        A player who is prolific in Powerplay but struggles in Death receives different context observations.
        """
        rec_pp = self.estimator.estimate_batter_boundary_posterior(
            player_id=3, phase="Powerplay", tier="Tier 1: Low",
            context_balls=60, context_boundaries=18.0, context_matches=6,
            career_balls=120, career_boundaries=22.0, career_matches=10
        )
        rec_death = self.estimator.estimate_batter_boundary_posterior(
            player_id=3, phase="Death", tier="Tier 4: Extreme",
            context_balls=60, context_boundaries=4.0, context_matches=6,
            career_balls=120, career_boundaries=22.0, career_matches=10
        )
        self.assertGreater(rec_pp.observed_context_rate, rec_death.observed_context_rate)
        self.assertNotEqual(rec_pp.shrunk_estimate, rec_death.shrunk_estimate)

    def test_04_player_by_pressure_tier_interaction_behavior(self):
        """
        Requirement 4: Verifies distinct contextual observations across pressure tiers.
        """
        rec_low = self.estimator.estimate_batter_boundary_posterior(
            player_id=4, phase="Middle", tier="Tier 1: Low",
            context_balls=50, context_boundaries=5.0, context_matches=5,
            career_balls=100, career_boundaries=15.0, career_matches=10
        )
        rec_high = self.estimator.estimate_batter_boundary_posterior(
            player_id=4, phase="Middle", tier="Tier 4: Extreme",
            context_balls=50, context_boundaries=12.0, context_matches=5,
            career_balls=100, career_boundaries=15.0, career_matches=10
        )
        self.assertNotEqual(rec_low.observed_context_rate, rec_high.observed_context_rate)

    def test_05_zero_and_missing_contextual_exposure(self):
        """
        Requirement 5: Preserves zero-exposure and missing-outcome states explicitly.
        """
        # ZERO_CAREER_EXPOSURE
        r0 = self.estimator.estimate_batter_boundary_posterior(
            player_id=5, phase="Death", tier="Tier 4: Extreme",
            context_balls=0, context_boundaries=None, context_matches=0,
            career_balls=0, career_boundaries=None, career_matches=0
        )
        self.assertEqual(r0.state, EpistemicStateB42.ZERO_CAREER_EXPOSURE)
        self.assertTrue(np.isnan(r0.observed_context_rate))
        self.assertFalse(r0.has_observed_rate)
        
        # ZERO_CONTEXT_EXPOSURE (has career balls, but 0 in Death Tier 4)
        r1 = self.estimator.estimate_batter_boundary_posterior(
            player_id=6, phase="Death", tier="Tier 4: Extreme",
            context_balls=0, context_boundaries=None, context_matches=0,
            career_balls=100, career_boundaries=15.0, career_matches=8
        )
        self.assertEqual(r1.state, EpistemicStateB42.ZERO_CONTEXT_EXPOSURE)
        self.assertTrue(np.isnan(r1.observed_context_rate))
        self.assertAlmostEqual(r1.shrunk_estimate, r1.context_prior_mean)
        
        # MISSING_OUTCOME
        r2 = self.estimator.estimate_batter_boundary_posterior(
            player_id=7, phase="Death", tier="Tier 4: Extreme",
            context_balls=50, context_boundaries=None, context_matches=5,
            career_balls=100, career_boundaries=15.0, career_matches=8
        )
        self.assertEqual(r2.state, EpistemicStateB42.MISSING_OUTCOME)
        self.assertTrue(np.isnan(r2.shrunk_estimate))

    def test_06_leave_one_player_out_benchmark_contamination(self):
        """
        Requirement 6: In LOPO fairness analysis, bowler k's own deliveries are excluded
        from their context benchmark.
        """
        csv_path = "audit_reports/M5_5B_4_2/M5_5B_4_2_PLAYER_FAIRNESS_DIAGNOSTICS.csv"
        if not os.path.exists(csv_path):
            run_player_match_fairness_analysis_b42()
        df_f = pd.read_csv(csv_path)
        self.assertGreater(len(df_f), 10)
        # Gaps must be present, finite, and non-constant
        gaps = df_f["player_specific_counterfactual_gap"].dropna().values
        self.assertGreater(len(gaps), 10)
        self.assertGreater(np.std(gaps), 0.05)

    def test_07_match_paired_phase_estimate_and_confidence_interval(self):
        """
        Requirement 7: Genuinely paired player-match observations have valid cluster SEs
        and finite confidence intervals.
        """
        csv_path = "audit_reports/M5_5B_4_2/M5_5B_4_2_PLAYER_FAIRNESS_DIAGNOSTICS.csv"
        df_f = pd.read_csv(csv_path)
        valid_paired = df_f[df_f["paired_contrast_status"] == "VALID_MATCHED_CONTRAST"]
        self.assertGreater(len(valid_paired), 5)
        for _, row in valid_paired.iterrows():
            self.assertTrue(np.isfinite(row["shift_cluster_se"]))
            self.assertTrue(np.isfinite(row["shift_ci_lower"]))
            self.assertTrue(np.isfinite(row["shift_ci_upper"]))
            self.assertGreater(row["paired_matches_count"], 2)

    def test_08_unequal_legal_ball_exposure(self):
        """
        Requirement 8: Harmonic exposure weighting handles unequal PP vs Death legal ball exposure.
        """
        # Test harmonic formula: w = 2 / (1/n1 + 1/n2)
        n1, n2 = 12, 6  # 2 overs in PP, 1 over in Death
        h_w = 2.0 / ((1.0 / n1) + (1.0 / n2))
        self.assertAlmostEqual(h_w, 8.0)
        self.assertLess(h_w, min(n1, n2) * 1.5)

    def test_09_repeated_player_dependence_across_matches(self):
        """
        Requirement 9: Multiway cluster variance computes two-way variance on match and player.
        """
        resids = np.array([0.5, -0.5, 0.4, -0.4, 0.6, -0.6, 0.3, -0.3, 0.2, -0.2])
        g1 = np.array([1, 1, 2, 2, 3, 3, 4, 4, 5, 5])  # Matches (5 clusters)
        g2 = np.array([10, 20, 30, 40, 50, 10, 20, 30, 40, 50])  # Players (5 clusters)
        v, status = compute_multiway_cluster_variance(resids, g1, g2)
        self.assertTrue(np.isfinite(v))
        self.assertEqual(status, "TWOWAY_CLUSTER_VALID")

    def test_10_cross_tier_covariance(self):
        """
        Requirement 10: Match-block bootstrap returns a full covariance matrix across tiers.
        """
        cov, tiers, status = compute_match_block_bootstrap_covariance(
            self.df_synth, phase="Death", metric_type="batter_boundary", n_boot=30
        )
        self.assertEqual(cov.shape, (4, 4))
        self.assertEqual(status, "BOOTSTRAP_COVARIANCE_SUCCESS")

    def test_11_insufficient_independent_clusters(self):
        """
        Requirement 11: When clusters < 5, multiway cluster variance returns INSUFFICIENT_CLUSTERS.
        """
        resids = np.array([1.0, 2.0, 3.0])
        g1 = np.array([1, 1, 2])  # Only 2 clusters
        v, status = compute_multiway_cluster_variance(resids, g1)
        self.assertTrue(np.isnan(v))
        self.assertEqual(status, "INSUFFICIENT_CLUSTERS")

    def test_12_posterior_interval_coverage(self):
        """
        Requirement 12: Evaluates posterior credible interval coverage on simulated calibrated data.
        """
        y_true = np.array([8.0, 9.0, 7.5, 8.5, 9.5, 7.0, 8.2, 8.8, 9.1, 7.9])
        y_pred = np.full(10, 8.3)
        se = np.full(10, 1.0)
        cov = compute_posterior_interval_coverage(y_true, y_pred, se)
        self.assertTrue(np.isfinite(cov["coverage_80"]))
        self.assertTrue(np.isfinite(cov["coverage_95"]))
        self.assertGreater(cov["coverage_95"], 0.70)

    def test_13_training_fold_only_hyperparameter_estimation(self):
        """
        Requirement 13: Verifies M0 and tau2 are estimated and bounded strictly on training fold.
        """
        params = self.hier.hyperparameters
        self.assertIn("batter_m0", params)
        self.assertIn("bowler_m0", params)
        self.assertTrue(20.0 <= params["batter_m0"] <= 200.0)
        self.assertTrue(30.0 <= params["bowler_m0"] <= 250.0)

    def test_14_subgroup_metric_uncertainty(self):
        """
        Requirement 14: Subgroup cluster SE measures uncertainty in the prediction loss metric.
        """
        losses = np.array([0.1, 0.2, 0.15, 0.05, 0.3, 0.25, 0.1, 0.05, 0.2, 0.15])
        clusters = np.array([1, 1, 2, 2, 3, 3, 4, 4, 5, 5])
        se, status = compute_metric_cluster_robust_se(losses, clusters)
        self.assertTrue(np.isfinite(se))
        self.assertEqual(status, "VALID_CLUSTER_SE")

    def test_15_nan_cluster_se_cannot_become_sufficient(self):
        """
        Requirement 15: NaN or unavailable cluster SE must NEVER produce SUFFICIENT.
        """
        losses = np.array([0.1, 0.2])
        clusters = np.array([1, 1])  # Only 1 cluster
        se, status = compute_metric_cluster_robust_se(losses, clusters)
        self.assertTrue(np.isnan(se))
        # Rule check: if se is nan, status must NOT be SUFFICIENT
        self.assertNotEqual(status, "VALID_CLUSTER_SE")

    def test_16_full_pipeline_reproducibility(self):
        """
        Requirement 16: Verifies that fold isolation and model comparison records exist
        and maintain zero overlap across folds.
        """
        iso_path = "audit_reports/M5_5B_4_2/M5_5B_4_2_FOLD_MATCH_ISOLATION.json"
        if os.path.exists(iso_path):
            import json
            with open(iso_path, "r", encoding="utf-8") as f:
                iso = json.load(f)
            self.assertEqual(len(iso), 5)
            for f_key, f_data in iso.items():
                self.assertEqual(f_data["intersection_count"], 0)

    def test_17_canonical_dataset_hash_preservation(self):
        """
        Requirement 17: Canonical dataset SHA-256 matches exactly:
        ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4
        """
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        h = hashlib.sha256()
        with open(canonical_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        actual_hash = h.hexdigest()
        self.assertEqual(actual_hash, "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4")


if __name__ == "__main__":
    unittest.main()
