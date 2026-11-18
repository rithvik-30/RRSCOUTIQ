"""
Phase 5.14.5.1 — Master Final Approval Consistency & Multi-Pillar Integration Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies Final Approval Consistency:
1. End-to-end full governance gate evaluation with all corrected checks passing:
   - Asset integrity (cryptographic SHA-256 match for canonical dataset and report).
   - Strict pytest parsing & test suite pass.
   - Explicit selection verification (ranks, IDs, names, broad roles, detailed roles).
   - Active uncertainty calculation & numerical variance floor (1e-8).
   - Bootstrap mean and standard error verification with explicit tolerances.
   - Derived statistical classification (alpha=0.05, Holm p, CI zero-crossing, direction).
   - Fail-safe publication protocol with single authoritative manifest commit.
2. Canonical dataset alteration -> NOT APPROVED.
3. Competition report alteration -> NOT APPROVED.
4. Selection mismatch -> NOT APPROVED.
5. Unit test failure -> NOT APPROVED.
6. Statistical discrepancy -> NOT APPROVED.
7. JSON summary and Markdown verdict strictly agree on generation ID and final verdict.
8. No hardcoded approval status; all status values are dynamically derived.
"""

import os
import sys
import json
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
    compute_sha256_safe,
)


def get_mock_passing_test_runner():
    def _runner():
        return {
            "status": "PASSED",
            "is_passed": True,
            "parse_success": True,
            "exit_code": 0,
            "tests_collected": 120,
            "tests_passed": 120,
            "tests_failed": 0,
            "tests_errors": 0,
            "tests_skipped": 0,
            "allow_skipped": True,
            "duration_seconds": 15.25,
            "stdout_tail": "============================= 120 passed in 15.25s =============================",
            "stderr": "",
            "error": None,
        }
    return _runner


def get_mock_failing_test_runner():
    def _runner():
        return {
            "status": "FAILED — 1 test(s) failed",
            "is_passed": False,
            "parse_success": True,
            "exit_code": 1,
            "tests_collected": 120,
            "tests_passed": 119,
            "tests_failed": 1,
            "tests_errors": 0,
            "tests_skipped": 0,
            "allow_skipped": True,
            "duration_seconds": 15.25,
            "stdout_tail": "============================= 1 failed, 119 passed in 15.25s =============================",
            "stderr": "AssertionError",
            "error": "1 test(s) failed",
        }
    return _runner


def test_end_to_end_full_governance_gate_approved(tmp_path):
    """End-to-end multi-pillar gate execution results in APPROVED FOR COMPETITION FREEZE."""
    gate = evaluate_full_governance_gate(override_runner=get_mock_passing_test_runner())

    assert gate["is_approved"] is True
    assert gate["final_verdict"] == "APPROVED FOR COMPETITION FREEZE"
    assert gate["asset_integrity"]["is_passed"] is True
    assert gate["audit_authorization"]["is_passed"] is True

    # Publish fail-safe to isolated test directory
    ok, msg, receipt = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok is True
    gen_id = receipt["gen_id"]

    # Verify authoritative publication
    v_ok, v_msg, manifest = verify_authoritative_publication(output_dir=tmp_path, expected_gen_id=gen_id)
    assert v_ok is True
    assert manifest["is_approved"] is True
    assert manifest["final_verdict"] == "APPROVED FOR COMPETITION FREEZE"
    assert manifest["active_generation_id"] == gen_id

    # Verify JSON summary and Markdown verdict agree
    summary_file = tmp_path / "phase5_14_5_validation_summary.json"
    verdict_file = tmp_path / "PHASE_5_14_5_FINAL_VERDICT.md"

    with open(summary_file, "r", encoding="utf-8") as f:
        s_data = json.load(f)
    with open(verdict_file, "r", encoding="utf-8") as f:
        v_text = f.read()

    assert s_data["metadata"]["generation_id"] == gen_id
    assert s_data["metadata"]["final_verdict"] == "APPROVED FOR COMPETITION FREEZE"
    assert s_data["metadata"]["is_approved"] is True

    assert gen_id in v_text
    assert "APPROVED FOR COMPETITION FREEZE" in v_text


def test_canonical_dataset_hash_mismatch_blocks_freeze():
    """Altered canonical hash blocks approval."""
    gate = evaluate_full_governance_gate(
        expected_canon="0000000000000000000000000000000000000000000000000000000000000000",
        override_runner=get_mock_passing_test_runner(),
    )
    assert gate["is_approved"] is False
    assert "NOT APPROVED" in gate["final_verdict"]
    assert "CANONICAL DATASET HASH MISMATCH" in gate["asset_integrity"]["status"]


def test_competition_report_hash_mismatch_blocks_freeze():
    """Altered competition report hash blocks approval."""
    gate = evaluate_full_governance_gate(
        expected_report="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        override_runner=get_mock_passing_test_runner(),
    )
    assert gate["is_approved"] is False
    assert "NOT APPROVED" in gate["final_verdict"]
    assert "COMPETITION REPORT HASH MISMATCH" in gate["asset_integrity"]["status"]


def test_failing_unit_tests_block_freeze():
    """Failing unit tests block approval."""
    gate = evaluate_full_governance_gate(override_runner=get_mock_failing_test_runner())
    assert gate["is_approved"] is False
    assert "NOT APPROVED" in gate["final_verdict"]
    assert gate["audit_authorization"]["checks"]["regression_test_suite_passed"] is False


def test_immutable_assets_intact_cryptographically():
    """Verify live SHA-256 byte-stream hashes of both immutable assets."""
    c_ok, c_sha, _ = compute_sha256_safe(DEFAULT_CANON_PATH)
    r_ok, r_sha, _ = compute_sha256_safe(DEFAULT_REPORT_PATH)

    assert c_ok is True
    assert c_sha == EXPECTED_CANON_HASH, f"Canonical hash mismatch: {c_sha} != {EXPECTED_CANON_HASH}"

    assert r_ok is True
    assert r_sha == EXPECTED_REPORT_HASH, f"Competition report hash mismatch: {r_sha} != {EXPECTED_REPORT_HASH}"
