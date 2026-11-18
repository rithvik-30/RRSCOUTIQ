"""
RR ScoutIQ — Milestone M5.2.2 Canonical SHA-256 Integrity Tests
Module: tests/m5_enrichment/test_canonical_integrity.py

Verifies:
1. Strict match between physical disk files and authoritative M4.6 canonical SHA-256 baseline.
2. Exact preservation of all 33 raw local columns across all 179,837 rows in enriched_ball_by_ball_full.csv.
"""

import unittest
from src.m5_enrichment.canonical_integrity_audit import (
    verify_all_hashes,
    verify_local_column_preservation,
    M4_6_CANONICAL_BASELINE,
    compute_sha256
)


class TestM522CanonicalIntegrity(unittest.TestCase):
    """Test suite enforcing the authentic M4.6 canonical SHA-256 baseline."""

    def test_01_all_eight_files_match_m4_6_baseline(self):
        """Verifies that all 8 protected files match the M4.6 baseline bitwise."""
        results, all_match = verify_all_hashes()
        self.assertTrue(all_match, f"Hash mismatch detected in protected files: {results}")
        for r in results:
            self.assertEqual(r["status"], "MATCH", f"Mismatch in {r['path']}: {r['computed']} != {r['expected']}")

    def test_02_all_33_raw_columns_exact_preservation(self):
        """Verifies that all 33 original local columns match row-by-row, cell-by-cell."""
        discrepancies = verify_local_column_preservation()
        self.assertEqual(len(discrepancies), 0, f"Discrepancies found in raw columns: {discrepancies}")


if __name__ == "__main__":
    unittest.main()
