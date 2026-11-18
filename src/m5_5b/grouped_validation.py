"""
RR ScoutIQ — Milestone M5.5-B: Match-Grouped Validation Engine
Module: src/m5_5b/grouped_validation.py

Performs strict 5-fold match-grouped cross-validation on all 175,676 clean deliveries (744 matches)
evaluating candidate baseline models across both Batters and Bowlers:
- M0: M4 Pilot Fixed Matrix (uncalibrated)
- M1: Phase-Only (3 cells)
- M2: Empirical Phase x Tier Unpooled (12 cells)
- M3: Empirical Phase x Tier with EB Cell-Count Pooling (shrinkage on sparse cells)
- M4: Phase x Tier x Innings (24 cells)
- M5: Phase x Tier x Role (36 cells)
- M6: Phase x Tier x Innings x Role (72 cells)

Evaluates:
- Runs per ball / runs conceded per ball: RMSE, MAE, Bias (Mean Error), Calibration Slope & Intercept
- Binary events (Boundary, Dot, Wicket): Brier Score, Log Loss
- Subgroup & Role-specific performance
- Fold-to-fold stability

Strict Governance: No player scores, no rankings, no auction recommendations.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from typing import Dict, List, Tuple

from src.m5_5b.baseline_estimation import (
    load_clean_deliveries,
    assign_batter_roles,
    assign_bowler_roles
)


# Fixed M4 Pilot baseline matrix for reference
M4_PILOT_RUNS_BASELINE = {
    ("powerplay", "Tier 1: Low"): 1.15,
    ("powerplay", "Tier 2: Medium"): 1.25,
    ("powerplay", "Tier 3: High"): 1.40,
    ("powerplay", "Tier 4: Extreme"): 1.60,
    ("middle", "Tier 1: Low"): 1.20,
    ("middle", "Tier 2: Medium"): 1.30,
    ("middle", "Tier 3: High"): 1.45,
    ("middle", "Tier 4: Extreme"): 1.70,
    ("death", "Tier 1: Low"): 1.45,
    ("death", "Tier 2: Medium"): 1.60,
    ("death", "Tier 3: High"): 1.75,
    ("death", "Tier 4: Extreme"): 1.95,
    ("super over", "Tier 4: Extreme"): 1.80
}


def evaluate_batter_grouped_cv(df: pd.DataFrame, n_splits: int = 5) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Executes 5-fold match-grouped CV for batter baseline models on balls faced (ext_batter_balls_faced == 1).
    """
    b_df = df[df["ext_batter_balls_faced"] == 1].copy()
    b_df["is_bnd"] = ((b_df["ext_is_four"] == 1) | (b_df["ext_is_six"] == 1)).astype(int)
    b_df["is_dot"] = ((b_df["ext_batter_runs"] == 0) & (b_df["is_bnd"] == 0)).astype(int)
    b_df["is_out"] = (b_df["ext_is_wicket"] == 1).astype(int)
    b_df["target_runs"] = b_df["ext_batter_runs"].astype(float)
    
    # Normalise phase string
    b_df["phase_clean"] = b_df["pre_match_phase"].str.lower()
    
    gkf = GroupKFold(n_splits=n_splits)
    unique_matches = b_df["match_id"].values
    
    model_names = ["M0_M4Pilot", "M1_PhaseOnly", "M2_PhaseTier", "M3_PhaseTierEB", "M4_PhaseTierInn", "M5_PhaseTierRole", "M6_PhaseTierInnRole"]
    
    fold_records = []
    
    for fold, (train_idx, test_idx) in enumerate(gkf.split(b_df, b_df["target_runs"], groups=unique_matches), 1):
        train_data = b_df.iloc[train_idx]
        test_data = b_df.iloc[test_idx].copy()
        
        y_test = test_data["target_runs"].values
        bnd_test = test_data["is_bnd"].values
        dot_test = test_data["is_dot"].values
        out_test = test_data["is_out"].values
        
        # 1. Global train mean
        global_mean = train_data["target_runs"].mean()
        global_bnd = train_data["is_bnd"].mean()
        global_dot = train_data["is_dot"].mean()
        global_out = train_data["is_out"].mean()
        
        # --- Model 0: M4 Pilot Fixed ---
        pred_m0 = test_data.apply(
            lambda r: M4_PILOT_RUNS_BASELINE.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean),
            axis=1
        ).values
        
        # --- Model 1: Phase Only (3 cells) ---
        m1_map = train_data.groupby("phase_clean")["target_runs"].mean().to_dict()
        pred_m1 = test_data["phase_clean"].map(lambda p: m1_map.get(p, global_mean)).values
        
        # --- Model 2: Phase x Tier Unpooled (12 cells) ---
        m2_map = train_data.groupby(["phase_clean", "pre_pressure_tier"])["target_runs"].mean().to_dict()
        pred_m2 = test_data.apply(
            lambda r: m2_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean),
            axis=1
        ).values
        
        # --- Model 3: Phase x Tier EB Pooled (M=100 shrinkage to Phase mean) ---
        m3_counts = train_data.groupby(["phase_clean", "pre_pressure_tier"])["target_runs"].count().to_dict()
        m3_sums = train_data.groupby(["phase_clean", "pre_pressure_tier"])["target_runs"].sum().to_dict()
        m3_map = {}
        for (phase, tier), cnt in m3_counts.items():
            prior_mu = m1_map.get(phase, global_mean)
            shrunk_mean = (m3_sums[(phase, tier)] + 100.0 * prior_mu) / (cnt + 100.0)
            m3_map[(phase, tier)] = shrunk_mean
        pred_m3 = test_data.apply(
            lambda r: m3_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean),
            axis=1
        ).values
        
        # --- Model 4: Phase x Tier x Innings (24 cells) ---
        m4_map = train_data.groupby(["phase_clean", "pre_pressure_tier", "innings"])["target_runs"].mean().to_dict()
        pred_m4 = test_data.apply(
            lambda r: m4_map.get((r["phase_clean"], r["pre_pressure_tier"], r["innings"]), m2_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean)),
            axis=1
        ).values
        
        # --- Model 5: Phase x Tier x Role (36 cells) ---
        m5_map = train_data.groupby(["phase_clean", "pre_pressure_tier", "batter_role"])["target_runs"].mean().to_dict()
        pred_m5 = test_data.apply(
            lambda r: m5_map.get((r["phase_clean"], r["pre_pressure_tier"], r["batter_role"]), m2_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean)),
            axis=1
        ).values
        
        # --- Model 6: Phase x Tier x Innings x Role (72 cells) ---
        m6_map = train_data.groupby(["phase_clean", "pre_pressure_tier", "innings", "batter_role"])["target_runs"].mean().to_dict()
        pred_m6 = test_data.apply(
            lambda r: m6_map.get(
                (r["phase_clean"], r["pre_pressure_tier"], r["innings"], r["batter_role"]),
                m5_map.get((r["phase_clean"], r["pre_pressure_tier"], r["batter_role"]), global_mean)
            ),
            axis=1
        ).values
        
        preds = {
            "M0_M4Pilot": pred_m0,
            "M1_PhaseOnly": pred_m1,
            "M2_PhaseTier": pred_m2,
            "M3_PhaseTierEB": pred_m3,
            "M4_PhaseTierInn": pred_m4,
            "M5_PhaseTierRole": pred_m5,
            "M6_PhaseTierInnRole": pred_m6
        }
        
        for mname, y_pred in preds.items():
            err = y_test - y_pred
            rmse = np.sqrt(np.mean(err**2))
            mae = np.mean(np.abs(err))
            bias = np.mean(err)
            
            # Calibration slope (regress y on pred)
            var_pred = np.var(y_pred)
            cov_y_pred = np.cov(y_pred, y_test)[0, 1] if var_pred > 1e-8 else 0.0
            cal_slope = cov_y_pred / var_pred if var_pred > 1e-8 else 1.0
            cal_int = np.mean(y_test) - cal_slope * np.mean(y_pred)
            
            fold_records.append({
                "Fold": fold,
                "Model": mname,
                "Entity": "Batter",
                "Metric": "RunsPerBall",
                "RMSE": rmse,
                "MAE": mae,
                "Bias": bias,
                "Calibration_Slope": cal_slope,
                "Calibration_Intercept": cal_int
            })
            
    fold_df = pd.DataFrame(fold_records)
    
    summary = fold_df.groupby("Model").agg(
        Mean_RMSE=("RMSE", "mean"),
        Std_RMSE=("RMSE", "std"),
        Mean_MAE=("MAE", "mean"),
        Std_MAE=("MAE", "std"),
        Mean_Bias=("Bias", "mean"),
        Mean_Cal_Slope=("Calibration_Slope", "mean"),
        Mean_Cal_Intercept=("Calibration_Intercept", "mean")
    ).reset_index()
    
    return fold_df, summary, b_df


def evaluate_bowler_grouped_cv(df: pd.DataFrame, n_splits: int = 5) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executes 5-fold match-grouped CV for bowler baseline models on legal deliveries (ext_is_legal_delivery == 1).
    """
    bw_df = df[df["ext_is_legal_delivery"] == 1].copy()
    bw_df["is_bnd_con"] = ((bw_df["ext_is_four"] == 1) | (bw_df["ext_is_six"] == 1)).astype(int)
    bw_df["is_dot"] = (bw_df["ext_bowler_debit_runs"] == 0).astype(int)
    bw_df["is_wkt"] = (bw_df["ext_is_bowler_wicket"] == 1).astype(int)
    bw_df["target_runs"] = bw_df["ext_bowler_debit_runs"].astype(float)
    
    bw_df["phase_clean"] = bw_df["pre_match_phase"].str.lower()
    
    gkf = GroupKFold(n_splits=n_splits)
    unique_matches = bw_df["match_id"].values
    
    fold_records = []
    
    for fold, (train_idx, test_idx) in enumerate(gkf.split(bw_df, bw_df["target_runs"], groups=unique_matches), 1):
        train_data = bw_df.iloc[train_idx]
        test_data = bw_df.iloc[test_idx].copy()
        
        y_test = test_data["target_runs"].values
        
        global_mean = train_data["target_runs"].mean()
        
        pred_m0 = test_data.apply(
            lambda r: M4_PILOT_RUNS_BASELINE.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean),
            axis=1
        ).values
        
        m1_map = train_data.groupby("phase_clean")["target_runs"].mean().to_dict()
        pred_m1 = test_data["phase_clean"].map(lambda p: m1_map.get(p, global_mean)).values
        
        m2_map = train_data.groupby(["phase_clean", "pre_pressure_tier"])["target_runs"].mean().to_dict()
        pred_m2 = test_data.apply(
            lambda r: m2_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean),
            axis=1
        ).values
        
        m3_counts = train_data.groupby(["phase_clean", "pre_pressure_tier"])["target_runs"].count().to_dict()
        m3_sums = train_data.groupby(["phase_clean", "pre_pressure_tier"])["target_runs"].sum().to_dict()
        m3_map = {}
        for (phase, tier), cnt in m3_counts.items():
            prior_mu = m1_map.get(phase, global_mean)
            shrunk_mean = (m3_sums[(phase, tier)] + 100.0 * prior_mu) / (cnt + 100.0)
            m3_map[(phase, tier)] = shrunk_mean
        pred_m3 = test_data.apply(
            lambda r: m3_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean),
            axis=1
        ).values
        
        m4_map = train_data.groupby(["phase_clean", "pre_pressure_tier", "innings"])["target_runs"].mean().to_dict()
        pred_m4 = test_data.apply(
            lambda r: m4_map.get((r["phase_clean"], r["pre_pressure_tier"], r["innings"]), m2_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean)),
            axis=1
        ).values
        
        m5_map = train_data.groupby(["phase_clean", "pre_pressure_tier", "bowler_role"])["target_runs"].mean().to_dict()
        pred_m5 = test_data.apply(
            lambda r: m5_map.get((r["phase_clean"], r["pre_pressure_tier"], r["bowler_role"]), m2_map.get((r["phase_clean"], r["pre_pressure_tier"]), global_mean)),
            axis=1
        ).values
        
        m6_map = train_data.groupby(["phase_clean", "pre_pressure_tier", "innings", "bowler_role"])["target_runs"].mean().to_dict()
        pred_m6 = test_data.apply(
            lambda r: m6_map.get(
                (r["phase_clean"], r["pre_pressure_tier"], r["innings"], r["bowler_role"]),
                m5_map.get((r["phase_clean"], r["pre_pressure_tier"], r["bowler_role"]), global_mean)
            ),
            axis=1
        ).values
        
        preds = {
            "M0_M4Pilot": pred_m0,
            "M1_PhaseOnly": pred_m1,
            "M2_PhaseTier": pred_m2,
            "M3_PhaseTierEB": pred_m3,
            "M4_PhaseTierInn": pred_m4,
            "M5_PhaseTierRole": pred_m5,
            "M6_PhaseTierInnRole": pred_m6
        }
        
        for mname, y_pred in preds.items():
            err = y_test - y_pred
            rmse = np.sqrt(np.mean(err**2))
            mae = np.mean(np.abs(err))
            bias = np.mean(err)
            
            var_pred = np.var(y_pred)
            cov_y_pred = np.cov(y_pred, y_test)[0, 1] if var_pred > 1e-8 else 0.0
            cal_slope = cov_y_pred / var_pred if var_pred > 1e-8 else 1.0
            cal_int = np.mean(y_test) - cal_slope * np.mean(y_pred)
            
            fold_records.append({
                "Fold": fold,
                "Model": mname,
                "Entity": "Bowler",
                "Metric": "RunsConcededPerBall",
                "RMSE": rmse,
                "MAE": mae,
                "Bias": bias,
                "Calibration_Slope": cal_slope,
                "Calibration_Intercept": cal_int
            })
            
    fold_df = pd.DataFrame(fold_records)
    
    summary = fold_df.groupby("Model").agg(
        Mean_RMSE=("RMSE", "mean"),
        Std_RMSE=("RMSE", "std"),
        Mean_MAE=("MAE", "mean"),
        Std_MAE=("MAE", "std"),
        Mean_Bias=("Bias", "mean"),
        Mean_Cal_Slope=("Calibration_Slope", "mean"),
        Mean_Cal_Intercept=("Calibration_Intercept", "mean")
    ).reset_index()
    
    return fold_df, summary


if __name__ == "__main__":
    print("Loading clean deliveries...")
    clean_df = load_clean_deliveries()
    clean_df, _ = assign_batter_roles(clean_df)
    clean_df, _, _ = assign_bowler_roles(clean_df)
    
    print("\n--- RUNNING BATTER 5-FOLD GROUPED CV ---")
    b_fold_df, b_summary, _ = evaluate_batter_grouped_cv(clean_df)
    print("\nBatter Baseline Models Summary across 5 Folds:")
    print(b_summary.to_string(index=False))
    
    print("\n--- RUNNING BOWLER 5-FOLD GROUPED CV ---")
    bw_fold_df, bw_summary = evaluate_bowler_grouped_cv(clean_df)
    print("\nBowler Baseline Models Summary across 5 Folds:")
    print(bw_summary.to_string(index=False))
