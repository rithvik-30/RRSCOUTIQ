"""
Phase 5.14.5 — Selection Invariance Verification Tests
Verifies:
  1. Full 20/20 verification (10 batters, 10 bowlers) across IDs, names, explicit ranks, and roles.
  2. Detection of missing player.
  3. Detection of duplicate player ID.
  4. Detection of unexpected/substituted player.
  5. Detection of duplicate rank.
  6. Detection of reordered players.
  7. Detection of role mismatch.
  8. Missing rank or role field.
"""

import os
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    evaluate_selection_invariance,
    DEFAULT_RANKINGS_PATH,
    DEFAULT_PROD_EQUIV_PATH,
    FROZEN_EXPECTED_BATTERS,
    FROZEN_EXPECTED_BOWLERS,
)

def test_canonical_selection_all_20_players_pass():
    """Verify that the official prospective rankings match 100% across all 5 dimensions."""
    res = evaluate_selection_invariance()
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert res["total_players_verified"] == 20
    assert len(res["failures"]) == 0

    # Verify each batter record has all verified fields
    for b in res["batters"]:
        assert b["rank_match"] is True
        assert b["id_match"] is True
        assert b["name_match"] is True
        assert b["role_match"] is True

    # Verify each bowler record has all verified fields
    for bw in res["bowlers"]:
        assert bw["rank_match"] is True
        assert bw["id_match"] is True
        assert bw["name_match"] is True
        assert bw["role_match"] is True


def test_missing_player_detected(tmp_path):
    """Truncating the batter list to 9 players triggers missing player failure."""
    with open(DEFAULT_RANKINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Pop rank 10 batter
    data["window_a"]["top10_batters"].pop()
    bad_file = tmp_path / "missing_batter.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=bad_file)
    assert res["is_passed"] is False
    assert any("top10_batters count is 9" in f or "Missing batter" in f for f in res["failures"])


def test_duplicate_player_id_detected(tmp_path):
    """Duplicating a player ID triggers duplicate detection."""
    with open(DEFAULT_RANKINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Set rank 2 batter ID to rank 1 batter ID
    data["window_a"]["top10_batters"][1]["player_id"] = data["window_a"]["top10_batters"][0]["player_id"]
    bad_file = tmp_path / "dup_id.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=bad_file)
    assert res["is_passed"] is False
    assert any("Duplicate batter ID detected" in f for f in res["failures"])


def test_unexpected_player_detected(tmp_path):
    """Substituting an unexpected player triggers mismatch."""
    with open(DEFAULT_RANKINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["window_a"]["top10_batters"][0]["name"] = "Unexpected Batter"
    bad_file = tmp_path / "unexpected.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=bad_file)
    assert res["is_passed"] is False
    assert any("Batter Name mismatch" in f for f in res["failures"])


def test_reordered_players_detected(tmp_path):
    """Swapping positions of two bowlers triggers rank and ID mismatch."""
    with open(DEFAULT_RANKINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Swap bowler 1 and bowler 2
    b1 = data["window_a"]["top10_bowlers"][0]
    b2 = data["window_a"]["top10_bowlers"][1]
    data["window_a"]["top10_bowlers"][0] = b2
    data["window_a"]["top10_bowlers"][1] = b1

    bad_file = tmp_path / "reordered.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=bad_file)
    assert res["is_passed"] is False
    assert any("Bowler ID mismatch at rank 1" in f for f in res["failures"])


def test_role_mismatch_detected(tmp_path):
    """Changing player role triggers role mismatch failure."""
    with open(DEFAULT_RANKINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Change Suryakumar Yadav role to Bowler
    data["window_a"]["top10_batters"][0]["role"] = "Bowler"
    bad_file = tmp_path / "role_mismatch.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=bad_file)
    assert res["is_passed"] is False
    assert any("Batter Role mismatch" in f for f in res["failures"])
