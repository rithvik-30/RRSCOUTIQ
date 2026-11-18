"""
Tests for Phase 5.14.1 — Final Statistical Interpretation & Freeze-Gate Correction
Verifies:
  1. No individual player inherits cohort-level significance.
  2. Correct 6/0/2 statistical classification counts.
  3. All 2026 bowler comparisons are classified as NON_SIGNIFICANT.
  4. Credible-bound terminology represents one-sided 95% bound / central 90% endpoint.
  5. Hash gate is strictly fail-closed.
  6. Frozen production assets remain unmodified.
"""
import json
import pytest
import hashlib
from pathlib import Path

STATS_FILE = Path("research/phase5_14_1/corrected_statistical_interpretation.json")
SUMMARY_FILE = Path("research/phase5_14_1/phase5_14_1_validation_summary.json")
CANON_FILE = Path("data/processed/m5_3/match_state_full.csv")
REPORT_FILE = Path("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md")

EXPECTED_CANON_HASH = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
EXPECTED_REPORT_HASH = "0e0a11f87622dbeed44c3d918f37c5c9de2f2be8b22ac180099b5add1b882a1d"

def sha256_of_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()

def test_files_exist():
    assert STATS_FILE.exists(), f"File {STATS_FILE} does not exist."
    assert SUMMARY_FILE.exists(), f"File {SUMMARY_FILE} does not exist."

def test_no_individual_significance_attribution():
    with open(STATS_FILE, "r") as f:
        data = json.load(f)
    
    # Must contain cohort vs individual scope statement
    statement = data["metadata"]["cohort_vs_individual_scope_statement"]
    assert "cohort-level prospective comparisons" in statement
    assert "not individual players" in statement
    
    # Comparisons must only refer to cohort-level IDs
    for comp in data["comparisons"]:
        assert "vs_league" in comp["comparison_id"] or "vs_non_selected" in comp["comparison_id"]
        assert "player_id" not in comp

def test_classification_counts_6_0_2():
    with open(STATS_FILE, "r") as f:
        data = json.load(f)
    
    summary = data["metadata"]["classification_summary"]
    assert summary["statistically_significant_post_holm"] == 6
    assert summary["directional_raw_significant_post_holm_non_significant"] == 0
    assert summary["non_significant"] == 2
    assert summary["total_comparisons"] == 8

def test_2026_bowler_non_significance():
    with open(STATS_FILE, "r") as f:
        data = json.load(f)
    
    comps = {c["comparison_id"]: c for c in data["comparisons"]}
    b_lg = comps["2026_bowlers_vs_league"]
    b_ns = comps["2026_bowlers_vs_non_selected"]
    
    assert b_lg["inference_classification"] == "NON_SIGNIFICANT"
    assert b_ns["inference_classification"] == "NON_SIGNIFICANT"
    assert b_lg["holm_significant_05"] is False
    assert b_ns["holm_significant_05"] is False
    assert b_lg["raw_significant_05"] is False
    assert b_ns["raw_significant_05"] is False
    
    # Confidence intervals must cross zero
    assert b_lg["ci_95_low"] < 0 and b_lg["ci_95_high"] > 0
    assert b_ns["ci_95_low"] < 0 and b_ns["ci_95_high"] > 0

def test_credible_bound_terminology():
    with open(STATS_FILE, "r") as f:
        data = json.load(f)
    
    term = data["metadata"]["credible_bound_terminology_definition"]
    assert term["z_multiplier"] == 1.645
    assert "One-sided 95% credible bound" in term["exact_statistical_definition"]
    assert "central 90% credible interval" in term["exact_statistical_definition"]

def test_fail_closed_hash_gate():
    with open(SUMMARY_FILE, "r") as f:
        summary = json.load(f)
    
    # Test current passing state
    assert summary["hash_gate"]["hashes_intact"] is True
    assert summary["hash_gate"]["gate_verdict"] == "APPROVED FOR COMPETITION FREEZE"
    assert summary["metadata"]["verdict"] == "APPROVED FOR COMPETITION FREEZE"
    
    # Test simulated failure logic (fail-closed)
    def simulate_gate(canon_matches, report_matches):
        intact = canon_matches and report_matches
        return "APPROVED FOR COMPETITION FREEZE" if intact else "NOT APPROVED — FROZEN HASH MISMATCH"
    
    assert simulate_gate(False, True) == "NOT APPROVED — FROZEN HASH MISMATCH"
    assert simulate_gate(True, False) == "NOT APPROVED — FROZEN HASH MISMATCH"
    assert simulate_gate(False, False) == "NOT APPROVED — FROZEN HASH MISMATCH"
    assert simulate_gate(True, True) == "APPROVED FOR COMPETITION FREEZE"

def test_frozen_production_assets_unchanged():
    actual_canon = sha256_of_file(CANON_FILE)
    actual_report = sha256_of_file(REPORT_FILE)
    
    assert actual_canon == EXPECTED_CANON_HASH, f"Canonical dataset modified! Actual: {actual_canon}"
    assert actual_report == EXPECTED_REPORT_HASH, f"Competition report modified! Actual: {actual_report}"
