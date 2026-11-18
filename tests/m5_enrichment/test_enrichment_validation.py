"""
Unit and regression tests for M5.2 Full-Dataset Cricket Validation.
Module: tests/m5_enrichment/test_enrichment_validation.py
"""

import os
import unittest
import pandas as pd

from src.m5_enrichment.enrichment_validation import (
    FullDatasetEnrichmentValidator,
    VALIDATION_SUMMARY_PATH
)
from src.m4_pilot.input_validation import verify_dataset_immutability


class TestFullDatasetEnrichmentValidation(unittest.TestCase):
    """Test suite verifying full-dataset cricket validation results."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(VALIDATION_SUMMARY_PATH):
            validator = FullDatasetEnrichmentValidator()
            cls.summary_df, cls.all_passed = validator.run_validation()
        else:
            cls.summary_df = pd.read_csv(VALIDATION_SUMMARY_PATH)
            cls.all_passed = cls.summary_df["status"].isin(["PASSED"]).all()

    def test_01_all_validation_checks_pass(self):
        """Verifies that 100% of validation checks in summary pass."""
        self.assertTrue(self.all_passed, "One or more validation checks failed!")
        failures = self.summary_df[self.summary_df["status"] != "PASSED"]
        self.assertEqual(len(failures), 0, f"Validation failures detected: {failures.to_dict(orient='records')}")

    def test_02_delivery_count_invariants(self):
        """Verifies delivery count invariant (179,837) and 0 duplicates."""
        row_deliv = self.summary_df[self.summary_df["check_name"] == "Total Delivery Count Conservation"].iloc[0]
        self.assertEqual(row_deliv["status"], "PASSED")
        self.assertEqual(row_deliv["total_records_tested"], 179837)

        row_dup = self.summary_df[self.summary_df["check_name"] == "Local Delivery Uniqueness (No Duplicates)"].iloc[0]
        self.assertEqual(row_dup["status"], "PASSED")

    def test_03_player_resolution_invariants(self):
        """Verifies 100.0% resolution for striker, bowler, and non-striker."""
        for role in ["Striker", "Bowler", "Non-Striker"]:
            row = self.summary_df[self.summary_df["check_name"] == f"{role} Cricsheet ID Resolution"].iloc[0]
            self.assertEqual(row["status"], "PASSED")
            self.assertIn("100.00%", row["actual_outcome"])

    def test_04_scoring_additive_identities(self):
        """Verifies that all scoring additive rules hold across 179,837 deliveries."""
        for check in [
            "Delivery Total Runs Additive Identity",
            "Extras Component Additive Decomposition",
            "Legal Delivery Classification (No wide & No no-ball)",
            "Batter Balls Faced Accounting (MCC Law)",
            "Bowler Runs Conceded Debit (MCC Law 18.10.3)",
            "Boundary Four and Six Identification"
        ]:
            row = self.summary_df[self.summary_df["check_name"] == check].iloc[0]
            self.assertEqual(row["status"], "PASSED", f"Failed check: {check}")

    def test_05_dismissal_credit_rules(self):
        """Verifies bowler credit attribution, retired hurt exclusion, and retired out handling."""
        # Retired hurt
        rh = self.summary_df[self.summary_df["check_name"] == "Retired Hurt Exclusion (Not a Wicket)"].iloc[0]
        self.assertEqual(rh["status"], "PASSED")
        self.assertIn("0 wickets, 0 bowler wickets", rh["actual_outcome"])

        # Retired out
        ro = self.summary_df[self.summary_df["check_name"] == "Retired Out Classification (Team Wicket, No Bowler Credit)"].iloc[0]
        self.assertEqual(ro["status"], "PASSED")
        self.assertIn("0 bowler wickets", ro["actual_outcome"])

        # Bowler credit
        bc = self.summary_df[self.summary_df["check_name"] == "Bowler Credit Dismissal Attribution"].iloc[0]
        self.assertEqual(bc["status"], "PASSED")
        self.assertIn("0 invalid kinds", bc["actual_outcome"])

    def test_06_dataset_immutability(self):
        """Verifies that raw source archive and pilot files remain bitwise immutable."""
        passed, issues = verify_dataset_immutability()
        self.assertTrue(passed, f"Dataset immutability failure: {issues}")
        self.assertEqual(len(issues), 0)


if __name__ == "__main__":
    unittest.main()
