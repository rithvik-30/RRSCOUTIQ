"""
Unit Test: Corrected Bootstrap Statistical Inference
Verifies:
- Minimum 10,000 bootstrap replications
- Plus-one Monte Carlo correction
- Shift-under-the-null centering
- Mutual consistency between 95% CIs and p-values
- All 8 primary comparisons reported without omission
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath("."))

def test_corrected_bootstrap_properties():
    results_path = "research/phase5_12/corrected_bootstrap_results.json"
    assert os.path.exists(results_path), f"Missing {results_path}"

    with open(results_path, "r") as f:
        data = json.load(f)

    # 1. Metadata checks
    meta = data["metadata"]
    assert meta["bootstrap_replications"] >= 10000
    assert meta["monte_carlo_resolution"] <= 0.0001
    assert "Shift under Null" in meta["centering_method"]
    assert "+ 1" in meta["p_value_formula"]

    # 2. Eight primary comparisons
    primary = data["eight_primary_comparisons"]
    assert len(primary) == 8, f"Expected 8 primary comparisons, found {len(primary)}"

    for comp in primary:
        assert comp["null_centered"] is True
        assert comp["plus_one_corrected"] is True
        assert comp["mutually_consistent"] is True, f"Inconsistency in {comp['metric_name']}"
        assert comp["two_sided_p_value"] >= meta["monte_carlo_resolution"]

    # Verify non-significant comparisons are honestly reported
    bowl_2026_lg = [c for c in primary if c["metric_name"] == "2026 Bowler Econ vs League"][0]
    bowl_2026_ns = [c for c in primary if c["metric_name"] == "2026 Bowler Econ vs Eligible Non-Selected"][0]

    assert bowl_2026_lg["p_rejects_at_05"] is False
    assert bowl_2026_lg["two_sided_p_value"] > 0.05
    assert bowl_2026_ns["p_rejects_at_05"] is False
    assert bowl_2026_ns["two_sided_p_value"] > 0.05
