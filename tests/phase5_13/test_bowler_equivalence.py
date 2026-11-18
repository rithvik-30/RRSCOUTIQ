"""
Tests for Phase 5.13 Task 1: Bowler Numerical Equivalence
Verifies production equivalence between official ranking pipeline and Phase 5.11.
"""
import json
import pytest
from pathlib import Path

EQUIV_FILE = Path("research/phase5_13/final_numerical_equivalence.json")

def test_numerical_equivalence_file_exists():
    assert EQUIV_FILE.exists(), f"Equivalence file {EQUIV_FILE} does not exist."

def test_exact_production_equivalence_aligned():
    with open(EQUIV_FILE, "r") as f:
        data = json.load(f)
    
    aligned = data["phase_5_11_aligned_comparison"]
    assert aligned["exact_numerical_equivalence"] is True
    assert aligned["max_abs_diff_ub90_rpo"] < 1e-9
    assert aligned["max_abs_diff_mean_delta_rpo"] < 1e-9
    assert aligned["max_abs_diff_latent_se_rpo"] < 1e-9
    assert aligned["max_rank_position_difference"] == 0

def test_top10_cohort_identical_across_pipelines():
    with open(EQUIV_FILE, "r") as f:
        data = json.load(f)
    
    assert data["metadata"]["top10_cohort_identical"] is True
    assert len(data["metadata"]["top10_bowler_ids"]) == 10
    assert len(data["official_top10_bowlers"]) == 10
    
    # Official top 10 IDs check
    expected_top10_ids = [781, 4101, 2933, 4722, 7503, 2876, 8661, 152, 3644, 19316]
    actual_top10_ids = [b["player_id"] for b in data["official_top10_bowlers"]]
    assert actual_top10_ids == expected_top10_ids

def test_unaligned_pipeline_benign_bound():
    with open(EQUIV_FILE, "r") as f:
        data = json.load(f)
    
    unaligned = data["phase_5_11_unaligned_comparison"]
    assert unaligned["top10_cohort_affected"] is False
    assert unaligned["max_abs_diff_ub90_rpo"] < 0.01
