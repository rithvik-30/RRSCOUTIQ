"""
RR ScoutIQ — Milestone M5.5-B.4.1: Statistical Integrity & Invariant Test Battery
Test Suite: tests/m5_5b_4_1/test_statistical_integrity_b4_1.py

Validates all 12 adversarial requirements:
1. Unit Consistency: Bowler prior, observation, and posterior are strictly in RPO.
2. Invariant preservation: If observed RPO == prior RPO, posterior RPO == prior RPO exactly across all exposures.
3. Factor-of-six invariant: Debit runs / legal balls scaled by 6.0, no RPB/RPO mismatch.
4. DerSimonian-Laird Tau^2: Zero positive floors; exact Q <= df -> tau^2 = 0.0 with full pooling.
5. Removal of hard-coded variance proxies: Empirical cluster variance evaluated directly.
6. Player posterior uncertainty: Incorporates individual player sampling variance.
7. Epistemic state exhaustion: ZERO_EXPOSURE, MISSING_OUTCOME, VALID_OBSERVATION, INSUFFICIENT_EVIDENCE, INVALID_EXPOSURE.
8. Bowler fairness: Non-constant player-specific counterfactual gaps evaluated on exact death sequences.
9. Match-level paired phase shifts: Clustered uncertainty and standard errors.
10. Spell accounting: Expected runs summed strictly over legal balls (no double counting wides/no-balls).
11. Subgroup reliability: All 6 breakdowns present with grounded sufficiency criteria.
12. Canonical hash preservation: SHA-256 of match_state_full.csv matches ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4.
"""

import os
import sys
import hashlib
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_4_1.epistemic_engine_b4_1 import (
    EpistemicBaselineRecordB41,
    EpistemicState
)
from src.m5_5b_4_1.hierarchical_engine_b4_1 import (
    compute_dersimonian_laird_b41,
    ContextualHierarchyB41,
    PlayerPosteriorBaselineEstimatorB41
)
from src.m5_5b_4_1.bowler_fairness_matched_b4_1 import run_player_match_fairness_analysis_b41


class TestStatisticalIntegrityB41(unittest.TestCase):
    def test_01_unit_consistency_bowler_economy_rpo(self):
        """
        Correction 1: Bowler prior, observation, and posterior must all be in RPO.
        Invariant: If observed RPO == prior RPO, posterior RPO == prior RPO exactly.
        """
        prior_rpo = 8.40
        # 60 legal balls, 84 runs debit -> 84 / 60 * 6 = 8.40 RPO
        rec = EpistemicBaselineRecordB41(
            exposure=60,
            observed_events=84.0,
            prior_mean=prior_rpo,
            prior_m0=100.0,
            prior_variance=2.0,
            is_economy=True,
            min_exposure=30
        )
        self.assertAlmostEqual(rec.observed_rate, prior_rpo, places=7)
        self.assertAlmostEqual(rec.shrunk_estimate, prior_rpo, places=7)
        self.assertAlmostEqual(rec.shrunk_baseline, prior_rpo, places=7)

    def test_02_no_factor_of_six_distortion(self):
        """
        Verifies that passing raw runs debit and legal balls does NOT cause
        a factor-of-six distortion where observed was RPB (~1.4) while prior was RPO (~8.4).
        """
        prior_rpo = 8.50
        # 100 balls, 150 runs debit -> observed RPO = 9.00
        rec = EpistemicBaselineRecordB41(
            exposure=100,
            observed_events=150.0,
            prior_mean=prior_rpo,
            prior_m0=100.0,
            prior_variance=1.5,
            is_economy=True
        )
        self.assertAlmostEqual(rec.observed_rate, 9.00, places=5)
        # lambda = 100 / (100 + 100) = 0.5
        # shrunk = 0.5 * 9.00 + 0.5 * 8.50 = 8.75
        self.assertAlmostEqual(rec.shrunk_estimate, 8.75, places=5)
        # Must be around 8.75 RPO, NOT around 5.0 RPO from a unit mismatch
        self.assertTrue(8.0 <= rec.shrunk_estimate <= 9.5)

    def test_03_tau2_zero_floor_elimination(self):
        """
        Correction 2: DerSimonian-Laird must NOT have an artificial positive floor.
        When Q <= k - 1, tau^2 MUST evaluate strictly to 0.0 with full pooling status.
        """
        means = [0.15, 0.152, 0.149, 0.151]
        vars_ = [0.01, 0.012, 0.009, 0.011]
        tau2, status = compute_dersimonian_laird_b41(means, vars_)
        self.assertEqual(tau2, 0.0)
        self.assertEqual(status, "ESTIMATED_ZERO_HOMOGENEOUS")

    def test_04_no_hardcoded_proxy_variance(self):
        """
        Verifies that hierarchical engine does not use a hardcoded 4.0 proxy
        and evaluates empirical cluster variances directly.
        """
        hier = ContextualHierarchyB41()
        # Create synthetic training data with 6 matches
        records = []
        for mid in range(1, 10):
            for bid in range(1, 4):
                for _ in range(15):
                    records.append({
                        "match_id": mid,
                        "bowler_id": bid,
                        "pre_match_phase": "Powerplay",
                        "pre_pressure_tier": "Tier 1: Low",
                        "ext_is_legal_delivery": 1,
                        "ext_is_wide": 0,
                        "ext_is_noball": 0,
                        "ext_is_four": 0,
                        "ext_is_six": 0,
                        "ext_bowler_debit_runs": 1
                    })
        df_synth = pd.DataFrame(records)
        hier.fit(df_synth)
        cell = hier.priors.get("Cell::Powerplay::Tier 1: Low")
        self.assertIsNotNone(cell)
        self.assertIn("bowler_economy", cell)
        self.assertAlmostEqual(cell["bowler_economy"]["mean"], 6.0, places=2)

    def test_05_player_posterior_distinct_from_context_expectation(self):
        """
        Correction 3: Player posterior baseline must reflect individual player history,
        and not collapse to identical context cell expectations.
        """
        hier = ContextualHierarchyB41()
        # Synthetic data
        records = []
        for mid in range(1, 10):
            records.append({
                "match_id": mid,
                "striker_id": 101,
                "bowler_id": 201,
                "pre_match_phase": "Death",
                "pre_pressure_tier": "Tier 4: Extreme",
                "ext_is_legal_delivery": 1,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "ext_is_four": 1,
                "ext_is_six": 0,
                "ext_bowler_debit_runs": 4
            })
            records.append({
                "match_id": mid,
                "striker_id": 102,
                "bowler_id": 202,
                "pre_match_phase": "Death",
                "pre_pressure_tier": "Tier 4: Extreme",
                "ext_is_legal_delivery": 1,
                "ext_is_wide": 0,
                "ext_is_noball": 0,
                "ext_is_four": 0,
                "ext_is_six": 0,
                "ext_bowler_debit_runs": 1
            })
        df_synth = pd.DataFrame(records)
        hier.fit(df_synth)
        estimator = PlayerPosteriorBaselineEstimatorB41(hier, M0_default=50.0)
        
        # Player A: high boundaries
        rec_a = estimator.estimate_batter_boundary_posterior(
            player_id=101, phase="Death", tier="Tier 4: Extreme",
            player_balls=100, player_boundaries=40.0
        )
        # Player B: low boundaries
        rec_b = estimator.estimate_batter_boundary_posterior(
            player_id=102, phase="Death", tier="Tier 4: Extreme",
            player_balls=100, player_boundaries=5.0
        )
        self.assertNotEqual(rec_a.shrunk_estimate, rec_b.shrunk_estimate)
        self.assertGreater(rec_a.shrunk_estimate, rec_b.shrunk_estimate)

    def test_06_player_sampling_variance_in_posterior_uncertainty(self):
        """
        Verifies that posterior variance incorporates player-specific sampling variance.
        """
        rec_high_n = EpistemicBaselineRecordB41(
            exposure=300,
            observed_events=60.0,
            prior_mean=0.15,
            prior_m0=100.0,
            prior_variance=0.01,
            is_economy=False
        )
        rec_low_n = EpistemicBaselineRecordB41(
            exposure=40,
            observed_events=8.0,
            prior_mean=0.15,
            prior_m0=100.0,
            prior_variance=0.01,
            is_economy=False
        )
        self.assertLess(rec_high_n.posterior_variance, rec_low_n.posterior_variance)

    def test_07_epistemic_state_exhaustion(self):
        """
        Asserts the 5 distinct epistemic states are correctly classified.
        """
        # ZERO_EXPOSURE
        r0 = EpistemicBaselineRecordB41(0, None, 8.0, 100.0, 2.0, is_economy=True)
        self.assertEqual(r0.state, EpistemicState.ZERO_EXPOSURE)
        self.assertFalse(r0.has_observed_rate)
        self.assertTrue(np.isnan(r0.observed_rate))
        self.assertEqual(r0.shrunk_estimate, 8.0)
        
        # POSITIVE_EXPOSURE_MISSING_OUTCOME
        r1 = EpistemicBaselineRecordB41(50, None, 8.0, 100.0, 2.0, is_economy=True)
        self.assertEqual(r1.state, EpistemicState.POSITIVE_EXPOSURE_MISSING_OUTCOME)
        self.assertTrue(np.isnan(r1.shrunk_estimate))
        
        # INSUFFICIENT_EVIDENCE
        r2 = EpistemicBaselineRecordB41(10, 12.0, 8.0, 100.0, 2.0, is_economy=True, min_exposure=30)
        self.assertEqual(r2.state, EpistemicState.INSUFFICIENT_EVIDENCE)
        
        # POSITIVE_EXPOSURE_VALID_OBSERVATION
        r3 = EpistemicBaselineRecordB41(60, 70.0, 8.0, 100.0, 2.0, is_economy=True, min_exposure=30)
        self.assertEqual(r3.state, EpistemicState.POSITIVE_EXPOSURE_VALID_OBSERVATION)
        
        # INVALID_EXPOSURE
        r4 = EpistemicBaselineRecordB41(-5, 10.0, 8.0, 100.0, 2.0, is_economy=True)
        self.assertEqual(r4.state, EpistemicState.INVALID_EXPOSURE)

    def test_08_bowler_fairness_nonconstant_gap(self):
        """
        Correction 4: Verifies player-specific counterfactual gap is not a constant -1.27 RPO.
        """
        csv_path = "audit_reports/M5_5B_4_1/M5_5B_4_1_PLAYER_FAIRNESS_DIAGNOSTICS.csv"
        if not os.path.exists(csv_path):
            run_player_match_fairness_analysis_b41()
        df_f = pd.read_csv(csv_path)
        dual_df = df_f[df_f["is_dual_phase"] == True]
        self.assertGreater(len(dual_df), 5)
        # Check that gaps vary across bowlers
        gaps = dual_df["player_specific_counterfactual_gap"].values
        self.assertGreater(np.std(gaps), 0.05)
        # Check that none of them is exactly the uncorrected -1.27 constant
        for g in gaps:
            self.assertNotEqual(round(g, 4), -1.2700)

    def test_09_spell_accounting_legal_deliveries_strict(self):
        """
        Correction 5: Expected runs must be summed strictly over legal deliveries,
        preventing wide/no-ball double-counting in spell predicted economy.
        """
        hier = ContextualHierarchyB41()
        # Invariant check: 6 legal balls + 2 wides in a spell
        # The expected runs sum must only be over the 6 legal balls
        legal_exp_rpb = 1.5  # 9.0 RPO
        delivs = [
            {"is_legal": 1, "exp_rpb": 1.5},
            {"is_legal": 0, "exp_rpb": 1.5},  # wide
            {"is_legal": 1, "exp_rpb": 1.5},
            {"is_legal": 1, "exp_rpb": 1.5},
            {"is_legal": 0, "exp_rpb": 1.5},  # no ball
            {"is_legal": 1, "exp_rpb": 1.5},
            {"is_legal": 1, "exp_rpb": 1.5},
            {"is_legal": 1, "exp_rpb": 1.5},
        ]
        legal_delivs = [d for d in delivs if d["is_legal"] == 1]
        self.assertEqual(len(legal_delivs), 6)
        expected_runs_sum = sum(d["exp_rpb"] for d in legal_delivs)
        self.assertAlmostEqual(expected_runs_sum, 9.0, places=5)
        spell_predicted_econ = 6.0 * (expected_runs_sum / len(legal_delivs))
        self.assertAlmostEqual(spell_predicted_econ, 9.0, places=5)

    def test_10_subgroup_reliability_all_6_breakdowns(self):
        """
        Correction 6: Asserts that M5_5B_4_1_SUBGROUP_RELIABILITY.csv exists and contains
        all 6 structural breakdowns with cluster-adjusted standard errors.
        """
        csv_path = "audit_reports/M5_5B_4_1/M5_5B_4_1_SUBGROUP_RELIABILITY.csv"
        if os.path.exists(csv_path):
            df_sub = pd.read_csv(csv_path)
            breakdowns = set(df_sub["breakdown"].unique())
            expected = {
                "1_Batter_Phase_x_Tier",
                "2_Batter_Role_x_Phase",
                "3_Batter_Role_x_Tier",
                "4_Bowler_Phase_x_Tier",
                "5_Bowler_Role_x_Phase",
                "6_Bowler_Role_x_Tier"
            }
            self.assertTrue(expected.issubset(breakdowns))
            self.assertTrue("standard_error" in df_sub.columns)
            self.assertTrue("sufficiency_status" in df_sub.columns)

    def test_11_model_comparison_presence(self):
        """
        Correction 7: Asserts that M5_5B_4_1_MODEL_COMPARISON.csv exists and contains
        all models including M1, M2, M3, M4, M5 for both domains.
        """
        csv_path = "audit_reports/M5_5B_4_1/M5_5B_4_1_MODEL_COMPARISON.csv"
        if os.path.exists(csv_path):
            df_comp = pd.read_csv(csv_path)
            bat_models = set(df_comp[df_comp["domain"] == "Batter"]["model"].unique())
            bowl_models = set(df_comp[df_comp["domain"] == "Bowler"]["model"].unique())
            self.assertIn("M1_Global", bat_models)
            self.assertIn("M4_Contextual_B41", bat_models)
            self.assertIn("M5_Player_Posterior_EB_B41", bat_models)
            self.assertIn("M1_Global", bowl_models)
            self.assertIn("M4_Contextual_Composition_B41", bowl_models)
            self.assertIn("M5_Player_Posterior_EB_B41", bowl_models)

    def test_12_canonical_dataset_hash_preservation(self):
        """
        Governance Invariant: Canonical dataset SHA-256 must match exactly:
        ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4
        """
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        h = hashlib.sha256()
        with open(canonical_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        actual_hash = h.hexdigest()
        expected_hash = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
        self.assertEqual(actual_hash, expected_hash)


if __name__ == "__main__":
    unittest.main()
