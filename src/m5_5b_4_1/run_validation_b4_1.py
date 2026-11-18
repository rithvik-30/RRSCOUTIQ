"""
RR ScoutIQ — Milestone M5.5-B.4.1: Cross-Validation Runner & Invariant Validation
Module: src/m5_5b_4_1/run_validation_b4_1.py

Executes:
1. Strict 5-Fold Match-Grouped CV (GroupKFold on match_id).
2. Persists COMPLETE sorted match ID arrays for every training and validation fold.
3. Asserts exact pairwise zero overlap across all 5 folds.
4. Fits ContextualHierarchyB41 strictly on training data (without artificial positive floors, with RPO units).
5. Aggregates validation deliveries into bowler x match x phase spells.
6. Evaluates bowler economy predictions using exact delivery-composition weighting:
   predicted_spell_econ = 6.0 * (sum_{d in legal_delivs} exp_runs_d) / legal_balls_spell.
   Numerators and denominators are strictly aligned over legal deliveries.
7. Evaluates genuine player-specific posteriors (M5_Player_Posterior_EB_B41) alongside M1-M4 baselines.
8. Evaluates all 6 structural subgroup breakdowns with cluster-adjusted standard error bounds.
9. Persists all outputs to audit_reports/M5_5B_4_1/.
"""

import os
import sys
import json
import time
import math
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
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells
from src.m5_5b_4_1.hierarchical_engine_b4_1 import (
    ContextualHierarchyB41,
    PlayerPosteriorBaselineEstimatorB41
)


def compute_cluster_se(residuals: np.ndarray, clusters: np.ndarray) -> float:
    """
    Computes match-clustered standard error of the mean for residuals or target series:
    SE_cluster = sqrt( sum_{c in clusters} (sum_{i in c} e_i)^2 ) / N
    """
    n = len(residuals)
    if n <= 1:
        return np.nan
    df_res = pd.DataFrame({"e": residuals, "c": clusters})
    cluster_sums = df_res.groupby("c")["e"].sum().values
    var_sum = np.sum(cluster_sums ** 2)
    return float(np.sqrt(var_sum) / n)


def run_full_validation_b4_1(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_4_1"
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()
    
    print("[M5.5-B.4.1] Loading clean canonical deliveries...")
    df = load_clean_deliveries(data_path)
    total_deliveries = len(df)
    total_matches = df["match_id"].nunique()
    print(f"Loaded {total_deliveries} deliveries across {total_matches} matches.")
    
    # Enrich outcomes for evaluation
    df["phase"] = df["pre_match_phase"].astype(str)
    df["tier"] = df["pre_pressure_tier"].astype(str)
    df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
    df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
    bat_id_col = "striker_id" if "striker_id" in df.columns else "batter_id"
    
    # Initialize GroupKFold
    gkf = GroupKFold(n_splits=5)
    groups = df["match_id"].values
    
    fold_isolation_records = {}
    model_comparison_records = []
    subgroup_records = []
    
    print("\n[M5.5-B.4.1] Executing 5-Fold Match-Grouped Cross-Validation...")
    
    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(df, groups=groups), 1):
        fold_start = time.time()
        train_df = df.iloc[train_idx].copy()
        val_df = df.iloc[val_idx].copy()
        
        # Complete match ID sets
        train_matches = sorted([int(m) for m in train_df["match_id"].unique()])
        val_matches = sorted([int(m) for m in val_df["match_id"].unique()])
        intersection = set(train_matches).intersection(set(val_matches))
        assert len(intersection) == 0, f"LEAKAGE DETECTED in Fold {fold_idx}: {len(intersection)} shared matches!"
        
        # Persist complete sets for independent verification
        fold_isolation_records[f"fold_{fold_idx}"] = {
            "fold": fold_idx,
            "train_match_count": len(train_matches),
            "val_match_count": len(val_matches),
            "intersection_count": len(intersection),
            "train_matches_complete": train_matches,
            "val_matches_complete": val_matches,
            "train_deliveries": len(train_df),
            "val_deliveries": len(val_df)
        }
        
        print(f"\n--- Fold {fold_idx}/5 ---")
        print(f"Matches: {len(train_matches)} train, {len(val_matches)} val (Exact Overlap: 0)")
        
        # 1. Derive player roles strictly from training data
        batter_roles = derive_training_batter_roles_b2(train_df)
        bowler_roles, bowler_details = derive_training_bowler_roles_b2(train_df)
        
        val_df["batter_role"] = val_df[bat_id_col].map(batter_roles).fillna("TopOrderBatter")
        val_df["bowler_role"] = val_df["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        
        # 2. Fit Contextual Hierarchy B.4.1 strictly from training data
        context_hier = ContextualHierarchyB41()
        context_hier.fit(train_df)
        estimator = PlayerPosteriorBaselineEstimatorB41(context_hier, M0_default=100.0)
        
        # 3. Evaluate Batter Boundary % Out-of-Fold
        legal_val = val_df[val_df["is_legal"] == 1].copy()
        y_true_bnd = legal_val["is_boundary"].values
        
        # M1: Global training mean
        p_bnd_m1 = train_df[train_df["is_legal"] == 1]["is_boundary"].mean()
        pred_bnd_m1 = np.full_like(y_true_bnd, p_bnd_m1, dtype=float)
        
        # M2: Unpooled training player rates
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
        
        # M4: Contextual Hierarchy B.4.1
        pred_bnd_m4 = np.array([
            context_hier.get_context_expectation(row["phase"], row["tier"], "batter_boundary")
            for _, row in legal_val.iterrows()
        ])
        
        # M5: Genuine Player-Specific EB Posterior Baseline
        # Shrinks each player's career boundary experience toward the specific cell prior
        bat_train_balls = train_bat_bnd["balls"].to_dict()
        bat_train_bounds = train_bat_bnd["boundaries"].to_dict()
        
        pred_bnd_m5 = []
        for _, row in legal_val.iterrows():
            pid = row[bat_id_col]
            n_b = bat_train_balls.get(pid, 0)
            k_b = bat_train_bounds.get(pid, 0.0)
            post_rec = estimator.estimate_batter_boundary_posterior(
                player_id=pid,
                phase=row["phase"],
                tier=row["tier"],
                player_balls=n_b,
                player_boundaries=k_b if n_b > 0 else None,
                min_screening_balls=30
            )
            pred_bnd_m5.append(post_rec.shrunk_baseline)
        pred_bnd_m5 = np.array(pred_bnd_m5)
        
        # Batter model comparison evaluation
        batter_models = [
            ("M1_Global", pred_bnd_m1),
            ("M2_Unpooled", pred_bnd_m2),
            ("M3_Heuristic_M100", pred_bnd_m3),
            ("M4_Contextual_B41", pred_bnd_m4),
            ("M5_Player_Posterior_EB_B41", pred_bnd_m5)
        ]
        
        for m_name, p_arr in batter_models:
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
                "weighted_rmse": np.nan,
                "sample_size": len(y_true_bnd)
            })
            
        # 4. Evaluate Spell Bowler Economy with Strict Legal-Ball Delivery Accounting
        val_spells = aggregate_bowler_spells(val_df)
        valid_spells_mask = val_spells["is_valid_spell"] & np.isfinite(val_spells["actual_economy"])
        valid_spells = val_spells[valid_spells_mask].copy()
        
        y_true_econ = valid_spells["actual_economy"].values
        spell_weights = valid_spells["legal_balls"].values / valid_spells["legal_balls"].sum()
        
        # M1: Global mean economy from train (in RPO)
        train_global_econ = calculate_bowler_economy(train_df)["economy_rate"]
        pred_spell_m1 = np.full(len(valid_spells), train_global_econ, dtype=float)
        
        # M2: Unpooled career economy (in RPO)
        train_bowler_econ_map = {}
        train_bowler_balls_map = {}
        train_bowler_runs_map = {}
        for bid, b_grp in train_df.groupby("bowler_id"):
            s = calculate_bowler_economy(b_grp)
            if s["legal_balls"] > 0 and np.isfinite(s["economy_rate"]):
                train_bowler_econ_map[bid] = s["economy_rate"]
                train_bowler_balls_map[bid] = s["legal_balls"]
                train_bowler_runs_map[bid] = s["bowler_debit_runs"]
                
        pred_spell_m2 = np.array([
            train_bowler_econ_map.get(row["bowler_id"], train_global_econ)
            for _, row in valid_spells.iterrows()
        ])
        
        # M3: Heuristic M=100 shrinkage for bowlers (in RPO)
        # shrunk_rpb = (runs + (train_global_econ / 6.0) * 100) / (balls + 100)
        # shrunk_rpo = shrunk_rpb * 6.0
        pred_spell_m3 = []
        global_rpb = train_global_econ / 6.0
        for _, row in valid_spells.iterrows():
            bid = row["bowler_id"]
            b_balls = train_bowler_balls_map.get(bid, 0)
            b_runs = train_bowler_runs_map.get(bid, 0.0)
            shrunk_rpo = 6.0 * (b_runs + global_rpb * 100.0) / (b_balls + 100.0)
            pred_spell_m3.append(shrunk_rpo)
        pred_spell_m3 = np.array(pred_spell_m3)
        
        # M4: Composition-Weighted Predicted Economy
        # STRICT CORRECTION 5: Sum expected delivery runs strictly across LEGAL deliveries in spell
        pred_spell_m4 = []
        pred_spell_m5 = []
        
        for _, sp_row in valid_spells.iterrows():
            bid = sp_row["bowler_id"]
            mid = sp_row["match_id"]
            ph = sp_row["phase"]
            modal_t = sp_row["modal_tier"]
            
            # Extract deliveries for this exact spell
            sp_delivs = val_df[(val_df["bowler_id"] == bid) & (val_df["match_id"] == mid) & (val_df["pre_match_phase"] == ph)]
            legal_sp_delivs = sp_delivs[sp_delivs["ext_is_legal_delivery"] == 1]
            legal_sp_count = len(legal_sp_delivs)
            
            # M4: Sum delivery-by-delivery expected runs strictly on legal deliveries
            if legal_sp_count > 0:
                exp_runs_sum = sum(
                    context_hier.get_expected_runs_per_legal_ball(row["phase"], row["tier"])
                    for _, row in legal_sp_delivs.iterrows()
                )
                pred_econ_comp = (exp_runs_sum / legal_sp_count) * 6.0
            else:
                pred_econ_comp = train_global_econ
            pred_spell_m4.append(pred_econ_comp)
            
            # M5: Genuine Player-Specific EB Posterior Baseline in RPO
            b_legal_train = train_bowler_balls_map.get(bid, 0)
            b_runs_train = train_bowler_runs_map.get(bid, 0.0)
            post_econ_rec = estimator.estimate_bowler_economy_posterior(
                player_id=bid,
                phase=ph,
                tier=modal_t,
                player_legal_balls=b_legal_train,
                player_debit_runs=b_runs_train if b_legal_train > 0 else None,
                min_screening_balls=30
            )
            pred_spell_m5.append(post_econ_rec.shrunk_baseline)
            
        pred_spell_m4 = np.array(pred_spell_m4)
        pred_spell_m5 = np.array(pred_spell_m5)
        
        bowler_models = [
            ("M1_Global", pred_spell_m1),
            ("M2_Unpooled", pred_spell_m2),
            ("M3_Heuristic_M100", pred_spell_m3),
            ("M4_Contextual_Composition_B41", pred_spell_m4),
            ("M5_Player_Posterior_EB_B41", pred_spell_m5)
        ]
        
        for m_name, p_econ in bowler_models:
            unweighted_rmse = float(np.sqrt(np.mean((p_econ - y_true_econ) ** 2)))
            weighted_rmse = float(np.sqrt(np.sum(spell_weights * ((p_econ - y_true_econ) ** 2))))
            model_comparison_records.append({
                "fold": fold_idx,
                "domain": "Bowler",
                "metric": "Spell_Economy_RPO",
                "model": m_name,
                "brier_score": np.nan,
                "log_loss": np.nan,
                "rmse": unweighted_rmse,
                "weighted_rmse": weighted_rmse,
                "sample_size": len(valid_spells)
            })
            
        # 5. Complete Subgroup Reliability Across ALL 6 Breakdowns
        valid_spells["bowler_role"] = valid_spells["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        valid_spells["pred_m4"] = pred_spell_m4
        
        subgroup_configs = [
            ("Batter", legal_val, ["phase", "tier"], "1_Batter_Phase_x_Tier", "is_boundary", pred_bnd_m4, True, 150),
            ("Batter", legal_val, ["batter_role", "phase"], "2_Batter_Role_x_Phase", "is_boundary", pred_bnd_m4, True, 150),
            ("Batter", legal_val, ["batter_role", "tier"], "3_Batter_Role_x_Tier", "is_boundary", pred_bnd_m4, True, 150),
            ("Bowler", valid_spells, ["phase", "modal_tier"], "4_Bowler_Phase_x_Tier", "actual_economy", valid_spells["pred_m4"].values, False, 50),
            ("Bowler", valid_spells, ["bowler_role", "phase"], "5_Bowler_Role_x_Phase", "actual_economy", valid_spells["pred_m4"].values, False, 50),
            ("Bowler", valid_spells, ["bowler_role", "modal_tier"], "6_Bowler_Role_x_Tier", "actual_economy", valid_spells["pred_m4"].values, False, 50),
        ]
        
        for domain, s_df, grp_cols, b_name, target_col, p_vals, is_binary, min_req in subgroup_configs:
            eval_data = s_df.copy()
            eval_data["pred"] = p_vals
            eval_data["actual"] = eval_data[target_col].values
            id_col = bat_id_col if domain == "Batter" else "bowler_id"
            
            for g_vals, grp in eval_data.groupby(grp_cols):
                if not isinstance(g_vals, tuple):
                    g_vals = (g_vals,)
                n_obs = len(grp)
                n_players = grp[id_col].nunique()
                n_matches = grp["match_id"].nunique()
                y_act = grp["actual"].values
                y_pr = grp["pred"].values
                clusters = grp["match_id"].values
                
                residuals = y_act - y_pr
                
                if is_binary:
                    score = float(np.mean((y_pr - y_act) ** 2))
                    metric_name = "brier_score"
                    se_cluster = compute_cluster_se(y_act - np.mean(y_act), clusters)
                else:
                    score = float(np.sqrt(np.mean((y_pr - y_act) ** 2)))
                    metric_name = "rmse"
                    se_cluster = compute_cluster_se(y_act - np.mean(y_act), clusters)
                    
                # Explicit Grounded Sufficiency Evaluation
                if n_obs == 0:
                    status = "EMPTY_CELL"
                elif n_obs < min_req:
                    status = "INSUFFICIENT_SAMPLE_SIZE"
                elif n_players < 5:
                    status = "INSUFFICIENT_PLAYER_DIVERSITY"
                elif np.isfinite(se_cluster) and se_cluster > (0.10 if is_binary else 1.5):
                    status = "HIGH_ESTIMATION_UNCERTAINTY"
                else:
                    status = "SUFFICIENT"
                    
                rec = {
                    "fold": fold_idx,
                    "domain": domain,
                    "breakdown": b_name,
                    "sample_size": n_obs,
                    "unique_players": n_players,
                    "unique_matches": n_matches,
                    "target_metric": metric_name,
                    "score": score,
                    "mean_actual": float(np.mean(y_act)),
                    "mean_prediction": float(np.mean(y_pr)),
                    "standard_error": se_cluster,
                    "sufficiency_status": status
                }
                for c_name, c_val in zip(grp_cols, g_vals):
                    rec[c_name] = c_val
                subgroup_records.append(rec)
                
        print(f"Fold {fold_idx} completed in {time.time() - fold_start:.2f}s")
        
    # Persist isolation JSON, comparison CSV, and subgroup CSV
    isolation_path = os.path.join(output_dir, "M5_5B_4_1_FOLD_MATCH_ISOLATION.json")
    with open(isolation_path, "w", encoding="utf-8") as f:
        json.dump(fold_isolation_records, f, indent=2)
        
    df_comparison = pd.DataFrame(model_comparison_records)
    comparison_csv_path = os.path.join(output_dir, "M5_5B_4_1_MODEL_COMPARISON.csv")
    df_comparison.to_csv(comparison_csv_path, index=False)
    
    df_subgroups = pd.DataFrame(subgroup_records)
    subgroups_csv_path = os.path.join(output_dir, "M5_5B_4_1_SUBGROUP_RELIABILITY.csv")
    df_subgroups.to_csv(subgroups_csv_path, index=False)
    
    print(f"\n[M5.5-B.4.1] Validation completed in {time.time() - start_time:.2f}s")
    print(f"Saved: {isolation_path}")
    print(f"Saved: {comparison_csv_path}")
    print(f"Saved: {subgroups_csv_path}")
    
    return {
        "fold_isolation": fold_isolation_records,
        "model_comparison": df_comparison,
        "subgroups": df_subgroups
    }


if __name__ == "__main__":
    res = run_full_validation_b4_1()
    print("\nModel Comparison Aggregate Summary:")
    print(res["model_comparison"].groupby(["domain", "metric", "model"])[["brier_score", "rmse", "weighted_rmse"]].mean())
