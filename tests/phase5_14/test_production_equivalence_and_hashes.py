"""
Tests for Phase 5.14 Task 5 & Task 8: Production Equivalence Verification & Final Freeze Hashes
Verifies exact reproduction of production values, Top 10 cohort invariance, and integrity of frozen files.
"""
import json
import pytest
import hashlib
from pathlib import Path

PROD_FILE = Path("research/phase5_14/production_equivalence_verification.json")
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

def test_production_equivalence_file_exists():
    assert PROD_FILE.exists(), f"File {PROD_FILE} does not exist."

def test_exact_numerical_equivalence():
    with open(PROD_FILE, "r") as f:
        data = json.load(f)
    
    # Batters
    bat = data["batters_equivalence"]
    assert bat["max_abs_diff_value_add"] < 1e-9
    assert bat["max_abs_diff_latent_se"] < 1e-9
    assert bat["max_abs_diff_lb90"] < 1e-9
    assert bat["max_rank_position_difference"] == 0
    assert bat["top10_cohort_identical"] is True
    
    # Aligned Bowlers
    bowl_aligned = data["bowlers_equivalence"]["aligned_implementation"]
    assert bowl_aligned["exact_numerical_equivalence"] is True
    assert bowl_aligned["max_abs_diff_posterior_delta_rpo"] < 1e-9
    assert bowl_aligned["max_abs_diff_latent_se_rpo"] < 1e-9
    assert bowl_aligned["max_abs_diff_ub90_rpo"] < 1e-9
    assert bowl_aligned["max_rank_position_difference"] == 0
    assert bowl_aligned["top10_cohort_identical"] is True

def test_official_top10_identities():
    with open(PROD_FILE, "r") as f:
        data = json.load(f)
    
    expected_top10_batters = [
        "Suryakumar Yadav", "Travis Head", "Yashasvi Jaiswal", "Sanju Samson",
        "Abhishek Sharma", "Andre Russell", "Phil Salt", "Glenn Maxwell",
        "Jos Buttler", "Ruturaj Gaikwad"
    ]
    expected_top10_bowlers = [
        "Sunil Narine", "Mitchell Santner", "Jasprit Bumrah", "Rashid Khan",
        "Ravi Bishnoi", "Axar Patel", "Matheesha Pathirana", "Ravindra Jadeja",
        "Kuldeep Yadav", "Maheesh Theekshana"
    ]
    assert data["official_top10_players"]["batters"] == expected_top10_batters
    assert data["official_top10_players"]["bowlers"] == expected_top10_bowlers

def test_frozen_dataset_hash():
    actual_hash = sha256_of_file(CANON_FILE)
    assert actual_hash == EXPECTED_CANON_HASH, (
        f"CRITICAL: Canonical dataset hash mismatch! Actual: {actual_hash}, Expected: {EXPECTED_CANON_HASH}"
    )

def test_frozen_competition_report_hash():
    actual_hash = sha256_of_file(REPORT_FILE)
    assert actual_hash == EXPECTED_REPORT_HASH, (
        f"CRITICAL: Competition report hash mismatch! Actual: {actual_hash}, Expected: {EXPECTED_REPORT_HASH}"
    )
