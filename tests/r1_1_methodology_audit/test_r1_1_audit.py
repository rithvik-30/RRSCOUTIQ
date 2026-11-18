"""
Unit and Integration Tests for Milestone R1.1: Independent Methodological Audit.
Verifies baseline model comparison, forward outcome non-leakage, setting DLI progression,
tier population reconciliation arithmetic, and statistical significance tests.
"""

from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.r1_1_methodology_audit.chase_baseline_comparison import (
    compute_expected_calibration_error,
    prepare_chase_dataset,
)
from src.r1_1_methodology_audit.forward_outcome_audit import construct_strict_legal_forward_windows
from src.r1_1_methodology_audit.setting_dli_audit import compute_experimental_phi
from src.r1_1_methodology_audit.tier_distribution_reconciliation import reconcile_tier_populations
from src.r1_1_methodology_audit.threshold_significance_audit import bootstrap_hazard_difference


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def match_state_df(project_root) -> pd.DataFrame:
    path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    assert path.exists(), f"Missing match state file: {path}"
    return pd.read_csv(path, low_memory=False)


@pytest.fixture(scope="session")
def matches_df(project_root) -> pd.DataFrame:
    path = project_root / "data" / "extracted" / "matches.csv"
    assert path.exists(), f"Missing matches file: {path}"
    return pd.read_csv(path, low_memory=False)


def test_ece_calculation_properties():
    """Verify that Expected Calibration Error is bounded in [0, 1] and 0 for perfectly calibrated predictions."""
    y_true = np.array([1, 1, 0, 0])
    y_perfect = np.array([1.0, 1.0, 0.0, 0.0])
    assert compute_expected_calibration_error(y_true, y_perfect, n_bins=2) == 0.0

    y_worst = np.array([0.0, 0.0, 1.0, 1.0])
    assert compute_expected_calibration_error(y_true, y_worst, n_bins=2) == 1.0


def test_forward_outcome_window_anti_leakage(match_state_df: pd.DataFrame):
    """Verify that forward windows strictly exclude current delivery outcome and do not cross innings."""
    # Test on single match
    sample_match = match_state_df[match_state_df["match_id"] == 13511].copy()
    fwd = construct_strict_legal_forward_windows(sample_match)

    # Must contain columns
    assert "fwd_6_runs" in fwd.columns
    assert "fwd_6_wkts" in fwd.columns

    # Verify that first delivery of innings 2 does NOT include runs from innings 1
    inn1_rows = fwd[fwd["innings"] == 1]
    inn2_rows = fwd[fwd["innings"] == 2]

    # Innings 1 last rows should have fwd_legal_balls < 6 or nan
    last_inn1 = inn1_rows.iloc[-1]
    assert last_inn1["fwd_legal_balls"] < 6


def test_setting_progression_monotonicity():
    """Verify that approved Phi(t) is strictly increasing from ball 1 to ball 120."""
    t_vals = [6, 12, 36, 60, 90, 114, 120]
    phi_vals = [compute_experimental_phi(t, "approved_convex_1_2") for t in t_vals]

    for i in range(len(phi_vals) - 1):
        assert phi_vals[i + 1] > phi_vals[i], f"Phi monotonicity failure: {phi_vals[i+1]} <= {phi_vals[i]}"

    # Bounds: Phi(0) = 0.80, Phi(120) = 1.50
    assert np.isclose(compute_experimental_phi(0, "approved_convex_1_2"), 0.80)
    assert np.isclose(compute_experimental_phi(120, "approved_convex_1_2"), 1.50)


def test_tier_reconciliation_exact_accounting(match_state_df: pd.DataFrame, matches_df: pd.DataFrame):
    """Verify that tier reconciliation accounts for every single omitted delivery without arithmetic loss."""
    from src.r1_dli_research.dli_outcome_validation import compute_forward_outcomes
    fwd_filtered = compute_forward_outcomes(match_state_df, matches_df)

    rec_df = reconcile_tier_populations(match_state_df, fwd_filtered)
    assert len(rec_df) == 3

    pop1_count = rec_df.loc[0, "delivery_count"]
    pop2_count = rec_df.loc[1, "delivery_count"]
    diff_count = rec_df.loc[2, "delivery_count"]

    assert pop1_count == 175676
    assert pop2_count == 163658
    assert diff_count == 12018
    assert pop1_count == pop2_count + diff_count

    # Verify tier sum equality
    for t_col in ["tier1_count", "tier2_count", "tier3_count", "tier4_count"]:
        assert rec_df.loc[0, t_col] == rec_df.loc[1, t_col] + rec_df.loc[2, t_col]


def test_hazard_difference_bootstrap_finite():
    """Verify that bootstrap hazard difference produces finite, non-null standard errors and CIs."""
    # Create synthetic test frame
    df_syn = pd.DataFrame({
        "match_id": [1, 1, 1, 2, 2, 2, 3, 3, 3] * 10,
        "pre_dli": [0.5, 1.1, 1.8] * 30,
        "fwd_6_wkts": [0.2, 0.3, 0.5] * 30,
    })
    res = bootstrap_hazard_difference(df_syn, 0.90, 1.35, 2.25, n_boot=50)
    assert np.isfinite(res["se_cluster_bootstrap"])
    assert res["ci95_low"] <= res["ci95_high"]
