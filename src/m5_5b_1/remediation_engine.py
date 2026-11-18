"""
RR ScoutIQ — Milestone M5.5-B.1: Statistical Remediation Engine
Module: src/m5_5b_1/remediation_engine.py

Core implementation of:
1. Strict fold-specific role derivation (zero match leakage)
2. Beta-Binomial Marginal Maximum Likelihood with Kleinman-corrected Method-of-Moments safeguards
3. Normal-Normal continuous hierarchical Bayesian calibration
4. Full evaluation of continuous (runs/ball) and binary outcomes (Boundary, Dot, Wicket/Dismissal)
5. Out-of-sample Brier score, Log Loss, calibration slope/intercept, and reliability tables
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import betaln, gammaln
from sklearn.model_selection import GroupKFold
from typing import Dict, List, Tuple, Any, Optional


# ==============================================================================
# 1. LEAK-FREE FOLD-SPECIFIC ROLE DERIVATION
# ==============================================================================

def derive_training_batter_roles(train_df: pd.DataFrame) -> Tuple[Dict[int, str], Dict[str, Any]]:
    """
    Derives batter primary tactical roles STRICTLY from training matches.
    Preserves approved M3 Definition 1:
      Top Order: mean regulation entry over <= 6.0
      Middle Order: mean regulation entry over > 6.0 and <= 13.0
      Finisher: mean regulation entry over > 13.0
    Returns:
      role_map: Dict[striker_id -> role]
      audit_stats: Dict of role counts, entry averages, coverage metrics
    """
    reg = train_df[train_df["innings"] <= 2]
    first_overs = (
        reg.groupby(["striker_id", "match_id", "innings"])["overid"]
        .min()
        .reset_index()
    )
    mean_entries = first_overs.groupby("striker_id")["overid"].mean()
    inns_counts = first_overs.groupby("striker_id")["overid"].count()
    
    role_map = {}
    details = {}
    for sid, avg_entry in mean_entries.items():
        sid = int(sid)
        if avg_entry <= 6.0:
            role = "Top Order"
        elif avg_entry <= 13.0:
            role = "Middle Order"
        else:
            role = "Finisher"
        role_map[sid] = role
        details[sid] = {
            "mean_entry": avg_entry,
            "innings_count": inns_counts.get(sid, 0),
            "role": role
        }
        
    counts = pd.Series(list(role_map.values())).value_counts().to_dict()
    return role_map, {"counts": counts, "details": details, "total_batters": len(role_map)}


def derive_training_bowler_roles(train_df: pd.DataFrame) -> Tuple[Dict[int, str], Dict[str, Any]]:
    """
    Derives bowler tactical roles STRICTLY from training matches.
    Preserves approved M3 Definition B1:
      Powerplay Specialist: PP legal balls / total legal balls >= 40%
      Death Specialist: Death legal balls / total legal balls >= 30%
      Operative tiebreak: pp_pct >= death_pct -> Powerplay Specialist
      Remainder: Middle Enforcer
    Returns:
      role_map: Dict[bowler_id -> role]
      audit_stats: Dict of workloads, counts, coverage
    """
    reg = train_df[(train_df["innings"] <= 2) & (train_df["ext_is_legal_delivery"] == 1)]
    bowler_stats = reg.groupby("bowler_id").agg(
        total_legal=("ext_is_legal_delivery", "sum"),
        pp_balls=("overid", lambda s: (s <= 6).sum()),
        mid_balls=("overid", lambda s: ((s >= 7) & (s <= 15)).sum()),
        death_balls=("overid", lambda s: (s >= 16).sum())
    ).reset_index()
    
    role_map = {}
    details = {}
    for _, row in bowler_stats.iterrows():
        bid = int(row["bowler_id"])
        total = row["total_legal"]
        if total == 0:
            role = "Middle Enforcer"
            pp_pct, death_pct, mid_pct = 0.0, 0.0, 0.0
        else:
            pp_pct = row["pp_balls"] / total
            death_pct = row["death_balls"] / total
            mid_pct = row["mid_balls"] / total
            is_pp = pp_pct >= 0.40
            is_death = death_pct >= 0.30
            if is_pp and is_death:
                role = "Powerplay Specialist" if pp_pct >= death_pct else "Death Specialist"
            elif is_pp:
                role = "Powerplay Specialist"
            elif is_death:
                role = "Death Specialist"
            else:
                role = "Middle Enforcer"
                
        role_map[bid] = role
        details[bid] = {
            "total_legal": total,
            "pp_pct": pp_pct,
            "death_pct": death_pct,
            "mid_pct": mid_pct,
            "role": role
        }
        
    counts = pd.Series(list(role_map.values())).value_counts().to_dict()
    return role_map, {"counts": counts, "details": details, "total_bowlers": len(role_map)}


def apply_fold_roles(
    val_df: pd.DataFrame,
    b_role_map: Dict[int, str],
    bw_role_map: Dict[int, str]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Applies training-derived roles to validation set.
    Explicitly tracks and flags fallbacks for players unseen in the training fold.
    """
    val = val_df.copy()
    
    # Batter role assignment
    b_fallbacks = 0
    b_assigned = 0
    val_b_roles = []
    val_b_is_fallback = []
    
    for sid in val["striker_id"]:
        sid = int(sid)
        if sid in b_role_map:
            val_b_roles.append(b_role_map[sid])
            val_b_is_fallback.append(0)
            b_assigned += 1
        else:
            # Explicit fallback
            val_b_roles.append("Middle Order")
            val_b_is_fallback.append(1)
            b_fallbacks += 1
            
    val["batter_role"] = val_b_roles
    val["batter_role_is_fallback"] = val_b_is_fallback
    
    # Bowler role assignment
    bw_fallbacks = 0
    bw_assigned = 0
    val_bw_roles = []
    val_bw_is_fallback = []
    
    for bid in val["bowler_id"]:
        bid = int(bid)
        if bid in bw_role_map:
            val_bw_roles.append(bw_role_map[bid])
            val_bw_is_fallback.append(0)
            bw_assigned += 1
        else:
            val_bw_roles.append("Middle Enforcer")
            val_bw_is_fallback.append(1)
            bw_fallbacks += 1
            
    val["bowler_role"] = val_bw_roles
    val["bowler_role_is_fallback"] = val_bw_is_fallback
    
    coverage_report = {
        "batter_assigned_deliveries": b_assigned,
        "batter_fallback_deliveries": b_fallbacks,
        "batter_fallback_rate": b_fallbacks / max(len(val), 1),
        "bowler_assigned_deliveries": bw_assigned,
        "bowler_fallback_deliveries": bw_fallbacks,
        "bowler_fallback_rate": bw_fallbacks / max(len(val), 1),
    }
    return val, coverage_report


# ==============================================================================
# 2. STATISTICALLY SAFEGUARDED BETA-BINOMIAL MML OPTIMIZATION
# ==============================================================================

def beta_binomial_log_likelihood(mu: float, M: float, k: np.ndarray, n: np.ndarray) -> float:
    """
    Computes exact log-likelihood for Beta-Binomial(n, alpha=mu*M, beta=(1-mu)*M).
    Handles edge conditions safely.
    """
    alpha = mu * M
    beta = (1.0 - mu) * M
    
    # Combination term
    log_comb = gammaln(n + 1.0) - gammaln(k + 1.0) - gammaln(n - k + 1.0)
    # Beta ratio term
    log_beta_ratio = betaln(k + alpha, n - k + beta) - betaln(alpha, beta)
    
    ll_per_obs = log_comb + log_beta_ratio
    return float(np.sum(ll_per_obs))


def kleinman_corrected_method_of_moments(k: np.ndarray, n: np.ndarray) -> Tuple[float, float, str]:
    """
    Kleinman (1973) corrected method-of-moments estimator for Beta-Binomial.
    Explicitly subtracts binomial sampling variance from total empirical variance.
    Returns:
      mu_est: Prior mean
      M_est: Effective prior sample size (alpha + beta)
      status: Diagnostic message
    """
    p_hat = k / np.maximum(n, 1)
    w = n.astype(float)
    W = np.sum(w)
    
    if W == 0 or len(k) == 0:
        return 0.2, 50.0, "Zero weights; default returned"
        
    # Weighted mean
    p_bar = np.sum(w * p_hat) / W
    
    if p_bar <= 0.0 or p_bar >= 1.0:
        return float(np.clip(p_bar, 0.001, 0.999)), 100.0, "Degenerate mean"
        
    # Sum of weighted squared errors
    S = np.sum(w * ((p_hat - p_bar) ** 2))
    
    # Degrees of freedom and correction terms
    sum_w_sq = np.sum(w ** 2)
    coeff_between = W - (sum_w_sq / W)
    sum_df = len(k) - 1.0
    
    # Expected binomial sampling variance component
    sampling_var_component = (len(k) - 1.0) * p_bar * (1.0 - p_bar)
    
    # Excess variance attributable to true between-player differences
    excess_var = S - sampling_var_component
    
    if excess_var <= 0.0:
        # Under-dispersion or pure binomial noise: between-player variance is indistinguishable from 0
        # Corresponds to M -> infinity (or very large shrinkage)
        return p_bar, 5000.0, "Zero excess variance (pure binomial noise; M set to 5000)"
        
    tau_sq = excess_var / max(coeff_between - sum_df, 1e-6)
    max_tau_sq = p_bar * (1.0 - p_bar)
    tau_sq = min(tau_sq, max_tau_sq * 0.99)
    
    # Var(p) = p_bar * (1 - p_bar) / (M + 1) -> M = (p_bar * (1 - p_bar) / tau_sq) - 1
    M_est = (p_bar * (1.0 - p_bar) / max(tau_sq, 1e-8)) - 1.0
    M_est = float(np.clip(M_est, 2.0, 10000.0))
    
    return float(p_bar), M_est, "Kleinman MOM successful"


def fit_beta_binomial_safeguarded(
    k: np.ndarray,
    n: np.ndarray,
    entity: str = "Player",
    metric_name: str = "Metric",
    role: str = "Global",
    fold: int = 0
) -> Dict[str, Any]:
    """
    Fits Beta-Binomial hyperparameters (mu, M) with strict statistical safeguards:
    1. Initial parameter derivation via Kleinman corrected MOM.
    2. Numerical optimization of Marginal Log-Likelihood with bounded L-BFGS-B on (logit(mu), log(M)).
    3. Boundary detection and failure handling.
    4. Diagnostic logging of convergence, Hessian, and fallback usage.
    """
    mask = n > 0
    k_v = k[mask].astype(float)
    n_v = n[mask].astype(float)
    N_players = len(k_v)
    total_trials = int(np.sum(n_v))
    total_successes = int(np.sum(k_v))
    
    if N_players < 3 or total_trials < 10:
        return {
            "Entity": entity,
            "Metric": metric_name,
            "Role": role,
            "Fold": fold,
            "Convergence_Status": "FAIL_INSUFFICIENT_DATA",
            "Optimizer_Message": f"Insufficient data: {N_players} players, {total_trials} trials",
            "Fallback_Used": True,
            "Prior_Mean": 0.15,
            "Effective_M_Prior": 100.0,
            "Alpha": 15.0,
            "Beta": 85.0,
            "N_Players": N_players,
            "Total_Trials": total_trials,
            "Total_Successes": total_successes,
            "Log_Likelihood": -9999.0,
            "Boundary_Warning": "Insufficient samples"
        }
        
    # 1. Kleinman Initial Estimate
    mom_mu, mom_M, mom_status = kleinman_corrected_method_of_moments(k_v, n_v)
    
    # 2. Likelihood Optimization
    def objective(params):
        logit_mu, log_M = params
        mu = 1.0 / (1.0 + np.exp(-logit_mu))
        M = np.exp(log_M)
        ll = beta_binomial_log_likelihood(mu, M, k_v, n_v)
        return -ll if np.isfinite(ll) else 1e12

    init_logit_mu = np.log(mom_mu / (1.0 - mom_mu))
    init_log_M = np.log(mom_M)
    init_params = np.array([init_logit_mu, init_log_M])
    
    bounds = [(-9.0, 9.0), (np.log(1.0), np.log(10000.0))]
    
    res = minimize(
        objective,
        init_params,
        method="L-BFGS-B",
        bounds=bounds,
        options={"ftol": 1e-9, "gtol": 1e-7, "maxiter": 200}
    )
    
    boundary_warn = "None"
    if res.success:
        opt_mu = 1.0 / (1.0 + np.exp(-res.x[0]))
        opt_M = np.exp(res.x[1])
        final_mu = float(opt_mu)
        final_M = float(opt_M)
        ll = -float(res.fun)
        conv_status = "CONVERGED_MML"
        msg = str(res.message)
        fallback = False
        
        # Check boundary hit
        if opt_M >= 9900.0 or opt_M <= 1.05:
            boundary_warn = f"M near boundary ({opt_M:.1f})"
    else:
        # Fallback to Kleinman MOM
        final_mu = mom_mu
        final_M = mom_M
        ll = beta_binomial_log_likelihood(final_mu, final_M, k_v, n_v)
        conv_status = "FALLBACK_KLEINMAN_MOM"
        msg = f"Optimizer failed: {res.message}; Kleinman MOM used ({mom_status})"
        fallback = True
        boundary_warn = "Optimizer did not converge; Kleinman MOM active"
        
    alpha = final_mu * final_M
    beta = (1.0 - final_mu) * final_M
    
    return {
        "Entity": entity,
        "Metric": metric_name,
        "Role": role,
        "Fold": fold,
        "Convergence_Status": conv_status,
        "Optimizer_Message": msg,
        "Fallback_Used": fallback,
        "Prior_Mean": final_mu,
        "Effective_M_Prior": final_M,
        "Alpha": alpha,
        "Beta": beta,
        "N_Players": N_players,
        "Total_Trials": total_trials,
        "Total_Successes": total_successes,
        "Log_Likelihood": float(ll),
        "Boundary_Warning": boundary_warn
    }


# ==============================================================================
# 3. NORMAL-NORMAL CONTINUOUS HIERARCHICAL MML CALIBRATION
# ==============================================================================

def fit_normal_normal_safeguarded(
    y: np.ndarray,
    n: np.ndarray,
    s_within: np.ndarray,
    entity: str = "Player",
    metric_name: str = "ContinuousMetric",
    role: str = "Global",
    fold: int = 0
) -> Dict[str, Any]:
    """
    Fits Normal-Normal continuous hierarchical model:
      y_i ~ N(mu_0, tau^2 + s_within_i^2 / n_i)
    DerSimonian-Laird initialization + bounded L-BFGS-B MML estimation.
    """
    mask = (n > 1) & (s_within > 0)
    y_m = y[mask].astype(float)
    n_m = n[mask].astype(float)
    s_m = s_within[mask].astype(float)
    N_players = len(y_m)
    total_volume = int(np.sum(n_m))
    
    if N_players < 3:
        return {
            "Entity": entity,
            "Metric": metric_name,
            "Role": role,
            "Fold": fold,
            "Convergence_Status": "FAIL_INSUFFICIENT_DATA",
            "Prior_Mean": float(np.mean(y)) if len(y) > 0 else 100.0,
            "Between_Player_Tau": 10.0,
            "Effective_M_Prior": 100.0,
            "Fallback_Used": True,
            "Boundary_Warning": "N < 3"
        }
        
    sigma_sq_i = (s_m ** 2) / n_m
    w_fixed = 1.0 / np.maximum(sigma_sq_i, 1e-6)
    mu_dsl = np.sum(w_fixed * y_m) / np.sum(w_fixed)
    q = np.sum(w_fixed * ((y_m - mu_dsl) ** 2))
    df = N_players - 1.0
    c = np.sum(w_fixed) - (np.sum(w_fixed ** 2) / np.sum(w_fixed))
    tau_sq_dsl = max((q - df) / max(c, 1e-6), 1e-4)
    
    def neg_log_lik(params):
        mu_0, log_tau_sq = params
        tau_sq = np.exp(log_tau_sq)
        tot_var = tau_sq + sigma_sq_i
        ll = -0.5 * (np.log(2.0 * np.pi) + np.log(tot_var) + ((y_m - mu_0) ** 2) / tot_var)
        return -np.sum(ll)
        
    init_params = np.array([mu_dsl, np.log(tau_sq_dsl)])
    res = minimize(
        neg_log_lik,
        init_params,
        method="L-BFGS-B",
        bounds=[(None, None), (np.log(1e-6), np.log(1e5))]
    )
    
    if res.success:
        mu_0 = float(res.x[0])
        tau_sq = float(np.exp(res.x[1]))
        conv_status = "CONVERGED_MML"
        fallback = False
    else:
        mu_0 = float(mu_dsl)
        tau_sq = float(tau_sq_dsl)
        conv_status = "FALLBACK_DER_SIMONIAN_LAIRD"
        fallback = True
        
    tau = float(np.sqrt(tau_sq))
    mean_s_sq = float(np.mean(s_m ** 2))
    M_0 = float(mean_s_sq / max(tau_sq, 1e-6))
    
    return {
        "Entity": entity,
        "Metric": metric_name,
        "Role": role,
        "Fold": fold,
        "Convergence_Status": conv_status,
        "Optimizer_Message": str(res.message) if res.success else "DSL used",
        "Fallback_Used": fallback,
        "Prior_Mean": mu_0,
        "Between_Player_Tau": tau,
        "Between_Player_Tau_Sq": tau_sq,
        "Mean_Within_Variance": mean_s_sq,
        "Effective_M_Prior": M_0,
        "N_Players": N_players,
        "Total_Volume": total_volume,
        "Boundary_Warning": "None" if tau_sq > 1e-5 else "Near zero tau"
    }


# ==============================================================================
# 4. METRIC COMPUTATION ENGINE (BRIER, LOG LOSS, CALIBRATION)
# ==============================================================================

def compute_binary_validation_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, float]:
    """
    Computes Brier score, Log Loss, and linear calibration parameters for binary probabilities.
    Clamps probabilities to [1e-15, 1 - 1e-15] to prevent log(0).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    
    # Brier score
    brier = float(np.mean((y_prob - y_true) ** 2))
    
    # Log loss
    eps = 1e-15
    y_prob_c = np.clip(y_prob, eps, 1.0 - eps)
    log_loss = -float(np.mean(y_true * np.log(y_prob_c) + (1.0 - y_true) * np.log(1.0 - y_prob_c)))
    
    # Calibration slope & intercept
    var_p = float(np.var(y_prob))
    if var_p > 1e-8:
        cov = float(np.cov(y_prob, y_true)[0, 1])
        cal_slope = cov / var_p
        cal_int = float(np.mean(y_true) - cal_slope * np.mean(y_prob))
    else:
        cal_slope = 1.0
        cal_int = 0.0
        
    return {
        "Brier_Score": brier,
        "Log_Loss": log_loss,
        "Calibration_Slope": cal_slope,
        "Calibration_Intercept": cal_int,
        "Mean_Predicted_Prob": float(np.mean(y_prob)),
        "Mean_Observed_Rate": float(np.mean(y_true)),
        "Mean_Bias": float(np.mean(y_prob) - np.mean(y_true))
    }


def compute_reliability_table(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """
    Computes binned calibration / reliability table for diagnostic inspection.
    """
    df = pd.DataFrame({"y_true": y_true, "y_prob": y_prob})
    df["bin"] = pd.qcut(df["y_prob"], q=n_bins, duplicates="drop")
    
    table = df.groupby("bin", observed=True).agg(
        delivery_count=("y_true", "count"),
        mean_pred_prob=("y_prob", "mean"),
        empirical_event_rate=("y_true", "mean")
    ).reset_index()
    
    table["calibration_error"] = table["mean_pred_prob"] - table["empirical_event_rate"]
    return table
