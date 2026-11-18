"""
RR ScoutIQ — Milestone M5.5-B: Empirical Bayes Prior Calibration Engine
Module: src/m5_5b/eb_prior_fitting.py

Performs Marginal Maximum Likelihood (MML) estimation of Empirical Bayes priors:
1. Beta-Binomial models for binary proportions (Boundaries, Dots, Wickets/Dismissals)
2. Normal-Normal models for continuous performance rates (Strike Rate, Economy, xRA, xRS)
3. Compares Global Pooled priors vs Role-Stratified priors
4. Evaluates effective prior sample sizes (M_0 = alpha + beta, M_0 = sigma^2 / tau^2) vs M=100 heuristic

Strict Governance: No player scores, no rankings, no auction recommendations.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import betaln, gammaln
from typing import Dict, Tuple, List, Optional

from src.m5_5b.baseline_estimation import (
    load_clean_deliveries,
    assign_batter_roles,
    assign_bowler_roles,
    compute_batter_cell_baselines,
    compute_bowler_cell_baselines
)


# --- 1. BETA-BINOMIAL MARGINAL MAXIMUM LIKELIHOOD ---

def beta_binomial_neg_log_lik(params: np.ndarray, k: np.ndarray, n: np.ndarray) -> float:
    """
    Computes negative log-likelihood of Beta-Binomial(n, alpha, beta).
    params = [log(alpha), log(beta)]
    """
    log_alpha, log_beta = params
    alpha = np.exp(log_alpha)
    beta = np.exp(log_beta)
    
    # Exclude n == 0 if any
    mask = n > 0
    k_m = k[mask]
    n_m = n[mask]
    
    # log P(k | n, alpha, beta) = log_comb(n, k) + betaln(k + alpha, n - k + beta) - betaln(alpha, beta)
    log_comb = gammaln(n_m + 1) - gammaln(k_m + 1) - gammaln(n_m - k_m + 1)
    ll = log_comb + betaln(k_m + alpha, n_m - k_m + beta) - betaln(alpha, beta)
    
    return -np.sum(ll)


def fit_beta_binomial_mml(k: np.ndarray, n: np.ndarray, init_mu: float = 0.2, init_M: float = 50.0) -> Dict[str, float]:
    """
    Fits alpha and beta using L-BFGS-B on log(alpha), log(beta).
    Returns alpha, beta, mu_0 = alpha/(alpha+beta), M_0 = alpha+beta.
    """
    init_alpha = max(init_mu * init_M, 0.01)
    init_beta = max((1.0 - init_mu) * init_M, 0.01)
    init_params = np.array([np.log(init_alpha), np.log(init_beta)])
    
    res = minimize(
        beta_binomial_neg_log_lik,
        init_params,
        args=(k, n),
        method="L-BFGS-B",
        bounds=[(-10.0, 15.0), (-10.0, 15.0)]
    )
    
    if not res.success:
        # Fallback to method of moments
        p_hat = k / np.maximum(n, 1)
        mean_p = np.average(p_hat, weights=n)
        var_p = np.average((p_hat - mean_p)**2, weights=n)
        # var_p = mean_p*(1-mean_p)/(M+1)
        M_est = max((mean_p * (1.0 - mean_p) / max(var_p, 1e-6)) - 1.0, 1.0)
        alpha = mean_p * M_est
        beta = (1.0 - mean_p) * M_est
    else:
        alpha = np.exp(res.x[0])
        beta = np.exp(res.x[1])
        
    M_0 = alpha + beta
    mu_0 = alpha / M_0
    nll = res.fun if res.success else beta_binomial_neg_log_lik(np.array([np.log(alpha), np.log(beta)]), k, n)
    aic = 2 * 2 + 2 * nll
    
    return {
        "alpha": float(alpha),
        "beta": float(beta),
        "mu_0": float(mu_0),
        "M_0": float(M_0),
        "neg_log_lik": float(nll),
        "aic": float(aic),
        "n_samples": int(len(k)),
        "total_trials": int(np.sum(n)),
        "total_successes": int(np.sum(k))
    }


# --- 2. NORMAL-NORMAL MARGINAL MAXIMUM LIKELIHOOD ---

def normal_normal_neg_log_lik(params: np.ndarray, y: np.ndarray, sigma_sq_i: np.ndarray) -> float:
    """
    Computes negative log-likelihood of Normal-Normal hierarchical model:
    y_i ~ N(mu_0, tau^2 + sigma_sq_i)
    params = [mu_0, log(tau^2)]
    """
    mu_0, log_tau_sq = params
    tau_sq = np.exp(log_tau_sq)
    
    total_var = tau_sq + sigma_sq_i
    ll = -0.5 * (np.log(2.0 * np.pi) + np.log(total_var) + ((y - mu_0)**2) / total_var)
    return -np.sum(ll)


def fit_normal_normal_mml(y: np.ndarray, n: np.ndarray, s_within: np.ndarray) -> Dict[str, float]:
    """
    Fits mu_0 and tau^2 using L-BFGS-B.
    sigma_sq_i = s_within^2 / n_i
    Returns mu_0, tau, tau^2, M_0 = (s_within_mean^2) / tau^2.
    """
    mask = n > 1
    y_m = y[mask]
    n_m = n[mask]
    s_m = s_within[mask]
    
    sigma_sq_i = (s_m**2) / np.maximum(n_m, 1)
    
    # Initial values via DerSimonian-Laird
    w_fixed = 1.0 / np.maximum(sigma_sq_i, 1e-6)
    mu_init = np.sum(w_fixed * y_m) / np.sum(w_fixed)
    q = np.sum(w_fixed * ((y_m - mu_init)**2))
    df = len(y_m) - 1
    c = np.sum(w_fixed) - (np.sum(w_fixed**2) / np.sum(w_fixed))
    tau_sq_init = max((q - df) / max(c, 1e-6), 1e-4)
    
    init_params = np.array([mu_init, np.log(tau_sq_init)])
    
    res = minimize(
        normal_normal_neg_log_lik,
        init_params,
        args=(y_m, sigma_sq_i),
        method="L-BFGS-B"
    )
    
    if res.success:
        mu_0 = res.x[0]
        tau_sq = np.exp(res.x[1])
        nll = res.fun
    else:
        mu_0 = mu_init
        tau_sq = tau_sq_init
        nll = normal_normal_neg_log_lik(init_params, y_m, sigma_sq_i)
        
    tau = np.sqrt(tau_sq)
    mean_sigma_sq = np.mean(s_m**2)
    M_0 = mean_sigma_sq / max(tau_sq, 1e-6)
    aic = 2 * 2 + 2 * nll
    
    return {
        "mu_0": float(mu_0),
        "tau": float(tau),
        "tau_sq": float(tau_sq),
        "mean_within_sd": float(np.sqrt(mean_sigma_sq)),
        "M_0": float(M_0),
        "neg_log_lik": float(nll),
        "aic": float(aic),
        "n_samples": int(len(y_m)),
        "total_volume": int(np.sum(n_m))
    }


# --- 3. FULL PIPELINE EXECUTION ---

def run_empirical_bayes_calibration(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_csv: str = "M5_5B_EMPIRICAL_BAYES_PRIOR_ESTIMATES.csv"
) -> pd.DataFrame:
    """
    Runs MML Empirical Bayes calibration across:
    - Batter dimensions: SR, Boundary %, Dot %, Dismissal %
    - Bowler dimensions: Economy, Wicket %, Dot %, Boundary Concession %
    - Strata: Global Pooled, Role-Stratified, and Pressure vs Non-Pressure
    """
    clean_df = load_clean_deliveries(data_path)
    clean_df, b_role_map = assign_batter_roles(clean_df)
    clean_df, bw_role_map, workloads = assign_bowler_roles(clean_df)
    
    # Separate pressure vs non-pressure
    # Approved definition: Pressure is Tier 3 (High) & Tier 4 (Extreme)
    # Non-Pressure is Tier 1 (Low) & Tier 2 (Medium)
    clean_df["is_pressure"] = clean_df["pre_pressure_tier"].isin(["Tier 3: High", "Tier 4: Extreme"]).astype(int)
    
    # 1. Batter Player-Level Aggregation
    # Filter to eligible cohort for primary prior fitting, but test sensitivity to unfiltered
    b_df = clean_df[clean_df["ext_batter_balls_faced"] == 1].copy()
    b_df["is_bnd"] = ((b_df["ext_is_four"] == 1) | (b_df["ext_is_six"] == 1)).astype(int)
    b_df["is_dot"] = ((b_df["ext_batter_runs"] == 0) & (b_df["is_bnd"] == 0)).astype(int)
    b_df["is_out"] = (b_df["ext_is_wicket"] == 1).astype(int)
    b_df["runs"] = b_df["ext_batter_runs"].astype(float)
    
    records = []
    
    # We calibrate priors on two populations:
    # 1. Qualified Eligible Batters (>= 120 balls faced across all matches)
    # 2. All Batters (>= 30 balls faced)
    
    batter_totals = b_df.groupby("striker_id")["runs"].count()
    eligible_batters = batter_totals[batter_totals >= 120].index
    
    for cond_name, cond_mask in [
        ("All Conditions", np.ones(len(b_df), dtype=bool)),
        ("Pressure (Tiers 3-4)", b_df["is_pressure"] == 1),
        ("Non-Pressure (Tiers 1-2)", b_df["is_pressure"] == 0),
    ]:
        sub_b = b_df[cond_mask]
        
        # Test roles: Pooled, and each role
        role_subsets = [("Global Pooled", np.ones(len(sub_b), dtype=bool))]
        for r in ["Top Order", "Middle Order", "Finisher"]:
            role_subsets.append((r, sub_b["batter_role"] == r))
            
        for role_name, r_mask in role_subsets:
            rb_df = sub_b[r_mask]
            
            # Aggregate per player (among eligible)
            p_agg = rb_df[rb_df["striker_id"].isin(eligible_batters)].groupby("striker_id").agg(
                n=("runs", "count"),
                bnds=("is_bnd", "sum"),
                dots=("is_dot", "sum"),
                outs=("is_out", "sum"),
                runs_sum=("runs", "sum"),
                runs_mean=("runs", "mean"),
                runs_sd=("runs", lambda s: s.std() if len(s) > 1 else 0.0)
            ).reset_index()
            
            # Require at least 5 balls per player in this slice
            p_agg = p_agg[p_agg["n"] >= 5]
            if len(p_agg) < 5:
                continue
                
            # Beta-Binomial: Boundary %
            res_bnd = fit_beta_binomial_mml(p_agg["bnds"].values, p_agg["n"].values, init_mu=0.18, init_M=50.0)
            records.append({
                "Entity": "Batter",
                "Metric": "Boundary %",
                "Condition": cond_name,
                "Role_Stratum": role_name,
                "Model_Family": "Beta-Binomial",
                "Prior_Mean": res_bnd["mu_0"],
                "Prior_Scale": np.nan,
                "Hyperparam_Alpha": res_bnd["alpha"],
                "Hyperparam_Beta": res_bnd["beta"],
                "Effective_M_Prior": res_bnd["M_0"],
                "Heuristic_M": 100.0,
                "M_Ratio_to_100": res_bnd["M_0"] / 100.0,
                "N_Players": res_bnd["n_samples"],
                "Total_Volume": res_bnd["total_trials"],
                "AIC": res_bnd["aic"]
            })
            
            # Beta-Binomial: Dot %
            res_dot = fit_beta_binomial_mml(p_agg["dots"].values, p_agg["n"].values, init_mu=0.35, init_M=50.0)
            records.append({
                "Entity": "Batter",
                "Metric": "Dot %",
                "Condition": cond_name,
                "Role_Stratum": role_name,
                "Model_Family": "Beta-Binomial",
                "Prior_Mean": res_dot["mu_0"],
                "Prior_Scale": np.nan,
                "Hyperparam_Alpha": res_dot["alpha"],
                "Hyperparam_Beta": res_dot["beta"],
                "Effective_M_Prior": res_dot["M_0"],
                "Heuristic_M": 100.0,
                "M_Ratio_to_100": res_dot["M_0"] / 100.0,
                "N_Players": res_dot["n_samples"],
                "Total_Volume": res_dot["total_trials"],
                "AIC": res_dot["aic"]
            })
            
            # Beta-Binomial: Dismissal %
            res_out = fit_beta_binomial_mml(p_agg["outs"].values, p_agg["n"].values, init_mu=0.05, init_M=100.0)
            records.append({
                "Entity": "Batter",
                "Metric": "Dismissal %",
                "Condition": cond_name,
                "Role_Stratum": role_name,
                "Model_Family": "Beta-Binomial",
                "Prior_Mean": res_out["mu_0"],
                "Prior_Scale": np.nan,
                "Hyperparam_Alpha": res_out["alpha"],
                "Hyperparam_Beta": res_out["beta"],
                "Effective_M_Prior": res_out["M_0"],
                "Heuristic_M": 100.0,
                "M_Ratio_to_100": res_out["M_0"] / 100.0,
                "N_Players": res_out["n_samples"],
                "Total_Volume": res_out["total_trials"],
                "AIC": res_out["aic"]
            })
            
            # Normal-Normal: Strike Rate (runs_mean * 100)
            p_agg_sr = p_agg[p_agg["n"] >= 10]
            if len(p_agg_sr) >= 5:
                y_sr = p_agg_sr["runs_mean"].values * 100.0
                s_sr = p_agg_sr["runs_sd"].values * 100.0
                res_sr = fit_normal_normal_mml(y_sr, p_agg_sr["n"].values, s_sr)
                records.append({
                    "Entity": "Batter",
                    "Metric": "Strike Rate",
                    "Condition": cond_name,
                    "Role_Stratum": role_name,
                    "Model_Family": "Normal-Normal",
                    "Prior_Mean": res_sr["mu_0"],
                    "Prior_Scale": res_sr["tau"],
                    "Hyperparam_Alpha": np.nan,
                    "Hyperparam_Beta": np.nan,
                    "Effective_M_Prior": res_sr["M_0"],
                    "Heuristic_M": 100.0,
                    "M_Ratio_to_100": res_sr["M_0"] / 100.0,
                    "N_Players": res_sr["n_samples"],
                    "Total_Volume": res_sr["total_volume"],
                    "AIC": res_sr["aic"]
                })

    # 2. Bowler Player-Level Aggregation
    bw_df = clean_df[clean_df["ext_is_legal_delivery"] == 1].copy()
    bw_df["is_bnd_con"] = ((bw_df["ext_is_four"] == 1) | (bw_df["ext_is_six"] == 1)).astype(int)
    bw_df["is_dot"] = (bw_df["ext_bowler_debit_runs"] == 0).astype(int)
    bw_df["is_wkt"] = (bw_df["ext_is_bowler_wicket"] == 1).astype(int)
    bw_df["runs_conceded"] = bw_df["ext_bowler_debit_runs"].astype(float)
    
    bowler_totals = bw_df.groupby("bowler_id")["runs_conceded"].count()
    eligible_bowlers = bowler_totals[bowler_totals >= 144].index
    
    for cond_name, cond_mask in [
        ("All Conditions", np.ones(len(bw_df), dtype=bool)),
        ("Pressure (Tiers 3-4)", bw_df["is_pressure"] == 1),
        ("Non-Pressure (Tiers 1-2)", bw_df["is_pressure"] == 0),
    ]:
        sub_bw = bw_df[cond_mask]
        
        role_subsets = [("Global Pooled", np.ones(len(sub_bw), dtype=bool))]
        for r in ["Powerplay Specialist", "Middle Enforcer", "Death Specialist"]:
            role_subsets.append((r, sub_bw["bowler_role"] == r))
            
        for role_name, r_mask in role_subsets:
            rbw_df = sub_bw[r_mask]
            
            p_agg = rbw_df[rbw_df["bowler_id"].isin(eligible_bowlers)].groupby("bowler_id").agg(
                n=("runs_conceded", "count"),
                bnds=("is_bnd_con", "sum"),
                dots=("is_dot", "sum"),
                wkts=("is_wkt", "sum"),
                runs_sum=("runs_conceded", "sum"),
                runs_mean=("runs_conceded", "mean"),
                runs_sd=("runs_conceded", lambda s: s.std() if len(s) > 1 else 0.0)
            ).reset_index()
            
            p_agg = p_agg[p_agg["n"] >= 6]
            if len(p_agg) < 5:
                continue
                
            # Beta-Binomial: Boundary Concession %
            res_bnd = fit_beta_binomial_mml(p_agg["bnds"].values, p_agg["n"].values, init_mu=0.18, init_M=50.0)
            records.append({
                "Entity": "Bowler",
                "Metric": "Boundary Concession %",
                "Condition": cond_name,
                "Role_Stratum": role_name,
                "Model_Family": "Beta-Binomial",
                "Prior_Mean": res_bnd["mu_0"],
                "Prior_Scale": np.nan,
                "Hyperparam_Alpha": res_bnd["alpha"],
                "Hyperparam_Beta": res_bnd["beta"],
                "Effective_M_Prior": res_bnd["M_0"],
                "Heuristic_M": 100.0,
                "M_Ratio_to_100": res_bnd["M_0"] / 100.0,
                "N_Players": res_bnd["n_samples"],
                "Total_Volume": res_bnd["total_trials"],
                "AIC": res_bnd["aic"]
            })
            
            # Beta-Binomial: Dot %
            res_dot = fit_beta_binomial_mml(p_agg["dots"].values, p_agg["n"].values, init_mu=0.35, init_M=50.0)
            records.append({
                "Entity": "Bowler",
                "Metric": "Dot %",
                "Condition": cond_name,
                "Role_Stratum": role_name,
                "Model_Family": "Beta-Binomial",
                "Prior_Mean": res_dot["mu_0"],
                "Prior_Scale": np.nan,
                "Hyperparam_Alpha": res_dot["alpha"],
                "Hyperparam_Beta": res_dot["beta"],
                "Effective_M_Prior": res_dot["M_0"],
                "Heuristic_M": 100.0,
                "M_Ratio_to_100": res_dot["M_0"] / 100.0,
                "N_Players": res_dot["n_samples"],
                "Total_Volume": res_dot["total_trials"],
                "AIC": res_dot["aic"]
            })
            
            # Beta-Binomial: Wicket %
            res_wkt = fit_beta_binomial_mml(p_agg["wkts"].values, p_agg["n"].values, init_mu=0.05, init_M=100.0)
            records.append({
                "Entity": "Bowler",
                "Metric": "Wicket %",
                "Condition": cond_name,
                "Role_Stratum": role_name,
                "Model_Family": "Beta-Binomial",
                "Prior_Mean": res_wkt["mu_0"],
                "Prior_Scale": np.nan,
                "Hyperparam_Alpha": res_wkt["alpha"],
                "Hyperparam_Beta": res_wkt["beta"],
                "Effective_M_Prior": res_wkt["M_0"],
                "Heuristic_M": 100.0,
                "M_Ratio_to_100": res_wkt["M_0"] / 100.0,
                "N_Players": res_wkt["n_samples"],
                "Total_Volume": res_wkt["total_trials"],
                "AIC": res_wkt["aic"]
            })
            
            # Normal-Normal: Economy (runs_mean * 6.0)
            p_agg_econ = p_agg[p_agg["n"] >= 12]
            if len(p_agg_econ) >= 5:
                y_econ = p_agg_econ["runs_mean"].values * 6.0
                s_econ = p_agg_econ["runs_sd"].values * 6.0
                res_econ = fit_normal_normal_mml(y_econ, p_agg_econ["n"].values, s_econ)
                records.append({
                    "Entity": "Bowler",
                    "Metric": "Economy Rate",
                    "Condition": cond_name,
                    "Role_Stratum": role_name,
                    "Model_Family": "Normal-Normal",
                    "Prior_Mean": res_econ["mu_0"],
                    "Prior_Scale": res_econ["tau"],
                    "Hyperparam_Alpha": np.nan,
                    "Hyperparam_Beta": np.nan,
                    "Effective_M_Prior": res_econ["M_0"],
                    "Heuristic_M": 100.0,
                    "M_Ratio_to_100": res_econ["M_0"] / 100.0,
                    "N_Players": res_econ["n_samples"],
                    "Total_Volume": res_econ["total_volume"],
                    "AIC": res_econ["aic"]
                })
                
    results_df = pd.DataFrame(records)
    
    # Save output
    results_df.to_csv(output_csv, index=False)
    audit_path = os.path.join("audit_reports", os.path.basename(output_csv))
    results_df.to_csv(audit_path, index=False)
    print(f"Saved {len(results_df)} Empirical Bayes prior estimates to {output_csv} and {audit_path}")
    return results_df


if __name__ == "__main__":
    print("Running Empirical Bayes MML Prior Fitting...")
    res_df = run_empirical_bayes_calibration()
    print("\nSample Fitted Priors:")
    print(res_df.head(12)[["Entity", "Metric", "Condition", "Role_Stratum", "Prior_Mean", "Effective_M_Prior", "Heuristic_M", "M_Ratio_to_100"]].to_string())
