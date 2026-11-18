"""
RR ScoutIQ — Milestone M5.5-B.2: Bowler Fairness & Dual-Phase Player-Level Analysis
Module: src/m5_5b_2/bowler_fairness_b2.py

Investigates:
1. Reconciled bowler role classification with documented workload dominance tiebreak.
2. Player-level evaluation of all 21 dual-phase bowlers across Powerplay, Middle, and Death.
3. Compares delivery-level contextual phase baseline (Option A) vs career role baseline (Option B).
4. Quantifies player-level residual differences, sample sizes, and distortion.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
from typing import Dict, List, Any
import numpy as np
import pandas as pd

from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy, derive_training_bowler_roles_b2


def run_bowler_fairness_analysis_b2(
    data_path: str = "data/processed/m5_3/match_state_full.csv"
) -> Dict[str, Any]:
    df = load_clean_deliveries(data_path)
    df["phase_clean"] = df["pre_match_phase"].str.lower()
    
    # 1. Classification & Workload Dominance
    role_map, role_details = derive_training_bowler_roles_b2(df)
    
    # Merge bowler roles back onto delivery dataframe
    df["bowler_role"] = df["bowler_id"].map(role_map).fillna("Middle Enforcer")
    
    # 2. Identify Dual-Phase Bowlers (Total legal >= 144, pp_pct >= 0.40, death_pct >= 0.30)
    eligible_details = role_details[role_details["total_legal"] >= 144].copy()
    dual_mask = (eligible_details["pp_pct"] >= 0.40) & (eligible_details["death_pct"] >= 0.30)
    dual_bowlers = eligible_details[dual_mask].copy()
    
    # Add bowler names
    bowler_names = df.groupby("bowler_id")["bowler_name"].first()
    dual_bowlers["bowler_name"] = dual_bowlers["bowler_id"].map(bowler_names)
    
    # Verify tiebreak consistency
    # Documented rule: pp_pct >= death_pct -> Powerplay Specialist, else Death Specialist
    dual_bowlers["expected_tiebreak_role"] = np.where(
        dual_bowlers["pp_pct"] >= dual_bowlers["death_pct"],
        "Powerplay Specialist",
        "Death Specialist"
    )
    dual_bowlers["tiebreak_matched"] = dual_bowlers["assigned_role"] == dual_bowlers["expected_tiebreak_role"]
    
    # 3. Compute Phase and Role Baselines across entire league (using Law-compliant economy)
    league_phase_econ = {}
    for phase, p_df in df.groupby("phase_clean"):
        stats = calculate_bowler_economy(p_df)
        league_phase_econ[phase] = stats["economy_rate"]
        
    role_baselines = {}
    for role, r_df in df.groupby("bowler_role"):
        stats = calculate_bowler_economy(r_df)
        role_baselines[role] = stats["economy_rate"]
        
    # 4. Player-Level Evaluation of Dual-Phase Bowlers in Death Overs
    death_delivs = df[df["phase_clean"] == "death"]
    player_level_records = []
    
    for _, b in dual_bowlers.iterrows():
        bid = b["bowler_id"]
        bname = b["bowler_name"]
        role = b["assigned_role"]
        
        b_death = death_delivs[death_delivs["bowler_id"] == bid]
        b_econ_stats = calculate_bowler_economy(b_death)
        
        actual_death_econ = b_econ_stats["economy_rate"]
        legal_death_balls = b_econ_stats["legal_balls"]
        total_death_debit = b_econ_stats["bowler_debit_runs"]
        
        # Baselines
        phase_expected_econ = league_phase_econ.get("death", 9.62)
        role_expected_econ = role_baselines.get(role, 8.46)
        
        # Residuals (Positive residual = conceded fewer runs than expected, i.e. saving runs)
        # Delta Econ = Expected - Actual
        delta_econ_phase = phase_expected_econ - actual_death_econ if np.isfinite(actual_death_econ) else np.nan
        delta_econ_role = role_expected_econ - actual_death_econ if np.isfinite(actual_death_econ) else np.nan
        
        # Distortion = Delta Role - Delta Phase = Role Expected - Phase Expected
        distortion = role_expected_econ - phase_expected_econ
        
        player_level_records.append({
            "bowler_id": bid,
            "bowler_name": bname,
            "total_career_legal": b["total_legal"],
            "pp_pct": b["pp_pct"],
            "death_pct": b["death_pct"],
            "assigned_role": role,
            "death_legal_balls": legal_death_balls,
            "death_debit_runs": total_death_debit,
            "actual_death_econ": actual_death_econ,
            "phase_expected_econ": phase_expected_econ,
            "role_expected_econ": role_expected_econ,
            "delta_econ_phase_context": delta_econ_phase,
            "delta_econ_career_role": delta_econ_role,
            "distortion_rpo": distortion
        })
        
    df_player_level = pd.DataFrame(player_level_records)
    
    # 5. Aggregate Performance of Dual Bowlers in Death Overs
    dual_ids = set(dual_bowlers["bowler_id"])
    dual_death_delivs = death_delivs[death_delivs["bowler_id"].isin(dual_ids)]
    dual_death_stats = calculate_bowler_economy(dual_death_delivs)
    
    aggregate_death_econ = dual_death_stats["economy_rate"]
    aggregate_distortion = role_baselines.get("Powerplay Specialist", 8.46) - league_phase_econ.get("death", 9.62)
    
    return {
        "role_details": role_details,
        "dual_bowlers": dual_bowlers,
        "player_level_death": df_player_level,
        "league_phase_econ": league_phase_econ,
        "role_baselines": role_baselines,
        "aggregate_death_econ": aggregate_death_econ,
        "aggregate_distortion": aggregate_distortion
    }


if __name__ == "__main__":
    res = run_bowler_fairness_analysis_b2()
    print("=== DUAL-PHASE BOWLER FAIRNESS RECONCILIATION ===")
    print(f"Total Dual-Phase Bowlers: {len(res['dual_bowlers'])}")
    print(f"Tiebreak matches 100%: {res['dual_bowlers']['tiebreak_matched'].all()}")
    print(f"League Death Economy: {res['league_phase_econ'].get('death'):.3f} RPO")
    print(f"Powerplay Specialist Role Economy: {res['role_baselines'].get('Powerplay Specialist'):.3f} RPO")
    print(f"Dual Bowlers Actual Death Economy: {res['aggregate_death_econ']:.3f} RPO")
    print(f"Aggregate Systematic Distortion: {res['aggregate_distortion']:.3f} RPO")
    print("\nSample Player-Level Death Over Performance:")
    print(res["player_level_death"][["bowler_name", "assigned_role", "death_legal_balls", "actual_death_econ", "delta_econ_phase_context", "delta_econ_career_role", "distortion_rpo"]].head(10))
