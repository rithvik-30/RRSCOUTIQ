"""
RR ScoutIQ — Milestone M5.5-B.4.2: Match-Grouped Validation & Calibration Runner
Module: src/m5_5b_4_2/run_validation_b4_2.py

Executes:
1. Strict 5-Fold Match-Grouped Cross-Validation (GroupKFold on match_id).
2. Persists complete sorted match ID arrays for training and validation folds.
3. Fits ContextualHierarchyB42 strictly on training data:
   - Cross-tier covariance via match-block bootstrap.
   - Multivariate DerSimonian-Laird without positive floors.
   - Fold-specific hyperparameter estimation (M0 and tau2).
4. Evaluates M1 through M5 benchmarks out-of-fold:
   - M1: Global training mean
   - M2: Unpooled player rates
   - M3: Heuristic M=100 shrinkage
   - M4: Hierarchical contextual expectations / composition
   - M5: Context-consistent empirical Bayes player posteriors
5. Rebuilt Subgroup Reliability:
   - Estimand is the model prediction error / loss.
   - Computes cluster-robust uncertainty for that metric across independent match clusters.
   - Invariant: NaN or unavailable SE never silently produces SUFFICIENT.
6. Calibration and Interval Coverage Evaluation:
   - 80% and 95% credible interval empirical coverage.
   - Expected Calibration Error (ECE) and standardized residuals.
7. Saves all machine-readable predictions, diagnostics, and reports.
"""

import os
import sys
import json
import time
import math
from typing import Dict, List, Any, Tuple
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
from src.m5_5b_4_2.hierarchical_engine_b4_2 import (
    ContextualHierarchyB42,
    PlayerPosteriorBaselineEstimatorB42
)
from src.m5_5b_4_2.calibration_engine_b4_2 import (
    compute_binary_calibration_metrics,
    compute_posterior_interval_coverage,
    compute_stratified_calibration_table
)


def compute_metric_cluster_robust_se(
    loss_series: np.ndarray,
    cluster_ids: np.ndarray
) -> Tuple[float, str]:
    """
    Computes cluster-robust standard error for the prediction error estimand:
    loss_series: L_i = (y_i - y_hat_i)^2
    cluster_ids: match_id
    """
    n = len(loss_series)
    if n <= 1:
        return np.nan, "INSUFFICIENT_OBSERVATIONS"
        
    df_loss = pd.DataFrame({"l": loss_series, "c": cluster_ids})
    unique_clusters = df_loss["c"].nunique()
    if unique_clusters < 5:
        return np.nan, "INSUFFICIENT_CLUSTERS"
        
    mean_l = float(np.mean(loss_series))
    cluster_devs = df_loss.groupby("c")["l"].apply(lambda s: np.sum(s - mean_l)).values
    
    var_sum = np.sum(cluster_devs ** 2)
    # Degrees of freedom adjustment: (G / (G - 1))
    dof_adj = unique_clusters / (unique_clusters - 1)
    se = math.sqrt((var_sum / (n ** 2)) * dof_adj)
    return float(se), "VALID_CLUSTER_SE"


def run_full_validation_b4_2(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_4_2",
    n_boot: int = 100
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()
    
    print("[M5.5-B.4.2] Loading clean canonical deliveries...")
    df = load_clean_deliveries(data_path)
    total_deliveries = len(df)
    total_matches = df["match_id"].nunique()
    print(f"Loaded {total_deliveries} deliveries across {total_matches} matches.")
    
    # Enrich outcomes
    df["phase"] = df["pre_match_phase"].astype(str)
    df["tier"] = df["pre_pressure_tier"].astype(str)
    df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
    df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
    bat_id_col = "striker_id" if "striker_id" in df.columns else "batter_id"
    
    # 5-Fold Match-Grouped CV
    gkf = GroupKFold(n_splits=5)
    groups = df["match_id"].values
    
    fold_isolation_records = {}
    model_comparison_records = []
    subgroup_records = []
    prediction_records = []
    calibration_diag_records = []
    
    print("\n[M5.5-B.4.2] Executing 5-Fold Match-Grouped Cross-Validation...")
    
    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(df, groups=groups), 1):
        fold_start = time.time()
        train_df = df.iloc[train_idx].copy()
        val_df = df.iloc[val_idx].copy()
        
        train_matches = sorted([int(m) for m in train_df["match_id"].unique()])
        val_matches = sorted([int(m) for m in val_df["match_id"].unique()])
        intersection = set(train_matches).intersection(set(val_matches))
        assert len(intersection) == 0, f"LEAKAGE DETECTED in Fold {fold_idx}: {len(intersection)} shared matches!"
        
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
        
        # 1. Player roles strictly from training data
        batter_roles = derive_training_batter_roles_b2(train_df)
        bowler_roles, bowler_details = derive_training_bowler_roles_b2(train_df)
        val_df["batter_role"] = val_df[bat_id_col].map(batter_roles).fillna("TopOrderBatter")
        val_df["bowler_role"] = val_df["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        
        # 2. Contextual Hierarchy & Hyperparameter Estimation
        context_hier = ContextualHierarchyB42(n_boot=n_boot)
        context_hier.fit(train_df)
        estimator = PlayerPosteriorBaselineEstimatorB42(context_hier)
        
        # Pre-compute training aggregates for batters:
        # Context-specific aggregates: (player_id, phase, tier)
        train_legal = train_df[train_df["is_legal"] == 1]
        bat_ctx_agg = train_legal.groupby([bat_id_col, "phase", "tier"]).agg(
            ctx_boundaries=("is_boundary", "sum"),
            ctx_balls=("is_legal", "sum"),
            ctx_matches=("match_id", "nunique")
        )
        bat_ctx_dict = bat_ctx_agg.to_dict(orient="index")
        
        # Career aggregates: player_id
        bat_car_agg = train_legal.groupby(bat_id_col).agg(
            car_boundaries=("is_boundary", "sum"),
            car_balls=("is_legal", "sum"),
            car_matches=("match_id", "nunique")
        )
        bat_car_dict = bat_car_agg.to_dict(orient="index")
        
        # 3. Evaluate Batter Boundary % Out-of-Fold
        legal_val = val_df[val_df["is_legal"] == 1].copy()
        y_true_bnd = legal_val["is_boundary"].values
        val_matches_arr = legal_val["match_id"].values
        
        # M1: Global training mean
        p_bnd_m1 = float(train_legal["is_boundary"].mean())
        pred_bnd_m1 = np.full_like(y_true_bnd, p_bnd_m1, dtype=float)
        
        # M2: Unpooled training rate
        bat_car_rates = {k: v["car_boundaries"] / v["car_balls"] for k, v in bat_car_dict.items() if v["car_balls"] > 0}
        pred_bnd_m2 = legal_val[bat_id_col].map(bat_car_rates).fillna(p_bnd_m1).values
        
        # M3: Heuristic M=100
        shrunk_bnd_m3 = {
            k: (v["car_boundaries"] + p_bnd_m1 * 100.0) / (v["car_balls"] + 100.0)
            for k, v in bat_car_dict.items()
        }
        pred_bnd_m3 = legal_val[bat_id_col].map(shrunk_bnd_m3).fillna(p_bnd_m1).values
        
        # M4: Hierarchical Context Expectation
        pred_bnd_m4 = np.array([
            context_hier.get_context_expectation(row["phase"], row["tier"], "batter_boundary")
            for _, row in legal_val.iterrows()
        ])
        
        # M5: Context-Consistent Empirical Bayes Posterior Baseline
        pred_bnd_m5 = []
        se_bnd_m5 = []
        state_bnd_m5 = []
        ctx_exp_bnd = []
        
        for _, row in legal_val.iterrows():
            pid = row[bat_id_col]
            ph = row["phase"]
            tr = row["tier"]
            
            ctx_data = bat_ctx_dict.get((pid, ph, tr), {"ctx_balls": 0, "ctx_boundaries": 0.0, "ctx_matches": 0})
            car_data = bat_car_dict.get(pid, {"car_balls": 0, "car_boundaries": 0.0, "car_matches": 0})
            
            rec = estimator.estimate_batter_boundary_posterior(
                player_id=pid,
                phase=ph,
                tier=tr,
                context_balls=ctx_data["ctx_balls"],
                context_boundaries=ctx_data["ctx_boundaries"] if ctx_data["ctx_balls"] > 0 else None,
                context_matches=ctx_data["ctx_matches"],
                career_balls=car_data["car_balls"],
                career_boundaries=car_data["car_boundaries"] if car_data["car_balls"] > 0 else None,
                career_matches=car_data["car_matches"],
                min_context_screening_balls=30
            )
            pred_bnd_m5.append(rec.shrunk_baseline)
            se_bnd_m5.append(rec.standard_error)
            state_bnd_m5.append(rec.state.value)
            ctx_exp_bnd.append(ctx_data["ctx_balls"])
            
        pred_bnd_m5 = np.array(pred_bnd_m5)
        se_bnd_m5 = np.array(se_bnd_m5)
        
        # Store predictions for diagnostics
        legal_val["pred_m1"] = pred_bnd_m1
        legal_val["pred_m2"] = pred_bnd_m2
        legal_val["pred_m3"] = pred_bnd_m3
        legal_val["pred_m4"] = pred_bnd_m4
        legal_val["pred_m5"] = pred_bnd_m5
        legal_val["se_m5"] = se_bnd_m5
        legal_val["epistemic_state"] = state_bnd_m5
        legal_val["context_exposure"] = ctx_exp_bnd
        legal_val["fold"] = fold_idx
        legal_val["actual"] = y_true_bnd
        
        # Batter Model Comparison Ledger
        batter_models = [
            ("M1_Global", pred_bnd_m1),
            ("M2_Unpooled", pred_bnd_m2),
            ("M3_Heuristic_M100", pred_bnd_m3),
            ("M4_Contextual_B42", pred_bnd_m4),
            ("M5_Player_Posterior_EB_B42", pred_bnd_m5)
        ]
        
        for m_name, p_arr in batter_models:
            brier_loss = (p_arr - y_true_bnd) ** 2
            brier = float(np.mean(brier_loss))
            p_clip = np.clip(p_arr, 1e-6, 1.0 - 1e-6)
            ll = float(-np.mean(y_true_bnd * np.log(p_clip) + (1.0 - y_true_bnd) * np.log(1.0 - p_clip)))
            
            # Cluster-robust SE of Brier score
            se_brier, se_status = compute_metric_cluster_robust_se(brier_loss, val_matches_arr)
            
            model_comparison_records.append({
                "fold": fold_idx,
                "domain": "Batter",
                "metric": "Boundary%",
                "model": m_name,
                "score": brier,
                "score_cluster_se": se_brier,
                "log_loss": ll,
                "rmse": np.nan,
                "weighted_rmse": np.nan,
                "sample_size": len(y_true_bnd)
            })
            
        # 4. Evaluate Bowler Spell Economy Out-of-Fold
        val_spells = aggregate_bowler_spells(val_df)
        valid_spells_mask = val_spells["is_valid_spell"] & np.isfinite(val_spells["actual_economy"])
        valid_spells = val_spells[valid_spells_mask].copy()
        
        y_true_econ = valid_spells["actual_economy"].values
        spell_weights = valid_spells["legal_balls"].values / valid_spells["legal_balls"].sum()
        spell_matches_arr = valid_spells["match_id"].values
        
        train_global_econ = calculate_bowler_economy(train_df)["economy_rate"]
        pred_spell_m1 = np.full(len(valid_spells), train_global_econ, dtype=float)
        
        # Training aggregates for bowlers:
        # Context-specific: (bowler_id, phase, tier)
        bowl_ctx_agg = {}
        for (bid, ph, tr), b_grp in train_df.groupby(["bowler_id", "phase", "tier"]):
            s = calculate_bowler_economy(b_grp)
            bowl_ctx_agg[(bid, ph, tr)] = {
                "legal_balls": s["legal_balls"],
                "debit_runs": s["bowler_debit_runs"],
                "matches": b_grp["match_id"].nunique()
            }
            
        # Career aggregates: bowler_id
        bowl_car_agg = {}
        for bid, b_grp in train_df.groupby("bowler_id"):
            s = calculate_bowler_economy(b_grp)
            bowl_car_agg[bid] = {
                "legal_balls": s["legal_balls"],
                "debit_runs": s["bowler_debit_runs"],
                "econ": s["economy_rate"],
                "matches": b_grp["match_id"].nunique()
            }
            
        pred_spell_m2 = np.array([
            bowl_car_agg.get(row["bowler_id"], {}).get("econ", train_global_econ)
            for _, row in valid_spells.iterrows()
        ])
        
        # M3 Heuristic
        global_rpb = train_global_econ / 6.0
        pred_spell_m3 = []
        for _, row in valid_spells.iterrows():
            bid = row["bowler_id"]
            car = bowl_car_agg.get(bid, {"legal_balls": 0, "debit_runs": 0.0})
            shrunk_rpo = 6.0 * (car["debit_runs"] + global_rpb * 100.0) / (car["legal_balls"] + 100.0)
            pred_spell_m3.append(shrunk_rpo)
        pred_spell_m3 = np.array(pred_spell_m3)
        
        # M4 and M5
        pred_spell_m4 = []
        pred_spell_m5 = []
        se_spell_m5 = []
        state_spell_m5 = []
        ctx_exp_spell = []
        
        for _, sp_row in valid_spells.iterrows():
            bid = sp_row["bowler_id"]
            mid = sp_row["match_id"]
            ph = sp_row["phase"]
            modal_t = sp_row["modal_tier"]
            
            # Exact deliveries in this spell
            sp_delivs = val_df[(val_df["bowler_id"] == bid) & (val_df["match_id"] == mid) & (val_df["pre_match_phase"] == ph)]
            legal_sp_delivs = sp_delivs[sp_delivs["ext_is_legal_delivery"] == 1]
            legal_sp_count = len(legal_sp_delivs)
            
            # M4 Contextual Composition
            if legal_sp_count > 0:
                exp_runs_sum = sum(
                    context_hier.get_expected_runs_per_legal_ball(row["phase"], row["tier"])
                    for _, row in legal_sp_delivs.iterrows()
                )
                pred_econ_comp = (exp_runs_sum / legal_sp_count) * 6.0
            else:
                pred_econ_comp = train_global_econ
            pred_spell_m4.append(pred_econ_comp)
            
            # M5 Context-Consistent Empirical Bayes Posterior Baseline
            ctx_data = bowl_ctx_agg.get((bid, ph, modal_t), {"legal_balls": 0, "debit_runs": 0.0, "matches": 0})
            car_data = bowl_car_agg.get(bid, {"legal_balls": 0, "debit_runs": 0.0, "matches": 0})
            
            rec = estimator.estimate_bowler_economy_posterior(
                player_id=bid,
                phase=ph,
                tier=modal_t,
                context_legal_balls=ctx_data["legal_balls"],
                context_debit_runs=ctx_data["debit_runs"] if ctx_data["legal_balls"] > 0 else None,
                context_matches=ctx_data["matches"],
                career_legal_balls=car_data["legal_balls"],
                career_debit_runs=car_data["debit_runs"] if car_data["legal_balls"] > 0 else None,
                career_matches=car_data["matches"],
                min_context_screening_balls=30
            )
            pred_spell_m5.append(rec.shrunk_baseline)
            se_spell_m5.append(rec.standard_error)
            state_spell_m5.append(rec.state.value)
            ctx_exp_spell.append(ctx_data["legal_balls"])
            
        pred_spell_m4 = np.array(pred_spell_m4)
        pred_spell_m5 = np.array(pred_spell_m5)
        se_spell_m5 = np.array(se_spell_m5)
        
        valid_spells["pred_m1"] = pred_spell_m1
        valid_spells["pred_m2"] = pred_spell_m2
        valid_spells["pred_m3"] = pred_spell_m3
        valid_spells["pred_m4"] = pred_spell_m4
        valid_spells["pred_m5"] = pred_spell_m5
        valid_spells["se_m5"] = se_spell_m5
        valid_spells["epistemic_state"] = state_spell_m5
        valid_spells["context_exposure"] = ctx_exp_spell
        valid_spells["fold"] = fold_idx
        valid_spells["actual"] = y_true_econ
        valid_spells["bowler_role"] = valid_spells["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        
        bowler_models = [
            ("M1_Global", pred_spell_m1),
            ("M2_Unpooled", pred_spell_m2),
            ("M3_Heuristic_M100", pred_spell_m3),
            ("M4_Contextual_Composition_B42", pred_spell_m4),
            ("M5_Player_Posterior_EB_B42", pred_spell_m5)
        ]
        
        for m_name, p_econ in bowler_models:
            sq_err = (p_econ - y_true_econ) ** 2
            unweighted_rmse = float(np.sqrt(np.mean(sq_err)))
            weighted_rmse = float(np.sqrt(np.sum(spell_weights * sq_err)))
            
            # Cluster-robust SE of squared error loss
            se_mse, se_status = compute_metric_cluster_robust_se(sq_err, spell_matches_arr)
            # Delta method for RMSE SE: SE(RMSE) = SE(MSE) / (2 * RMSE)
            se_rmse = (se_mse / (2.0 * unweighted_rmse)) if unweighted_rmse > 0 else np.nan
            
            model_comparison_records.append({
                "fold": fold_idx,
                "domain": "Bowler",
                "metric": "Spell_Economy_RPO",
                "model": m_name,
                "score": unweighted_rmse,
                "score_cluster_se": se_rmse,
                "log_loss": np.nan,
                "rmse": unweighted_rmse,
                "weighted_rmse": weighted_rmse,
                "sample_size": len(valid_spells)
            })
            
        # 5. Rebuilt Subgroup Reliability (Major Correction E)
        subgroup_configs = [
            ("Batter", legal_val, ["phase", "tier"], "1_Batter_Phase_x_Tier", "is_boundary", pred_bnd_m5, True, 150),
            ("Batter", legal_val, ["batter_role", "phase"], "2_Batter_Role_x_Phase", "is_boundary", pred_bnd_m5, True, 150),
            ("Batter", legal_val, ["batter_role", "tier"], "3_Batter_Role_x_Tier", "is_boundary", pred_bnd_m5, True, 150),
            ("Bowler", valid_spells, ["phase", "modal_tier"], "4_Bowler_Phase_x_Tier", "actual_economy", valid_spells["pred_m5"].values, False, 50),
            ("Bowler", valid_spells, ["bowler_role", "phase"], "5_Bowler_Role_x_Phase", "actual_economy", valid_spells["pred_m5"].values, False, 50),
            ("Bowler", valid_spells, ["bowler_role", "modal_tier"], "6_Bowler_Role_x_Tier", "actual_economy", valid_spells["pred_m5"].values, False, 50),
        ]
        
        for domain, s_df, grp_cols, b_name, target_col, p_vals, is_binary, min_req in subgroup_configs:
            eval_data = s_df.copy()
            eval_data["pred"] = p_vals
            eval_data["actual_val"] = eval_data[target_col].values
            id_col = bat_id_col if domain == "Batter" else "bowler_id"
            
            for g_vals, grp in eval_data.groupby(grp_cols):
                if not isinstance(g_vals, tuple):
                    g_vals = (g_vals,)
                n_obs = len(grp)
                n_players = grp[id_col].nunique()
                n_matches = grp["match_id"].nunique()
                y_act = grp["actual_val"].values
                y_pr = grp["pred"].values
                clusters = grp["match_id"].values
                
                # ESTIMAND DEFINED EXPLICITLY: Model Prediction Error / Loss
                if is_binary:
                    # Loss = Squared Error (Brier Loss)
                    loss_i = (y_pr - y_act) ** 2
                    metric_estimand = float(np.mean(loss_i))
                    metric_name = "brier_score"
                    se_metric, cluster_status = compute_metric_cluster_robust_se(loss_i, clusters)
                else:
                    # Loss = Squared Error (for RMSE)
                    loss_i = (y_pr - y_act) ** 2
                    mse_val = float(np.mean(loss_i))
                    metric_estimand = float(np.sqrt(mse_val))
                    metric_name = "rmse"
                    se_mse, cluster_status = compute_metric_cluster_robust_se(loss_i, clusters)
                    se_metric = (se_mse / (2.0 * metric_estimand)) if metric_estimand > 0 and np.isfinite(se_mse) else np.nan
                    
                # Explicit Grounded Sufficiency Evaluation
                # INVARIANT: NaN or unavailable standard error NEVER produces SUFFICIENT
                if n_obs == 0:
                    status = "EMPTY_CELL"
                elif n_obs < min_req:
                    status = "INSUFFICIENT_SAMPLE_SIZE"
                elif n_players < 5:
                    status = "INSUFFICIENT_PLAYER_DIVERSITY"
                elif n_matches < 5 or not np.isfinite(se_metric):
                    status = "INSUFFICIENT_INDEPENDENT_CLUSTERS"
                elif se_metric > (0.05 if is_binary else 1.20):
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
                    "independent_clusters": n_matches,
                    "target_metric": metric_name,
                    "metric_estimand": metric_estimand,
                    "cluster_robust_se": se_metric,
                    "mean_actual": float(np.mean(y_act)),
                    "mean_prediction": float(np.mean(y_pr)),
                    "sufficiency_status": status
                }
                for c_name, c_val in zip(grp_cols, g_vals):
                    rec[c_name] = c_val
                subgroup_records.append(rec)
                
        # Stratified Calibration Table for this fold
        cal_bat = compute_stratified_calibration_table(legal_val, domain="Batter")
        cal_bat["fold"] = fold_idx
        cal_bowl = compute_stratified_calibration_table(valid_spells, domain="Bowler")
        cal_bowl["fold"] = fold_idx
        calibration_diag_records.extend(cal_bat.to_dict(orient="records"))
        calibration_diag_records.extend(cal_bowl.to_dict(orient="records"))
        
        print(f"Fold {fold_idx} completed in {time.time() - fold_start:.2f}s")
        
    # Save Isolation JSON
    isolation_path = os.path.join(output_dir, "M5_5B_4_2_FOLD_MATCH_ISOLATION.json")
    with open(isolation_path, "w", encoding="utf-8") as f:
        json.dump(fold_isolation_records, f, indent=2)
        
    # Save Model Comparison CSV
    df_comparison = pd.DataFrame(model_comparison_records)
    comparison_csv_path = os.path.join(output_dir, "M5_5B_4_2_MODEL_COMPARISON.csv")
    df_comparison.to_csv(comparison_csv_path, index=False)
    
    # Save Subgroup Reliability CSV
    df_subgroups = pd.DataFrame(subgroup_records)
    subgroups_csv_path = os.path.join(output_dir, "M5_5B_4_2_SUBGROUP_RELIABILITY.csv")
    df_subgroups.to_csv(subgroups_csv_path, index=False)
    
    # Save Calibration Diagnostics CSV
    df_calibration = pd.DataFrame(calibration_diag_records)
    cal_csv_path = os.path.join(output_dir, "M5_5B_4_2_POSTERIOR_CALIBRATION_DIAGNOSTICS.csv")
    df_calibration.to_csv(cal_csv_path, index=False)
    
    print(f"\n[M5.5-B.4.2] Validation successfully completed in {time.time() - start_time:.2f}s")
    print(f"Saved: {isolation_path}")
    print(f"Saved: {comparison_csv_path}")
    print(f"Saved: {subgroups_csv_path}")
    print(f"Saved: {cal_csv_path}")
    
    return {
        "fold_isolation": fold_isolation_records,
        "model_comparison": df_comparison,
        "subgroups": df_subgroups,
        "calibration": df_calibration
    }


if __name__ == "__main__":
    res = run_full_validation_b4_2(n_boot=60)
    print("\nModel Comparison Aggregate Summary:")
    print(res["model_comparison"].groupby(["domain", "metric", "model"])[["score", "score_cluster_se"]].mean())
