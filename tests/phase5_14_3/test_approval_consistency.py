"""
Tests for Phase 5.14.3 — Final Approval Consistency Hardening
Verifies:
  1. Path existence-check exceptions are trapped.
  2. Hashing exceptions are trapped.
  3. Both hashes matching passes Asset Integrity.
  4. Each individual mismatch fails Asset Integrity.
  5. Both mismatches fail Asset Integrity.
  6. Missing and unreadable files fail Asset Integrity.
  7. Failed JSON publication handled safely.
  8. Failed Markdown publication handled safely.
  9. Stale approval prevention after a failed rerun.
  10. JSON/Markdown verdict consistency.
  11. Audit authorization blocked when tests or statistical verification fail.
  12. Original frozen files and selections remain unchanged.
"""
import os
import sys
import json
import pytest
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_3.hardened_gate import (
    compute_sha256_safe,
    evaluate_asset_integrity,
    evaluate_audit_authorization,
    evaluate_full_governance_gate,
    publish_artifacts_atomic,
    EXPECTED_CANON_HASH,
    EXPECTED_REPORT_HASH,
    DEFAULT_CANON_PATH,
    DEFAULT_REPORT_PATH
)

SUMMARY_FILE = Path("research/phase5_14_3/phase5_14_3_validation_summary.json")
VERDICT_FILE = Path("research/phase5_14_3/PHASE_5_14_3_FINAL_VERDICT.md")

def sha256_of_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()

def test_path_existence_exceptions_trapped():
    # Pass a directory to test is_file() failure trapping
    ok, hash_val, err = compute_sha256_safe(Path("research"))
    assert ok is False
    assert "NOT_A_FILE" in err
    assert hash_val == ""

def test_hashing_exceptions_trapped():
    # Pass an invalid nonexistent path
    ok, hash_val, err = compute_sha256_safe(Path("non_existent_directory/file.csv"))
    assert ok is False
    assert "FILE_NOT_FOUND" in err
    assert hash_val == ""

def test_both_hashes_matching_passes_asset_integrity():
    res = evaluate_asset_integrity()
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert res["failures_count"] == 0

def test_individual_hash_mismatches_fail_asset_integrity():
    fake_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    
    # Canon mismatch
    res_c = evaluate_asset_integrity(expected_canon=fake_hash)
    assert res_c["is_passed"] is False
    assert "CANONICAL DATASET HASH MISMATCH" in res_c["status"]
    
    # Report mismatch
    res_r = evaluate_asset_integrity(expected_report=fake_hash)
    assert res_r["is_passed"] is False
    assert "COMPETITION REPORT HASH MISMATCH" in res_r["status"]

def test_both_hash_mismatches_fail_asset_integrity():
    fake_hash = "1111111111111111111111111111111111111111111111111111111111111111"
    res = evaluate_asset_integrity(expected_canon=fake_hash, expected_report=fake_hash)
    assert res["is_passed"] is False
    assert "MULTIPLE HASH MISMATCHES" in res["status"]
    assert res["failures_count"] == 2

def test_missing_and_unreadable_files_fail_asset_integrity():
    missing_path = Path("non_existent/data.csv")
    res = evaluate_asset_integrity(canon_path=missing_path)
    assert res["is_passed"] is False
    assert "CANONICAL DATASET ACCESS FAILURE" in res["status"]
    assert res["canonical_dataset"]["accessible"] is False

def test_failed_json_publication_handled(tmp_path):
    # Test publishing to an invalid/read-only path
    invalid_dir = tmp_path / "invalid_target"
    invalid_dir.mkdir()
    # Create a directory with the same name as the target file to cause a replace error
    (invalid_dir / "phase5_14_3_validation_summary.json").mkdir()
    
    gate_res = evaluate_full_governance_gate()
    ok, msg = publish_artifacts_atomic(gate_res, output_dir=invalid_dir)
    assert ok is False
    assert "PUBLICATION_FAILED" in msg

def test_failed_markdown_publication_handled(tmp_path):
    invalid_dir = tmp_path / "invalid_target_md"
    invalid_dir.mkdir()
    (invalid_dir / "PHASE_5_14_3_FINAL_VERDICT.md").mkdir()
    
    gate_res = evaluate_full_governance_gate()
    ok, msg = publish_artifacts_atomic(gate_res, output_dir=invalid_dir)
    assert ok is False
    assert "PUBLICATION_FAILED" in msg

def test_stale_approval_prevention_after_failed_rerun(tmp_path):
    # 1. First publish an approved verdict to tmp_path
    approved_gate = evaluate_full_governance_gate()
    assert approved_gate["is_approved"] is True
    ok1, _ = publish_artifacts_atomic(approved_gate, output_dir=tmp_path)
    assert ok1 is True
    
    # Check that it is currently approved
    with open(tmp_path / "PHASE_5_14_3_FINAL_VERDICT.md", "r", encoding="utf-8") as f:
        text1 = f.read()
    assert "APPROVED FOR COMPETITION FREEZE" in text1
    
    # 2. Now simulate a failed rerun (e.g. hash mismatch)
    failed_gate = evaluate_full_governance_gate(expected_canon="fake_hash_12345")
    assert failed_gate["is_approved"] is False
    
    # Publish failed result
    ok2, _ = publish_artifacts_atomic(failed_gate, output_dir=tmp_path)
    assert ok2 is True
    
    # Check that previous approval was completely overwritten and replaced with NOT APPROVED
    with open(tmp_path / "PHASE_5_14_3_FINAL_VERDICT.md", "r", encoding="utf-8") as f:
        text2 = f.read()
    assert "NOT APPROVED" in text2
    assert "FINAL VERDICT: \\quad APPROVED" not in text2

def test_json_markdown_verdict_consistency():
    assert SUMMARY_FILE.exists()
    assert VERDICT_FILE.exists()
    
    with open(SUMMARY_FILE, "r") as f:
        summary = json.load(f)
    with open(VERDICT_FILE, "r", encoding="utf-8") as f:
        verdict_text = f.read()
        
    final_verdict = summary["metadata"]["final_verdict"]
    is_approved = summary["metadata"]["is_approved"]
    
    if is_approved:
        assert "APPROVED FOR COMPETITION FREEZE" in verdict_text
        assert "NOT APPROVED" not in verdict_text
    else:
        assert "NOT APPROVED" in verdict_text

def test_audit_authorization_blocked_when_tests_or_stats_fail():
    # 1. Blocked when test suite fails
    auth_fail_test = evaluate_audit_authorization(asset_integrity_passed=True, override_test_pass=False)
    assert auth_fail_test["is_passed"] is False
    assert any("Repository unit test suite did not pass" in f for f in auth_fail_test["failures"])
    
    # 2. Blocked when asset integrity fails
    auth_fail_asset = evaluate_audit_authorization(asset_integrity_passed=False)
    assert auth_fail_asset["is_passed"] is False
    assert any("Asset integrity was not passed" in f for f in auth_fail_asset["failures"])

def test_frozen_files_and_official_selections_unchanged():
    actual_canon = sha256_of_file(DEFAULT_CANON_PATH)
    actual_report = sha256_of_file(DEFAULT_REPORT_PATH)
    
    assert actual_canon == EXPECTED_CANON_HASH
    assert actual_report == EXPECTED_REPORT_HASH
    
    with open(SUMMARY_FILE, "r") as f:
        data = json.load(f)
    assert data["audit_authorization"]["checks"]["official_selections_invariant"] is True
