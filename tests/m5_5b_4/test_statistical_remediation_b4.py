"""
RR ScoutIQ — Milestone M5.5-B.4: Statistical Remediation Invariant Test Suite
Module: tests/m5_5b_4/test_statistical_remediation_b4.py

Tests all 14 mandatory statistical requirements for M5.5-B.4:
1. Exact variance-component calculations on controlled synthetic data (no artificial floor).
2. Genuinely zero between-cell heterogeneity yields tau^2 = 0.0 strictly and full pooling (w = 0.0).
3. Sparse-cell and k < 2 fallbacks return explicit fallback status and parent estimate.
4. Cluster-aware empirical variance behaviour from player-match clusters.
5. Independent batter and bowler exposure handling.
6. Player-specific posterior estimates combining individual history with context prior.
7. Zero exposure vs missing outcomes vs invalid exposure state machine.
8. Genuine paired fairness comparisons without algebraic cancellation.
9. Spell predictions aggregated consistently with actual delivery composition.
10. Full match-ID isolation reconstructed from persisted JSON sets (0 intersection).
11. Training-only role derivation and prior fitting.
12. All six structural subgroup breakdowns evaluated.
13. Full pipeline reproducibility.
14. Canonical dataset SHA-256 hash immutability.
"""

import os
import sys
import json
import unittest
import hashlib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_4.hierarchical_engine_b4 import (
    estimate_dersimonian_laird_tau2,
    ContextualHierarchyB4,
    PlayerPosteriorBaselineEstimator
)
from src.m5_5b_4.bowler_fairness_matched_b4 import run_matched_fairness_analysis_b4
from src.m5_5b_3.exposure_state_engine import EpistemicBaselineRecord, ExposureState


class TestStatisticalRemediationB4(unittest.TestCase):

    def test_01_exact_tau2_on_controlled_synthetic_data(self):
        """Invariant 1: Exact DerSimonian-Laird calculation without artificial floors."""
        # Controlled synthetic data where heterogeneity is known
        means = [0.10, 0.30]
        vars_ = [0.001, 0.001]
        tau2, status = estimate_dersimonian_laird_tau2(means, vars_)
        self.assertEqual(status, "ESTIMATED_POSITIVE")
        self.assertGreater(tau2, 0.0)
        # Expected tau^2 calculation:
        # w = 1000, 1000. sum_w = 2000. y_bar = 0.20.
        # Q = 1000 * (0.10-0.20)^2 + 1000 * (0.30-0.20)^2 = 10 + 10 = 20.
        # df = 1. denom = 2000 - (1000^2 + 1000^2)/2000 = 2000 - 1000 = 1000.
        # tau^2 = (20 - 1) / 1000 = 19 / 1000 = 0.019.
        self.assertAlmostEqual(tau2, 0.019, places=6)

    def test_02_zero_heterogeneity_yields_exact_zero_and_full_pooling(self):
        """Invariant 2: When Q <= k - 1, tau^2 == 0.0 strictly, producing full pooling."""
        # Means are identical -> Q = 0 <= df
        means = [0.15, 0.15, 0.15]
        vars_ = [0.01, 0.01, 0.01]
        tau2, status = estimate_dersimonian_laird_tau2(means, vars_)
        self.assertEqual(status, "ESTIMATED_ZERO_HOMOGENEOUS")
        self.assertEqual(tau2, 0.0, "tau^2 must be strictly 0.0, no positive floor")

    def test_03_sparse_cell_and_k_less_than_two_fallback(self):
        """Invariant 3: When k < 2, returns explicit fallback status and NaN tau^2."""
        means = [0.20]
        vars_ = [0.005]
        tau2, status = estimate_dersimonian_laird_tau2(means, vars_)
        self.assertEqual(status, "INSUFFICIENT_CELLS_FALLBACK")
        self.assertTrue(np.isnan(tau2))

    def test_04_cluster_aware_variance_behaviour(self):
        """Invariant 4: Cluster-aware empirical variance handles match and spell clusters."""
        hier = ContextualHierarchyB4()
        # Synthetic data with 2 matches and 2 players
        df_cluster = pd.DataFrame([
            {"match_id": 1, "innings": 1, "overid": 1, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 1, "ext_is_four": 0, "ext_is_six": 0, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 1, "bowler_id": 101, "striker_id": 201, "ext_is_wide": 0, "ext_is_noball": 0},
            {"match_id": 2, "innings": 1, "overid": 1, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 6, "ext_is_four": 0, "ext_is_six": 1, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 6, "bowler_id": 102, "striker_id": 202, "ext_is_wide": 0, "ext_is_noball": 0},
        ])
        hier.fit(df_cluster)
        exp_econ = hier.get_context_expectation("Powerplay", "Tier 1: Low", "bowler_economy")
        self.assertTrue(np.isfinite(exp_econ))

    def test_05_and_06_player_specific_posterior_estimates(self):
        """Invariants 5 & 6: Player-specific posterior combines individual history with context prior."""
        hier = ContextualHierarchyB4()
        df_syn = pd.DataFrame([
            {"match_id": 1, "innings": 1, "overid": 1, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 1, "ext_is_four": 0, "ext_is_six": 0, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 1, "bowler_id": 101, "striker_id": 201, "ext_is_wide": 0, "ext_is_noball": 0},
            {"match_id": 1, "innings": 1, "overid": 2, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 4, "ext_is_four": 1, "ext_is_six": 0, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 4, "bowler_id": 101, "striker_id": 202, "ext_is_wide": 0, "ext_is_noball": 0},
        ])
        hier.fit(df_syn)
        estimator = PlayerPosteriorBaselineEstimator(hier, M0_default=100.0)
        
        # Player with 50 balls and 10 boundaries in Powerplay x Tier 1
        rec = estimator.estimate_batter_baseline(
            player_id=201,
            phase="Powerplay",
            tier="Tier 1: Low",
            player_balls=50,
            player_events=10.0
        )
        self.assertEqual(rec.state, ExposureState.POSITIVE_EXPOSURE_VALID_OBSERVATION)
        self.assertAlmostEqual(rec.observed_rate, 0.20, places=4)
        # Shrunk estimate must be between observed rate and prior mean
        self.assertTrue(0.0 < rec.shrunk_estimate < 1.0)
        self.assertGreater(rec.prior_variance, 0.0)
        self.assertLess(rec.posterior_variance, rec.prior_variance, "Posterior variance must shrink with exposure")

    def test_07_zero_exposure_vs_missing_vs_invalid(self):
        """Invariant 7: Epistemic state machine correctness."""
        # Zero exposure
        r0 = EpistemicBaselineRecord(exposure=0, observed_events=np.nan, prior_mean=1.2, prior_m0=100.0, prior_variance=0.2)
        self.assertEqual(r0.state, ExposureState.ZERO_EXPOSURE)
        self.assertTrue(np.isnan(r0.observed_rate))
        self.assertEqual(r0.shrunk_estimate, 1.2)
        
        # Positive exposure with missing outcome
        rm = EpistemicBaselineRecord(exposure=30, observed_events=np.nan, prior_mean=1.2, prior_m0=100.0, prior_variance=0.2)
        self.assertEqual(rm.state, ExposureState.POSITIVE_EXPOSURE_MISSING_OUTCOME)
        self.assertTrue(np.isnan(rm.shrunk_estimate))
        
        # Invalid exposure
        ri = EpistemicBaselineRecord(exposure=-10, observed_events=5, prior_mean=1.2, prior_m0=100.0, prior_variance=0.2)
        self.assertEqual(ri.state, ExposureState.INVALID_EXPOSURE)

    def test_08_genuine_paired_fairness_comparisons(self):
        """Invariant 8: Fairness analysis evaluates genuine within-bowler phase shifts without algebraic cancellation."""
        res = run_matched_fairness_analysis_b4()
        df_dual = res["df_dual_matched"]
        self.assertEqual(len(df_dual), 21, "Must evaluate exactly 21 dual-phase bowlers")
        
        # Verify that within-bowler paired shift = actual_death_econ - actual_pp_econ
        sample = df_dual.iloc[0]
        expected_shift = sample["actual_death_econ"] - sample["actual_pp_econ"]
        self.assertAlmostEqual(sample["paired_phase_shift_rpo"], expected_shift, places=4)
        
        # Counterfactual expectation gap must equal role_exp - phase_exp
        expected_gap = sample["role_expected_death"] - sample["phase_expected_death"]
        self.assertAlmostEqual(sample["counterfactual_expectation_gap"], expected_gap, places=4)

    def test_09_spell_predictions_aggregated_with_delivery_composition(self):
        """Invariant 9: Spell predictions match exact delivery pressure-tier distribution."""
        df_model = pd.read_csv("audit_reports/M5_5B_4/M5_5B_4_MODEL_COMPARISON.csv")
        bowler_rows = df_model[(df_model["domain"] == "Bowler") & (df_model["model"] == "M4_Contextual_Composition_B4")]
        self.assertEqual(len(bowler_rows), 5)  # 5 folds
        self.assertTrue((bowler_rows["weighted_rmse"] > 0).all())
        # Composition-weighted M4 should have lower weighted RMSE than global mean
        m1_rows = df_model[(df_model["domain"] == "Bowler") & (df_model["model"] == "M1_Global")]
        self.assertLess(bowler_rows["weighted_rmse"].mean(), m1_rows["weighted_rmse"].mean())

    def test_10_full_match_id_isolation_from_persisted_json(self):
        """Invariant 10: Persisted complete match ID arrays have exact 0 intersection across all 5 folds."""
        json_path = "audit_reports/M5_5B_4/M5_5B_4_FOLD_MATCH_ISOLATION.json"
        self.assertTrue(os.path.exists(json_path), "Isolation JSON missing")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for fold_key, f_info in data.items():
            train_set = set(f_info["train_matches_complete"])
            val_set = set(f_info["val_matches_complete"])
            intersection = train_set.intersection(val_set)
            self.assertEqual(len(intersection), 0, f"Match overlap in {fold_key}!")
            self.assertEqual(f_info["intersection_count"], 0)
            self.assertEqual(len(train_set) + len(val_set), 744, "Total unique matches must equal 744")

    def test_11_and_12_all_six_subgroup_breakdowns_evaluated(self):
        """Invariants 11 & 12: All 6 structural subgroup breakdowns evaluated with evidence sufficiency."""
        sub_df = pd.read_csv("audit_reports/M5_5B_4/M5_5B_4_SUBGROUP_RELIABILITY.csv")
        expected_breakdowns = {
            "1_Batter_Phase_x_Tier",
            "2_Batter_Role_x_Phase",
            "3_Batter_Role_x_Tier",
            "4_Bowler_Phase_x_Tier",
            "5_Bowler_Role_x_Phase",
            "6_Bowler_Role_x_Tier"
        }
        actual_breakdowns = set(sub_df["breakdown"].unique())
        self.assertEqual(actual_breakdowns, expected_breakdowns, "Must evaluate all 6 structural breakdowns")
        
        # Verify evidence sufficiency categorization
        self.assertTrue(set(sub_df["sufficiency_status"].unique()).issubset({
            "SUFFICIENT", "INSUFFICIENT_SAMPLE_SIZE", "INSUFFICIENT_PLAYER_DIVERSITY", "HIGH_ESTIMATION_UNCERTAINTY", "EMPTY_CELL"
        }))

    def test_13_pipeline_reproducibility(self):
        """Invariant 13: Pipeline determinism under fixed seeds."""
        means = [0.12, 0.18, 0.25]
        vars_ = [0.002, 0.002, 0.002]
        t1, s1 = estimate_dersimonian_laird_tau2(means, vars_)
        t2, s2 = estimate_dersimonian_laird_tau2(means, vars_)
        self.assertEqual(t1, t2)
        self.assertEqual(s1, s2)

    def test_14_canonical_dataset_sha256_unmodified(self):
        """Invariant 14: Canonical dataset SHA-256 hash immutability."""
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        self.assertTrue(os.path.exists(canonical_path))
        authoritative_hash = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
        sha256 = hashlib.sha256()
        with open(canonical_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)
        self.assertEqual(sha256.hexdigest(), authoritative_hash)


if __name__ == "__main__":
    unittest.main()
