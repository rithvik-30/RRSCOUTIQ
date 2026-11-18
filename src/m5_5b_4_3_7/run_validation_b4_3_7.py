"""
RR ScoutIQ — Milestone M5.5-B.4.3.7: Leave-Player-and-Matches-Out (LPMO) Contextual Prior
Module: src/m5_5b_4_3_7/run_validation_b4_3_7.py

Implements:
1. Leakage-free 5-fold match-grouped cross-validation.
2. Henderson Method III crossed random-effects variance estimation strictly from training data.
3. Genuine Leave-Player-and-Matches-Out (LPMO) contextual priors completely decontaminating
   individual player observations and shared-match environmental shocks.
4. Exact match cluster-linearization ratio variance estimation over independent remaining matches.
5. Full Joint Conjugate Gaussian Bayesian posterior mean and posterior variance.
6. Dual continuous interval coverage evaluation (80% and 95%) for bowler economy.
7. Probability calibration framework (ECE, Brier, Log Loss, Slope, Intercept) for discrete batter outcomes.
8. Two-way cluster-robust uncertainty across independent match and player clusters.
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
from src.m5_5b_4_3_7.cluster_variance_b4_3_7 import (
    compute_two_way_cluster_variance,
    compute_match_block_bootstrap_covariance
)
from src.m5_5b_4_3_7.variance_decomposition_b4_3_7 import (
    estimate_crossed_variance_components_henderson3
)
from src.m5_5b_4_3_7.epistemic_context_engine_b4_3_7 import (
    ContextualPlayerBaselineRecordB437,
    EpistemicStateB437
)
from src.m5_5b_4_3_7.hierarchical_engine_b4_3_7 import (
    ContextualHierarchyB437,
    PlayerPosteriorBaselineEstimatorB437
)
from src.m5_5b_4_3_7.bowler_fairness_matched_b4_3_7 import run_player_match_fairness_analysis_b437
from src.m5_5b_4_3_7.calibration_engine_b4_3_7 import (
    compute_continuous_interval_coverage_b436 as compute_continuous_interval_coverage_b437,
    compute_binary_probability_calibration_b436 as compute_binary_probability_calibration_b437,
    compute_stratified_calibration_table_b436 as compute_stratified_calibration_table_b437
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


def run_full_validation_b4_3_7(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_4_3_7",
    n_boot: int = 100
) -> Dict[str, Any]:
    start_time = time.time()
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n=======================================================")
    print(f"  RR ScoutIQ — Milestone M5.5-B.4.3.7 Validation Suite")
    print(f"  Leave-Player-and-Matches-Out (LPMO) Contextual Prior")
    print(f"=======================================================\n")
    
    print(f"Loading canonical dataset from {data_path}...")
    df = load_clean_deliveries(data_path)
    
    df["phase"] = df["pre_match_phase"].astype(str)
    df["tier"] = df["pre_pressure_tier"].astype(str)
    df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
    df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
        
    bat_id_col = "batter_id" if "batter_id" in df.columns else "striker_id"
    bat_name_col = "batter_name" if "batter_name" in df.columns else "striker"
    
    unique_matches = df["match_id"].unique()
    n_matches = len(unique_matches)
    print(f"Total unique matches in canonical dataset: {n_matches}")
    
    gkf = GroupKFold(n_splits=5)
    splits = list(gkf.split(df, groups=df["match_id"]))
    
    fold_isolation_records = {}
    model_comparison_records = []
    paired_comparison_records = []
    subgroup_records = []
    calibration_diag_records = []
    binary_reliability_records = []
    all_oof_prediction_rows = []
    
    all_val_spells_list = []
    all_legal_val_list = []
    
    for fold_idx, (train_idx, val_idx) in enumerate(splits, 1):
        fold_start = time.time()
        print(f"\n--- Processing Fold {fold_idx}/5 ---")
        train_df = df.iloc[train_idx].copy()
        val_df = df.iloc[val_idx].copy()
        
        train_matches = sorted([int(m) for m in train_df["match_id"].unique()])
        val_matches = sorted([int(m) for m in val_df["match_id"].unique()])
        intersection = set(train_matches).intersection(set(val_matches))
        assert len(intersection) == 0, f"Fold {fold_idx} match leakage detected: {intersection}"
        
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
        print(f"Fold {fold_idx} strict match isolation verified (0 shared matches).")
        
        # 1. Player roles strictly from training data
        batter_roles = derive_training_batter_roles_b2(train_df)
        bowler_roles, bowler_details = derive_training_bowler_roles_b2(train_df)
        val_df["batter_role"] = val_df[bat_id_col].map(batter_roles).fillna("TopOrderBatter")
        val_df["bowler_role"] = val_df["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        
        # 2. Fit Contextual Hierarchy on Training Fold
        print(f"Fitting training contextual hierarchy with LPMO pre-aggregates...")
        context_hier = ContextualHierarchyB437()
        context_hier.fit(train_df)
        
        estimator = PlayerPosteriorBaselineEstimatorB437(context_hier)
        
        # 3. Evaluate Batter Boundary% Out-of-Fold
        legal_val = val_df[val_df["is_legal"] == 1].copy()
        y_true_bnd = legal_val["is_boundary"].values
        val_matches_arr = legal_val["match_id"].values
        val_batters_arr = legal_val[bat_id_col].values
        
        train_legal = train_df[train_df["is_legal"] == 1]
        train_global_bnd = float(train_legal["is_boundary"].mean())
        pred_bnd_m1 = np.full(len(legal_val), train_global_bnd, dtype=float)
        
        # Batter training aggregates
        bat_ctx_agg = train_legal.groupby([bat_id_col, "phase", "tier"]).agg(
            ctx_balls=("is_legal", "count"),
            ctx_boundaries=("is_boundary", "sum"),
            ctx_matches=("match_id", "nunique")
        ).reset_index()
        bat_ctx_dict = {
            (r[bat_id_col], r["phase"], r["tier"]): {
                "ctx_balls": r["ctx_balls"],
                "ctx_boundaries": r["ctx_boundaries"],
                "ctx_matches": r["ctx_matches"]
            }
            for _, r in bat_ctx_agg.iterrows()
        }
        
        bat_car_agg = train_legal.groupby(bat_id_col).agg(
            car_balls=("is_legal", "count"),
            car_boundaries=("is_boundary", "sum"),
            car_rate=("is_boundary", "mean"),
            car_matches=("match_id", "nunique")
        ).reset_index()
        bat_car_dict = {
            r[bat_id_col]: {
                "car_balls": r["car_balls"],
                "car_boundaries": r["car_boundaries"],
                "car_rate": r["car_rate"],
                "car_matches": r["car_matches"]
            }
            for _, r in bat_car_agg.iterrows()
        }
        
        # M2 Unpooled
        pred_bnd_m2 = np.array([
            bat_car_dict.get(row[bat_id_col], {}).get("car_rate", train_global_bnd)
            for _, row in legal_val.iterrows()
        ])
        
        # M3 Heuristic M=100
        pred_bnd_m3 = []
        for _, row in legal_val.iterrows():
            pid = row[bat_id_col]
            car = bat_car_dict.get(pid, {"car_balls": 0, "car_boundaries": 0})
            shrunk_bnd = (car["car_boundaries"] + train_global_bnd * 100.0) / (car["car_balls"] + 100.0)
            pred_bnd_m3.append(shrunk_bnd)
        pred_bnd_m3 = np.array(pred_bnd_m3)
        
        # M4 & M5
        pred_bnd_m4 = []
        pred_bnd_m5 = []
        se_latent_bnd_m5 = []
        se_pred_bnd_m5 = []
        state_bnd_m5 = []
        ctx_exp_bnd = []
        prov_bnd_m5 = []
        pop_balls_bnd_m5 = []
        exc_match_bnd_m5 = []
        rem_match_bnd_m5 = []
        eff_match_bnd_m5 = []
        hhi_match_bnd_m5 = []
        
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
                context_legal_balls=ctx_stat["ctx_balls"],
                context_boundaries=ctx_stat["ctx_boundaries"],
                context_matches=ctx_stat["ctx_matches"],
                career_legal_balls=car_stat["car_balls"],
                career_boundaries=car_stat["car_boundaries"],
                career_matches=car_stat["car_matches"],
                min_context_screening_balls=30
            )
            pred_bnd_m5.append(rec.shrunk_baseline)
            se_latent_bnd_m5.append(rec.standard_error)
            se_pred_bnd_m5.append(rec.get_predictive_se(n_eval=1))
            state_bnd_m5.append(rec.state.value)
            ctx_exp_bnd.append(ctx_stat["ctx_balls"])
            prov_bnd_m5.append(rec.prior_provenance)
            pop_balls_bnd_m5.append(rec.prior_population_balls)
            exc_match_bnd_m5.append(rec.excluded_match_count)
            rem_match_bnd_m5.append(rec.remaining_match_count)
            eff_match_bnd_m5.append(rec.effective_match_count)
            hhi_match_bnd_m5.append(rec.match_concentration_hhi)
            
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
        legal_val["prior_provenance"] = prov_bnd_m5
        legal_val["prior_population_balls"] = pop_balls_bnd_m5
        legal_val["excluded_match_count"] = exc_match_bnd_m5
        legal_val["remaining_match_count"] = rem_match_bnd_m5
        legal_val["effective_match_count"] = eff_match_bnd_m5
        legal_val["match_concentration_hhi"] = hhi_match_bnd_m5
        legal_val["player_id"] = legal_val[bat_id_col]
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
                "context_training_exposure": int(row["context_exposure"]),
                "prior_provenance": str(row.get("prior_provenance", "CELL_LPMO_ROBUST")),
                "prior_population_balls": int(row.get("prior_population_balls", 0)),
                "excluded_match_count": int(row.get("excluded_match_count", 0)),
                "remaining_match_count": int(row.get("remaining_match_count", 0)),
                "effective_match_count": float(row.get("effective_match_count", 0.0)),
                "match_concentration_hhi": float(row.get("match_concentration_hhi", 0.0))
            })
            
        # Batter Model Comparison Ledger
        batter_models = [
            ("M1_Global", pred_bnd_m1),
            ("M2_Unpooled", pred_bnd_m2),
            ("M3_Heuristic_M100", pred_bnd_m3),
            ("M4_Contextual_B437", pred_bnd_m4),
            ("M5_Player_Posterior_EB_B437", pred_bnd_m5)
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
        for comp_base in ["M4_Contextual_B437", "M3_Heuristic_M100", "M1_Global"]:
            diff_loss = losses_bat["M5_Player_Posterior_EB_B437"] - losses_bat[comp_base]
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
        calib_stats = compute_binary_probability_calibration_b437(y_true_bnd, pred_bnd_m5, n_bins=10)
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
            match_balls_list = b_grp[b_grp["is_legal"] == 1].groupby("match_id").size().tolist()
            bowl_ctx_agg[(bid, ph, tr)] = {
                "legal_balls": s["legal_balls"],
                "debit_runs": s["bowler_debit_runs"],
                "matches": b_grp["match_id"].nunique(),
                "match_balls_list": match_balls_list
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
        prov_spell_m5 = []
        pop_balls_spell_m5 = []
        exc_match_spell_m5 = []
        rem_match_spell_m5 = []
        eff_match_spell_m5 = []
        hhi_match_spell_m5 = []
        
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
            
            # M5 Empirical Bayes Posterior Baseline with LPMO
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
                min_context_screening_balls=30,
                context_match_balls_list=ctx_data.get("match_balls_list", None)
            )
            pred_spell_m5.append(rec.shrunk_baseline)
            se_latent_spell_m5.append(rec.standard_error)
            
            sp_balls = int(sp_row.get("legal_balls", legal_sp_count))
            n_eval_balls = max(1, sp_balls if sp_balls > 0 else legal_sp_count)
            pred_var_spell = rec.get_predictive_variance(n_eval=n_eval_balls)
            se_pred_spell_m5.append(math.sqrt(pred_var_spell))
            state_spell_m5.append(rec.state.value)
            ctx_exp_spell.append(ctx_data["legal_balls"])
            prov_spell_m5.append(rec.prior_provenance)
            pop_balls_spell_m5.append(rec.prior_population_balls)
            exc_match_spell_m5.append(rec.excluded_match_count)
            rem_match_spell_m5.append(rec.remaining_match_count)
            eff_match_spell_m5.append(rec.effective_match_count)
            hhi_match_spell_m5.append(rec.match_concentration_hhi)
            
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
        valid_spells["prior_provenance"] = prov_spell_m5
        valid_spells["prior_population_balls"] = pop_balls_spell_m5
        valid_spells["excluded_match_count"] = exc_match_spell_m5
        valid_spells["remaining_match_count"] = rem_match_spell_m5
        valid_spells["effective_match_count"] = eff_match_spell_m5
        valid_spells["match_concentration_hhi"] = hhi_match_spell_m5
        valid_spells["fold"] = fold_idx
        valid_spells["actual"] = y_true_econ
        valid_spells["bowler_role"] = valid_spells["bowler_id"].map(bowler_roles).fillna("Middle Enforcer")
        valid_spells["tier"] = valid_spells["modal_tier"]
        valid_spells["player_id"] = valid_spells["bowler_id"]
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
                "context_training_exposure": int(sp_row["context_exposure"]),
                "prior_provenance": str(sp_row.get("prior_provenance", "CELL_LPMO_ROBUST")),
                "prior_population_balls": int(sp_row.get("prior_population_balls", 0)),
                "excluded_match_count": int(sp_row.get("excluded_match_count", 0)),
                "remaining_match_count": int(sp_row.get("remaining_match_count", 0)),
                "effective_match_count": float(sp_row.get("effective_match_count", 0.0)),
                "match_concentration_hhi": float(sp_row.get("match_concentration_hhi", 0.0))
            })
            
        bowler_models = [
            ("M1_Global", pred_spell_m1),
            ("M2_Unpooled", pred_spell_m2),
            ("M3_Heuristic_M100", pred_spell_m3),
            ("M4_Contextual_Composition_B437", pred_spell_m4),
            ("M5_Player_Posterior_EB_B437", pred_spell_m5)
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
        for comp_base in ["M4_Contextual_Composition_B437", "M3_Heuristic_M100", "M1_Global"]:
            diff_loss = losses_bowl["M5_Player_Posterior_EB_B437"] - losses_bowl[comp_base]
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
            
        # 5. Subgroup Reliability
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
        cal_bat = compute_stratified_calibration_table_b437(legal_val, domain="Batter")
        cal_bat["fold"] = fold_idx
        cal_bowl = compute_stratified_calibration_table_b437(valid_spells, domain="Bowler")
        cal_bowl["fold"] = fold_idx
        calibration_diag_records.extend(cal_bat.to_dict(orient="records"))
        calibration_diag_records.extend(cal_bowl.to_dict(orient="records"))
        
        print(f"Fold {fold_idx} completed in {time.time() - fold_start:.2f}s")
        
    # Save Isolation JSON
    isolation_path = os.path.join(output_dir, "M5_5B_4_3_7_FOLD_MATCH_ISOLATION.json")
    with open(isolation_path, "w", encoding="utf-8") as f:
        json.dump(fold_isolation_records, f, indent=2)
        
    # Save Model Comparison CSV
    df_comparison = pd.DataFrame(model_comparison_records)
    comparison_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_MODEL_COMPARISON.csv")
    df_comparison.to_csv(comparison_csv_path, index=False)
    
    # Save Paired Comparison CSV
    df_paired = pd.DataFrame(paired_comparison_records)
    paired_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_PAIRED_MODEL_COMPARISON.csv")
    df_paired.to_csv(paired_csv_path, index=False)
    
    # Save Subgroup Reliability CSV
    df_subgroups = pd.DataFrame(subgroup_records)
    subgroups_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_SUBGROUP_RELIABILITY.csv")
    df_subgroups.to_csv(subgroups_csv_path, index=False)
    
    # Authoritative Global Calibration Diagnostics across all 18 Strata
    df_all_valid_spells = pd.concat(all_val_spells_list, ignore_index=True)
    df_all_legal_val = pd.concat(all_legal_val_list, ignore_index=True)
    cal_global_bowl = compute_stratified_calibration_table_b437(df_all_valid_spells, domain="Bowler")
    cal_global_bat = compute_stratified_calibration_table_b437(df_all_legal_val, domain="Batter")
    df_global_calibration = pd.concat([cal_global_bowl, cal_global_bat], ignore_index=True)
    
    cal_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_POSTERIOR_CALIBRATION_DIAGNOSTICS.csv")
    df_global_calibration.to_csv(cal_csv_path, index=False)
    
    # Save Fold-by-Fold Calibration Breakdown CSV
    df_fold_calibration = pd.DataFrame(calibration_diag_records)
    cal_fold_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_POSTERIOR_CALIBRATION_DIAGNOSTICS_BY_FOLD.csv")
    df_fold_calibration.to_csv(cal_fold_csv_path, index=False)
    
    # Save Binary Reliability Deciles CSV
    df_deciles = pd.DataFrame(binary_reliability_records)
    deciles_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_BINARY_RELIABILITY_DECILES.csv")
    df_deciles.to_csv(deciles_csv_path, index=False)
    
    # Save Complete Out-Of-Fold Predictions CSV
    df_oof = pd.DataFrame(all_oof_prediction_rows)
    oof_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_PREDICTIONS_OUT_OF_FOLD.csv")
    df_oof.to_csv(oof_csv_path, index=False)
    
    print(f"\n[M5.5-B.4.3.7] Validation successfully completed in {time.time() - start_time:.2f}s")
    print(f"Saved: {isolation_path}")
    print(f"Saved: {comparison_csv_path}")
    print(f"Saved: {paired_csv_path}")
    print(f"Saved: {subgroups_csv_path}")
    print(f"Saved: {cal_csv_path}")
    print(f"Saved: {cal_fold_csv_path}")
    print(f"Saved: {deciles_csv_path}")
    print(f"Saved: {oof_csv_path} ({len(df_oof)} rows)")
    
    # Generate Player Fairness Diagnostics (LPMO decontaminated)
    print("\nComputing matched bowler fairness diagnostics (LPMO decontaminated)...")
    fairness_res = run_player_match_fairness_analysis_b437(data_path=data_path)
    fairness_csv_path = os.path.join(output_dir, "M5_5B_4_3_7_PLAYER_FAIRNESS_DIAGNOSTICS.csv")
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
    res = run_full_validation_b4_3_7(n_boot=60)
    print("\nModel Comparison Aggregate Summary:")
    print(res["model_comparison"].groupby(["domain", "metric", "model"])[["score", "score_cluster_se"]].mean())
