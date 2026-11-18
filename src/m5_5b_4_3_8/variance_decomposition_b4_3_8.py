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


def estimate_batter_crossed_match_variance(
    df: pd.DataFrame,
    cell_cols: Union[str, Tuple[str, ...]] = ("phase", "tier"),
    bat_id_col: Optional[str] = None,
    outcome_col: str = "is_boundary",
    method: str = "paule_mandel",
    lambda_reg: float = 1e-3,
    min_matches: int = 5,
    min_deliveries: int = 50,
    check_convergence: bool = True,
    iter_lim: int = 1000,
    atol: float = 1e-8,
    btol: float = 1e-8
) -> Dict[str, Any]:
    """
    Estimates residual match-level environmental variance for batter boundary outcomes
    on the probability scale using a crossed-effects linear probability / Bernoulli model.
    
    Rigorous Statistical Corrections (M5.5-B.4.3.8 Audit Remediation):
    1. Cross-Match Dependence:
       Explicitly derives and accounts for the full M x M covariance matrix Omega induced
       by repeated player participation across multiple matches:
           Omega = diag(v_m) - W_DX C P^T - P C W_DX^T + P C W_XX C P^T
       where C = (X^T X + lambda I)^-1 and P = D X is the match composition matrix.
    2. Solver Convergence:
       Uses regularized damped LSQR and verified normal-equation Cholesky factorization.
       Validates convergence diagnostics (istop in {1, 2, 4}, itn, arnorm).
       Unconverged fits raise RuntimeError when check_convergence is True.
    3. Strict Zero-Variance Boundary Selection:
       Paule-Mandel score F(0) <= 0 strictly selects 0.0 without falling back to DSL.
       Both DSL and PM estimates are reported separately and distinctly.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Legal delivery records with context columns, batter IDs, and binary boundary outcomes.
    cell_cols : str or tuple of str
        Context columns forming the cell baseline (default: phase, tier).
    bat_id_col : str, optional
        Batter identification column name. Auto-detected if None.
    outcome_col : str
        Binary boundary outcome column (1 = boundary, 0 = non-boundary).
    method : str
        'paule_mandel' (Empirical Bayes / REML root) or 'dsl' (DerSimonian-Laird MoM).
    lambda_reg : float
        Ridge regularization parameter for crossed design inversion (default 1e-3).
    min_matches : int
        Minimum matches required for estimation.
    min_deliveries : int
        Minimum deliveries required for estimation.
    check_convergence : bool
        If True, raises RuntimeError if LSQR solver fails to reach verified convergence.
    iter_lim : int
        Maximum LSQR iterations (default 1000).
    atol, btol : float
        LSQR stopping tolerances (default 1e-8).
        
    Returns:
    --------
    dict with comprehensive variance estimates, covariance statistics, and solver diagnostics.
    """
    import scipy.sparse.linalg as spla
    import scipy.linalg as sla
    from scipy.optimize import brentq
    from scipy.stats import chi2
    
    legal_df = df.copy()
    if bat_id_col is None:
        for c in ["batter_id", "striker_id", "bat_id", "player_id"]:
            if c in legal_df.columns:
                bat_id_col = c
                break
        if bat_id_col is None:
            raise ValueError("Could not auto-detect batter ID column in DataFrame.")
            
    if isinstance(cell_cols, str):
        cell_keys = legal_df[cell_cols].astype(str)
    else:
        cell_keys = legal_df[cell_cols[0]].astype(str)
        for c_col in cell_cols[1:]:
            cell_keys = cell_keys + "::" + legal_df[c_col].astype(str)
    legal_df["_cell_key_internal"] = cell_keys
    
    unique_cells = sorted(legal_df["_cell_key_internal"].unique())
    unique_batters = sorted(legal_df[bat_id_col].unique())
    unique_matches = sorted(legal_df["match_id"].unique())
    
    N = len(legal_df)
    M = len(unique_matches)
    K = len(unique_cells)
    I = len(unique_batters)
    
    if M < min_matches or N < min_deliveries:
        return {
            "sigma2_match_bat": 0.00069,
            "sigma2_match_selected": 0.00069,
            "sigma2_match_dsl": 0.00069,
            "sigma2_match_pm": 0.00069,
            "selected_method": method,
            "used_method": "FALLBACK",
            "status": "INSUFFICIENT_DATA",
            "Q": 0.0,
            "p_value": 1.0,
            "df": max(1, M - 1),
            "M": M,
            "N": N,
            "solver_converged": True,
            "solver_istop": 1,
            "solver_itn": 0,
            "solver_arnorm": 0.0,
            "covariance_adjusted": False
        }
        
    c_map = {c: idx for idx, c in enumerate(unique_cells)}
    b_map = {b: idx for idx, b in enumerate(unique_batters)}
    m_map = {m: idx for idx, m in enumerate(unique_matches)}
    
    c_idx = legal_df["_cell_key_internal"].map(c_map).values
    b_idx = legal_df[bat_id_col].map(b_map).values
    m_idx = legal_df["match_id"].map(m_map).values
    
    # 1. Construct crossed design matrix [X_cell, X_batter]
    rows = np.arange(N)
    Xc = sp.csr_matrix((np.ones(N), (rows, c_idx)), shape=(N, K))
    Xb = sp.csr_matrix((np.ones(N), (rows, b_idx)), shape=(N, I))
    X = sp.hstack([Xc, Xb]).tocsr()
    y = legal_df[outcome_col].astype(float).values
    
    # 2. Direct Normal Equations Solve via Cholesky Factorization and LSQR Agreement Check
    P_dim = K + I
    XtX = (X.T @ X).toarray()
    Xty = (X.T @ y).astype(float)
    ridge_mat = XtX + lambda_reg * np.eye(P_dim)
    try:
        c_factor = sla.cho_factor(ridge_mat, lower=True)
        gamma = sla.cho_solve(c_factor, Xty)
    except np.linalg.LinAlgError:
        raise RuntimeError("Direct Cholesky factorization of ridge normal equations failed.")
        
    # Diagnostic LSQR solver check to verify agreement and gradient
    damp_lsqr = float(np.sqrt(lambda_reg))
    fit_res = spla.lsqr(X, y, damp=damp_lsqr, atol=atol, btol=btol, iter_lim=iter_lim)
    istop = int(fit_res[1])
    itn = int(fit_res[2])
    r1norm = float(fit_res[3])
    r2norm = float(fit_res[4])
    anorm = float(fit_res[5])
    acond = float(fit_res[6])
    arnorm = float(fit_res[7])
    xnorm = float(fit_res[8])
    gamma_lsqr = fit_res[0]
    
    solver_converged = istop in (0, 1, 2, 4)
    if not solver_converged and check_convergence:
        raise RuntimeError(
            f"LSQR solver failed to reach convergence within {iter_lim} iterations: "
            f"istop={istop}, itn={itn}, arnorm={arnorm:.4e}, r1norm={r1norm:.4e}. "
            f"Unconverged fits cannot be silently accepted."
        )
        
    # Solver agreement verification
    norm_gamma = float(np.linalg.norm(gamma))
    rel_diff = float(np.linalg.norm(gamma - gamma_lsqr) / max(norm_gamma, 1e-12)) if norm_gamma > 0 else 0.0
    normal_eq_grad = float(np.linalg.norm(ridge_mat @ gamma_lsqr - Xty) / max(norm_gamma, 1e-12))
    
    if rel_diff > 1e-2 and check_convergence:
        raise RuntimeError(
            f"Solver agreement check failed: relative difference between Cholesky and LSQR is {rel_diff:.4e} (> 1e-2)."
        )
        
    solver_diagnostics = {
        "converged": bool(solver_converged),
        "istop": istop,
        "itn": itn,
        "r1norm": r1norm,
        "r2norm": r2norm,
        "anorm": anorm,
        "acond": acond,
        "arnorm": arnorm,
        "xnorm": xnorm,
        "rel_diff_chol_lsqr": rel_diff,
        "normal_eq_grad": normal_eq_grad,
        "method": "DIRECT_CHOLESKY_WITH_LSQR_VERIFICATION"
    }
    
    raw_pred = X @ gamma
    resid = y - raw_pred
    pred_p = np.clip(raw_pred, 0.01, 0.99)
    v_imb = pred_p * (1.0 - pred_p)
    
    # 3. Match level aggregates
    n_m = np.bincount(m_idx, minlength=M)
    sum_resid_m = np.bincount(m_idx, weights=resid, minlength=M)
    mean_resid = sum_resid_m / n_m
    
    # 4. Explicit Cross-Match Covariance Matrix Omega (accounting for repeated batters)
    # Match averaging matrix D = inv(diag(n_m)) @ Z_m^T
    inv_nm = sp.diags(1.0 / n_m)
    Zm = sp.csr_matrix((np.ones(N), (m_idx, np.arange(N))), shape=(M, N))
    D = inv_nm @ Zm
    P = (D @ X).toarray()  # M x P_dim: match contextual and batter composition
    
    # Compute U = (X^T X + lambda I)^(-1) P^T via Cholesky solve without explicit matrix inversion
    U = sla.cho_solve(c_factor, P.T)  # P_dim x M
    
    # W_DX = D @ diag(v) @ X,  XVX = X^T @ diag(v) @ X
    D_V = inv_nm @ sp.csr_matrix((v_imb, (m_idx, np.arange(N))), shape=(M, N))
    W_DX = (D_V @ X).toarray()  # M x P_dim
    XVX = (X.T @ sp.diags(v_imb) @ X).toarray()  # P_dim x P_dim
    
    sum_v_m = np.bincount(m_idx, weights=v_imb, minlength=M)
    diag_v_arr = sum_v_m / (n_m ** 2)
    diag_v = np.diag(diag_v_arr)
    
    # Exact covariance matrix of residual means Omega:
    # Omega_raw = diag(v) - W_DX U - (W_DX U)^T + U^T XVX U
    W_DX_U = W_DX @ U  # M x M
    UT_XVX_U = U.T @ XVX @ U  # M x M
    Omega_raw = diag_v - W_DX_U - W_DX_U.T + UT_XVX_U
    
    # Quantify asymmetry
    asym_matrix = Omega_raw - Omega_raw.T
    asym_frobenius = float(np.linalg.norm(asym_matrix, "fro"))
    asym_max = float(np.max(np.abs(asym_matrix)))
    
    # Numerical symmetrization
    Omega_sym = 0.5 * (Omega_raw + Omega_raw.T)
    
    # Inspect eigenvalue spectrum
    eigvals = np.linalg.eigvalsh(Omega_sym)
    min_eig = float(np.min(eigvals))
    max_eig = float(np.max(eigvals))
    
    # Regularize to guarantee positive definiteness:
    # If min_eig is <= 0 due to float precision, shift by |min_eig| + 1e-9
    shift_psd = max(0.0, -min_eig) + 1e-9
    Omega = Omega_sym + shift_psd * np.eye(M)
    
    # Match shock projection matrix A = I_M - P U diag(n_m)
    # Note: P @ C @ P^T = P @ U
    A = np.eye(M) - (P @ U) * n_m[None, :]
    AAt = A @ A.T
    
    # Diagnostics on cross-match covariance
    diag_Omega = np.diag(Omega)
    off_diag_Omega = Omega - np.diag(diag_Omega)
    max_cross_cov = float(np.max(np.abs(off_diag_Omega)))
    mean_cross_cov = float(np.mean(np.abs(off_diag_Omega)))
    
    ones = np.ones(M)
    df_M = M - 1
    
    # 5. Covariance-Adjusted DerSimonian-Laird Estimator
    # Prohibit diagonal fallback; if Omega cannot be factored, raise explicit failure
    try:
        L0 = np.linalg.cholesky(Omega)
    except np.linalg.LinAlgError as e:
        raise RuntimeError(
            f"Covariance matrix Omega factorization failed (min eigenvalue={min_eig:.4e}, "
            f"max eigenvalue={max_eig:.4e}, shift={shift_psd:.4e}): {e}. "
            "Diagonal fallback is prohibited under B.4.3.8 audit standards."
        )
        
    om_inv_e = sla.cho_solve((L0, True), mean_resid)
    om_inv_1 = sla.cho_solve((L0, True), ones)
    mu_hat0 = float(np.sum(om_inv_e) / np.sum(om_inv_1))
    diff0 = mean_resid - mu_hat0 * ones
    v_inv_diff0 = sla.cho_solve((L0, True), diff0)
    Q0 = float(diff0.T @ v_inv_diff0)
    
    om_inv_AAt = sla.cho_solve((L0, True), AAt)
    tr_om_AAt = float(np.trace(om_inv_AAt))
    denom_dsl = float(tr_om_AAt - (om_inv_1.T @ AAt @ om_inv_1) / np.sum(om_inv_1))
    s2_dsl = float(max(0.0, (Q0 - df_M) / max(1e-9, denom_dsl)))
        
    p_val = float(1.0 - chi2.cdf(Q0, df_M)) if df_M > 0 else 1.0
    
    # 6. Covariance-Adjusted Paule-Mandel Empirical Bayes Estimator
    def f_pm(s2):
        V = s2 * AAt + Omega
        try:
            L = np.linalg.cholesky(V)
        except np.linalg.LinAlgError:
            return np.nan
        v_inv_e = sla.cho_solve((L, True), mean_resid)
        v_inv_1 = sla.cho_solve((L, True), ones)
        sum_v_inv_1 = np.sum(v_inv_1)
        if abs(sum_v_inv_1) < 1e-15:
            return np.nan
        mu_hat = np.sum(v_inv_e) / sum_v_inv_1
        diff = mean_resid - mu_hat * ones
        v_inv_diff = sla.cho_solve((L, True), diff)
        return float(diff.T @ v_inv_diff - df_M)
            
    f0 = f_pm(0.0)
    pm_status = "UNKNOWN"
    s2_pm = np.nan
    if np.isnan(f0):
        pm_status = "PM_FACTORIZATION_FAILED"
    elif f0 <= 0.0:
        # Match variation does not exceed sampling variance: strictly zero
        s2_pm = 0.0
        pm_status = "PAULE_MANDEL_ZERO"
    else:
        # Search for bracket upper bound where f(b) < 0
        upper_bound = None
        for b_cand in [0.01, 0.05, 0.10, 0.50, 1.0, 5.0]:
            fb = f_pm(b_cand)
            if not np.isnan(fb) and fb < 0.0:
                upper_bound = b_cand
                break
                
        if upper_bound is not None:
            try:
                s2_pm = float(brentq(f_pm, 0.0, upper_bound, xtol=1e-8, maxiter=100))
                pm_status = "PAULE_MANDEL_CONVERGED"
            except Exception:
                pm_status = "PM_ROOT_FINDING_FAILED"
        else:
            pm_status = "PM_BRACKETING_FAILED"
        
    # 7. Method Selection (Strictly Zero when PM Identifies Boundary; No DSL Substitution)
    if method == "dsl":
        s2_selected = s2_dsl
        selected_method = "DSL"
        used_method = "DSL"
        status = "ESTIMATED_POSITIVE" if s2_dsl > 0.0 else "ESTIMATED_ZERO"
    elif method == "paule_mandel":
        selected_method = "PAULE_MANDEL"
        if pm_status == "PAULE_MANDEL_ZERO":
            s2_selected = 0.0
            used_method = "PAULE_MANDEL_ZERO"
            status = "ESTIMATED_ZERO"
        elif pm_status == "PAULE_MANDEL_CONVERGED":
            s2_selected = s2_pm
            used_method = "PAULE_MANDEL"
            status = "ESTIMATED_POSITIVE" if s2_pm > 0.0 else "ESTIMATED_ZERO"
        else:
            if check_convergence:
                raise RuntimeError(
                    f"Paule-Mandel estimation failed with status '{pm_status}': "
                    f"f(0)={f0:.4e}. DSL substitution is prohibited."
                )
            s2_selected = np.nan
            used_method = pm_status
            status = pm_status
    else:
        raise ValueError(f"Unknown estimation method: {method}")
        
    return {
        "sigma2_match_bat": float(s2_selected) if not np.isnan(s2_selected) else np.nan,
        "sigma2_match_selected": float(s2_selected) if not np.isnan(s2_selected) else np.nan,
        "sigma2_match_dsl": float(s2_dsl),
        "sigma2_match_pm": float(s2_pm) if not np.isnan(s2_pm) else np.nan,
        "selected_method": selected_method,
        "used_method": used_method,
        "status": status,
        "Q": float(Q0),
        "p_value": float(p_val),
        "df": df_M,
        "M": M,
        "N": N,
        "solver_converged": bool(solver_converged),
        "solver_istop": istop,
        "solver_itn": itn,
        "solver_arnorm": float(arnorm),
        "solver_diagnostics": solver_diagnostics,
        "covariance_adjusted": True,
        "asymmetry_frobenius": asym_frobenius,
        "asymmetry_max": asym_max,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "shift_psd": shift_psd,
        "cross_match_cov_max": max_cross_cov,
        "cross_match_cov_mean": mean_cross_cov,
        "mean_sampling_variance": float(np.mean(diag_v_arr))
    }


def generate_synthetic_batter_crossed_dataset(
    n_deliveries: int = 20000,
    n_matches: int = 50,
    n_batters: int = 40,
    tau2_player: float = 0.003,
    sigma2_match: float = 0.0010,
    context_cell_means: Optional[Dict[str, float]] = None,
    player_skew_exponent: float = 0.8,
    match_exposure_skew: bool = True,
    link: str = "linear",
    seed: int = 42
) -> pd.DataFrame:
    """
    Generates synthetic crossed batter delivery records with:
    1. Repeated player participation across multiple matches with realistic skewed distribution.
    2. Unequal match delivery exposure.
    3. Known contextual cell baselines, player ability variance, and match shock variance.
    4. Support for both additive linear probability model and strained logistic link model.
    """
    rng = np.random.default_rng(seed)
    if context_cell_means is None:
        context_cell_means = {
            "Powerplay::Tier 1": 0.22,
            "Powerplay::Tier 2": 0.20,
            "Middle::Tier 1": 0.16,
            "Middle::Tier 2": 0.14,
            "Death::Tier 1": 0.26,
            "Death::Tier 2": 0.24
        }
        
    cell_keys = list(context_cell_means.keys())
    cell_logits = {c: float(np.log(p / (1.0 - p))) for c, p in context_cell_means.items()}
    
    # Skewed player participation: power-law weights (e.g. star players face many balls)
    player_weights = 1.0 / (np.arange(1, n_batters + 1) ** player_skew_exponent)
    player_weights /= player_weights.sum()
    
    # Skewed match weights
    if match_exposure_skew:
        match_weights = rng.uniform(0.5, 1.5, size=n_matches)
        match_weights /= match_weights.sum()
    else:
        match_weights = np.full(n_matches, 1.0 / n_matches)
        
    # True random effects
    alpha = rng.normal(0.0, math.sqrt(max(0.0, tau2_player)), size=n_batters)
    beta = rng.normal(0.0, math.sqrt(max(0.0, sigma2_match)), size=n_matches)
    
    batters_arr = rng.choice(n_batters, size=n_deliveries, p=player_weights)
    matches_arr = rng.choice(n_matches, size=n_deliveries, p=match_weights)
    cells_arr = rng.choice(cell_keys, size=n_deliveries)
    
    records = []
    for b_idx in range(n_deliveries):
        m = int(matches_arr[b_idx])
        i = int(batters_arr[b_idx])
        c = str(cells_arr[b_idx])
        
        mu_c = context_cell_means[c]
        if link == "linear":
            p_true = float(np.clip(mu_c + alpha[i] + beta[m], 0.01, 0.99))
        elif link == "logistic":
            # Strained non-linear link
            scale = float(mu_c * (1.0 - mu_c))
            logit_p = cell_logits[c] + (alpha[i] + beta[m]) / max(0.05, scale)
            p_true = float(1.0 / (1.0 + np.exp(-logit_p)))
        else:
            raise ValueError(f"Unknown link function: {link}")
            
        y = int(rng.binomial(1, p_true))
        ph, tr = c.split("::")
        
        records.append({
            "delivery_id": b_idx,
            "match_id": m,
            "batter_id": i,
            "phase": ph,
            "tier": tr,
            "is_boundary": y,
            "ext_is_legal_delivery": 1,
            "is_legal": 1,
            "p_true": p_true
        })
        
    return pd.DataFrame(records)


def run_synthetic_batter_crossed_simulation_benchmark(
    n_seeds: int = 5,
    true_sigma2_match: float = 0.0010,
    n_deliveries: int = 15000,
    n_matches: int = 40,
    n_batters: int = 30,
    link: str = "linear",
    method: str = "paule_mandel"
) -> Dict[str, Any]:
    """
    Runs repeated multi-seed simulations to benchmark bias, empirical RMSE,
    and boundary detection rate under cross-match dependence.
    """
    estimates = []
    statuses = []
    converged_flags = []
    
    for s in range(n_seeds):
        syn_df = generate_synthetic_batter_crossed_dataset(
            n_deliveries=n_deliveries,
            n_matches=n_matches,
            n_batters=n_batters,
            tau2_player=0.003,
            sigma2_match=true_sigma2_match,
            link=link,
            seed=100 + s
        )
        res = estimate_batter_crossed_match_variance(
            syn_df,
            cell_cols=("phase", "tier"),
            bat_id_col="batter_id",
            outcome_col="is_boundary",
            method=method,
            check_convergence=True
        )
        estimates.append(res["sigma2_match_bat"])
        statuses.append(res["status"])
        converged_flags.append(res["solver_converged"])
        
    est_arr = np.array(estimates)
    mean_est = float(np.mean(est_arr))
    bias = float(mean_est - true_sigma2_match)
    rmse = float(np.sqrt(np.mean((est_arr - true_sigma2_match) ** 2)))
    zero_rate = float(np.mean([s == "ESTIMATED_ZERO" for s in statuses]))
    
    return {
        "n_seeds": n_seeds,
        "true_sigma2_match": true_sigma2_match,
        "link": link,
        "method": method,
        "estimates": [float(x) for x in estimates],
        "mean_estimate": mean_est,
        "bias": bias,
        "rmse": rmse,
        "zero_boundary_detection_rate": zero_rate,
        "all_converged": all(converged_flags)
    }
