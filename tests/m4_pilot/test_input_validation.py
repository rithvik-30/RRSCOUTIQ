"""
RR ScoutIQ - Unit Tests for Module M4.1 (Input Validation)
==========================================================

Evidence Level: IMPLEMENTATION CORRECTNESS
Validates that M4.1 input validation catches schema violations, record count anomalies,
duplicate keys, crosswalk integrity flaws, delivery legality violations,
innings total mismatches, Super Over detection, and source file hash changes.
Uses standard library unittest for 100% environment compatibility.
"""

import unittest
import pandas as pd
from src.m4_pilot.input_validation import (
    validate_pilot_dataset,
    load_and_validate_pilot_data,
    verify_dataset_immutability,
    EXPECTED_PILOT_DELIVERIES,
    EXPECTED_PILOT_MATCHES,
    EXPECTED_COLUMNS,
    EXPECTED_RAW_HASHES
)


class TestInputValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Loads genuine pilot delivery dataset and auxiliary tables once for test suite."""
        cls.df = pd.read_csv("data/enriched/pilot/enriched_ball_by_ball_pilot.csv")
        cls.match_cw = pd.read_csv("data/enriched/match_crosswalk.csv")
        cls.player_cw = pd.read_csv("data/enriched/player_crosswalk.csv")
        cls.matches = pd.read_csv("data/extracted/matches.csv")

    def test_01_valid_pilot_input(self):
        """Verifies that the authentic pilot dataset passes all M4.1 validation rules."""
        report = validate_pilot_dataset(
            df=self.df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=True
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.delivery_count, EXPECTED_PILOT_DELIVERIES)
        self.assertEqual(report.match_count, EXPECTED_PILOT_MATCHES)
        errors = [i for i in report.issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0, f"Unexpected errors found: {errors}")

    def test_02_source_file_hash_integrity(self):
        """Verifies that all 8 raw and pilot files match their approved SHA-256 hashes."""
        passed, issues = verify_dataset_immutability()
        self.assertTrue(passed)
        self.assertEqual(len(issues), 0)

    def test_03_hash_integrity_failure_detection(self):
        """Verifies that modifying expected hash values correctly causes validation failure."""
        tampered_hashes = EXPECTED_RAW_HASHES.copy()
        tampered_hashes["data/extracted/matches.csv"] = "0" * 64
        passed, issues = verify_dataset_immutability(tampered_hashes)
        self.assertFalse(passed)
        self.assertTrue(any("Hash mismatch" in i.message for i in issues))

    def test_04_missing_required_column_detection(self):
        """Verifies that dropping a mandatory column triggers a schema error."""
        corrupted_df = self.df.drop(columns=["ext_bowler_debit_runs"])
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "SCHEMA" for i in report.issues))

    def test_05_duplicate_key_detection(self):
        """Verifies that duplicate delivery keys are flagged as critical errors."""
        corrupted_df = pd.concat([self.df, self.df.iloc[[0]]], ignore_index=True)
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "KEY_INTEGRITY" for i in report.issues))

    def test_06_delivery_count_mismatch_detection(self):
        """Verifies that slicing rows out is flagged as a record count error."""
        truncated_df = self.df.iloc[:1000]
        report = validate_pilot_dataset(
            df=truncated_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "RECORD_COUNT" for i in report.issues))

    def test_07_delivery_legality_violation_detection(self):
        """Verifies that illegal delivery flag inconsistency is flagged."""
        corrupted_df = self.df.copy()
        wide_idx = corrupted_df[corrupted_df["ext_is_wide"] == True].index[0]
        corrupted_df.loc[wide_idx, "ext_is_legal_delivery"] = True
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category in ["LEGALITY_RULE", "LEGALITY_M2_RECONCILIATION"] for i in report.issues))

    def test_07b_m2_legality_reconciliation_negative_test(self):
        """Verifies that classifying an 'Overstep' or 'other' delivery as legal triggers LEGALITY_M2_RECONCILIATION error."""
        corrupted_df = self.df.copy()
        overstep_idx = corrupted_df[corrupted_df["extras_type"] == "Overstep"].index[0]
        corrupted_df.loc[overstep_idx, "ext_is_legal_delivery"] = True
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "LEGALITY_M2_RECONCILIATION" for i in report.issues))

    def test_07c_m2_byes_legbyes_legality_negative_test(self):
        """Verifies that incorrectly classifying 'byes' or 'legbyes' as illegal triggers LEGALITY_M2_RECONCILIATION error."""
        corrupted_df = self.df.copy()
        bye_idx = corrupted_df[corrupted_df["extras_type"] == "byes"].index[0]
        corrupted_df.loc[bye_idx, "ext_is_legal_delivery"] = False
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "LEGALITY_M2_RECONCILIATION" for i in report.issues))

    def test_08_batter_balls_faced_violation_detection(self):
        """Verifies that wide balls incorrectly counted as balls faced are flagged."""
        corrupted_df = self.df.copy()
        wide_idx = corrupted_df[corrupted_df["ext_is_wide"] == True].index[0]
        corrupted_df.loc[wide_idx, "ext_batter_balls_faced"] = 1
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "BBF_RULE" for i in report.issues))

    def test_09_innings_total_reconciliation_failure(self):
        """Verifies that an unaligned runs total across an innings causes validation failure."""
        corrupted_df = self.df.copy()
        corrupted_df.loc[0, "runs"] += 10
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "INNINGS_TOTAL_RECONCILIATION" for i in report.issues))

    def test_09b_bowler_debit_reconciliation_failure(self):
        """Verifies that altering ext_bowler_debit_runs triggers an explicit INNINGS_DEBIT_RECONCILIATION error."""
        corrupted_df = self.df.copy()
        corrupted_df.loc[0, "ext_bowler_debit_runs"] += 6
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "INNINGS_DEBIT_RECONCILIATION" for i in report.issues))

    def test_09c_extras_classification_inconsistency(self):
        """Verifies that negative extras or wide flag inconsistency triggers EXTRAS_VALIDATION errors."""
        corrupted_df = self.df.copy()
        corrupted_df.loc[0, "ext_wide_runs"] = -1
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "EXTRAS_VALIDATION" for i in report.issues))

    def test_09d_shortened_and_dls_metadata_tracking(self):
        """Verifies that matches_df metadata correctly populates DLS and revised overs tracking."""
        report = validate_pilot_dataset(
            df=self.df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertIn("dls_revised_target_matches", report.metadata)
        self.assertIn("shortened_overs_matches", report.metadata)
        self.assertIsInstance(report.metadata["dls_revised_target_matches"], list)
        self.assertIsInstance(report.metadata["shortened_overs_matches"], list)

    def test_10_crosswalk_unmapped_player_detection(self):
        """Verifies that a delivery with an unmapped player ID is flagged."""
        corrupted_df = self.df.copy()
        corrupted_df.loc[0, "striker_id"] = 99999999
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "CROSSWALK_INTEGRITY" for i in report.issues))

    def test_11_super_over_detection(self):
        """Verifies that Super Overs (innings 3 & 4) in matches 34429 & 40725 are identified."""
        report = validate_pilot_dataset(
            df=self.df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertIn("super_over_matches", report.metadata)
        self.assertEqual(set(report.metadata["super_over_matches"]), {34429, 40725})
        self.assertGreater(report.metadata["super_over_deliveries"], 0)

    def test_12_missing_provenance_detection(self):
        """Verifies that missing provenance values trigger an error."""
        corrupted_df = self.df.copy()
        corrupted_df.loc[0, "ext_provenance"] = ""
        report = validate_pilot_dataset(
            df=corrupted_df,
            match_crosswalk_df=self.match_cw,
            player_crosswalk_df=self.player_cw,
            matches_df=self.matches,
            verify_hashes=False
        )
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "PROVENANCE" for i in report.issues))

    def test_13_convenience_loader(self):
        """Verifies that load_and_validate_pilot_data loads data and passes validation."""
        data, report = load_and_validate_pilot_data()
        self.assertIsInstance(data, pd.DataFrame)
        self.assertEqual(len(data), EXPECTED_PILOT_DELIVERIES)
        self.assertTrue(report.passed)


if __name__ == "__main__":
    unittest.main()
