"""
Phase 5.14.5.1 — Explicit Rank and Detailed Role Verification Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies Fix B:
1. Canonical selection baseline with all 20 players passes with 100% precision.
2. Deliberately removes a rank field -> fails.
3. Changes rank 3 to rank 4 -> fails.
4. Duplicates a rank -> fails.
5. Swaps two players -> fails.
6. Changes a player ID -> fails.
7. Changes a player name -> fails.
8. Changes a broad role -> fails.
9. Changes a detailed role -> fails (e.g. Batter cannot substitute for Top-Order Batter or Wicketkeeper-Batter).
10. Removes a required role field (role or detailed_role) -> fails.
11. Adds a duplicate player -> fails.
12. Adds an unexpected player -> fails.
13. Verifies that prospective_rankings.json (which lacks explicit rank and detailed_role) fails closed.
"""

import os
import sys
import copy
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    evaluate_selection_invariance,
    DEFAULT_SELECTION_PATH,
    FROZEN_EXPECTED_BATTERS,
    FROZEN_EXPECTED_BOWLERS,
)


@pytest.fixture
def canonical_selection_data():
    with open(DEFAULT_SELECTION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_canonical_baseline_passes_all_checks():
    """Verify that the official frozen selections pass all 20 players across all explicit fields."""
    res = evaluate_selection_invariance()
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert res["total_players_verified"] == 20
    assert len(res["failures"]) == 0
    assert len(res["batters"]) == 10
    assert len(res["bowlers"]) == 10

    for b in res["batters"]:
        assert b["rank_match"] is True
        assert b["id_match"] is True
        assert b["name_match"] is True
        assert b["role_match"] is True
        assert b["detailed_role_match"] is True
        assert b["order_match"] is True

    for bw in res["bowlers"]:
        assert bw["rank_match"] is True
        assert bw["id_match"] is True
        assert bw["name_match"] is True
        assert bw["role_match"] is True
        assert bw["detailed_role_match"] is True
        assert bw["order_match"] is True


def test_missing_rank_field_fails(tmp_path, canonical_selection_data):
    """Adversarial 1: Removing an explicit rank field must fail closed (no array fallback)."""
    data = copy.deepcopy(canonical_selection_data)
    del data["top10_batters"][0]["rank"]
    if "window_a" in data:
        del data["window_a"]["top10_batters"][0]["rank"]

    p = tmp_path / "missing_rank.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("missing required field 'rank'" in f or "rank mismatch" in f for f in res["failures"])


def test_change_rank_3_to_rank_4_fails(tmp_path, canonical_selection_data):
    """Adversarial 2: Changing rank 3 to rank 4 must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    data["top10_batters"][2]["rank"] = 4
    if "window_a" in data:
        data["window_a"]["top10_batters"][2]["rank"] = 4

    p = tmp_path / "rank_changed.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("rank mismatch" in f.lower() or "duplicate batter rank" in f.lower() for f in res["failures"])


def test_duplicate_rank_fails(tmp_path, canonical_selection_data):
    """Adversarial 3: Two players having the same rank must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    data["top10_bowlers"][1]["rank"] = data["top10_bowlers"][0]["rank"]
    if "window_a" in data:
        data["window_a"]["top10_bowlers"][1]["rank"] = data["window_a"]["top10_bowlers"][0]["rank"]

    p = tmp_path / "dup_rank.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("duplicate bowler rank detected" in f.lower() or "rank mismatch" in f.lower() for f in res["failures"])


def test_swapped_two_players_fails(tmp_path, canonical_selection_data):
    """Adversarial 4: Swapping positions of two players must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    b0 = data["top10_batters"][0]
    b1 = data["top10_batters"][1]
    data["top10_batters"][0] = b1
    data["top10_batters"][1] = b0
    if "window_a" in data:
        data["window_a"]["top10_batters"][0] = b1
        data["window_a"]["top10_batters"][1] = b0

    p = tmp_path / "swapped.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("mismatch at rank" in f or "ordering mismatch" in f or "rank mismatch" in f for f in res["failures"])


def test_change_player_id_fails(tmp_path, canonical_selection_data):
    """Adversarial 5: Changing player ID must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    data["top10_batters"][0]["player_id"] = 99999
    if "window_a" in data:
        data["window_a"]["top10_batters"][0]["player_id"] = 99999

    p = tmp_path / "changed_id.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("ID mismatch at rank 1" in f for f in res["failures"])


def test_change_player_name_fails(tmp_path, canonical_selection_data):
    """Adversarial 6: Changing player name must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    data["top10_bowlers"][0]["name"] = "Altered Narine"
    if "window_a" in data:
        data["window_a"]["top10_bowlers"][0]["name"] = "Altered Narine"

    p = tmp_path / "changed_name.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("Name mismatch at rank 1" in f for f in res["failures"])


def test_change_broad_role_fails(tmp_path, canonical_selection_data):
    """Adversarial 7: Changing broad role must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    data["top10_batters"][0]["role"] = "Bowler"
    if "window_a" in data:
        data["window_a"]["top10_batters"][0]["role"] = "Bowler"

    p = tmp_path / "changed_role.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("Role mismatch" in f for f in res["failures"])


def test_change_detailed_role_fails(tmp_path, canonical_selection_data):
    """
    Adversarial 8: Changing detailed role must fail verification.
    Verifying broad 'Batter' must NOT count as verifying 'Top-Order Batter' or 'Wicketkeeper-Batter'.
    """
    data = copy.deepcopy(canonical_selection_data)
    # Travis Head is 'Top-Order Batter', change to generic 'Batter' or 'Finisher'
    data["top10_batters"][1]["detailed_role"] = "Batter"
    if "window_a" in data:
        data["window_a"]["top10_batters"][1]["detailed_role"] = "Batter"

    p = tmp_path / "changed_detailed_role.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("Batter Detailed Role mismatch" in f for f in res["failures"])


def test_remove_required_detailed_role_field_fails(tmp_path, canonical_selection_data):
    """Adversarial 9: Removing required detailed_role field must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    del data["top10_batters"][3]["detailed_role"]
    if "window_a" in data:
        del data["window_a"]["top10_batters"][3]["detailed_role"]

    p = tmp_path / "missing_detailed_role.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("missing required field 'detailed_role'" in f for f in res["failures"])


def test_duplicate_player_fails(tmp_path, canonical_selection_data):
    """Adversarial 10: Adding a duplicate player must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    # Replace player at rank 10 with player at rank 1
    data["top10_batters"][9] = copy.deepcopy(data["top10_batters"][0])
    data["top10_batters"][9]["rank"] = 10
    if "window_a" in data:
        data["window_a"]["top10_batters"][9] = copy.deepcopy(data["top10_batters"][0])
        data["window_a"]["top10_batters"][9]["rank"] = 10

    p = tmp_path / "dup_player.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("Duplicate batter ID detected" in f or "Duplicate batter name detected" in f for f in res["failures"])


def test_unexpected_player_fails(tmp_path, canonical_selection_data):
    """Adversarial 11: Replacing a player with an unexpected outsider must fail verification."""
    data = copy.deepcopy(canonical_selection_data)
    data["top10_bowlers"][0] = {
        "rank": 1,
        "player_id": 999999,
        "name": "Unknown Mystery Bowler",
        "role": "Bowler",
        "detailed_role": "Mystery Spinner",
    }
    if "window_a" in data:
        data["window_a"]["top10_bowlers"][0] = copy.deepcopy(data["top10_bowlers"][0])

    p = tmp_path / "unexpected_player.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_selection_invariance(rankings_path=p)
    assert res["is_passed"] is False
    assert any("Bowler ID mismatch at rank 1" in f or "Bowler Name mismatch at rank 1" in f for f in res["failures"])


def test_prospective_rankings_fails_due_to_missing_fields():
    """Historical prospective_rankings.json lacks explicit 'rank' and 'detailed_role', so it must fail closed."""
    hist_path = Path("research/phase5_11/prospective_rankings.json")
    if hist_path.exists():
        res = evaluate_selection_invariance(rankings_path=hist_path)
        assert res["is_passed"] is False
        assert any("missing required field" in f for f in res["failures"])
