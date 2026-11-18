"""
RR ScoutIQ — Milestone M5.5-B: Baseline Estimation Engine
Module: src/m5_5b/baseline_estimation.py

Analyzes contextual baselines for batters and bowlers across:
- Match Phase (Powerplay, Middle, Death)
- Pressure Tier (Tier 1: Low, Tier 2: Moderate, Tier 3: High, Tier 4: Extreme)
- Setting vs Chasing (Innings 1 vs Innings 2)
- Batter Role (Top Order, Middle Order, Finisher)
- Bowler Role (Powerplay Specialist, Middle Enforcer, Death Specialist, Dual-Role)

Strict Governance: No player scores, no rankings, no auction recommendations.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional


def load_clean_deliveries(filepath: str = "data/processed/m5_3/match_state_full.csv") -> pd.DataFrame:
    """Loads match_state_full.csv and filters to clean DLI-valid deliveries (744 matches, 175,676 balls)."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    df = pd.read_csv(filepath, low_memory=False)
    clean = df[df["is_dli_valid"] == True].copy()
    if len(clean) != 175676:
        raise ValueError(f"Expected 175,676 clean deliveries, got {len(clean):,}")
    return clean


def assign_batter_roles(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[int, str]]:
    """
    Assigns career batting roles based on approved M3 Definition:
    Regulation innings entry over <= 6.0: Top Order
    Regulation innings entry over > 6.0 and <= 13.0: Middle Order
    Regulation innings entry over > 13.0: Finisher
    """
    reg = df[df["innings"] <= 2]
    first_overs = (
        reg.groupby(["striker_id", "match_id", "innings"])["overid"]
        .min()
        .reset_index()
    )
    mean_entries = first_overs.groupby("striker_id")["overid"].mean()
    
    role_map = {}
    for sid, avg_entry in mean_entries.items():
        if avg_entry <= 6.0:
            role_map[sid] = "Top Order"
        elif avg_entry <= 13.0:
            role_map[sid] = "Middle Order"
        else:
            role_map[sid] = "Finisher"
            
    df_with_roles = df.copy()
    df_with_roles["batter_role"] = df_with_roles["striker_id"].map(
        lambda sid: role_map.get(sid, "Middle Order")
    )
    return df_with_roles, role_map


def assign_bowler_roles(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[int, str], Dict[int, Dict[str, float]]]:
    """
    Assigns career bowling roles based on approved M3 Definition B1:
    PP balls (overs 1-6) / Total legal balls >= 40% -> Powerplay Specialist
    Death balls (overs 16-20) / Total legal balls >= 30% -> Death Specialist
    Dual qualification -> Operative tiebreak pp_pct >= death_pct -> PP Specialist
    Neither -> Middle Enforcer
    """
    reg = df[(df["innings"] <= 2) & (df["ext_is_legal_delivery"] == 1)]
    bowler_stats = reg.groupby("bowler_id").agg(
        total_legal=("ext_is_legal_delivery", "sum"),
        pp_balls=("overid", lambda s: (s <= 6).sum()),
        mid_balls=("overid", lambda s: ((s >= 7) & (s <= 15)).sum()),
        death_balls=("overid", lambda s: (s >= 16).sum())
    ).reset_index()
    
    role_map = {}
    workloads = {}
    for _, row in bowler_stats.iterrows():
        bid = int(row["bowler_id"])
        total = row["total_legal"]
        if total == 0:
            role_map[bid] = "Middle Enforcer"
            workloads[bid] = {"pp_pct": 0.0, "death_pct": 0.0, "mid_pct": 0.0, "total": 0}
            continue
        pp_pct = row["pp_balls"] / total
        death_pct = row["death_balls"] / total
        mid_pct = row["mid_balls"] / total
        workloads[bid] = {"pp_pct": pp_pct, "death_pct": death_pct, "mid_pct": mid_pct, "total": total}
        
        is_pp = pp_pct >= 0.40
        is_death = death_pct >= 0.30
        
        if is_pp and is_death:
            role_map[bid] = "Powerplay Specialist" if pp_pct >= death_pct else "Death Specialist"
        elif is_pp:
            role_map[bid] = "Powerplay Specialist"
        elif is_death:
            role_map[bid] = "Death Specialist"
        else:
            role_map[bid] = "Middle Enforcer"
            
    df_with_roles = df.copy()
    df_with_roles["bowler_role"] = df_with_roles["bowler_id"].map(
        lambda bid: role_map.get(bid, "Middle Enforcer")
    )
    return df_with_roles, role_map, workloads


def compute_batter_cell_baselines(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Computes batter baselines across multiple slicing granularities:
    1. Phase (3 cells)
    2. Phase x Tier (12 cells)
    3. Phase x Tier x Innings (24 cells)
    4. Phase x Tier x Role (36 cells)
    5. Phase x Tier x Innings x Role (72 cells)
    """
    b_df = df[df["ext_batter_balls_faced"] == 1].copy()
    b_df["is_boundary"] = ((b_df["ext_is_four"] == 1) | (b_df["ext_is_six"] == 1)).astype(int)
    b_df["is_dot"] = ((b_df["ext_batter_runs"] == 0) & (b_df["is_boundary"] == 0)).astype(int)
    b_df["is_dismissal"] = (b_df["ext_is_wicket"] == 1).astype(int)
    b_df["runs"] = b_df["ext_batter_runs"].astype(float)
    
    slices = {
        "phase": ["pre_match_phase"],
        "phase_tier": ["pre_match_phase", "pre_pressure_tier"],
        "phase_tier_innings": ["pre_match_phase", "pre_pressure_tier", "innings"],
        "phase_tier_role": ["pre_match_phase", "pre_pressure_tier", "batter_role"],
        "phase_tier_innings_role": ["pre_match_phase", "pre_pressure_tier", "innings", "batter_role"],
    }
    
    results = {}
    for name, cols in slices.items():
        agg = b_df.groupby(cols).agg(
            ball_count=("runs", "count"),
            runs_mean=("runs", "mean"),
            runs_std=("runs", "std"),
            runs_sem=("runs", lambda s: s.std() / np.sqrt(len(s)) if len(s) > 1 else 0.0),
            sr_mean=("runs", lambda s: s.mean() * 100.0),
            bnd_prob=("is_boundary", "mean"),
            dot_prob=("is_dot", "mean"),
            out_prob=("is_dismissal", "mean")
        ).reset_index()
        results[name] = agg
        
    return results


def compute_bowler_cell_baselines(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Computes bowler baselines across multiple slicing granularities:
    1. Phase (3 cells)
    2. Phase x Tier (12 cells)
    3. Phase x Tier x Innings (24 cells)
    4. Phase x Tier x Role (36 cells)
    5. Phase x Tier x Innings x Role (72 cells)
    """
    b_df = df[df["ext_is_legal_delivery"] == 1].copy()
    b_df["is_boundary_conceded"] = ((b_df["ext_is_four"] == 1) | (b_df["ext_is_six"] == 1)).astype(int)
    b_df["is_dot"] = (b_df["ext_bowler_debit_runs"] == 0).astype(int)
    b_df["is_wicket"] = (b_df["ext_is_bowler_wicket"] == 1).astype(int)
    b_df["runs_conceded"] = b_df["ext_bowler_debit_runs"].astype(float)
    
    slices = {
        "phase": ["pre_match_phase"],
        "phase_tier": ["pre_match_phase", "pre_pressure_tier"],
        "phase_tier_innings": ["pre_match_phase", "pre_pressure_tier", "innings"],
        "phase_tier_role": ["pre_match_phase", "pre_pressure_tier", "bowler_role"],
        "phase_tier_innings_role": ["pre_match_phase", "pre_pressure_tier", "innings", "bowler_role"],
    }
    
    results = {}
    for name, cols in slices.items():
        agg = b_df.groupby(cols).agg(
            ball_count=("runs_conceded", "count"),
            runs_mean=("runs_conceded", "mean"),
            runs_std=("runs_conceded", "std"),
            runs_sem=("runs_conceded", lambda s: s.std() / np.sqrt(len(s)) if len(s) > 1 else 0.0),
            econ_mean=("runs_conceded", lambda s: s.mean() * 6.0),
            bnd_con_prob=("is_boundary_conceded", "mean"),
            dot_prob=("is_dot", "mean"),
            wkt_prob=("is_wicket", "mean")
        ).reset_index()
        results[name] = agg
        
    return results


if __name__ == "__main__":
    print("Loading clean deliveries...")
    clean_df = load_clean_deliveries()
    print(f"Loaded {len(clean_df):,} clean deliveries.")
    
    print("Assigning batter roles...")
    clean_df, b_role_map = assign_batter_roles(clean_df)
    b_role_counts = pd.Series(list(b_role_map.values())).value_counts()
    print("Batter career roles across all strikers:")
    print(b_role_counts)
    
    print("\nAssigning bowler roles...")
    clean_df, bw_role_map, workloads = assign_bowler_roles(clean_df)
    bw_role_counts = pd.Series(list(bw_role_map.values())).value_counts()
    print("Bowler career roles across all bowlers:")
    print(bw_role_counts)
    
    print("\nComputing batter baselines...")
    batter_res = compute_batter_cell_baselines(clean_df)
    print("\n--- Batter Phase x Tier Baselines (12 cells) ---")
    print(batter_res["phase_tier"].to_string(index=False))
    
    print("\nComputing bowler baselines...")
    bowler_res = compute_bowler_cell_baselines(clean_df)
    print("\n--- Bowler Phase x Tier Baselines (12 cells) ---")
    print(bowler_res["phase_tier"].to_string(index=False))
