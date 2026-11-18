"""
Unit Test: Bowler Spell Aggregation Equivalence
Asserts exact numerical equality between official production aggregate_bowler_spells
and the corrected vectorized aggregation, verifying:
- Identical spell count after filtering legal_balls > 0
- 0 differences in legal balls
- 0 differences in debited runs
- 0 differences in modal pressure tier
- Identification and handling of zero-legal-ball edge cases
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import pytest
import pandas as pd
import numpy as np

from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells

@pytest.fixture(scope="module")
def sample_match_data():
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    # Take a representative sample of 20 matches covering powerplay, middle, death, extras, dismissals
    sample_mids = raw[raw["is_dli_valid"] == 1]["match_id"].unique()[:20]
    return raw[(raw["is_dli_valid"] == 1) & (raw["match_id"].isin(sample_mids))].copy()

def test_spell_aggregation_exact_equivalence(sample_match_data):
    # 1. Official aggregation
    official = aggregate_bowler_spells(sample_match_data)
    official_valid = official[official["is_valid_spell"]].copy()

    # 2. Corrected vectorized aggregation
    grp = sample_match_data.groupby(["bowler_id", "match_id", "pre_match_phase"])
    p512 = grp.agg(
        legal_balls=("ext_is_legal_delivery", lambda x: (x == 1).sum()),
        bowler_debit_runs=("ext_bowler_debit_runs", "sum"),
        modal_tier=("pre_pressure_tier", lambda x: x.mode().iloc[0] if len(x) > 0 else "Tier 2: Medium")
    ).reset_index().rename(columns={"pre_match_phase": "phase"})
    
    # Apply official valid spell filter
    p512_valid = p512[p512["legal_balls"] > 0].copy()

    # Assert row counts match
    assert len(official_valid) == len(p512_valid), f"Spell counts differ: {len(official_valid)} vs {len(p512_valid)}"

    # Merge on primary keys
    merged = pd.merge(
        official_valid,
        p512_valid,
        on=["bowler_id", "match_id", "phase"],
        suffixes=("_official", "_p512")
    )
    assert len(merged) == len(official_valid), "Primary keys do not align perfectly"

    # Assert exact numerical equality
    diff_balls = (merged["legal_balls_official"] != merged["legal_balls_p512"]).sum()
    diff_runs = (merged["bowler_debit_runs_official"] != merged["bowler_debit_runs_p512"]).sum()
    diff_tier = (merged["modal_tier_official"] != merged["modal_tier_p512"]).sum()

    assert diff_balls == 0, f"Found {diff_balls} legal ball mismatches"
    assert diff_runs == 0, f"Found {diff_runs} debit run mismatches"
    assert diff_tier == 0, f"Found {diff_tier} modal tier mismatches"

def test_zero_legal_ball_spell_handling():
    # Construct synthetic edge case: 1 delivery, wide, 0 legal balls
    synthetic_df = pd.DataFrame([{
        "bowler_id": 99999,
        "bowler_name": "Test Bowler",
        "match_id": 88888,
        "pre_match_phase": "Death",
        "pre_pressure_tier": "Tier 3: High",
        "ext_is_legal_delivery": 0,
        "ext_is_wide": 1,
        "ext_is_noball": 0,
        "ext_bowler_debit_runs": 1
    }])
    
    official = aggregate_bowler_spells(synthetic_df)
    assert len(official) == 1
    assert official.iloc[0]["legal_balls"] == 0
    assert official.iloc[0]["is_valid_spell"] == False

    # Vectorized filter must reject it
    grp = synthetic_df.groupby(["bowler_id", "match_id", "pre_match_phase"])
    p512 = grp.agg(
        legal_balls=("ext_is_legal_delivery", lambda x: (x == 1).sum()),
        bowler_debit_runs=("ext_bowler_debit_runs", "sum"),
        modal_tier=("pre_pressure_tier", lambda x: x.mode().iloc[0] if len(x) > 0 else "Tier 2: Medium")
    ).reset_index().rename(columns={"pre_match_phase": "phase"})
    
    p512_valid = p512[p512["legal_balls"] > 0]
    assert len(p512_valid) == 0, "Vectorized aggregation failed to filter 0-legal-ball spell"
