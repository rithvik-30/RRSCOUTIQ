"""
Unit Test: Production Ranking Equivalence
Verifies that Phase 5.11 rankings match official production ranking pipeline:
- Exact 100% identity for eligible batters
- Exact 100% roster and rank order identity for Top 10 bowlers
- Bounded numerical difference for bowlers (|diff| < 0.01 RPO)
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath("."))

def test_production_ranking_equivalence():
    results_path = "research/phase5_12/production_ranking_equivalence.json"
    assert os.path.exists(results_path), f"Missing {results_path}"

    with open(results_path, "r") as f:
        data = json.load(f)

    # 1. Batters
    bat = data["batters"]
    assert bat["eligible_count_ref"] == bat["eligible_count_p511"] == 66
    assert bat["max_abs_diff_val_add"] < 1e-9
    assert bat["max_abs_diff_se"] < 1e-9
    assert bat["max_abs_diff_lb90"] < 1e-9
    assert bat["max_rank_position_difference"] == 0

    # Verify all 10 batters match
    for row in bat["top10_comparison"]:
        assert row["ref_id"] == row["p511_id"]
        assert row["abs_diff_lb90"] < 1e-9

    # 2. Bowlers
    bowl = data["bowlers"]
    assert bowl["eligible_count_ref"] == bowl["eligible_count_p511"] == 64
    assert bowl["max_abs_diff_ub90"] < 0.01, f"Bowler UB90 diff exceeds tolerance: {bowl['max_abs_diff_ub90']}"

    # Verify exact Top 10 roster and ordering
    for row in bowl["top10_comparison"]:
        assert row["ref_id"] == row["p511_id"], f"Rank {row['rank']} mismatch: Ref {row['ref_id']} vs P511 {row['p511_id']}"
        assert row["abs_diff_ub90"] < 0.01
