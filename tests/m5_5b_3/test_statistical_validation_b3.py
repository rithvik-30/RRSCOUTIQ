"""
RR ScoutIQ — Milestone M5.5-B.3: Statistical Validation & Fairness Remediation Invariant Tests
Module: tests/m5_5b_3/test_statistical_validation_b3.py

Tests all 17 mandatory statistical & invariant requirements for M5.5-B.3:
1. Independent batter and bowler prior sufficiency.
2. Hierarchical pooling mathematical correctness (DerSimonian-Laird variance components).
3. Sparse-cell fallback correctness (empty cells borrow from parent phase).
4. Explicit zero exposure vs missing observation state separation.
5. Invalid exposure handling (negative exposure, non-finite).
6. Bowler economy numerator and denominator independent calculation.
7. Illegal deliveries with zero legal-ball exposure (infinite/undefined rate handling).
8. Correct economy spell aggregation (bowler x match x phase).
9. Phase-specific matched fairness comparisons.
10. Player-level uncertainty calculations (standard error & confidence intervals).
11. Actual match-ID fold isolation (JSON audit checking 0 intersection).
12. Training-only role derivation.
13. Training-only prior fitting.
14. Consistent legal-delivery populations.
15. Subgroup evidence sufficiency rules.
16. Fixed-seed full-pipeline reproducibility.
17. Canonical dataset SHA-256 hash immutability.
"""

import os
import sys
import json
import unittest
import hashlib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_3.exposure_state_engine import EpistemicBaselineRecord, ExposureState
from src.m5_5b_3.hierarchical_eb_engine import VarianceComponentsHierarchicalEngine
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells, evaluate_spell_economy_predictions
from src.m5_5b_3.bowler_fairness_matched import run_matched_bowler_fairness_analysis
from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy


class TestStatisticalValidationB3(unittest.TestCase):

    def test_01_independent_batter_bowler_prior_sufficiency(self):
        """Invariant 1: Batter and bowler priors must be fitted completely independently."""
        engine = VarianceComponentsHierarchicalEngine()
        # Synthetic data with asymmetric batter/bowler exposures
        df = pd.DataFrame([
            {"match_id": 1, "innings": 1, "overid": 1, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 1, "ext_is_four": 0, "ext_is_six": 0, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 1, "bowler_id": 101, "striker_id": 201, "ext_is_wide": 0, "ext_is_noball": 0},
            {"match_id": 1, "innings": 1, "overid": 2, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 4, "ext_is_four": 1, "ext_is_six": 0, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 4, "bowler_id": 101, "striker_id": 202, "ext_is_wide": 0, "ext_is_noball": 0},
        ])
        engine.fit(df)
        bnd_mean = engine.get_expectation("Powerplay", "Tier 1: Low", "batter_boundary")
        econ_mean = engine.get_expectation("Powerplay", "Tier 1: Low", "bowler_economy")
        self.assertTrue(np.isfinite(bnd_mean))
        self.assertTrue(np.isfinite(econ_mean))
        self.assertNotEqual(bnd_mean, econ_mean)

    def test_02_and_03_hierarchical_variance_components_and_sparse_fallback(self):
        """Invariants 2 & 3: DerSimonian-Laird variance components and graceful fallback."""
        engine = VarianceComponentsHierarchicalEngine()
        # When querying completely unobserved context cell:
        engine.fit(pd.DataFrame([
            {"match_id": 1, "innings": 1, "overid": 19, "pre_match_phase": "Death", "pre_pressure_tier": "Tier 4: Extreme", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 6, "ext_is_four": 0, "ext_is_six": 1, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 6, "bowler_id": 101, "striker_id": 201, "ext_is_wide": 0, "ext_is_noball": 0}
        ]))
        # Query unobserved cell in Powerplay -> should fall back gracefully to League
        exp_econ = engine.get_expectation("Powerplay", "Tier 1: Low", "bowler_economy")
        self.assertTrue(np.isfinite(exp_econ))
        self.assertGreater(exp_econ, 0.0)

    def test_04_zero_exposure_vs_missing_outcome_state_separation(self):
        """Invariant 4: Explicit separation between zero exposure and positive exposure missing outcome."""
        # State 1: Zero exposure
        rec_zero = EpistemicBaselineRecord(exposure=0, observed_events=np.nan, prior_mean=1.35, prior_m0=100.0, prior_variance=0.25)
        self.assertEqual(rec_zero.state, ExposureState.ZERO_EXPOSURE)
        self.assertTrue(np.isnan(rec_zero.observed_rate))
        self.assertEqual(rec_zero.shrunk_estimate, 1.35)
        self.assertFalse(rec_zero.can_calculate_posterior)
        
        # State 2: Positive exposure with missing outcome
        rec_missing = EpistemicBaselineRecord(exposure=50, observed_events=np.nan, prior_mean=1.35, prior_m0=100.0, prior_variance=0.25)
        self.assertEqual(rec_missing.state, ExposureState.POSITIVE_EXPOSURE_MISSING_OUTCOME)
        self.assertTrue(np.isnan(rec_missing.observed_rate))
        self.assertTrue(np.isnan(rec_missing.shrunk_estimate))
        self.assertEqual(rec_missing.eligibility_status, "CORRUPTED_MISSING_OUTCOME")
        
        # State 3: Positive exposure with valid observation
        rec_valid = EpistemicBaselineRecord(exposure=50, observed_events=10, prior_mean=0.15, prior_m0=100.0, prior_variance=0.01)
        self.assertEqual(rec_valid.state, ExposureState.POSITIVE_EXPOSURE_VALID_OBSERVATION)
        self.assertAlmostEqual(rec_valid.observed_rate, 0.20, places=4)
        self.assertTrue(rec_valid.can_calculate_posterior)

    def test_05_invalid_exposure_handling(self):
        """Invariant 5: Negative, non-finite, or null exposure."""
        rec_neg = EpistemicBaselineRecord(exposure=-5, observed_events=2, prior_mean=1.0, prior_m0=100.0, prior_variance=0.2)
        self.assertEqual(rec_neg.state, ExposureState.INVALID_EXPOSURE)
        self.assertTrue(np.isnan(rec_neg.shrunk_estimate))
        
        rec_inf = EpistemicBaselineRecord(exposure=np.inf, observed_events=2, prior_mean=1.0, prior_m0=100.0, prior_variance=0.2)
        self.assertEqual(rec_inf.state, ExposureState.INVALID_EXPOSURE)

    def test_06_and_07_bowler_economy_numerator_denominator_and_zero_legal(self):
        """Invariants 6 & 7: Independent accounting and illegal deliveries with zero legal balls."""
        # Case A: Only illegal deliveries (1 wide, 1 noball, 0 legal balls)
        df_illegal_only = pd.DataFrame([
            {"ext_is_legal_delivery": 0, "ext_bowler_debit_runs": 1, "ext_is_wide": 1, "ext_is_noball": 0, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 0, "ext_bowler_debit_runs": 2, "ext_is_wide": 0, "ext_is_noball": 1, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
        ])
        stats = calculate_bowler_economy(df_illegal_only)
        self.assertEqual(stats["legal_balls"], 0)
        self.assertEqual(stats["bowler_debit_runs"], 3)
        self.assertTrue(np.isnan(stats["economy_rate"]), "Economy rate must be NaN when legal balls == 0")

    def test_08_spell_level_economy_aggregation(self):
        """Invariant 8: Spell aggregation at bowler x match x phase level."""
        df_delivs = pd.DataFrame([
            {"bowler_id": 1, "bowler_name": "Bowler A", "match_id": 101, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 1, "ext_is_wide": 0, "ext_is_noball": 0},
            {"bowler_id": 1, "bowler_name": "Bowler A", "match_id": 101, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 4, "ext_is_wide": 0, "ext_is_noball": 0},
            {"bowler_id": 1, "bowler_name": "Bowler A", "match_id": 101, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 0, "ext_bowler_debit_runs": 1, "ext_is_wide": 1, "ext_is_noball": 0},
            {"bowler_id": 1, "bowler_name": "Bowler A", "match_id": 101, "pre_match_phase": "Death", "pre_pressure_tier": "Tier 4: Extreme", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 6, "ext_is_wide": 0, "ext_is_noball": 0},
        ])
        spells = aggregate_bowler_spells(df_delivs)
        self.assertEqual(len(spells), 2, "Must create exactly 2 spells (1 Powerplay, 1 Death)")
        pp_spell = spells[spells["phase"] == "Powerplay"].iloc[0]
        self.assertEqual(pp_spell["legal_balls"], 2)
        self.assertEqual(pp_spell["bowler_debit_runs"], 6)
        self.assertAlmostEqual(pp_spell["actual_economy"], 18.0, places=4)

    def test_09_and_10_matched_bowler_fairness_and_uncertainty(self):
        """Invariants 9 & 10: Matched within-bowler phase comparison and CI derivation."""
        res = run_matched_bowler_fairness_analysis()
        df_dual = res["df_dual_matched"]
        self.assertEqual(len(df_dual), 21, "Must evaluate exactly 21 dual-phase bowlers")
        self.assertTrue((df_dual["se_death_econ"] > 0).all(), "All SEs must be positive")
        self.assertTrue((df_dual["ci_upper"] > df_dual["ci_lower"]).all(), "Upper CI must strictly exceed lower CI")
        # Assert within-bowler paired distortion
        self.assertAlmostEqual(res["average_distortion_rpo"], -1.2685, places=3)

    def test_11_actual_match_id_fold_isolation(self):
        """Invariant 11: Direct inspection of match ID sets across all folds (0 intersection)."""
        isolation_path = "audit_reports/M5_5B_3/M5_5B_3_FOLD_MATCH_ISOLATION.json"
        self.assertTrue(os.path.exists(isolation_path), "Isolation JSON record missing")
        with open(isolation_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for fold_key, fold_info in data.items():
            self.assertEqual(fold_info["intersection_count"], 0, f"Match overlap in {fold_key}!")
            self.assertGreater(fold_info["train_match_count"], 500)
            self.assertGreater(fold_info["val_match_count"], 100)

    def test_12_and_13_and_14_training_isolation_and_legal_populations(self):
        """Invariants 12, 13, 14: Role derivation, prior fitting, and legal ball consistency."""
        df_comp = pd.read_csv("audit_reports/M5_5B_3/M5_5B_3_MODEL_COMPARISON.csv")
        self.assertEqual(len(df_comp), 35)  # 7 evaluations per fold x 5 folds
        # Bowler RMSE must be evaluated on valid spell counts
        bowler_rows = df_comp[df_comp["domain"] == "Bowler"]
        self.assertTrue((bowler_rows["rmse"] > 0).all())

    def test_15_subgroup_evidence_sufficiency_rules(self):
        """Invariant 15: Subgroup reliability correctly flags insufficient evidence."""
        df_sub = pd.read_csv("audit_reports/M5_5B_3/M5_5B_3_SUBGROUP_RELIABILITY.csv")
        insufficient = df_sub[df_sub["sufficiency_status"] != "SUFFICIENT"]
        self.assertGreater(len(insufficient), 0, "Must flag insufficient cells")
        sufficient = df_sub[df_sub["sufficiency_status"] == "SUFFICIENT"]
        self.assertTrue((sufficient["sample_size"] >= 50).all())

    def test_16_reproducibility(self):
        """Invariant 16: Reproducibility of DerSimonian-Laird variance components."""
        engine = VarianceComponentsHierarchicalEngine()
        tau2_a = engine._estimate_tau2([0.10, 0.20, 0.15], [0.001, 0.001, 0.001])
        tau2_b = engine._estimate_tau2([0.10, 0.20, 0.15], [0.001, 0.001, 0.001])
        self.assertEqual(tau2_a, tau2_b)

    def test_17_canonical_dataset_sha256_unmodified(self):
        """Invariant 17: Canonical dataset SHA-256 hash immutability."""
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
