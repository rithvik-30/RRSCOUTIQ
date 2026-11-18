"""
RR ScoutIQ — Milestone M5.5-B.4.3.8: Matched Fairness & LPMO Counterfactual Engine
Module: src/m5_5b_4_3_8/bowler_fairness_matched_b4_3_8.py

Remediates audit defect:
1. Genuine Leave-Player-and-Matches-Out (LPMO) decontamination:
   - Evaluated bowler's participated matches (bowling or batting) are strictly excised
     from all contextual and role benchmark calculations.
   - 100% of deliveries in any match involving the player are excluded to prevent
     shared-match environmental shock contamination.
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
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy, derive_training_bowler_roles_b2


def run_player_match_fairness_analysis_b437(
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
    cell_totals: Dict[Tuple[str, str], Tuple[float, int]] = {}
    for (ph, tr), c_df in df.groupby(["phase_clean", "tier_clean"]):
        stats = calculate_bowler_economy(c_df)
        cell_totals[(ph, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Phase totals: phase -> (total_runs, total_legal_balls)
    phase_totals: Dict[str, Tuple[float, int]] = {}
    for ph, p_df in df.groupby("phase_clean"):
        stats = calculate_bowler_economy(p_df)
        phase_totals[ph] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Role x Tier totals: (role, tier) -> (total_runs, total_legal_balls) across all phases
    role_tier_totals: Dict[Tuple[str, str], Tuple[float, int]] = {}
    for (role, tr), r_df in df.groupby(["bowler_role", "tier_clean"]):
        stats = calculate_bowler_economy(r_df)
        role_tier_totals[(role, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Role overall totals: role -> (total_runs, total_legal_balls)
    role_overall_totals: Dict[str, Tuple[float, int]] = {}
    for role, r_df in df.groupby("bowler_role"):
        stats = calculate_bowler_economy(r_df)
        role_overall_totals[role] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Match-level aggregates for fast LPMO subtraction
    # (phase, tier, match_id) -> (runs, balls)
    match_cell_totals: Dict[Tuple[str, str, Any], Tuple[float, int]] = {}
    for (ph, tr, mid), mc_df in df.groupby(["phase_clean", "tier_clean", "match_id"]):
        stats = calculate_bowler_economy(mc_df)
        match_cell_totals[(ph, tr, mid)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # (phase, match_id) -> (runs, balls)
    match_phase_totals: Dict[Tuple[str, Any], Tuple[float, int]] = {}
    for (ph, mid), mp_df in df.groupby(["phase_clean", "match_id"]):
        stats = calculate_bowler_economy(mp_df)
        match_phase_totals[(ph, mid)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # (role, tier, match_id) -> (runs, balls)
    match_role_tier_totals: Dict[Tuple[str, str, Any], Tuple[float, int]] = {}
    for (role, tr, mid), mr_df in df.groupby(["bowler_role", "tier_clean", "match_id"]):
        stats = calculate_bowler_economy(mr_df)
        match_role_tier_totals[(role, tr, mid)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # (role, match_id) -> (runs, balls)
    match_role_totals: Dict[Tuple[str, Any], Tuple[float, int]] = {}
    for (role, mid), mo_df in df.groupby(["bowler_role", "match_id"]):
        stats = calculate_bowler_economy(mo_df)
        match_role_totals[(role, mid)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Build complete mapping of player -> all participated match IDs (bowling or batting)
    player_matches: Dict[str, Set[Any]] = {}
    if "bowler_id" in df.columns:
        for bid, b_grp in df.groupby("bowler_id"):
            player_matches.setdefault(str(bid), set()).update(b_grp["match_id"].unique())
    if "batter_id" in df.columns:
        for batid, bat_grp in df.groupby("batter_id"):
            player_matches.setdefault(str(batid), set()).update(bat_grp["match_id"].unique())

    player_fairness_records = []
    
    for bid, b_grp in df.groupby("bowler_id"):
        bid_str = str(bid)
        b_name = b_grp["bowler_name"].iloc[0] if "bowler_name" in b_grp.columns else "Unknown"
        role = role_map.get(bid, "Middle Enforcer")
        p_matches = player_matches.get(bid_str, set())
        
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
            
        # 2. Genuine LPMO Counterfactual Expectation on Evaluated Death Balls
        exp_econ_phase_lpmo = np.nan
        exp_econ_role_lpmo = np.nan
        player_specific_gap = np.nan
        lpmo_status = "NO_DEATH_DELIVERIES"
        
        if n_death_legal > 0:
            legal_death = death_delivs[death_delivs["ext_is_legal_delivery"] == 1]
            exp_runs_phase_lpmo = 0.0
            exp_runs_role_lpmo = 0.0
            
            cell_fallback_count = 0
            role_fallback_count = 0
            
            tier_counts = legal_death["tier_clean"].value_counts().to_dict()
            for tr, t_count in tier_counts.items():
                # 1. LPMO Context Cell Expectation: excise all matches in p_matches
                tot_c_runs, tot_c_balls = cell_totals.get(("death", tr), (10.0, 6))
                exc_c_runs = sum(match_cell_totals.get(("death", tr, m), (0.0, 0))[0] for m in p_matches)
                exc_c_balls = sum(match_cell_totals.get(("death", tr, m), (0.0, 0))[1] for m in p_matches)
                rem_c_runs = tot_c_runs - exc_c_runs
                rem_c_balls = tot_c_balls - exc_c_balls
                
                if rem_c_balls >= 30:
                    rpb_phase_lpmo = rem_c_runs / rem_c_balls
                else:
                    # Clean fallback: excise bowler's matches from Death Phase totals
                    ph_runs, ph_balls = phase_totals.get("death", (10.0, 6))
                    exc_ph_runs = sum(match_phase_totals.get(("death", m), (0.0, 0))[0] for m in p_matches)
                    exc_ph_balls = sum(match_phase_totals.get(("death", m), (0.0, 0))[1] for m in p_matches)
                    rem_ph_runs = ph_runs - exc_ph_runs
                    rem_ph_balls = ph_balls - exc_ph_balls
                    if rem_ph_balls >= 30:
                        rpb_phase_lpmo = rem_ph_runs / rem_ph_balls
                    else:
                        rpb_phase_lpmo = league_econ_rpo / 6.0
                    cell_fallback_count += t_count
                exp_runs_phase_lpmo += rpb_phase_lpmo * t_count
                
                # 2. LPMO Role Expectation: excise bowler's matches across ALL phases for this tier
                tot_r_runs, tot_r_balls = role_tier_totals.get((role, tr), (9.0, 6))
                exc_r_runs = sum(match_role_tier_totals.get((role, tr, m), (0.0, 0))[0] for m in p_matches)
                exc_r_balls = sum(match_role_tier_totals.get((role, tr, m), (0.0, 0))[1] for m in p_matches)
                rem_r_runs = tot_r_runs - exc_r_runs
                rem_r_balls = tot_r_balls - exc_r_balls
                
                if rem_r_balls >= 30:
                    rpb_role_lpmo = rem_r_runs / rem_r_balls
                else:
                    # Clean fallback: excise bowler's matches across all tiers for that role
                    ov_r_runs, ov_r_balls = role_overall_totals.get(role, (9.0, 6))
                    exc_ov_runs = sum(match_role_totals.get((role, m), (0.0, 0))[0] for m in p_matches)
                    exc_ov_balls = sum(match_role_totals.get((role, m), (0.0, 0))[1] for m in p_matches)
                    rem_ov_runs = ov_r_runs - exc_ov_runs
                    rem_ov_balls = ov_r_balls - exc_ov_balls
                    if rem_ov_balls >= 30:
                        rpb_role_lpmo = rem_ov_runs / rem_ov_balls
                    else:
                        rpb_role_lpmo = league_econ_rpo / 6.0
                    role_fallback_count += t_count
                exp_runs_role_lpmo += rpb_role_lpmo * t_count
                
            exp_econ_phase_lpmo = (exp_runs_phase_lpmo / n_death_legal) * 6.0
            exp_econ_role_lpmo = (exp_runs_role_lpmo / n_death_legal) * 6.0
            
            # Non-constant descriptive counterfactual gap
            player_specific_gap = exp_econ_role_lpmo - exp_econ_phase_lpmo
            
            lpmo_status = "GENUINE_FULL_DECONTAMINATED_LPMO"
            if role_fallback_count > 0 or cell_fallback_count > 0:
                lpmo_status = f"LPMO_WITH_EXPLICIT_FALLBACKS(cell_fb={cell_fallback_count},role_fb={role_fallback_count})"
                
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
                "lpmo_context_expected_death_econ": exp_econ_phase_lpmo,
                "lpmo_role_expected_death_econ": exp_econ_role_lpmo,
                "lopo_context_expected_death_econ": exp_econ_phase_lpmo,
                "lopo_role_expected_death_econ": exp_econ_role_lpmo,
                "player_specific_counterfactual_gap": player_specific_gap,
                "lpmo_status": lpmo_status,
                "lopo_status": lpmo_status
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


run_player_match_fairness_analysis_b438 = run_player_match_fairness_analysis_b437
run_player_match_fairness_analysis_b436 = run_player_match_fairness_analysis_b437
run_player_match_fairness_analysis_b434 = run_player_match_fairness_analysis_b437
