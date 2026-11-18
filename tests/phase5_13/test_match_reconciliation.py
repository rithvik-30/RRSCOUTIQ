"""
Tests for Phase 5.13 Task 2: Match Count Reconciliation
Verifies exact match counts between raw, clean, legal, and pressure deliveries.
"""
import json
import pytest
from pathlib import Path

RECON_FILE = Path("research/phase5_13/final_match_reconciliation.json")

def test_match_reconciliation_file_exists():
    assert RECON_FILE.exists(), f"Reconciliation file {RECON_FILE} does not exist."

def test_season_2025_match_counts():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    s25 = data["2025"]
    assert s25["dli_valid_matches_count"] == 173
    assert s25["clean_legal_matches_count"] == 173
    assert s25["pressure_matches_count"] == 172
    assert s25["discrepant_matches_count"] == 1
    assert s25["discrepant_matches"][0]["match_id"] == 41979
    assert s25["total_pressure_deliveries"] == 32332

def test_season_2026_match_counts():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    s26 = data["2026"]
    assert s26["dli_valid_matches_count"] == 126
    assert s26["clean_legal_matches_count"] == 126
    assert s26["pressure_matches_count"] == 126
    assert s26["discrepant_matches_count"] == 0
    assert s26["total_pressure_deliveries"] == 24133

def test_root_cause_explanation():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    assert "explanation" in data
    assert data["2025"]["discrepant_matches"][0]["match_id"] == 41979
