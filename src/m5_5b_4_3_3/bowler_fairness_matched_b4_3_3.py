"""
RR ScoutIQ — Milestone M5.5-B.4.3.3: Matched Fairness & LOPO Counterfactual Engine
Module: src/m5_5b_4_3_1/bowler_fairness_matched_b4_3_3.py

Remediates audit defect:
1. Genuine Leave-One-Player-Out (LOPO) decontamination:
   - Evaluated bowler's own deliveries across ALL phases are strictly excised from role x tier benchmarks.
   - Evaluated bowler's death deliveries are strictly excised from context cell benchmarks.
   - Handles empty/sparse remaining benchmarks cleanly with explicit fallbacks and status tags.
2. Genuinely paired player-match phase contrasts:
   - Evaluates within-bowler phase shifts strictly on matches where the bowler
     bowled >= 6 legal balls in Powerplay AND >= 6 legal balls in Death.
   - Weights unequal legal-ball exposure via harmonic precision weighting.
   - Computes match cluster-robust standard errors around the exact paired estimand.
   - Explicit INSUFFICIENT_PAIRED_MATCHES state for < 3 paired matches.
3. Player-specific counterfactual benchmark gaps evaluated on identical legal delivery sequences.
4. Purely descriptive framing; zero causal assertions.
"""

import math
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy, derive_training_bowler_roles_b2


def run_player_match_fairness_analysis_b433(
    data_path: str = "data/processed/m5_3/match_state_full.csv"
) -> Dict[str, Any]:
    df = load_clean_deliveries(data_path)
    df["phase_clean"] = df["pre_match_phase"].str.lower()
    df["tier_clean"] = df["pre_pressure_tier"].astype(str)
    
    # 1. Bowler roles
    role_map, role_details = derive_training_bowler_roles_b2(df)
    df["bowler_role"] = df["bowler_id"].map(role_map).fillna("Middle Enforcer")
    
    # League baseline
    league_stats = calculate_bowler_economy(df)
    league_econ_rpo = league_stats["economy_rate"]
    
    # Pre-aggregate cell totals: (phase, tier) -> (total_runs, total_legal_balls)
    cell_totals = {}
    for (ph, tr), c_df in df.groupby(["phase_clean", "tier_clean"]):
        stats = calculate_bowler_economy(c_df)
        cell_totals[(ph, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Phase totals: phase -> (total_runs, total_legal_balls)
    phase_totals = {}
    for ph, p_df in df.groupby("phase_clean"):
        stats = calculate_bowler_economy(p_df)
        phase_totals[ph] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Role x Tier totals: (role, tier) -> (total_runs, total_legal_balls) across all phases
    role_tier_totals = {}
    for (role, tr), r_df in df.groupby(["bowler_role", "tier_clean"]):
        stats = calculate_bowler_economy(r_df)
        role_tier_totals[(role, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Role overall totals: role -> (total_runs, total_legal_balls)
    role_overall_totals = {}
    for role, r_df in df.groupby("bowler_role"):
        stats = calculate_bowler_economy(r_df)
        role_overall_totals[role] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Pre-aggregate individual player totals
    # (player, phase, tier) -> (runs, balls)
    player_cell_totals = {}
    for (bid, ph, tr), p_df in df.groupby(["bowler_id", "phase_clean", "tier_clean"]):
        stats = calculate_bowler_economy(p_df)
        player_cell_totals[(bid, ph, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # (player, phase) -> (runs, balls)
    player_phase_totals = {}
    for (bid, ph), p_df in df.groupby(["bowler_id", "phase_clean"]):
        stats = calculate_bowler_economy(p_df)
        player_phase_totals[(bid, ph)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # (player, tier) -> (runs, balls across ALL phases)
    player_tier_totals = {}
    for (bid, tr), p_df in df.groupby(["bowler_id", "tier_clean"]):
        stats = calculate_bowler_economy(p_df)
        player_tier_totals[(bid, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # player overall career: player -> (runs, balls)
    player_overall_totals = {}
    for bid, p_df in df.groupby("bowler_id"):
        stats = calculate_bowler_economy(p_df)
        player_overall_totals[bid] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Identify dual-phase qualification: >= 60 legal balls in Powerplay AND >= 60 in Death
    player_fairness_records = []
    
    for bid, b_grp in df.groupby("bowler_id"):
        b_name = b_grp["bowler_name"].iloc[0] if "bowler_name" in b_grp.columns else "Unknown"
        role = role_map.get(bid, "Middle Enforcer")
        
        pp_delivs = b_grp[b_grp["phase_clean"] == "powerplay"]
        death_delivs = b_grp[b_grp["phase_clean"] == "death"]
        
        n_pp_legal = int(pp_delivs["ext_is_legal_delivery"].sum())
        n_death_legal = int(death_delivs["ext_is_legal_delivery"].sum())
        
        is_dual = (n_pp_legal >= 60) and (n_death_legal >= 60)
        
        econ_pp_career = calculate_bowler_economy(pp_delivs)["economy_rate"] if n_pp_legal > 0 else np.nan
        econ_death_career = calculate_bowler_economy(death_delivs)["economy_rate"] if n_death_legal > 0 else np.nan
        
        # 1. Genuinely Paired Match-Level Phase Contrasts
        # Bowler must have bowled >= 6 legal balls in PP AND >= 6 legal balls in Death IN THE SAME MATCH
        pp_match_stats = pp_delivs.groupby("match_id").apply(
            lambda g: calculate_bowler_economy(g), include_groups=False
        )
        death_match_stats = death_delivs.groupby("match_id").apply(
            lambda g: calculate_bowler_economy(g), include_groups=False
        )
        
        paired_matches = set(pp_match_stats.index).intersection(set(death_match_stats.index))
        valid_paired_matches = []
        
        match_diffs = []
        match_weights = []
        
        for mid in paired_matches:
            s_pp = pp_match_stats.loc[mid]
            s_death = death_match_stats.loc[mid]
            
            b_pp = s_pp["legal_balls"]
            b_death = s_death["legal_balls"]
            
            if b_pp >= 6 and b_death >= 6:
                diff_m = s_death["economy_rate"] - s_pp["economy_rate"]
                # Harmonic exposure weight: 2 / (1/b_pp + 1/b_death)
                w_m = (2.0 * b_pp * b_death) / (b_pp + b_death)
                match_diffs.append(diff_m)
                match_weights.append(w_m)
                valid_paired_matches.append(mid)
                
        n_paired_matches = len(valid_paired_matches)
        
        if n_paired_matches >= 3:
            w_arr = np.array(match_weights)
            d_arr = np.array(match_diffs)
            weighted_paired_shift = float(np.sum(w_arr * d_arr) / np.sum(w_arr))
            
            # Match cluster-robust standard error of weighted mean difference
            resids = d_arr - weighted_paired_shift
            norm_w = w_arr / np.sum(w_arr)
            var_shift = float(np.sum((norm_w * resids) ** 2) * (n_paired_matches / (n_paired_matches - 1)))
            shift_se = math.sqrt(max(0.0, var_shift))
            ci_low = weighted_paired_shift - 1.96 * shift_se
            ci_high = weighted_paired_shift + 1.96 * shift_se
            paired_status = "VALID_MATCHED_CONTRAST"
        else:
            weighted_paired_shift = np.nan
            shift_se = np.nan
            ci_low = np.nan
            ci_high = np.nan
            paired_status = "INSUFFICIENT_PAIRED_MATCHES"
            
        # 2. Genuine LOPO Counterfactual Expectation on Evaluated Death Balls
        exp_econ_phase_lopo = np.nan
        exp_econ_role_lopo = np.nan
        player_specific_gap = np.nan
        lopo_status = "NO_DEATH_DELIVERIES"
        
        if n_death_legal > 0:
            legal_death = death_delivs[death_delivs["ext_is_legal_delivery"] == 1]
            exp_runs_phase_lopo = 0.0
            exp_runs_role_lopo = 0.0
            
            cell_fallback_count = 0
            role_fallback_count = 0
            
            for _, deliv in legal_death.iterrows():
                tr = deliv["tier_clean"]
                
                # 1. LOPO Context Cell Expectation
                tot_c_runs, tot_c_balls = cell_totals.get(("death", tr), (10.0, 6))
                p_c_runs, p_c_balls = player_cell_totals.get((bid, "death", tr), (0.0, 0))
                rem_c_runs = tot_c_runs - p_c_runs
                rem_c_balls = tot_c_balls - p_c_balls
                
                if rem_c_balls >= 30:
                    rpb_phase_lopo = rem_c_runs / rem_c_balls
                else:
                    # Clean fallback: excise bowler's death balls from Death Phase totals
                    ph_runs, ph_balls = phase_totals.get("death", (10.0, 6))
                    p_death_runs, p_death_balls = player_phase_totals.get((bid, "death"), (0.0, 0))
                    rem_ph_runs = ph_runs - p_death_runs
                    rem_ph_balls = ph_balls - p_death_balls
                    if rem_ph_balls >= 30:
                        rpb_phase_lopo = rem_ph_runs / rem_ph_balls
                    else:
                        rpb_phase_lopo = league_econ_rpo / 6.0
                    cell_fallback_count += 1
                exp_runs_phase_lopo += rpb_phase_lopo
                
                # 2. LOPO Role Expectation (EXCISE BOWLER ACROSS ALL PHASES FOR THIS TIER)
                tot_r_runs, tot_r_balls = role_tier_totals.get((role, tr), (9.0, 6))
                p_tier_runs, p_tier_balls = player_tier_totals.get((bid, tr), (0.0, 0))
                rem_r_runs = tot_r_runs - p_tier_runs
                rem_r_balls = tot_r_balls - p_tier_balls
                
                if rem_r_balls >= 30:
                    rpb_role_lopo = rem_r_runs / rem_r_balls
                else:
                    # Clean fallback: excise bowler across all tiers for that role
                    ov_r_runs, ov_r_balls = role_overall_totals.get(role, (9.0, 6))
                    ov_p_runs, ov_p_balls = player_overall_totals.get(bid, (0.0, 0))
                    rem_ov_runs = ov_r_runs - ov_p_runs
                    rem_ov_balls = ov_r_balls - ov_p_balls
                    if rem_ov_balls >= 30:
                        rpb_role_lopo = rem_ov_runs / rem_ov_balls
                    else:
                        rpb_role_lopo = league_econ_rpo / 6.0
                    role_fallback_count += 1
                exp_runs_role_lopo += rpb_role_lopo
                
            exp_econ_phase_lopo = (exp_runs_phase_lopo / n_death_legal) * 6.0
            exp_econ_role_lopo = (exp_runs_role_lopo / n_death_legal) * 6.0
            
            # Non-constant descriptive counterfactual gap
            player_specific_gap = exp_econ_role_lopo - exp_econ_phase_lopo
            
            lopo_status = "GENUINE_FULL_DECONTAMINATED_LOPO"
            if role_fallback_count > 0 or cell_fallback_count > 0:
                lopo_status = f"LOPO_WITH_EXPLICIT_FALLBACKS(cell_fb={cell_fallback_count},role_fb={role_fallback_count})"
                
            player_fairness_records.append({
                "bowler_id": bid,
                "bowler_name": b_name,
                "assigned_role": role,
                "is_dual_phase": is_dual,
                "death_legal_balls": n_death_legal,
                "pp_legal_balls": n_pp_legal,
                "paired_matches_count": n_paired_matches,
                "paired_contrast_status": paired_status,
                "career_pp_econ": econ_pp_career,
                "career_death_econ": econ_death_career,
                "weighted_paired_phase_shift": weighted_paired_shift,
                "shift_cluster_se": shift_se,
                "shift_ci_lower": ci_low,
                "shift_ci_upper": ci_high,
                "lopo_context_expected_death_econ": exp_econ_phase_lopo,
                "lopo_role_expected_death_econ": exp_econ_role_lopo,
                "player_specific_counterfactual_gap": player_specific_gap,
                "lopo_status": lopo_status
            })
            
    df_fairness = pd.DataFrame(player_fairness_records)
    dual_fairness = df_fairness[df_fairness["is_dual_phase"]].copy()
    valid_paired_dual = dual_fairness[dual_fairness["paired_contrast_status"] == "VALID_MATCHED_CONTRAST"]
    
    return {
        "df_all_matched": df_fairness,
        "df_dual_matched": dual_fairness,
        "dual_count": len(dual_fairness),
        "dual_valid_paired_count": len(valid_paired_dual),
        "dual_mean_paired_shift": float(valid_paired_dual["weighted_paired_phase_shift"].mean()) if len(valid_paired_dual) > 0 else np.nan,
        "dual_mean_counterfactual_gap": float(dual_fairness["player_specific_counterfactual_gap"].mean()) if len(dual_fairness) > 0 else np.nan,
        "dual_min_counterfactual_gap": float(dual_fairness["player_specific_counterfactual_gap"].min()) if len(dual_fairness) > 0 else np.nan,
        "dual_max_counterfactual_gap": float(dual_fairness["player_specific_counterfactual_gap"].max()) if len(dual_fairness) > 0 else np.nan
    }
