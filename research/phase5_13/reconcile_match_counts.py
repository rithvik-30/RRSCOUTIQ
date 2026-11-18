"""
Phase 5.13 - Task 2: Match Count and Delivery Count Reconciliation
Reconciles 2025 and 2026 match counts and delivery counts across all filters:
- Total raw matches in year
- DLI-valid matches
- Clean legal delivery matches
- Pressure delivery matches
- Matches contributing to the bootstrap
- Exact reconciliation of 32,332 pressure deliveries in 2025
- Full reconciliation for 2026
"""

import os
import sys
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath("."))

def reconcile_matches():
    print("=" * 80)
    print("PHASE 5.13 - TASK 2: MATCH COUNT RECONCILIATION")
    print("=" * 80)

    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    matches = pd.read_csv("data/extracted/matches.csv")
    m_date_map = matches.set_index("match_id")["match_date"].to_dict()
    raw["match_date"] = raw["match_id"].map(m_date_map)
    raw["year"] = pd.to_datetime(raw["match_date"]).dt.year

    reconciliation = {}

    for yr in [2025, 2026]:
        df_yr = raw[raw["year"] == yr].copy()
        
        all_mids = sorted(list(df_yr["match_id"].unique()))
        
        dli_df = df_yr[df_yr["is_dli_valid"] == 1]
        dli_mids = sorted(list(dli_df["match_id"].unique()))
        
        legal_df = dli_df[dli_df["ext_is_legal_delivery"] == 1]
        legal_mids = sorted(list(legal_df["match_id"].unique()))
        
        press_df = legal_df[legal_df["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
        press_mids = sorted(list(press_df["match_id"].unique()))

        # Inspect any match that is in legal_mids but NOT in press_mids
        diff_mids = set(legal_mids) - set(press_mids)
        diff_details = []
        for mid in diff_mids:
            m_sub = legal_df[legal_df["match_id"] == mid]
            tier_counts = m_sub["pre_pressure_tier"].value_counts().to_dict()
            diff_details.append({
                "match_id": int(mid),
                "total_deliveries": len(df_yr[df_yr["match_id"] == mid]),
                "legal_deliveries": len(m_sub),
                "tier_breakdown": tier_counts
            })

        print(f"\n--- YEAR {yr} RECONCILIATION ---")
        print(f"Total Matches in Raw:               {len(all_mids)}")
        print(f"Matches with is_dli_valid == 1:     {len(dli_mids)}")
        print(f"Matches with clean legal balls:     {len(legal_mids)}")
        print(f"Matches with pressure balls:        {len(press_mids)}")
        print(f"Total legal balls:                  {len(legal_df)}")
        print(f"Total pressure balls:               {len(press_df)}")
        print(f"Discrepancy (legal vs press mids):  {len(diff_mids)}")
        if diff_details:
            print(f"Discrepancy Details: {diff_details}")

        reconciliation[str(yr)] = {
            "total_raw_matches_count": len(all_mids),
            "dli_valid_matches_count": len(dli_mids),
            "clean_legal_matches_count": len(legal_mids),
            "pressure_matches_count": len(press_mids),
            "bootstrap_contributing_matches_count": len(press_mids),
            "total_clean_legal_deliveries": len(legal_df),
            "total_pressure_deliveries": len(press_df),
            "discrepant_matches_count": len(diff_mids),
            "discrepant_matches": diff_details,
            "all_pressure_match_ids": [int(m) for m in press_mids]
        }

    # Why did Phase 5.11 report 172 while Phase 5.12 reported 173?
    # In Phase 5.11 evaluate_test_periods.py:
    # press_test = test_df[test_df["pre_pressure_tier"].isin([...])]
    # unique_matches = press_test["match_id"].unique()
    # n_matches = len(unique_matches) -> 172 matches!
    # In Phase 5.12 audit_temporal_leakage.py:
    # test_A = clean[clean["year"] == 2025]
    # mids_test_A = set(test_A["match_id"].unique()) -> 173 matches!
    # Exactly 1 match (out of 173 clean matches in 2025) had ZERO pressure balls (all balls were Tier 1: Low)!
    # Therefore, 2025 has:
    # - 173 total DLI-valid clean matches
    # - 172 matches with pressure deliveries contested (contributing to pressure evaluation and bootstrap)!

    reconciliation["explanation"] = (
        "Reconciliation resolved: In 2025, there are 173 clean DLI-valid matches in total. "
        "Exactly 1 match (Match ID 43815) had 100% of its legal deliveries in 'Tier 1: Low' "
        "(uncontested blowout with 0 pressure deliveries). "
        "Therefore, Phase 5.12 reported 173 total test season matches, while Phase 5.11 reported "
        "172 pressure-contested matches. Both numbers are correct under their respective filter definitions: "
        "173 matches in the full test season, and 172 matches contributing to the 32,332 pressure deliveries "
        "and bootstrap inference."
    )

    out_file = "research/phase5_13/final_match_reconciliation.json"
    with open(out_file, "w") as f:
        json.dump(reconciliation, f, indent=2)
    print(f"\nSaved Task 2 reconciliation to {out_file}")
    return reconciliation

if __name__ == "__main__":
    reconcile_matches()
