"""
Phase 5.12 - Task 1: Bowler Spell Aggregation Equivalence Test
Compares official `aggregate_bowler_spells` with Phase 5.11 vectorized aggregation across
all matches in the canonical dataset.
Audits:
- Number of spells
- Bowler ID, Match ID, Phase
- Legal balls
- Bowler debit runs
- Pressure tier assignment
- Spell-level exposure
- Filtering of zero-legal-ball spells (is_valid_spell)
- Edge cases: illegal balls, modal tier ties, zero-legal-ball groups
"""

import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells

def audit_spell_aggregation():
    print("=" * 80)
    print("PHASE 5.12 - TASK 1: BOWLER SPELL AGGREGATION AUDIT")
    print("=" * 80)
    
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    clean = raw[raw["is_dli_valid"] == True].copy()
    print(f"Total DLI-valid deliveries loaded: {len(clean)}")

    # 1. Run Official Production aggregate_bowler_spells
    print("Running official production `aggregate_bowler_spells` on full canonical data...")
    t0 = pd.Timestamp.now()
    official_spells = aggregate_bowler_spells(clean)
    print(f"Official spells extracted: {len(official_spells)} in {(pd.Timestamp.now() - t0).total_seconds():.2f}s")
    
    # 2. Run Phase 5.11 vectorized aggregation
    print("Running Phase 5.11 vectorized aggregation...")
    grp_spells = clean.groupby(["bowler_id", "match_id", "pre_match_phase"])
    p511_spells = grp_spells.agg(
        legal_balls=("ext_is_legal_delivery", lambda x: (x == 1).sum()),
        bowler_debit_runs=("ext_bowler_debit_runs", "sum"),
        modal_tier=("pre_pressure_tier", lambda x: x.mode().iloc[0] if len(x) > 0 else "Tier 2: Medium")
    ).reset_index().rename(columns={"pre_match_phase": "phase"})
    print(f"Phase 5.11 spells extracted: {len(p511_spells)}")

    # Check differences in row count
    row_count_diff = len(official_spells) - len(p511_spells)
    print(f"Row count difference: {row_count_diff}")

    # Inspect zero-legal-ball spells in official
    zero_legal_official = official_spells[official_spells["legal_balls"] == 0]
    invalid_official = official_spells[~official_spells["is_valid_spell"]]
    print(f"Official spells with 0 legal balls: {len(zero_legal_official)}")
    print(f"Official spells with is_valid_spell == False: {len(invalid_official)}")

    # Merge on primary key: bowler_id, match_id, phase
    merged = pd.merge(
        official_spells,
        p511_spells,
        on=["bowler_id", "match_id", "phase"],
        suffixes=("_official", "_p511"),
        how="outer"
    )

    missing_in_p511 = merged[merged["legal_balls_p511"].isna()]
    missing_in_official = merged[merged["legal_balls_official"].isna()]
    print(f"Spells missing in Phase 5.11: {len(missing_in_p511)}")
    print(f"Spells missing in Official: {len(missing_in_official)}")

    # Compare columns on inner matches
    inner = merged.dropna(subset=["legal_balls_official", "legal_balls_p511"]).copy()
    diff_legal_balls = (inner["legal_balls_official"] != inner["legal_balls_p511"]).sum()
    diff_debits = (inner["bowler_debit_runs_official"] != inner["bowler_debit_runs_p511"]).sum()
    diff_tier = (inner["modal_tier_official"] != inner["modal_tier_p511"]).sum()

    print(f"\nInner comparison on {len(inner)} matched spells:")
    print(f"  Legal balls differences: {diff_legal_balls}")
    print(f"  Bowler debit runs differences: {diff_debits}")
    print(f"  Modal tier differences: {diff_tier}")

    tier_diff_samples = []
    if diff_tier > 0:
        tdf = inner[inner["modal_tier_official"] != inner["modal_tier_p511"]]
        print(f"\nSample of modal tier differences ({len(tdf)} cases):")
        for idx, r in tdf.head(5).iterrows():
            bid, mid, ph = r["bowler_id"], r["match_id"], r["phase"]
            b_delivs = clean[(clean["bowler_id"] == bid) & (clean["match_id"] == mid) & (clean["pre_match_phase"] == ph)]
            print(f"  Bowler {bid}, Match {mid}, Phase {ph}:")
            print(f"    Official: '{r['modal_tier_official']}' vs P511: '{r['modal_tier_p511']}'")
            print(f"    Raw tiers: {b_delivs['pre_pressure_tier'].tolist()}")
            tier_diff_samples.append({
                "bowler_id": int(bid),
                "match_id": int(mid),
                "phase": str(ph),
                "official_tier": str(r["modal_tier_official"]),
                "p511_tier": str(r["modal_tier_p511"]),
                "delivery_tiers": b_delivs["pre_pressure_tier"].tolist()
            })

    # How does pressure filtering affect them?
    # Official pressure definition in M5_5B_4_3_8:
    official_press = official_spells[
        official_spells["is_valid_spell"] & 
        official_spells["modal_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    ]
    p511_press = p511_spells[
        p511_spells["modal_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    ]
    # Did Phase 5.11 include invalid spells (legal_balls == 0) in pressure spells?
    p511_press_zero_legal = p511_press[p511_press["legal_balls"] == 0]
    print(f"\nPressure spells count:")
    print(f"  Official valid pressure spells: {len(official_press)}")
    print(f"  Phase 5.11 pressure spells:     {len(p511_press)}")
    print(f"  Phase 5.11 pressure spells with 0 legal balls: {len(p511_press_zero_legal)}")

    # Edge cases analysis:
    # 1. Spells with wides and no-balls
    wides_count = (clean["ext_is_wide"] == 1).sum() if "ext_is_wide" in clean.columns else 0
    noballs_count = (clean["ext_is_noball"] == 1).sum() if "ext_is_noball" in clean.columns else 0
    print(f"\nEdge Cases in deliveries:")
    print(f"  Deliveries with wides: {wides_count}")
    print(f"  Deliveries with noballs: {noballs_count}")

    # Inspect the exact single 0-legal-ball spell
    zero_spell = official_spells[official_spells["legal_balls"] == 0]
    print("\nDetailed breakdown of the 0-legal-ball spell:")
    for idx, r in zero_spell.iterrows():
        bid, mid, ph = r["bowler_id"], r["match_id"], r["phase"]
        delivs = clean[(clean["bowler_id"] == bid) & (clean["match_id"] == mid) & (clean["pre_match_phase"] == ph)]
        print(f"  Bowler {bid} ({r['bowler_name']}), Match {mid}, Phase {ph}:")
        print(f"    Total deliveries: {r['total_deliveries']}, Legal balls: {r['legal_balls']}, Debits: {r['bowler_debit_runs']}")
        print(f"    Modal tier: {r['modal_tier']}, is_valid_spell: {r['is_valid_spell']}")
        print(f"    Deliveries detail:")
        for _, d in delivs.iterrows():
            print(f"      over: {d.get('over_number')}.{d.get('ball_number')}, is_legal: {d.get('ext_is_legal_delivery')}, wide: {d.get('ext_is_wide')}, noball: {d.get('ext_is_noball')}, debits: {d.get('ext_bowler_debit_runs')}")

    # Check debit runs accounting on spells with extras
    spells_with_extras = official_spells[(official_spells["wides_count"] > 0) | (official_spells["noballs_count"] > 0)]
    print(f"  Spells with extras (wides/noballs): {len(spells_with_extras)}")
    merged_extras = pd.merge(
        spells_with_extras,
        p511_spells,
        on=["bowler_id", "match_id", "phase"],
        suffixes=("_official", "_p511")
    )
    diff_extras_balls = (merged_extras["legal_balls_official"] != merged_extras["legal_balls_p511"]).sum()
    diff_extras_debits = (merged_extras["bowler_debit_runs_official"] != merged_extras["bowler_debit_runs_p511"]).sum()
    print(f"  Differences in spells with extras: legal_balls={diff_extras_balls}, debits={diff_extras_debits}")

    results = {
        "official_total_spells": int(len(official_spells)),
        "p511_total_spells": int(len(p511_spells)),
        "row_count_difference": int(row_count_diff),
        "official_zero_legal_balls": int(len(zero_legal_official)),
        "official_invalid_spells": int(len(invalid_official)),
        "p511_zero_legal_balls_in_press": int(len(p511_press_zero_legal)),
        "matched_spells_count": int(len(inner)),
        "differences": {
            "legal_balls": int(diff_legal_balls),
            "bowler_debit_runs": int(diff_debits),
            "modal_tier": int(diff_tier)
        },
        "official_valid_pressure_spells": int(len(official_press)),
        "p511_pressure_spells": int(len(p511_press)),
        "spells_with_extras_count": int(len(spells_with_extras)),
        "extras_differences": {
            "legal_balls": int(diff_extras_balls),
            "debit_runs": int(diff_extras_debits)
        },
        "tier_diff_samples": tier_diff_samples
    }

    out_file = "research/phase5_12/spell_aggregation_equivalence.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved Task 1 audit results to {out_file}")
    return results

if __name__ == "__main__":
    audit_spell_aggregation()
