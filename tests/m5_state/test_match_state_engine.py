"""
RR ScoutIQ - Module M5.3: Match-State Reconstruction Test Suite
==============================================================

Automated regression test suite for Milestone M5.3.
Validates:
1. Exact row count (179,837 deliveries across 776 matches).
2. Initial innings state invariants (score=0, wkt=0, balls=0, crr=NaN).
3. Monotonicity of pre-delivery cumulative runs and wickets.
4. Legal ball counting progression strictly on ext_is_legal_delivery.
5. Balls remaining non-negativity.
6. Chase target and RRR reconstruction.
7. Super Over separation with fixed DLI = 3.50.
8. DLS and shortened match exclusion logic.
9. Pressure tier cutoffs and distribution validity.
10. Quarantine enforcement.
"""

import os
import pytest
import numpy as np
import pandas as pd

STATE_CSV_PATH = os.path.join("data", "processed", "m5_3", "match_state_full.csv")
VAL_CSV_PATH = os.path.join("data", "processed", "m5_3", "match_state_validation_summary.csv")
EXCL_CSV_PATH = os.path.join("data", "processed", "m5_3", "match_state_exclusion_register.csv")
SUMMARY_CSV_PATH = os.path.join("data", "processed", "m5_3", "match_state_match_summary.csv")


@pytest.fixture(scope="module")
def state_df():
    """Loads reconstructed match state dataset."""
    assert os.path.exists(STATE_CSV_PATH), f"File {STATE_CSV_PATH} not found. Run pipeline first."
    return pd.read_csv(STATE_CSV_PATH, low_memory=False)


def test_row_and_match_counts(state_df):
    """Invariant 1: Exactly 179,837 deliveries across 776 matches."""
    assert len(state_df) == 179837, f"Expected 179,837 rows, got {len(state_df)}"
    assert state_df["match_id"].nunique() == 776, f"Expected 776 matches, got {state_df['match_id'].nunique()}"


def test_no_duplicate_delivery_keys(state_df):
    """Invariant 2: No duplicate primary delivery keys."""
    dups = state_df.duplicated(subset=["match_id", "innings", "overid", "over_ball_num"]).sum()
    assert dups == 0, f"Found {dups} duplicate delivery keys."


def test_initial_innings_boundary_resets(state_df):
    """Invariant 3: Initial ball in every innings has pre_score=0, pre_wickets_lost=0, pre_legal_balls=0."""
    first_balls = (
        state_df.sort_values(["match_id", "innings", "overid", "over_ball_num", "innings_ball_num"])
        .groupby(["match_id", "innings"])
        .nth(0)
        .reset_index()
    )
    assert (first_balls["pre_score"] == 0).all()
    assert (first_balls["pre_wickets_lost"] == 0).all()
    assert (first_balls["pre_legal_balls_bowled"] == 0).all()
    assert first_balls["pre_crr"].isna().all()


def test_monotonicity_of_runs_and_wickets(state_df):
    """Invariant 4 & 5: Pre-delivery score and wickets lost never decrease within an innings."""
    for (mid, inn), grp in state_df.groupby(["match_id", "innings"]):
        score_diffs = np.diff(grp["pre_score"].values)
        assert np.all(score_diffs >= 0), f"Match {mid} Inn {inn} has decreasing pre_score: {score_diffs[score_diffs < 0]}"
        wkt_diffs = np.diff(grp["pre_wickets_lost"].values)
        assert np.all(wkt_diffs >= 0), f"Match {mid} Inn {inn} has decreasing pre_wickets_lost: {wkt_diffs[wkt_diffs < 0]}"


def test_legal_ball_progression(state_df):
    """Invariant 6: pre_legal_balls_bowled increments if and only if prior delivery was legal."""
    # Test on a deterministic sample of matches
    sample_mids = [13613, 14130, 14164, 21176, 34429, 40725]
    sample_df = state_df[state_df["match_id"].isin(sample_mids)]
    for (mid, inn), grp in sample_df.groupby(["match_id", "innings"]):
        b_vals = grp["pre_legal_balls_bowled"].values
        is_leg = grp["ext_is_legal_delivery"].values
        expected_next = b_vals[:-1] + is_leg[:-1].astype(int)
        assert np.array_equal(b_vals[1:], expected_next)


def test_balls_remaining_non_negative(state_df):
    """Invariant 7: Balls remaining never negative."""
    assert (state_df["pre_legal_balls_rem"] >= 0).all()


def test_super_over_separation(state_df):
    """Invariant 8: Super Overs have 26 deliveries across 4 matches with fixed DLI = 3.50."""
    so_df = state_df[state_df["is_super_over"]]
    assert len(so_df) == 26
    assert set(so_df["match_id"].unique()) == {34429, 40725, 45512, 50359}
    assert (so_df["pre_dli"] == 3.50).all()
    assert (so_df["pre_match_phase"] == "Super Over").all()
    assert (so_df["pre_pressure_tier"] == "Tier 4: Extreme").all()


def test_chase_targets_and_rrr(state_df):
    """Invariant 9: Unshortened regulation chases have targets and valid non-negative RRR."""
    chase_df = state_df[(state_df["innings"] == 2) & (~state_df["is_shortened_match"]) & (~state_df["is_dls_match"])]
    assert chase_df["pre_target"].notna().all()
    assert (chase_df["pre_rrr"] >= 0).all()


def test_dls_and_shortened_exclusions(state_df):
    """Invariant 10: DLS chases and shortened matches are flagged as invalid DLI with null DLI & tier."""
    dls_chase = state_df[state_df["is_dls_match"] & (state_df["innings"] == 2)]
    assert (~dls_chase["is_dli_valid"]).all()
    assert dls_chase["pre_rrr"].isna().all()
    assert dls_chase["pre_dli"].isna().all()
    assert dls_chase["pre_pressure_tier"].isna().all()
    assert (dls_chase["dli_exclusion_reason"] == "DLS_REVISED_TARGET_UNAVAILABLE_TIMING").all()

    shortened = state_df[state_df["is_shortened_match"]]
    assert (~shortened["is_dli_valid"]).all()
    assert shortened["pre_dli"].isna().all()
    assert shortened["pre_pressure_tier"].isna().all()
    assert (shortened["pre_match_phase"] == "Shortened Match").all()


def test_pressure_tier_thresholds(state_df):
    """Invariant 11: Pressure tiers adhere strictly to approved cutoff boundaries with null for invalid."""
    valid_dli = state_df[state_df["is_dli_valid"]]
    t1 = valid_dli[valid_dli["pre_pressure_tier"] == "Tier 1: Low"]
    t2 = valid_dli[valid_dli["pre_pressure_tier"] == "Tier 2: Medium"]
    t3 = valid_dli[valid_dli["pre_pressure_tier"] == "Tier 3: High"]
    t4 = valid_dli[valid_dli["pre_pressure_tier"] == "Tier 4: Extreme"]

    assert (t1["pre_dli"] < 0.90).all()
    assert ((t2["pre_dli"] >= 0.90) & (t2["pre_dli"] < 1.35)).all()
    assert ((t3["pre_dli"] >= 1.35) & (t3["pre_dli"] < 2.25)).all()
    assert (t4["pre_dli"] >= 2.25).all()

    # All invalid observations must have null pressure tier and null DLI
    invalid_dli = state_df[~state_df["is_dli_valid"]]
    assert invalid_dli["pre_dli"].isna().all()
    assert invalid_dli["pre_pressure_tier"].isna().all()


def test_quarantine_enforcement(state_df):
    """Invariant 12: Quarantined matches are completely absent."""
    quarantined = [32618, 37349, 37352, 46250, 50504]
    assert state_df["match_id"].isin(quarantined).sum() == 0
