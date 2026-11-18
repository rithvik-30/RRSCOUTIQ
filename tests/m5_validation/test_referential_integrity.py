"""
Tests for M5.4 Referential and Structural Integrity.
"""

import pytest
import pandas as pd


def test_schema_column_counts(enriched_df: pd.DataFrame, match_state_df: pd.DataFrame):
    """Verify enriched delivery dataset has 76 columns and match state has 95 columns."""
    assert len(enriched_df.columns) == 76, f"Expected 76 cols in enriched, got {len(enriched_df.columns)}"
    assert len(match_state_df.columns) == 95, f"Expected 95 cols in match state, got {len(match_state_df.columns)}"
    # Verify match_state_df contains all enriched columns
    assert set(enriched_df.columns).issubset(set(match_state_df.columns))


def test_total_row_count_and_one_to_one_alignment(enriched_df: pd.DataFrame, match_state_df: pd.DataFrame):
    """Verify exact 179,837 deliveries and 1-to-1 key alignment between enriched and state."""
    expected_rows = 179837
    assert len(enriched_df) == expected_rows
    assert len(match_state_df) == expected_rows

    key_enriched = enriched_df["match_id"].astype(str) + "_" + enriched_df["innings"].astype(str) + "_" + enriched_df["innings_ball_num"].astype(str)
    key_state = match_state_df["match_id"].astype(str) + "_" + match_state_df["innings"].astype(str) + "_" + match_state_df["innings_ball_num"].astype(str)
    assert (key_enriched == key_state).all(), "Delivery sequence mismatch between enriched and state files"


def test_primary_key_uniqueness(enriched_df: pd.DataFrame, match_state_df: pd.DataFrame):
    """Verify zero duplicate delivery keys across candidate unique combinations."""
    dup_over = enriched_df.duplicated(subset=["match_id", "innings", "overid", "over_ball_num"]).sum()
    dup_innings = enriched_df.duplicated(subset=["match_id", "innings", "innings_ball_num"]).sum()
    dup_state = match_state_df.duplicated(subset=["match_id", "innings", "innings_ball_num"]).sum()

    assert dup_over == 0, f"Found {dup_over} duplicate (match_id, innings, overid, over_ball_num)"
    assert dup_innings == 0, f"Found {dup_innings} duplicate (match_id, innings, innings_ball_num)"
    assert dup_state == 0, f"Found {dup_state} duplicate match state delivery keys"


def test_match_conservation(enriched_df: pd.DataFrame, match_state_df: pd.DataFrame):
    """Verify all 776 approved matches exist identically in both datasets."""
    matches_enriched = set(enriched_df["match_id"].unique())
    matches_state = set(match_state_df["match_id"].unique())

    assert len(matches_enriched) == 776, f"Expected 776 matches in enriched, got {len(matches_enriched)}"
    assert len(matches_state) == 776, f"Expected 776 matches in match state, got {len(matches_state)}"
    assert matches_enriched == matches_state, "Mismatch in match sets between enriched and match state"


def test_player_resolution_parity(enriched_df: pd.DataFrame, crosswalk_df: pd.DataFrame):
    """Verify all 852 unique active players in delivery logs are resolved in crosswalk."""
    strikers = set(enriched_df["striker_id"].dropna().unique())
    non_strikers = set(enriched_df["non_striker_id"].dropna().unique())
    bowlers = set(enriched_df["bowler_id"].dropna().unique())
    active_players = strikers.union(non_strikers).union(bowlers)

    assert len(active_players) == 852, f"Expected 852 unique active players, got {len(active_players)}"

    resolved_players = set(crosswalk_df["local_player_id"].dropna().unique())
    unresolved = active_players - resolved_players
    assert len(unresolved) == 0, f"Found {len(unresolved)} unresolved active players: {unresolved}"
