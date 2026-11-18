"""
M5.5-B.4.3.8 Independent Synthetic Simulation Harness
=====================================================
Rigorous Monte Carlo validation of the crossed-effects batter match variance estimator
under known ground truth conditions:
- Repeated players across matches.
- Realistic participation skew (Zipf/power-law batter selection).
- Unequal match exposure (variable deliveries per match).
- Known player variance component tau2_player = 0.0030.
- Known match variance components sigma2_m in {0.0000, 0.0010, 0.0020}.
- Additive linear probability model vs non-linear logistic link.
- 10 seeds per scenario (60 total runs).
"""

import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, Any, List

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.m5_5b_4_3_8.variance_decomposition_b4_3_8 import estimate_batter_crossed_match_variance


def simulate_crossed_batter_dataset(
    n_deliveries: int = 15000,
    n_matches: int = 40,
    n_batters: int = 35,
    tau2_player: float = 0.0030,
    sigma2_match: float = 0.0010,
    link: str = "linear",
    seed: int = 42
) -> pd.DataFrame:
    """
    Generates synthetic crossed batter deliveries with known ground-truth parameters,
    power-law player participation skew, and unequal match exposure.
    """
    rng = np.random.RandomState(seed)
    
    # Context cells: 3 phases x 2 tiers = 6 cells
    phases = ["powerplay", "middle", "death"]
    tiers = ["Tier 1: Low", "Tier 3: High"]
    cells = [(p, t) for p in phases for t in tiers]
    K = len(cells)
    
    # Baseline cell boundary rates
    cell_baseline_probs = {
        ("powerplay", "Tier 1: Low"): 0.17,
        ("powerplay", "Tier 3: High"): 0.19,
        ("middle", "Tier 1: Low"): 0.11,
        ("middle", "Tier 3: High"): 0.13,
        ("death", "Tier 1: Low"): 0.19,
        ("death", "Tier 3: High"): 0.23,
    }
    
    # Latent player effects alpha_i ~ N(0, tau2_player)
    player_effects = rng.normal(0.0, np.sqrt(tau2_player), size=n_batters)
    
    # Latent match environmental shocks delta_m ~ N(0, sigma2_match)
    if sigma2_match > 0.0:
        match_shocks = rng.normal(0.0, np.sqrt(sigma2_match), size=n_matches)
    else:
        match_shocks = np.zeros(n_matches)
        
    # Participation skew: Zipf/power-law sampling probabilities for batters
    zipf_weights = 1.0 / np.power(np.arange(1, n_batters + 1), 0.8)
    zipf_probs = zipf_weights / np.sum(zipf_weights)
    
    # Unequal match exposure: Dirichlet-multinomial match delivery counts
    alpha_m = rng.uniform(2.0, 5.0, size=n_matches)
    match_weights = rng.dirichlet(alpha_m)
    match_deliveries = rng.multinomial(n_deliveries, match_weights)
    
    records = []
    for m in range(n_matches):
        n_m = match_deliveries[m]
        if n_m == 0:
            continue
        
        # Select active batters in this match (skewed sample)
        n_active_batters = min(n_batters, rng.choice([4, 6, 8, 10]))
        active_batters = rng.choice(n_batters, size=n_active_batters, replace=False, p=zipf_probs)
        active_weights = zipf_probs[active_batters] / np.sum(zipf_probs[active_batters])
        
        # Assign deliveries to active batters
        bat_assign = rng.choice(active_batters, size=n_m, p=active_weights)
        # Assign contextual cells (powerplay ~25%, middle ~50%, death ~25%)
        cell_dist = [0.25/2, 0.25/2, 0.50/2, 0.50/2, 0.25/2, 0.25/2]
        cell_assign = rng.choice(K, size=n_m, p=cell_dist)
        
        d_m = match_shocks[m]
        
        for k in range(n_m):
            c_idx = cell_assign[k]
            ph, tr = cells[c_idx]
            b_idx = bat_assign[k]
            a_i = player_effects[b_idx]
            base_p = cell_baseline_probs[(ph, tr)]
            
            if link == "linear":
                p = base_p + a_i + d_m
                p = np.clip(p, 0.01, 0.99)
            elif link == "logistic":
                base_logit = np.log(base_p / (1.0 - base_p))
                # Scale latent variance to match linear scale around baseline
                p_grad = base_p * (1.0 - base_p)
                a_i_logit = a_i / p_grad
                d_m_logit = d_m / p_grad
                p = 1.0 / (1.0 + np.exp(-(base_logit + a_i_logit + d_m_logit)))
                p = np.clip(p, 0.01, 0.99)
            else:
                raise ValueError(f"Unknown link: {link}")
                
            y = 1 if rng.uniform(0.0, 1.0) < p else 0
            
            records.append({
                "match_id": m + 1,
                "batter_id": b_idx + 100,
                "phase": ph,
                "tier": tr,
                "is_boundary": y
            })
            
    return pd.DataFrame(records)


def run_full_simulation_suite(
    n_seeds: int = 10,
    output_csv_path: str = "audit_reports/M5_5B_4_3_8/INDEPENDENT_SYNTHETIC_SIMULATION_RESULTS.csv"
) -> Dict[str, Any]:
    """
    Executes 6 scenarios (3 variance levels x 2 link functions) across n_seeds each (60 runs total).
    Logs all metrics and produces summary table.
    """
    scenarios = [
        {"name": "Linear_Null", "sigma2_match": 0.0000, "link": "linear"},
        {"name": "Linear_Moderate", "sigma2_match": 0.0010, "link": "linear"},
        {"name": "Linear_High", "sigma2_match": 0.0020, "link": "linear"},
        {"name": "Logistic_Null", "sigma2_match": 0.0000, "link": "logistic"},
        {"name": "Logistic_Moderate", "sigma2_match": 0.0010, "link": "logistic"},
        {"name": "Logistic_High", "sigma2_match": 0.0020, "link": "logistic"},
    ]
    
    results = []
    
    for sc in scenarios:
        sc_name = sc["name"]
        s2_true = sc["sigma2_match"]
        link = sc["link"]
        print(f"Executing Scenario: {sc_name} (sigma2_true={s2_true:.4f}, link={link})...")
        
        for s in range(n_seeds):
            seed = 1000 + s * 17
            df_sim = simulate_crossed_batter_dataset(
                n_deliveries=15000,
                n_matches=40,
                n_batters=35,
                tau2_player=0.0030,
                sigma2_match=s2_true,
                link=link,
                seed=seed
            )
            
            fit_res = estimate_batter_crossed_match_variance(
                df_sim,
                cell_cols=("phase", "tier"),
                bat_id_col="batter_id",
                outcome_col="is_boundary",
                method="paule_mandel",
                check_convergence=True
            )
            
            s2_est = fit_res["sigma2_match_bat"]
            bias = s2_est - s2_true
            err_sq = bias ** 2
            
            diag = fit_res["solver_diagnostics"]
            
            results.append({
                "scenario": sc_name,
                "seed": seed,
                "link": link,
                "true_sigma2_match": s2_true,
                "tau2_player": 0.0030,
                "N": len(df_sim),
                "M": fit_res["M"],
                "I": 35,
                "estimated_sigma2_match": s2_est,
                "bias": bias,
                "squared_error": err_sq,
                "status": fit_res["status"],
                "used_method": fit_res["used_method"],
                "Q": fit_res["Q"],
                "df": fit_res["df"],
                "p_value": fit_res["p_value"],
                "solver_converged": fit_res["solver_converged"],
                "rel_diff_chol_lsqr": diag["rel_diff_chol_lsqr"],
                "normal_eq_grad": diag["normal_eq_grad"],
                "asymmetry_frobenius": fit_res["asymmetry_frobenius"],
                "min_eigenvalue": fit_res["min_eigenvalue"],
                "shift_psd": fit_res["shift_psd"]
            })
            
    res_df = pd.DataFrame(results)
    
    # Ensure target directory exists
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    res_df.to_csv(output_csv_path, index=False)
    print(f"Saved full simulation results to: {output_csv_path}")
    
    # Compute summary table per scenario
    summary_rows = []
    for sc in scenarios:
        sc_name = sc["name"]
        sub = res_df[res_df["scenario"] == sc_name]
        s2_true = sc["sigma2_match"]
        
        mean_est = sub["estimated_sigma2_match"].mean()
        mean_bias = sub["bias"].mean()
        rmse = np.sqrt(sub["squared_error"].mean())
        
        if s2_true == 0.0:
            zero_det_rate = (sub["status"] == "ESTIMATED_ZERO").mean()
            false_pos_rate = (sub["status"] == "ESTIMATED_POSITIVE").mean()
        else:
            zero_det_rate = np.nan
            false_pos_rate = np.nan
            
        conv_rate = sub["solver_converged"].mean()
        max_rel_diff = sub["rel_diff_chol_lsqr"].max()
        max_asym = sub["asymmetry_frobenius"].max()
        
        summary_rows.append({
            "Scenario": sc_name,
            "True sigma2_m": s2_true,
            "Link": sc["link"],
            "Mean Estimate": mean_est,
            "Empirical Bias": mean_bias,
            "Empirical RMSE": rmse,
            "Zero Detection Rate": zero_det_rate,
            "False Positive Rate": false_pos_rate,
            "Convergence Rate": conv_rate,
            "Max Rel Diff (Chol vs LSQR)": max_rel_diff,
            "Max Asymmetry ||Omega - Omega^T||_F": max_asym
        })
        
    summary_df = pd.DataFrame(summary_rows)
    print("\nSimulation Benchmark Summary Table:")
    print(summary_df.to_string(index=False))
    
    return {
        "results_df": res_df,
        "summary_df": summary_df
    }


if __name__ == "__main__":
    run_full_simulation_suite()
