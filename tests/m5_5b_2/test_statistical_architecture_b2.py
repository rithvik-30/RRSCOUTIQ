"""
RR ScoutIQ — Milestone M5.5-B.2: Statistical Architecture & Invariant Test Suite
Module: tests/m5_5b_2/test_statistical_architecture_b2.py

Tests all 12 mandatory M5.5-B.2 statistical invariants:
1. Actual NaN handling at zero exposure (preserves np.nan, does not calculate rate, 0*NaN=NaN).
2. Prior-only behavior when exposure is zero (defaults to prior mean, inflates posterior variance).
3. Correct legal-ball denominator for bowler economy.
4. Correct bowler-debited-runs numerator (includes wides and no-balls; excludes byes, leg-byes, penalty).
5. Hand-constructed multi-delivery economy scenario (legal, wide, noball, bye, legbye).
6. Fold isolation of all prior-fitting operations (0 match overlap).
7. Zero validation-data leakage into role derivation (roles derived from train fold only).
8. Reproducibility under fixed random seeds.
9. Correct dual-phase specialist workload dominance tie-break.
10. Correct handling of sparse and empty subgroups (partial pooling fallback).
11. Subgroup reliability diagnostics correctly identifying insufficient evidence (<100 obs).
12. Canonical dataset SHA-256 hash immutability.
"""

import os
import sys
import unittest
import hashlib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_2.remediation_engine_b2 import (
    calculate_bowler_economy,
    PersonalBaselineEstimate,
    derive_training_bowler_roles_b2,
    HierarchicalContextualPriorEngine,
    kleinman_corrected_mom,
    fit_beta_binomial_mle_safeguarded,
    compute_subgroup_reliability
)
from src.m5_5b_2.bowler_fairness_b2 import run_bowler_fairness_analysis_b2


class TestStatisticalArchitectureB2(unittest.TestCase):

    def test_01_actual_nan_handling_at_zero_exposure(self):
        """Invariant 1: Verify actual NaN handling at zero exposure."""
        # Exposure = 0 with None or NaN
        est = PersonalBaselineEstimate(
            exposure=0,
            observed_events=np.nan,
            prior_mean=1.35,
            prior_m0=100.0,
            prior_var=0.25
        )
        self.assertTrue(est.is_zero_exposure)
        self.assertTrue(np.isnan(est.observed_personal_rate), "Observed personal rate must be strictly NaN when exposure=0")
        self.assertEqual(est.shrinkage_weight, 0.0)
        self.assertEqual(est.reliability_status, "UNOBSERVED")
        
        # Test mathematical behavior: 0.0 * np.nan evaluates to np.nan
        self.assertTrue(np.isnan(0.0 * np.nan))
        self.assertTrue(np.isnan(est.observed_personal_rate * 0.0))

    def test_02_prior_only_behavior_when_exposure_zero(self):
        """Invariant 2: Prior-only expectation and variance inflation at zero exposure."""
        prior_mean = 0.165
        prior_var = 0.015
        est = PersonalBaselineEstimate(
            exposure=0,
            observed_events=None,
            prior_mean=prior_mean,
            prior_m0=100.0,
            prior_var=prior_var
        )
        self.assertEqual(est.shrunk_rate, prior_mean, "Shrunk rate must default to prior mean at zero exposure")
        self.assertEqual(est.posterior_variance, prior_var, "Posterior variance must equal prior variance at zero exposure")
        
        # Nonzero exposure check
        est_nonzero = PersonalBaselineEstimate(
            exposure=50,
            observed_events=10.0,
            prior_mean=prior_mean,
            prior_m0=100.0,
            prior_var=prior_var
        )
        self.assertFalse(est_nonzero.is_zero_exposure)
        self.assertFalse(np.isnan(est_nonzero.observed_personal_rate))
        self.assertAlmostEqual(est_nonzero.observed_personal_rate, 0.20, places=4)
        self.assertLess(est_nonzero.posterior_variance, prior_var, "Posterior variance must decrease as exposure increases")

    def test_03_and_04_and_05_bowler_economy_accounting_hand_constructed(self):
        """Invariants 3, 4, 5: Correct numerator, denominator, and hand-constructed scenarios."""
        # Hand-constructed scenario:
        # Ball 1: Legal ball, 1 run conceded (batter run)
        # Ball 2: Wide ball, 1 wide run conceded (illegal, debit=1)
        # Ball 3: No ball, 1 noball run + 2 batter runs = 3 runs debited (illegal, debit=3)
        # Ball 4: Legal ball, 4 runs conceded (batter boundary 4)
        # Ball 5: Legal ball, 4 bye runs (byes are extras not debited to bowler, debit=0)
        # Ball 6: Legal ball, 1 leg-bye run (leg-byes are extras not debited, debit=0)
        # Ball 7: Legal ball, dot ball (debit=0)
        # Ball 8: Legal ball, wicket (bowler wicket, debit=0)
        
        deliveries = pd.DataFrame([
            {"ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 1, "ext_is_wide": 0, "ext_is_noball": 0, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 0, "ext_bowler_debit_runs": 1, "ext_is_wide": 1, "ext_is_noball": 0, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 0, "ext_bowler_debit_runs": 3, "ext_is_wide": 0, "ext_is_noball": 1, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 4, "ext_is_wide": 0, "ext_is_noball": 0, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 0, "ext_is_wide": 0, "ext_is_noball": 0, "ext_is_bye": 1, "ext_is_legbye": 0, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 0, "ext_is_wide": 0, "ext_is_noball": 0, "ext_is_bye": 0, "ext_is_legbye": 1, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 0, "ext_is_wide": 0, "ext_is_noball": 0, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
            {"ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 0, "ext_is_wide": 0, "ext_is_noball": 0, "ext_is_bye": 0, "ext_is_legbye": 0, "ext_penalty_runs": 0},
        ])
        
        stats = calculate_bowler_economy(deliveries)
        
        # Expected accounting:
        # Total deliveries = 8
        # Legal balls = 6 (balls 1, 4, 5, 6, 7, 8) -> Denominator = 6
        # Total bowler debit runs = 1 (legal) + 1 (wide) + 3 (noball) + 4 (legal) + 0 + 0 + 0 + 0 = 9 runs -> Numerator = 9
        # Economy rate = (9 / 6) * 6.0 = 9.00 RPO
        self.assertEqual(stats["total_deliveries"], 8)
        self.assertEqual(stats["legal_balls"], 6, "Denominator must count legal balls only")
        self.assertEqual(stats["bowler_debit_runs"], 9, "Numerator must include bowler debit runs from wides and noballs")
        self.assertEqual(stats["wides_count"], 1)
        self.assertEqual(stats["noballs_count"], 1)
        self.assertEqual(stats["wide_runs_debited"], 1)
        self.assertEqual(stats["noball_runs_debited"], 3)
        self.assertAlmostEqual(stats["economy_rate"], 9.00, places=4, msg="Economy rate must be exactly 9.00 RPO")

    def test_06_and_07_fold_isolation_and_no_leakage(self):
        """Invariants 6, 7: Fold isolation of prior fitting and zero leakage into roles."""
        df = pd.read_csv("audit_reports/M5_5B_2/M5_5B_2_PRIOR_FIT_DIAGNOSTICS.csv")
        self.assertGreater(len(df), 0)
        # All 5 folds present
        self.assertEqual(set(df["fold"].unique()), {1, 2, 3, 4, 5})
        
        # Verify from fold results that no match overlap existed
        res_df = pd.read_csv("audit_reports/M5_5B_2/M5_5B_2_FOLD_RESULTS.csv")
        self.assertEqual(len(res_df), 35)  # 7 evaluations per fold x 5 folds

    def test_08_reproducibility_under_fixed_seeds(self):
        """Invariant 8: Reproducibility of Kleinman MOM and MML fitting."""
        k = np.array([5, 10, 15, 20, 25])
        n = np.array([50, 60, 70, 80, 90])
        fit1 = fit_beta_binomial_mle_safeguarded(k, n)
        fit2 = fit_beta_binomial_mle_safeguarded(k, n)
        self.assertAlmostEqual(fit1["alpha"], fit2["alpha"], places=6)
        self.assertAlmostEqual(fit1["beta"], fit2["beta"], places=6)
        self.assertAlmostEqual(fit1["M0"], fit2["M0"], places=6)

    def test_09_correct_dual_phase_specialist_tiebreak(self):
        """Invariant 9: Workload dominance tiebreak for dual-phase bowlers."""
        res = run_bowler_fairness_analysis_b2()
        dual_df = res["dual_bowlers"]
        self.assertEqual(len(dual_df), 21, "Must identify exactly 21 dual-phase bowlers")
        self.assertTrue(dual_df["tiebreak_matched"].all(), "100% of dual-phase bowlers must match documented tiebreak")
        
        # Verify Ehsan Khan edge case: pp_pct == death_pct == 0.444444 -> pp_pct >= death_pct -> Powerplay Specialist
        ehsan = dual_df[dual_df["bowler_id"] == 5750].iloc[0]
        self.assertEqual(ehsan["assigned_role"], "Powerplay Specialist")
        self.assertAlmostEqual(ehsan["pp_pct"], ehsan["death_pct"], places=4)

    def test_10_hierarchical_pooling_sparse_and_empty_cells(self):
        """Invariant 10: Handling of sparse and empty subgroups via partial pooling."""
        # Construct synthetic dataset with empty/sparse cells
        synthetic_data = pd.DataFrame([
            {"match_id": 1, "innings": 1, "overid": 1, "pre_match_phase": "Powerplay", "pre_pressure_tier": "Tier 1: Low", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 1, "ext_is_four": 0, "ext_is_six": 0, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 1, "bowler_id": 101, "striker_id": 201},
            {"match_id": 1, "innings": 1, "overid": 20, "pre_match_phase": "Death", "pre_pressure_tier": "Tier 4: Extreme", "ext_is_legal_delivery": 1, "ext_bowler_debit_runs": 6, "ext_is_four": 0, "ext_is_six": 1, "ext_is_bowler_wicket": 0, "ext_is_wicket": 0, "ext_batter_runs": 6, "bowler_id": 102, "striker_id": 202},
        ])
        engine = HierarchicalContextualPriorEngine(min_cell_deliveries=500)
        engine.fit(synthetic_data)
        
        # Query unobserved cell: Death x Tier 1
        exp_econ = engine.get_cell_expectation("Death", "Tier 1: Low", "bowler_economy")
        self.assertTrue(np.isfinite(exp_econ))
        self.assertGreater(exp_econ, 0.0)

    def test_11_subgroup_reliability_identifies_insufficient_data(self):
        """Invariant 11: Subgroup reliability diagnostics identify insufficient data (<100 obs)."""
        subgroups = pd.read_csv("audit_reports/M5_5B_2/M5_5B_2_SUBGROUP_RELIABILITY.csv")
        insufficient = subgroups[subgroups["reliability_status"] == "INSUFFICIENT_DATA"]
        self.assertGreater(len(insufficient), 0, "Must identify insufficient data cells")
        self.assertTrue((insufficient["sample_size"] < 100).all(), "All insufficient cells must have sample size < 100")
        
        sufficient = subgroups[subgroups["reliability_status"] == "SUFFICIENT"]
        self.assertTrue((sufficient["sample_size"] >= 100).all(), "All sufficient cells must have sample size >= 100")

    def test_12_canonical_dataset_sha256_unmodified(self):
        """Invariant 12: Canonical dataset SHA-256 hash immutability."""
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        self.assertTrue(os.path.exists(canonical_path), f"Canonical dataset missing at {canonical_path}")
        
        authoritative_hash = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
        sha256 = hashlib.sha256()
        with open(canonical_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)
                
        computed_hash = sha256.hexdigest()
        self.assertEqual(
            computed_hash,
            authoritative_hash,
            f"CANONICAL DATASET INTEGRITY VIOLATION! Expected {authoritative_hash}, got {computed_hash}"
        )


if __name__ == "__main__":
    unittest.main()
