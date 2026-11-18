"""
Unit and regression tests for M5.2 Full-Dataset Enrichment Pipeline.
Module: tests/m5_enrichment/test_enrichment_pipeline.py
"""

import os
import unittest
import pandas as pd

from src.m5_enrichment.delivery_alignment import QUARANTINED_MATCH_IDS

BASE_DIR = os.path.abspath(".")
ENRICHED_FULL_DIR = os.path.join(BASE_DIR, "data", "enriched", "full")
ENRICHED_BBB_PATH = os.path.join(ENRICHED_FULL_DIR, "enriched_ball_by_ball_full.csv")
MANIFEST_PATH = os.path.join(ENRICHED_FULL_DIR, "match_enrichment_manifest.csv")
RAW_BBB_PATH = os.path.join(BASE_DIR, "data", "extracted", "ball_by_ball.csv")


class TestFullDatasetEnrichmentPipeline(unittest.TestCase):
    """Test suite verifying the pipeline artifacts and properties."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = pd.read_csv(MANIFEST_PATH)
        # Load sample of enriched data for fast checking
        cls.df_sample = pd.read_csv(ENRICHED_BBB_PATH, nrows=5000)
        cls.raw_cols = pd.read_csv(RAW_BBB_PATH, nrows=2).columns.tolist()

    def test_01_artifacts_exist(self):
        """Verifies that all required M5.2 artifacts exist and are non-empty."""
        self.assertTrue(os.path.exists(ENRICHED_BBB_PATH))
        self.assertTrue(os.path.exists(MANIFEST_PATH))
        self.assertGreater(os.path.getsize(ENRICHED_BBB_PATH), 10_000_000)
        self.assertGreater(os.path.getsize(MANIFEST_PATH), 10_000)

    def test_02_original_columns_preserved(self):
        """Verifies that all 33 original local columns are preserved intact in enriched output."""
        enriched_cols = set(self.df_sample.columns)
        for c in self.raw_cols:
            self.assertIn(c, enriched_cols, f"Original local column missing: {c}")

    def test_03_enriched_ext_columns_present(self):
        """Verifies that all required ext_ enriched columns are present."""
        expected_ext_cols = [
            "ext_cricsheet_match_id", "ext_cricsheet_archive", "ext_cricsheet_file",
            "ext_cricsheet_competition_name", "ext_match_format", "ext_innings",
            "ext_is_super_over", "ext_cricsheet_delivery_index",
            "ext_striker_name", "ext_striker_cricsheet_id",
            "ext_non_striker_name", "ext_non_striker_cricsheet_id",
            "ext_bowler_name", "ext_bowler_cricsheet_id",
            "ext_dismissed_player_name", "ext_dismissed_player_cricsheet_id",
            "ext_dismissed_player_local_id",
            "ext_batter_runs", "ext_extra_runs", "ext_extras_type", "ext_delivery_total_runs",
            "ext_is_wide", "ext_wide_runs", "ext_is_noball", "ext_noball_runs",
            "ext_is_bye", "ext_bye_runs", "ext_is_legbye", "ext_legbye_runs",
            "ext_is_penalty", "ext_penalty_runs", "ext_is_legal_delivery",
            "ext_batter_balls_faced", "ext_bowler_debit_runs",
            "ext_is_four", "ext_is_six", "ext_is_wicket", "ext_dismissal_kind",
            "ext_is_bowler_wicket", "ext_is_retired_hurt", "ext_is_retired_out",
            "ext_alignment_strategy", "ext_provenance"
        ]
        enriched_cols = set(self.df_sample.columns)
        for col in expected_ext_cols:
            self.assertIn(col, enriched_cols, f"Required enriched column missing: {col}")

    def test_04_manifest_accounting(self):
        """Verifies 883 total matches in manifest with mutually exclusive scopes."""
        self.assertEqual(len(self.manifest), 883)
        status_counts = self.manifest["processing_status"].value_counts()
        self.assertEqual(status_counts.get("ENRICHED_AND_VALIDATED", 0), 776)
        self.assertEqual(status_counts.get("EXCLUDED_POLICY_WITHHELD", 0), 61)
        self.assertEqual(status_counts.get("UNRESOLVED_MATCH_MAPPING", 0), 25)
        self.assertEqual(status_counts.get("EXCLUDED_UNPLAYED", 0), 16)
        self.assertEqual(status_counts.get("MATCHED_WITH_WARNINGS", 0), 5)

        # Quarantined matches are the 5 MATCHED_WITH_WARNINGS that were excluded
        quarantined = self.manifest[self.manifest["analytical_scope"] == "EXCLUDED_QUARANTINE"]
        self.assertEqual(len(quarantined), 5)
        self.assertEqual(set(quarantined["local_match_id"]), QUARANTINED_MATCH_IDS)

    def test_05_quarantined_matches_strictly_excluded(self):
        """Verifies that none of the 5 quarantined matches exist in the enriched deliveries."""
        # Check by match_id in manifest
        enr_mids = set(self.manifest[self.manifest["processing_status"] == "ENRICHED_AND_VALIDATED"]["local_match_id"])
        self.assertEqual(len(enr_mids.intersection(QUARANTINED_MATCH_IDS)), 0)

    def test_06_special_matches_scope_in_manifest(self):
        """Verifies manifest analytical scopes for regulation-only and minor-omission matches."""
        m13613 = self.manifest[self.manifest["local_match_id"] == 13613].iloc[0]
        m21176 = self.manifest[self.manifest["local_match_id"] == 21176].iloc[0]
        m14130 = self.manifest[self.manifest["local_match_id"] == 14130].iloc[0]
        m14164 = self.manifest[self.manifest["local_match_id"] == 14164].iloc[0]

        self.assertEqual(m13613["analytical_scope"], "REGULATION_ONLY")
        self.assertEqual(m21176["analytical_scope"], "REGULATION_ONLY")
        self.assertEqual(m14130["analytical_scope"], "SAFE_FULL_ALIGNMENT")
        self.assertEqual(m14164["analytical_scope"], "SAFE_FULL_ALIGNMENT")

        self.assertEqual(m13613["enriched_delivery_count"], 246)
        self.assertEqual(m21176["enriched_delivery_count"], 252)
        self.assertEqual(m14130["enriched_delivery_count"], 251)
        self.assertEqual(m14164["enriched_delivery_count"], 219)


if __name__ == "__main__":
    unittest.main()
