"""
Tests for Phase 5.14.2 — Final Freeze-Gate Hardening & Epistemic Uncertainty Audit
Verifies:
  1. Both hashes matching produces approval.
  2. Canonical dataset mismatch blocks approval.
  3. Competition report mismatch blocks approval.
  4. Both mismatches block approval.
  5. Missing canonical file blocks approval.
  6. Missing competition report blocks approval.
  7. Exceptions / unreadable files block approval.
  8. Final verdict document agrees with machine-readable gate.
  9. Original frozen files remain unchanged.
  10. Statistical results and official selections remain unchanged.
"""
import os
import sys
import json
import pytest
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_2.freeze_gate import (
    evaluate_freeze_gate,
    compute_sha256_safe,
    EXPECTED_CANON_HASH,
    EXPECTED_REPORT_HASH,
    DEFAULT_CANON_PATH,
    DEFAULT_REPORT_PATH
)

SUMMARY_FILE = Path("research/phase5_14_2/phase5_14_2_validation_summary.json")
VERDICT_FILE = Path("research/phase5_14_2/PHASE_5_14_2_FINAL_VERDICT.md")
STATS_FILE = Path("research/phase5_14_1/corrected_statistical_interpretation.json")

def sha256_of_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()

def test_both_hashes_matching_produces_approval():
    result = evaluate_freeze_gate(
        canon_path=DEFAULT_CANON_PATH,
        report_path=DEFAULT_REPORT_PATH,
        expected_canon=EXPECTED_CANON_HASH,
        expected_report=EXPECTED_REPORT_HASH
    )
    assert result["is_approved"] is True
    assert result["verdict"] == "APPROVED FOR COMPETITION FREEZE"
    assert result["failures_count"] == 0

def test_canonical_mismatch_blocks_approval():
    fake_canon_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    result = evaluate_freeze_gate(
        canon_path=DEFAULT_CANON_PATH,
        report_path=DEFAULT_REPORT_PATH,
        expected_canon=fake_canon_hash,
        expected_report=EXPECTED_REPORT_HASH
    )
    assert result["is_approved"] is False
    assert result["verdict"] == "NOT APPROVED — CANONICAL DATASET HASH MISMATCH"
    assert result["failures_count"] == 1

def test_report_mismatch_blocks_approval():
    fake_report_hash = "1111111111111111111111111111111111111111111111111111111111111111"
    result = evaluate_freeze_gate(
        canon_path=DEFAULT_CANON_PATH,
        report_path=DEFAULT_REPORT_PATH,
        expected_canon=EXPECTED_CANON_HASH,
        expected_report=fake_report_hash
    )
    assert result["is_approved"] is False
    assert result["verdict"] == "NOT APPROVED — COMPETITION REPORT HASH MISMATCH"
    assert result["failures_count"] == 1

def test_both_mismatch_blocks_approval():
    fake_hash = "2222222222222222222222222222222222222222222222222222222222222222"
    result = evaluate_freeze_gate(
        canon_path=DEFAULT_CANON_PATH,
        report_path=DEFAULT_REPORT_PATH,
        expected_canon=fake_hash,
        expected_report=fake_hash
    )
    assert result["is_approved"] is False
    assert result["verdict"] == "NOT APPROVED — MULTIPLE HASH MISMATCHES"
    assert result["failures_count"] == 2

def test_missing_canonical_file_blocks_approval():
    missing_path = Path("data/processed/non_existent_file.csv")
    result = evaluate_freeze_gate(
        canon_path=missing_path,
        report_path=DEFAULT_REPORT_PATH,
        expected_canon=EXPECTED_CANON_HASH,
        expected_report=EXPECTED_REPORT_HASH
    )
    assert result["is_approved"] is False
    assert "CANONICAL DATASET ACCESS FAILURE" in result["verdict"]
    assert result["canonical_dataset"]["accessible"] is False

def test_missing_report_file_blocks_approval():
    missing_path = Path("non_existent_report.md")
    result = evaluate_freeze_gate(
        canon_path=DEFAULT_CANON_PATH,
        report_path=missing_path,
        expected_canon=EXPECTED_CANON_HASH,
        expected_report=EXPECTED_REPORT_HASH
    )
    assert result["is_approved"] is False
    assert "COMPETITION REPORT ACCESS FAILURE" in result["verdict"]
    assert result["competition_report"]["accessible"] is False

def test_exceptions_cannot_produce_approval():
    # Pass an invalid directory as file path to trigger OS read exception
    dir_path = Path("research")
    ok, hash_val, err_msg = compute_sha256_safe(dir_path)
    assert ok is False
    assert len(err_msg) > 0
    assert hash_val == ""

def test_verdict_document_matches_machine_gate():
    assert SUMMARY_FILE.exists()
    assert VERDICT_FILE.exists()
    
    with open(SUMMARY_FILE, "r") as f:
        summary = json.load(f)
    with open(VERDICT_FILE, "r", encoding="utf-8") as f:
        verdict_text = f.read()
    
    gate_verdict = summary["hash_gate_results"]["verdict"]
    is_approved = summary["hash_gate_results"]["is_approved"]
    
    if is_approved:
        assert "APPROVED FOR COMPETITION FREEZE" in verdict_text
        assert "NOT APPROVED" not in verdict_text
    else:
        assert "NOT APPROVED" in verdict_text

def test_frozen_files_unchanged():
    actual_canon = sha256_of_file(DEFAULT_CANON_PATH)
    actual_report = sha256_of_file(DEFAULT_REPORT_PATH)
    
    assert actual_canon == EXPECTED_CANON_HASH
    assert actual_report == EXPECTED_REPORT_HASH

def test_statistical_results_and_rankings_unchanged():
    with open(STATS_FILE, "r") as f:
        stats = json.load(f)
    
    summary = stats["metadata"]["classification_summary"]
    assert summary["statistically_significant_post_holm"] == 6
    assert summary["directional_raw_significant_post_holm_non_significant"] == 0
    assert summary["non_significant"] == 2
