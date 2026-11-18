"""
M5.5-B.4.3.1: Crossed-Effects Variance Decomposition via Henderson Method III
Separates:
1. Between-bowler talent heterogeneity (tau2_player)
2. Match-level environmental variation (sigma2_match)
3. Within-bowler spell residual variation (sigma2_within)

Prevents double counting through simultaneous orthogonal projection, exact degrees-of-freedom
corrections accounting for bipartite graph connectivity, and analytical trace coefficients.
"""

import math
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr
import scipy.sparse.csgraph as csgraph


def estimate_crossed_variance_components_henderson3(
    df_spells: pd.DataFrame,
    cell_mean_cols: Tuple[str, str] = ("phase", "modal_tier"),
    min_balls_per_spell: int = 6
) -> Dict[str, Any]:
    """
    Fits an unbalanced two-way crossed random-effects model with exposure weights:
        y_{ims} = mu_c + alpha_i + beta_m + epsilon_{ims}
    where:
        alpha_i ~ N(0, tau2_player)  [Bowler talent heterogeneity]
        beta_m  ~ N(0, sigma2_match) [Match environmental shock]
        epsilon_{ims} ~ N(0, sigma2_within / w_{ims}) [Within-spell delivery noise]
        w_{ims} = legal_balls / 6.0 (overs bowled)

    Returns exact Henderson Method III estimates:
        sigma2_within, sigma2_match, tau2_player, and unified M0 in legal balls.
    """
    spells = df_spells[
        df_spells["is_valid_spell"] & 
        np.isfinite(df_spells["actual_economy"]) & 
        (df_spells["legal_balls"] >= min_balls_per_spell)
    ].copy()

    N = len(spells)
    if N < 50:
        raise ValueError(f"Insufficient spells for crossed variance estimation: N={N} (min required: 50)")

    # 1. Adjust for fixed context effects (phase x tier cell means)
    col1, col2 = cell_mean_cols
    cell_means = spells.groupby([col1, col2])["actual_economy"].mean()
    spells["c_mean"] = spells.set_index([col1, col2]).index.map(cell_means)
    spells["c_mean"] = spells["c_mean"].fillna(spells["actual_economy"].mean())
    spells["y_star"] = spells["actual_economy"] - spells["c_mean"]
    spells["w"] = spells["legal_balls"] / 6.0

    w = spells["w"].values
    sqrt_w = np.sqrt(w)
    y_weighted = spells["y_star"].values * sqrt_w

    bowler_cats = pd.Categorical(spells["bowler_id"])
    match_cats = pd.Categorical(spells["match_id"])
    I = len(bowler_cats.categories)
    M = len(match_cats.categories)

    if I < 5 or M < 5:
        raise ValueError(f"Insufficient crossed factor levels: Bowlers={I}, Matches={M}")

    row_ind = np.arange(N, dtype=np.int64)
    col_b = bowler_cats.codes.astype(np.int64)
    col_m = match_cats.codes.astype(np.int64)

    # 2. Check Bipartite Graph Connectivity to find exact rank of [X_b, X_m]
    top_right = sparse.coo_matrix((np.ones(N), (col_b, col_m)), shape=(I, M))
    bipartite_adj = sparse.bmat([[None, top_right], [top_right.T, None]]).tocsr()
    n_components = csgraph.connected_components(bipartite_adj, directed=False)[0]
    rank_X = I + M - n_components
    df_E = N - rank_X

    if df_E <= 0:
        raise ValueError(f"Degrees of freedom exhausted: N={N}, rank={rank_X}")

    # 3. Simultaneous Orthogonal Projection onto [X_b, X_m]
    data = np.concatenate([sqrt_w, sqrt_w])
    rows = np.concatenate([row_ind, row_ind])
    cols = np.concatenate([col_b, I + col_m])
    X_sp = sparse.coo_matrix((data, (rows, cols)), shape=(N, I + M)).tocsr()

    res_both = lsqr(X_sp, y_weighted)
    pred_both = X_sp.dot(res_both[0])
    SSE = float(np.sum((y_weighted - pred_both) ** 2))
    sigma2_within = float(SSE / df_E)

    # 4. Partial Reductions for Match and Bowler Effects
    # R(alpha) from Bowler alone
    X_b = sparse.coo_matrix((sqrt_w, (row_ind, col_b)), shape=(N, I)).tocsr()
    res_b = lsqr(X_b, y_weighted)
    R_alpha = float(np.sum(X_b.dot(res_b[0]) ** 2))

    # R(beta) from Match alone
    X_m = sparse.coo_matrix((sqrt_w, (row_ind, col_m)), shape=(N, M)).tocsr()
    res_m = lsqr(X_m, y_weighted)
    R_beta = float(np.sum(X_m.dot(res_m[0]) ** 2))

    R_both = float(np.sum(pred_both ** 2))
    R_beta_given_alpha = max(0.0, R_both - R_alpha)
    R_alpha_given_beta = max(0.0, R_both - R_beta)

    # 5. Exact Trace Coefficients for Expected Sums of Squares
    w_im_df = spells.groupby(["match_id", "bowler_id"])["w"].sum().reset_index()
    W_b = spells.groupby("bowler_id")["w"].sum()
    W_m = spells.groupby("match_id")["w"].sum()
    W_total = float(spells["w"].sum())

    w_im_df["W_bi"] = w_im_df["bowler_id"].map(W_b)
    w_im_df["W_m"] = w_im_df["match_id"].map(W_m)

    # c_m = tr((I - P_b) V_m) = W_total - sum_{m, i} (w_{im}^2 / W_{b,i})
    sum_wim2_over_Wbi = float((w_im_df["w"] ** 2 / w_im_df["W_bi"]).sum())
    c_m = max(1.0, W_total - sum_wim2_over_Wbi)
    df_m = M - n_components

    # c_b = tr((I - P_m) V_b) = W_total - sum_{m, i} (w_{im}^2 / W_m)
    sum_wim2_over_Wm = float((w_im_df["w"] ** 2 / w_im_df["W_m"]).sum())
    c_b = max(1.0, W_total - sum_wim2_over_Wm)
    df_b = I - n_components

    # Solve Henderson III Equations:
    # E[R(beta | alpha)] = c_m * sigma2_match + df_m * sigma2_within
    # E[R(alpha | beta)] = c_b * tau2_player + df_b * sigma2_within
    raw_sigma2_match = (R_beta_given_alpha - df_m * sigma2_within) / c_m
    raw_tau2_player = (R_alpha_given_beta - df_b * sigma2_within) / c_b

    # Non-negative projection (restricted method of moments)
    sigma2_match = float(max(0.05, raw_sigma2_match))
    tau2_player = float(max(0.05, raw_tau2_player))

    # 6. Unified M0 parameter strictly consistent with estimated components:
    # Under EB: lambda_i = k / (k + sigma2_within / tau2_player) = n / (n + M0)
    # where M0 = 6.0 * (sigma2_within / tau2_player)
    m0_legal_balls = float(6.0 * (sigma2_within / tau2_player))

    return {
        "sigma2_within": sigma2_within,
        "sigma2_match": sigma2_match,
        "tau2_player": tau2_player,
        "m0_legal_balls": m0_legal_balls,
        "n_spells": N,
        "n_bowlers": I,
        "n_matches": M,
        "rank_crossed": rank_X,
        "df_error": df_E,
        "connected_components": n_components,
        "c_m": c_m,
        "c_b": c_b,
        "R_beta_given_alpha": R_beta_given_alpha,
        "R_alpha_given_beta": R_alpha_given_beta,
        "estimation_method": "HENDERSON_METHOD_III_CROSSED_WEIGHTED"
    }
