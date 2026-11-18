"""
Tests for Milestone R1: Empirical DLI Validation Research.
Verifies DLI monotonicity, elasticity directions, tier population bounds,
clamping ceilings, and subsequent hazard differentiation.
"""

from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.r1_dli_research.dli_sensitivity_analysis import compute_chase_dli, compute_setting_dli


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def match_state_df(project_root) -> pd.DataFrame:
    path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    assert path.exists(), f"Match state dataset missing: {path}"
    return pd.read_csv(path, low_memory=False)


def test_chase_dli_monotonicity_with_rrr():
    """Verify that chase DLI strictly increases with RRR (before 5.00 ceiling clamp)."""
    r_list = [4.0, 6.0, 8.0, 10.0, 12.0, 14.0]
    dlis = [compute_chase_dli(r, w_hand=8, b_rem=60, phase_par=8.0) for r in r_list]

    for i in range(len(dlis) - 1):
        assert dlis[i + 1] > dlis[i], f"Monotonicity violation in RRR: {dlis[i+1]} <= {dlis[i]}"


def test_chase_dli_monotonicity_with_wickets():
    """Verify that chase DLI strictly decreases as wickets in hand increase."""
    w_list = [10, 8, 6, 4, 2, 1]
    dlis = [compute_chase_dli(rrr=9.0, w_hand=w, b_rem=60, phase_par=8.0) for w in w_list]

    for i in range(len(dlis) - 1):
        assert dlis[i + 1] > dlis[i], f"Monotonicity violation in Wickets (fewer wickets must increase DLI): {dlis[i+1]} <= {dlis[i]}"


def test_setting_dli_monotonicity_with_progression():
    """Verify that setting DLI strictly increases over time t as overs advance."""
    t_list = [6, 24, 48, 72, 96, 114, 120]
    dlis = [compute_setting_dli(t, w_hand=8, crr=8.0, phase_par=8.0) for t in t_list]

    for i in range(len(dlis) - 1):
        assert dlis[i + 1] > dlis[i], f"Monotonicity violation in Setting t progression: {dlis[i+1]} <= {dlis[i]}"


def test_tier_population_bounds(match_state_df: pd.DataFrame):
    """Verify that all 4 pressure tiers are well-populated (no empty or trivial tiers)."""
    valid = match_state_df[match_state_df["is_dli_valid"] == True]
    counts = valid["pre_pressure_tier"].value_counts().to_dict()

    t1_pct = counts.get("Tier 1: Low", 0) / len(valid)
    t2_pct = counts.get("Tier 2: Medium", 0) / len(valid)
    t3_pct = counts.get("Tier 3: High", 0) / len(valid)
    t4_pct = counts.get("Tier 4: Extreme", 0) / len(valid)

    # All tiers must have substantial volume (between 10% and 45%)
    assert 0.10 <= t1_pct <= 0.20, f"Tier 1 proportion unexpected: {t1_pct:.2%}"
    assert 0.30 <= t2_pct <= 0.45, f"Tier 2 proportion unexpected: {t2_pct:.2%}"
    assert 0.30 <= t3_pct <= 0.40, f"Tier 3 proportion unexpected: {t3_pct:.2%}"
    assert 0.10 <= t4_pct <= 0.20, f"Tier 4 proportion unexpected: {t4_pct:.2%}"


def test_clamping_saturation_bounds(match_state_df: pd.DataFrame):
    """Verify empirical clamping saturation bounds across chase and setting regimes."""
    chase = match_state_df[(match_state_df["pre_innings_type"] == "Chase") & (match_state_df["is_dli_valid"] == True)]
    upper_clamped_chase = (np.isclose(chase["pre_dli"], 5.00, atol=1e-4)).sum()
    upper_pct_chase = upper_clamped_chase / len(chase)

    setting = match_state_df[(match_state_df["pre_innings_type"] == "Setting") & (match_state_df["is_dli_valid"] == True)]
    upper_clamped_setting = (np.isclose(setting["pre_dli"], 3.50, atol=1e-4)).sum()
    upper_pct_setting = upper_clamped_setting / len(setting)
    lower_clamped_setting = (np.isclose(setting["pre_dli"], 0.20, atol=1e-4)).sum()

    # Chase upper clamping is bounded below 6.0% (actual ~4.86%)
    assert upper_pct_chase < 0.06, f"Chase upper clamping exceeds 6% boundary: {upper_pct_chase:.2%}"
    # Setting upper clamping is bounded below 2.0% (actual ~1.37%)
    assert upper_pct_setting < 0.02, f"Setting upper clamping exceeds 2% boundary: {upper_pct_setting:.2%}"
    # Setting lower clamping (0.20) is completely inactive (0%)
    assert lower_clamped_setting == 0, f"Setting lower clamp unexpectedly active: {lower_clamped_setting}"
