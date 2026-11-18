"""
Tests for M5.4 Cricket Scoring Rules and Delivery Laws.
"""

import pytest
import pandas as pd


def test_delivery_run_additivity(enriched_df: pd.DataFrame):
    """Verify ext_delivery_total_runs == ext_batter_runs + ext_extra_runs for all 179,837 rows."""
    expected_total = enriched_df["ext_batter_runs"] + enriched_df["ext_extra_runs"]
    mismatches = (enriched_df["ext_delivery_total_runs"] != expected_total).sum()
    assert mismatches == 0, f"Found {mismatches} delivery total run additivity violations"


def test_extras_component_additivity(enriched_df: pd.DataFrame):
    """Verify ext_extra_runs == wide + noball + bye + legbye + penalty."""
    extras_sum = (
        enriched_df["ext_wide_runs"]
        + enriched_df["ext_noball_runs"]
        + enriched_df["ext_bye_runs"]
        + enriched_df["ext_legbye_runs"]
        + enriched_df["ext_penalty_runs"]
    )
    mismatches = (enriched_df["ext_extra_runs"] != extras_sum).sum()
    assert mismatches == 0, f"Found {mismatches} extras component decomposition violations"


def test_delivery_legality_consistency(enriched_df: pd.DataFrame):
    """Verify ext_is_legal_delivery == ~(ext_is_wide | ext_is_noball)."""
    expected_legal = ~(enriched_df["ext_is_wide"] | enriched_df["ext_is_noball"])
    mismatches = (enriched_df["ext_is_legal_delivery"] != expected_legal).sum()
    assert mismatches == 0, f"Found {mismatches} legality consistency violations"


def test_batter_balls_faced_law(enriched_df: pd.DataFrame):
    """Verify balls faced credited on legal deliveries and no-balls, strictly excluded on wides."""
    expected_bf = enriched_df["ext_is_legal_delivery"] | enriched_df["ext_is_noball"]
    mismatches = (enriched_df["ext_batter_balls_faced"] != expected_bf).sum()
    assert mismatches == 0, f"Found {mismatches} balls faced law violations"

    wides_credited = (enriched_df["ext_is_wide"] & enriched_df["ext_batter_balls_faced"]).sum()
    assert wides_credited == 0, f"Found {wides_credited} wides erroneously credited as balls faced"


def test_bowler_debit_run_accounting(enriched_df: pd.DataFrame):
    """Verify ext_bowler_debit_runs == batter_runs + wide_runs + noball_runs (MCC Law 18.10.3)."""
    expected_debit = (
        enriched_df["ext_batter_runs"]
        + enriched_df["ext_wide_runs"]
        + enriched_df["ext_noball_runs"]
    )
    mismatches = (enriched_df["ext_bowler_debit_runs"] != expected_debit).sum()
    assert mismatches == 0, f"Found {mismatches} bowler debit run violations"

    # Confirm byes and legbyes are never debited to bowler
    bye_debit_leaks = (
        (enriched_df["ext_bye_runs"] > 0)
        & (enriched_df["ext_bowler_debit_runs"] == enriched_df["ext_delivery_total_runs"])
        & (enriched_df["ext_batter_runs"] == 0)
    ).sum()
    assert bye_debit_leaks == 0, f"Found {bye_debit_leaks} bye debit leaks"


def test_boundary_flag_consistency(enriched_df: pd.DataFrame):
    """Verify four and six boundary flags require sufficient batter runs and are mutually exclusive."""
    four_with_less_than_4 = (enriched_df["ext_is_four"] & (enriched_df["ext_batter_runs"] < 4)).sum()
    six_with_less_than_6 = (enriched_df["ext_is_six"] & (enriched_df["ext_batter_runs"] < 6)).sum()
    both_flags = (enriched_df["ext_is_four"] & enriched_df["ext_is_six"]).sum()

    assert four_with_less_than_4 == 0, f"Found {four_with_less_than_4} four flags with <4 runs"
    assert six_with_less_than_6 == 0, f"Found {six_with_less_than_6} six flags with <6 runs"
    assert both_flags == 0, f"Found {both_flags} deliveries with both four and six flags"


def test_dismissal_attribution_and_bowler_credit(enriched_df: pd.DataFrame):
    """Verify bowler wicket credit matches MCC rules for standard 6 dismissal types."""
    bowler_types = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}
    is_dismissal = enriched_df["ext_is_wicket"]
    dis_type = enriched_df["ext_dismissal_kind"].fillna("none").str.lower()

    should_credit = is_dismissal & dis_type.isin(bowler_types)
    actual_credit = enriched_df["ext_is_bowler_wicket"]

    mismatches = (should_credit != actual_credit).sum()
    assert mismatches == 0, f"Found {mismatches} bowler wicket credit mismatches"


def test_retired_hurt_compliance_mcc_law_25_4_2(enriched_df: pd.DataFrame):
    """Verify retired hurt is not treated as a wicket (0 team wickets, 0 bowler wickets)."""
    mask = enriched_df["ext_dismissal_kind"].fillna("none").str.lower() == "retired hurt"
    assert mask.sum() == 13, f"Expected 13 retired hurt deliveries, found {mask.sum()}"

    team_wickets = enriched_df.loc[mask, "ext_is_wicket"].sum()
    bowler_wickets = enriched_df.loc[mask, "ext_is_bowler_wicket"].sum()

    assert team_wickets == 0, f"Retired hurt credited {team_wickets} team wickets"
    assert bowler_wickets == 0, f"Retired hurt credited {bowler_wickets} bowler wickets"


def test_retired_out_compliance_mcc_law_25_4_3(enriched_df: pd.DataFrame):
    """Verify retired out is treated as team wicket but zero bowler wickets."""
    mask = enriched_df["ext_dismissal_kind"].fillna("none").str.lower() == "retired out"
    assert mask.sum() == 7, f"Expected 7 retired out deliveries, found {mask.sum()}"

    team_wickets = enriched_df.loc[mask, "ext_is_wicket"].sum()
    bowler_wickets = enriched_df.loc[mask, "ext_is_bowler_wicket"].sum()

    assert team_wickets == 7, f"Expected 7 team wickets for retired out, got {team_wickets}"
    assert bowler_wickets == 0, f"Retired out credited {bowler_wickets} bowler wickets"
