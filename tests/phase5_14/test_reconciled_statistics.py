"""
Tests for Phase 5.14 Task 3 & Task 4: Reconciled Statistical Results & Bootstrap Methodology
Verifies confidence interval consistency, Holm-Bonferroni ordering, and accurate classification.
"""
import json
import pytest
from pathlib import Path

STATS_FILE = Path("research/phase5_14/corrected_statistical_results.json")
BOOT_FILE = Path("research/phase5_13/independently_verified_bootstrap.json")

def test_statistical_results_file_exists():
    assert STATS_FILE.exists(), f"File {STATS_FILE} does not exist."

def test_confidence_interval_and_stats_harmony():
    with open(STATS_FILE, "r") as f:
        s_data = json.load(f)
    with open(BOOT_FILE, "r") as f:
        b_data = json.load(f)
    
    boot_map = {c["id"]: c for c in b_data["comparisons"]}
    assert len(s_data["comparisons"]) == 8
    
    for c in s_data["comparisons"]:
        cid = c["comparison_id"]
        b = boot_map[cid]
        assert abs(c["observed_effect"] - b["observed_diff"]) < 1e-9
        assert abs(c["bootstrap_standard_error"] - b["standard_error"]) < 1e-9
        assert abs(c["ci_95_low"] - b["ci_95_low"]) < 1e-9
        assert abs(c["ci_95_high"] - b["ci_95_high"]) < 1e-9
        assert abs(c["raw_p_value"] - b["p_value_two_sided"]) < 1e-9

def test_holm_monotonicity_and_step_down():
    with open(STATS_FILE, "r") as f:
        s_data = json.load(f)
    
    comps = s_data["comparisons"]
    assert s_data["metadata"]["monotonicity_verified"] is True
    
    for i in range(len(comps) - 1):
        assert comps[i]["holm_adjusted_p"] <= comps[i+1]["holm_adjusted_p"], (
            f"Monotonicity violation between rank {comps[i]['rank']} and {comps[i+1]['rank']}"
        )
    
    # Verify multiplier countdown
    for i, c in enumerate(comps):
        assert c["holm_multiplier"] == 8 - i

def test_inference_classification_accuracy():
    with open(STATS_FILE, "r") as f:
        s_data = json.load(f)
    
    summary = s_data["metadata"]["summary_counts"]
    assert summary["statistically_significant_post_holm"] == 6
    assert summary["non_significant"] == 2
    
    comp_map = {c["comparison_id"]: c for c in s_data["comparisons"]}
    
    # Batters must be statistically significant
    assert comp_map["2025_batters_vs_league"]["holm_significant_05"] is True
    assert comp_map["2025_batters_vs_non_selected"]["holm_significant_05"] is True
    assert comp_map["2026_batters_vs_league"]["holm_significant_05"] is True
    assert comp_map["2026_batters_vs_non_selected"]["holm_significant_05"] is True
    
    # 2025 Bowlers must be statistically significant
    assert comp_map["2025_bowlers_vs_league"]["holm_significant_05"] is True
    assert comp_map["2025_bowlers_vs_non_selected"]["holm_significant_05"] is True
    
    # 2026 Bowlers must NOT be statistically significant post-Holm
    assert comp_map["2026_bowlers_vs_league"]["holm_significant_05"] is False
    assert comp_map["2026_bowlers_vs_non_selected"]["holm_significant_05"] is False
    assert comp_map["2026_bowlers_vs_league"]["holm_adjusted_p"] > 0.05
    assert comp_map["2026_bowlers_vs_non_selected"]["holm_adjusted_p"] > 0.05
