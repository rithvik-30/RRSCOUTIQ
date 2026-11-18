"""
M5.5-B.4.3.3: Crossed-Effects Variance Decomposition via Henderson Method III
with Explicit Contextual Fixed Effects

Mathematical Foundation:
Fits an unbalanced two-way crossed random-effects mixed model with exposure weights:
    y_{ims} = mu_c + alpha_i + beta_m + epsilon_{ims}
where:
    mu_c: Fixed contextual effect for cell c = (phase, pressure_tier) [K cells]
    alpha_i ~ N(0, tau2_player)  [Bowler latent talent heterogeneity, (Runs/Over)^2]
    beta_m  ~ N(0, sigma2_match) [Match environmental shock, (Runs/Over)^2]
    epsilon_{ims} ~ N(0, sigma2_within / w_{ims}) [Within-spell delivery noise]
    w_{ims} = legal_balls / 6.0 (Exposure in overs)

Design Matrix & Rank Formulation:
Let X_c (N x K), X_b (N x I), X_m (N x M) be design matrices for cells, bowlers, and matches.
Weighted least squares transforms observations by sqrt(w).
Because sum(X_c) = sum(X_b) = sum(X_m) = 1_N, there are 2 linear dependencies among
the three blocks when the bipartite graph between bowlers and matches has c connected components:
    rank([X_c, X_b, X_m]) = K + I + M - 1 - c
    rank([X_c, X_b]) = K + I - 1
    rank([X_c, X_m]) = K + M - 1
    df_E = N - (K + I + M - 1 - c)
    df_m = rank(X_cbm) - rank(X_cb) = M - c
    df_b = rank(X_cbm) - rank(X_cm) = I - c

Exact Henderson Method III Partial Reductions:
    R(m | c, b) = R(c, b, m) - R(c, b)
    R(b | c, m) = R(c, b, m) - R(c, m)
    SSE = y^T W y - R(c, b, m)

Trace Coefficients via Normal Equations:
    c_m = tr((I - P_{cb}) W^{1/2} X_m X_m^T W^{1/2}) = W_total - tr(B_{cb}^T Theta_m)
    c_b = tr((I - P_{cm}) W^{1/2} X_b X_b^T W^{1/2}) = W_total - tr(B_{cm}^T Theta_b)
where B_{cb} = X_{cb}^T X_m, Theta_m = (X_{cb}^T X_{cb})^+ B_{cb}.

Unbiased Estimators:
    sigma2_within = SSE / df_E
    sigma2_match  = (R(m | c, b) - df_m * sigma2_within) / c_m
    tau2_player   = (R(b | c, m) - df_b * sigma2_within) / c_b
"""

import math
from typing import Dict, Any, Tuple, List, Optional
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
    Fits an unbalanced crossed random-effects mixed model with exposure weights
    and explicit contextual fixed effects:
        y_{ims} = mu_c + alpha_i + beta_m + epsilon_{ims}
    
    Returns exact Henderson Method III estimates:
        sigma2_within, sigma2_match, tau2_player, and unified baseline M0.
    """
    spells = df_spells[
        df_spells["is_valid_spell"] & 
        np.isfinite(df_spells["actual_economy"]) & 
        (df_spells["legal_balls"] >= min_balls_per_spell)
    ].copy()

    N = len(spells)
    if N < 50:
        raise ValueError(f"Insufficient spells for crossed variance estimation: N={N} (min required: 50)")

    # 1. Factors: Context Cells, Bowlers, Matches
    col1, col2 = cell_mean_cols
    spells["context_str"] = spells[col1].astype(str) + "::" + spells[col2].astype(str)
    
    ctx_cats = pd.Categorical(spells["context_str"])
    bowler_cats = pd.Categorical(spells["bowler_id"])
    match_cats = pd.Categorical(spells["match_id"])
    
    K = len(ctx_cats.categories)
    I = len(bowler_cats.categories)
    M = len(match_cats.categories)

    if I < 5 or M < 5:
        raise ValueError(f"Insufficient crossed factor levels: Bowlers={I}, Matches={M}")

    # 2. Exposure Weights & Weighted Response
    w = (spells["legal_balls"] / 6.0).values
    sqrt_w = np.sqrt(w)
    y = spells["actual_economy"].values
    sqrt_w_y = sqrt_w * y
    W_total = float(np.sum(w))

    row_ind = np.arange(N, dtype=np.int64)
    col_c = ctx_cats.codes.astype(np.int64)
    col_b = bowler_cats.codes.astype(np.int64)
    col_m = match_cats.codes.astype(np.int64)

    # 3. Check Bipartite Graph Connectivity between Bowlers and Matches
    top_right = sparse.coo_matrix((np.ones(N), (col_b, col_m)), shape=(I, M))
    bipartite_adj = sparse.bmat([[None, top_right], [top_right.T, None]]).tocsr()
    n_components = csgraph.connected_components(bipartite_adj, directed=False)[0]

    # Exact rank accounting for K cells and c components
    rank_X = K + I + M - 1 - n_components
    df_E = N - rank_X
    df_m = M - n_components
    df_b = I - n_components

    if df_E <= 0:
        raise ValueError(f"Degrees of freedom exhausted: N={N}, rank={rank_X}")

    # 4. Construct Sparse Weighted Design Blocks
    X_c = sparse.coo_matrix((sqrt_w, (row_ind, col_c)), shape=(N, K)).tocsr()
    X_b = sparse.coo_matrix((sqrt_w, (row_ind, col_b)), shape=(N, I)).tocsr()
    X_m = sparse.coo_matrix((sqrt_w, (row_ind, col_m)), shape=(N, M)).tocsr()

    X_cb = sparse.hstack([X_c, X_b]).tocsr()
    X_cm = sparse.hstack([X_c, X_m]).tocsr()
    X_cbm = sparse.hstack([X_c, X_b, X_m]).tocsr()

    # 5. Full Model Projection [X_c, X_b, X_m]
    res_cbm = lsqr(X_cbm, sqrt_w_y)
    pred_cbm = X_cbm.dot(res_cbm[0])
    R_cbm = float(np.sum(pred_cbm ** 2))
    SSE = float(np.sum((sqrt_w_y - pred_cbm) ** 2))
    sigma2_within = float(SSE / df_E)

    # 6. Submodel Projections: [X_c, X_b] and [X_c, X_m]
    res_cb = lsqr(X_cb, sqrt_w_y)
    R_cb = float(np.sum(X_cb.dot(res_cb[0]) ** 2))

    res_cm = lsqr(X_cm, sqrt_w_y)
    R_cm = float(np.sum(X_cm.dot(res_cm[0]) ** 2))

    # Partial reductions adjusted for fixed context effects
    R_m_given_cb = max(0.0, R_cbm - R_cb)
    R_b_given_cm = max(0.0, R_cbm - R_cm)

    # 7. Exact Trace Coefficients via Normal Equations
    # c_m = W_total - tr(B_{cb}^T Theta_m)
    A_cb = (X_cb.T.dot(X_cb)).toarray()
    B_cb = (X_cb.T.dot(X_m)).toarray()
    Theta_m = np.linalg.lstsq(A_cb, B_cb, rcond=1e-10)[0]
    proj_sq_m = float(np.sum(Theta_m * B_cb))
    c_m = max(1.0, W_total - proj_sq_m)

    # c_b = W_total - tr(B_{cm}^T Theta_b)
    A_cm = (X_cm.T.dot(X_cm)).toarray()
    B_cm = (X_cm.T.dot(X_b)).toarray()
    Theta_b = np.linalg.lstsq(A_cm, B_cm, rcond=1e-10)[0]
    proj_sq_b = float(np.sum(Theta_b * B_cm))
    c_b = max(1.0, W_total - proj_sq_b)

    # Solve Henderson III Equations:
    # E[R(m | c, b)] = c_m * sigma2_match + df_m * sigma2_within
    # E[R(b | c, m)] = c_b * tau2_player + df_b * sigma2_within
    raw_sigma2_match = (R_m_given_cb - df_m * sigma2_within) / c_m
    raw_tau2_player = (R_b_given_cm - df_b * sigma2_within) / c_b

    # Non-negative projection
    sigma2_match = float(max(0.05, raw_sigma2_match))
    tau2_player = float(max(0.05, raw_tau2_player))

    # Baseline M0 parameter (for a single hypothetical isolated over):
    # M0 = 6.0 * (sigma2_within / tau2_player)
    m0_legal_balls = float(6.0 * (sigma2_within / tau2_player))

    return {
        "sigma2_within": sigma2_within,
        "sigma2_match": sigma2_match,
        "tau2_player": tau2_player,
        "raw_sigma2_match": raw_sigma2_match,
        "raw_tau2_player": raw_tau2_player,
        "m0_legal_balls": m0_legal_balls,
        "n_spells": N,
        "n_contexts": K,
        "n_bowlers": I,
        "n_matches": M,
        "rank_crossed": rank_X,
        "df_error": df_E,
        "df_match": df_m,
        "df_player": df_b,
        "connected_components": n_components,
        "c_m": c_m,
        "c_b": c_b,
        "R_m_given_cb": R_m_given_cb,
        "R_b_given_cm": R_b_given_cm,
        "W_total": W_total,
        "estimation_method": "HENDERSON_METHOD_III_CROSSED_WITH_CONTEXT_FIXED_EFFECTS"
    }


def generate_synthetic_crossed_spells(
    n_bowlers: int = 40,
    n_matches: int = 60,
    true_tau2: float = 0.50,
    true_sig2_m: float = 1.25,
    true_sig2_w: float = 23.0,
    contexts: Optional[List[Tuple[str, str]]] = None,
    true_mu_dict: Optional[Dict[Tuple[str, str], float]] = None,
    n_components: int = 1,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generates a synthetic unbalanced crossed spells dataset containing:
    - Multiple contextual cells (phase x tier) with distinct fixed effects
    - Unequal exposure weights (6, 12, 18, 24 legal balls)
    - Crossed bowler and match random effects
    - Known variance components
    """
    rng = np.random.RandomState(seed)
    
    if contexts is None:
        contexts = [
            ("Powerplay", "Tier 1: Low"),
            ("Powerplay", "Tier 2: Medium"),
            ("Middle", "Tier 2: Medium"),
            ("Middle", "Tier 3: High"),
            ("Death", "Tier 3: High"),
            ("Death", "Tier 4: Extreme")
        ]
        
    if true_mu_dict is None:
        true_mu_dict = {
            contexts[0]: 7.10,
            contexts[1]: 7.80,
            contexts[2]: 7.50,
            contexts[3]: 8.20,
            contexts[4]: 9.60,
            contexts[5]: 10.90
        }
        
    n_contexts = len(contexts)
    comp_size_b = n_bowlers // n_components
    comp_size_m = n_matches // n_components
    
    rows = []
    for c in range(n_components):
        b_offset = c * comp_size_b
        m_offset = c * comp_size_m
        
        b_eff = rng.normal(0, np.sqrt(true_tau2), size=comp_size_b)
        m_eff = rng.normal(0, np.sqrt(true_sig2_m), size=comp_size_m)
        
        for m in range(comp_size_m):
            sp_per_match = rng.choice([6, 7, 8])
            chosen_bowlers = rng.choice(comp_size_b, size=min(sp_per_match, comp_size_b), replace=False)
            for b in chosen_bowlers:
                ctx = contexts[rng.choice(n_contexts)]
                balls = int(rng.choice([6, 12, 18, 24], p=[0.45, 0.35, 0.15, 0.05]))
                w = balls / 6.0
                err = rng.normal(0, np.sqrt(true_sig2_w / w))
                econ = true_mu_dict[ctx] + b_eff[b] + m_eff[m] + err
                rows.append({
                    "bowler_id": f"B_{b + b_offset}",
                    "match_id": f"M_{m + m_offset}",
                    "phase": ctx[0],
                    "modal_tier": ctx[1],
                    "legal_balls": balls,
                    "actual_economy": float(econ),
                    "is_valid_spell": True
                })
                
    return pd.DataFrame(rows)
