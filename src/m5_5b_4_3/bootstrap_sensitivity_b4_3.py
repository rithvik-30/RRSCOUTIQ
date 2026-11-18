"""
RR ScoutIQ — Milestone M5.5-B.4.3: Match-Block Bootstrap Sensitivity Engine
Module: src/m5_5b_4_3/bootstrap_sensitivity_b4_3.py

Investigates bootstrap sensitivity across B in [100, 500, 1000] replicates:
1. Monte Carlo error of variance estimates: MCE = sqrt(2 / (B - 1)) * Var
2. Covariance matrix stability: Frobenius norm relative distance to B=1000 reference
3. Positive semidefiniteness: Minimum eigenvalue lambda_min >= 0
4. Preserves canonical dataset integrity and reports machine-readable diagnostics.
"""

import os
import sys
import time
from typing import Dict, List, Any
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b.baseline_estimation import load_clean_deliveries
from src.m5_5b_4_3.cluster_variance_b4_3 import compute_match_block_bootstrap_covariance


def run_bootstrap_sensitivity_analysis_b43(
    data_path: str = "data/processed/m5_3/match_state_full.csv",
    output_dir: str = "audit_reports/M5_5B_4_3",
    replicate_levels: List[int] = [100, 500, 1000]
) -> pd.DataFrame:
    os.makedirs(output_dir, exist_ok=True)
    print("[M5.5-B.4.3] Loading deliveries for bootstrap sensitivity analysis...")
    df = load_clean_deliveries(data_path)
    
    phases = ["Powerplay", "Middle", "Death"]
    metrics = ["batter_boundary", "bowler_economy"]
    
    records = []
    
    for phase in phases:
        for metric in metrics:
            print(f"\nAnalyzing Phase: {phase} | Metric: {metric}...")
            
            # First compute reference with highest B (1000)
            cov_ref, _, status_ref = compute_match_block_bootstrap_covariance(
                df, phase=phase, metric_type=metric, n_boot=1000
            )
            fro_ref = np.linalg.norm(cov_ref, ord="fro") if cov_ref is not None else 1.0
            
            for B in replicate_levels:
                t0 = time.time()
                cov_mat, _, status = compute_match_block_bootstrap_covariance(
                    df, phase=phase, metric_type=metric, n_boot=B
                )
                dur = time.time() - t0
                
                if cov_mat is not None:
                    eigvals = np.linalg.eigvalsh(cov_mat)
                    lambda_min = float(np.min(eigvals))
                    lambda_max = float(np.max(eigvals))
                    cond_num = float(lambda_max / max(1e-12, lambda_min))
                    trace_val = float(np.trace(cov_mat))
                    is_psd = bool(lambda_min >= -1e-9)
                    
                    # Frobenius distance to B=1000 reference
                    fro_diff = float(np.linalg.norm(cov_mat - cov_ref, ord="fro"))
                    rel_fro_diff = float(fro_diff / max(1e-9, fro_ref))
                    
                    # Mean Monte Carlo Error of diagonal variance estimates
                    diag_vars = np.diag(cov_mat)
                    mce_diag = np.sqrt(2.0 / max(1, B - 1)) * diag_vars
                    mean_mce = float(np.mean(mce_diag))
                    mean_var = float(np.mean(diag_vars))
                else:
                    lambda_min = np.nan
                    lambda_max = np.nan
                    cond_num = np.nan
                    trace_val = np.nan
                    is_psd = False
                    fro_diff = np.nan
                    rel_fro_diff = np.nan
                    mean_mce = np.nan
                    mean_var = np.nan
                    
                records.append({
                    "phase": phase,
                    "metric": metric,
                    "n_boot_replicates": B,
                    "runtime_seconds": float(dur),
                    "matrix_dimension": cov_mat.shape[0] if cov_mat is not None else 0,
                    "trace": trace_val,
                    "lambda_min": lambda_min,
                    "lambda_max": lambda_max,
                    "condition_number": cond_num,
                    "is_positive_semidefinite": is_psd,
                    "mean_cell_variance": mean_var,
                    "mean_monte_carlo_error": mean_mce,
                    "relative_frobenius_dist_to_b1000": rel_fro_diff,
                    "status": status
                })
                print(f"  B={B:4d}: trace={trace_val:.6f}, lambda_min={lambda_min:.6e}, rel_dist={rel_fro_diff:.4f}, time={dur:.2f}s")
                
    df_res = pd.DataFrame(records)
    out_csv = os.path.join(output_dir, "M5_5B_4_3_BOOTSTRAP_SENSITIVITY.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"\n[M5.5-B.4.3] Saved bootstrap sensitivity results to: {out_csv}")
    return df_res


if __name__ == "__main__":
    run_bootstrap_sensitivity_analysis_b43()
