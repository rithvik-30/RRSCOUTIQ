"""
Tests for Phase 5.14 Task 1: Reconciled 2025 Match ID
Verifies that the zero-pressure match is dynamically and accurately identified as 41979.
"""
import json
import pytest
import pandas as pd
from pathlib import Path

RECON_FILE = Path("research/phase5_14/corrected_match_reconciliation.json")

def test_reconciliation_file_exists():
    assert RECON_FILE.exists(), f"File {RECON_FILE} does not exist."

def test_zero_pressure_match_identity():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    s25 = data["2025"]
    assert s25["zero_pressure_matches_count"] == 1
    assert s25["zero_pressure_match_ids"] == [41979]
    
    details = s25["zero_pressure_matches_details"][0]
    assert details["match_id"] == 41979
    assert details["total_deliveries"] == 29
    assert details["legal_deliveries"] == 29
    assert details["pressure_deliveries"] == 0
    assert details["tier_distribution"] == {"Tier 1: Low": 29}
    assert details["match_date"] == "2025-11-08"

def test_no_hardcoded_ghost_match_43815():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    # 43815 must never be in zero pressure match IDs
    assert 43815 not in data["2025"]["zero_pressure_match_ids"]
    assert 43815 not in data["2026"]["zero_pressure_match_ids"]
    
    # Check canonical dataset directly
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    assert len(raw[raw["match_id"] == 43815]) == 0

def test_2025_overall_counts():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    s25 = data["2025"]
    assert s25["raw_matches_count"] == 182
    assert s25["dli_valid_matches_count"] == 173
    assert s25["clean_legal_matches_count"] == 173
    assert s25["pressure_contributing_matches_count"] == 172
    assert s25["clean_legal_deliveries_count"] == 38214
    assert s25["pressure_deliveries_count"] == 32332
    assert s25["excluded_matches_count"] == 9
