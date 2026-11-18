"""
Phase 5.14.5.1 — Real Manifest Replacement Failure and Recovery Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies Fix E:
1. Seeds an existing valid APPROVED manifest on disk.
2. Executes the real publish_artifacts_fail_safe() pathway.
3. Injects failure specifically at the actual manifest os.replace() operation (via monkeypatch).
4. Verifies that the publication returns False and status is PUBLICATION_FAILED.
5. Verifies that the previous approval CANNOT remain authoritative for the failed generation.
6. Verifies that all temporary files (.tmp) are cleaned up.
7. Verifies that a subsequent publication without simulated filesystem failure recovers completely.
8. Tests missing manifest scenario: verify_authoritative_publication() fails closed.
9. Tests inaccessible/unreadable manifest scenario: verify_authoritative_publication() fails closed.
10. Exercises the actual publication function and its failure handler without pre-emptive bypass.
"""

import os
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    publish_artifacts_fail_safe,
    verify_authoritative_publication,
    evaluate_full_governance_gate,
    PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE,
    PUB_STATE_PUBLICATION_FAILED,
    PUB_STATE_PUBLICATION_COMMITTED,
    MANIFEST_FILENAME,
)


def get_mock_approved_gate():
    return {
        "final_verdict": "APPROVED FOR COMPETITION FREEZE",
        "is_approved": True,
        "primary_reason": "All checks passed.",
        "asset_integrity": {
            "status": "PASSED",
            "is_passed": True,
            "failures_count": 0,
            "failures": [],
            "canonical_dataset": {"match": True},
            "competition_report": {"match": True},
        },
        "audit_authorization": {
            "status": "PASSED",
            "is_passed": True,
            "failures_count": 0,
            "failures": [],
            "checks": {
                "asset_integrity_prerequisite": True,
                "statistical_precision_verified": True,
                "uncertainty_calculation_verified": True,
                "selection_invariance_verified": True,
                "regression_test_suite_passed": True,
            },
        },
    }


def test_real_manifest_replace_failure_invalidates_and_recovers(tmp_path, monkeypatch):
    """
    1. Seed valid approved manifest.
    2. Monkeypatch os.replace specifically during manifest atomic commit.
    3. Verify authoritative state becomes NOT APPROVED and old approval does NOT survive.
    4. Verify temp files cleaned up.
    5. Verify recovery on subsequent publication.
    """
    gate = get_mock_approved_gate()

    # Step 1: Seed valid APPROVED manifest
    ok1, msg1, receipt1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok1 is True
    assert receipt1["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE
    gen1 = receipt1["gen_id"]

    v1, _, m1 = verify_authoritative_publication(output_dir=tmp_path, expected_gen_id=gen1)
    assert v1 is True
    assert m1["is_approved"] is True
    assert m1["active_generation_id"] == gen1

    # Step 2: Intercept real os.replace ONLY when target is MANIFEST_FILENAME
    real_replace = os.replace

    def mock_replace_fail_on_manifest(src, dst):
        dst_path = Path(dst)
        # Allow summary and verdict replace; fail specifically on manifest atomic commit
        if dst_path.name == MANIFEST_FILENAME:
            raise OSError(f"[Errno 13] Permission denied / real filesystem lock on {dst}")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace_fail_on_manifest)

    # Step 3: Run real publication pathway
    ok2, msg2, receipt2 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok2 is False
    assert receipt2["publication_state"] == PUB_STATE_PUBLICATION_FAILED
    gen2 = receipt2["gen_id"]
    assert gen2 != gen1

    # Step 4: Verify authoritative verification for gen2 FAILS
    v2, v2_msg, m2 = verify_authoritative_publication(output_dir=tmp_path, expected_gen_id=gen2)
    assert v2 is False

    # Step 5: Verify that the old approval CANNOT remain authoritative
    # If fallback unlinked the manifest, or wrote invalid manifest, or if expected_gen_id doesn't match:
    v_stale, stale_msg, m_stale = verify_authoritative_publication(output_dir=tmp_path, expected_gen_id=gen2)
    assert v_stale is False

    # Also check general verification without expected_gen_id
    v_gen, _, m_gen = verify_authoritative_publication(output_dir=tmp_path)
    assert v_gen is False, "A failed publication must never leave an authoritative approved state!"

    # Step 6: Verify all temporary files are cleaned up
    tmps = list(tmp_path.glob("*.tmp"))
    assert len(tmps) == 0, f"Lingering temporary files found: {tmps}"

    # Step 7: Restore real os.replace and verify recovery on subsequent run
    monkeypatch.undo()

    ok3, msg3, receipt3 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok3 is True
    assert receipt3["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE
    gen3 = receipt3["gen_id"]

    v3, _, m3 = verify_authoritative_publication(output_dir=tmp_path, expected_gen_id=gen3)
    assert v3 is True
    assert m3["is_approved"] is True
    assert m3["active_generation_id"] == gen3


def test_missing_manifest_fails_closed(tmp_path):
    """When manifest does not exist, authoritative verification must fail closed."""
    v, msg, m = verify_authoritative_publication(output_dir=tmp_path)
    assert v is False
    assert "missing" in msg.lower()


def test_unreadable_manifest_fails_closed(tmp_path):
    """When manifest is corrupted or unreadable, authoritative verification must fail closed."""
    manifest_path = tmp_path / MANIFEST_FILENAME
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("{ invalid json corrupted bytes ...")

    v, msg, m = verify_authoritative_publication(output_dir=tmp_path)
    assert v is False
    assert "error verifying" in msg.lower()
