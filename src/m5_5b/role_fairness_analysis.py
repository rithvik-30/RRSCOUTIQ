"""
RR ScoutIQ — Milestone M5.5-B: Role Fairness and Cohort Analysis Engine
Module: src/m5_5b/role_fairness_analysis.py

Conducts detailed empirical investigations of:
1. Cohort sizes and workload distributions for eligible batters and bowlers.
2. Boundary cases and role volatility (61 batters with plurality ties; 16 multi-phase bowlers).
3. The 16 dual-phase bowlers forced into Powerplay Specialist under the asymmetric 40%/30% cutoff.
4. Part-time bowlers and lower-order tailenders.
5. Delivery-level contextual expectations vs coarse categorical player-level roles.

Strict Governance: No player scores, no rankings, no auction recommendations.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

from src.m5_5b.baseline_estimation import (
    load_clean_deliveries,
    assign_batter_roles,
    assign_bowler_roles
)


def analyze_bowler_role_fairness(clean_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Examines bowling workload distributions across Powerplay (overs 1-6), Middle (7-15), Death (16-20).
    Identifies bowlers meeting both PP (>=40%) and Death (>=30%) thresholds.
    Evaluates introducing a 'Dual-Phase Specialist' role.
    """
    reg = clean_df[(clean_df["innings"] <= 2) & (clean_df["ext_is_legal_delivery"] == 1)].copy()
    
    bowler_agg = reg.groupby(["bowler_id", "bowler_name"]).agg(
        total_legal=("ext_is_legal_delivery", "sum"),
        pp_balls=("overid", lambda s: (s <= 6).sum()),
        mid_balls=("overid", lambda s: ((s >= 7) & (s <= 15)).sum()),
        death_balls=("overid", lambda s: (s >= 16).sum()),
        matches=("match_id", "nunique"),
        innings=("innings", "count")  # deliveries count
    ).reset_index()
    
    # Filter to eligible bowlers: >= 144 legal balls
    eligible = bowler_agg[bowler_agg["total_legal"] >= 144].copy()
    eligible["pp_pct"] = eligible["pp_balls"] / eligible["total_legal"]
    eligible["mid_pct"] = eligible["mid_balls"] / eligible["total_legal"]
    eligible["death_pct"] = eligible["death_balls"] / eligible["total_legal"]
    
    # Current approved M3 role classification
    def get_current_role(row):
        is_pp = row["pp_pct"] >= 0.40
        is_death = row["death_pct"] >= 0.30
        if is_pp and is_death:
            return "Powerplay Specialist" if row["pp_pct"] >= row["death_pct"] else "Death Specialist"
        elif is_pp:
            return "Powerplay Specialist"
        elif is_death:
            return "Death Specialist"
        else:
            return "Middle Enforcer"
            
    # Proposed 4-role classification with Dual-Phase Specialist
    def get_proposed_role(row):
        is_pp = row["pp_pct"] >= 0.40
        is_death = row["death_pct"] >= 0.30
        if is_pp and is_death:
            return "Dual-Phase Specialist"
        elif is_pp:
            return "Powerplay Specialist"
        elif is_death:
            return "Death Specialist"
        else:
            return "Middle Enforcer"
            
    eligible["current_role"] = eligible.apply(get_current_role, axis=1)
    eligible["proposed_role"] = eligible.apply(get_proposed_role, axis=1)
    
    # Dual-phase bowlers
    dual_phase_mask = (eligible["pp_pct"] >= 0.40) & (eligible["death_pct"] >= 0.30)
    dual_phase_bowlers = eligible[dual_phase_mask].sort_values("total_legal", ascending=False).copy()
    
    # Summary of cohort sizes under both systems
    current_counts = eligible["current_role"].value_counts().rename("Current_M3_Count")
    proposed_counts = eligible["proposed_role"].value_counts().rename("Proposed_4Role_Count")
    cohort_summary = pd.concat([current_counts, proposed_counts], axis=1).fillna(0).astype(int)
    
    return eligible, dual_phase_bowlers, cohort_summary


def analyze_batter_role_fairness(clean_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Examines batting entry over distributions, plurality ties, and role stability.
    Identifies batters with significant role dispersion across innings.
    """
    reg = clean_df[clean_df["innings"] <= 2].copy()
    first_overs = (
        reg.groupby(["striker_id", "striker_name", "match_id", "innings"])["overid"]
        .min()
        .reset_index()
    )
    
    def get_inn_role(over):
        if over <= 6.0:
            return "Top Order"
        elif over <= 13.0:
            return "Middle Order"
        else:
            return "Finisher"
            
    first_overs["inn_role"] = first_overs["overid"].apply(get_inn_role)
    
    batter_totals = clean_df[clean_df["ext_batter_balls_faced"] == 1].groupby("striker_id")["ext_batter_runs"].count()
    eligible_ids = batter_totals[batter_totals >= 120].index
    
    batter_agg = first_overs[first_overs["striker_id"].isin(eligible_ids)].groupby(["striker_id", "striker_name"]).agg(
        total_innings=("innings", "count"),
        mean_entry=("overid", "mean"),
        std_entry=("overid", lambda s: s.std() if len(s) > 1 else 0.0),
        top_inns=("inn_role", lambda s: (s == "Top Order").sum()),
        mid_inns=("inn_role", lambda s: (s == "Middle Order").sum()),
        fin_inns=("inn_role", lambda s: (s == "Finisher").sum())
    ).reset_index()
    
    batter_agg["top_pct"] = batter_agg["top_inns"] / batter_agg["total_innings"]
    batter_agg["mid_pct"] = batter_agg["mid_inns"] / batter_agg["total_innings"]
    batter_agg["fin_pct"] = batter_agg["fin_inns"] / batter_agg["total_innings"]
    
    def get_primary_role(mean_entry):
        if mean_entry <= 6.0:
            return "Top Order"
        elif mean_entry <= 13.0:
            return "Middle Order"
        else:
            return "Finisher"
            
    batter_agg["primary_role"] = batter_agg["mean_entry"].apply(get_primary_role)
    
    # Identify volatile batters: max role percentage < 60%
    batter_agg["max_role_pct"] = batter_agg[["top_pct", "mid_pct", "fin_pct"]].max(axis=1)
    volatile_batters = batter_agg[batter_agg["max_role_pct"] < 0.60].sort_values("total_innings", ascending=False).copy()
    
    # Boundary cases: mean entry near cutoffs (5.0 - 7.0 or 12.0 - 14.0)
    boundary_cases = batter_agg[
        ((batter_agg["mean_entry"] >= 5.0) & (batter_agg["mean_entry"] <= 7.0)) |
        ((batter_agg["mean_entry"] >= 12.0) & (batter_agg["mean_entry"] <= 14.0))
    ].sort_values("mean_entry").copy()
    
    cohort_summary = batter_agg["primary_role"].value_counts().to_frame("Eligible_Count")
    
    return batter_agg, volatile_batters, boundary_cases


if __name__ == "__main__":
    print("Loading clean dataset...")
    df = load_clean_deliveries()
    
    print("\n--- BOWLER ROLE FAIRNESS ANALYSIS ---")
    bw_elig, dual_bw, bw_cohorts = analyze_bowler_role_fairness(df)
    print(f"Total Eligible Bowlers (>=144 legal balls): {len(bw_elig)}")
    print("\nBowler Cohort Distribution (Current M3 vs Proposed 4-Role):")
    print(bw_cohorts)
    print(f"\nDual-Phase Bowlers (PP >= 40% AND Death >= 30%): Count = {len(dual_bw)}")
    print(dual_bw[["bowler_id", "bowler_name", "total_legal", "pp_pct", "death_pct", "mid_pct", "current_role", "proposed_role"]].to_string(index=False))
    
    print("\n--- BATTER ROLE FAIRNESS ANALYSIS ---")
    b_elig, volatile_b, boundary_b = analyze_batter_role_fairness(df)
    print(f"Total Eligible Batters (>=120 balls faced): {len(b_elig)}")
    print("\nBatter Cohort Distribution:")
    print(b_elig["primary_role"].value_counts())
    print(f"\nVolatile / Multi-Role Batters (Max Role Workload < 60%): Count = {len(volatile_b)}")
    print(volatile_b[["striker_id", "striker_name", "total_innings", "mean_entry", "top_pct", "mid_pct", "fin_pct", "primary_role"]].head(15).to_string(index=False))
    print(f"\nBoundary Batters (Mean entry 5-7 or 12-14 overs): Count = {len(boundary_b)}")
    print(boundary_b[["striker_id", "striker_name", "mean_entry", "primary_role"]].head(10).to_string(index=False))
