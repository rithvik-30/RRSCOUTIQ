"""
RR ScoutIQ — Milestone M5.5-B.4.3.4: Crossed Random-Effects Variance Decomposition Engine
Module: src/m5_5b_4_3_4/variance_decomposition_b4_3_4.py

Remediates Priority 1 & 2 audit requirements:
1. Exact Design Matrix Rank:
   - Calculates exact numerical ranks of [X_c, X_b, X_m], [X_c, X_b], and [X_c, X_m] independently.
   - Accounts for contextual categories distributed across disconnected components.
   - Computes exact degrees of freedom:
       df_E = N - rank(X_cbm)
       df_m = rank(X_cbm) - rank(X_cb)
       df_b = rank(X_cbm) - rank(X_cm)
   - Supports direct dense SVD and Gram-matrix spectral eigenvalue decomposition.
2. Henderson Trace Coefficients:
   - Removes artificial floors on c_m and c_b.
   - Validates strict positivity and numerical conditioning; raises NumericalConditioningError if non-positive.
   - Preserves raw Henderson variance estimates, with explicit tracking of any non-negativity truncation.
"""

import math
from typing import Dict, Any, Tuple, Optional, List, Union
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.linalg as la


class NumericalConditioningError(Exception):
    """Raised when a design matrix or trace coefficient fails numerical conditioning."""
    pass


class IdentifiabilityError(Exception):
    """Raised when model components are unidentifiable or completely confounded."""
    pass


def compute_design_matrix_rank(
    X_mat: Union[np.ndarray, sp.spmatrix],
    method: str = "auto",
    tol: Optional[float] = None
) -> Tuple[int, np.ndarray, float]:
    """
    Computes exact numerical rank of design matrix X using direct SVD or Gram-matrix
    spectral eigenvalue decomposition.
    
    Parameters:
    -----------
    X_mat : np.ndarray or scipy.sparse matrix
        The (weighted) design matrix of shape (N, P).
    method : str
        'auto', 'svd', or 'gram'.
        'svd' uses dense singular value decomposition.
        'gram' uses spectral decomposition of G = X^T X with eigenvalue tolerance
        tol_G = lambda_max * max(N, P) * eps_mach.
        'auto' selects 'svd' for P <= 500 and 'gram' for P > 500.
    tol : float, optional
        Custom numerical tolerance. If None, derives theoretical floating-point tolerance.
        
    Returns:
    --------
    rank : int
        The exact numerical column rank.
    spectrum : np.ndarray
        Singular values (if SVD) or eigenvalues (if Gram).
    tol_used : float
        The numerical cutoff threshold used to determine rank.
    """
    N, P = X_mat.shape
    if N == 0 or P == 0:
        return 0, np.array([]), 0.0
        
    use_svd = (method == "svd") or (method == "auto" and (P <= 500 or N <= 500))
    eps = np.finfo(np.float64).eps
    
    if use_svd:
        if sp.issparse(X_mat):
            A = X_mat.toarray()
        else:
            A = np.asarray(X_mat, dtype=np.float64)
            
        svals = la.svdvals(A)
        tol_svd = tol if tol is not None else float(svals[0] * max(N, P) * eps)
        rank = int(np.sum(svals > tol_svd))
        return rank, svals, tol_svd
    else:
        # Gram matrix spectral eigenvalue decomposition
        if sp.issparse(X_mat):
            G = (X_mat.T @ X_mat).toarray()
        else:
            G = X_mat.T @ X_mat
            
        evals = la.eigvalsh(G)
        lambda_max = float(evals[-1]) if len(evals) > 0 else 0.0
        tol_G = tol if tol is not None else float(lambda_max * max(N, P) * eps)
        rank = int(np.sum(evals > tol_G))
        return rank, evals, tol_G


def estimate_crossed_variance_components_henderson3(
    spells_df: pd.DataFrame,
    cell_mean_cols: Tuple[str, str] = ("phase", "modal_tier"),
    min_balls_per_spell: int = 6,
    rank_method: str = "auto"
) -> Dict[str, Any]:
    """
    Estimates crossed random-effects variance components via Henderson Method III
    with simultaneous contextual fixed-effect block estimation.
    
    Model:
        y_ims = mu_c + alpha_i + beta_m + epsilon_ims
        weight w_ims = balls / 6.0
    
    Exact Degrees of Freedom:
        df_E = N - rank(X_cbm)
        df_m = rank(X_cbm) - rank(X_cb)
        df_b = rank(X_cbm) - rank(X_cm)
    """
    valid = spells_df[spells_df["legal_balls"] >= min_balls_per_spell].copy()
    N = len(valid)
    if N < 30:
        raise ValueError(f"Insufficient observations for Henderson Method III: N={N} < 30")

    # Map contextual cells, bowlers, and matches
    context_keys = sorted(valid[list(cell_mean_cols)].drop_duplicates().apply(tuple, axis=1).tolist())
    bowler_ids = sorted(valid["bowler_id"].unique())
    match_ids = sorted(valid["match_id"].unique())

    K = len(context_keys)
    I = len(bowler_ids)
    M = len(match_ids)

    c_map = {k: idx for idx, k in enumerate(context_keys)}
    b_map = {b: idx for idx, b in enumerate(bowler_ids)}
    m_map = {m: idx for idx, m in enumerate(match_ids)}

    c_indices = [c_map[(r[cell_mean_cols[0]], r[cell_mean_cols[1]])] for _, r in valid.iterrows()]
    b_indices = [b_map[r["bowler_id"]] for _, r in valid.iterrows()]
    m_indices = [m_map[r["match_id"]] for _, r in valid.iterrows()]

    w = valid["legal_balls"].values / 6.0
    sqrt_w = np.sqrt(w)
    econ_col = "economy_rate" if "economy_rate" in valid.columns else "actual_economy"
    y_raw = valid[econ_col].values
    y_tilde = sqrt_w * y_raw
    W_total = float(np.sum(w))

    rows = np.arange(N)
    Xc = sp.csr_matrix((sqrt_w, (rows, c_indices)), shape=(N, K))
    Xb = sp.csr_matrix((sqrt_w, (rows, b_indices)), shape=(N, I))
    Xm = sp.csr_matrix((sqrt_w, (rows, m_indices)), shape=(N, M))

    X_cbm = sp.hstack([Xc, Xb, Xm]).tocsr()
    X_cb = sp.hstack([Xc, Xb]).tocsr()
    X_cm = sp.hstack([Xc, Xm]).tocsr()

    # Exact independent rank determination
    rank_cbm, spectrum_cbm, tol_cbm = compute_design_matrix_rank(X_cbm, method=rank_method)
    rank_cb, spectrum_cb, tol_cb = compute_design_matrix_rank(X_cb, method=rank_method)
    rank_cm, spectrum_cm, tol_cm = compute_design_matrix_rank(X_cm, method=rank_method)

    df_E = N - rank_cbm
    df_m = rank_cbm - rank_cb
    df_b = rank_cbm - rank_cm

    if df_E <= 0:
        raise IdentifiabilityError(f"Residual error degrees of freedom non-positive: df_E = {df_E} (N={N}, rank={rank_cbm})")
    if df_m <= 0:
        raise IdentifiabilityError(f"Match effect degrees of freedom non-positive: df_m = {df_m} (rank_cbm={rank_cbm}, rank_cb={rank_cb})")
    if df_b <= 0:
        raise IdentifiabilityError(f"Bowler effect degrees of freedom non-positive: df_b = {df_b} (rank_cbm={rank_cbm}, rank_cm={rank_cm})")

    # Project y onto column spaces
    # 1. Full model projection P_cbm y
    G_cbm = (X_cbm.T @ X_cbm).toarray()
    Xy_cbm = X_cbm.T @ y_tilde
    beta_cbm = la.lstsq(G_cbm, Xy_cbm)[0]
    y_hat_cbm = X_cbm @ beta_cbm
    SS_cbm = float(np.dot(y_hat_cbm, y_hat_cbm))

    # Total weighted sum of squares
    SS_total = float(np.dot(y_tilde, y_tilde))
    SSE = max(0.0, SS_total - SS_cbm)
    s2_w = SSE / df_E

    # 2. Reduction for Match Effects R(m | c, b)
    G_cb = (X_cb.T @ X_cb).toarray()
    Xy_cb = X_cb.T @ y_tilde
    beta_cb = la.lstsq(G_cb, Xy_cb)[0]
    y_hat_cb = X_cb @ beta_cb
    SS_cb = float(np.dot(y_hat_cb, y_hat_cb))
    R_m = max(0.0, SS_cbm - SS_cb)

    # 3. Reduction for Bowler Effects R(b | c, m)
    G_cm = (X_cm.T @ X_cm).toarray()
    Xy_cm = X_cm.T @ y_tilde
    beta_cm = la.lstsq(G_cm, Xy_cm)[0]
    y_hat_cm = X_cm @ beta_cm
    SS_cm = float(np.dot(y_hat_cm, y_hat_cm))
    R_b = max(0.0, SS_cbm - SS_cm)

    # Analytical Trace Coefficients via Normal Equations
    # tr(X_m^T P_cb X_m) = tr(B_cb^T Theta_m) where G_cb Theta_m = B_cb
    B_cb = (X_cb.T @ Xm).toarray()
    Theta_m = la.lstsq(G_cb, B_cb)[0]
    proj_sq_m = float(np.sum(B_cb * Theta_m))
    c_m = float(W_total - proj_sq_m)

    B_cm = (X_cm.T @ Xb).toarray()
    Theta_b = la.lstsq(G_cm, B_cm)[0]
    proj_sq_b = float(np.sum(B_cm * Theta_b))
    c_b = float(W_total - proj_sq_b)

    # Numerical validity validation: NO artificial floors
    if c_m <= 0.0 or not np.isfinite(c_m):
        raise NumericalConditioningError(
            f"Henderson Method III trace coefficient for match variance is non-positive or non-finite: c_m = {c_m}. "
            f"W_total = {W_total}, proj_sq_m = {proj_sq_m}. Design is confounded or unidentifiable."
        )
    if c_b <= 0.0 or not np.isfinite(c_b):
        raise NumericalConditioningError(
            f"Henderson Method III trace coefficient for bowler variance is non-positive or non-finite: c_b = {c_b}. "
            f"W_total = {W_total}, proj_sq_b = {proj_sq_b}. Design is confounded or unidentifiable."
        )

    # Unconstrained raw Henderson Method III variance components
    raw_s2_m = (R_m - df_m * s2_w) / c_m
    raw_tau2_p = (R_b - df_b * s2_w) / c_b

    # Constrained (positive semi-definite) estimators for inference
    is_match_constrained = (raw_s2_m < 0.0)
    is_player_constrained = (raw_tau2_p < 0.0)
    
    s2_m = float(max(0.0, raw_s2_m))
    tau2_p = float(max(0.0, raw_tau2_p))

    match_constraint_reason = (
        "NEGATIVE_HENDERSON_ESTIMATE_TRUNCATED_TO_ZERO" if is_match_constrained else "UNCONSTRAINED"
    )
    player_constraint_reason = (
        "NEGATIVE_HENDERSON_ESTIMATE_TRUNCATED_TO_ZERO" if is_player_constrained else "UNCONSTRAINED"
    )

    m0_balls = (6.0 * s2_w / tau2_p) if tau2_p > 0.0 else np.nan

    return {
        "sigma2_within": float(s2_w),
        "sigma2_match": float(s2_m),
        "tau2_player": float(tau2_p),
        "raw_sigma2_match": float(raw_s2_m),
        "raw_tau2_player": float(raw_tau2_p),
        "is_match_variance_constrained": bool(is_match_constrained),
        "is_player_variance_constrained": bool(is_player_constrained),
        "match_constraint_reason": match_constraint_reason,
        "player_constraint_reason": player_constraint_reason,
        "m0_legal_balls": float(m0_balls) if np.isfinite(m0_balls) else 300.0,
        "n_spells": int(N),
        "n_contexts": int(K),
        "n_bowlers": int(I),
        "n_matches": int(M),
        "rank_cbm": int(rank_cbm),
        "rank_cb": int(rank_cb),
        "rank_cm": int(rank_cm),
        "df_error": int(df_E),
        "df_match": int(df_m),
        "df_player": int(df_b),
        "c_m": float(c_m),
        "c_b": float(c_b),
        "R_m_given_cb": float(R_m),
        "R_b_given_cm": float(R_b),
        "W_total": float(W_total),
        "identifiability_status": "IDENTIFIABLE_UNCONSTRAINED" if (not is_match_constrained and not is_player_constrained) else "CONSTRAINED_AT_BOUNDARY",
        "rank_method_used": str(rank_method)
    }


def generate_synthetic_crossed_spells(
    n_bowlers: int = 50,
    n_matches: int = 100,
    spells_per_match: int = 8,
    tau2_player: float = 0.50,
    sigma2_match: float = 1.50,
    sigma2_within: float = 20.0,
    context_cell_means: Optional[List[float]] = None,
    seed: int = 42,
    disconnected_components: int = 1,
    exclusive_contexts_per_component: bool = False
) -> pd.DataFrame:
    """
    Generates synthetic crossed spell datasets supporting multi-context baselines,
    unequal exposures, disconnected bipartite components, and exclusive context assignments.
    """
    rng = np.random.RandomState(seed)
    
    if context_cell_means is None:
        context_cell_means = [8.0]
    K = len(context_cell_means)
    
    c = max(1, disconnected_components)
    b_per_comp = n_bowlers // c
    m_per_comp = n_matches // c
    
    records = []
    spell_id = 0
    
    for comp_idx in range(c):
        comp_b_start = comp_idx * b_per_comp
        comp_b_end = comp_b_start + b_per_comp if comp_idx < c - 1 else n_bowlers
        comp_m_start = comp_idx * m_per_comp
        comp_m_end = comp_m_start + m_per_comp if comp_idx < c - 1 else n_matches
        
        comp_bowlers = list(range(comp_b_start, comp_b_end))
        comp_matches = list(range(comp_m_start, comp_m_end))
        
        # Player and match random effects for this component
        alpha = {b: float(rng.normal(0.0, math.sqrt(tau2_player))) for b in comp_bowlers}
        beta = {m: float(rng.normal(0.0, math.sqrt(sigma2_match))) for m in comp_matches}
        
        if exclusive_contexts_per_component:
            # Each component gets an exclusive slice of context categories
            ctx_start = (comp_idx * K) // c
            ctx_end = ((comp_idx + 1) * K) // c if comp_idx < c - 1 else K
            comp_contexts = list(range(ctx_start, max(ctx_start + 1, ctx_end)))
        else:
            comp_contexts = list(range(K))
            
        for m in comp_matches:
            # Select bowlers for this match
            n_sp = min(spells_per_match, len(comp_bowlers))
            match_bowlers = rng.choice(comp_bowlers, size=n_sp, replace=False)
            
            for b in match_bowlers:
                ctx_idx = rng.choice(comp_contexts)
                mu_c = context_cell_means[ctx_idx]
                
                # Unequal ball exposures (between 6 and 24 balls)
                balls = int(rng.choice([6, 12, 18, 24], p=[0.4, 0.3, 0.2, 0.1]))
                w = balls / 6.0
                
                # Residual error scaled by sqrt(w)
                eps = float(rng.normal(0.0, math.sqrt(sigma2_within / w)))
                y_econ = mu_c + alpha[b] + beta[m] + eps
                
                records.append({
                    "spell_id": spell_id,
                    "bowler_id": b,
                    "match_id": m,
                    "phase": f"Phase_{ctx_idx % 3}",
                    "modal_tier": f"Tier_{(ctx_idx // 3) + 1}",
                    "context_idx": ctx_idx,
                    "legal_balls": balls,
                    "economy_rate": y_econ,
                    "component": comp_idx
                })
                spell_id += 1
                
    return pd.DataFrame(records)
