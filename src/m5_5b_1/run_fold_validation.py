"""
RR ScoutIQ — Milestone M5.5-B.1: Leak-Free 5-Fold Cross-Validation Pipeline
Module: src/m5_5b_1/run_fold_validation.py

Executes leak-free 5-fold match-grouped cross-validation across all 175,676 clean deliveries (744 matches):
1. Training-only role derivation
2. Training-only Empirical Bayes MML prior fitting
3. Evaluation of continuous and binary outcomes
4. Produces M5_5B_1_FOLD_RESULTS.csv, M5_5B_1_PRIOR_FIT_DIAGNOSTICS.csv, M5_5B_1_ROLE_ASSIGNMENT_STABILITY.csv
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from typing import Dict, List, Tuple, Any

from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_1.remediation_engine import (
    derive_training_batter_roles,
    derive_training_bowler_roles,
    apply_fold_roles,
    fit_beta_binomial_safeguarded,
    fit_normal_normal_safeguarded,
    compute_binary_validation_metrics,
    compute_reliability_table
)


def run_remediated_cross_validation(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_1",
    n_splits: int = 5
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Executes leak-free 5-fold validation pipeline with all M5.5-B.1 safeguards.
    """
    os.makedirs(output_dir, exist_ok=True)
    print("=" * 80)
    print("RR ScoutIQ — Milestone M5.5-B.1 Leak-Free Validation Engine")
    print("=" * 80)
    
    clean_df = load_clean_deliveries(data_path)
    clean_df["phase_clean"] = clean_df["pre_match_phase"].str.lower()
    
    # 1. Setup Match-Grouped Splitting
    gkf = GroupKFold(n_splits=n_splits)
    unique_matches = clean_df["match_id"].values
    
    fold_metric_records = []
    prior_fit_records = []
    role_stability_records = []
    coverage_audit_records = []
    
    # Pre-derive full-dataset roles for stability baseline comparison
    full_b_roles, _ = derive_training_batter_roles(clean_df)
    full_bw_roles, _ = derive_training_bowler_roles(clean_df)
    
    print(f"\nTotal Clean Matches: {clean_df['match_id'].nunique()}")
    print(f"Total Clean Deliveries: {len(clean_df):,}")
    
    for fold, (train_idx, val_idx) in enumerate(gkf.split(clean_df, clean_df["runs"], groups=unique_matches), 1):
        print(f"\n>>> Running Fold {fold} / {n_splits}...")
        train_df = clean_df.iloc[train_idx].copy()
        val_df = clean_df.iloc[val_idx].copy()
        
        # Verify zero match leakage
        train_matches = set(train_df["match_id"].unique())
        val_matches = set(val_df["match_id"].unique())
        match_intersection = train_matches.intersection(val_matches)
        if match_intersection:
            raise ValueError(f"CRITICAL LEAKAGE: Fold {fold} has {len(match_intersection)} overlapping matches!")
            
        print(f"  Train matches: {len(train_matches)}, Val matches: {len(val_matches)} (Overlap: {len(match_intersection)})")
        print(f"  Train deliveries: {len(train_df):,}, Val deliveries: {len(val_df):,}")
        
        # ----------------------------------------------------------------------
        # REMEDIATION A: Training-Only Role Derivation
        # ----------------------------------------------------------------------
        b_role_map, b_role_audit = derive_training_batter_roles(train_df)
        bw_role_map, bw_role_audit = derive_training_bowler_roles(train_df)
        
        # Apply roles to validation set
        val_df, cov_rep = apply_fold_roles(val_df, b_role_map, bw_role_map)
        train_df, _ = apply_fold_roles(train_df, b_role_map, bw_role_map)
        
        cov_rep["fold"] = fold
        coverage_audit_records.append(cov_rep)
        
        print(f"  Batter training coverage: {len(b_role_map)} batters. Val fallback rate: {cov_rep['batter_fallback_rate']*100:.2f}%")
        print(f"  Bowler training coverage: {len(bw_role_map)} bowlers. Val fallback rate: {cov_rep['bowler_fallback_rate']*100:.2f}%")
        
        # Record role stability for this fold
        for sid, f_role in b_role_map.items():
            full_role = full_b_roles.get(sid, "Unknown")
            role_stability_records.append({
                "Player_ID": sid,
                "Entity": "Batter",
                "Fold": fold,
                "Fold_Role": f_role,
                "Full_Dataset_Role": full_role,
                "Role_Matches_Full": (f_role == full_role)
            })
        for bid, f_role in bw_role_map.items():
            full_role = full_bw_roles.get(bid, "Unknown")
            role_stability_records.append({
                "Player_ID": bid,
                "Entity": "Bowler",
                "Fold": fold,
                "Fold_Role": f_role,
                "Full_Dataset_Role": full_role,
                "Role_Matches_Full": (f_role == full_role)
            })

        # ----------------------------------------------------------------------
        # REMEDIATION B & D: Training-Only Empirical Bayes MML Prior Fitting
        # ----------------------------------------------------------------------
        # Batters: balls faced
        tr_b = train_df[train_df["ext_batter_balls_faced"] == 1].copy()
        tr_b["is_bnd"] = ((tr_b["ext_is_four"] == 1) | (tr_b["ext_is_six"] == 1)).astype(int)
        tr_b["is_dot"] = ((tr_b["ext_batter_runs"] == 0) & (tr_b["is_bnd"] == 0)).astype(int)
        tr_b["is_out"] = (tr_b["ext_is_wicket"] == 1).astype(int)
        tr_b["runs"] = tr_b["ext_batter_runs"].astype(float)
        
        # Filter eligible batters on training fold (>= 100 balls in training)
        b_totals = tr_b.groupby("striker_id")["runs"].count()
        elig_b_ids = b_totals[b_totals >= 100].index
        p_agg_b = tr_b[tr_b["striker_id"].isin(elig_b_ids)].groupby("striker_id").agg(
            n=("runs", "count"),
            bnds=("is_bnd", "sum"),
            dots=("is_dot", "sum"),
            outs=("is_out", "sum"),
            runs_mean=("runs", "mean"),
            runs_sd=("runs", lambda s: s.std() if len(s) > 1 else 0.0)
        ).reset_index()
        
        # Fit Batter Priors on Train
        fit_b_bnd = fit_beta_binomial_safeguarded(p_agg_b["bnds"].values, p_agg_b["n"].values, "Batter", "Boundary %", "Global", fold)
        fit_b_dot = fit_beta_binomial_safeguarded(p_agg_b["dots"].values, p_agg_b["n"].values, "Batter", "Dot %", "Global", fold)
        fit_b_out = fit_beta_binomial_safeguarded(p_agg_b["outs"].values, p_agg_b["n"].values, "Batter", "Dismissal %", "Global", fold)
        fit_b_runs = fit_normal_normal_safeguarded(p_agg_b["runs_mean"].values, p_agg_b["n"].values, p_agg_b["runs_sd"].values, "Batter", "RunsPerBall", "Global", fold)
        
        prior_fit_records.extend([fit_b_bnd, fit_b_dot, fit_b_out, fit_b_runs])
        
        # Bowlers: legal deliveries
        tr_bw = train_df[train_df["ext_is_legal_delivery"] == 1].copy()
        tr_bw["is_bnd_con"] = ((tr_bw["ext_is_four"] == 1) | (tr_bw["ext_is_six"] == 1)).astype(int)
        tr_bw["is_dot"] = (tr_bw["ext_bowler_debit_runs"] == 0).astype(int)
        tr_bw["is_wkt"] = (tr_bw["ext_is_bowler_wicket"] == 1).astype(int)
        tr_bw["runs_conceded"] = tr_bw["ext_bowler_debit_runs"].astype(float)
        
        bw_totals = tr_bw.groupby("bowler_id")["runs_conceded"].count()
        elig_bw_ids = bw_totals[bw_totals >= 120].index
        p_agg_bw = tr_bw[tr_bw["bowler_id"].isin(elig_bw_ids)].groupby("bowler_id").agg(
            n=("runs_conceded", "count"),
            bnds=("is_bnd_con", "sum"),
            dots=("is_dot", "sum"),
            wkts=("is_wkt", "sum"),
            runs_mean=("runs_conceded", "mean"),
            runs_sd=("runs_conceded", lambda s: s.std() if len(s) > 1 else 0.0)
        ).reset_index()
        
        # Fit Bowler Priors on Train
        fit_bw_bnd = fit_beta_binomial_safeguarded(p_agg_bw["bnds"].values, p_agg_bw["n"].values, "Bowler", "BoundaryConcession %", "Global", fold)
        fit_bw_dot = fit_beta_binomial_safeguarded(p_agg_bw["dots"].values, p_agg_bw["n"].values, "Bowler", "Dot %", "Global", fold)
        fit_bw_wkt = fit_beta_binomial_safeguarded(p_agg_bw["wkts"].values, p_agg_bw["n"].values, "Bowler", "Wicket %", "Global", fold)
        fit_bw_runs = fit_normal_normal_safeguarded(p_agg_bw["runs_mean"].values, p_agg_bw["n"].values, p_agg_bw["runs_sd"].values, "Bowler", "RunsConcededPerBall", "Global", fold)
        
        prior_fit_records.extend([fit_bw_bnd, fit_bw_dot, fit_bw_wkt, fit_bw_runs])
        
        print(f"  Fitted MML Priors: Batter M0(bnd)={fit_b_bnd['Effective_M_Prior']:.1f}, M0(out)={fit_b_out['Effective_M_Prior']:.1f}; Bowler M0(wkt)={fit_bw_wkt['Effective_M_Prior']:.1f}")

        # ----------------------------------------------------------------------
        # REMEDIATION B, C & F: Candidate Baseline Models Evaluation on Validation Set
        # ----------------------------------------------------------------------
        # Target variables in Validation
        val_b = val_df[val_df["ext_batter_balls_faced"] == 1].copy()
        val_b["is_bnd"] = ((val_b["ext_is_four"] == 1) | (val_b["ext_is_six"] == 1)).astype(int)
        val_b["is_dot"] = ((val_b["ext_batter_runs"] == 0) & (val_b["is_bnd"] == 0)).astype(int)
        val_b["is_out"] = (val_b["ext_is_wicket"] == 1).astype(int)
        val_b["runs"] = val_b["ext_batter_runs"].astype(float)
        
        val_bw = val_df[val_df["ext_is_legal_delivery"] == 1].copy()
        val_bw["is_bnd_con"] = ((val_bw["ext_is_four"] == 1) | (val_bw["ext_is_six"] == 1)).astype(int)
        val_bw["is_dot"] = (val_bw["ext_bowler_debit_runs"] == 0).astype(int)
        val_bw["is_wkt"] = (val_bw["ext_is_bowler_wicket"] == 1).astype(int)
        val_bw["runs_conceded"] = val_bw["ext_bowler_debit_runs"].astype(float)
        
        # 1. Continuous Runs Evaluation (Batters & Bowlers)
        # Learn training cell statistics
        # Batter mappings
        b_glob_mean = float(tr_b["runs"].mean())
        b_phase_map = tr_b.groupby("phase_clean")["runs"].mean().to_dict()
        b_pt_mean = tr_b.groupby(["phase_clean", "pre_pressure_tier"])["runs"].mean().to_dict()
        b_pt_cnt = tr_b.groupby(["phase_clean", "pre_pressure_tier"])["runs"].count().to_dict()
        b_pt_sum = tr_b.groupby(["phase_clean", "pre_pressure_tier"])["runs"].sum().to_dict()
        b_ptr_map = tr_b.groupby(["phase_clean", "pre_pressure_tier", "batter_role"])["runs"].mean().to_dict()
        b_ptri_map = tr_b.groupby(["phase_clean", "pre_pressure_tier", "innings", "batter_role"])["runs"].mean().to_dict()
        
        # M3 Heuristic (M=100) vs M4 Calibrated EB (M=M0_fit)
        b_M_calibrated = fit_b_runs["Effective_M_Prior"]
        b_m3_map = {}
        b_m4_map = {}
        for pt, cnt in b_pt_cnt.items():
            phase = pt[0]
            p_prior = b_phase_map.get(phase, b_glob_mean)
            s = b_pt_sum[pt]
            b_m3_map[pt] = (s + 100.0 * p_prior) / (cnt + 100.0)
            b_m4_map[pt] = (s + b_M_calibrated * p_prior) / (cnt + b_M_calibrated)
            
        # Predictions for Batters Runs
        y_b_true = val_b["runs"].values
        preds_b_runs = {
            "M1_PhaseOnly": val_b["phase_clean"].map(lambda p: b_phase_map.get(p, b_glob_mean)).values,
            "M2_PhaseTier_Unpooled": val_b.apply(lambda r: b_pt_mean.get((r["phase_clean"], r["pre_pressure_tier"]), b_glob_mean), axis=1).values,
            "M3_Heuristic_M100": val_b.apply(lambda r: b_m3_map.get((r["phase_clean"], r["pre_pressure_tier"]), b_glob_mean), axis=1).values,
            "M4_CalibratedEB": val_b.apply(lambda r: b_m4_map.get((r["phase_clean"], r["pre_pressure_tier"]), b_glob_mean), axis=1).values,
            "M5_RoleAware": val_b.apply(lambda r: b_ptr_map.get((r["phase_clean"], r["pre_pressure_tier"], r["batter_role"]), b_pt_mean.get((r["phase_clean"], r["pre_pressure_tier"]), b_glob_mean)), axis=1).values,
            "M6_FullInteraction": val_b.apply(lambda r: b_ptri_map.get((r["phase_clean"], r["pre_pressure_tier"], r["innings"], r["batter_role"]), b_ptr_map.get((r["phase_clean"], r["pre_pressure_tier"], r["batter_role"]), b_glob_mean)), axis=1).values,
        }
        
        for mname, pred_vals in preds_b_runs.items():
            err = y_b_true - pred_vals
            rmse = float(np.sqrt(np.mean(err ** 2)))
            mae = float(np.mean(np.abs(err)))
            bias = float(np.mean(err))
            var_p = float(np.var(pred_vals))
            cal_slope = float(np.cov(pred_vals, y_b_true)[0, 1] / var_p) if var_p > 1e-8 else 1.0
            cal_int = float(np.mean(y_b_true) - cal_slope * np.mean(pred_vals))
            fold_metric_records.append({
                "Fold": fold,
                "Entity": "Batter",
                "Metric_Category": "Continuous",
                "Metric_Name": "RunsPerBall",
                "Model_Name": mname,
                "RMSE": rmse,
                "MAE": mae,
                "Mean_Bias": bias,
                "Calibration_Slope": cal_slope,
                "Calibration_Intercept": cal_int,
                "Brier_Score": np.nan,
                "Log_Loss": np.nan,
                "N_Deliveries": len(y_b_true)
            })
            
        # 2. Bowler Runs Conceded Evaluation
        bw_glob_mean = float(tr_bw["runs_conceded"].mean())
        bw_phase_map = tr_bw.groupby("phase_clean")["runs_conceded"].mean().to_dict()
        bw_pt_mean = tr_bw.groupby(["phase_clean", "pre_pressure_tier"])["runs_conceded"].mean().to_dict()
        bw_pt_cnt = tr_bw.groupby(["phase_clean", "pre_pressure_tier"])["runs_conceded"].count().to_dict()
        bw_pt_sum = tr_bw.groupby(["phase_clean", "pre_pressure_tier"])["runs_conceded"].sum().to_dict()
        bw_ptr_map = tr_bw.groupby(["phase_clean", "pre_pressure_tier", "bowler_role"])["runs_conceded"].mean().to_dict()
        bw_ptri_map = tr_bw.groupby(["phase_clean", "pre_pressure_tier", "innings", "bowler_role"])["runs_conceded"].mean().to_dict()
        
        bw_M_calibrated = fit_bw_runs["Effective_M_Prior"]
        bw_m3_map = {}
        bw_m4_map = {}
        for pt, cnt in bw_pt_cnt.items():
            phase = pt[0]
            p_prior = bw_phase_map.get(phase, bw_glob_mean)
            s = bw_pt_sum[pt]
            bw_m3_map[pt] = (s + 100.0 * p_prior) / (cnt + 100.0)
            bw_m4_map[pt] = (s + bw_M_calibrated * p_prior) / (cnt + bw_M_calibrated)
            
        y_bw_true = val_bw["runs_conceded"].values
        preds_bw_runs = {
            "M1_PhaseOnly": val_bw["phase_clean"].map(lambda p: bw_phase_map.get(p, bw_glob_mean)).values,
            "M2_PhaseTier_Unpooled": val_bw.apply(lambda r: bw_pt_mean.get((r["phase_clean"], r["pre_pressure_tier"]), bw_glob_mean), axis=1).values,
            "M3_Heuristic_M100": val_bw.apply(lambda r: bw_m3_map.get((r["phase_clean"], r["pre_pressure_tier"]), bw_glob_mean), axis=1).values,
            "M4_CalibratedEB": val_bw.apply(lambda r: bw_m4_map.get((r["phase_clean"], r["pre_pressure_tier"]), bw_glob_mean), axis=1).values,
            "M5_RoleAware": val_bw.apply(lambda r: bw_ptr_map.get((r["phase_clean"], r["pre_pressure_tier"], r["bowler_role"]), bw_pt_mean.get((r["phase_clean"], r["pre_pressure_tier"]), bw_glob_mean)), axis=1).values,
            "M6_FullInteraction": val_bw.apply(lambda r: bw_ptri_map.get((r["phase_clean"], r["pre_pressure_tier"], r["innings"], r["bowler_role"]), bw_ptr_map.get((r["phase_clean"], r["pre_pressure_tier"], r["bowler_role"]), bw_glob_mean)), axis=1).values,
        }
        
        for mname, pred_vals in preds_bw_runs.items():
            err = y_bw_true - pred_vals
            rmse = float(np.sqrt(np.mean(err ** 2)))
            mae = float(np.mean(np.abs(err)))
            bias = float(np.mean(err))
            var_p = float(np.var(pred_vals))
            cal_slope = float(np.cov(pred_vals, y_bw_true)[0, 1] / var_p) if var_p > 1e-8 else 1.0
            cal_int = float(np.mean(y_bw_true) - cal_slope * np.mean(pred_vals))
            fold_metric_records.append({
                "Fold": fold,
                "Entity": "Bowler",
                "Metric_Category": "Continuous",
                "Metric_Name": "RunsConcededPerBall",
                "Model_Name": mname,
                "RMSE": rmse,
                "MAE": mae,
                "Mean_Bias": bias,
                "Calibration_Slope": cal_slope,
                "Calibration_Intercept": cal_int,
                "Brier_Score": np.nan,
                "Log_Loss": np.nan,
                "N_Deliveries": len(y_bw_true)
            })

        # ----------------------------------------------------------------------
        # REMEDIATION C: Binary Outcome Validation
        # ----------------------------------------------------------------------
        # Batter Binary: Boundary, Dot, Dismissal
        binary_targets_b = [
            ("Boundary", "is_bnd", fit_b_bnd["Effective_M_Prior"]),
            ("Dot", "is_dot", fit_b_dot["Effective_M_Prior"]),
            ("Dismissal", "is_out", fit_b_out["Effective_M_Prior"])
        ]
        
        for b_name, col_name, M_cal in binary_targets_b:
            y_bin = val_b[col_name].values
            glob_prob = float(tr_b[col_name].mean())
            phase_prob = tr_b.groupby("phase_clean")[col_name].mean().to_dict()
            pt_prob = tr_b.groupby(["phase_clean", "pre_pressure_tier"])[col_name].mean().to_dict()
            pt_cnt = tr_b.groupby(["phase_clean", "pre_pressure_tier"])[col_name].count().to_dict()
            pt_sum = tr_b.groupby(["phase_clean", "pre_pressure_tier"])[col_name].sum().to_dict()
            ptr_prob = tr_b.groupby(["phase_clean", "pre_pressure_tier", "batter_role"])[col_name].mean().to_dict()
            
            m3_bin_map = {}
            m4_bin_map = {}
            for pt, cnt in pt_cnt.items():
                p_prior = phase_prob.get(pt[0], glob_prob)
                s = pt_sum[pt]
                m3_bin_map[pt] = (s + 100.0 * p_prior) / (cnt + 100.0)
                m4_bin_map[pt] = (s + M_cal * p_prior) / (cnt + M_cal)
                
            pred_binary = {
                "M1_PhaseOnly": val_b["phase_clean"].map(lambda p: phase_prob.get(p, glob_prob)).values,
                "M2_PhaseTier_Unpooled": val_b.apply(lambda r: pt_prob.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob), axis=1).values,
                "M3_Heuristic_M100": val_b.apply(lambda r: m3_bin_map.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob), axis=1).values,
                "M4_CalibratedEB": val_b.apply(lambda r: m4_bin_map.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob), axis=1).values,
                "M5_RoleAware": val_b.apply(lambda r: ptr_prob.get((r["phase_clean"], r["pre_pressure_tier"], r["batter_role"]), pt_prob.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob)), axis=1).values,
            }
            
            for mname, p_vals in pred_binary.items():
                met = compute_binary_validation_metrics(y_bin, p_vals)
                fold_metric_records.append({
                    "Fold": fold,
                    "Entity": "Batter",
                    "Metric_Category": "Binary",
                    "Metric_Name": b_name,
                    "Model_Name": mname,
                    "RMSE": np.nan,
                    "MAE": np.nan,
                    "Mean_Bias": met["Mean_Bias"],
                    "Calibration_Slope": met["Calibration_Slope"],
                    "Calibration_Intercept": met["Calibration_Intercept"],
                    "Brier_Score": met["Brier_Score"],
                    "Log_Loss": met["Log_Loss"],
                    "N_Deliveries": len(y_bin)
                })

        # Bowler Binary: Boundary Concession, Dot, Wicket
        binary_targets_bw = [
            ("BoundaryConcession", "is_bnd_con", fit_bw_bnd["Effective_M_Prior"]),
            ("Dot", "is_dot", fit_bw_dot["Effective_M_Prior"]),
            ("Wicket", "is_wkt", fit_bw_wkt["Effective_M_Prior"])
        ]
        
        for bw_name, col_name, M_cal in binary_targets_bw:
            y_bin = val_bw[col_name].values
            glob_prob = float(tr_bw[col_name].mean())
            phase_prob = tr_bw.groupby("phase_clean")[col_name].mean().to_dict()
            pt_prob = tr_bw.groupby(["phase_clean", "pre_pressure_tier"])[col_name].mean().to_dict()
            pt_cnt = tr_bw.groupby(["phase_clean", "pre_pressure_tier"])[col_name].count().to_dict()
            pt_sum = tr_bw.groupby(["phase_clean", "pre_pressure_tier"])[col_name].sum().to_dict()
            ptr_prob = tr_bw.groupby(["phase_clean", "pre_pressure_tier", "bowler_role"])[col_name].mean().to_dict()
            
            m3_bin_map = {}
            m4_bin_map = {}
            for pt, cnt in pt_cnt.items():
                p_prior = phase_prob.get(pt[0], glob_prob)
                s = pt_sum[pt]
                m3_bin_map[pt] = (s + 100.0 * p_prior) / (cnt + 100.0)
                m4_bin_map[pt] = (s + M_cal * p_prior) / (cnt + M_cal)
                
            pred_binary = {
                "M1_PhaseOnly": val_bw["phase_clean"].map(lambda p: phase_prob.get(p, glob_prob)).values,
                "M2_PhaseTier_Unpooled": val_bw.apply(lambda r: pt_prob.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob), axis=1).values,
                "M3_Heuristic_M100": val_bw.apply(lambda r: m3_bin_map.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob), axis=1).values,
                "M4_CalibratedEB": val_bw.apply(lambda r: m4_bin_map.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob), axis=1).values,
                "M5_RoleAware": val_bw.apply(lambda r: ptr_prob.get((r["phase_clean"], r["pre_pressure_tier"], r["bowler_role"]), pt_prob.get((r["phase_clean"], r["pre_pressure_tier"]), glob_prob)), axis=1).values,
            }
            
            for mname, p_vals in pred_binary.items():
                met = compute_binary_validation_metrics(y_bin, p_vals)
                fold_metric_records.append({
                    "Fold": fold,
                    "Entity": "Bowler",
                    "Metric_Category": "Binary",
                    "Metric_Name": bw_name,
                    "Model_Name": mname,
                    "RMSE": np.nan,
                    "MAE": np.nan,
                    "Mean_Bias": met["Mean_Bias"],
                    "Calibration_Slope": met["Calibration_Slope"],
                    "Calibration_Intercept": met["Calibration_Intercept"],
                    "Brier_Score": met["Brier_Score"],
                    "Log_Loss": met["Log_Loss"],
                    "N_Deliveries": len(y_bin)
                })

    # Assemble and Persist All Deliverables
    fold_results_df = pd.DataFrame(fold_metric_records)
    prior_fit_df = pd.DataFrame(prior_fit_records)
    role_stability_df = pd.DataFrame(role_stability_records)
    
    # Save CSVs in versioned audit directory and root
    fold_csv_path = os.path.join(output_dir, "M5_5B_1_FOLD_RESULTS.csv")
    prior_csv_path = os.path.join(output_dir, "M5_5B_1_PRIOR_FIT_DIAGNOSTICS.csv")
    role_csv_path = os.path.join(output_dir, "M5_5B_1_ROLE_ASSIGNMENT_STABILITY.csv")
    
    fold_results_df.to_csv(fold_csv_path, index=False)
    prior_fit_df.to_csv(prior_csv_path, index=False)
    role_stability_df.to_csv(role_csv_path, index=False)
    
    # Also mirror to root
    fold_results_df.to_csv("M5_5B_1_FOLD_RESULTS.csv", index=False)
    prior_fit_df.to_csv("M5_5B_1_PRIOR_FIT_DIAGNOSTICS.csv", index=False)
    role_stability_df.to_csv("M5_5B_1_ROLE_ASSIGNMENT_STABILITY.csv", index=False)
    
    print("\n" + "=" * 80)
    print("M5.5-B.1 REMEDIATED CROSS-VALIDATION COMPLETE")
    print(f"Saved: {fold_csv_path} ({len(fold_results_df)} evaluations)")
    print(f"Saved: {prior_csv_path} ({len(prior_fit_df)} prior fits)")
    print(f"Saved: {role_csv_path} ({len(role_stability_df)} role records)")
    print("=" * 80)
    
    return fold_results_df, prior_fit_df, role_stability_df


if __name__ == "__main__":
    run_remediated_cross_validation()
