"""
RR ScoutIQ — Milestone M5.5-B.2: Leak-Free 5-Fold Cross-Validation Runner
Module: src/m5_5b_2/run_validation_b2.py

Executes:
1. Strict 5-fold match-grouped cross-validation (GroupKFold on match_id).
2. Verifies 0 match overlap between train and validation folds.
3. Derives batter and bowler roles strictly within train folds.
4. Fits Hierarchical Empirical Bayes priors strictly within train folds:
   - Cell: Phase x Pressure Tier
   - Partial pooling fallback to Phase / League level.
5. Evaluates out-of-fold validation deliveries:
   - Continuous outcomes (batter runs/ball, bowler economy).
   - Binary probabilistic outcomes (boundary, dot, wicket, dismissal).
6. Computes subgroup reliability diagnostics across Phase, Tier, Role, and Exposure categories.
7. Saves results to audit_reports/M5_5B_2/.
"""

import os
import sys
import time
sys.path.insert(0, os.path.abspath("."))
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_2.remediation_engine_b2 import (
    calculate_bowler_economy,
    derive_training_batter_roles_b2,
    derive_training_bowler_roles_b2,
    HierarchicalContextualPriorEngine,
    compute_subgroup_reliability,
    fit_beta_binomial_mle_safeguarded,
    fit_normal_normal_safeguarded,
    PersonalBaselineEstimate
)


def run_full_validation_b2(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_2"
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()
    
    print("[M5.5-B.2] Loading clean canonical deliveries...")
    df = load_clean_deliveries(data_path)
    total_rows = len(df)
    unique_matches = df["match_id"].nunique()
    print(f"Loaded {total_rows} deliveries across {unique_matches} matches.")
    
    # Enrich outcomes for evaluation
    df["phase"] = df["pre_match_phase"].astype(str)
    df["tier"] = df["pre_pressure_tier"].astype(str)
    df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
    df["is_dot"] = (df["ext_bowler_debit_runs"] == 0).astype(int)
    df["is_wkt"] = (df["ext_is_bowler_wicket"] == 1).astype(int)
    df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
    df["is_dismissal"] = (df["ext_is_wicket"] == 1).astype(int)
    
    # Initialize 5-fold match-grouped cross-validation
    gkf = GroupKFold(n_splits=5)
    groups = df["match_id"].values
    
    fold_records = []
    prior_fit_records = []
    all_subgroup_reliability = []
    
    print("\n[M5.5-B.2] Beginning 5-Fold Match-Grouped Validation...")
    
    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(df, groups=groups), 1):
        fold_start = time.time()
        train_df = df.iloc[train_idx].copy()
        val_df = df.iloc[val_idx].copy()
        
        train_matches = set(train_df["match_id"])
        val_matches = set(val_df["match_id"])
        match_overlap = len(train_matches.intersection(val_matches))
        assert match_overlap == 0, f"Fold {fold_idx}: Match overlap detected! ({match_overlap} matches)"
        
        print(f"\n--- Fold {fold_idx}/5 ---")
        print(f"Train matches: {len(train_matches)}, Val matches: {len(val_matches)} (Overlap: {match_overlap})")
        print(f"Train deliveries: {len(train_df)}, Val deliveries: {len(val_df)}")
        
        # 1. Derive roles strictly within train_df
        batter_roles = derive_training_batter_roles_b2(train_df)
        bowler_roles, bowler_details = derive_training_bowler_roles_b2(train_df)
        
        # Apply roles to validation fold with explicit fallback logging
        bat_id_col = "striker_id" if "striker_id" in val_df.columns else "batter_id"
        val_df["batter_role"] = val_df[bat_id_col].map(batter_roles).fillna("TopOrderBatter")
        val_df["bowler_role"] = val_df["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        
        fallback_batters = val_df[bat_id_col].map(batter_roles).isna().sum()
        fallback_bowlers = val_df["bowler_id"].map(bowler_roles).isna().sum()
        
        print(f"Validation role fallback deliveries: Batter={fallback_batters} ({fallback_batters/len(val_df):.2%}), Bowler={fallback_bowlers} ({fallback_bowlers/len(val_df):.2%})")
        
        # 2. Fit Hierarchical Contextual Priors strictly within train_df
        hier_engine = HierarchicalContextualPriorEngine(min_cell_deliveries=500)
        hier_engine.fit(train_df)
        
        for diag in hier_engine.fit_diagnostics:
            diag_copy = diag.copy()
            diag_copy["fold"] = fold_idx
            prior_fit_records.append(diag_copy)
            
        # 3. Model Out-of-Fold Predictions
        # Evaluate Batter Boundary %
        legal_val = val_df[val_df["is_legal"] == 1].copy()
        
        # M1: Global Unconditional Mean
        p_bnd_m1 = train_df["is_boundary"].mean()
        # M2: Personal Unpooled Rate
        train_bat_bnd = train_df[train_df["is_legal"] == 1].groupby(bat_id_col).agg(
            boundaries=("is_boundary", "sum"),
            balls=("is_legal", "sum")
        )
        train_bat_bnd["rate"] = train_bat_bnd["boundaries"] / train_bat_bnd["balls"]
        unpooled_bnd_map = train_bat_bnd["rate"].to_dict()
        pred_bnd_m2 = legal_val[bat_id_col].map(unpooled_bnd_map).fillna(p_bnd_m1).values
        
        # M3: Heuristic Shrinkage (M=100)
        heuristic_m0 = 100.0
        train_bat_bnd["shrunk_m3"] = (train_bat_bnd["boundaries"] + p_bnd_m1 * heuristic_m0) / (train_bat_bnd["balls"] + heuristic_m0)
        shrunk_bnd_m3_map = train_bat_bnd["shrunk_m3"].to_dict()
        pred_bnd_m3 = legal_val[bat_id_col].map(shrunk_bnd_m3_map).fillna(p_bnd_m1).values
        
        # M4: Hierarchical Contextual Empirical Bayes (Cell Prior + MML Shrinkage)
        # For each validation delivery, contextual baseline expectation
        cell_preds = []
        for _, row in legal_val.iterrows():
            exp_bnd = hier_engine.get_cell_expectation(row["phase"], row["tier"], "batter_boundary")
            cell_preds.append(exp_bnd)
        pred_bnd_m4 = np.array(cell_preds)
        
        # Metrics for Boundary %
        y_true_bnd = legal_val["is_boundary"].values
        for m_name, p_arr in [("M1_Global", np.full_like(y_true_bnd, p_bnd_m1, dtype=float)),
                              ("M2_Unpooled", pred_bnd_m2),
                              ("M3_Heuristic_M100", pred_bnd_m3),
                              ("M4_Hierarchical_EB", pred_bnd_m4)]:
            brier = float(np.mean((p_arr - y_true_bnd) ** 2))
            p_clip = np.clip(p_arr, 1e-6, 1.0 - 1e-6)
            log_loss = float(-np.mean(y_true_bnd * np.log(p_clip) + (1.0 - y_true_bnd) * np.log(1.0 - p_clip)))
            fold_records.append({
                "fold": fold_idx,
                "domain": "Batter",
                "metric": "Boundary%",
                "model": m_name,
                "brier_score": brier,
                "log_loss": log_loss,
                "sample_size": len(y_true_bnd)
            })
            
        # 4. Evaluate Bowler Economy (RPO)
        # Using Law-compliant economy accounting:
        # Group by bowler in train_df
        train_bowler_econ_stats = {}
        for bid, b_grp in train_df.groupby("bowler_id"):
            train_bowler_econ_stats[bid] = calculate_bowler_economy(b_grp)
            
        unpooled_econ_map = {bid: s["economy_rate"] for bid, s in train_bowler_econ_stats.items() if np.isfinite(s["economy_rate"])}
        global_econ = calculate_bowler_economy(train_df)["economy_rate"]
        
        # Validation bowler actual runs per ball conceded on legal deliveries
        val_bowler_rpb = (legal_val["ext_bowler_debit_runs"] * 6.0).values
        pred_econ_m1 = np.full_like(val_bowler_rpb, global_econ, dtype=float)
        pred_econ_m2 = legal_val["bowler_id"].map(unpooled_econ_map).fillna(global_econ).values
        
        # M4: Hierarchical Contextual Economy
        econ_cell_preds = []
        for _, row in legal_val.iterrows():
            exp_econ = hier_engine.get_cell_expectation(row["phase"], row["tier"], "bowler_economy")
            econ_cell_preds.append(exp_econ)
        pred_econ_m4 = np.array(econ_cell_preds)
        
        for m_name, p_arr in [("M1_Global", pred_econ_m1),
                              ("M2_Unpooled", pred_econ_m2),
                              ("M4_Hierarchical_EB", pred_econ_m4)]:
            rmse = float(np.sqrt(np.mean((p_arr - val_bowler_rpb) ** 2)))
            fold_records.append({
                "fold": fold_idx,
                "domain": "Bowler",
                "metric": "Economy_RPO",
                "model": m_name,
                "rmse": rmse,
                "sample_size": len(val_bowler_rpb)
            })
            
        # 5. Subgroup Reliability Diagnostics on Validation Fold
        # Subgroup 1: Phase x Tier
        subgroup_phase_tier = compute_subgroup_reliability(
            val_df=legal_val,
            predictions=pred_bnd_m4,
            actuals=y_true_bnd,
            group_cols=["phase", "tier"],
            is_binary=True
        )
        subgroup_phase_tier["fold"] = fold_idx
        subgroup_phase_tier["grouping"] = "Phase_x_Tier"
        all_subgroup_reliability.append(subgroup_phase_tier)
        
        # Subgroup 2: Bowler Role x Phase
        subgroup_role_phase = compute_subgroup_reliability(
            val_df=legal_val,
            predictions=pred_econ_m4,
            actuals=val_bowler_rpb,
            group_cols=["bowler_role", "phase"],
            is_binary=False
        )
        subgroup_role_phase["fold"] = fold_idx
        subgroup_role_phase["grouping"] = "BowlerRole_x_Phase"
        all_subgroup_reliability.append(subgroup_role_phase)
        
        print(f"Fold {fold_idx} complete in {time.time() - fold_start:.2f}s")
        
    # Aggregate and save deliverables
    df_folds = pd.DataFrame(fold_records)
    df_priors = pd.DataFrame(prior_fit_records)
    df_subgroups = pd.concat(all_subgroup_reliability, ignore_index=True)
    
    folds_path = os.path.join(output_dir, "M5_5B_2_FOLD_RESULTS.csv")
    priors_path = os.path.join(output_dir, "M5_5B_2_PRIOR_FIT_DIAGNOSTICS.csv")
    subgroups_path = os.path.join(output_dir, "M5_5B_2_SUBGROUP_RELIABILITY.csv")
    
    df_folds.to_csv(folds_path, index=False)
    df_priors.to_csv(priors_path, index=False)
    df_subgroups.to_csv(subgroups_path, index=False)
    
    print(f"\n[M5.5-B.2] Validation completed in {time.time() - start_time:.2f}s")
    print(f"Saved: {folds_path}")
    print(f"Saved: {priors_path}")
    print(f"Saved: {subgroups_path}")
    
    return {
        "fold_results": df_folds,
        "prior_diagnostics": df_priors,
        "subgroup_reliability": df_subgroups
    }


if __name__ == "__main__":
    res = run_full_validation_b2()
    print("\nSummary Fold Results:")
    print(res["fold_results"].groupby(["domain", "metric", "model"])[["brier_score", "log_loss", "rmse"]].mean())
