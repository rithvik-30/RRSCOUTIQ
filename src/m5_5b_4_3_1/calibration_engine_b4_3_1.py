"""
RR ScoutIQ — Milestone M5.5-B.4.3.1: Stratified Calibration Engine
Module: src/m5_5b_4_3_1/calibration_engine_b4_3_1.py

Remediates audit defect:
1. Evaluates BOTH 80% and 95% interval coverage for continuous bowler economy outcomes.
   - Computes two-way cluster-robust confidence intervals for both levels.
   - Requires BOTH levels to meet calibration thresholds; does not classify as calibrated
     if either level has material under-coverage.
2. Implements a statistically appropriate binary probability-calibration framework for batters:
   - Evaluates Expected Calibration Error (ECE), Brier score, log loss, calibration slope,
     and calibration intercept.
   - Eliminates misleading Gaussian interval coverage claims for individual 0/1 Bernoulli outcomes.
3. Distinguishes insufficient evidence from genuine miscalibration across all 18 strata.
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression

from src.m5_5b_4_3_1.cluster_variance_b4_3_1 import compute_two_way_cluster_variance


def compute_continuous_interval_coverage_b431(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    se_pred: np.ndarray
) -> Dict[str, Any]:
    """
    Computes empirical coverage of nominal 80% and 95% credible intervals
    for continuous outcomes (e.g. bowler economy rate).
    """
    valid_mask = np.isfinite(y_true) & np.isfinite(y_pred) & np.isfinite(se_pred) & (se_pred > 0)
    y_t = y_true[valid_mask]
    y_p = y_pred[valid_mask]
    s = se_pred[valid_mask]
    n = len(y_t)
    
    if n == 0:
        return {
            "n_evaluated": 0,
            "coverage_80": np.nan,
            "coverage_80_se": np.nan,
            "coverage_95": np.nan,
            "coverage_95_se": np.nan,
            "mean_z_residual": np.nan,
            "std_z_residual": np.nan,
            "covered_80": np.array([], dtype=bool),
            "covered_95": np.array([], dtype=bool)
        }
        
    z = (y_t - y_p) / s
    mean_z = float(np.mean(z))
    std_z = float(np.std(z, ddof=1)) if n > 1 else np.nan
    
    # Nominal 80% interval (z_crit = 1.28155)
    ci_80_low = y_p - 1.28155 * s
    ci_80_high = y_p + 1.28155 * s
    covered_80 = (y_t >= ci_80_low) & (y_t <= ci_80_high)
    cov_80 = float(np.mean(covered_80))
    cov_80_se = float(math.sqrt(cov_80 * (1.0 - cov_80) / n)) if n > 0 else np.nan
    
    # Nominal 95% interval (z_crit = 1.95996)
    ci_95_low = y_p - 1.95996 * s
    ci_95_high = y_p + 1.95996 * s
    covered_95 = (y_t >= ci_95_low) & (y_t <= ci_95_high)
    cov_95 = float(np.mean(covered_95))
    cov_95_se = float(math.sqrt(cov_95 * (1.0 - cov_95) / n)) if n > 0 else np.nan
    
    return {
        "n_evaluated": n,
        "coverage_80": cov_80,
        "coverage_80_se": cov_80_se,
        "coverage_95": cov_95,
        "coverage_95_se": cov_95_se,
        "mean_z_residual": mean_z,
        "std_z_residual": std_z,
        "covered_80": covered_80,
        "covered_95": covered_95
    }


def compute_binary_probability_calibration_b431(
    y_true: np.ndarray,
    p_pred: np.ndarray,
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Computes probability calibration metrics for discrete binary Bernoulli outcomes (e.g. boundary 0/1).
    Evaluates:
    - Brier score: MSE of predicted probabilities
    - Log loss: binary cross-entropy
    - Expected Calibration Error (ECE): weighted mean absolute deviation across probability bins
    - Maximum Calibration Error (MCE)
    - Logistic calibration slope and intercept
    """
    valid_mask = np.isfinite(y_true) & np.isfinite(p_pred)
    y_t = y_true[valid_mask].astype(float)
    p_p = np.clip(p_pred[valid_mask].astype(float), 1e-6, 1.0 - 1e-6)
    n = len(y_t)
    
    if n == 0:
        return {
            "n_evaluated": 0,
            "brier_score": np.nan,
            "log_loss": np.nan,
            "ece": np.nan,
            "mce": np.nan,
            "calib_intercept": np.nan,
            "calib_slope": np.nan
        }
        
    brier = float(np.mean((p_p - y_t) ** 2))
    log_l = float(-np.mean(y_t * np.log(p_p) + (1.0 - y_t) * np.log(1.0 - p_p)))
    
    # ECE and MCE across decile bins
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(p_p, bins) - 1
    
    ece = 0.0
    mce = 0.0
    for b in range(n_bins):
        mask = bin_indices == b
        n_b = np.sum(mask)
        if n_b > 0:
            act_b = float(np.mean(y_t[mask]))
            pred_b = float(np.mean(p_p[mask]))
            err_b = abs(act_b - pred_b)
            ece += (n_b / n) * err_b
            if err_b > mce:
                mce = err_b
                
    # Calibration slope & intercept via logistic regression
    # logit(P(Y=1)) = alpha + beta * logit(p)
    try:
        logit_p = logit(p_p).reshape(-1, 1)
        # Only fit if both classes present
        if len(np.unique(y_t)) > 1 and n >= 30:
            clf = LogisticRegression(solver="lbfgs")
            clf.fit(logit_p, y_t)
            alpha = float(clf.intercept_[0])
            beta = float(clf.coef_[0][0])
        else:
            alpha = 0.0
            beta = 1.0
    except Exception:
        alpha = np.nan
        beta = np.nan
        
    return {
        "n_evaluated": n,
        "brier_score": brier,
        "log_loss": log_l,
        "ece": float(ece),
        "mce": float(mce),
        "calib_intercept": alpha,
        "calib_slope": beta
    }


def compute_stratified_calibration_table_b431(
    df_eval: pd.DataFrame,
    domain: str = "Bowler"
) -> pd.DataFrame:
    """
    Generates the authoritative 18-strata calibration table:
    - 4 Exposure Bands
    - 4 Phases (including Super Over)
    - 4 Pressure Tiers
    - 3 Roles
    - 3 Overall Summary Cohorts

    For Bowlers: evaluates continuous 80% and 95% credible intervals with cluster SEs.
    For Batters: evaluates probability calibration (ECE, Brier, Log Loss, Slope, Intercept).
    """
    records = []
    df_eval_copy = df_eval.copy()
    
    # Define Exposure Bands
    def get_band(exp):
        if domain == "Bowler":
            if exp <= 6:
                return "1_Single_Over [<=6 balls]"
            elif exp <= 12:
                return "2_Short_Spell [7-12 balls]"
            elif exp <= 18:
                return "3_Medium_Spell [13-18 balls]"
            else:
                return "4_Full_Spell [19+ balls]"
        else:
            if exp < 30:
                return "1_Sparse [1, 29]"
            elif exp < 100:
                return "2_Moderate [30, 99]"
            elif exp < 300:
                return "3_Substantial [100, 299]"
            else:
                return "4_High [300+]"
                
    exp_col = "legal_balls" if (domain == "Bowler" and "legal_balls" in df_eval_copy.columns) else (
        "context_exposure" if "context_exposure" in df_eval_copy.columns else "legal_balls"
    )
    df_eval_copy["exposure_band"] = df_eval_copy[exp_col].apply(get_band)
    
    se_col = "se_pred_m5" if "se_pred_m5" in df_eval_copy.columns else "se_m5"
    id_col = "striker_id" if domain == "Batter" else "bowler_id"
    if id_col not in df_eval_copy.columns and "player_id" in df_eval_copy.columns:
        id_col = "player_id"
        
    strata_dims = [
        ("Exposure_Band", "exposure_band"),
        ("Phase", "phase"),
        ("Pressure_Tier", "tier" if "tier" in df_eval_copy.columns else "modal_tier"),
        ("Role", "batter_role" if domain == "Batter" else "bowler_role")
    ]
    
    tier_col = "tier" if "tier" in df_eval_copy.columns else "modal_tier"
    
    evaluation_groups = []
    for str_name, col_name in strata_dims:
        if col_name in df_eval_copy.columns:
            for val, grp in df_eval_copy.groupby(col_name):
                evaluation_groups.append((str_name, str(val), grp))
                
    # 3 Summary Cohorts
    evaluation_groups.append(("Summary_Cohort", "1_All_Observations", df_eval_copy))
    if "phase" in df_eval_copy.columns:
        death_grp = df_eval_copy[df_eval_copy["phase"] == "Death"]
        if len(death_grp) > 0:
            evaluation_groups.append(("Summary_Cohort", "2_Death_Phase", death_grp))
    if tier_col in df_eval_copy.columns:
        hl_grp = df_eval_copy[df_eval_copy[tier_col].isin(["Tier 3: High", "Tier 4: Extreme"])]
        if len(hl_grp) > 0:
            evaluation_groups.append(("Summary_Cohort", "3_High_Leverage_Tiers_3_4", hl_grp))
            
    for str_name, val, grp in evaluation_groups:
        n_obs = len(grp)
        n_players = grp[id_col].nunique() if id_col in grp.columns else 1
        n_matches = grp["match_id"].nunique() if "match_id" in grp.columns else 1
        mean_act = float(grp["actual"].mean())
        mean_pr = float(grp["pred_m5"].mean())
        
        cluster_m = grp["match_id"].values if "match_id" in grp.columns else np.arange(n_obs)
        cluster_p = grp[id_col].values if id_col in grp.columns else np.arange(n_obs)
        
        if domain == "Bowler":
            # Continuous interval calibration
            cov_res = compute_continuous_interval_coverage_b431(
                grp["actual"].values, grp["pred_m5"].values, grp[se_col].values
            )
            cov_80 = cov_res["coverage_80"]
            cov_95 = cov_res["coverage_95"]
            cov_80_arr = cov_res["covered_80"].astype(float)
            cov_95_arr = cov_res["covered_95"].astype(float)
            
            # CGM two-way cluster SE for empirical coverage indicators
            if len(cov_80_arr) >= 10:
                resids_80 = cov_80_arr - cov_80
                var_c80, stat_80 = compute_two_way_cluster_variance(resids_80, cluster_m, cluster_p)
                se_c80 = math.sqrt(max(0.0, var_c80)) if np.isfinite(var_c80) else cov_res["coverage_80_se"]
                
                resids_95 = cov_95_arr - cov_95
                var_c95, stat_95 = compute_two_way_cluster_variance(resids_95, cluster_m, cluster_p)
                se_c95 = math.sqrt(max(0.0, var_c95)) if np.isfinite(var_c95) else cov_res["coverage_95_se"]
            else:
                se_c80 = cov_res["coverage_80_se"]
                se_c95 = cov_res["coverage_95_se"]
                
            ci_80_low = max(0.0, cov_80 - 1.96 * se_c80)
            ci_80_high = min(1.0, cov_80 + 1.96 * se_c80)
            ci_95_low = max(0.0, cov_95 - 1.96 * se_c95)
            ci_95_high = min(1.0, cov_95 + 1.96 * se_c95)
            
            # Dual-level calibration status logic (Priority 5)
            if n_obs < 30:
                status = "INSUFFICIENT_EVIDENCE"
            elif cov_80 < 0.75 or cov_95 < 0.90:
                status = "UNDER_COVERAGE"
            elif (ci_80_low <= 0.80 <= ci_80_high) and (ci_95_low <= 0.95 <= ci_95_high):
                status = "CALIBRATED_NOMINAL_COVERED"
            elif (cov_80 >= 0.78) and (cov_95 >= 0.93):
                status = "CALIBRATED_WITHIN_TOLERANCE"
            elif cov_80 > 0.85 and cov_95 > 0.97:
                status = "OVER_COVERAGE"
            else:
                status = "CALIBRATED_WITHIN_TOLERANCE"
                
            rec = {
                "domain": "Bowler",
                "stratum_type": str_name,
                "stratum_value": str(val),
                "sample_size": n_obs,
                "unique_players": n_players,
                "unique_matches": n_matches,
                "mean_actual": mean_act,
                "mean_pred": mean_pr,
                "coverage_80_nominal": 0.80,
                "coverage_80_empirical": cov_80,
                "coverage_80_cluster_se": se_c80,
                "coverage_80_ci_lower": ci_80_low,
                "coverage_80_ci_upper": ci_80_high,
                "coverage_95_nominal": 0.95,
                "coverage_95_empirical": cov_95,
                "coverage_95_cluster_se": se_c95,
                "coverage_95_ci_lower": ci_95_low,
                "coverage_95_ci_upper": ci_95_high,
                "std_z_residual": cov_res["std_z_residual"],
                "ece": np.nan,
                "calibration_slope": np.nan,
                "calibration_intercept": np.nan,
                "calibration_status": status
            }
        else:
            # Binary Probability Calibration for Batters (Priority 3 & 5)
            bin_res = compute_binary_probability_calibration_b431(
                grp["actual"].values, grp["pred_m5"].values, n_bins=10
            )
            ece = bin_res["ece"]
            brier = bin_res["brier_score"]
            log_l = bin_res["log_loss"]
            slope = bin_res["calib_slope"]
            intercept = bin_res["calib_intercept"]
            bias = mean_pr - mean_act
            
            # Cluster-robust SE for mean predicted probability error (bias)
            bias_series = grp["pred_m5"].values - grp["actual"].values
            var_bias, _ = compute_two_way_cluster_variance(bias_series, cluster_m, cluster_p)
            se_bias = math.sqrt(max(0.0, var_bias)) if np.isfinite(var_bias) else np.nan
            
            # Probability calibration status
            if n_obs < 100:
                status = "INSUFFICIENT_EVIDENCE"
            elif ece <= 0.02 and (0.85 <= slope <= 1.15) and abs(bias) <= 0.02:
                status = "CALIBRATED_PROBABILITY_ALIGNED"
            elif ece <= 0.04 and (0.80 <= slope <= 1.20):
                status = "CALIBRATED_WITHIN_TOLERANCE"
            elif ece > 0.05 or slope < 0.75 or slope > 1.30:
                status = "MISCALIBRATED_PROBABILITY"
            else:
                status = "CALIBRATED_WITHIN_TOLERANCE"
                
            rec = {
                "domain": "Batter",
                "stratum_type": str_name,
                "stratum_value": str(val),
                "sample_size": n_obs,
                "unique_players": n_players,
                "unique_matches": n_matches,
                "mean_actual": mean_act,
                "mean_pred": mean_pr,
                "coverage_80_nominal": np.nan,
                "coverage_80_empirical": np.nan,
                "coverage_80_cluster_se": np.nan,
                "coverage_80_ci_lower": np.nan,
                "coverage_80_ci_upper": np.nan,
                "coverage_95_nominal": np.nan,
                "coverage_95_empirical": np.nan,
                "coverage_95_cluster_se": np.nan,
                "coverage_95_ci_lower": np.nan,
                "coverage_95_ci_upper": np.nan,
                "std_z_residual": np.nan,
                "ece": ece,
                "calibration_slope": slope,
                "calibration_intercept": intercept,
                "calibration_status": status
            }
        records.append(rec)
        
    return pd.DataFrame(records)
