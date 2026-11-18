"""
RR ScoutIQ — Milestone M5.5-B.4.3.2: Final Targeted Statistical Remediation & Cross-Validation Pipeline
Module: src/m5_5b_4_3_2/run_validation_b4_3_2.py

Implements:
1. Leakage-free 5-fold match-grouped cross-validation.
2. Henderson Method III crossed random-effects variance estimation strictly from training data.
3. Unification of bowler predictive variance with hyperparameter estimation (no 16.0 RPO^2 assumption).
4. Dual continuous interval coverage evaluation (80% and 95%) for bowler economy.
5. Probability calibration framework (ECE, Brier, Log Loss, Slope, Intercept) for discrete batter outcomes.
6. Two-way cluster-robust uncertainty across independent match and player clusters.
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
from src.m5_5b_4_3_2.cluster_variance_b4_3_2 import (
    compute_two_way_cluster_variance,
    compute_match_block_bootstrap_covariance
)
from src.m5_5b_4_3_2.variance_decomposition_b4_3_2 import (
    estimate_crossed_variance_components_henderson3
)
from src.m5_5b_4_3_2.epistemic_context_engine_b4_3_2 import (
    ContextualPlayerBaselineRecordB432,
    EpistemicStateB432
)
from src.m5_5b_4_3_2.hierarchical_engine_b4_3_2 import (
    ContextualHierarchyB432,
    PlayerPosteriorBaselineEstimatorB432
)
from src.m5_5b_4_3_2.bowler_fairness_matched_b4_3_2 import run_player_match_fairness_analysis_b432
from src.m5_5b_4_3_2.calibration_engine_b4_3_2 import (
    compute_continuous_interval_coverage_b432,
    compute_binary_probability_calibration_b432,
    compute_stratified_calibration_table_b432
)


def compute_loss_two_way_cluster_se(
    loss_series: np.ndarray,
    cluster_match: np.ndarray,
    cluster_player: np.ndarray
) -> Tuple[float, str]:
    """
    Computes Cameron-Gelbach-Miller two-way cluster standard error on the loss series.
    """
    n = len(loss_series)
    if n <= 1:
        return np.nan, "INSUFFICIENT_OBSERVATIONS"
        
    mean_l = float(np.mean(loss_series))
    resids = loss_series - mean_l
    var_l, status = compute_two_way_cluster_variance(resids, cluster_match, cluster_player)
    
    if np.isfinite(var_l) and var_l >= 0:
        return float(math.sqrt(var_l)), status
    return np.nan, status


def run_full_validation_b4_3_2(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_4_3_2",
    n_boot: int = 100
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()
    
    print("[M5.5-B.4.3.2] Loading clean canonical deliveries...")
    df = load_clean_deliveries(data_path)
    total_deliveries = len(df)
    total_matches = df["match_id"].nunique()
    print(f"Loaded {total_deliveries} deliveries across {total_matches} matches.")
    
    df["phase"] = df["pre_match_phase"].astype(str)
    df["tier"] = df["pre_pressure_tier"].astype(str)
    df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
    df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
    
    bat_id_col = "batter_id" if "batter_id" in df.columns else "striker_id"
    bat_name_col = "batter_name" if "batter_name" in df.columns else "striker"
    
    gkf = GroupKFold(n_splits=5)
    groups = df["match_id"].values
    
    fold_isolation_records = {}
    model_comparison_records = []
    paired_comparison_records = []
    subgroup_records = []
    all_oof_prediction_rows = []
    all_val_spells_list = []
    all_legal_val_list = []
    calibration_diag_records = []
    binary_reliability_records = []
    
    print("\n[M5.5-B.4.3.2] Executing 5-Fold Match-Grouped Cross-Validation...")
    
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
        
        # 2. Contextual Hierarchy & Hyperparameter Estimation strictly from training data
        context_hier = ContextualHierarchyB432(n_boot=n_boot)
        context_hier.fit(train_df)
        estimator = PlayerPosteriorBaselineEstimatorB432(context_hier)
        
        # Pre-compute training aggregates for batters:
        train_legal = train_df[train_df["is_legal"] == 1]
        bat_ctx_agg = train_legal.groupby([bat_id_col, "phase", "tier"]).agg(
            ctx_boundaries=("is_boundary", "sum"),
            ctx_balls=("is_legal", "sum"),
            ctx_matches=("match_id", "nunique")
        )
        bat_ctx_dict = bat_ctx_agg.to_dict(orient="index")
        
        bat_car_agg = train_legal.groupby(bat_id_col).agg(
            car_boundaries=("is_boundary", "sum"),
            car_balls=("is_legal", "sum"),
            car_matches=("match_id", "nunique")
        )
        bat_car_dict = bat_car_agg.to_dict(orient="index")
        
        # 3. Evaluate Batter Out-of-Fold
        legal_val = val_df[val_df["is_legal"] == 1].copy()
        y_true_bnd = legal_val["is_boundary"].values
        val_matches_arr = legal_val["match_id"].values
        val_batters_arr = legal_val[bat_id_col].values
        
        train_global_bnd = float(train_legal["is_boundary"].mean())
        pred_bnd_m1 = np.full(len(legal_val), train_global_bnd, dtype=float)
        
        # M2: Unpooled Empirical
        pred_bnd_m2 = np.array([
            bat_car_dict.get(pid, {}).get("car_boundaries", 0) / max(1, bat_car_dict.get(pid, {}).get("car_balls", 0))
            if pid in bat_car_dict else train_global_bnd
            for pid in val_batters_arr
        ])
        
        # M3: Heuristic Shrunk M=100
        pred_bnd_m3 = np.array([
            (bat_car_dict.get(pid, {}).get("car_boundaries", 0) + train_global_bnd * 100.0) /
            (bat_car_dict.get(pid, {}).get("car_balls", 0) + 100.0)
            if pid in bat_car_dict else train_global_bnd
            for pid in val_batters_arr
        ])
        
        # M4 & M5
        pred_bnd_m4 = []
        pred_bnd_m5 = []
        se_latent_bnd_m5 = []
        se_pred_bnd_m5 = []
        state_bnd_m5 = []
        ctx_exp_bnd = []
        
        for _, row in legal_val.iterrows():
            pid = row[bat_id_col]
            ph = row["phase"]
            tr = row["tier"]
            
            p_comp = context_hier.get_context_expectation(ph, tr, "batter_boundary")
            pred_bnd_m4.append(p_comp)
            
            ctx_stat = bat_ctx_dict.get((pid, ph, tr), {"ctx_balls": 0, "ctx_boundaries": None, "ctx_matches": 0})
            car_stat = bat_car_dict.get(pid, {"car_balls": 0, "car_boundaries": None, "car_matches": 0})
            
            rec = estimator.estimate_batter_boundary_posterior(
                player_id=pid,
                phase=ph,
                tier=tr,
                context_balls=ctx_stat["ctx_balls"],
                context_boundaries=ctx_stat["ctx_boundaries"],
                context_matches=ctx_stat["ctx_matches"],
                career_balls=car_stat["car_balls"],
                career_boundaries=car_stat["car_boundaries"],
                career_matches=car_stat["car_matches"],
                min_context_screening_balls=30
            )
            pred_bnd_m5.append(rec.shrunk_baseline)
            se_latent_bnd_m5.append(rec.standard_error)
            se_pred_bnd_m5.append(rec.get_predictive_se(n_eval=1))
            state_bnd_m5.append(rec.state.value)
            ctx_exp_bnd.append(ctx_stat["ctx_balls"])
            
        pred_bnd_m4 = np.array(pred_bnd_m4)
        pred_bnd_m5 = np.array(pred_bnd_m5)
        se_latent_bnd_m5 = np.array(se_latent_bnd_m5)
        se_pred_bnd_m5 = np.array(se_pred_bnd_m5)
        
        legal_val["pred_m1"] = pred_bnd_m1
        legal_val["pred_m2"] = pred_bnd_m2
        legal_val["pred_m3"] = pred_bnd_m3
        legal_val["pred_m4"] = pred_bnd_m4
        legal_val["pred_m5"] = pred_bnd_m5
        legal_val["se_latent_m5"] = se_latent_bnd_m5
        legal_val["se_pred_m5"] = se_pred_bnd_m5
        legal_val["epistemic_state"] = state_bnd_m5
        legal_val["context_exposure"] = ctx_exp_bnd
        legal_val["fold"] = fold_idx
        legal_val["actual"] = y_true_bnd
        all_legal_val_list.append(legal_val.copy())
        
        for _, row in legal_val.iterrows():
            all_oof_prediction_rows.append({
                "fold": fold_idx,
                "domain": "Batter",
                "match_id": int(row["match_id"]),
                "player_id": int(row[bat_id_col]),
                "player_name": str(row.get(bat_name_col, "Unknown")),
                "role": str(row.get("batter_role", "Unknown")),
                "phase": str(row["phase"]),
                "tier": str(row["tier"]),
                "exposure_balls": 1,
                "actual": float(row["actual"]),
                "pred_m1": float(row["pred_m1"]),
                "pred_m2": float(row["pred_m2"]),
                "pred_m3": float(row["pred_m3"]),
                "pred_m4": float(row["pred_m4"]),
                "pred_m5": float(row["pred_m5"]),
                "se_latent_m5": float(row["se_latent_m5"]),
                "se_pred_m5": float(row["se_pred_m5"]),
                "epistemic_state": str(row["epistemic_state"]),
                "context_training_exposure": int(row["context_exposure"])
            })
            
        # Batter Model Comparison Ledger
        batter_models = [
            ("M1_Global", pred_bnd_m1),
            ("M2_Unpooled", pred_bnd_m2),
            ("M3_Heuristic_M100", pred_bnd_m3),
            ("M4_Contextual_B432", pred_bnd_m4),
            ("M5_Player_Posterior_EB_B432", pred_bnd_m5)
        ]
        
        losses_bat = {}
        for m_name, p_arr in batter_models:
            brier_loss = (p_arr - y_true_bnd) ** 2
            losses_bat[m_name] = brier_loss
            brier = float(np.mean(brier_loss))
            p_clip = np.clip(p_arr, 1e-6, 1.0 - 1e-6)
            ll = float(-np.mean(y_true_bnd * np.log(p_clip) + (1.0 - y_true_bnd) * np.log(1.0 - p_clip)))
            
            se_brier, se_status = compute_loss_two_way_cluster_se(brier_loss, val_matches_arr, val_batters_arr)
            
            model_comparison_records.append({
                "fold": fold_idx,
                "domain": "Batter",
                "metric": "Boundary%",
                "model": m_name,
                "score": brier,
                "score_cluster_se": se_brier,
                "cluster_se_status": se_status,
                "log_loss": ll,
                "rmse": np.nan,
                "weighted_rmse": np.nan,
                "sample_size": len(y_true_bnd)
            })
            
        # Paired model comparisons for batters
        for comp_base in ["M4_Contextual_B432", "M3_Heuristic_M100", "M1_Global"]:
            diff_loss = losses_bat["M5_Player_Posterior_EB_B432"] - losses_bat[comp_base]
            mean_diff = float(np.mean(diff_loss))
            diff_se, diff_status = compute_loss_two_way_cluster_se(diff_loss, val_matches_arr, val_batters_arr)
            t_stat = (mean_diff / diff_se) if (np.isfinite(diff_se) and diff_se > 0) else np.nan
            paired_comparison_records.append({
                "fold": fold_idx,
                "domain": "Batter",
                "comparison": f"M5_vs_{comp_base}",
                "mean_loss_difference": mean_diff,
                "cluster_se": diff_se,
                "t_stat": t_stat,
                "status": diff_status
            })
            
        # Binary Probability Calibration Deciles for Batters
        calib_stats = compute_binary_probability_calibration_b432(y_true_bnd, pred_bnd_m5, n_bins=10)
        bins = np.linspace(0.0, 1.0, 11)
        bin_idx = np.digitize(pred_bnd_m5, bins) - 1
        for b_i in range(10):
            m_bin = bin_idx == b_i
            if np.sum(m_bin) > 0:
                binary_reliability_records.append({
                    "fold": fold_idx,
                    "domain": "Batter",
                    "bin_index": b_i,
                    "bin_lower": bins[b_i],
                    "bin_upper": bins[b_i + 1],
                    "bin_center": 0.5 * (bins[b_i] + bins[b_i + 1]),
                    "sample_size": int(np.sum(m_bin)),
                    "actual_rate": float(np.mean(y_true_bnd[m_bin])),
                    "predicted_rate": float(np.mean(pred_bnd_m5[m_bin])),
                    "calibration_error": float(abs(np.mean(y_true_bnd[m_bin]) - np.mean(pred_bnd_m5[m_bin])))
                })
                
        # 4. Evaluate Bowler Spell Economy Out-of-Fold
        val_spells = aggregate_bowler_spells(val_df)
        valid_spells_mask = val_spells["is_valid_spell"] & np.isfinite(val_spells["actual_economy"])
        valid_spells = val_spells[valid_spells_mask].copy()
        
        y_true_econ = valid_spells["actual_economy"].values
        spell_weights = valid_spells["legal_balls"].values / valid_spells["legal_balls"].sum()
        spell_matches_arr = valid_spells["match_id"].values
        spell_bowlers_arr = valid_spells["bowler_id"].values
        
        train_global_econ = calculate_bowler_economy(train_df)["economy_rate"]
        pred_spell_m1 = np.full(len(valid_spells), train_global_econ, dtype=float)
        
        # Training aggregates for bowlers:
        bowl_ctx_agg = {}
        for (bid, ph, tr), b_grp in train_df.groupby(["bowler_id", "phase", "tier"]):
            s = calculate_bowler_economy(b_grp)
            bowl_ctx_agg[(bid, ph, tr)] = {
                "legal_balls": s["legal_balls"],
                "debit_runs": s["bowler_debit_runs"],
                "matches": b_grp["match_id"].nunique()
            }
            
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
        
        # M3 Heuristic M=100
        global_rpb = train_global_econ / 6.0
        pred_spell_m3 = []
        for _, row in valid_spells.iterrows():
            bid = row["bowler_id"]
            car = bowl_car_agg.get(bid, {"legal_balls": 0, "debit_runs": 0.0})
            shrunk_rpo = 6.0 * (car["debit_runs"] + global_rpb * 100.0) / (car["legal_balls"] + 100.0)
            pred_spell_m3.append(shrunk_rpo)
        pred_spell_m3 = np.array(pred_spell_m3)
        
        # M4 & M5
        pred_spell_m4 = []
        pred_spell_m5 = []
        se_latent_spell_m5 = []
        se_pred_spell_m5 = []
        state_spell_m5 = []
        ctx_exp_spell = []
        
        for _, sp_row in valid_spells.iterrows():
            bid = sp_row["bowler_id"]
            mid = sp_row["match_id"]
            ph = sp_row["phase"]
            modal_t = sp_row["modal_tier"]
            
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
            
            # M5 Empirical Bayes Posterior Baseline
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
            se_latent_spell_m5.append(rec.standard_error)
            
            sp_balls = int(sp_row.get("legal_balls", legal_sp_count))
            n_eval_balls = max(1, sp_balls if sp_balls > 0 else legal_sp_count)
            pred_var_spell = rec.get_predictive_variance(n_eval=n_eval_balls)
            se_pred_spell_m5.append(math.sqrt(pred_var_spell))
            
            state_spell_m5.append(rec.state.value)
            ctx_exp_spell.append(ctx_data["legal_balls"])
            
        pred_spell_m4 = np.array(pred_spell_m4)
        pred_spell_m5 = np.array(pred_spell_m5)
        se_latent_spell_m5 = np.array(se_latent_spell_m5)
        se_pred_spell_m5 = np.array(se_pred_spell_m5)
        
        valid_spells["pred_m1"] = pred_spell_m1
        valid_spells["pred_m2"] = pred_spell_m2
        valid_spells["pred_m3"] = pred_spell_m3
        valid_spells["pred_m4"] = pred_spell_m4
        valid_spells["pred_m5"] = pred_spell_m5
        valid_spells["se_latent_m5"] = se_latent_spell_m5
        valid_spells["se_pred_m5"] = se_pred_spell_m5
        valid_spells["epistemic_state"] = state_spell_m5
        valid_spells["context_exposure"] = ctx_exp_spell
        valid_spells["fold"] = fold_idx
        valid_spells["actual"] = y_true_econ
        valid_spells["bowler_role"] = valid_spells["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        all_val_spells_list.append(valid_spells.copy())
        
        for _, sp_row in valid_spells.iterrows():
            all_oof_prediction_rows.append({
                "fold": fold_idx,
                "domain": "Bowler",
                "match_id": int(sp_row["match_id"]),
                "player_id": int(sp_row["bowler_id"]),
                "player_name": str(sp_row.get("bowler_name", "Unknown")),
                "role": str(sp_row.get("bowler_role", "Middle Enforcer")),
                "phase": str(sp_row["phase"]),
                "tier": str(sp_row["modal_tier"]),
                "exposure_balls": int(sp_row["legal_balls"]),
                "actual": float(sp_row["actual"]),
                "pred_m1": float(sp_row["pred_m1"]),
                "pred_m2": float(sp_row["pred_m2"]),
                "pred_m3": float(sp_row["pred_m3"]),
                "pred_m4": float(sp_row["pred_m4"]),
                "pred_m5": float(sp_row["pred_m5"]),
                "se_latent_m5": float(sp_row["se_latent_m5"]),
                "se_pred_m5": float(sp_row["se_pred_m5"]),
                "epistemic_state": str(sp_row["epistemic_state"]),
                "context_training_exposure": int(sp_row["context_exposure"])
            })
            
        bowler_models = [
            ("M1_Global", pred_spell_m1),
            ("M2_Unpooled", pred_spell_m2),
            ("M3_Heuristic_M100", pred_spell_m3),
            ("M4_Contextual_Composition_B432", pred_spell_m4),
            ("M5_Player_Posterior_EB_B432", pred_spell_m5)
        ]
        
        losses_bowl = {}
        for m_name, p_econ in bowler_models:
            sq_err = (p_econ - y_true_econ) ** 2
            losses_bowl[m_name] = sq_err
            unweighted_rmse = float(np.sqrt(np.mean(sq_err)))
            weighted_rmse = float(np.sqrt(np.sum(spell_weights * sq_err)))
            
            se_mse, se_status = compute_loss_two_way_cluster_se(sq_err, spell_matches_arr, spell_bowlers_arr)
            se_rmse = (se_mse / (2.0 * unweighted_rmse)) if (unweighted_rmse > 0 and np.isfinite(se_mse)) else np.nan
            
            model_comparison_records.append({
                "fold": fold_idx,
                "domain": "Bowler",
                "metric": "Spell_Economy_RPO",
                "model": m_name,
                "score": unweighted_rmse,
                "score_cluster_se": se_rmse,
                "cluster_se_status": se_status,
                "log_loss": np.nan,
                "rmse": unweighted_rmse,
                "weighted_rmse": weighted_rmse,
                "sample_size": len(valid_spells)
            })
            
        # Paired model comparisons for bowlers
        for comp_base in ["M4_Contextual_Composition_B432", "M3_Heuristic_M100", "M1_Global"]:
            diff_loss = losses_bowl["M5_Player_Posterior_EB_B432"] - losses_bowl[comp_base]
            mean_diff = float(np.mean(diff_loss))
            diff_se, diff_status = compute_loss_two_way_cluster_se(diff_loss, spell_matches_arr, spell_bowlers_arr)
            t_stat = (mean_diff / diff_se) if (np.isfinite(diff_se) and diff_se > 0) else np.nan
            paired_comparison_records.append({
                "fold": fold_idx,
                "domain": "Bowler",
                "comparison": f"M5_vs_{comp_base}",
                "mean_loss_difference": mean_diff,
                "cluster_se": diff_se,
                "t_stat": t_stat,
                "status": diff_status
            })
            
        # 5. Subgroup Reliability (349 rows across 5 folds)
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
                clusters_m = grp["match_id"].values
                clusters_p = grp[id_col].values
                
                loss_i = (y_pr - y_act) ** 2
                if is_binary:
                    metric_estimand = float(np.mean(loss_i))
                    metric_name = "brier_score"
                    se_metric, cluster_status = compute_loss_two_way_cluster_se(loss_i, clusters_m, clusters_p)
                else:
                    mse_val = float(np.mean(loss_i))
                    metric_estimand = float(np.sqrt(mse_val))
                    metric_name = "rmse"
                    se_mse, cluster_status = compute_loss_two_way_cluster_se(loss_i, clusters_m, clusters_p)
                    se_metric = (se_mse / (2.0 * metric_estimand)) if (metric_estimand > 0 and np.isfinite(se_mse)) else np.nan
                    
                # Invariant: NaN or unavailable standard error NEVER produces SUFFICIENT
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
                    "cluster_status": cluster_status,
                    "mean_actual": float(np.mean(y_act)),
                    "mean_prediction": float(np.mean(y_pr)),
                    "sufficiency_status": status
                }
                for c_name, c_val in zip(grp_cols, g_vals):
                    rec[c_name] = c_val
                subgroup_records.append(rec)
                
        # Stratified Calibration Table for this fold
        cal_bat = compute_stratified_calibration_table_b432(legal_val, domain="Batter")
        cal_bat["fold"] = fold_idx
        cal_bowl = compute_stratified_calibration_table_b432(valid_spells, domain="Bowler")
        cal_bowl["fold"] = fold_idx
        calibration_diag_records.extend(cal_bat.to_dict(orient="records"))
        calibration_diag_records.extend(cal_bowl.to_dict(orient="records"))
        
        print(f"Fold {fold_idx} completed in {time.time() - fold_start:.2f}s")
        
    # Save Isolation JSON
    isolation_path = os.path.join(output_dir, "M5_5B_4_3_2_FOLD_MATCH_ISOLATION.json")
    with open(isolation_path, "w", encoding="utf-8") as f:
        json.dump(fold_isolation_records, f, indent=2)
        
    # Save Model Comparison CSV
    df_comparison = pd.DataFrame(model_comparison_records)
    comparison_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_MODEL_COMPARISON.csv")
    df_comparison.to_csv(comparison_csv_path, index=False)
    
    # Save Paired Comparison CSV
    df_paired = pd.DataFrame(paired_comparison_records)
    paired_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_PAIRED_MODEL_COMPARISON.csv")
    df_paired.to_csv(paired_csv_path, index=False)
    
    # Save Subgroup Reliability CSV
    df_subgroups = pd.DataFrame(subgroup_records)
    subgroups_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_SUBGROUP_RELIABILITY.csv")
    df_subgroups.to_csv(subgroups_csv_path, index=False)
    
    # Authoritative Global Calibration Diagnostics across all 18 Strata
    df_all_valid_spells = pd.concat(all_val_spells_list, ignore_index=True)
    df_all_legal_val = pd.concat(all_legal_val_list, ignore_index=True)
    cal_global_bowl = compute_stratified_calibration_table_b432(df_all_valid_spells, domain="Bowler")
    cal_global_bat = compute_stratified_calibration_table_b432(df_all_legal_val, domain="Batter")
    df_global_calibration = pd.concat([cal_global_bowl, cal_global_bat], ignore_index=True)
    
    cal_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_POSTERIOR_CALIBRATION_DIAGNOSTICS.csv")
    df_global_calibration.to_csv(cal_csv_path, index=False)
    
    # Save Fold-by-Fold Calibration Breakdown CSV
    df_fold_calibration = pd.DataFrame(calibration_diag_records)
    cal_fold_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_POSTERIOR_CALIBRATION_DIAGNOSTICS_BY_FOLD.csv")
    df_fold_calibration.to_csv(cal_fold_csv_path, index=False)
    
    # Save Binary Reliability Deciles CSV
    df_deciles = pd.DataFrame(binary_reliability_records)
    deciles_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_BINARY_RELIABILITY_DECILES.csv")
    df_deciles.to_csv(deciles_csv_path, index=False)
    
    # Save Complete Out-Of-Fold Predictions CSV
    df_oof = pd.DataFrame(all_oof_prediction_rows)
    oof_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_PREDICTIONS_OUT_OF_FOLD.csv")
    df_oof.to_csv(oof_csv_path, index=False)
    
    print(f"\n[M5.5-B.4.3.2] Validation successfully completed in {time.time() - start_time:.2f}s")
    print(f"Saved: {isolation_path}")
    print(f"Saved: {comparison_csv_path}")
    print(f"Saved: {paired_csv_path}")
    print(f"Saved: {subgroups_csv_path}")
    print(f"Saved: {cal_csv_path}")
    print(f"Saved: {cal_fold_csv_path}")
    print(f"Saved: {deciles_csv_path}")
    print(f"Saved: {oof_csv_path} ({len(df_oof)} rows)")
    
    
    # Generate Player Fairness Diagnostics (LOPO decontaminated)
    print("\nComputing matched bowler fairness diagnostics (LOPO decontaminated)...")
    fairness_res = run_player_match_fairness_analysis_b432(data_path=data_path)
    fairness_csv_path = os.path.join(output_dir, "M5_5B_4_3_2_PLAYER_FAIRNESS_DIAGNOSTICS.csv")
    fairness_res["df_all_matched"].to_csv(fairness_csv_path, index=False)
    print(f"Saved: {fairness_csv_path} ({len(fairness_res['df_all_matched'])} rows)")
    return {
        "fold_isolation": fold_isolation_records,
        "model_comparison": df_comparison,
        "paired_comparison": df_paired,
        "subgroups": df_subgroups,
        "calibration": df_global_calibration,
        "calibration_by_fold": df_fold_calibration,
        "oof_predictions": df_oof
    }


if __name__ == "__main__":
    res = run_full_validation_b4_3_2(n_boot=60)
    print("\nModel Comparison Aggregate Summary:")
    print(res["model_comparison"].groupby(["domain", "metric", "model"])[["score", "score_cluster_se"]].mean())
