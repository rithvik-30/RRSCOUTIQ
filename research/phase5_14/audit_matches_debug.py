"""
Audit script for Task 1 & Task 2: Granular Match & Delivery Inspection
"""
import pandas as pd
import numpy as np

def inspect():
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    matches = pd.read_csv("data/extracted/matches.csv")
    m_date_map = matches.set_index("match_id")["match_date"].to_dict()
    raw["match_date"] = raw["match_id"].map(m_date_map)
    raw["year"] = pd.to_datetime(raw["match_date"]).dt.year

    print("=== INSPECTING MATCH 41979 & 43815 ===")
    for mid in [41979, 43815]:
        m_df = raw[raw["match_id"] == mid]
        m_info = matches[matches["match_id"] == mid]
        print(f"\nMatch ID {mid}:")
        if len(m_info) > 0:
            print(f"  Matches.csv row: date={m_info.iloc[0]['match_date']}, season={m_info.iloc[0].get('season', 'N/A')}")
        else:
            print("  Not in matches.csv!")
        print(f"  Total deliveries in raw: {len(m_df)}")
        if len(m_df) > 0:
            print(f"  Year from map: {m_df['year'].iloc[0]}")
            print(f"  is_dli_valid counts:\n{m_df['is_dli_valid'].value_counts()}")
            print(f"  ext_is_legal_delivery counts:\n{m_df['ext_is_legal_delivery'].value_counts()}")
            print(f"  pre_pressure_tier counts:\n{m_df['pre_pressure_tier'].value_counts()}")
            print(f"  innings count: {m_df['innings'].unique()}")
            print(f"  overid: min={m_df['overid'].min() if 'overid' in m_df.columns else 'N/A'}, max={m_df['overid'].max() if 'overid' in m_df.columns else 'N/A'}")

    print("\n=== 2025 MATCH & DELIVERY AUDIT ===")
    matches["year"] = pd.to_datetime(matches["match_date"]).dt.year
    m25 = matches[matches["year"] == 2025]
    print(f"Matches in matches.csv for 2025: {len(m25)}")
    raw25 = raw[raw["year"] == 2025]
    print(f"Raw deliveries in 2025: {len(raw25)} across {raw25['match_id'].nunique()} matches")
    dli25 = raw25[raw25["is_dli_valid"] == 1]
    print(f"DLI valid deliveries in 2025: {len(dli25)} across {dli25['match_id'].nunique()} matches")
    legal25 = dli25[dli25["ext_is_legal_delivery"] == 1]
    print(f"Clean legal deliveries in 2025: {len(legal25)} across {legal25['match_id'].nunique()} matches")
    press25 = legal25[legal25["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
    print(f"Pressure deliveries in 2025: {len(press25)} across {press25['match_id'].nunique()} matches")

    # Find matches in legal25 not in press25
    zero_p_25 = set(legal25["match_id"].unique()) - set(press25["match_id"].unique())
    print(f"Zero pressure matches in 2025: {zero_p_25}")

    print("\n=== 2026 MATCH & DELIVERY AUDIT ===")
    m26 = matches[matches["year"] == 2026]
    print(f"Matches in matches.csv for 2026: {len(m26)}")
    raw26 = raw[raw["year"] == 2026]
    print(f"Raw deliveries in 2026: {len(raw26)} across {raw26['match_id'].nunique()} matches")
    dli26 = raw26[raw26["is_dli_valid"] == 1]
    print(f"DLI valid deliveries in 2026: {len(dli26)} across {dli26['match_id'].nunique()} matches")
    legal26 = dli26[dli26["ext_is_legal_delivery"] == 1]
    print(f"Clean legal deliveries in 2026: {len(legal26)} across {legal26['match_id'].nunique()} matches")
    press26 = legal26[legal26["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
    print(f"Pressure deliveries in 2026: {len(press26)} across {press26['match_id'].nunique()} matches")

    zero_p_26 = set(legal26["match_id"].unique()) - set(press26["match_id"].unique())
    print(f"Zero pressure matches in 2026: {zero_p_26}")

    # Inspect excluded matches in 2026
    raw_mids_26 = set(raw26["match_id"].unique())
    dli_mids_26 = set(dli26["match_id"].unique())
    excl_mids_26 = raw_mids_26 - dli_mids_26
    print(f"\nExcluded matches in 2026 ({len(excl_mids_26)}): {excl_mids_26}")
    for mid in excl_mids_26:
        m_rows = raw26[raw26["match_id"] == mid]
        print(f"  Match {mid}: total_balls={len(m_rows)}, dli_valid_balls={(m_rows['is_dli_valid']==1).sum()}, reasons={m_rows['dli_invalid_reason'].value_counts().to_dict() if 'dli_invalid_reason' in m_rows.columns else 'N/A'}")

    # Also check if raw has non-legal deliveries that were DLI valid
    print("\n2026 delivery breakdown:")
    print(f"Total DLI valid deliveries: {len(dli26)}")
    print(f"Total DLI valid & legal deliveries: {len(legal26)}")
    print(f"Total DLI valid & non-legal deliveries (wides/no-balls): {len(dli26) - len(legal26)}")
    print(f"Total raw deliveries in 2026 matches: {len(raw26)}")

if __name__ == "__main__":
    inspect()
