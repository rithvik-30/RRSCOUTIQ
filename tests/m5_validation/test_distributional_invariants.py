"""
Tests for M5.4 Distributional and Statistical Invariants.
"""

import numpy as np
import pytest
import pandas as pd


def test_batter_run_distribution(enriched_df: pd.DataFrame):
    """Verify batter runs fall strictly in standard set {0, 1, 2, 3, 4, 5, 6, 7}."""
    valid_runs = enriched_df["ext_batter_runs"].isin([0, 1, 2, 3, 4, 5, 6, 7])
    assert valid_runs.all(), f"Found {(~valid_runs).sum()} deliveries with implausible batter runs"

    # Distribution profile checks
    counts = enriched_df["ext_batter_runs"].value_counts().to_dict()
    assert counts.get(0, 0) > 70000, "Dot balls count unexpectedly low"
    assert counts.get(1, 0) > 60000, "Single runs count unexpectedly low"
    assert counts.get(4, 0) > 15000, "Fours count unexpectedly low"
    assert counts.get(6, 0) > 7000, "Sixes count unexpectedly low"


def test_delivery_total_run_bounds(enriched_df: pd.DataFrame):
    """Verify total delivery runs fall strictly within physical bounds [0, 8]."""
    in_bounds = (enriched_df["ext_delivery_total_runs"] >= 0) & (enriched_df["ext_delivery_total_runs"] <= 8)
    assert in_bounds.all(), f"Found {(~in_bounds).sum()} deliveries with total runs outside [0, 8]"


def test_dli_empirical_bounds_and_percentiles(match_state_df: pd.DataFrame):
    """Verify DLI bounds, finiteness, and characteristic quantiles."""
    valid_dli = match_state_df.loc[match_state_df["is_dli_valid"] == True, "pre_dli"]
    assert len(valid_dli) == 175676

    # Realism bounds
    assert (valid_dli >= 0.10).all(), "Found DLI < 0.10"
    assert (valid_dli <= 10.0).all(), "Found DLI > 10.0"
    assert np.isfinite(valid_dli).all(), "Found non-finite DLI values"

    # Check characteristic percentiles
    q25 = valid_dli.quantile(0.25)
    q50 = valid_dli.quantile(0.50)
    q75 = valid_dli.quantile(0.75)

    assert 0.80 <= q25 <= 1.10, f"Q25 DLI {q25:.3f} outside expected range [0.80, 1.10]"
    assert 1.10 <= q50 <= 1.45, f"Median DLI {q50:.3f} outside expected range [1.10, 1.45]"
    assert 1.50 <= q75 <= 2.05, f"Q75 DLI {q75:.3f} outside expected range [1.50, 2.05]"


def test_pressure_tier_distribution_proportions(match_state_df: pd.DataFrame):
    """Verify pressure tier counts match the verified canonical distribution."""
    valid = match_state_df[match_state_df["is_dli_valid"] == True]
    counts = valid["pre_pressure_tier"].value_counts().to_dict()

    expected = {
        "Tier 2: Medium": 65587,
        "Tier 3: High": 61990,
        "Tier 4: Extreme": 24128,
        "Tier 1: Low": 23971,
    }
    assert counts == expected, f"Pressure tier distribution mismatch: {counts} vs expected {expected}"
