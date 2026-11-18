"""
RR ScoutIQ — Milestone M5.5-B.4.3: Cluster Variance & Multiway Covariance Engine
Module: src/m5_5b_4_3/cluster_variance_b4_3.py

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
    
    if v_twoway <= 0 or not np.isfinite(v_twoway):
        # Finite-sample instability fallback: V_G1 is asymptotically conservative and always positive
        return float(max(0.0, v_g1)), "ONEWAY_CLUSTER_FALLBACK_NEGATIVE_TWOWAY"
        
    return float(v_twoway), "TWOWAY_CLUSTER_VALID"


def compute_match_block_bootstrap_covariance_b43(
    df: pd.DataFrame,
    phase: str,
    metric_type: str = "batter_boundary",
    n_boot: int = 100,
    seed: int = 42
) -> Tuple[np.ndarray, List[str], str]:
    """
    Executes a match-block bootstrap to estimate the empirical covariance matrix
    across all pressure tiers within a phase.
    """
    rng = np.random.default_rng(seed)
    phase_df = df[df["pre_match_phase"].astype(str) == phase].copy()
    unique_matches = phase_df["match_id"].unique()
    n_matches = len(unique_matches)
    
    tiers = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
    
    if n_matches < 10:
        return np.full((len(tiers), len(tiers)), np.nan), tiers, "INSUFFICIENT_CLUSTERS"
        
    match_data = {}
    for mid, m_df in phase_df.groupby("match_id"):
        m_stats = {}
        for tier in tiers:
            c_df = m_df[m_df["pre_pressure_tier"].astype(str) == tier]
            c_legal = c_df[c_df["ext_is_legal_delivery"] == 1]
            if metric_type == "batter_boundary":
                events = c_legal["ext_is_four"].sum() + c_legal["ext_is_six"].sum()
            else:
                events = c_df["ext_bowler_debit_runs"].sum()
            m_stats[tier] = (events, len(c_legal))
        match_data[mid] = m_stats
        
    boot_estimates = []
    for _ in range(n_boot):
        sampled_matches = rng.choice(unique_matches, size=n_matches, replace=True)
        tier_events = {t: 0.0 for t in tiers}
        tier_counts = {t: 0 for t in tiers}
        
        for mid in sampled_matches:
            m_stats = match_data[mid]
            for t in tiers:
                ev, cnt = m_stats[t]
                tier_events[t] += ev
                tier_counts[t] += cnt
                
        boot_row = []
        for t in tiers:
            cnt = tier_counts[t]
            if cnt > 0:
                if metric_type == "batter_boundary":
                    rate = tier_events[t] / cnt
                else:
                    rate = 6.0 * (tier_events[t] / cnt)
            else:
                rate = np.nan
            boot_row.append(rate)
        boot_estimates.append(boot_row)
        
    boot_arr = np.array(boot_estimates, dtype=float)
    valid_cols = ~np.isnan(boot_arr).any(axis=0)
    if valid_cols.sum() < 2:
        return np.full((len(tiers), len(tiers)), np.nan), tiers, "INSUFFICIENT_TIER_SAMPLES"
        
    cov_matrix = np.cov(boot_arr, rowvar=False)
    if cov_matrix.shape != (len(tiers), len(tiers)):
        return np.full((len(tiers), len(tiers)), np.nan), tiers, "INVALID_COVARIANCE_SHAPE"
        
    return cov_matrix, tiers, "BOOTSTRAP_COVARIANCE_SUCCESS"


def compute_multivariate_dersimonian_laird_b43(
    means: np.ndarray,
    cov_matrix: np.ndarray
) -> Tuple[float, str]:
    """
    Multivariate DerSimonian-Laird between-cell variance tau^2 estimation.
    Zero artificial floors: Q <= df -> tau^2 = 0.0.
    """
    k = len(means)
    if k < 2 or cov_matrix is None or np.isnan(cov_matrix).any():
        return np.nan, "INSUFFICIENT_CELLS_OR_NAN_COVARIANCE"
        
    try:
        inv_cov = np.linalg.pinv(cov_matrix)
    except Exception:
        return np.nan, "COVARIANCE_INVERSION_ERROR"
        
    ones = np.ones(k)
    denom_w = ones.T @ inv_cov @ ones
    if denom_w <= 0:
        return np.nan, "SINGULAR_COVARIANCE_WEIGHTS"
        
    w = (inv_cov @ ones) / denom_w
    y_bar = float(w.T @ means)
    
    diff = means - y_bar * ones
    Q = float(diff.T @ inv_cov @ diff)
    df = k - 1
    
    if Q <= df:
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    trace_inv = np.trace(inv_cov)
    quad_term = (ones.T @ (inv_cov @ inv_cov) @ ones) / denom_w
    denom_tau = trace_inv - quad_term
    
    if denom_tau <= 0:
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    tau2 = (Q - df) / denom_tau
    return float(max(0.0, tau2)), "ESTIMATED_POSITIVE"


compute_match_block_bootstrap_covariance = compute_match_block_bootstrap_covariance_b43

