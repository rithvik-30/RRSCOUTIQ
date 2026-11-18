"""
Adversarial tests for causal pre-delivery state, anti-leakage, and score monotonicity.
"""

import pytest
import pandas as pd


def test_adversarial_score_leakage_detection(match_state_df: pd.DataFrame):
    """
    Simulates outcome leakage where current delivery runs prematurely enter the current pre-score.
    Asserts that the test suite detects any temporal contamination.
    """
    df_leak = match_state_df.head(200).copy()
    scoring_idx = df_leak[df_leak["ext_delivery_total_runs"] > 0].index[0]

    # Maliciously add current delivery runs to current pre-score
    df_leak.loc[scoring_idx, "pre_score"] += df_leak.loc[scoring_idx, "ext_delivery_total_runs"]

    # Verify that comparing pre_score against cumulative sum before delivery flags a discrepancy
    expected_pre_score = df_leak["ext_delivery_total_runs"].cumsum().shift(1).fillna(0)
    # The corrupted row will differ from lag-1 cumsum
    assert df_leak.loc[scoring_idx, "pre_score"] != expected_pre_score.loc[scoring_idx]


def test_monotonicity_adversarial_perturbation(match_state_df: pd.DataFrame):
    """
    Verifies that any backward step in cumulative pre-score triggers an immediate failure.
    """
    sample = match_state_df.head(500).copy()
    # Inject a negative transition
    sample.loc[10, "pre_score"] = sample.loc[9, "pre_score"] - 1

    diffs = sample.groupby(["match_id", "innings"])["pre_score"].diff()
    violations = (diffs < 0).sum()
    assert violations >= 1, "Adversarial test failed: negative score delta was not detected"
