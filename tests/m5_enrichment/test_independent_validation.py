"""
RR ScoutIQ — Milestone M5.2.1 Independent Validation Tests
Module: tests/m5_enrichment/test_independent_validation.py

Verifies:
1. Exact delivery accounting: 179,837 = 172,076 legal + 6,976 wides + 785 no-balls (0 overlap).
2. Authoritative fixture identities for 13613 (AUS vs SL) and 21176 (NZ vs SL).
3. Sequence alignment stability for minor omission matches 14130 and 14164.
4. Independent reconciliation of enriched fields against raw Cricsheet JSON archives (0 mismatches).
5. 33/33 raw local columns bitwise preserved.
6. Bitwise immutability of all 8 canonical files.
"""

import os
import unittest
import pandas as pd

from src.m5_enrichment.independent_event_reconciliation import IndependentEventReconciliation
from src.m4_pilot.input_validation import verify_dataset_immutability

BASE_DIR = os.path.abspath(".")
ENRICHED_BBB_PATH = os.path.join(BASE_DIR, "data", "enriched", "full", "enriched_ball_by_ball_full.csv")
MANIFEST_PATH = os.path.join(BASE_DIR, "data", "enriched", "full", "match_enrichment_manifest.csv")
MATCHES_PATH = os.path.join(BASE_DIR, "data", "extracted", "matches.csv")


class TestM521IndependentValidation(unittest.TestCase):
    """Independent audit test suite for M5.2.1."""

    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv(ENRICHED_BBB_PATH)
        cls.manifest = pd.read_csv(MANIFEST_PATH)
        cls.matches = pd.read_csv(MATCHES_PATH)

    def test_01_exact_legal_delivery_accounting(self):
        """Verifies exact legal, wide, and no-ball delivery counts and 0 overlap."""
        total = len(self.df)
        self.assertEqual(total, 179837)

        wides = (self.df["ext_is_wide"] == True).sum()
        noballs = (self.df["ext_is_noball"] == True).sum()
        both = ((self.df["ext_is_wide"] == True) & (self.df["ext_is_noball"] == True)).sum()
        legals = (self.df["ext_is_legal_delivery"] == True).sum()

        self.assertEqual(wides, 6976)
        self.assertEqual(noballs, 785)
        self.assertEqual(both, 0)
        self.assertEqual(legals, 172076)

        # Exact mathematical partition
        self.assertEqual(legals + wides + noballs, total)

    def test_02_authoritative_match_identities_13613_21176(self):
        """Verifies true fixture identities for matches 13613 and 21176."""
        # Match 13613
        m13613_loc = self.matches[self.matches["match_id"] == 13613].iloc[0]
        m13613_man = self.manifest[self.manifest["local_match_id"] == 13613].iloc[0]
        m13613_enr = self.df[self.df["match_id"] == 13613]

        self.assertEqual(m13613_loc["home_team"], "Australia")
        self.assertEqual(m13613_loc["away_team"], "Sri Lanka")
        self.assertEqual(m13613_loc["match_date"], "2022-02-13")
        self.assertEqual(m13613_man["cricsheet_match_id"], 1263472.0)
        self.assertEqual(m13613_man["analytical_scope"], "REGULATION_ONLY")
        self.assertEqual(len(m13613_enr), 246)
        self.assertEqual(m13613_enr["ext_cricsheet_file"].iloc[0], "1263472.json")
        self.assertEqual(m13613_enr["ext_is_super_over"].sum(), 0)

        # Match 21176
        m21176_loc = self.matches[self.matches["match_id"] == 21176].iloc[0]
        m21176_man = self.manifest[self.manifest["local_match_id"] == 21176].iloc[0]
        m21176_enr = self.df[self.df["match_id"] == 21176]

        self.assertEqual(m21176_loc["home_team"], "New Zealand")
        self.assertEqual(m21176_loc["away_team"], "Sri Lanka")
        self.assertEqual(m21176_loc["match_date"], "2023-04-02")
        self.assertEqual(m21176_man["cricsheet_match_id"], 1322362.0)
        self.assertEqual(m21176_man["analytical_scope"], "REGULATION_ONLY")
        self.assertEqual(len(m21176_enr), 252)
        self.assertEqual(m21176_enr["ext_cricsheet_file"].iloc[0], "1322362.json")
        self.assertEqual(m21176_enr["ext_is_super_over"].sum(), 0)

    def test_03_minor_omission_matches_stability(self):
        """Verifies delivery stability for matches 14130 and 14164."""
        # Match 14130
        m14130 = self.df[self.df["match_id"] == 14130]
        self.assertEqual(len(m14130), 251)
        self.assertEqual(m14130["ext_cricsheet_file"].iloc[0], "1304083.json")
        self.assertEqual(m14130["ext_alignment_strategy"].iloc[0], "SAFE_MINOR_OMISSION")

        # Match 14164
        m14164 = self.df[self.df["match_id"] == 14164]
        self.assertEqual(len(m14164), 219)
        self.assertEqual(m14164["ext_cricsheet_file"].iloc[0], "1304116.json")
        self.assertEqual(m14164["ext_alignment_strategy"].iloc[0], "SAFE_MINOR_OMISSION")

    def test_04_independent_event_reconciliation(self):
        """Executes independent event reconciliation across all 179,837 deliveries."""
        recon = IndependentEventReconciliation()
        res = recon.run_reconciliation()
        self.assertEqual(res["total_deliveries_checked"], 179837)
        self.assertEqual(res["cric_internal_mismatches"], 0)
        self.assertEqual(len(res["col_preservation_failures"]), 0)

    def test_05_canonical_dataset_immutability(self):
        """Verifies bitwise immutability of all 8 canonical files."""
        passed, issues = verify_dataset_immutability()
        self.assertTrue(passed, f"Immutability failure: {issues}")
        self.assertEqual(len(issues), 0)


if __name__ == "__main__":
    unittest.main()
