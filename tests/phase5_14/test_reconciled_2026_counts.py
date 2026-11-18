"""
Tests for Phase 5.14 Task 2: Reconciled 2026 Match and Delivery Counts
Verifies exact match counts, delivery counts, and exclusions for the 2026 test season.
"""
import json
import pytest
from pathlib import Path

RECON_FILE = Path("research/phase5_14/corrected_match_reconciliation.json")

def test_2026_match_counts():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    s26 = data["2026"]
    assert s26["raw_matches_count"] == 134
    assert s26["dli_valid_matches_count"] == 126
    assert s26["clean_legal_matches_count"] == 126
    assert s26["pressure_contributing_matches_count"] == 126
    assert s26["zero_pressure_matches_count"] == 0
    assert s26["excluded_matches_count"] == 8

def test_2026_delivery_counts():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    s26 = data["2026"]
    assert s26["clean_legal_deliveries_count"] == 28243
    assert s26["pressure_deliveries_count"] == 24133
    assert s26["dli_valid_non_legal_deliveries_count"] == 1360
    assert s26["dli_valid_deliveries_count"] == 29603
    assert s26["raw_deliveries_count"] == 30816

def test_2026_excluded_matches():
    with open(RECON_FILE, "r") as f:
        data = json.load(f)
    
    s26 = data["2026"]
    expected_excluded_ids = [41851, 48610, 48611, 50137, 50190, 50371, 50408, 54711]
    assert sorted(s26["excluded_match_ids"]) == sorted(expected_excluded_ids)
    assert len(s26["excluded_matches_details"]) == 8
