"""
RR ScoutIQ - Milestone R1.1.1 Investigation 3: Clustered Regression Inference Audit.
Audits the econometric properties of forward outcome regressions under delivery-level independence,
White heteroskedasticity, and match-clustered sandwich covariance estimation (Liang-Zeger / CGM).
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from scipy import stats


def compute_ols_with_clustered_se(
    X: np.ndarray, y: np.ndarray, clusters: np.ndarray, feature_names: List[str]
) -> pd.DataFrame:
    """
    Computes OLS regression coefficients along with:
    1. Classical OLS standard errors (assuming i.i.d. errors)
    2. White HC1 heteroskedasticity-consistent standard errors
    3. Match-Clustered Sandwich standard errors (accounting for match clustering and MA(5) window overlap)
    """
    N, K = X.shape
    unique_clusters = np.unique(clusters)
    G = len(unique_clusters)

    # 1. OLS estimation: beta = (X'X)^(-1) X'y
    XtX = X.T @ X
    XtX_inv = np.linalg.inv(XtX)
    beta = XtX_inv @ (X.T @ y)

    # Residuals
    residuals = y - X @ beta
    ssr = float(np.sum(residuals ** 2))
    sigma2_ols = ssr / (N - K)

    # Classical OLS Variance: sigma2 * (X'X)^(-1)
    V_ols = sigma2_ols * XtX_inv
    se_ols = np.sqrt(np.diag(V_ols))

    # White HC1 Heteroskedasticity-Robust Variance:
    # V_hc1 = (N / (N - K)) * (X'X)^(-1) [ sum_i e_i^2 x_i x_i' ] (X'X)^(-1)
    meat_white = np.zeros((K, K))
    for i in range(N):
        x_i = X[i : i + 1, :]
        meat_white += (residuals[i] ** 2) * (x_i.T @ x_i)
    V_hc1 = (N / (N - K)) * (XtX_inv @ meat_white @ XtX_inv)
    se_white = np.sqrt(np.diag(V_hc1))

    # Match-Clustered Sandwich Variance (Liang-Zeger / Cameron-Gelbach-Miller):
    # Meat = sum_g X_g' e_g e_g' X_g
    meat_cluster = np.zeros((K, K))
    for g in unique_clusters:
        idx_g = np.where(clusters == g)[0]
        X_g = X[idx_g, :]
        e_g = residuals[idx_g]
        score_g = X_g.T @ e_g
        meat_cluster += np.outer(score_g, score_g)

    # Finite sample cluster degrees-of-freedom correction: c = (G / (G - 1)) * ((N - 1) / (N - K))
    dof_corr = (G / (G - 1.0)) * ((N - 1.0) / (N - K))
    V_cluster = dof_corr * (XtX_inv @ meat_cluster @ XtX_inv)
    se_cluster = np.sqrt(np.diag(V_cluster))

    # Standardized coefficients (beta_std = beta * (sd_X / sd_y))
    sd_y = float(np.std(y))
    sd_x = np.std(X, axis=0)
    beta_std = beta * (sd_x / sd_y)

    rows = []
    for j in range(K):
        b_val = beta[j]
        s_ols = se_ols[j]
        s_wht = se_white[j]
        s_cls = se_cluster[j]

        t_ols = b_val / s_ols if s_ols > 0 else 0.0
        p_ols = 2.0 * (1.0 - stats.t.cdf(abs(t_ols), df=N - K))

        t_cls = b_val / s_cls if s_cls > 0 else 0.0
        p_cls = 2.0 * (1.0 - stats.t.cdf(abs(t_cls), df=G - 1))

        # 95% CIs under clustered SE
        crit_t = stats.t.ppf(0.975, df=G - 1)
        ci_cls_low = b_val - crit_t * s_cls
        ci_cls_high = b_val + crit_t * s_cls

        se_inflation = s_cls / s_ols if s_ols > 0 else 1.0

        rows.append({
            "variable_name": feature_names[j],
            "coefficient_beta": round(b_val, 5),
            "standardized_beta": round(beta_std[j], 4) if feature_names[j] != "Intercept" else 0.0,
            "se_classical_ols": round(s_ols, 6),
            "t_stat_classical_ols": round(t_ols, 3),
            "p_val_classical_ols": "< 0.0001" if p_ols < 0.0001 else round(p_ols, 5),
            "se_white_robust": round(s_wht, 6),
            "se_match_clustered": round(s_cls, 6),
            "t_stat_match_clustered": round(t_cls, 3),
            "p_val_match_clustered": "< 0.0001" if p_cls < 0.0001 else round(p_cls, 5),
            "clustered_ci95_low": round(ci_cls_low, 5),
            "clustered_ci95_high": round(ci_cls_high, 5),
            "se_cluster_inflation_ratio": round(se_inflation, 2),
            "sample_size_n": N,
            "cluster_count_g": G,
        })

    return pd.DataFrame(rows)


def run_clustered_regression_audit(df_legal_fwd: pd.DataFrame) -> pd.DataFrame:
    """Executes the full econometric inference audit on exact 6-legal-ball forward wicket loss."""
    clean = df_legal_fwd[
        (df_legal_fwd["is_dli_valid"] == True)
        & (df_legal_fwd["window_length"] == 6)
    ].dropna(subset=["fwd_wkts_scaled", "pre_dli", "pre_wickets_in_hand", "pre_legal_balls_rem"]).copy()

    y = clean["fwd_wkts_scaled"].to_numpy()
    clusters = clean["match_id"].to_numpy()

    # Features: Intercept, W_hand, B_rem, is_PP, is_Death, Rate, DLI
    clean["intercept"] = 1.0
    clean["wkt"] = clean["pre_wickets_in_hand"].to_numpy()
    clean["b_rem"] = clean["pre_legal_balls_rem"].to_numpy()
    clean["is_pp"] = (clean["pre_match_phase"] == "Powerplay").astype(float).to_numpy()
    clean["is_death"] = (clean["pre_match_phase"] == "Death").astype(float).to_numpy()
    clean["rate"] = clean["pre_rrr"].fillna(clean["pre_crr"].fillna(8.0)).to_numpy()
    clean["dli"] = clean["pre_dli"].to_numpy()

    feature_cols = ["intercept", "wkt", "b_rem", "is_pp", "is_death", "rate", "dli"]
    feature_labels = [
        "Intercept",
        "Wickets in Hand (W_hand)",
        "Legal Balls Remaining (B_rem)",
        "Powerplay Indicator (is_PP)",
        "Death Phase Indicator (is_Death)",
        "Run Rate (CRR / RRR)",
        "Approved DLI",
    ]

    X = clean[feature_cols].to_numpy()
    return compute_ols_with_clustered_se(X, y, clusters, feature_labels)
