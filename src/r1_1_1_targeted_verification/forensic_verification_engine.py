"""
RR ScoutIQ - Milestone R1.1.1 Final Forensic Verification Engine
Performs independent forensic verification across Investigations A, B, C, and D:
- Investigation A: Exact-six window reproduction, window distribution, and partial window exposure analysis.
- Investigation B: Complete Setting DLI model comparison (all 5 specifications, fold-level & aggregate).
- Investigation C: Clustered regression audit, covariance estimator validation, statsmodels investigation.
- Investigation D: Threshold adjacent-tier uncertainty via match-clustered bootstrap (Approved M3 vs Candidate E).
"""

from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score, brier_score_loss, log_loss
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


def run_investigation_a(df_state: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Independently reconstructs forward legal delivery windows and audits exact-6 vs partial windows.
    Returns:
        df_exact_six_csv: DataFrame ready for exact_six_independent_reproduction.csv
        valid_legal: DataFrame containing all valid legal deliveries with forward window stats
    """
    df = df_state.sort_values(["match_id", "innings", "overid", "over_ball_num"]).copy()

    df["is_legal"] = df["ext_is_legal_delivery"] == True
    df["delivery_runs"] = df["ext_delivery_total_runs"].fillna(0).astype(int)
    df["is_wkt"] = (df["ext_is_wicket"] == True).astype(int)
    df["is_dot"] = ((df["ext_delivery_total_runs"] == 0) & (df["is_legal"] == True)).astype(int)
    df["is_bnd"] = ((df["ext_is_four"] == True) | (df["ext_is_six"] == True)).astype(int)

    results = []
    for (m_id, inn), group in df.groupby(["match_id", "innings"], sort=False):
        n_rows = len(group)
        is_legal_arr = group["is_legal"].to_numpy()
        runs_arr = group["delivery_runs"].to_numpy()
        wkts_arr = group["is_wkt"].to_numpy()
        dots_arr = group["is_dot"].to_numpy()
        bnds_arr = group["is_bnd"].to_numpy()

        legal_indices = np.where(is_legal_arr)[0]

        for i in range(n_rows):
            future_legal = legal_indices[legal_indices > i]
            k_avail = len(future_legal)

            if k_avail >= 6:
                end_idx = future_legal[5]
                w_runs = int(np.sum(runs_arr[i + 1 : end_idx + 1]))
                w_wkts = int(np.sum(wkts_arr[i + 1 : end_idx + 1]))
                w_dots = int(np.sum(dots_arr[i + 1 : end_idx + 1]))
                w_bnds = int(np.sum(bnds_arr[i + 1 : end_idx + 1]))
                results.append((m_id, inn, i, 6, w_runs, w_wkts, w_dots, w_bnds, w_runs, w_wkts, (w_dots / 6.0) * 100.0, (w_bnds / 6.0) * 100.0, "Exact 6 Legal Balls"))
            elif k_avail > 0:
                end_idx = future_legal[-1]
                w_runs = int(np.sum(runs_arr[i + 1 : end_idx + 1]))
                w_wkts = int(np.sum(wkts_arr[i + 1 : end_idx + 1]))
                w_dots = int(np.sum(dots_arr[i + 1 : end_idx + 1]))
                w_bnds = int(np.sum(bnds_arr[i + 1 : end_idx + 1]))
                scaled_runs = (w_runs / k_avail) * 6.0
                scaled_wkts = (w_wkts / k_avail) * 6.0
                tag = f"Partial Window ({k_avail} Legal Balls)"
                results.append((m_id, inn, i, k_avail, w_runs, w_wkts, w_dots, w_bnds, scaled_runs, scaled_wkts, (w_dots / k_avail) * 100.0, (w_bnds / k_avail) * 100.0, tag))
            else:
                results.append((m_id, inn, i, 0, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, "Terminal Delivery (0 Legal Balls)"))

    fwd_df = pd.DataFrame(
        results,
        columns=[
            "match_id", "innings", "row_in_inn", "window_length",
            "fwd_runs_raw", "fwd_wkts_raw", "fwd_dots_raw", "fwd_bnds_raw",
            "fwd_runs_scaled", "fwd_wkts_scaled", "fwd_dot_pct", "fwd_bnd_pct", "window_category"
        ]
    )

    df["window_length"] = fwd_df["window_length"].to_numpy()
    df["fwd_runs_raw"] = fwd_df["fwd_runs_raw"].to_numpy()
    df["fwd_wkts_raw"] = fwd_df["fwd_wkts_raw"].to_numpy()
    df["fwd_runs_scaled"] = fwd_df["fwd_runs_scaled"].to_numpy()
    df["fwd_wkts_scaled"] = fwd_df["fwd_wkts_scaled"].to_numpy()
    df["fwd_dot_pct"] = fwd_df["fwd_dot_pct"].to_numpy()
    df["fwd_bnd_pct"] = fwd_df["fwd_bnd_pct"].to_numpy()
    df["window_category"] = fwd_df["window_category"].to_numpy()

    valid = df[df["is_dli_valid"] == True].copy()
    valid_legal = valid[valid["ext_is_legal_delivery"] == True].copy()

    # Section 1: Window Length Distribution (0..6)
    total_valid_legal = len(valid_legal)
    w_counts = valid_legal["window_length"].value_counts().sort_index().to_dict()

    rows = []
    for k in range(7):
        cnt = w_counts.get(k, 0)
        pct = (cnt / total_valid_legal) * 100.0
        rows.append({
            "section": "1_WINDOW_LENGTH_DISTRIBUTION",
            "metric_or_tier": f"Window Length k={k}",
            "sample_size_n": cnt,
            "pct_of_total": round(pct, 4),
            "runs_mean": round(float(valid_legal[valid_legal['window_length'] == k]['fwd_runs_scaled'].mean()), 4) if cnt > 0 and k > 0 else np.nan,
            "wkts_mean": round(float(valid_legal[valid_legal['window_length'] == k]['fwd_wkts_scaled'].mean()), 4) if cnt > 0 and k > 0 else np.nan,
            "dot_pct": round(float(valid_legal[valid_legal['window_length'] == k]['fwd_dot_pct'].mean()), 2) if cnt > 0 and k > 0 else np.nan,
            "bnd_pct": round(float(valid_legal[valid_legal['window_length'] == k]['fwd_bnd_pct'].mean()), 2) if cnt > 0 and k > 0 else np.nan,
            "notes": "Exact Complete Window" if k == 6 else ("Partial Window (Lengths 1..5)" if k > 0 else "Innings Terminal Delivery (0 forward legal balls)")
        })

    # Section 2: Exact 6-Legal-Ball Primary Outcomes by Pressure Tier
    exact_6 = valid_legal[valid_legal["window_length"] == 6].copy()
    tier_names = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]

    for t_name in tier_names:
        sub = exact_6[exact_6["pre_pressure_tier"] == t_name]
        cnt = len(sub)
        pct = (cnt / len(exact_6)) * 100.0
        r_mean = float(sub["fwd_runs_scaled"].mean())
        w_mean = float(sub["fwd_wkts_scaled"].mean())
        d_mean = float(sub["fwd_dot_pct"].mean())
        b_mean = float(sub["fwd_bnd_pct"].mean())

        rows.append({
            "section": "2_EXACT_6_BALL_TIER_REPRODUCTION",
            "metric_or_tier": t_name,
            "sample_size_n": cnt,
            "pct_of_total": round(pct, 2),
            "runs_mean": round(r_mean, 4),
            "wkts_mean": round(w_mean, 4),
            "dot_pct": round(d_mean, 2),
            "bnd_pct": round(b_mean, 2),
            "notes": "Exact 6 Legal Balls (Primary Analysis)"
        })

    # Total row for exact 6
    rows.append({
        "section": "2_EXACT_6_BALL_TIER_REPRODUCTION",
        "metric_or_tier": "Total Exact 6-Ball Sample",
        "sample_size_n": len(exact_6),
        "pct_of_total": 100.0,
        "runs_mean": round(float(exact_6["fwd_runs_scaled"].mean()), 4),
        "wkts_mean": round(float(exact_6["fwd_wkts_scaled"].mean()), 4),
        "dot_pct": round(float(exact_6["fwd_dot_pct"].mean()), 2),
        "bnd_pct": round(float(exact_6["fwd_bnd_pct"].mean()), 2),
        "notes": "All Valid Legal Deliveries with Runway >= 6"
    })

    # Section 3: Partial Window (3..5) and Exposure Scaling Comparison
    partial_3_5 = valid_legal[(valid_legal["window_length"] >= 3) & (valid_legal["window_length"] <= 5)].copy()
    combined_ge_3 = valid_legal[valid_legal["window_length"] >= 3].copy()

    for t_name in tier_names:
        sub_p = partial_3_5[partial_3_5["pre_pressure_tier"] == t_name]
        cnt_p = len(sub_p)
        r_p_raw = float(sub_p["fwd_runs_raw"].mean()) if cnt_p > 0 else 0.0
        w_p_raw = float(sub_p["fwd_wkts_raw"].mean()) if cnt_p > 0 else 0.0
        r_p_scaled = float(sub_p["fwd_runs_scaled"].mean()) if cnt_p > 0 else 0.0
        w_p_scaled = float(sub_p["fwd_wkts_scaled"].mean()) if cnt_p > 0 else 0.0

        sub_c = combined_ge_3[combined_ge_3["pre_pressure_tier"] == t_name]
        cnt_c = len(sub_c)
        r_c_scaled = float(sub_c["fwd_runs_scaled"].mean()) if cnt_c > 0 else 0.0
        w_c_scaled = float(sub_c["fwd_wkts_scaled"].mean()) if cnt_c > 0 else 0.0

        sub_e = exact_6[exact_6["pre_pressure_tier"] == t_name]
        w_e = float(sub_e["fwd_wkts_scaled"].mean())

        rows.append({
            "section": "3_EXPOSURE_SCALING_RECONCILIATION",
            "metric_or_tier": f"{t_name} (Partial vs Exact)",
            "sample_size_n": cnt_p,
            "pct_of_total": round((cnt_p / len(partial_3_5)) * 100.0, 2) if len(partial_3_5) > 0 else 0.0,
            "runs_mean": round(r_p_scaled, 4),
            "wkts_mean": round(w_p_scaled, 4),
            "dot_pct": round(float(sub_p["fwd_dot_pct"].mean()), 2) if cnt_p > 0 else 0.0,
            "bnd_pct": round(float(sub_p["fwd_bnd_pct"].mean()), 2) if cnt_p > 0 else 0.0,
            "notes": f"Partial Raw Wkts={round(w_p_raw, 3)}, Scaled Wkts={round(w_p_scaled, 3)}, Exact-6 Wkts={round(w_e, 3)}, Combined Wkts={round(w_c_scaled, 3)}"
        })

    return pd.DataFrame(rows), valid_legal


def run_investigation_b(valid_legal: pd.DataFrame) -> pd.DataFrame:
    """
    Executes complete Setting DLI model comparison across 5 nested specifications:
    1. Progression Only (t)
    2. Progression + Wickets in Hand (t, W_hand)
    3. Progression, Wickets, Phase & CRR (t, W_hand, Phase, CRR)
    4. Setting DLI Alone (DLI_setting)
    5. Full Raw Match State + Setting DLI (t, W_hand, Phase, CRR, DLI_setting)
    Evaluates fold-level (1..5) and aggregate metrics via 5-fold GroupKFold.
    """
    setting = valid_legal[
        (valid_legal["pre_innings_type"] == "Setting")
        & (valid_legal["is_dli_valid"] == True)
        & (valid_legal["window_length"] == 6)
    ].copy()

    setting["t_progression"] = setting["pre_legal_balls_bowled"].clip(0, 120)
    setting["wkt_hand"] = setting["pre_wickets_in_hand"].clip(1, 10)
    setting["crr_clean"] = setting["pre_crr"].fillna(8.0).clip(0.0, 36.0)
    setting["is_pp"] = (setting["pre_match_phase"] == "Powerplay").astype(float)
    setting["is_death"] = (setting["pre_match_phase"] == "Death").astype(float)
    setting["dli"] = setting["pre_dli"]
    setting["has_wkt"] = (setting["fwd_wkts_raw"] >= 1).astype(int)

    groups = setting["match_id"].to_numpy()

    specs = {
        "Spec 1: Progression Only": setting[["t_progression"]].to_numpy(),
        "Spec 2: Progression + Wickets in Hand": setting[["t_progression", "wkt_hand"]].to_numpy(),
        "Spec 3: Full Raw Match State (Prog, Wkt, Phase, CRR)": setting[["t_progression", "wkt_hand", "is_pp", "is_death", "crr_clean"]].to_numpy(),
        "Spec 4: Setting DLI Alone": setting[["dli"]].to_numpy(),
        "Spec 5: Full Raw Match State + Setting DLI": setting[["t_progression", "wkt_hand", "is_pp", "is_death", "crr_clean", "dli"]].to_numpy(),
    }

    targets = {
        "Fwd 6-Ball Runs": (setting["fwd_runs_scaled"].to_numpy(), "continuous"),
        "Fwd 6-Ball Wickets": (setting["fwd_wkts_scaled"].to_numpy(), "continuous"),
        "Fwd 6-Ball Dot %": (setting["fwd_dot_pct"].to_numpy(), "continuous"),
        "Fwd 6-Ball Boundary %": (setting["fwd_bnd_pct"].to_numpy(), "continuous"),
        "Fwd Wicket Occurrence (>=1 Wkt)": (setting["has_wkt"].to_numpy(), "binary"),
    }

    gkf = GroupKFold(n_splits=5)
    splits = list(gkf.split(setting, groups=groups))

    records = []

    for target_name, (y_arr, t_type) in targets.items():
        for spec_name, X_mat in specs.items():
            oof_preds = np.zeros(len(y_arr))
            fold_metrics = []

            for fold_idx, (train_idx, test_idx) in enumerate(splits, start=1):
                X_tr, X_te = X_mat[train_idx], X_mat[test_idx]
                y_tr, y_te = y_arr[train_idx], y_arr[test_idx]

                scaler = StandardScaler()
                X_tr_s = scaler.fit_transform(X_tr)
                X_te_s = scaler.transform(X_te)

                if t_type == "continuous":
                    model = LinearRegression()
                    model.fit(X_tr_s, y_tr)
                    preds_te = model.predict(X_te_s)
                    oof_preds[test_idx] = preds_te

                    f_r2 = float(r2_score(y_te, preds_te))
                    f_rmse = float(np.sqrt(mean_squared_error(y_te, preds_te)))
                    f_mae = float(mean_absolute_error(y_te, preds_te))
                    fold_metrics.append((f_r2, f_rmse, f_mae))

                    records.append({
                        "target_variable": target_name,
                        "model_specification": spec_name,
                        "evaluation_scope": f"Fold {fold_idx}",
                        "sample_size_n": len(test_idx),
                        "metric_primary_r2_or_auc": round(f_r2, 5),
                        "metric_secondary_rmse_or_brier": round(f_rmse, 4),
                        "metric_tertiary_mae_or_logloss": round(f_mae, 4),
                    })
                else:
                    model = LogisticRegression(max_iter=500, random_state=42)
                    model.fit(X_tr_s, y_tr)
                    probs_te = model.predict_proba(X_te_s)[:, 1]
                    oof_preds[test_idx] = probs_te

                    f_auc = float(roc_auc_score(y_te, probs_te))
                    f_brier = float(brier_score_loss(y_te, probs_te))
                    f_loss = float(log_loss(y_te, probs_te))
                    fold_metrics.append((f_auc, f_brier, f_loss))

                    records.append({
                        "target_variable": target_name,
                        "model_specification": spec_name,
                        "evaluation_scope": f"Fold {fold_idx}",
                        "sample_size_n": len(test_idx),
                        "metric_primary_r2_or_auc": round(f_auc, 4),
                        "metric_secondary_rmse_or_brier": round(f_brier, 4),
                        "metric_tertiary_mae_or_logloss": round(f_loss, 4),
                    })

            # Aggregate OOF record
            if t_type == "continuous":
                agg_r2 = float(r2_score(y_arr, oof_preds))
                agg_rmse = float(np.sqrt(mean_squared_error(y_arr, oof_preds)))
                agg_mae = float(mean_absolute_error(y_arr, oof_preds))
                records.append({
                    "target_variable": target_name,
                    "model_specification": spec_name,
                    "evaluation_scope": "Aggregate OOF (5-Fold CV)",
                    "sample_size_n": len(y_arr),
                    "metric_primary_r2_or_auc": round(agg_r2, 5),
                    "metric_secondary_rmse_or_brier": round(agg_rmse, 4),
                    "metric_tertiary_mae_or_logloss": round(agg_mae, 4),
                })
            else:
                agg_auc = float(roc_auc_score(y_arr, oof_preds))
                agg_brier = float(brier_score_loss(y_arr, oof_preds))
                agg_loss = float(log_loss(y_arr, oof_preds))
                records.append({
                    "target_variable": target_name,
                    "model_specification": spec_name,
                    "evaluation_scope": "Aggregate OOF (5-Fold CV)",
                    "sample_size_n": len(y_arr),
                    "metric_primary_r2_or_auc": round(agg_auc, 4),
                    "metric_secondary_rmse_or_brier": round(agg_brier, 4),
                    "metric_tertiary_mae_or_logloss": round(agg_loss, 4),
                })

    return pd.DataFrame(records)


def run_investigation_c(valid_legal: pd.DataFrame) -> pd.DataFrame:
    """
    Audits clustered regression and reproduces reported coefficient:
    beta_dli = +0.06382, classical OLS SE, White HC1 SE, Match-Clustered SE.
    """
    clean = valid_legal[
        (valid_legal["is_dli_valid"] == True)
        & (valid_legal["window_length"] == 6)
    ].dropna(subset=["fwd_wkts_scaled", "pre_dli", "pre_wickets_in_hand", "pre_legal_balls_rem"]).copy()

    y = clean["fwd_wkts_scaled"].to_numpy()
    clusters = clean["match_id"].to_numpy()
    N = len(y)
    unique_clusters = np.unique(clusters)
    G = len(unique_clusters)

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
    K = X.shape[1]

    # OLS estimation
    XtX = X.T @ X
    XtX_inv = np.linalg.inv(XtX)
    beta = XtX_inv @ (X.T @ y)

    residuals = y - X @ beta
    ssr = float(np.sum(residuals ** 2))
    sigma2_ols = ssr / (N - K)

    # 1. Classical OLS SE
    V_ols = sigma2_ols * XtX_inv
    se_ols = np.sqrt(np.diag(V_ols))

    # 2. White HC1 SE
    meat_white = np.zeros((K, K))
    for i in range(N):
        x_i = X[i : i + 1, :]
        meat_white += (residuals[i] ** 2) * (x_i.T @ x_i)
    V_hc1 = (N / (N - K)) * (XtX_inv @ meat_white @ XtX_inv)
    se_white = np.sqrt(np.diag(V_hc1))

    # 3. Match-Clustered Sandwich Covariance (Liang-Zeger / CGM)
    meat_cluster = np.zeros((K, K))
    for g in unique_clusters:
        idx_g = np.where(clusters == g)[0]
        X_g = X[idx_g, :]
        e_g = residuals[idx_g]
        score_g = X_g.T @ e_g
        meat_cluster += np.outer(score_g, score_g)

    dof_corr = (G / (G - 1.0)) * ((N - 1.0) / (N - K))
    V_cluster = dof_corr * (XtX_inv @ meat_cluster @ XtX_inv)
    se_cluster = np.sqrt(np.diag(V_cluster))

    # Standardized beta: beta * (sd_X / sd_y)
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

        crit_t = stats.t.ppf(0.975, df=G - 1)
        ci_cls_low = b_val - crit_t * s_cls
        ci_cls_high = b_val + crit_t * s_cls

        se_inflation = s_cls / s_ols if s_ols > 0 else 1.0

        rows.append({
            "variable_name": feature_labels[j],
            "raw_coefficient_beta": round(b_val, 6),
            "standardized_beta": round(beta_std[j], 4) if feature_labels[j] != "Intercept" else 0.0,
            "se_classical_ols": round(s_ols, 6),
            "t_stat_classical_ols": round(t_ols, 3),
            "p_val_classical_ols": "< 0.0001" if p_ols < 0.0001 else round(p_ols, 5),
            "se_white_robust": round(s_wht, 6),
            "se_match_clustered": round(s_cls, 6),
            "t_stat_match_clustered": round(t_cls, 3),
            "p_val_match_clustered": "< 0.0001" if p_cls < 0.0001 else round(p_cls, 5),
            "clustered_ci95_low": round(ci_cls_low, 5),
            "clustered_ci95_high": round(ci_cls_high, 5),
            "se_inflation_ratio": round(se_inflation, 2),
            "degrees_of_freedom": G - 1,
            "sample_size_n": N,
            "cluster_count_g": G,
            "covariance_estimator": "Liang-Zeger (1986) / Cameron-Gelbach-Miller (2011) Cluster-Robust Sandwich",
            "ma5_rolling_window_treatment": "Subsumed within match cluster sum (sum_{i in g} sum_{j in g} x_i e_i e_j x_j')",
        })

    return pd.DataFrame(rows)


def run_investigation_d(valid_legal: pd.DataFrame, n_boot: int = 1000, random_seed: int = 42) -> pd.DataFrame:
    """
    Evaluates threshold uncertainty for all adjacent-tier hazard differences:
    Delta H_{2-1}, Delta H_{3-2}, Delta H_{4-3}
    for both Approved Baseline (0.90/1.35/2.25) and Candidate E (0.70/1.30/2.00)
    using match-clustered bootstrap with B=1,000 iterations.
    """
    from src.r1_dli_research.dli_threshold_sensitivity import classify_experimental_tiers

    clean = valid_legal[
        (valid_legal["is_dli_valid"] == True)
        & (valid_legal["window_length"] == 6)
    ].copy()

    total_n = len(clean)
    unique_matches = clean["match_id"].unique()
    n_matches = len(unique_matches)
    rng = np.random.default_rng(random_seed)

    schemes = [
        ("Approved M3 Baseline", 0.90, 1.35, 2.25, "Operationally Defensible Convention (Balanced Cohorts)"),
        ("Candidate E (Draft Thresholds)", 0.70, 1.30, 2.00, "Operationally Defective (Tier 1 Cohort Starvation)"),
    ]

    records = []

    for name, t1, t2, t3, framing in schemes:
        clean["exp_tier"] = classify_experimental_tiers(clean["pre_dli"], t1, t2, t3)

        t_counts = clean["exp_tier"].value_counts().to_dict()
        n1 = t_counts.get("Tier 1: Low", 0)
        n2 = t_counts.get("Tier 2: Medium", 0)
        n3 = t_counts.get("Tier 3: High", 0)
        n4 = t_counts.get("Tier 4: Extreme", 0)

        p1 = (n1 / total_n) * 100.0
        p2 = (n2 / total_n) * 100.0
        p3 = (n3 / total_n) * 100.0
        p4 = (n4 / total_n) * 100.0

        t1_haz = float(clean[clean["exp_tier"] == "Tier 1: Low"]["fwd_wkts_scaled"].mean()) if n1 > 0 else np.nan
        t2_haz = float(clean[clean["exp_tier"] == "Tier 2: Medium"]["fwd_wkts_scaled"].mean()) if n2 > 0 else np.nan
        t3_haz = float(clean[clean["exp_tier"] == "Tier 3: High"]["fwd_wkts_scaled"].mean()) if n3 > 0 else np.nan
        t4_haz = float(clean[clean["exp_tier"] == "Tier 4: Extreme"]["fwd_wkts_scaled"].mean()) if n4 > 0 else np.nan

        # Point estimates of adjacent differences
        diff_21 = t2_haz - t1_haz
        diff_32 = t3_haz - t2_haz
        diff_43 = t4_haz - t3_haz

        # Group pre-aggregation for cluster bootstrap
        match_t = {1: {}, 2: {}, 3: {}, 4: {}}
        for m, grp in clean.groupby("match_id"):
            for k_tier, label in [(1, "Tier 1: Low"), (2, "Tier 2: Medium"), (3, "Tier 3: High"), (4, "Tier 4: Extreme")]:
                match_t[k_tier][m] = grp[grp["exp_tier"] == label]["fwd_wkts_scaled"].to_numpy()

        boot_d21 = []
        boot_d32 = []
        boot_d43 = []

        for _ in range(n_boot):
            sampled_matches = rng.choice(unique_matches, size=n_matches, replace=True)
            v = {1: [], 2: [], 3: [], 4: []}
            for s in sampled_matches:
                for k_tier in [1, 2, 3, 4]:
                    v[k_tier].extend(match_t[k_tier][s])

            m_haz = {}
            for k_tier in [1, 2, 3, 4]:
                m_haz[k_tier] = np.nanmean(v[k_tier]) if len(v[k_tier]) > 0 else np.nan

            boot_d21.append(m_haz[2] - m_haz[1])
            boot_d32.append(m_haz[3] - m_haz[2])
            boot_d43.append(m_haz[4] - m_haz[3])

        diff_data = [
            ("Tier 2 minus Tier 1 (Delta H_21)", diff_21, np.array(boot_d21), n1, n2),
            ("Tier 3 minus Tier 2 (Delta H_32)", diff_32, np.array(boot_d32), n2, n3),
            ("Tier 4 minus Tier 3 (Delta H_43)", diff_43, np.array(boot_d43), n3, n4),
        ]

        for diff_label, pt_est, boot_arr, c_low, c_high in diff_data:
            boot_se = float(np.nanstd(boot_arr))
            ci_low = float(np.percentile(boot_arr, 2.5))
            ci_high = float(np.percentile(boot_arr, 97.5))
            z_score = pt_est / boot_se if boot_se > 0 else 0.0
            p_val = 2.0 * (1.0 - stats.norm.cdf(abs(z_score)))

            records.append({
                "partition_scheme": name,
                "threshold_cutoffs": f"[{t1} / {t2} / {t3}]",
                "adjacent_tier_contrast": diff_label,
                "point_estimate_hazard_diff": round(pt_est, 5),
                "clustered_bootstrap_se": round(boot_se, 5),
                "bootstrap_ci95_low": round(ci_low, 5),
                "bootstrap_ci95_high": round(ci_high, 5),
                "z_statistic": round(z_score, 3),
                "p_value": "< 0.0001" if p_val < 0.0001 else round(p_val, 5),
                "tier_lower_cohort_n": c_low,
                "tier_upper_cohort_n": c_high,
                "bootstrap_replications": n_boot,
                "bootstrap_resampling_unit": "match_id (Cluster Block Bootstrap)",
                "random_seed": random_seed,
                "governance_interpretation": framing,
            })

    return pd.DataFrame(records)
