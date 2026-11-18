"""
Tests for Phase 5.13 Task 3: Holm-Bonferroni Step-Down Correction
Verifies monotonicity, hypothesis ranking, and valid inferential statistics.
"""
import json
import pytest
from pathlib import Path

HOLM_FILE = Path("research/phase5_13/holm_adjusted_results.json")
BOOT_FILE = Path("research/phase5_13/independently_verified_bootstrap.json")

def test_holm_and_bootstrap_files_exist():
    assert HOLM_FILE.exists(), f"File {HOLM_FILE} does not exist."
    assert BOOT_FILE.exists(), f"File {BOOT_FILE} does not exist."

def test_bootstrap_replications_and_centering():
    with open(BOOT_FILE, "r") as f:
        data = json.load(f)
    
    assert data["metadata"]["replications"] == 10000
    assert data["metadata"]["resampling_unit"] == "match_id (match-clustered)"
    assert len(data["comparisons"]) == 8
    for comp in data["comparisons"]:
        assert comp["null_centered"] is True
        assert comp["p_value_two_sided"] >= 1.0 / 10001
        assert comp["ci_95_low"] < comp["ci_95_high"]

def test_holm_monotonicity():
    with open(HOLM_FILE, "r") as f:
        data = json.load(f)
    
    assert data["metadata"]["monotonicity_verified"] is True
    comps = data["ranked_comparisons"]
    assert len(comps) == 8
    
    adj_p = [c["holm_adjusted_p"] for c in comps]
    for i in range(len(adj_p) - 1):
        assert adj_p[i] <= adj_p[i+1], f"Monotonicity violation at index {i}: {adj_p[i]} > {adj_p[i+1]}"

def test_inference_classifications():
    with open(HOLM_FILE, "r") as f:
        data = json.load(f)
    
    summary = data["metadata"]["summary_counts"]
    # 6 statistically significant post-Holm, 0 directional only, 2 non-significant post-Holm
    assert summary["statistically_significant_post_holm"] == 6
    assert summary["non_significant"] == 2
    
    # 2026 Bowlers must NOT be called statistically significant post-Holm
    comps = {c["comparison_id"]: c for c in data["ranked_comparisons"]}
    assert comps["2026_bowlers_vs_league"]["holm_significant_05"] is False
    assert comps["2026_bowlers_vs_non_selected"]["holm_significant_05"] is False
    
    # All batter comparisons must be statistically significant post-Holm
    assert comps["2025_batters_vs_league"]["holm_significant_05"] is True
    assert comps["2025_batters_vs_non_selected"]["holm_significant_05"] is True
    assert comps["2026_batters_vs_league"]["holm_significant_05"] is True
    assert comps["2026_batters_vs_non_selected"]["holm_significant_05"] is True
