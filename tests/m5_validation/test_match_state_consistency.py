"""
Tests for M5.4 Match-State Reconstruction and Pressure Consistency.
"""

import numpy as np
import pytest
import pandas as pd


def test_pre_score_monotonicity(match_state_df: pd.DataFrame):
    """Verify pre-delivery score is strictly non-decreasing within every innings."""
    diffs = match_state_df.groupby(["match_id", "innings"])["pre_score"].diff()
    negative_deltas = (diffs < 0).sum()
    assert negative_deltas == 0, f"Found {negative_deltas} pre-score regressions within innings"


def test_legal_ball_progression_invariants(match_state_df: pd.DataFrame):
    """Verify legal balls bowled is non-decreasing and balls remaining is non-increasing."""
    bowled_diffs = match_state_df.groupby(["match_id", "innings"])["pre_legal_balls_bowled"].diff()
    rem_diffs = match_state_df.groupby(["match_id", "innings"])["pre_legal_balls_rem"].diff()

    bowled_regressions = (bowled_diffs < 0).sum()
    rem_increments = (rem_diffs > 0).sum()

    assert bowled_regressions == 0, f"Found {bowled_regressions} bowled ball regressions"
    assert rem_increments == 0, f"Found {rem_increments} balls remaining increments"


def test_chase_target_and_rrr_invariants(match_state_df: pd.DataFrame):
    """Verify target existence, runs required formula max(0, target-score), and RRR calculation."""
    chase = match_state_df[match_state_df["pre_innings_type"] == "Chase"]
    assert len(chase) == 85210

    # No null targets in chase
    assert chase["pre_target"].isna().sum() == 0, "Found null targets in chase innings"

    # Runs required arithmetic
    expected_runs_req = np.maximum(0, chase["pre_target"] - chase["pre_score"])
    runs_req_mismatches = (chase["pre_runs_required"] != expected_runs_req).sum()
    assert runs_req_mismatches == 0, f"Found {runs_req_mismatches} runs required arithmetic mismatches"

    # RRR formula check where pre_rrr is not null and balls_rem > 0
    valid_rrr = chase[(chase["pre_legal_balls_rem"] > 0) & (chase["pre_rrr"].notna())]
    expected_rrr = (valid_rrr["pre_runs_required"] / valid_rrr["pre_legal_balls_rem"]) * 6.0
    rrr_diff = np.abs(valid_rrr["pre_rrr"] - expected_rrr)
    assert (rrr_diff > 1e-4).sum() == 0, "Found RRR calculation formula discrepancies"


def test_pressure_tier_approved_m3_thresholds(match_state_df: pd.DataFrame):
    """Verify valid DLI deliveries map strictly to approved M3 pressure thresholds."""
    valid = match_state_df[match_state_df["is_dli_valid"] == True]
    assert len(valid) == 175676

    dli = valid["pre_dli"]
    tier = valid["pre_pressure_tier"]

    # Tier 1: Low (DLI < 0.90)
    t1_violations = ((tier == "Tier 1: Low") & (dli >= 0.90)).sum()
    # Tier 2: Medium (0.90 <= DLI < 1.35)
    t2_violations = ((tier == "Tier 2: Medium") & ((dli < 0.90) | (dli >= 1.35))).sum()
    # Tier 3: High (1.35 <= DLI < 2.25)
    t3_violations = ((tier == "Tier 3: High") & ((dli < 1.35) | (dli >= 2.25))).sum()
    # Tier 4: Extreme (DLI >= 2.25)
    t4_violations = ((tier == "Tier 4: Extreme") & (dli < 2.25)).sum()

    total_violations = t1_violations + t2_violations + t3_violations + t4_violations
    assert total_violations == 0, f"Found {total_violations} pressure-tier threshold violations"


def test_exclusion_and_super_over_semantics(match_state_df: pd.DataFrame):
    """Verify 4,161 excluded deliveries have NaN DLI/Tier and 26 Super Over deliveries have DLI 3.50/Tier 4: Extreme."""
    invalid = match_state_df[match_state_df["is_dli_valid"] == False]
    assert len(invalid) == 4161, f"Expected 4,161 excluded deliveries, got {len(invalid)}"

    # All invalid must have NaN DLI and NaN tier
    assert invalid["pre_dli"].notna().sum() == 0, "Found non-NaN DLI in excluded deliveries"
    assert invalid["pre_pressure_tier"].notna().sum() == 0, "Found non-null pressure tier in excluded deliveries"

    # Super Overs
    so = match_state_df[match_state_df["is_super_over"] == True]
    assert len(so) == 26, f"Expected 26 Super Over deliveries, got {len(so)}"
    assert (so["is_dli_valid"] == True).all(), "Super Over deliveries must have is_dli_valid == True"
    assert (so["pre_dli"] == 3.50).all(), "Super Over deliveries must have pre_dli == 3.50"
    assert (so["pre_pressure_tier"] == "Tier 4: Extreme").all(), "Super Over deliveries must have Tier 4: Extreme"
