"""
RR ScoutIQ — Milestone M5.5-B.1: Bowler Role Fairness & Dual-Phase Remediation
Module: src/m5_5b_1/bowler_fairness_remediation.py

Investigates:
1. Delivery-level contextual expectations vs coarse career role conditioning
2. Quantifies systematic residual bias for the 21 dual-phase bowlers
3. Compares Powerplay, Middle, and Death deliveries separately
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import pandas as pd
from typing import Dict, Any

from src.m5_5b.baseline_estimation import load_clean_deliveries


def analyze_dual_phase_fairness(data_path: str = "data/processed/m5_3/match_state_full.csv") -> Dict[str, Any]:
    df = load_clean_deliveries(data_path)
    df["phase_clean"] = df["pre_match_phase"].str.lower()
    
    # Identify legal deliveries
    legal = df[df["ext_is_legal_delivery"] == 1].copy()
    legal["runs_conceded"] = legal["ext_bowler_debit_runs"].astype(float)
    legal["is_bnd_con"] = ((legal["ext_is_four"] == 1) | (legal["ext_is_six"] == 1)).astype(int)
    legal["is_dot"] = (legal["ext_bowler_debit_runs"] == 0).astype(int)
    legal["is_wkt"] = (legal["ext_is_bowler_wicket"] == 1).astype(int)
    
    # Compute bowler career workloads in regulation
    reg = legal[legal["innings"] <= 2]
    bowler_stats = reg.groupby(["bowler_id", "bowler_name"]).agg(
        total_legal=("ext_is_legal_delivery", "sum"),
        pp_balls=("overid", lambda s: (s <= 6).sum()),
        mid_balls=("overid", lambda s: ((s >= 7) & (s <= 15)).sum()),
        death_balls=("overid", lambda s: (s >= 16).sum())
    ).reset_index()
    
    # Filter to eligible bowlers (>= 144 legal balls)
    eligible = bowler_stats[bowler_stats["total_legal"] >= 144].copy()
    eligible["pp_pct"] = eligible["pp_balls"] / eligible["total_legal"]
    eligible["death_pct"] = eligible["death_balls"] / eligible["total_legal"]
    eligible["mid_pct"] = eligible["mid_balls"] / eligible["total_legal"]
    
    # Identify the 21 dual-phase bowlers
    dual_mask = (eligible["pp_pct"] >= 0.40) & (eligible["death_pct"] >= 0.30)
    dual_bowlers = eligible[dual_mask].copy()
    dual_ids = set(dual_bowlers["bowler_id"])
    
    print(f"Total eligible bowlers: {len(eligible)}")
    print(f"Total dual-phase bowlers: {len(dual_bowlers)}")
    
    # Calculate Phase baselines across all legal balls
    phase_baselines = legal.groupby("phase_clean").agg(
        mean_runs=("runs_conceded", "mean"),
        econ=("runs_conceded", lambda s: s.mean() * 6.0),
        dot_rate=("is_dot", "mean"),
        bnd_rate=("is_bnd_con", "mean"),
        wkt_rate=("is_wkt", "mean")
    ).to_dict(orient="index")
    
    # Calculate Role baselines under approved M3
    # Bowler role map
    role_map = {}
    for _, row in eligible.iterrows():
        bid = row["bowler_id"]
        is_pp = row["pp_pct"] >= 0.40
        is_death = row["death_pct"] >= 0.30
        if is_pp and is_death:
            role_map[bid] = "Powerplay Specialist" if row["pp_pct"] >= row["death_pct"] else "Death Specialist"
        elif is_pp:
            role_map[bid] = "Powerplay Specialist"
        elif is_death:
            role_map[bid] = "Death Specialist"
        else:
            role_map[bid] = "Middle Enforcer"
            
    legal["bowler_role"] = legal["bowler_id"].map(lambda bid: role_map.get(bid, "Middle Enforcer"))
    legal["is_dual_phase"] = legal["bowler_id"].isin(dual_ids).astype(int)
    
    # Evaluate deliveries bowled by dual-phase bowlers
    dual_deliveries = legal[legal["is_dual_phase"] == 1].copy()
    
    # Workload breakdown by phase for dual-phase bowlers
    phase_breakdown = dual_deliveries.groupby("phase_clean").agg(
        legal_balls=("ext_is_legal_delivery", "sum"),
        runs_conceded=("runs_conceded", "sum"),
        actual_runs_per_ball=("runs_conceded", "mean"),
        actual_econ=("runs_conceded", lambda s: s.mean() * 6.0),
        actual_dot_rate=("is_dot", "mean"),
        actual_bnd_rate=("is_bnd_con", "mean"),
        actual_wkt_rate=("is_wkt", "mean")
    ).reset_index()
    
    # Expected under Phase-conditioned baseline vs Role-conditioned baseline
    # Under Role-conditioned baseline, all dual-phase bowlers are "Powerplay Specialist"
    pp_specialist_mean_runs = legal[legal["bowler_role"] == "Powerplay Specialist"]["runs_conceded"].mean()
    pp_specialist_econ = pp_specialist_mean_runs * 6.0
    
    phase_breakdown["phase_baseline_econ"] = phase_breakdown["phase_clean"].map(lambda p: phase_baselines[p]["econ"])
    phase_breakdown["role_baseline_econ"] = pp_specialist_econ
    phase_breakdown["phase_residual_econ"] = phase_breakdown["phase_baseline_econ"] - phase_breakdown["actual_econ"]  # positive = saving runs
    phase_breakdown["role_residual_econ"] = phase_breakdown["role_baseline_econ"] - phase_breakdown["actual_econ"]
    phase_breakdown["role_distortion_rpo"] = phase_breakdown["role_residual_econ"] - phase_breakdown["phase_residual_econ"]
    
    print("\n--- DUAL-PHASE BOWLERS PHASE PERFORMANCE & BIAS ---")
    print(phase_breakdown[["phase_clean", "legal_balls", "actual_econ", "phase_baseline_econ", "role_baseline_econ", "phase_residual_econ", "role_residual_econ", "role_distortion_rpo"]].to_string(index=False))
    
    return {
        "dual_bowlers": dual_bowlers,
        "phase_breakdown": phase_breakdown,
        "total_dual_balls": len(dual_deliveries)
    }


if __name__ == "__main__":
    analyze_dual_phase_fairness()
