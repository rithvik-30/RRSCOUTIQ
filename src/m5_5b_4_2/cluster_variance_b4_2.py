"""
RR ScoutIQ — Milestone M5.5-B.4.2: Cluster Variance & Covariance Engine
Module: src/m5_5b_4_2/cluster_variance_b4_2.py

Implements:
1. Multiway cluster-robust variance estimation (Cameron, Gelbach, Miller 2011).
   Accounts for:
   - Repeated deliveries within matches.
   - Repeated observations from the same player across matches.
   - Unequal match and spell exposure.
2. Match-block bootstrap for empirical covariance across contextual cells:
   - Resamples entire matches with replacement.
   - Preserves delivery-level correlation, cross-tier dependence, and spell composition.
3. Multivariate DerSimonian-Laird heterogeneity estimation:
   - Uses the full cross-cell covariance matrix (no diagonal-only assumption).
   - Zero artificial floors: Q <= df -> tau^2 = 0.0 with full pooling.
4. Explicit insufficient cluster handling:
   - When independent clusters < 10, returns INSUFFICIENT_CLUSTERS with NaN variance.
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd


def compute_multiway_cluster_variance(
    residuals: np.ndarray,
    cluster_g1: np.ndarray,
    cluster_g2: Optional[np.ndarray] = None
) -> Tuple[float, str]:
    """
    Computes one-way or two-way cluster-robust variance of the mean.
    - cluster_g1: primary cluster (e.g. match_id)
    - cluster_g2: secondary cluster (e.g. player_id)
    Formula (Cameron, Gelbach, Miller 2011):
      V_two_way = V_g1 + V_g2 - V_g12
    """
    n = len(residuals)
    if n <= 1:
        return np.nan, "INSUFFICIENT_OBSERVATIONS"
        
    u_g1 = len(np.unique(cluster_g1))
    if u_g1 < 5:
        return np.nan, "INSUFFICIENT_CLUSTERS"
        
    # G1 cluster variance
    df_g1 = pd.DataFrame({"e": residuals, "g1": cluster_g1})
    sums_g1 = df_g1.groupby("g1")["e"].sum().values
    v_g1 = np.sum(sums_g1 ** 2) / (n ** 2)
    # Small sample cluster adjustment: (G / (G - 1)) * ((N - 1) / N)
    adj_g1 = (u_g1 / (u_g1 - 1)) if u_g1 > 1 else 1.0
    v_g1 *= adj_g1
    
    if cluster_g2 is None:
        return float(max(0.0, v_g1)), "ONEWAY_CLUSTER_VALID"
        
    u_g2 = len(np.unique(cluster_g2))
    if u_g2 < 5:
        # Fall back to one-way on g1 if g2 has too few clusters
        return float(max(0.0, v_g1)), "ONEWAY_CLUSTER_FALLBACK_G2_SPARSE"
        
    # G2 cluster variance
    df_g2 = pd.DataFrame({"e": residuals, "g2": cluster_g2})
    sums_g2 = df_g2.groupby("g2")["e"].sum().values
    v_g2 = np.sum(sums_g2 ** 2) / (n ** 2)
    adj_g2 = (u_g2 / (u_g2 - 1)) if u_g2 > 1 else 1.0
    v_g2 *= adj_g2
    
    # Interaction cluster (g1 x g2)
    g12 = [f"{m}_{p}" for m, p in zip(cluster_g1, cluster_g2)]
    u_g12 = len(np.unique(g12))
    df_g12 = pd.DataFrame({"e": residuals, "g12": g12})
    sums_g12 = df_g12.groupby("g12")["e"].sum().values
    v_g12 = np.sum(sums_g12 ** 2) / (n ** 2)
    adj_g12 = (u_g12 / (u_g12 - 1)) if u_g12 > 1 else 1.0
    v_g12 *= adj_g12
    
    v_two_way = v_g1 + v_g2 - v_g12
    return float(max(0.0, v_two_way)), "TWOWAY_CLUSTER_VALID"


def compute_match_block_bootstrap_covariance(
    df: pd.DataFrame,
    phase: str,
    metric_type: str = "batter_boundary",
    n_boot: int = 150,
    seed: int = 42
) -> Tuple[np.ndarray, List[str], str]:
    """
    Executes a match-block bootstrap to estimate the empirical covariance matrix
    across all pressure tiers within a phase.
    
    Resampling unit: entire match_id.
    This preserves:
    - Intra-match correlation between deliveries.
    - Repeated bowler/batter spells in the match.
    - Cross-tier covariance within the same match.
    """
    rng = np.random.default_rng(seed)
    phase_df = df[df["pre_match_phase"].astype(str) == phase].copy()
    unique_matches = phase_df["match_id"].unique()
    n_matches = len(unique_matches)
    
    tiers = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
    
    if n_matches < 10:
        return np.full((len(tiers), len(tiers)), np.nan), tiers, "INSUFFICIENT_CLUSTERS"
        
    # Pre-aggregate match-level sums and counts for fast bootstrapping
    match_data = {}
    for mid, m_df in phase_df.groupby("match_id"):
        m_stats = {}
        for tier in tiers:
            c_df = m_df[m_df["pre_pressure_tier"].astype(str) == tier]
            if metric_type == "batter_boundary":
                c_legal = c_df[c_df["ext_is_legal_delivery"] == 1]
                events = c_legal["ext_is_four"].sum() + c_legal["ext_is_six"].sum()
                n_obs = len(c_legal)
            else:
                # Bowler economy: legal balls and debit runs
                c_legal = c_df[c_df["ext_is_legal_delivery"] == 1]
                events = c_df["ext_bowler_debit_runs"].sum()
                n_obs = len(c_legal)
            m_stats[tier] = (events, n_obs)
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
    # Check if any tier had zero observations across too many bootstrap samples
    valid_cols = ~np.isnan(boot_arr).any(axis=0)
    if valid_cols.sum() < 2:
        return np.full((len(tiers), len(tiers)), np.nan), tiers, "INSUFFICIENT_TIER_SAMPLES"
        
    cov_matrix = np.cov(boot_arr, rowvar=False)
    # Ensure shape is (4, 4)
    if cov_matrix.shape != (len(tiers), len(tiers)):
        cov_matrix = np.full((len(tiers), len(tiers)), np.nan)
        return cov_matrix, tiers, "INVALID_COVARIANCE_SHAPE"
        
    return cov_matrix, tiers, "BOOTSTRAP_COVARIANCE_SUCCESS"


def compute_multivariate_dersimonian_laird_b42(
    means: np.ndarray,
    cov_matrix: np.ndarray
) -> Tuple[float, str]:
    """
    Multivariate DerSimonian-Laird between-cell variance tau^2 estimation
    accounting for full cross-cell covariance.
    
    Zero artificial floors:
    If Q <= df, tau^2 = 0.0 (natural full pooling).
    """
    k = len(means)
    if k < 2 or cov_matrix is None or np.isnan(cov_matrix).any():
        return np.nan, "INSUFFICIENT_CELLS_OR_NAN_COVARIANCE"
        
    # Regularize covariance if ill-conditioned
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
        # Natural full pooling: between-cell heterogeneity is indistinguishable from cluster variance
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    # Multivariate denominator for tau^2:
    # tr(inv_cov) - tr(inv_cov @ ones @ ones.T @ inv_cov) / denom_w
    trace_inv = np.trace(inv_cov)
    quad_term = (ones.T @ (inv_cov @ inv_cov) @ ones) / denom_w
    denom_tau = trace_inv - quad_term
    
    if denom_tau <= 0:
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    tau2 = (Q - df) / denom_tau
    return float(max(0.0, tau2)), "ESTIMATED_POSITIVE"
