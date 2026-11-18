"""
Unit Test: Temporal Integrity and Leakage Isolation
Verifies:
- 0 match ID overlap between training and test sets in Window A and Window B
- Strict chronological monotonicity: max(train_date) < min(test_date)
- Complete temporal isolation of all training statistics
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath("."))

def test_temporal_leakage_absence():
    audit_path = "research/phase5_12/temporal_leakage_audit.json"
    assert os.path.exists(audit_path), f"Missing {audit_path}"

    with open(audit_path, "r") as f:
        data = json.load(f)

    # Window A
    win_a = data["window_a"]
    assert win_a["match_id_overlap_count"] == 0, "Window A has match ID overlap!"
    assert win_a["strict_temporal_order"] is True, "Window A violates chronological monotonicity!"
    assert win_a["train_date_range"][1] < win_a["test_date_range"][0], "Train date exceeds test date in Window A!"

    # Window B
    win_b = data["window_b"]
    assert win_b["match_id_overlap_count"] == 0, "Window B has match ID overlap!"
    assert win_b["strict_temporal_order"] is True, "Window B violates chronological monotonicity!"
    assert win_b["train_date_range"][1] < win_b["test_date_range"][0], "Train date exceeds test date in Window B!"

    # Leakage checks
    for key, desc in data["leakage_checks"].items():
        assert "NONE" in desc, f"Leakage detected in {key}: {desc}"
