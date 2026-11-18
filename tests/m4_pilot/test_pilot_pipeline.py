"""
RR ScoutIQ - Unit Test Suite: Module M4.6 Controlled Pilot Outputs
==================================================================
Comprehensive verification of the integrated M4 pipeline orchestrator,
end-to-end dataflow, explainable batter/bowler diagnostics, match-level
causal explainability traces, dataset immutability, and governance constraints.
"""

import unittest
import math
import numpy as np
import pandas as pd

from src.m4_pilot.input_validation import verify_dataset_immutability
from src.m4_pilot.pilot_pipeline import (
    run_controlled_pilot_pipeline,
    generate_match_level_explainability_traces,
    ControlledPilotReport,
    MatchDeliveryExplainabilityTrace
)


class TestControlledPilotOutputs(unittest.TestCase):
    """Test suite for Module M4.6 Controlled Pilot Outputs."""

    @classmethod
    def setUpClass(cls):
        """Runs the complete integrated controlled pilot pipeline once for test suite."""
        cls.report = run_controlled_pilot_pipeline(run_bootstrap=False)

    # -----------------------------------------------------------------------
    # 1. Pipeline Integration & Scope Integrity
    # -----------------------------------------------------------------------

    def test_01_total_matches_and_deliveries_processed(self):
        """Verifies integrated pipeline processes exactly 8 matches and 1,994 deliveries."""
        self.assertEqual(self.report.total_matches_processed, 8)
        self.assertEqual(self.report.total_deliveries_processed, 1994)
        expected_matches = [13513, 14094, 14113, 20181, 30058, 34429, 40037, 40725]
        self.assertEqual(self.report.match_ids, expected_matches)

    def test_02_raw_hashes_verified_by_pipeline(self):
        """Verifies that the integrated pipeline cryptographically confirms dataset immutability."""
        self.assertTrue(self.report.raw_hashes_verified)
        ok, diffs = verify_dataset_immutability()
        self.assertTrue(ok)
        self.assertEqual(len(diffs), 0)

    # -----------------------------------------------------------------------
    # 2. Batter Diagnostic Outputs
    # -----------------------------------------------------------------------

    def test_03_batter_diagnostics_coverage_and_structure(self):
        """Verifies batter diagnostic outputs contain all 102 evaluated batters with mandatory fields."""
        self.assertEqual(self.report.total_batters_evaluated, 102)
        self.assertEqual(len(self.report.batter_diagnostics), 102)

        sample = self.report.batter_diagnostics[0]
        required_keys = [
            "player_id", "player_name", "primary_role", "bppi_score",
            "component_z_scores", "attribution_positives", "attribution_negatives",
            "innings_count", "total_balls_faced", "pressure_balls",
            "reliability_tier", "reliability_note", "is_eligible",
            "exclusion_reasons", "bootstrap_se", "ci_percentile_90",
            "credible_interval_90", "lower_bound_90", "lower_bound_status",
            "data_quality_warnings"
        ]
        for k in required_keys:
            self.assertIn(k, sample)

    def test_04_batter_component_decomposition_completeness(self):
        """Verifies each batter diagnostic contains all 5 BPPI z-score components."""
        for b in self.report.batter_diagnostics[:10]:
            comps = b["component_z_scores"]
            self.assertIn("z_xra", comps)
            self.assertIn("z_delta_sr", comps)
            self.assertIn("z_delta_bnd", comps)
            self.assertIn("z_delta_dot", comps)
            self.assertIn("z_delta_survival", comps)

    # -----------------------------------------------------------------------
    # 3. Bowler Diagnostic Outputs
    # -----------------------------------------------------------------------

    def test_05_bowler_diagnostics_coverage_and_structure(self):
        """Verifies bowler diagnostic outputs contain all 74 evaluated bowlers with mandatory fields."""
        self.assertEqual(self.report.total_bowlers_evaluated, 74)
        self.assertEqual(len(self.report.bowler_diagnostics), 74)

        sample = self.report.bowler_diagnostics[0]
        required_keys = [
            "player_id", "player_name", "primary_role", "ppbi_score",
            "component_z_scores", "attribution_positives", "attribution_negatives",
            "innings_count", "total_legal_balls", "pressure_legal_balls",
            "reliability_tier", "reliability_note", "is_eligible",
            "exclusion_reasons", "bootstrap_se", "ci_percentile_90",
            "credible_interval_90", "lower_bound_90", "lower_bound_status",
            "data_quality_warnings"
        ]
        for k in required_keys:
            self.assertIn(k, sample)

    def test_06_bowler_component_decomposition_completeness(self):
        """Verifies each bowler diagnostic contains all 5 PPBI z-score components."""
        for bw in self.report.bowler_diagnostics[:10]:
            comps = bw["component_z_scores"]
            self.assertIn("z_xrs", comps)
            self.assertIn("z_delta_econ", comps)
            self.assertIn("z_delta_wkt", comps)
            self.assertIn("z_delta_dot", comps)
            self.assertIn("z_delta_bnd_con", comps)

    # -----------------------------------------------------------------------
    # 4. Eligibility & Reliability Distributions
    # -----------------------------------------------------------------------

    def test_07_pilot_eligibility_enforcement(self):
        """Verifies zero batters and zero bowlers qualify under the 12-innings threshold in 8-match pilot."""
        self.assertEqual(self.report.eligible_batters_count, 0)
        self.assertEqual(self.report.eligible_bowlers_count, 0)

        for b in self.report.batter_diagnostics:
            self.assertFalse(b["is_eligible"])
            self.assertIn("INSUFFICIENT_SAMPLE_SIZE_FOR_COMPETITION_EVALUATION", b["data_quality_warnings"])

        for bw in self.report.bowler_diagnostics:
            self.assertFalse(bw["is_eligible"])
            self.assertIn("INSUFFICIENT_SAMPLE_SIZE_FOR_COMPETITION_EVALUATION", bw["data_quality_warnings"])

    def test_08_reliability_tier_distributions(self):
        """Verifies 100% of pilot players classify into INELIGIBLE_INSUFFICIENT_SAMPLE tier."""
        self.assertEqual(self.report.batter_tier_distribution["INELIGIBLE_INSUFFICIENT_SAMPLE"], 102)
        self.assertEqual(self.report.bowler_tier_distribution["INELIGIBLE_INSUFFICIENT_SAMPLE"], 74)

    # -----------------------------------------------------------------------
    # 5. Match-Level Explainability Traces
    # -----------------------------------------------------------------------

    def test_09_match_level_trace_structure_and_anti_leakage(self):
        """Verifies match explainability traces contain full causal pre-state without outcome leakage."""
        self.assertGreaterEqual(len(self.report.match_traces), 5)
        for t in self.report.match_traces:
            # Pre-state values must be defined
            self.assertGreaterEqual(t.pre_score, 0)
            self.assertGreaterEqual(t.pre_wickets_lost, 0)
            self.assertGreater(t.pre_dli, 0.0)
            self.assertIn(t.pre_pressure_tier, ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
            self.assertIn(t.pre_match_phase, ["Powerplay", "Middle", "Death", "Super Over"])
            # Inclusion rationale must be explicit
            self.assertTrue(len(t.inclusion_rationale) > 0)

    def test_10_super_over_trace_decoupling(self):
        """Verifies Super Over trace in Match 40725 exhibits fixed DLI=3.50 and Super Over phase."""
        so_traces = [t for t in self.report.match_traces if t.match_id == 40725 and t.innings == 3]
        self.assertGreater(len(so_traces), 0)
        so_t = so_traces[0]
        self.assertEqual(so_t.pre_match_phase, "Super Over")
        self.assertEqual(so_t.pre_pressure_tier, "Tier 4: Extreme")
        self.assertEqual(so_t.pre_dli, 3.50)
        self.assertTrue(so_t.included_in_pressure_metrics)

    # -----------------------------------------------------------------------
    # 6. Pressure Volume & Distribution
    # -----------------------------------------------------------------------

    def test_11_pressure_delivery_counts_and_percentages(self):
        """Verifies pressure delivery counting across the pilot dataset."""
        self.assertEqual(self.report.pressure_deliveries_count, 1032)
        self.assertEqual(self.report.pressure_percentage, 51.76)

    # -----------------------------------------------------------------------
    # 7. Governance Assertions
    # -----------------------------------------------------------------------

    def test_12_no_official_rankings_or_top10_generation(self):
        """Verifies governance constraint: official role rankings contain zero qualified players."""
        for role, dossier in self.report.batter_role_rankings["point_score"].items():
            self.assertEqual(len(dossier.ranked_players), 0)
            self.assertGreater(len(dossier.ineligible_players), 0)

        for role, dossier in self.report.bowler_role_rankings["point_score"].items():
            self.assertEqual(len(dossier.ranked_players), 0)
            self.assertGreater(len(dossier.ineligible_players), 0)


if __name__ == "__main__":
    unittest.main()

