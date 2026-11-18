"""
RR ScoutIQ - Module M5.3: Match-State Zero-Leakage & Causality Test Suite
========================================================================

Negative and perturbation tests proving zero outcome leakage in M5.3.
Verifies that all pre-delivery features for delivery t depend strictly on
deliveries 1..t-1 and are completely invariant to the current delivery's outcomes.
"""

import os
import pytest
import numpy as np
import pandas as pd
from src.m5_state.match_state_engine import MatchStateEngine

ENRICHED_FULL_PATH = os.path.join("data", "enriched", "full", "enriched_ball_by_ball_full.csv")
MATCHES_PATH = os.path.join("data", "extracted", "matches.csv")


@pytest.fixture(scope="module")
def base_data():
    """Loads a deterministic sample match for perturbation testing."""
    enriched = pd.read_csv(ENRICHED_FULL_PATH, low_memory=False)
    matches = pd.read_csv(MATCHES_PATH)
    # Pick a standard clean match: match_id 13613
    sample_enriched = enriched[enriched["match_id"] == 13613].copy()
    sample_matches = matches[matches["match_id"] == 13613].copy()
    return sample_enriched, sample_matches


def test_outcome_leakage_runs_perturbation(base_data):
    """
    Negative test: Injecting runs into delivery t MUST NOT alter pre_score on delivery t.
    It should only affect pre_score on deliveries t+1 onwards in that innings,
    and propagate to Innings 2 chase target.
    """
    df_orig, matches = base_data
    engine = MatchStateEngine(matches_df=matches)
    baseline_res = engine.reconstruct_match_state(df_orig.copy())

    # Target an Innings 1 delivery: index 15
    inn1_mask = df_orig["innings"] == 1
    inn1_indices = np.where(inn1_mask)[0]
    target_idx = inn1_indices[15]

    perturbed_df = df_orig.copy()
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("runs")] += 6
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("ext_delivery_total_runs")] += 6

    perturbed_res = engine.reconstruct_match_state(perturbed_df)

    # 1. State at delivery t MUST be completely identical
    assert perturbed_res.iloc[target_idx]["pre_score"] == baseline_res.iloc[target_idx]["pre_score"], \
        "Outcome leakage detected: current delivery score leaked into pre_score!"
    assert perturbed_res.iloc[target_idx]["pre_dli"] == baseline_res.iloc[target_idx]["pre_dli"]

    # 2. State prior to delivery t MUST be identical
    pd.testing.assert_series_equal(
        perturbed_res.iloc[:target_idx]["pre_score"],
        baseline_res.iloc[:target_idx]["pre_score"]
    )

    # 3. State after delivery t within Innings 1 MUST increase by exactly 6 runs
    subsequent_inn1_indices = [idx for idx in inn1_indices if idx > target_idx]
    diff = (
        perturbed_res.iloc[subsequent_inn1_indices]["pre_score"]
        - baseline_res.iloc[subsequent_inn1_indices]["pre_score"]
    )
    assert (diff == 6).all(), "Score did not propagate correctly within the innings."

    # 4. State in Innings 2: pre_score resets to start from 0, but pre_target increases by 6
    inn2_mask = df_orig["innings"] == 2
    inn2_target_diff = (
        perturbed_res.loc[inn2_mask, "pre_target"]
        - baseline_res.loc[inn2_mask, "pre_target"]
    )
    assert (inn2_target_diff == 6).all(), "Innings 1 score addition did not update Innings 2 chase target."


def test_outcome_leakage_wicket_perturbation(base_data):
    """
    Negative test: Injecting a dismissal into delivery t MUST NOT alter pre_wickets_lost on delivery t.
    It should only increment pre_wickets_lost on deliveries t+1 onwards within the same innings.
    """
    df_orig, matches = base_data
    engine = MatchStateEngine(matches_df=matches)
    baseline_res = engine.reconstruct_match_state(df_orig.copy())

    # Target an Innings 1 delivery where no wicket fell: index 10
    inn1_mask = df_orig["innings"] == 1
    inn1_indices = np.where(inn1_mask)[0]
    target_idx = inn1_indices[10]

    perturbed_df = df_orig.copy()
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("is_wicket")] = True
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("ext_is_wicket")] = True

    perturbed_res = engine.reconstruct_match_state(perturbed_df)

    # 1. State at delivery t MUST be identical
    assert perturbed_res.iloc[target_idx]["pre_wickets_lost"] == baseline_res.iloc[target_idx]["pre_wickets_lost"], \
        "Outcome leakage detected: current delivery wicket leaked into pre_wickets_lost!"

    # 2. State after delivery t within Innings 1 MUST be incremented by 1
    subsequent_inn1_indices = [idx for idx in inn1_indices if idx > target_idx]
    diff = (
        perturbed_res.iloc[subsequent_inn1_indices]["pre_wickets_lost"]
        - baseline_res.iloc[subsequent_inn1_indices]["pre_wickets_lost"]
    )
    assert (diff == 1).all(), "Wicket did not propagate causally to subsequent deliveries in innings."

    # 3. Innings 2 boundary reset: Innings 2 starts with pre_wickets_lost == 0
    inn2_mask = df_orig["innings"] == 2
    assert (perturbed_res.loc[inn2_mask, "pre_wickets_lost"].iloc[0] == 0)


def test_outcome_leakage_legality_perturbation(base_data):
    """
    Negative test: Changing delivery t legality MUST NOT alter pre_legal_balls_bowled on delivery t.
    """
    df_orig, matches = base_data
    engine = MatchStateEngine(matches_df=matches)
    baseline_res = engine.reconstruct_match_state(df_orig.copy())

    target_idx = 8
    perturbed_df = df_orig.copy()
    # Turn a legal ball into a wide
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("ext_is_legal_delivery")] = False
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("ext_is_wide")] = True
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("ext_wide_runs")] = 1
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("ext_extra_runs")] = 1
    perturbed_df.iloc[target_idx, perturbed_df.columns.get_loc("ext_delivery_total_runs")] = 1

    perturbed_res = engine.reconstruct_match_state(perturbed_df)

    # 1. State at delivery t MUST be identical
    assert perturbed_res.iloc[target_idx]["pre_legal_balls_bowled"] == baseline_res.iloc[target_idx]["pre_legal_balls_bowled"], \
        "Outcome leakage detected: current delivery legality leaked into pre_legal_balls_bowled!"

    # 2. State at delivery t+1 MUST be 1 less because delivery t was converted to illegal
    assert perturbed_res.iloc[target_idx + 1]["pre_legal_balls_bowled"] == baseline_res.iloc[target_idx + 1]["pre_legal_balls_bowled"] - 1


def test_outcome_leakage_first_and_last_delivery(base_data):
    """
    Negative test on boundary deliveries:
    - First delivery (t=0): outcomes MUST NOT leak into initial score/wickets/balls (must remain 0).
    - Last delivery of Innings 1: runs propagate to Innings 2 chase target, but Innings 2 pre_score resets to 0.
    """
    df_orig, matches = base_data
    engine = MatchStateEngine(matches_df=matches)
    baseline_res = engine.reconstruct_match_state(df_orig.copy())

    # 1. First delivery of Innings 1 (index 0)
    p_first = df_orig.copy()
    p_first.iloc[0, p_first.columns.get_loc("runs")] += 4
    p_first.iloc[0, p_first.columns.get_loc("ext_delivery_total_runs")] += 4
    p_first.iloc[0, p_first.columns.get_loc("is_wicket")] = True
    p_first.iloc[0, p_first.columns.get_loc("ext_is_wicket")] = True
    p_first.iloc[0, p_first.columns.get_loc("ext_is_legal_delivery")] = False
    p_first.iloc[0, p_first.columns.get_loc("ext_is_wide")] = True
    res_first = engine.reconstruct_match_state(p_first)

    # Ball 0 pre-state MUST remain 0, 0, 0
    assert res_first.iloc[0]["pre_score"] == 0
    assert res_first.iloc[0]["pre_wickets_lost"] == 0
    assert res_first.iloc[0]["pre_legal_balls_bowled"] == 0
    assert res_first.iloc[0]["pre_dli"] == baseline_res.iloc[0]["pre_dli"]

    # Ball 1 must reflect the 4 runs, 1 wicket, but 0 legal balls (since wide)
    assert res_first.iloc[1]["pre_score"] == 4
    assert res_first.iloc[1]["pre_wickets_lost"] == 1
    assert res_first.iloc[1]["pre_legal_balls_bowled"] == 0

    # 2. Last delivery of Innings 1 (index 123)
    inn1_mask = df_orig["innings"] == 1
    last_inn1_idx = np.where(inn1_mask)[0][-1]
    p_last = df_orig.copy()
    p_last.iloc[last_inn1_idx, p_last.columns.get_loc("runs")] += 6
    p_last.iloc[last_inn1_idx, p_last.columns.get_loc("ext_delivery_total_runs")] += 6
    res_last = engine.reconstruct_match_state(p_last)

    # Ball 123 pre-state unchanged
    assert res_last.iloc[last_inn1_idx]["pre_score"] == baseline_res.iloc[last_inn1_idx]["pre_score"]
    # Innings 2 starts at ball 124: pre_score starts at 0, target increases by 6
    assert res_last.iloc[last_inn1_idx + 1]["pre_score"] == 0
    assert res_last.iloc[last_inn1_idx + 1]["pre_target"] == baseline_res.iloc[last_inn1_idx + 1]["pre_target"] + 6


def test_outcome_leakage_super_over_transition():
    """
    Negative test on Super Over deliveries (Match 34429):
    - Super Over deliveries start at score=0, wickets=0, legal_balls=0, fixed DLI = 3.50.
    - Perturbing delivery t outcomes does not leak into delivery t pre-state.
    """
    enriched = pd.read_csv(ENRICHED_FULL_PATH, low_memory=False)
    matches = pd.read_csv(MATCHES_PATH)
    sample_df = enriched[enriched["match_id"] == 34429].copy().reset_index(drop=True)

    engine = MatchStateEngine(matches_df=matches)
    baseline_res = engine.reconstruct_match_state(sample_df.copy())

    so_indices = np.where(sample_df["ext_is_super_over"])[0]
    first_so_idx = so_indices[0]

    # Verify baseline Super Over initial state
    assert baseline_res.iloc[first_so_idx]["pre_score"] == 0
    assert baseline_res.iloc[first_so_idx]["pre_wickets_lost"] == 0
    assert baseline_res.iloc[first_so_idx]["pre_legal_balls_bowled"] == 0
    assert baseline_res.iloc[first_so_idx]["pre_dli"] == 3.50
    assert baseline_res.iloc[first_so_idx]["pre_pressure_tier"] == "Tier 4: Extreme"

    # Perturb first Super Over delivery: +6 runs
    p_so = sample_df.copy()
    p_so.iloc[first_so_idx, p_so.columns.get_loc("runs")] += 6
    p_so.iloc[first_so_idx, p_so.columns.get_loc("ext_delivery_total_runs")] += 6
    res_so = engine.reconstruct_match_state(p_so)

    # Ball t remains uncorrupted
    assert res_so.iloc[first_so_idx]["pre_score"] == 0
    assert res_so.iloc[first_so_idx]["pre_dli"] == 3.50
    # Ball t+1 reflects the score change
    assert res_so.iloc[first_so_idx + 1]["pre_score"] == baseline_res.iloc[first_so_idx + 1]["pre_score"] + 6
    assert res_so.iloc[first_so_idx + 1]["pre_dli"] == 3.50

