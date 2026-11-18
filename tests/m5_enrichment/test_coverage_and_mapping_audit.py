"""
RR ScoutIQ — Milestone M5.1 Unit & Conformance Test Battery
Module: tests/m5_enrichment/test_coverage_and_mapping_audit.py

Verifies:
1. Complete accounting of all 883 matches into mutually exclusive categories.
2. Exact delivery count conservation: local deliveries sum to 200,999.
3. Proper handling of all 16 unplayed abandoned matches (0 local deliveries).
4. Proper classification of 61 Afghanistan policy-withheld matches.
5. High player mapping resolution rate with deterministic crosswalks.
6. Bitwise immutability of raw datasets and source archives.
"""

import os
import unittest
import pandas as pd

from src.m5_enrichment.coverage_and_mapping_audit import (
    FullDatasetCoverageAudit,
    run_full_dataset_coverage_audit
)
from src.m4_pilot.input_validation import verify_dataset_immutability


class TestFullDatasetCoverageAudit(unittest.TestCase):
    """Test battery for M5.1 coverage and mapping audit."""

    @classmethod
    def setUpClass(cls):
        cls.match_df, cls.player_df, cls.stats = run_full_dataset_coverage_audit()

    def test_01_total_match_accounting(self):
        """Verifies that all 883 matches in the dataset are accounted for."""
        self.assertEqual(len(self.match_df), 883)
        self.assertEqual(self.stats["total_matches"], 883)

    def test_02_mutually_exclusive_status_partitioning(self):
        """Verifies that every match receives exactly one approved status."""
        valid_statuses = {
            "MATCHED_AND_VALIDATED",
            "MATCHED_WITH_WARNINGS",
            "EXCLUDED_POLICY_WITHHELD",
            "EXCLUDED_UNPLAYED",
            "EXCLUDED_UNSUPPORTED_FORMAT",
            "UNRESOLVED_MATCH_MAPPING",
            "UNRESOLVED_PLAYER_MAPPING",
            "PROCESSING_FAILED"
        }
        actual_statuses = set(self.match_df["processing_status"].unique())
        self.assertTrue(actual_statuses.issubset(valid_statuses))
        self.assertFalse(self.match_df["processing_status"].isnull().any())

    def test_03_expected_category_counts(self):
        """Verifies the audited category breakdown matches documented expectations."""
        counts = self.stats["status_counts"]
        self.assertEqual(counts.get("MATCHED_AND_VALIDATED", 0), 772)
        self.assertEqual(counts.get("MATCHED_WITH_WARNINGS", 0), 9)
        self.assertEqual(counts.get("EXCLUDED_UNPLAYED", 0), 16)
        self.assertEqual(counts.get("EXCLUDED_POLICY_WITHHELD", 0), 61)
        self.assertEqual(counts.get("UNRESOLVED_MATCH_MAPPING", 0), 25)
        self.assertEqual(sum(counts.values()), 883)

    def test_04_delivery_conservation(self):
        """Verifies that local delivery counts conserve all 200,999 deliveries in ball_by_ball.csv."""
        total_deliveries = self.match_df["local_delivery_count"].sum()
        self.assertEqual(total_deliveries, 200999)
        self.assertEqual(self.stats["total_local_deliveries"], 200999)

        # Breakdown checks
        del_by_status = self.stats["deliveries_by_status"]
        self.assertEqual(del_by_status["MATCHED_AND_VALIDATED"], 178869)
        self.assertEqual(del_by_status["MATCHED_WITH_WARNINGS"], 2169)
        self.assertEqual(del_by_status["EXCLUDED_UNPLAYED"], 0)
        self.assertEqual(del_by_status["EXCLUDED_POLICY_WITHHELD"], 14311)
        self.assertEqual(del_by_status["UNRESOLVED_MATCH_MAPPING"], 5650)

    def test_05_unplayed_matches_zero_deliveries(self):
        """Verifies that all 16 EXCLUDED_UNPLAYED matches have exactly 0 local deliveries."""
        unplayed = self.match_df[self.match_df["processing_status"] == "EXCLUDED_UNPLAYED"]
        self.assertEqual(len(unplayed), 16)
        self.assertTrue((unplayed["local_delivery_count"] == 0).all())

    def test_06_afghanistan_policy_withheld_matches(self):
        """Verifies that all 61 policy-withheld matches involve Afghanistan."""
        afg = self.match_df[self.match_df["processing_status"] == "EXCLUDED_POLICY_WITHHELD"]
        self.assertEqual(len(afg), 61)
        for _, row in afg.iterrows():
            teams_str = f"{row['home_team']} {row['away_team']}"
            self.assertIn("Afghanistan", teams_str)

    def test_07_player_mapping_resolution_rate(self):
        """Verifies player crosswalk resolves active players with high coverage."""
        active_resolved = self.stats["active_players_resolved"]
        active_total = self.stats["active_players_count"]
        coverage_pct = self.stats["active_players_coverage_pct"]

        # Expect >= 85% resolution among all active players across covered fixtures
        self.assertGreaterEqual(coverage_pct, 85.0)
        self.assertEqual(active_total, 958)

        # Check players with significant sample (>= 30 balls involved)
        high_sample = self.player_df[self.player_df["sample_balls_involved"] >= 30]
        high_sample_resolved = len(high_sample[high_sample["status"] == "RESOLVED"])
        high_sample_pct = high_sample_resolved / len(high_sample) * 100.0
        self.assertGreaterEqual(high_sample_pct, 90.0)

    def test_08_dataset_immutability(self):
        """Verifies that raw source archive and extracted CSVs remain bitwise immutable."""
        passed, issues = verify_dataset_immutability()
        self.assertTrue(passed, f"Dataset immutability failure: {issues}")
        self.assertEqual(len(issues), 0)

    def test_09_warning_match_dispositions(self):
        """Verifies explicit M5.1.1 forensic warning dispositions."""
        warn_df = self.match_df[self.match_df["processing_status"] == "MATCHED_WITH_WARNINGS"].set_index("local_match_id")
        self.assertEqual(len(warn_df), 9)

        # 1. Regulation only (Super Over omitted in local feed)
        self.assertEqual(warn_df.loc[13613, "warning_disposition"], "SAFE_REGULATION_ONLY")
        self.assertEqual(warn_df.loc[21176, "warning_disposition"], "SAFE_REGULATION_ONLY")

        # 2. Minor local omissions (IPL 2022)
        self.assertEqual(warn_df.loc[14130, "warning_disposition"], "SAFE_MINOR_OMISSION")
        self.assertEqual(warn_df.loc[14164, "warning_disposition"], "SAFE_MINOR_OMISSION")

        # 3. Quarantined incompatible matches
        for q_mid in [32618, 37349, 37352, 46250, 50504]:
            self.assertEqual(warn_df.loc[q_mid, "warning_disposition"], "QUARANTINED_INCOMPATIBLE")

    def test_10_validated_matches_zero_unresolved_players(self):
        """Verifies that all active players in the 772 validated matches are 100% resolved."""
        bbb_chunks = []
        for c in pd.read_csv("data/extracted/ball_by_ball.csv", usecols=["match_id", "striker_id", "bowler_id"], chunksize=50000):
            bbb_chunks.append(c)
        bbb = pd.concat(bbb_chunks, ignore_index=True)

        mids_772 = set(self.match_df[self.match_df["processing_status"] == "MATCHED_AND_VALIDATED"]["local_match_id"])
        bbb_772 = bbb[bbb["match_id"].isin(mids_772)]
        active_772 = set(bbb_772["striker_id"]).union(set(bbb_772["bowler_id"]))

        resolved_pids = set(self.player_df[self.player_df["status"] == "RESOLVED"]["local_player_id"])
        unresolved_772 = active_772 - resolved_pids

        self.assertEqual(len(active_772), 851)
        self.assertEqual(len(unresolved_772), 0, f"Unresolved active players found in 772 validated matches: {unresolved_772}")

    def test_11_eligible_delivery_accounting(self):
        """Verifies exact delivery accounting calculated dynamically from match audit CSV."""
        val_df = self.match_df[self.match_df["processing_status"] == "MATCHED_AND_VALIDATED"]
        self.assertEqual(len(val_df), 772)
        val_deliveries = int(val_df["local_delivery_count"].sum())
        self.assertEqual(val_deliveries, 178869)

        safe_warn_df = self.match_df[
            (self.match_df["processing_status"] == "MATCHED_WITH_WARNINGS") &
            (self.match_df["warning_disposition"].isin(["SAFE_REGULATION_ONLY", "SAFE_MINOR_OMISSION"]))
        ]
        self.assertEqual(len(safe_warn_df), 4)
        safe_warn_deliveries = int(safe_warn_df["local_delivery_count"].sum())
        self.assertEqual(safe_warn_deliveries, 968)

        # Dynamic sum verification
        total_eligible_matches = len(val_df) + len(safe_warn_df)
        total_eligible_deliveries = val_deliveries + safe_warn_deliveries
        self.assertEqual(total_eligible_matches, 776)
        self.assertEqual(total_eligible_deliveries, 179837)

        # Quarantined matches must be strictly excluded
        quarantine_df = self.match_df[self.match_df["warning_disposition"] == "QUARANTINED_INCOMPATIBLE"]
        self.assertEqual(len(quarantine_df), 5)
        quarantine_mids = set(quarantine_df["local_match_id"])
        self.assertEqual(quarantine_mids, {32618, 37349, 37352, 46250, 50504})
        self.assertFalse(quarantine_mids.intersection(set(safe_warn_df["local_match_id"])))

    def test_12_conditional_alignment_and_player_aliases(self):
        """Verifies conditional alignment parameters and player identity disambiguation."""
        # Check conditional alignment match counts
        m14130 = self.match_df[self.match_df["local_match_id"] == 14130].iloc[0]
        m14164 = self.match_df[self.match_df["local_match_id"] == 14164].iloc[0]
        self.assertEqual(m14130["local_delivery_count"], 251)
        self.assertEqual(m14164["local_delivery_count"], 219)
        self.assertEqual(m14130["warning_disposition"], "SAFE_MINOR_OMISSION")
        self.assertEqual(m14164["warning_disposition"], "SAFE_MINOR_OMISSION")

        # Check player aliases for 6645 and 29075
        p6645 = self.player_df[self.player_df["local_player_id"] == 6645].iloc[0]
        p29075 = self.player_df[self.player_df["local_player_id"] == 29075].iloc[0]
        self.assertEqual(p6645["status"], "RESOLVED")
        self.assertEqual(p6645["cricsheet_name"], "Mohammad Naim")
        self.assertEqual(p29075["status"], "RESOLVED")
        self.assertEqual(p29075["cricsheet_name"], "Mohammad Aadil Alam")

        # Collision verification in player mapping
        ctpm = pd.read_csv("data/extracted/competition_team_player_mapping.csv")
        p6645_names = set(ctpm[ctpm["player_id"] == 6645]["player_name"])
        self.assertEqual(p6645_names, {"Mohammad Sheikh"})
        p29075_names = set(ctpm[ctpm["player_id"] == 29075]["player_name"])
        self.assertEqual(p29075_names, {"Aadil Ansari"})

        # Confirm no other local player has these names
        other_6645 = ctpm[ctpm["player_name"] == "Mohammad Sheikh"]["player_id"].unique()
        self.assertEqual(list(other_6645), [6645])
        other_29075 = ctpm[ctpm["player_name"] == "Aadil Ansari"]["player_id"].unique()
        self.assertEqual(list(other_29075), [29075])


if __name__ == "__main__":
    unittest.main()
