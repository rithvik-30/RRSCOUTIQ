"""
RR ScoutIQ — Milestone M5.5-B.4.3: Posterior Calibration & Diagnostics Engine
Module: src/m5_5b_4_3/calibration_engine_b4_3.py

Remediates audit defect:
1. Distinguishes strictly between:
   (a) Latent ability uncertainty: Var_latent = (1 - lambda) * tau2_player
   (b) Posterior predictive uncertainty: Var_pred = Var_latent + Var_sampling(n_eval)
   (c) Population contextual mean sampling error: Var_mean
2. Evaluates binary predictions (batter boundary) via Expected Calibration Error (ECE),
   Brier score, and decile reliability diagrams.
3. Evaluates credible interval coverage on held-out aggregated player-context spells/cohorts
   using training-fold estimated predictive standard errors:
   - Batter held-out spells: SE_pred = sqrt(Var_latent + p*(1-p)/n_balls)
   - Bowler held-out spells: SE_pred = sqrt(Var_latent + sigma2_over / (n_balls/6.0))
4. Evaluates standardized residuals z = (y - y_hat) / SE_pred (mean ~ 0, std ~ 1).
5. Comprehensive Stratified Calibration Reporting across:
   - Phase (Powerplay, Middle, Death)
   - Pressure Tier (Tier 1 to Tier 4)
   - Bowling Role
   - Legal-Ball Exposure Band
   Including:
   - Number of spells / evaluations
   - Number of unique bowlers / players
   - Number of independent matches
   - Observed empirical coverage (80% and 95%)
   - Match/player cluster-aware uncertainty intervals
   - Calibration status without hiding subgroup variance.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.m5_5b_4_3.cluster_variance_b4_3 import compute_two_way_cluster_variance


def compute_binary_calibration_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Computes Expected Calibration Error (ECE), Brier score, and reliability bins.
    """
    valid = np.isfinite(y_true) & np.isfinite(y_prob)
    y_t = y_true[valid]
    y_p = np.clip(y_prob[valid], 1e-6, 1.0 - 1e-6)
    n = len(y_t)
    if n == 0:
        return {"ece": np.nan, "brier_score": np.nan, "bins": []}
        
    brier = float(np.mean((y_p - y_t) ** 2))
    
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    bin_details = []
    
    for b in range(n_bins):
        low, high = bin_edges[b], bin_edges[b + 1]
        mask = (y_p >= low) & (y_p < high) if b < n_bins - 1 else (y_p >= low) & (y_p <= high)
        n_b = mask.sum()
        if n_b > 0:
            obs_rate = float(y_t[mask].mean())
            pred_rate = float(y_p[mask].mean())
            ece += (n_b / n) * abs(obs_rate - pred_rate)
            bin_details.append({
                "bin": b + 1,
                "low": low,
                "high": high,
                "count": int(n_b),
                "obs_rate": obs_rate,
                "pred_rate": pred_rate,
                "abs_gap": abs(obs_rate - pred_rate)
            })
            
    return {
        "brier_score": brier,
        "ece": float(ece),
        "bins": bin_details
    }


def compute_interval_coverage(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    se_pred: np.ndarray
) -> Dict[str, Any]:
    """
    Evaluates empirical coverage of 80% and 95% posterior predictive credible intervals.
    Standard normal critical values: z_80 = 1.28155, z_95 = 1.95996.
    Computes binomial standard error for empirical coverage proportions.
    """
    valid = np.isfinite(y_true) & np.isfinite(y_pred) & np.isfinite(se_pred) & (se_pred > 0)
    y_t = y_true[valid]
    y_p = y_pred[valid]
    s = se_pred[valid]
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
        
    # Standardized residuals
    z = (y_t - y_p) / s
    mean_z = float(np.mean(z))
    std_z = float(np.std(z, ddof=1)) if n > 1 else np.nan
    
    # 80% coverage
    ci_80_low = y_p - 1.28155 * s
    ci_80_high = y_p + 1.28155 * s
    covered_80 = (y_t >= ci_80_low) & (y_t <= ci_80_high)
    cov_80 = float(np.mean(covered_80))
    cov_80_se = float(math.sqrt(cov_80 * (1.0 - cov_80) / n)) if n > 0 else np.nan
    
    # 95% coverage
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


def compute_stratified_calibration_table_b43(
    df_eval: pd.DataFrame,
    domain: str = "Batter"
) -> pd.DataFrame:
    """
    Generates a multi-dimensional stratified calibration summary across:
    - Exposure bands: [1, 29], [30, 99], [100, 299], [300+] (or balls per spell for bowler)
    - Phases: Powerplay, Middle, Death
    - Pressure Tiers
    - Roles
    Includes match/player cluster-aware uncertainty intervals and calibration status.
    """
    records = []
    
    def get_band(exp):
        if domain == "Bowler":
            # Spell balls
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
            
    df_eval_copy = df_eval.copy()
    exp_col = "legal_balls" if (domain == "Bowler" and "legal_balls" in df_eval_copy.columns) else (
        "context_exposure" if "context_exposure" in df_eval_copy.columns else "legal_balls"
    )
    df_eval_copy["exposure_band"] = df_eval_copy[exp_col].apply(get_band)
        
    se_col = "se_pred_m5" if "se_pred_m5" in df_eval_copy.columns else "se_m5"
    id_col = "striker_id" if domain == "Batter" else "bowler_id"
    if id_col not in df_eval_copy.columns and "player_id" in df_eval_copy.columns:
        id_col = "player_id"
        
    # Stratification dimensions
    strata_dims = [
        ("Exposure_Band", "exposure_band"),
        ("Phase", "phase"),
        ("Pressure_Tier", "tier" if "tier" in df_eval_copy.columns else "modal_tier"),
        ("Role", "batter_role" if domain == "Batter" else "bowler_role")
    ]
    
    tier_col = "tier" if "tier" in df_eval_copy.columns else "modal_tier"
    
    # Stratified groups
    evaluation_groups = []
    for str_name, col_name in strata_dims:
        if col_name in df_eval_copy.columns:
            for val, grp in df_eval_copy.groupby(col_name):
                evaluation_groups.append((str_name, str(val), grp))
                
    # Authoritative 3 Summary Cohorts
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
        n_spells = len(grp)
        n_players = grp[id_col].nunique() if id_col in grp.columns else 1
        n_matches = grp["match_id"].nunique() if "match_id" in grp.columns else 1
        
        cov_res = compute_interval_coverage(
            grp["actual"].values, grp["pred_m5"].values, grp[se_col].values
        )
        
        # Cluster-aware uncertainty around empirical coverage
        cov_80 = cov_res["coverage_80"]
        cov_95 = cov_res["coverage_95"]
        
        cov_80_arr = cov_res["covered_80"].astype(float)
        cov_95_arr = cov_res["covered_95"].astype(float)
        
        cluster_m = grp["match_id"].values if "match_id" in grp.columns else np.arange(n_spells)
        cluster_p = grp[id_col].values if id_col in grp.columns else np.arange(n_spells)
        
        # CGM Two-way cluster SE on binary coverage indicator
        if len(cov_80_arr) >= 10:
            resids_80 = cov_80_arr - cov_80
            var_c80, stat_80 = compute_two_way_cluster_variance(resids_80, cluster_m, cluster_p)
            se_cluster_80 = math.sqrt(max(0.0, var_c80)) if np.isfinite(var_c80) else cov_res["coverage_80_se"]
            
            resids_95 = cov_95_arr - cov_95
            var_c95, stat_95 = compute_two_way_cluster_variance(resids_95, cluster_m, cluster_p)
            se_cluster_95 = math.sqrt(max(0.0, var_c95)) if np.isfinite(var_c95) else cov_res["coverage_95_se"]
        else:
            se_cluster_80 = cov_res["coverage_80_se"]
            se_cluster_95 = cov_res["coverage_95_se"]
            
        ci_80_low = max(0.0, cov_80 - 1.96 * se_cluster_80)
        ci_80_high = min(1.0, cov_80 + 1.96 * se_cluster_80)
        ci_95_low = max(0.0, cov_95 - 1.96 * se_cluster_95)
        ci_95_high = min(1.0, cov_95 + 1.96 * se_cluster_95)
        
        # Calibration status determination
        if n_spells < 30:
            status = "INSUFFICIENT_EVIDENCE"
        elif ci_80_low <= 0.80 <= ci_80_high:
            status = "CALIBRATED_NOMINAL_COVERED"
        elif cov_80 >= 0.78:
            status = "CALIBRATED_WITHIN_TOLERANCE"
        elif cov_80 < 0.78:
            status = "UNDER_COVERAGE"
        else:
            status = "OVER_COVERAGE"
            
        rec = {
            "domain": domain,
            "stratum_type": str_name,
            "stratum_value": str(val),
            "sample_size": n_spells,
            "unique_players": n_players,
            "unique_matches": n_matches,
            "mean_actual": float(grp["actual"].mean()),
            "mean_pred": float(grp["pred_m5"].mean()),
            "coverage_80_nominal": 0.80,
            "coverage_80_empirical": cov_80,
            "coverage_80_cluster_se": se_cluster_80,
            "coverage_80_ci_lower": ci_80_low,
            "coverage_80_ci_upper": ci_80_high,
            "coverage_95_nominal": 0.95,
            "coverage_95_empirical": cov_95,
            "coverage_95_cluster_se": se_cluster_95,
            "coverage_95_ci_lower": ci_95_low,
            "coverage_95_ci_upper": ci_95_high,
            "std_z_residual": cov_res["std_z_residual"],
            "calibration_status": status
        }
        records.append(rec)
            
    return pd.DataFrame(records)
