"""
RR ScoutIQ — Milestone M5.5-B.3: Matched Within-Bowler Fairness Analyzer
Module: src/m5_5b_3/bowler_fairness_matched.py

Replaces flawed aggregate role-mean comparisons with:
1. Paired within-bowler matched phase performance across Powerplay, Middle, and Death.
2. Individual player-level residual analysis for dual-phase bowlers vs single-phase specialists.
3. Quantifies role-conditioned distortion vs phase-conditioned expectation at the player level.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy, derive_training_bowler_roles_b2


def run_matched_bowler_fairness_analysis(
    data_path: str = "data/processed/m5_3/match_state_full.csv"
) -> Dict[str, Any]:
    df = load_clean_deliveries(data_path)
    df["phase_clean"] = df["pre_match_phase"].str.lower()
    
    # Derive roles strictly
    role_map, role_details = derive_training_bowler_roles_b2(df)
    df["bowler_role"] = df["bowler_id"].map(role_map).fillna("Middle Enforcer")
    
    # 1. League phase baselines
    phase_baselines = {}
    for phase, p_df in df.groupby("phase_clean"):
        stats = calculate_bowler_economy(p_df)
        phase_baselines[phase] = stats["economy_rate"]
        
    role_baselines = {}
    for role, r_df in df.groupby("bowler_role"):
        stats = calculate_bowler_economy(r_df)
        role_baselines[role] = stats["economy_rate"]
        
    # 2. Bowler x Phase Matched Aggregations
    bowler_phase_records = []
    eligible_ids = role_details[role_details["total_legal"] >= 144]["bowler_id"].unique()
    
    for bid in eligible_ids:
        b_df = df[df["bowler_id"] == bid]
        bname = b_df["bowler_name"].iloc[0]
        role = role_map.get(bid, "Middle Enforcer")
        
        # Powerplay stats
        pp_df = b_df[b_df["phase_clean"] == "powerplay"]
        pp_stats = calculate_bowler_economy(pp_df)
        
        # Death stats
        death_df = b_df[b_df["phase_clean"] == "death"]
        death_stats = calculate_bowler_economy(death_df)
        
        # Middle stats
        mid_df = b_df[b_df["phase_clean"] == "middle"]
        mid_stats = calculate_bowler_economy(mid_df)
        
        # Check if dual-phase
        pp_balls = pp_stats["legal_balls"]
        death_balls = death_stats["legal_balls"]
        total_legal = pp_balls + death_balls + mid_stats["legal_balls"]
        
        is_dual = (pp_balls / total_legal >= 0.40) and (death_balls / total_legal >= 0.30) if total_legal > 0 else False
        
        # Paired within-bowler difference in death overs:
        # Actual death econ
        death_econ = death_stats["economy_rate"]
        
        if death_balls >= 30 and np.isfinite(death_econ):
            phase_death_expected = phase_baselines.get("death", 10.15)
            role_expected = role_baselines.get(role, 8.88)
            
            # Within-bowler evaluation under Phase vs Role conditioning
            delta_phase = phase_death_expected - death_econ  # positive = saved runs
            delta_role = role_expected - death_econ          # negative = penalized by PP role
            distortion = delta_role - delta_phase           # = role_expected - phase_death_expected
            
            # Standard error of economy ~ 4.0 / sqrt(overs)
            death_overs = death_balls / 6.0
            se_death_econ = 4.0 / math.sqrt(death_overs) if death_overs > 0 else np.nan
            ci_lower = death_econ - 1.96 * se_death_econ
            ci_upper = death_econ + 1.96 * se_death_econ
            
            bowler_phase_records.append({
                "bowler_id": bid,
                "bowler_name": bname,
                "assigned_role": role,
                "is_dual_phase": is_dual,
                "total_legal": total_legal,
                "pp_legal": pp_balls,
                "death_legal": death_balls,
                "death_debit_runs": death_stats["bowler_debit_runs"],
                "actual_death_econ": death_econ,
                "se_death_econ": se_death_econ,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "phase_expected_death": phase_death_expected,
                "role_expected": role_expected,
                "delta_econ_phase_context": delta_phase,
                "delta_econ_career_role": delta_role,
                "distortion_rpo": distortion
            })
            
    df_matched = pd.DataFrame(bowler_phase_records)
    
    # Dual-phase bowlers subset
    df_dual_matched = df_matched[df_matched["is_dual_phase"]].copy()
    
    # Statistical comparison between dual-phase pacers and pure death specialists in death overs
    pure_death_spec = df_matched[df_matched["assigned_role"] == "Death Specialist"]
    
    dual_death_mean_econ = float(np.average(df_dual_matched["actual_death_econ"], weights=df_dual_matched["death_legal"]))
    pure_death_mean_econ = float(np.average(pure_death_spec["actual_death_econ"], weights=pure_death_spec["death_legal"])) if len(pure_death_spec) > 0 else np.nan
    
    return {
        "df_matched": df_matched,
        "df_dual_matched": df_dual_matched,
        "phase_baselines": phase_baselines,
        "role_baselines": role_baselines,
        "dual_death_mean_econ": dual_death_mean_econ,
        "pure_death_mean_econ": pure_death_mean_econ,
        "average_distortion_rpo": float(df_dual_matched["distortion_rpo"].mean()) if len(df_dual_matched) > 0 else 0.0
    }
