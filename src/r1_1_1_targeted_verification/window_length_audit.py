"""
RR ScoutIQ - Milestone R1.1.1 Investigation 1: Forward Window Exactness Audit.
Decomposes the forward window length distribution (lengths 0..6), evaluates exact 6-legal-ball
windows vs partial terminal windows (lengths 1..5), and performs delta comparisons against originally reported figures.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def audit_window_lengths(df_state: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Constructs exact forward legal delivery windows and audits the distribution of window lengths.
    Separates strictly exact 6-legal-delivery windows from partial terminal windows.
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
        n_legal = len(legal_indices)

        for i in range(n_rows):
            future_legal = legal_indices[legal_indices > i]
            k_avail = len(future_legal)

            if k_avail >= 6:
                end_idx = future_legal[5]
                w_runs = int(np.sum(runs_arr[i + 1 : end_idx + 1]))
                w_wkts = int(np.sum(wkts_arr[i + 1 : end_idx + 1]))
                w_dots = int(np.sum(dots_arr[i + 1 : end_idx + 1]))
                w_bnds = int(np.sum(bnds_arr[i + 1 : end_idx + 1]))
                results.append((m_id, inn, i, 6, w_runs, w_wkts, (w_dots / 6.0) * 100.0, (w_bnds / 6.0) * 100.0, "Exact 6 Legal Balls"))
            elif k_avail > 0:
                end_idx = future_legal[-1]
                w_runs = int(np.sum(runs_arr[i + 1 : end_idx + 1]))
                w_wkts = int(np.sum(wkts_arr[i + 1 : end_idx + 1]))
                w_dots = int(np.sum(dots_arr[i + 1 : end_idx + 1]))
                w_bnds = int(np.sum(bnds_arr[i + 1 : end_idx + 1]))
                scaled_runs = (w_runs / k_avail) * 6.0
                scaled_wkts = (w_wkts / k_avail) * 6.0
                tag = f"Partial Window ({k_avail} Legal Balls)"
                results.append((m_id, inn, i, k_avail, scaled_runs, scaled_wkts, (w_dots / k_avail) * 100.0, (w_bnds / k_avail) * 100.0, tag))
            else:
                results.append((m_id, inn, i, 0, np.nan, np.nan, np.nan, np.nan, "Terminal Delivery (0 Legal Balls)"))

    fwd_df = pd.DataFrame(
        results,
        columns=[
            "match_id",
            "innings",
            "row_in_inn",
            "window_length",
            "fwd_runs_scaled",
            "fwd_wkts_scaled",
            "fwd_dot_pct",
            "fwd_bnd_pct",
            "window_category",
        ],
    )

    df["window_length"] = fwd_df["window_length"].to_numpy()
    df["fwd_runs_scaled"] = fwd_df["fwd_runs_scaled"].to_numpy()
    df["fwd_wkts_scaled"] = fwd_df["fwd_wkts_scaled"].to_numpy()
    df["fwd_dot_pct"] = fwd_df["fwd_dot_pct"].to_numpy()
    df["fwd_bnd_pct"] = fwd_df["fwd_bnd_pct"].to_numpy()
    df["window_category"] = fwd_df["window_category"].to_numpy()

    valid = df[df["is_dli_valid"] == True].copy()
    valid_legal = valid[valid["ext_is_legal_delivery"] == True].copy()

    # 1. Distribution of Window Lengths Table
    w_counts = valid_legal["window_length"].value_counts().sort_index().to_dict()
    total_legal = len(valid_legal)

    dist_rows = []
    for k in range(7):
        cnt = w_counts.get(k, 0)
        pct = (cnt / total_legal) * 100.0
        status_label = "Complete Window" if k == 6 else ("Partial Window (Evaluated in R1)" if k >= 3 else "Truncated Runway (Excluded in R1)")
        dist_rows.append({
            "window_length_k": k,
            "legal_delivery_count": cnt,
            "pct_of_valid_legal": round(pct, 3),
            "treatment_in_r1": status_label,
            "exposure_multiplier": f"6 / {k}" if k > 0 else "N/A",
        })
    df_dist = pd.DataFrame(dist_rows)

    # 2. Comparison of Exact-6 vs Partial vs Originally Reported Table
    tier_names = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]

    exact_6 = valid_legal[valid_legal["window_length"] == 6]
    partial_3_5 = valid_legal[(valid_legal["window_length"] >= 3) & (valid_legal["window_length"] <= 5)]
    combined_ge_3 = valid_legal[valid_legal["window_length"] >= 3]

    comp_rows = []
    for t_name in tier_names:
        sub_exact = exact_6[exact_6["pre_pressure_tier"] == t_name]
        sub_part = partial_3_5[partial_3_5["pre_pressure_tier"] == t_name]
        sub_comb = combined_ge_3[combined_ge_3["pre_pressure_tier"] == t_name]

        n_exact = len(sub_exact)
        n_part = len(sub_part)
        n_comb = len(sub_comb)

        r_exact = float(sub_exact["fwd_runs_scaled"].mean()) if n_exact > 0 else np.nan
        w_exact = float(sub_exact["fwd_wkts_scaled"].mean()) if n_exact > 0 else np.nan
        d_exact = float(sub_exact["fwd_dot_pct"].mean()) if n_exact > 0 else np.nan
        b_exact = float(sub_exact["fwd_bnd_pct"].mean()) if n_exact > 0 else np.nan

        r_part = float(sub_part["fwd_runs_scaled"].mean()) if n_part > 0 else np.nan
        w_part = float(sub_part["fwd_wkts_scaled"].mean()) if n_part > 0 else np.nan

        r_comb = float(sub_comb["fwd_runs_scaled"].mean()) if n_comb > 0 else np.nan
        w_comb = float(sub_comb["fwd_wkts_scaled"].mean()) if n_comb > 0 else np.nan
        d_comb = float(sub_comb["fwd_dot_pct"].mean()) if n_comb > 0 else np.nan
        b_comb = float(sub_comb["fwd_bnd_pct"].mean()) if n_comb > 0 else np.nan

        comp_rows.append({
            "pressure_tier": t_name,
            "exact_6_deliveries": n_exact,
            "partial_3_5_deliveries": n_part,
            "combined_ge_3_deliveries": n_comb,
            "exact_6_runs_mean": round(r_exact, 3),
            "combined_runs_mean": round(r_comb, 3),
            "delta_runs_exact_minus_comb": round(r_exact - r_comb, 3),
            "exact_6_wkts_mean": round(w_exact, 3),
            "combined_wkts_mean": round(w_comb, 3),
            "delta_wkts_exact_minus_comb": round(w_exact - w_comb, 3),
            "partial_3_5_runs_mean": round(r_part, 3) if not np.isnan(r_part) else 0.0,
            "partial_3_5_wkts_mean": round(w_part, 3) if not np.isnan(w_part) else 0.0,
            "exact_6_dot_pct": round(d_exact, 2),
            "combined_dot_pct": round(d_comb, 2),
            "exact_6_bnd_pct": round(b_exact, 2),
            "combined_bnd_pct": round(b_comb, 2),
        })

    df_comp = pd.DataFrame(comp_rows)

    # Combine into single structured audit dataframe
    df_combined_audit = pd.concat([df_dist, df_comp], axis=0, ignore_index=True)
    return df_combined_audit, valid_legal
