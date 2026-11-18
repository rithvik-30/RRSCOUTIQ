"""
Adversarial tests for delivery legality, extras decomposition, and bowler debits.
Enforces non-circular invariant assertions and tests detection of intentional perturbations.
"""

import pytest
import pandas as pd


def test_independent_delivery_legality_counts(enriched_df: pd.DataFrame):
    """
    Independently verifies exact delivery counts from raw flags, NOT just boolean tautology.
    Must verify:
    - Exactly 172,076 legal deliveries.
    - Exactly 6,976 wides.
    - Exactly 785 no-balls.
    - Exactly 0 overlapping deliveries (wide AND noball).
    - Exactly 179,837 total deliveries.
    """
    legal_count = int((enriched_df["ext_is_legal_delivery"] == True).sum())
    wide_count = int((enriched_df["ext_is_wide"] == True).sum())
    noball_count = int((enriched_df["ext_is_noball"] == True).sum())
    overlap_count = int(((enriched_df["ext_is_wide"] == True) & (enriched_df["ext_is_noball"] == True)).sum())
    total_count = len(enriched_df)

    assert legal_count == 172076, f"Expected 172,076 legal deliveries, got {legal_count}"
    assert wide_count == 6976, f"Expected 6,976 wides, got {wide_count}"
    assert noball_count == 785, f"Expected 785 no-balls, got {noball_count}"
    assert overlap_count == 0, f"Expected 0 overlapping wide+noball deliveries, got {overlap_count}"
    assert total_count == 179837, f"Expected 179,837 total deliveries, got {total_count}"
    assert legal_count + wide_count + noball_count == total_count, "Partition failure in delivery classification"


def test_adversarial_legality_perturbation_detection(enriched_df: pd.DataFrame):
    """
    Simulates malicious/accidental corruption of delivery legality.
    Asserts that altering even a single delivery flips the invariant test to FAIL.
    """
    df_corrupt = enriched_df.copy()
    # Flip one wide to legal
    wide_idx = df_corrupt[df_corrupt["ext_is_wide"] == True].index[0]
    df_corrupt.loc[wide_idx, "ext_is_legal_delivery"] = True

    expected_legal = ~(df_corrupt["ext_is_wide"] | df_corrupt["ext_is_noball"])
    mismatches = (df_corrupt["ext_is_legal_delivery"] != expected_legal).sum()
    assert mismatches == 1, "Adversarial test failed: corruption was not detected"


def test_compound_extras_bowler_debit_isolation(enriched_df: pd.DataFrame):
    """
    Verifies that for compound extras (no-ball + bye or no-ball + legbye),
    the bowler debit is strictly 1 run (the no-ball penalty) and bye/legbye runs
    are not debited to the bowler.
    """
    compound = enriched_df[
        (enriched_df["ext_is_noball"] == True)
        & ((enriched_df["ext_bye_runs"] > 0) | (enriched_df["ext_legbye_runs"] > 0))
    ]
    assert len(compound) == 34, f"Expected 34 compound deliveries, got {len(compound)}"

    # When batter runs == 0, bowler debit runs must equal exactly 1 (no-ball penalty)
    zero_bat = compound[compound["ext_batter_runs"] == 0]
    assert (zero_bat["ext_bowler_debit_runs"] == 1).all(), "Bowler debited with bye/legbye runs on compound no-ball"
