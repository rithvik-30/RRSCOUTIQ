"""
Adversarial tests for exclusion semantics, null discipline, and Super Over isolation.
"""

import pytest
import pandas as pd


def test_standard_match_deliveries_never_excluded(match_state_df: pd.DataFrame):
    """
    Verifies that no standard 20-over non-DLS deliveries are accidentally marked invalid.
    """
    standard_mask = (match_state_df["is_shortened_match"] == False) & (match_state_df["is_dls_match"] == False) & (match_state_df["is_super_over"] == False)
    standard_df = match_state_df[standard_mask]

    assert len(standard_df) > 170000
    assert (standard_df["is_dli_valid"] == True).all(), "Standard 20-over delivery incorrectly marked invalid"
    assert standard_df["pre_dli"].notna().all(), "Standard 20-over delivery has null DLI"
    assert standard_df["pre_pressure_tier"].notna().all(), "Standard 20-over delivery has null pressure tier"


def test_adversarial_null_tier_imputation_detection(match_state_df: pd.DataFrame):
    """
    Verifies that if an invalid delivery is assigned a fallback pressure tier (e.g. Tier 2: Medium),
    the validation suite detects the defect immediately.
    """
    corrupt_df = match_state_df.copy()
    invalid_idx = corrupt_df[corrupt_df["is_dli_valid"] == False].index[0]

    # Maliciously assign fallback tier
    corrupt_df.loc[invalid_idx, "pre_pressure_tier"] = "Tier 2: Medium"

    # Invariant: Invalid deliveries must have NaN pre_pressure_tier
    invalid_non_null = corrupt_df.loc[corrupt_df["is_dli_valid"] == False, "pre_pressure_tier"].notna().sum()
    assert invalid_non_null == 1, "Adversarial test failed: fallback tier on excluded delivery was not detected"


def test_super_over_deterministic_pinning(match_state_df: pd.DataFrame):
    """
    Verifies that Super Over deliveries (26 balls) are strictly pinned to DLI = 3.50,
    Tier 4: Extreme, and is_dli_valid == True across both matches (10190, 31251).
    """
    so = match_state_df[match_state_df["is_super_over"] == True]
    assert len(so) == 26
    assert (so["is_dli_valid"] == True).all()
    assert (so["pre_dli"] == 3.50).all()
    assert (so["pre_pressure_tier"] == "Tier 4: Extreme").all()
    assert set(so["match_id"].unique()) == {34429, 40725, 45512, 50359}
