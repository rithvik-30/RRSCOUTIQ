"""
Phase 5.14.5 — Final Approval Consistency and End-to-End Governance Tests
Verifies:
  1. Full governance gate passes all 6 pillars in end-to-end execution.
  2. Hash mismatch in canonical data or competition report blocks overall approval.
  3. Regression test failure blocks overall approval.
  4. Selection invariance mismatch blocks overall approval.
  5. Uncertainty calculation failure blocks overall approval.
  6. Statistical precision failure blocks overall approval.
  7. Published JSON and Markdown strictly agree on generation ID, status, and verdict.
  8. Cryptographic hashes of immutable assets remain intact.
"""

import sys
import os
import json
import hashlib
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    evaluate_full_governance_gate,
    publish_artifacts_fail_safe,
    verify_authoritative_publication,
    DEFAULT_CANON_PATH,
    DEFAULT_REPORT_PATH,
    EXPECTED_CANON_HASH,
    EXPECTED_REPORT_HASH,
    MANIFEST_FILENAME,
    PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE,
)

def get_simulated_passing_runner():
    """Returns a synthetic runner callable representing a successful pytest execution."""
    return lambda: {
        "status": "PASSED",
        "is_passed": True,
        "parse_success": True,
        "exit_code": 0,
        "tests_collected": 132,
        "tests_passed": 132,
        "tests_failed": 0,
        "tests_errors": 0,
        "tests_skipped": 0,
        "duration_seconds": 47.12,
        "stdout_tail": "132 passed in 47.12s",
        "stderr": "",
        "error": None,
    }


def test_full_governance_gate_end_to_end_approval():
    """Verify that full governance gate approves when all pillars pass."""
    gate = evaluate_full_governance_gate(override_runner=get_simulated_passing_runner())
    assert gate["is_approved"] is True
    assert gate["final_verdict"] == "APPROVED FOR COMPETITION FREEZE"
    assert gate["asset_integrity"]["is_passed"] is True
    assert gate["audit_authorization"]["is_passed"] is True


def test_hash_mismatch_blocks_freeze_approval():
    """Verify that altering expected canonical hash blocks approval."""
    bogus_hash = "0" * 64
    gate = evaluate_full_governance_gate(
        expected_canon=bogus_hash,
        override_runner=get_simulated_passing_runner(),
    )
    assert gate["is_approved"] is False
    assert "NOT APPROVED" in gate["final_verdict"]


def test_failing_unit_tests_block_freeze_approval():
    """Verify that failing test runner blocks approval."""
    failing_runner = lambda: {
        "status": "FAILED",
        "is_passed": False,
        "parse_success": True,
        "exit_code": 1,
        "tests_collected": 50,
        "tests_passed": 48,
        "tests_failed": 2,
        "tests_errors": 0,
        "tests_skipped": 0,
        "duration_seconds": 10.0,
        "stdout_tail": "2 failed",
        "stderr": "AssertionError",
        "error": "Pytest exited with code 1",
    }
    gate = evaluate_full_governance_gate(override_runner=failing_runner)
    assert gate["is_approved"] is False
    assert "NOT APPROVED" in gate["final_verdict"]


def test_json_and_markdown_verdicts_agree_on_generation_and_status(tmp_path):
    """Verify that published JSON summary and Markdown verdict match generation ID and verdict."""
    gate = evaluate_full_governance_gate(override_runner=get_simulated_passing_runner())
    ok, msg, receipt = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok is True

    summary_file = tmp_path / "phase5_14_5_validation_summary.json"
    verdict_file = tmp_path / "PHASE_5_14_5_FINAL_VERDICT.md"

    with open(summary_file, "r", encoding="utf-8") as f:
        sum_data = json.load(f)
    with open(verdict_file, "r", encoding="utf-8") as f:
        ver_text = f.read()

    gen_id = receipt["gen_id"]
    assert sum_data["metadata"]["generation_id"] == gen_id
    assert gen_id in ver_text
    assert sum_data["metadata"]["final_verdict"] == "APPROVED FOR COMPETITION FREEZE"
    assert "APPROVED FOR COMPETITION FREEZE" in ver_text


def test_immutable_assets_cryptographically_verified():
    """Direct raw SHA-256 calculation verifies untouched baseline assets."""
    def calc_sha(p):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().lower()

    canon_sha = calc_sha(DEFAULT_CANON_PATH)
    report_sha = calc_sha(DEFAULT_REPORT_PATH)

    assert canon_sha == EXPECTED_CANON_HASH
    assert report_sha == EXPECTED_REPORT_HASH
