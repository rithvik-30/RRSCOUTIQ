"""
RR ScoutIQ — Milestone M5.5-B.4.3.1: Cluster Variance & Multiway Covariance Engine
Module: src/m5_5b_4_3_1/cluster_variance_b4_3_1.py

Implements:
1. Two-way cluster-robust variance estimation (Cameron, Gelbach, Miller 2011):
   - Primary cluster: match_id (G1)
   - Secondary cluster: player_id (G2)
   - Intersection: match_id x player_id (G12)
   - Formula: V_twoway = V_G1 + V_G2 - V_G12
   - Finite-sample degrees of freedom corrections: (G / (G - 1)) * ((N - 1) / N)
   - Robust fallback when V_twoway < 0 or G2 has < 5 clusters.
2. Match-block bootstrap for empirical cross-tier covariance:
   - Resamples entire matches with replacement.
   - Preserves delivery correlation, spell composition, and cross-tier dependence.
3. Multivariate DerSimonian-Laird heterogeneity without positive floors.
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd


def compute_two_way_cluster_variance(
    residuals: np.ndarray,
    cluster_match: np.ndarray,
    cluster_player: np.ndarray
) -> Tuple[float, str]:
    """
    Computes Cameron-Gelbach-Miller two-way cluster-robust variance of the mean.
    Estimand: Mean of residuals (e.g. loss series or prediction errors).
    """
    n = len(residuals)
    if n <= 1:
        return np.nan, "INSUFFICIENT_OBSERVATIONS"
        
    u_match = len(np.unique(cluster_match))
    if u_match < 5:
        return np.nan, "INSUFFICIENT_MATCH_CLUSTERS"
        
    # G1: Match cluster variance
    df_g1 = pd.DataFrame({"e": residuals, "g1": cluster_match})
    sums_g1 = df_g1.groupby("g1")["e"].sum().values
    v_g1 = np.sum(sums_g1 ** 2) / (n ** 2)
    adj_g1 = (u_match / (u_match - 1)) if u_match > 1 else 1.0
    v_g1 *= adj_g1
    
    # Check G2: Player clusters
    u_player = len(np.unique(cluster_player))
    if u_player < 5:
        return float(max(0.0, v_g1)), "ONEWAY_CLUSTER_FALLBACK_PLAYER_SPARSE"
        
    # G2: Player cluster variance
    df_g2 = pd.DataFrame({"e": residuals, "g2": cluster_player})
    sums_g2 = df_g2.groupby("g2")["e"].sum().values
    v_g2 = np.sum(sums_g2 ** 2) / (n ** 2)
    adj_g2 = (u_player / (u_player - 1)) if u_player > 1 else 1.0
    v_g2 *= adj_g2
    
    # G12: Match x Player cluster variance
    g12 = [f"{m}_{p}" for m, p in zip(cluster_match, cluster_player)]
    u_g12 = len(np.unique(g12))
    df_g12 = pd.DataFrame({"e": residuals, "g12": g12})
    sums_g12 = df_g12.groupby("g12")["e"].sum().values
    v_g12 = np.sum(sums_g12 ** 2) / (n ** 2)
    adj_g12 = (u_g12 / (u_g12 - 1)) if u_g12 > 1 else 1.0
    v_g12 *= adj_g12
    
    v_twoway = v_g1 + v_g2 - v_g12
    
    if v_twoway > 0:
        return float(v_twoway), "TWOWAY_CLUSTER_VALID"
    else:
        # Standard CGM non-negative fallback to primary match cluster variance
        return float(max(0.0, v_g1)), "ONEWAY_CLUSTER_FALLBACK_NEGATIVE_TWOWAY"


def compute_match_block_bootstrap_covariance(
    df: pd.DataFrame,
    domain: str = "bowler",
    phase: str = "Death",
    n_boot: int = 100,
    seed: int = 42
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Computes an empirical cross-tier covariance matrix using Match-Block Bootstrap.
    Resamples matches with replacement to preserve cross-tier correlation structures.
    Guarantees positive semi-definiteness via eigenvalue clipping.
    """
    rng = np.random.RandomState(seed)
    
    # Filter to phase
    phase_df = df[df["pre_match_phase"] == phase].copy()
    matches = phase_df["match_id"].unique()
    n_matches = len(matches)
    
    if n_matches < 10:
        return np.eye(4) * 0.05, {"status": "INSUFFICIENT_MATCHES_FOR_BOOTSTRAP", "n_matches": n_matches}
        
    tiers = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
    k_dim = len(tiers)
    
    # Pre-index match slices for speed
    match_groups = {m: grp for m, grp in phase_df.groupby("match_id")}
    
    tier_means_boot = np.zeros((n_boot, k_dim))
    
    for b in range(n_boot):
        sample_matches = rng.choice(matches, size=n_matches, replace=True)
        # Concatenate sampled matches
        sampled_rows = pd.concat([match_groups[m] for m in sample_matches], ignore_index=True)
        
        # Calculate metric by tier
        if domain == "bowler":
            tier_agg = sampled_rows.groupby("pre_pressure_tier").apply(
                lambda g: (g["ext_bowler_debit_runs"].sum() / max(1, g["ext_is_legal_delivery"].sum())) * 6.0,
                include_groups=False
            ).to_dict()
        else:
            tier_agg = sampled_rows.groupby("pre_pressure_tier").apply(
                lambda g: g["is_boundary"].sum() / max(1, g["is_legal"].sum()),
                include_groups=False
            ).to_dict()
            
        for t_idx, tier_name in enumerate(tiers):
            tier_means_boot[b, t_idx] = tier_agg.get(tier_name, np.nan)
            
    # Impute missing bootstrap replicates with column means
    col_means = np.nanmean(tier_means_boot, axis=0)
    for t_idx in range(k_dim):
        inds = np.isnan(tier_means_boot[:, t_idx])
        tier_means_boot[inds, t_idx] = col_means[t_idx] if np.isfinite(col_means[t_idx]) else 0.0
        
    # Covariance across replicates
    cov_matrix = np.cov(tier_means_boot, rowvar=False)
    
    # PSD Guarantee via SVD/Eigenvalue clipping
    eigvals, eigvecs = np.linalg.eigh(cov_matrix)
    min_eig = float(np.min(eigvals))
    is_psd_initial = bool(min_eig >= 0)
    
    # Clip negative eigenvalues to numerical epsilon
    eigvals_clipped = np.maximum(eigvals, 1e-8)
    cov_psd = eigvecs @ np.diag(eigvals_clipped) @ eigvecs.T
    
    # Symmetrize
    cov_psd = 0.5 * (cov_psd + cov_psd.T)
    
    meta = {
        "status": "BOOTSTRAP_COVARIANCE_SUCCESS",
        "n_boot": n_boot,
        "n_matches": n_matches,
        "initial_min_eigenvalue": min_eig,
        "is_psd_initial": is_psd_initial,
        "final_min_eigenvalue": float(np.min(np.linalg.eigvalsh(cov_psd))),
        "tier_labels": tiers
    }
    
    return cov_psd, meta


def estimate_multivariate_dersimonian_laird(
    y_vectors: np.ndarray,
    v_matrices: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Multivariate DerSimonian-Laird meta-analytic variance estimator across players/cells.
    Estimates between-player heterogeneity covariance Sigma_tau2.
    Strictly avoids artificial positive floors: genuine zero heterogeneity yields 0.0.
    """
    n_obs, k_dim = y_vectors.shape
    if n_obs < 2:
        return np.mean(y_vectors, axis=0), np.zeros((k_dim, k_dim)), {"status": "INSUFFICIENT_OBSERVATIONS"}
        
    # Fixed-effects initial weights
    w_sum = np.zeros((k_dim, k_dim))
    wy_sum = np.zeros(k_dim)
    
    for i in range(n_obs):
        v_i = v_matrices[i]
        try:
            w_i = np.linalg.pinv(v_i)
        except np.linalg.LinAlgError:
            w_i = np.eye(k_dim) / (1e-4 + np.trace(v_i) / k_dim)
        w_sum += w_i
        wy_sum += w_i @ y_vectors[i]
        
    try:
        mu_fe = np.linalg.pinv(w_sum) @ wy_sum
    except np.linalg.LinAlgError:
        mu_fe = np.mean(y_vectors, axis=0)
        
    # Generalized Q-statistic
    q_stat = np.zeros((k_dim, k_dim))
    for i in range(n_obs):
        diff = (y_vectors[i] - mu_fe).reshape(-1, 1)
        q_stat += diff @ diff.T
        
    # DerSimonian-Laird degrees of freedom adjustment
    df_val = float(n_obs - 1)
    trace_w = float(np.trace(w_sum))
    
    # Unbiased heterogeneity estimate
    if trace_w > 0:
        c_denom = trace_w - (float(np.trace(w_sum @ w_sum)) / trace_w)
        c_denom = max(1e-6, c_denom)
        tau2_unconstrained = (q_stat - np.mean(v_matrices, axis=0) * df_val) / c_denom
    else:
        tau2_unconstrained = np.zeros((k_dim, k_dim))
        
    # Spectral decomposition: clip strictly at 0.0 (zero floor, NO positive floor)
    eigvals, eigvecs = np.linalg.eigh(tau2_unconstrained)
    eigvals_clipped = np.maximum(eigvals, 0.0)
    tau2_psd = eigvecs @ np.diag(eigvals_clipped) @ eigvecs.T
    tau2_psd = 0.5 * (tau2_psd + tau2_psd.T)
    
    # Final random-effects pooled mean
    w_re_sum = np.zeros((k_dim, k_dim))
    w_re_y_sum = np.zeros(k_dim)
    
    for i in range(n_obs):
        v_total = v_matrices[i] + tau2_psd
        w_re = np.linalg.pinv(v_total)
        w_re_sum += w_re
        w_re_y_sum += w_re @ y_vectors[i]
        
    try:
        mu_re = np.linalg.pinv(w_re_sum) @ w_re_y_sum
    except np.linalg.LinAlgError:
        mu_re = mu_fe
        
    meta = {
        "status": "MULTIVARIATE_DSL_SUCCESS",
        "n_obs": n_obs,
        "q_trace": float(np.trace(q_stat)),
        "tau2_trace": float(np.trace(tau2_psd)),
        "is_zero_heterogeneity": bool(np.all(eigvals_clipped == 0.0))
    }
    
    return mu_re, tau2_psd, meta
