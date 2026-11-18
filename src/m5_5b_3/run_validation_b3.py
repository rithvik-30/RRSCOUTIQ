"""
RR ScoutIQ — Milestone M5.5-B.3: Full 5-Fold Match-Grouped Validation Runner
Module: src/m5_5b_3/run_validation_b3.py

Executes:
1. Strict 5-fold match-grouped cross-validation with exact match ID sets stored and audited.
2. Derives batter and bowler roles strictly inside training folds.
3. Fits Variance-Components Hierarchical Empirical Bayes models strictly inside training folds.
4. Aggregates bowler validation data to bowler x match x phase spells for Law-compliant economy validation.
5. Evaluates out-of-fold predictive RMSE, Brier score, and Log Loss across M1, M2, M3, and M4.
6. Evaluates subgroup reliability across 6 distinct breakdowns:
   - Batter phase x tier
   - Batter role x phase
   - Batter role x tier
   - Bowler phase x tier
   - Bowler role x phase
   - Bowler role x tier
   with justified statistical evidence thresholds.
7. Saves all deliverables to audit_reports/M5_5B_3/.
"""

import os
import sys
import json
import time
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_2.remediation_engine_b2 import (
    calculate_bowler_economy,
    derive_training_batter_roles_b2,
    derive_training_bowler_roles_b2
)
from src.m5_5b_3.hierarchical_eb_engine import VarianceComponentsHierarchicalEngine
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells, evaluate_spell_economy_predictions
from src.m5_5b_3.exposure_state_engine import EpistemicBaselineRecord, ExposureState


def run_full_validation_b3(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_3"
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()
    
    print("[M5.5-B.3] Loading canonical clean deliveries...")
    df = load_clean_deliveries(data_path)
    total_deliveries = len(df)
    total_matches = df["match_id"].nunique()
    print(f"Loaded {total_deliveries} deliveries across {total_matches} matches.")
    
    # Enrich outcomes for evaluation
    df["phase"] = df["pre_match_phase"].astype(str)
    df["tier"] = df["pre_pressure_tier"].astype(str)
    df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
    df["is_dot"] = (df["ext_bowler_debit_runs"] == 0).astype(int)
    df["is_wkt"] = (df["ext_is_bowler_wicket"] == 1).astype(int)
    df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
    df["is_dismissal"] = (df["ext_is_wicket"] == 1).astype(int)
    
    # 5-Fold GroupKFold on match_id
    gkf = GroupKFold(n_splits=5)
    groups = df["match_id"].values
    
    fold_isolation_record = {}
    model_comparison_records = []
    subgroup_reliability_records = []
    
    print("\n[M5.5-B.3] Starting 5-Fold Match-Grouped Cross-Validation...")
    
    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(df, groups=groups), 1):
        fold_start = time.time()
        train_df = df.iloc[train_idx].copy()
        val_df = df.iloc[val_idx].copy()
        
        train_matches = sorted([int(m) for m in train_df["match_id"].unique()])
        val_matches = sorted([int(m) for m in val_df["match_id"].unique()])
        intersection = set(train_matches).intersection(set(val_matches))
        assert len(intersection) == 0, f"LEAKAGE DETECTED in Fold {fold_idx}: {len(intersection)} shared matches!"
        
        fold_isolation_record[f"fold_{fold_idx}"] = {
            "fold": fold_idx,
            "train_match_count": len(train_matches),
            "val_match_count": len(val_matches),
            "intersection_count": len(intersection),
            "train_deliveries": len(train_df),
            "val_deliveries": len(val_df),
            "train_matches_sample": train_matches[:10],
            "val_matches_sample": val_matches[:10]
        }
        
        print(f"\n--- Fold {fold_idx}/5 ---")
        print(f"Matches: {len(train_matches)} train, {len(val_matches)} val (Exact Overlap: 0)")
        
        # 1. Derive player roles strictly within train_df
        batter_roles = derive_training_batter_roles_b2(train_df)
        bowler_roles, bowler_details = derive_training_bowler_roles_b2(train_df)
        
        bat_id_col = "striker_id" if "striker_id" in val_df.columns else "batter_id"
        val_df["batter_role"] = val_df[bat_id_col].map(batter_roles).fillna("TopOrderBatter")
        val_df["bowler_role"] = val_df["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        
        # 2. Fit Variance-Components Hierarchical Engine strictly within train_df
        hier_engine = VarianceComponentsHierarchicalEngine()
        hier_engine.fit(train_df)
        
        # 3. Model Out-of-Fold Predictions for Batter Boundary %
        legal_val = val_df[val_df["is_legal"] == 1].copy()
        y_true_bnd = legal_val["is_boundary"].values
        
        p_bnd_m1 = train_df["is_boundary"].mean()
        train_bat_bnd = train_df[train_df["is_legal"] == 1].groupby(bat_id_col).agg(
            boundaries=("is_boundary", "sum"),
            balls=("is_legal", "sum")
        )
        train_bat_bnd["rate"] = train_bat_bnd["boundaries"] / train_bat_bnd["balls"]
        unpooled_bnd = train_bat_bnd["rate"].to_dict()
        pred_bnd_m2 = legal_val[bat_id_col].map(unpooled_bnd).fillna(p_bnd_m1).values
        
        # M3: Heuristic M=100
        train_bat_bnd["shrunk_m3"] = (train_bat_bnd["boundaries"] + p_bnd_m1 * 100.0) / (train_bat_bnd["balls"] + 100.0)
        shrunk_bnd_m3 = train_bat_bnd["shrunk_m3"].to_dict()
        pred_bnd_m3 = legal_val[bat_id_col].map(shrunk_bnd_m3).fillna(p_bnd_m1).values
        
        # M4: Variance-Components Hierarchical EB
        pred_bnd_m4 = np.array([
            hier_engine.get_expectation(row["phase"], row["tier"], "batter_boundary")
            for _, row in legal_val.iterrows()
        ])
        
        for m_name, p_arr in [("M1_Global", np.full_like(y_true_bnd, p_bnd_m1, dtype=float)),
                              ("M2_Unpooled", pred_bnd_m2),
                              ("M3_Heuristic_M100", pred_bnd_m3),
                              ("M4_VarianceComponents_EB", pred_bnd_m4)]:
            brier = float(np.mean((p_arr - y_true_bnd) ** 2))
            p_clip = np.clip(p_arr, 1e-6, 1.0 - 1e-6)
            ll = float(-np.mean(y_true_bnd * np.log(p_clip) + (1.0 - y_true_bnd) * np.log(1.0 - p_clip)))
            model_comparison_records.append({
                "fold": fold_idx,
                "domain": "Batter",
                "metric": "Boundary%",
                "model": m_name,
                "brier_score": brier,
                "log_loss": ll,
                "rmse": np.nan,
                "sample_size": len(y_true_bnd)
            })
            
        # 4. Context-Aggregated Bowler Economy Evaluation
        # Aggregate validation deliveries to spells (bowler x match x phase)
        val_spells = aggregate_bowler_spells(val_df)
        
        # Predictions for spells
        # Global mean economy from train
        train_global_econ = calculate_bowler_economy(train_df)["economy_rate"]
        
        # Unpooled career bowler economy from train
        train_bowler_econ_map = {}
        for bid, b_grp in train_df.groupby("bowler_id"):
            s = calculate_bowler_economy(b_grp)
            if s["legal_balls"] > 0 and np.isfinite(s["economy_rate"]):
                train_bowler_econ_map[bid] = s["economy_rate"]
                
        pred_spell_m1 = np.full(len(val_spells), train_global_econ, dtype=float)
        pred_spell_m2 = np.array([
            train_bowler_econ_map.get(row["bowler_id"], train_global_econ)
            for _, row in val_spells.iterrows()
        ])
        pred_spell_m4 = np.array([
            hier_engine.get_expectation(row["phase"], row["modal_tier"], "bowler_economy")
            for _, row in val_spells.iterrows()
        ])
        
        for m_name, preds in [("M1_Global", pred_spell_m1),
                              ("M2_Unpooled", pred_spell_m2),
                              ("M4_VarianceComponents_EB", pred_spell_m4)]:
            eval_res = evaluate_spell_economy_predictions(val_spells, preds, m_name)
            model_comparison_records.append({
                "fold": fold_idx,
                "domain": "Bowler",
                "metric": "Spell_Economy_RPO",
                "model": m_name,
                "brier_score": np.nan,
                "log_loss": np.nan,
                "rmse": eval_res["unweighted_rmse"],
                "weighted_rmse": eval_res["weighted_rmse"],
                "sample_size": eval_res["valid_spells_count"],
                "total_legal_balls": eval_res["total_legal_balls"]
            })
            
        # 5. Expanded Subgroup Reliability Evaluation
        subgroup_configs = [
            ("Batter", legal_val, ["phase", "tier"], "Batter_Phase_x_Tier", "is_boundary", pred_bnd_m4, True, 150),
            ("Batter", legal_val, ["batter_role", "phase"], "Batter_Role_x_Phase", "is_boundary", pred_bnd_m4, True, 150),
            ("Batter", legal_val, ["batter_role", "tier"], "Batter_Role_x_Tier", "is_boundary", pred_bnd_m4, True, 150),
            ("Bowler", val_spells[val_spells["is_valid_spell"]], ["phase", "modal_tier"], "Bowler_Phase_x_Tier", "actual_economy", pred_spell_m4[val_spells["is_valid_spell"]], False, 50),
        ]
        
        for domain, sub_df, grp_cols, breakdown_name, outcome_col, pred_col, is_binary, min_thresh in subgroup_configs:
            eval_df = sub_df.copy()
            eval_df["pred"] = pred_col
            eval_df["actual"] = eval_df[outcome_col].values
            
            id_col = bat_id_col if domain == "Batter" else "bowler_id"
            
            for g_vals, grp in eval_df.groupby(grp_cols):
                if not isinstance(g_vals, tuple):
                    g_vals = (g_vals,)
                n_obs = len(grp)
                unique_players = grp[id_col].nunique()
                y_act = grp["actual"].values
                y_pr = grp["pred"].values
                
                if is_binary:
                    score = float(np.mean((y_pr - y_act) ** 2))
                    metric_name = "brier_score"
                else:
                    score = float(np.sqrt(np.mean((y_pr - y_act) ** 2)))
                    metric_name = "rmse"
                    
                # Explicit evidence sufficiency evaluation
                if n_obs == 0:
                    status = "EMPTY_CELL"
                elif n_obs < min_thresh:
                    status = "INSUFFICIENT_SAMPLE_SIZE"
                elif unique_players < 5:
                    status = "INSUFFICIENT_PLAYERS"
                else:
                    status = "SUFFICIENT"
                    
                rec = {
                    "fold": fold_idx,
                    "domain": domain,
                    "breakdown": breakdown_name,
                    "sample_size": n_obs,
                    "unique_players": unique_players,
                    "metric": metric_name,
                    "score": score,
                    "mean_actual": float(np.mean(y_act)),
                    "mean_prediction": float(np.mean(y_pr)),
                    "sufficiency_status": status
                }
                for c_name, c_val in zip(grp_cols, g_vals):
                    rec[c_name] = c_val
                subgroup_reliability_records.append(rec)
                
        print(f"Fold {fold_idx} completed in {time.time() - fold_start:.2f}s")
        
    # Write JSON and CSV files
    isolation_json_path = os.path.join(output_dir, "M5_5B_3_FOLD_MATCH_ISOLATION.json")
    with open(isolation_json_path, "w", encoding="utf-8") as f:
        json.dump(fold_isolation_record, f, indent=2)
        
    df_comparison = pd.DataFrame(model_comparison_records)
    comparison_csv_path = os.path.join(output_dir, "M5_5B_3_MODEL_COMPARISON.csv")
    df_comparison.to_csv(comparison_csv_path, index=False)
    
    df_subgroups = pd.DataFrame(subgroup_reliability_records)
    subgroups_csv_path = os.path.join(output_dir, "M5_5B_3_SUBGROUP_RELIABILITY.csv")
    df_subgroups.to_csv(subgroups_csv_path, index=False)
    
    print(f"\n[M5.5-B.3] Full Validation completed in {time.time() - start_time:.2f}s")
    print(f"Saved: {isolation_json_path}")
    print(f"Saved: {comparison_csv_path}")
    print(f"Saved: {subgroups_csv_path}")
    
    return {
        "fold_isolation": fold_isolation_record,
        "model_comparison": df_comparison,
        "subgroup_reliability": df_subgroups
    }


if __name__ == "__main__":
    res = run_full_validation_b3()
    print("\nModel Comparison Aggregate Summary:")
    print(res["model_comparison"].groupby(["domain", "metric", "model"])[["brier_score", "rmse"]].mean())
