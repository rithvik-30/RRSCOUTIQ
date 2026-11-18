"""
RR ScoutIQ — Milestone M5.5-B.4.3: Matched Fairness & LOPO Counterfactual Engine
Module: src/m5_5b_4_3/bowler_fairness_matched_b4_3.py

Remediates audit defect (Correction B):
1. Genuine Leave-One-Player-Out (LOPO) decontamination:
   - Evaluated bowler's own deliveries across ALL phases are strictly excised from role x tier benchmarks.
   - Evaluated bowler's death deliveries are strictly excised from context cell benchmarks.
   - Handles empty/sparse remaining benchmarks cleanly with explicit fallbacks and status tags (never silently falling back to contaminated totals).
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


def run_player_match_fairness_analysis_b43(
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
    for (rl, tr), r_df in df.groupby(["bowler_role", "tier_clean"]):
        stats = calculate_bowler_economy(r_df)
        role_tier_totals[(rl, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Role overall totals: role -> (total_runs, total_legal_balls)
    role_overall_totals = {}
    for rl, r_df in df.groupby("bowler_role"):
        stats = calculate_bowler_economy(r_df)
        role_overall_totals[rl] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Player cell totals: (bowler_id, phase, tier) -> (player_runs, player_legal_balls)
    player_cell_totals = {}
    for (bid, ph, tr), p_df in df.groupby(["bowler_id", "phase_clean", "tier_clean"]):
        stats = calculate_bowler_economy(p_df)
        player_cell_totals[(bid, ph, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Player phase totals: (bowler_id, phase) -> (player_runs, player_legal_balls)
    player_phase_totals = {}
    for (bid, ph), p_df in df.groupby(["bowler_id", "phase_clean"]):
        stats = calculate_bowler_economy(p_df)
        player_phase_totals[(bid, ph)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Player tier totals across all phases: (bowler_id, tier) -> (player_runs, player_legal_balls)
    player_tier_totals = {}
    for (bid, tr), p_df in df.groupby(["bowler_id", "tier_clean"]):
        stats = calculate_bowler_economy(p_df)
        player_tier_totals[(bid, tr)] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # Player overall career totals: bowler_id -> (player_runs, player_legal_balls)
    player_overall_totals = {}
    for bid, p_df in df.groupby("bowler_id"):
        stats = calculate_bowler_economy(p_df)
        player_overall_totals[bid] = (stats["bowler_debit_runs"], stats["legal_balls"])
        
    # 2. Eligible Bowlers (>= 144 total legal balls)
    eligible_details = role_details[role_details["total_legal"] >= 144].copy()
    eligible_ids = set(eligible_details["bowler_id"])
    
    dual_mask = (eligible_details["pp_pct"] >= 0.40) & (eligible_details["death_pct"] >= 0.30)
    dual_ids = set(eligible_details[dual_mask]["bowler_id"])
    
    # 3. Deliveries by phase
    death_delivs = df[df["phase_clean"] == "death"]
    pp_delivs = df[df["phase_clean"] == "powerplay"]
    
    player_fairness_records = []
    
    for bid in eligible_ids:
        b_df = df[df["bowler_id"] == bid]
        b_name = b_df["bowler_name"].iloc[0]
        role = role_map.get(bid, "Middle Enforcer")
        is_dual = bid in dual_ids
        
        b_death = death_delivs[death_delivs["bowler_id"] == bid]
        b_pp = pp_delivs[pp_delivs["bowler_id"] == bid]
        
        d_stats = calculate_bowler_economy(b_death)
        pp_stats = calculate_bowler_economy(b_pp)
        
        n_death_legal = d_stats["legal_balls"]
        n_pp_legal = pp_stats["legal_balls"]
        
        # Check screening threshold: >= 30 legal balls in each phase
        if n_death_legal >= 30 and n_pp_legal >= 30:
            econ_death_career = d_stats["economy_rate"]
            econ_pp_career = pp_stats["economy_rate"]
            
            # --- Matched Player-Match Phase Contrasts ---
            paired_match_records = []
            
            pp_by_m = {mid: m for mid, m in b_pp.groupby("match_id")}
            death_by_m = {mid: m for mid, m in b_death.groupby("match_id")}
            common_matches = set(pp_by_m.keys()).intersection(set(death_by_m.keys()))
            
            for mid in common_matches:
                m_pp = pp_by_m[mid]
                m_death = death_by_m[mid]
                
                n_pp_m = int(m_pp["ext_is_legal_delivery"].sum())
                n_d_m = int(m_death["ext_is_legal_delivery"].sum())
                
                if n_pp_m >= 6 and n_d_m >= 6:
                    r_pp_m = float(m_pp["ext_bowler_debit_runs"].sum())
                    r_d_m = float(m_death["ext_bowler_debit_runs"].sum())
                    
                    econ_pp_m = 6.0 * (r_pp_m / n_pp_m)
                    econ_d_m = 6.0 * (r_d_m / n_d_m)
                    diff_m = econ_d_m - econ_pp_m
                    
                    # Harmonic weight for unequal legal-ball exposure
                    h_weight = 2.0 / ((1.0 / n_pp_m) + (1.0 / n_d_m))
                    paired_match_records.append({
                        "match_id": mid,
                        "n_pp": n_pp_m,
                        "n_death": n_d_m,
                        "econ_pp": econ_pp_m,
                        "econ_death": econ_d_m,
                        "diff": diff_m,
                        "weight": h_weight
                    })
                    
            n_paired_matches = len(paired_match_records)
            
            if n_paired_matches >= 3:
                df_paired = pd.DataFrame(paired_match_records)
                weights = df_paired["weight"].values
                diffs = df_paired["diff"].values
                sum_w = np.sum(weights)
                
                weighted_paired_shift = float(np.sum(weights * diffs) / sum_w)
                
                # Match cluster-robust standard error around the paired estimand
                resids = diffs - weighted_paired_shift
                weighted_var = np.sum((weights ** 2) * (resids ** 2)) / (sum_w ** 2)
                dof_adj = n_paired_matches / (n_paired_matches - 1)
                shift_se = float(math.sqrt(weighted_var * dof_adj))
                
                ci_low = weighted_paired_shift - 1.96 * shift_se
                ci_high = weighted_paired_shift + 1.96 * shift_se
                paired_status = "VALID_MATCHED_CONTRAST"
            else:
                weighted_paired_shift = econ_death_career - econ_pp_career
                shift_se = np.nan
                ci_low = np.nan
                ci_high = np.nan
                paired_status = "INSUFFICIENT_PAIRED_MATCHES"
                
            # --- Leave-One-Player-Out (LOPO) Counterfactual Benchmarks ---
            # Evaluated strictly on this bowler's exact legal death delivery sequence
            legal_death_delivs = b_death[b_death["ext_is_legal_delivery"] == 1]
            
            exp_runs_phase_lopo = 0.0
            exp_runs_role_lopo = 0.0
            
            role_fallback_count = 0
            cell_fallback_count = 0
            
            for _, row in legal_death_delivs.iterrows():
                tr = row["tier_clean"]
                
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
                # Full decontamination: excise all deliveries bowler contributed to tier tr across PP, Middle, and Death
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


if __name__ == "__main__":
    print("[M5.5-B.4.3] Executing Genuine LOPO Matched Fairness Analysis...")
    res = run_player_match_fairness_analysis_b43()
    os.makedirs("audit_reports/M5_5B_4_3", exist_ok=True)
    out_csv = "audit_reports/M5_5B_4_3/M5_5B_4_3_PLAYER_FAIRNESS_DIAGNOSTICS.csv"
    res["df_all_matched"].to_csv(out_csv, index=False)
    print(f"Saved: {out_csv} ({len(res['df_all_matched'])} bowlers)")
    print(f"Dual-Phase Bowlers: {res['dual_count']} (Valid Paired: {res['dual_valid_paired_count']})")
    print(f"Mean Paired Phase Shift: {res['dual_mean_paired_shift']:.3f} RPO")
    print(f"LOPO Counterfactual Gaps: [{res['dual_min_counterfactual_gap']:.3f}, {res['dual_max_counterfactual_gap']:.3f}] RPO (Mean: {res['dual_mean_counterfactual_gap']:.3f})")
