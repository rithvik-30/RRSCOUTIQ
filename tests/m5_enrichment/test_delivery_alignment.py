"""
Unit tests for DeliveryAlignmentEngine.
Module: tests/m5_enrichment/test_delivery_alignment.py
"""

import json
import zipfile
import unittest
import pandas as pd

from src.m5_enrichment.delivery_alignment import (
    DeliveryAlignmentEngine,
    QuarantinedMatchError,
    AlignmentStrategy,
    QUARANTINED_MATCH_IDS
)


class TestDeliveryAlignmentEngine(unittest.TestCase):
    """Test suite for delivery alignment logic."""

    @classmethod
    def setUpClass(cls):
        cls.audit_df = pd.read_csv("data/enriched/m5_match_coverage_audit.csv")
        # Read small sample of local deliveries
        test_mids = [14094, 13613, 21176, 14130, 14164]
        chunks = []
        for c in pd.read_csv("data/extracted/ball_by_ball.csv", chunksize=50000):
            sub = c[c["match_id"].isin(test_mids)]
            if not sub.empty:
                chunks.append(sub)
        cls.bbb_sub = pd.concat(chunks, ignore_index=True)

    def _load_cric_json(self, match_id: int):
        row = self.audit_df[self.audit_df["local_match_id"] == match_id].iloc[0]
        arch = row["cricsheet_archive"]
        fname = row["cricsheet_file"]
        zip_path = f"data/external/cricsheet/downloads/{arch}"
        with zipfile.ZipFile(zip_path, "r") as z:
            with z.open(fname) as f:
                return json.load(f), row["warning_disposition"]

    def test_01_clean_validated_match(self):
        """Tests standard 1-to-1 delivery alignment for a clean match."""
        mid = 14094
        cdata, warn = self._load_cric_json(mid)
        aligned = DeliveryAlignmentEngine.align_match_deliveries(
            local_match_id=mid,
            cdata=cdata,
            local_df=self.bbb_sub,
            warning_disposition=warn
        )
        self.assertEqual(len(aligned), 237)
        # Check metadata
        for _, _, meta in aligned:
            self.assertEqual(meta["alignment_strategy"], AlignmentStrategy.CLEAN_VALIDATED.value)
            self.assertFalse(meta["omitted_cricsheet_event"])

    def test_02_regulation_only_matches(self):
        """Tests regulation-only alignment for 13613 and 21176, confirming Super Overs are omitted."""
        # Match 13613
        cdata_13613, warn_13613 = self._load_cric_json(13613)
        aligned_13613 = DeliveryAlignmentEngine.align_match_deliveries(
            local_match_id=13613,
            cdata=cdata_13613,
            local_df=self.bbb_sub,
            warning_disposition=warn_13613
        )
        self.assertEqual(len(aligned_13613), 246)
        for _, _, meta in aligned_13613:
            self.assertEqual(meta["alignment_strategy"], AlignmentStrategy.REGULATION_ONLY.value)
            self.assertFalse(meta["is_super_over"])

        # Match 21176
        cdata_21176, warn_21176 = self._load_cric_json(21176)
        aligned_21176 = DeliveryAlignmentEngine.align_match_deliveries(
            local_match_id=21176,
            cdata=cdata_21176,
            local_df=self.bbb_sub,
            warning_disposition=warn_21176
        )
        self.assertEqual(len(aligned_21176), 252)
        for _, _, meta in aligned_21176:
            self.assertEqual(meta["alignment_strategy"], AlignmentStrategy.REGULATION_ONLY.value)
            self.assertFalse(meta["is_super_over"])

    def test_03_minor_omission_matches(self):
        """Tests deterministic minor omission alignment for matches 14130 and 14164."""
        # Match 14130
        cdata_14130, warn_14130 = self._load_cric_json(14130)
        aligned_14130 = DeliveryAlignmentEngine.align_match_deliveries(
            local_match_id=14130,
            cdata=cdata_14130,
            local_df=self.bbb_sub,
            warning_disposition=warn_14130
        )
        self.assertEqual(len(aligned_14130), 251)
        omitted_events_14130 = [meta for _, _, meta in aligned_14130 if meta["omitted_cricsheet_event"]]
        # In Match 14130, Over 14 in inn 1 has 5 mapped deliveries, Over 14 in inn 2 has 6 mapped deliveries
        self.assertEqual(len(omitted_events_14130), 11)

        # Match 14164
        cdata_14164, warn_14164 = self._load_cric_json(14164)
        aligned_14164 = DeliveryAlignmentEngine.align_match_deliveries(
            local_match_id=14164,
            cdata=cdata_14164,
            local_df=self.bbb_sub,
            warning_disposition=warn_14164
        )
        self.assertEqual(len(aligned_14164), 219)
        omitted_events_14164 = [meta for _, _, meta in aligned_14164 if meta["omitted_cricsheet_event"]]
        self.assertEqual(len(omitted_events_14164), 5)

    def test_04_quarantined_matches_raise_error(self):
        """Verifies that quarantined matches raise QuarantinedMatchError."""
        for q_mid in QUARANTINED_MATCH_IDS:
            with self.assertRaises(QuarantinedMatchError):
                DeliveryAlignmentEngine.align_match_deliveries(
                    local_match_id=q_mid,
                    cdata={},
                    local_df=pd.DataFrame(),
                    warning_disposition="QUARANTINED_INCOMPATIBLE"
                )


if __name__ == "__main__":
    unittest.main()
