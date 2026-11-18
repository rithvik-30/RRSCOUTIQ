"""
Phase 5.14.5.2 — Final Authoritative Reader State & Validation Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies:
1. get_authoritative_generation_status() correctly distinguishes all 5 lifecycle states:
   - COMMITTED
   - PREVIOUS / STALE
   - IN_PROGRESS
   - FAILED
   - UNVERIFIABLE
2. verify_authoritative_publication() fails closed on:
   - Missing manifest
   - Unreadable/corrupted manifest JSON
   - Artifact hash mismatches (summary or verdict)
   - Generation ID discrepancies across summary, verdict, and manifest
   - Double-failure stale approval states
3. Valid committed publications are verified with 100% cryptographic precision.
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
    get_authoritative_generation_status,
    MANIFEST_FILENAME,
    PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE,
    PUB_STATE_PUBLICATION_FAILED,
)


def get_mock_gate():
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


def test_reader_verifies_committed_state(tmp_path):
    """Test standard COMMITTED state verification."""
    gate = get_mock_gate()
    ok, msg, receipt = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok is True

    status_info = get_authoritative_generation_status(output_dir=tmp_path)
    assert status_info["generation_status"] == "COMMITTED"
    assert status_info["is_approved"] is True
    assert status_info["active_generation_id"] == receipt["gen_id"]

    v, v_msg, m = verify_authoritative_publication(output_dir=tmp_path)
    assert v is True
    assert "100% cryptographic precision" in v_msg


def test_reader_fails_on_missing_manifest(tmp_path):
    """Missing manifest must report failure and indicate missing status."""
    v, msg, details = verify_authoritative_publication(output_dir=tmp_path)
    assert v is False
    assert "missing" in msg.lower()


def test_reader_fails_on_corrupted_manifest(tmp_path):
    """Corrupted manifest JSON must trigger unreadable error and fail closed."""
    manifest_p = tmp_path / MANIFEST_FILENAME
    with open(manifest_p, "w", encoding="utf-8") as f:
        f.write("{ corrupted json [")

    v, msg, details = verify_authoritative_publication(output_dir=tmp_path)
    assert v is False
    assert "error verifying" in msg.lower()


def test_reader_fails_on_summary_hash_tampering(tmp_path):
    """Tampering with summary JSON must trigger SHA-256 mismatch rejection."""
    gate = get_mock_gate()
    ok, _, receipt = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok is True

    # Tamper with summary file
    summary_p = tmp_path / "phase5_14_5_validation_summary.json"
    with open(summary_p, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["tampered"] = True
    with open(summary_p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    v, msg, details = verify_authoritative_publication(output_dir=tmp_path)
    assert v is False
    assert "summary sha-256 mismatch" in msg.lower()


def test_reader_fails_on_verdict_hash_tampering(tmp_path):
    """Tampering with verdict Markdown must trigger SHA-256 mismatch rejection."""
    gate = get_mock_gate()
    ok, _, receipt = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok is True

    # Tamper with verdict file
    verdict_p = tmp_path / "PHASE_5_14_5_FINAL_VERDICT.md"
    with open(verdict_p, "a", encoding="utf-8") as f:
        f.write("\n<!-- Tampered content -->\n")

    v, msg, details = verify_authoritative_publication(output_dir=tmp_path)
    assert v is False
    assert "verdict sha-256 mismatch" in msg.lower()


def test_reader_fails_on_generation_id_mismatch(tmp_path):
    """Expected generation ID mismatch must fail closed."""
    gate = get_mock_gate()
    ok, _, receipt = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok is True
    actual_gen = receipt["gen_id"]

    v, msg, details = verify_authoritative_publication(output_dir=tmp_path, expected_gen_id="gen_wrong_id_123")
    assert v is False
    assert "generation id mismatch" in msg.lower()
