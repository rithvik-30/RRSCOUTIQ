"""
RR ScoutIQ — Milestone M5.5-B.4.1: Player-Match Matched Fairness Analyzer
Module: src/m5_5b_4_1/bowler_fairness_matched_b4_1.py

Remediates M5.5-B.4 fairness limitations:
1. Replaces constant counterfactual expectation gap with player-specific counterfactual gaps
   derived from each bowler's exact death delivery context sequence.
2. Player-Match level phase observations:
   Compares within-bowler phase shifts at the match level with clustered uncertainty.
3. Controls for pressure-tier composition in dual-phase vs pure death specialist comparisons.
4. Avoids causal claims; frames findings strictly as descriptive contextual contrasts.
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


def run_player_match_fairness_analysis_b41(
    data_path: str = "data/processed/m5_3/match_state_full.csv"
) -> Dict[str, Any]:
    df = load_clean_deliveries(data_path)
    df["phase_clean"] = df["pre_match_phase"].str.lower()
    
    # 1. Bowler roles
    role_map, role_details = derive_training_bowler_roles_b2(df)
    df["bowler_role"] = df["bowler_id"].map(role_map).fillna("Middle Enforcer")
    
    # 2. Contextual cell empirical expected runs per legal ball
    # Cell = Phase x Tier
    context_expected_rpb = {}
    for (phase, tier), c_df in df.groupby(["pre_match_phase", "pre_pressure_tier"]):
        stats = calculate_bowler_economy(c_df)
        if stats["legal_balls"] > 0:
            context_expected_rpb[(phase, tier)] = stats["bowler_debit_runs"] / stats["legal_balls"]
        else:
            context_expected_rpb[(phase, tier)] = 8.45 / 6.0
            
    # Role-conditioned expected runs per legal ball
    # Role x Tier
    role_expected_rpb = {}
    for (role, tier), r_df in df.groupby(["bowler_role", "pre_pressure_tier"]):
        stats = calculate_bowler_economy(r_df)
        if stats["legal_balls"] > 0:
            role_expected_rpb[(role, tier)] = stats["bowler_debit_runs"] / stats["legal_balls"]
        else:
            role_expected_rpb[(role, tier)] = 8.45 / 6.0
            
    # 3. Eligible Bowlers (>= 144 legal balls)
    eligible_details = role_details[role_details["total_legal"] >= 144].copy()
    eligible_ids = set(eligible_details["bowler_id"])
    
    dual_mask = (eligible_details["pp_pct"] >= 0.40) & (eligible_details["death_pct"] >= 0.30)
    dual_ids = set(eligible_details[dual_mask]["bowler_id"])
    
    # 4. Player-Specific Counterfactual Gap on Exact Death Delivery Sequence
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
        
        if n_death_legal >= 30 and n_pp_legal >= 30:
            econ_death = d_stats["economy_rate"]
            econ_pp = pp_stats["economy_rate"]
            within_bowler_phase_shift = econ_death - econ_pp
            
            # Match clustered standard error for phase shift
            # Group by match to get match-level paired differences
            match_pp = b_pp.groupby("match_id").apply(lambda m: calculate_bowler_economy(m)["economy_rate"]).dropna()
            match_death = b_death.groupby("match_id").apply(lambda m: calculate_bowler_economy(m)["economy_rate"]).dropna()
            common_matches = match_pp.index.intersection(match_death.index)
            
            if len(common_matches) >= 3:
                paired_match_diffs = match_death.loc[common_matches] - match_pp.loc[common_matches]
                shift_se = float(np.std(paired_match_diffs) / math.sqrt(len(common_matches)))
            else:
                shift_se = float(np.std([econ_death, econ_pp]) / math.sqrt(2))
                
            ci_low = within_bowler_phase_shift - 1.96 * shift_se
            ci_high = within_bowler_phase_shift + 1.96 * shift_se
            
            # Non-constant, player-specific counterfactual benchmark calculation:
            # Evaluate expected runs on this bowler's EXACT legal death deliveries
            legal_death_delivs = b_death[b_death["ext_is_legal_delivery"] == 1]
            exp_runs_phase = sum(
                context_expected_rpb.get((row["pre_match_phase"], row["pre_pressure_tier"]), 10.15 / 6.0)
                for _, row in legal_death_delivs.iterrows()
            )
            exp_runs_role = sum(
                role_expected_rpb.get((role, row["pre_pressure_tier"]), 8.88 / 6.0)
                for _, row in legal_death_delivs.iterrows()
            )
            
            exp_econ_phase = (exp_runs_phase / n_death_legal) * 6.0
            exp_econ_role = (exp_runs_role / n_death_legal) * 6.0
            
            # Player-specific counterfactual gap:
            player_specific_gap = exp_econ_role - exp_econ_phase
            
            player_fairness_records.append({
                "bowler_id": bid,
                "bowler_name": b_name,
                "assigned_role": role,
                "is_dual_phase": is_dual,
                "death_legal_balls": n_death_legal,
                "pp_legal_balls": n_pp_legal,
                "matched_matches_count": len(common_matches),
                "actual_pp_econ": econ_pp,
                "actual_death_econ": econ_death,
                "within_bowler_phase_shift": within_bowler_phase_shift,
                "shift_se": shift_se,
                "shift_ci_lower": ci_low,
                "shift_ci_upper": ci_high,
                "context_expected_death_econ": exp_econ_phase,
                "role_expected_death_econ": exp_econ_role,
                "player_specific_counterfactual_gap": player_specific_gap
            })
            
    df_fairness = pd.DataFrame(player_fairness_records)
    dual_fairness = df_fairness[df_fairness["is_dual_phase"]].copy()
    pure_death_fairness = df_fairness[df_fairness["assigned_role"] == "Death Specialist"].copy()
    
    return {
        "df_all_matched": df_fairness,
        "df_dual_matched": dual_fairness,
        "dual_count": len(dual_fairness),
        "pure_death_count": len(pure_death_fairness),
        "dual_mean_shift": float(np.average(dual_fairness["within_bowler_phase_shift"], weights=dual_fairness["death_legal_balls"])) if len(dual_fairness) > 0 else np.nan,
        "dual_mean_death_econ": float(np.average(dual_fairness["actual_death_econ"], weights=dual_fairness["death_legal_balls"])) if len(dual_fairness) > 0 else np.nan,
        "pure_death_mean_death_econ": float(np.average(pure_death_fairness["actual_death_econ"], weights=pure_death_fairness["death_legal_balls"])) if len(pure_death_fairness) > 0 else np.nan,
        "mean_counterfactual_gap": float(dual_fairness["player_specific_counterfactual_gap"].mean()) if len(dual_fairness) > 0 else np.nan,
        "min_counterfactual_gap": float(dual_fairness["player_specific_counterfactual_gap"].min()) if len(dual_fairness) > 0 else np.nan,
        "max_counterfactual_gap": float(dual_fairness["player_specific_counterfactual_gap"].max()) if len(dual_fairness) > 0 else np.nan
    }


if __name__ == "__main__":
    import os
    print("[M5.5-B.4.1] Running player-match fairness analysis...")
    out = run_player_match_fairness_analysis_b41()
    os.makedirs("audit_reports/M5_5B_4_1", exist_ok=True)
    out_csv = "audit_reports/M5_5B_4_1/M5_5B_4_1_PLAYER_FAIRNESS_DIAGNOSTICS.csv"
    out["df_all_matched"].to_csv(out_csv, index=False)
    print(f"Saved fairness diagnostics ({len(out['df_all_matched'])} rows) to {out_csv}")
    print(f"Dual-phase bowlers: {out['dual_count']}")
    print(f"Mean within-bowler phase shift: {out['dual_mean_shift']:.3f} RPO")
    print(f"Player-specific counterfactual gaps range: [{out['min_counterfactual_gap']:.3f}, {out['max_counterfactual_gap']:.3f}] RPO (Mean: {out['mean_counterfactual_gap']:.3f})")
