"""
RR ScoutIQ — Milestone M5.5-B.4.3.6: Dual-Domain Posterior Calibration Engine
Module: src/m5_5b_4_3_6/calibration_engine_b4_3_6.py

Preserves all exhaustive input validation and sanitization from B.4.3.4 and B.4.3.5.
"""

import math
from typing import Dict, Any, List, Tuple, Optional, Union
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression

from src.m5_5b_4_3_6.cluster_variance_b4_3_6 import compute_two_way_cluster_variance


def evaluate_bowler_calibration_status(
    cov_80: Optional[float],
    ci_80_low: Optional[float],
    ci_80_high: Optional[float],
    cov_95: Optional[float],
    ci_95_low: Optional[float],
    ci_95_high: Optional[float],
    n_obs: Union[int, float]
) -> Tuple[str, str]:
    """
    Derives bowler predictive interval calibration status with exhaustive input validation.
    
    Rejection Conditions (returns INVALID_CALIBRATION_INPUT):
    - Non-integer, negative, or boolean sample size
    - Null, None, NaN, or infinite inputs
    - Coverage point estimates or CI bounds outside [0, 1]
    - Reversed interval bounds (lower > upper)
    - Confidence interval that does not contain the point estimate coverage
    
    Sample Size Screening (returns INSUFFICIENT_EVIDENCE):
    - n_obs < 30
    """
    # 1. Sample size validation
    if isinstance(n_obs, bool) or not isinstance(n_obs, (int, np.integer)):
        return "INVALID_CALIBRATION_INPUT", f"INVALID_SAMPLE_SIZE:NON_INTEGER_TYPE:{type(n_obs).__name__}"
    if n_obs <= 0:
        return "INVALID_CALIBRATION_INPUT", f"INVALID_SAMPLE_SIZE:NON_POSITIVE_VALUE:{n_obs}"
        
    # 2. Null / None checks
    all_inputs = [cov_80, ci_80_low, ci_80_high, cov_95, ci_95_low, ci_95_high]
    if any(x is None for x in all_inputs):
        return "INVALID_CALIBRATION_INPUT", "MISSING_INPUT:NULL_OR_NONE_VALUE"
        
    # 3. Finite numerical validation
    if not all(isinstance(x, (int, float, np.floating, np.integer)) and not isinstance(x, bool) and np.isfinite(x) for x in all_inputs):
        return "INVALID_CALIBRATION_INPUT", "INVALID_NUMERICAL_VALUE:NaN_OR_INF"
        
    c80 = float(cov_80)
    c95 = float(cov_95)
    c80_l = float(ci_80_low)
    c80_u = float(ci_80_high)
    c95_l = float(ci_95_low)
    c95_u = float(ci_95_high)
    
    # 4. Probabilistic range validation [0, 1] for both point estimates and CI bounds
    if not (0.0 <= c80 <= 1.0 and 0.0 <= c95 <= 1.0):
        return "INVALID_CALIBRATION_INPUT", f"COVERAGE_OUTSIDE_RANGE_[0,1]:cov80={c80},cov95={c95}"
    if not (0.0 <= c80_l <= 1.0 and 0.0 <= c80_u <= 1.0 and 0.0 <= c95_l <= 1.0 and 0.0 <= c95_u <= 1.0):
        return "INVALID_CALIBRATION_INPUT", f"CI_BOUNDS_OUTSIDE_RANGE_[0,1]:[{c80_l},{c80_u}],[{c95_l},{c95_u}]"
        
    # 5. Monotonic interval bound validation (reversed bounds)
    if c80_l > c80_u or c95_l > c95_u:
        return "INVALID_CALIBRATION_INPUT", f"REVERSED_CONFIDENCE_INTERVAL_BOUNDS:[{c80_l},{c80_u}],[{c95_l},{c95_u}]"
        
    # 6. Containment validation: CI must contain empirical coverage point estimate
    # Tolerating floating point epsilon 1e-12
    eps = 1e-12
    if (c80 < c80_l - eps or c80 > c80_u + eps) or (c95 < c95_l - eps or c95 > c95_u + eps):
        return "INVALID_CALIBRATION_INPUT", (
            f"COVERAGE_OUTSIDE_CONFIDENCE_INTERVAL:cov80={c80} not in [{c80_l},{c80_u}] "
            f"or cov95={c95} not in [{c95_l},{c95_u}]"
        )
        
    # 7. Sample size screening (applied BEFORE evaluating coverage)
    if n_obs < 30:
        return "INSUFFICIENT_EVIDENCE", f"SAMPLE_SIZE_BELOW_MINIMUM:N={n_obs}<30"
        
    # 8. Objective status derivation
    violations = []
    under_80 = (c80_u < 0.80)
    under_95 = (c95_u < 0.95)
    over_80 = (c80_l > 0.80)
    over_95 = (c95_l > 0.95)
    cov_nom_80 = (c80_l <= 0.80 <= c80_u)
    cov_nom_95 = (c95_l <= 0.95 <= c95_u)
    
    if under_80:
        violations.append(f"UNDER_COVERAGE_80%:[{c80_l:.4f},{c80_u:.4f}]<0.80")
    if under_95:
        violations.append(f"UNDER_COVERAGE_95%:[{c95_l:.4f},{c95_u:.4f}]<0.95")
    if over_80:
        violations.append(f"OVER_COVERAGE_80%:[{c80_l:.4f},{c80_u:.4f}]>0.80")
    if over_95:
        violations.append(f"OVER_COVERAGE_95%:[{c95_l:.4f},{c95_u:.4f}]>0.95")
        
    v_str = "; ".join(violations) if violations else "NONE"
    
    if under_80 or under_95:
        return "SIGNIFICANT_UNDER_COVERAGE", v_str
    elif cov_nom_80 and cov_nom_95:
        return "CALIBRATED_NOMINAL_COVERED", "NONE"
    elif over_80 or over_95:
        return "CONSERVATIVE_OVER_COVERAGE", v_str
    elif abs(c80 - 0.80) <= 0.03 and abs(c95 - 0.95) <= 0.02:
        return "CALIBRATED_WITHIN_TOLERANCE", v_str
    else:
        return "CALIBRATED_WITHIN_TOLERANCE", v_str


def evaluate_batter_calibration_status(
    ece: Optional[float],
    slope: Optional[float],
    bias: Optional[float],
    n_obs: Union[int, float]
) -> Tuple[str, str]:
    """
    Derives batter binary probability calibration status with exhaustive input validation.
    
    Rejection Conditions (returns INVALID_CALIBRATION_INPUT):
    - Non-integer, negative, or boolean sample size
    - Null, None, NaN, or infinite inputs
    - ECE outside [0, 1]
    - Slope non-positive
    
    Sample Size Screening (returns INSUFFICIENT_EVIDENCE):
    - n_obs < 100
    """
    # 1. Sample size validation
    if isinstance(n_obs, bool) or not isinstance(n_obs, (int, np.integer)):
        return "INVALID_CALIBRATION_INPUT", f"INVALID_SAMPLE_SIZE:NON_INTEGER_TYPE:{type(n_obs).__name__}"
    if n_obs <= 0:
        return "INVALID_CALIBRATION_INPUT", f"INVALID_SAMPLE_SIZE:NON_POSITIVE_VALUE:{n_obs}"
        
    # 2. Null / None checks
    all_inputs = [ece, slope, bias]
    if any(x is None for x in all_inputs):
        return "INVALID_CALIBRATION_INPUT", "MISSING_INPUT:NULL_OR_NONE_VALUE"
        
    # 3. Finite numerical validation
    if not all(isinstance(x, (int, float, np.floating, np.integer)) and not isinstance(x, bool) and np.isfinite(x) for x in all_inputs):
        return "INVALID_CALIBRATION_INPUT", "INVALID_NUMERICAL_VALUE:NaN_OR_INF"
        
    e = float(ece)
    s = float(slope)
    b = float(bias)
    
    # 4. Domain constraints
    if not (0.0 <= e <= 1.0):
        return "INVALID_CALIBRATION_INPUT", f"ECE_OUTSIDE_RANGE_[0,1]:ece={e}"
    if s <= 0.0:
        return "INVALID_CALIBRATION_INPUT", f"SLOPE_NON_POSITIVE:slope={s}"
        
    # 5. Sample size screening
    if n_obs < 100:
        return "INSUFFICIENT_EVIDENCE", f"SAMPLE_SIZE_BELOW_MINIMUM:N={n_obs}<100"
        
    # 6. Objective status derivation
    violations = []
    if abs(s - 1.0) > 0.15:
        violations.append(f"SLOPE_OUT_OF_BOUNDS:{s:.4f} not in [0.85,1.15]")
    if e > 0.02:
        violations.append(f"ECE_ELEVATED:{e:.4f}>0.02")
    if abs(b) > 0.02:
        violations.append(f"BIAS_ELEVATED:{b:+.4f}>0.02")
        
    v_str = "; ".join(violations) if violations else "NONE"
    
    if violations:
        return "MODERATE_CALIBRATION_TOLERATED", v_str
    else:
        return "CALIBRATED_PROBABILITY_ALIGNED", "NONE"


def compute_continuous_interval_coverage_b434(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    se_pred: np.ndarray,
    cluster_match: np.ndarray,
    cluster_player: np.ndarray
) -> Dict[str, Any]:
    """
    Computes 80% and 95% continuous interval coverage with two-way cluster-robust CIs.
    """
    n = len(y_true)
    if n == 0:
        return {
            "sample_size": 0,
            "coverage_80": np.nan,
            "coverage_80_ci_lower": np.nan,
            "coverage_80_ci_upper": np.nan,
            "coverage_95": np.nan,
            "coverage_95_ci_lower": np.nan,
            "coverage_95_ci_upper": np.nan,
            "std_z_residual": np.nan,
            "calibration_status": "INSUFFICIENT_EVIDENCE",
            "calibration_violations": f"SAMPLE_SIZE_BELOW_MINIMUM:N=0<30"
        }
        
    z_80 = 1.2815515655446004
    z_95 = 1.959963984540054
    
    lower_80 = y_pred - z_80 * se_pred
    upper_80 = y_pred + z_80 * se_pred
    in_80 = ((y_true >= lower_80) & (y_true <= upper_80)).astype(float)
    cov_80 = float(np.mean(in_80))
    
    lower_95 = y_pred - z_95 * se_pred
    upper_95 = y_pred + z_95 * se_pred
    in_95 = ((y_true >= lower_95) & (y_true <= upper_95)).astype(float)
    cov_95 = float(np.mean(in_95))
    
    # Standardized residuals
    z_resids = (y_true - y_pred) / np.maximum(se_pred, 1e-6)
    std_z = float(np.std(z_resids, ddof=1)) if n > 1 else 0.0
    
    # Cluster-robust standard errors
    var_80, _ = compute_two_way_cluster_variance(in_80 - cov_80, cluster_match, cluster_player)
    se_80 = math.sqrt(max(0.0, var_80)) if np.isfinite(var_80) else (math.sqrt(cov_80 * (1 - cov_80) / n) if n > 1 else 0.0)
    
    var_95, _ = compute_two_way_cluster_variance(in_95 - cov_95, cluster_match, cluster_player)
    se_95 = math.sqrt(max(0.0, var_95)) if np.isfinite(var_95) else (math.sqrt(cov_95 * (1 - cov_95) / n) if n > 1 else 0.0)
    
    # 95% Confidence intervals on coverage: bounded to [0, 1] while strictly containing point estimate
    ci_80_l = max(0.0, min(cov_80, cov_80 - 1.96 * se_80))
    ci_80_u = min(1.0, max(cov_80, cov_80 + 1.96 * se_80))
    ci_95_l = max(0.0, min(cov_95, cov_95 - 1.96 * se_95))
    ci_95_u = min(1.0, max(cov_95, cov_95 + 1.96 * se_95))
    
    status, violations = evaluate_bowler_calibration_status(
        cov_80=cov_80,
        ci_80_low=ci_80_l,
        ci_80_high=ci_80_u,
        cov_95=cov_95,
        ci_95_low=ci_95_l,
        ci_95_high=ci_95_u,
        n_obs=n
    )
    
    return {
        "sample_size": int(n),
        "mean_actual": float(np.mean(y_true)),
        "mean_pred": float(np.mean(y_pred)),
        "coverage_80": cov_80,
        "coverage_80_se": se_80,
        "coverage_80_ci_lower": ci_80_l,
        "coverage_80_ci_upper": ci_80_u,
        "coverage_95": cov_95,
        "coverage_95_se": se_95,
        "coverage_95_ci_lower": ci_95_l,
        "coverage_95_ci_upper": ci_95_u,
        "std_z_residual": std_z,
        "calibration_status": status,
        "calibration_violations": violations
    }


def compute_binary_probability_calibration_b434(
    y_true: np.ndarray,
    p_pred: np.ndarray,
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Computes ECE, calibration slope, intercept, bias, and status for binary probabilities.
    """
    n = len(y_true)
    if n == 0:
        return {
            "sample_size": 0,
            "ece": np.nan,
            "calibration_slope": np.nan,
            "calibration_intercept": np.nan,
            "bias": np.nan,
            "calibration_status": "INSUFFICIENT_EVIDENCE",
            "calibration_violations": "SAMPLE_SIZE_BELOW_MINIMUM:N=0<100"
        }
        
    p_clipped = np.clip(p_pred, 1e-6, 1.0 - 1e-6)
    bias = float(np.mean(p_clipped) - np.mean(y_true))
    
    # ECE with equal-frequency quantile binning
    try:
        quantiles = np.linspace(0, 1, n_bins + 1)
        bin_edges = np.quantile(p_clipped, quantiles)
        bin_edges[0] = 0.0
        bin_edges[-1] = 1.0
        bin_indices = np.digitize(p_clipped, bin_edges[1:-1])
        
        ece = 0.0
        for b in range(n_bins):
            mask = (bin_indices == b)
            if np.sum(mask) > 0:
                bin_acc = np.mean(y_true[mask])
                bin_conf = np.mean(p_clipped[mask])
                ece += (np.sum(mask) / n) * abs(bin_acc - bin_conf)
        ece = float(ece)
    except Exception:
        ece = np.nan
        
    # Logistic calibration slope & intercept
    try:
        logit_p = logit(p_clipped).reshape(-1, 1)
        if len(np.unique(y_true)) > 1:
            lr = LogisticRegression(penalty=None, solver="lbfgs")
            lr.fit(logit_p, y_true)
            slope = float(lr.coef_[0][0])
            intercept = float(lr.intercept_[0])
        else:
            slope = 1.0
            intercept = 0.0
    except Exception:
        slope = np.nan
        intercept = np.nan
        
    status, violations = evaluate_batter_calibration_status(
        ece=ece,
        slope=slope,
        bias=bias,
        n_obs=n
    )
    
    return {
        "sample_size": int(n),
        "mean_actual": float(np.mean(y_true)),
        "mean_pred": float(np.mean(p_clipped)),
        "ece": ece,
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "bias": bias,
        "calibration_status": status,
        "calibration_violations": violations
    }


def compute_stratified_calibration_table_b434(
    oof_df: pd.DataFrame,
    domain: str
) -> pd.DataFrame:
    """
    Builds the stratified calibration diagnostic table across all strata.
    """
    records = []
    
    if domain.lower() == "bowler":
        t_col = "tier" if "tier" in oof_df.columns else "modal_tier"
        strata_definitions = [
            ("Summary_Cohort", "1_All_Observations", lambda df: df),
            ("Summary_Cohort", "2_Death_Phase", lambda df: df[df["phase"] == "Death"]),
            ("Summary_Cohort", "3_High_Leverage_Tiers_3_4", lambda df: df[df[t_col].isin(["Tier 3: High", "Tier 4: Extreme"])]),
            ("Exposure_Band", "1_Single_Over [<=6 balls]", lambda df: df[df["legal_balls"] <= 6]),
            ("Exposure_Band", "2_Short_Spell [7-12 balls]", lambda df: df[(df["legal_balls"] > 6) & (df["legal_balls"] <= 12)]),
            ("Exposure_Band", "3_Medium_Spell [13-18 balls]", lambda df: df[(df["legal_balls"] > 12) & (df["legal_balls"] <= 18)]),
            ("Exposure_Band", "4_Full_Spell [19+ balls]", lambda df: df[df["legal_balls"] >= 19]),
            ("Phase", "Powerplay", lambda df: df[df["phase"] == "Powerplay"]),
            ("Phase", "Middle", lambda df: df[df["phase"] == "Middle"]),
            ("Phase", "Death", lambda df: df[df["phase"] == "Death"]),
            ("Phase", "Super Over", lambda df: df[df["phase"] == "Super Over"]),
            ("Pressure_Tier", "Tier 1: Low", lambda df: df[df[t_col] == "Tier 1: Low"]),
            ("Pressure_Tier", "Tier 2: Medium", lambda df: df[df[t_col] == "Tier 2: Medium"]),
            ("Pressure_Tier", "Tier 3: High", lambda df: df[df[t_col] == "Tier 3: High"]),
            ("Pressure_Tier", "Tier 4: Extreme", lambda df: df[df[t_col] == "Tier 4: Extreme"]),
            ("Role", "Powerplay Specialist", lambda df: df[df["bowler_role"] == "Powerplay Specialist"]),
            ("Role", "Middle Enforcer", lambda df: df[df["bowler_role"] == "Middle Enforcer"]),
            ("Role", "Death Specialist", lambda df: df[df["bowler_role"] == "Death Specialist"]),
        ]
        
        for s_type, s_val, filter_fn in strata_definitions:
            sdf = filter_fn(oof_df)
            n = len(sdf)
            if n == 0:
                continue
                
            y_t = sdf["actual"].values
            y_p = sdf["pred_m5"].values
            se_p = sdf["se_pred_m5"].values
            pid_col = "player_id" if "player_id" in sdf.columns else ("bowler_id" if "bowler_id" in sdf.columns else "striker_id")
            m_cl = sdf["match_id"].values
            p_cl = sdf[pid_col].values
            
            res = compute_continuous_interval_coverage_b434(y_t, y_p, se_p, m_cl, p_cl)
            
            records.append({
                "domain": "Bowler",
                "stratum_type": s_type,
                "stratum_value": s_val,
                "sample_size": n,
                "unique_players": int(sdf[pid_col].nunique()),
                "unique_matches": int(sdf["match_id"].nunique()),
                "mean_actual": res["mean_actual"],
                "mean_pred": res["mean_pred"],
                "coverage_80_nominal": 0.80,
                "coverage_80_empirical": res["coverage_80"],
                "coverage_80_cluster_se": res["coverage_80_se"],
                "coverage_80_ci_lower": res["coverage_80_ci_lower"],
                "coverage_80_ci_upper": res["coverage_80_ci_upper"],
                "coverage_95_nominal": 0.95,
                "coverage_95_empirical": res["coverage_95"],
                "coverage_95_cluster_se": res["coverage_95_se"],
                "coverage_95_ci_lower": res["coverage_95_ci_lower"],
                "coverage_95_ci_upper": res["coverage_95_ci_upper"],
                "std_z_residual": res["std_z_residual"],
                "ece": np.nan,
                "calibration_slope": np.nan,
                "calibration_intercept": np.nan,
                "calibration_status": res["calibration_status"],
                "calibration_violations": res["calibration_violations"]
            })
            
    else:
        # Batter binary outcomes
        strata_definitions = [
            ("Summary_Cohort", "1_All_Observations", lambda df: df),
            ("Summary_Cohort", "2_Death_Phase", lambda df: df[df["phase"] == "Death"]),
            ("Summary_Cohort", "3_High_Leverage_Tiers_3_4", lambda df: df[df["tier"].isin(["Tier 3: High", "Tier 4: Extreme"])]),
            ("Exposure_Band", "1_Sparse [<30 balls]", lambda df: df[df["context_exposure"] < 30]),
            ("Exposure_Band", "2_Moderate [30, 99]", lambda df: df[(df["context_exposure"] >= 30) & (df["context_exposure"] < 100)]),
            ("Exposure_Band", "3_Substantial [100, 299]", lambda df: df[(df["context_exposure"] >= 100) & (df["context_exposure"] < 300)]),
            ("Exposure_Band", "4_High [300+]", lambda df: df[df["context_exposure"] >= 300]),
            ("Phase", "Powerplay", lambda df: df[df["phase"] == "Powerplay"]),
            ("Phase", "Middle", lambda df: df[df["phase"] == "Middle"]),
            ("Phase", "Death", lambda df: df[df["phase"] == "Death"]),
            ("Phase", "Super Over", lambda df: df[df["phase"] == "Super Over"]),
            ("Pressure_Tier", "Tier 1: Low", lambda df: df[df["tier"] == "Tier 1: Low"]),
            ("Pressure_Tier", "Tier 2: Medium", lambda df: df[df["tier"] == "Tier 2: Medium"]),
            ("Pressure_Tier", "Tier 3: High", lambda df: df[df["tier"] == "Tier 3: High"]),
            ("Pressure_Tier", "Tier 4: Extreme", lambda df: df[df["tier"] == "Tier 4: Extreme"]),
            ("Role", "TopOrderBatter", lambda df: df[df["batter_role"] == "TopOrderBatter"]),
            ("Role", "MiddleOrderAnchor", lambda df: df[df["batter_role"] == "MiddleOrderAnchor"]),
            ("Role", "Finisher", lambda df: df[df["batter_role"] == "Finisher"]),
        ]
        
        for s_type, s_val, filter_fn in strata_definitions:
            sdf = filter_fn(oof_df)
            n = len(sdf)
            if n == 0:
                continue
                
            y_t = sdf["actual"].values
            p_p = sdf["pred_m5"].values
            
            res = compute_binary_probability_calibration_b434(y_t, p_p)
            
            pid_col = "player_id" if "player_id" in sdf.columns else ("batter_id" if "batter_id" in sdf.columns else "striker_id")
            records.append({
                "domain": "Batter",
                "stratum_type": s_type,
                "stratum_value": s_val,
                "sample_size": n,
                "unique_players": int(sdf[pid_col].nunique()),
                "unique_matches": int(sdf["match_id"].nunique()),
                "mean_actual": res["mean_actual"],
                "mean_pred": res["mean_pred"],
                "coverage_80_nominal": 0.80,
                "coverage_80_empirical": np.nan,
                "coverage_80_cluster_se": np.nan,
                "coverage_80_ci_lower": np.nan,
                "coverage_80_ci_upper": np.nan,
                "coverage_95_nominal": 0.95,
                "coverage_95_empirical": np.nan,
                "coverage_95_cluster_se": np.nan,
                "coverage_95_ci_lower": np.nan,
                "coverage_95_ci_upper": np.nan,
                "std_z_residual": np.nan,
                "ece": res["ece"],
                "calibration_slope": res["calibration_slope"],
                "calibration_intercept": res["calibration_intercept"],
                "calibration_status": res["calibration_status"],
                "calibration_violations": res["calibration_violations"]
            })
            
    res_df = pd.DataFrame(records)
    # Sort order
    res_df = res_df.sort_values(by=["domain", "stratum_type", "stratum_value"]).reset_index(drop=True)
    return res_df


# Milestone B.4.3.6 Aliases
compute_continuous_interval_coverage_b436 = compute_continuous_interval_coverage_b434
compute_binary_probability_calibration_b436 = compute_binary_probability_calibration_b434
compute_stratified_calibration_table_b436 = compute_stratified_calibration_table_b434
evaluate_bowler_calibration_status_b436 = evaluate_bowler_calibration_status
evaluate_batter_calibration_status_b436 = evaluate_batter_calibration_status


