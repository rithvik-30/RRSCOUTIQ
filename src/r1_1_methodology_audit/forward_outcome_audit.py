"""
RR ScoutIQ - Milestone R1.1 Investigation 2: Forward Outcome Validation Audit.
Verifies next-six-legal-delivery outcomes, temporal non-leakage, innings-boundary isolation,
and tests incremental explanatory power of DLI over raw state variables.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def construct_strict_legal_forward_windows(df_state: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs forward outcome windows based strictly on NEXT 6 LEGAL DELIVERIES.
    Extras (wides, no-balls) occurring between legal deliveries are attributed to the window,
    but do not consume legal delivery slots. Windows NEVER cross innings boundaries.
    """
    # Sort strictly causal: match_id, innings, overid, over_ball_num
    df = df_state.sort_values(["match_id", "innings", "overid", "over_ball_num"]).copy()

    # Identify legal delivery indices
    df["is_legal"] = df["ext_is_legal_delivery"] == True
    df["delivery_runs"] = df["ext_delivery_total_runs"].fillna(0).astype(int)
    df["is_wkt"] = (df["ext_is_wicket"] == True).astype(int)
    df["is_dot"] = ((df["ext_delivery_total_runs"] == 0) & (df["is_legal"] == True)).astype(int)
    df["is_bnd"] = ((df["ext_is_four"] == True) | (df["ext_is_six"] == True)).astype(int)

    # Process per match and innings
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

        # For every delivery i (0..n_rows-1), find next 6 legal deliveries
        for i in range(n_rows):
            # Future deliveries strictly after i: j > i
            future_legal = legal_indices[legal_indices > i]
            n_avail_legal = len(future_legal)

            if n_avail_legal >= 6:
                end_idx = future_legal[5]  # The 6th legal delivery index
                # Window includes all delivery rows from i + 1 to end_idx (inclusive)
                w_runs = np.sum(runs_arr[i + 1 : end_idx + 1])
                w_wkts = np.sum(wkts_arr[i + 1 : end_idx + 1])
                w_dots = np.sum(dots_arr[i + 1 : end_idx + 1])
                w_bnds = np.sum(bnds_arr[i + 1 : end_idx + 1])
                results.append((m_id, inn, i, 6, w_runs, w_wkts, (w_dots / 6.0) * 100.0, (w_bnds / 6.0) * 100.0, True))
            elif n_avail_legal >= 3:
                # Truncated window at end of innings
                end_idx = future_legal[-1] if n_avail_legal > 0 else i
                w_runs = np.sum(runs_arr[i + 1 : end_idx + 1])
                w_wkts = np.sum(wkts_arr[i + 1 : end_idx + 1])
                w_dots = np.sum(dots_arr[i + 1 : end_idx + 1])
                w_bnds = np.sum(bnds_arr[i + 1 : end_idx + 1])
                scaled_runs = (w_runs / n_avail_legal) * 6.0
                scaled_wkts = (w_wkts / n_avail_legal) * 6.0
                results.append((m_id, inn, i, n_avail_legal, scaled_runs, scaled_wkts, (w_dots / n_avail_legal) * 100.0, (w_bnds / n_avail_legal) * 100.0, False))
            else:
                # Insufficient forward runway (< 3 legal balls)
                results.append((m_id, inn, i, n_avail_legal, np.nan, np.nan, np.nan, np.nan, False))

    fwd_df = pd.DataFrame(
        results,
        columns=[
            "match_id",
            "innings",
            "row_in_inn",
            "fwd_legal_balls",
            "fwd_6_runs",
            "fwd_6_wkts",
            "fwd_6_dot_pct",
            "fwd_6_bnd_pct",
            "is_full_6_balls",
        ],
    )

    # Attach back to df
    df["fwd_legal_balls"] = fwd_df["fwd_legal_balls"].to_numpy()
    df["fwd_6_runs"] = fwd_df["fwd_6_runs"].to_numpy()
    df["fwd_6_wkts"] = fwd_df["fwd_6_wkts"].to_numpy()
    df["fwd_6_dot_pct"] = fwd_df["fwd_6_dot_pct"].to_numpy()
    df["fwd_6_bnd_pct"] = fwd_df["fwd_6_bnd_pct"].to_numpy()
    df["is_full_6_balls"] = fwd_df["is_full_6_balls"].to_numpy()

    return df


def match_clustered_ci(
    df_sub: pd.DataFrame, metric_col: str, n_boot: int = 500, random_seed: int = 42
) -> Tuple[float, float, float]:
    """Computes point estimate and 95% CI via match-level clustered bootstrap."""
    rng = np.random.default_rng(random_seed)
    unique_matches = df_sub["match_id"].unique()
    n_matches = len(unique_matches)
    if n_matches == 0:
        return np.nan, np.nan, np.nan

    vals = df_sub[metric_col].to_numpy()
    point_mean = float(np.nanmean(vals))

    match_series = df_sub["match_id"].to_numpy()
    match_to_positions = {}
    for pos, m in enumerate(match_series):
        if m not in match_to_positions:
            match_to_positions[m] = []
        match_to_positions[m].append(pos)

    match_keys = list(match_to_positions.keys())
    match_key_arr = np.array(match_keys)

    boot_means = []
    for _ in range(n_boot):
        sampled_matches = rng.choice(match_key_arr, size=n_matches, replace=True)
        sampled_positions = []
        for sm in sampled_matches:
            sampled_positions.extend(match_to_positions[sm])
        sampled_vals = vals[sampled_positions]
        boot_means.append(np.nanmean(sampled_vals))

    ci_low = float(np.percentile(boot_means, 2.5))
    ci_high = float(np.percentile(boot_means, 97.5))
    return round(point_mean, 4), round(ci_low, 4), round(ci_high, 4)


def test_dli_incremental_signal(df_eval: pd.DataFrame, outcome_col: str) -> Dict:
    """
    Runs nested linear regressions to test whether DLI adds incremental explanatory power
    for forward outcomes beyond raw state variables (Phase, Wickets in hand, Balls remaining, CRR/RRR).
    """
    clean = df_eval.dropna(subset=[outcome_col, "pre_dli", "pre_wickets_in_hand", "pre_legal_balls_rem"]).copy()
    y = clean[outcome_col].to_numpy()

    # Model 1: State variables without DLI
    clean["wkt"] = clean["pre_wickets_in_hand"]
    clean["b_rem"] = clean["pre_legal_balls_rem"]
    clean["is_pp"] = (clean["pre_match_phase"] == "Powerplay").astype(float)
    clean["is_death"] = (clean["pre_match_phase"] == "Death").astype(float)
    clean["rate"] = clean["pre_rrr"].fillna(clean["pre_crr"].fillna(8.0))

    X_base = clean[["wkt", "b_rem", "is_pp", "is_death", "rate"]].to_numpy()
    X_dli = clean[["wkt", "b_rem", "is_pp", "is_death", "rate", "pre_dli"]].to_numpy()

    reg_base = LinearRegression().fit(X_base, y)
    r2_base = float(reg_base.score(X_base, y))

    reg_dli = LinearRegression().fit(X_dli, y)
    r2_dli = float(reg_dli.score(X_dli, y))

    # Partial R2 and DLI coefficient
    delta_r2 = r2_dli - r2_base
    dli_coef = float(reg_dli.coef_[-1])

    return {
        "outcome_metric": outcome_col,
        "base_state_r2": round(r2_base, 5),
        "state_plus_dli_r2": round(r2_dli, 5),
        "delta_r2": round(delta_r2, 5),
        "dli_coefficient": round(dli_coef, 4),
        "incremental_signal_confirmed": delta_r2 > 0.001,
    }


def run_forward_outcome_audit(df_state: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Executes exhaustive forward outcome validation stratified by innings, phase, and pressure tier."""
    df_fwd = construct_strict_legal_forward_windows(df_state)
    valid_fwd = df_fwd[(df_fwd["is_dli_valid"] == True) & (df_fwd["fwd_legal_balls"] >= 3)].copy()

    strata = [
        ("Overall Population", valid_fwd),
        ("Chase Innings", valid_fwd[valid_fwd["pre_innings_type"] == "Chase"]),
        ("Setting Innings", valid_fwd[valid_fwd["pre_innings_type"] == "Setting"]),
        ("Chase - Powerplay", valid_fwd[(valid_fwd["pre_innings_type"] == "Chase") & (valid_fwd["pre_match_phase"] == "Powerplay")]),
        ("Chase - Middle", valid_fwd[(valid_fwd["pre_innings_type"] == "Chase") & (valid_fwd["pre_match_phase"] == "Middle")]),
        ("Chase - Death", valid_fwd[(valid_fwd["pre_innings_type"] == "Chase") & (valid_fwd["pre_match_phase"] == "Death")]),
        ("Setting - Powerplay", valid_fwd[(valid_fwd["pre_innings_type"] == "Setting") & (valid_fwd["pre_match_phase"] == "Powerplay")]),
        ("Setting - Middle", valid_fwd[(valid_fwd["pre_innings_type"] == "Setting") & (valid_fwd["pre_match_phase"] == "Middle")]),
        ("Setting - Death", valid_fwd[(valid_fwd["pre_innings_type"] == "Setting") & (valid_fwd["pre_match_phase"] == "Death")]),
    ]

    tier_names = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
    results = []

    for s_name, s_df in strata:
        for t_name in tier_names:
            sub = s_df[s_df["pre_pressure_tier"] == t_name]
            n_obs = len(sub)
            if n_obs == 0:
                continue

            r_mean, r_low, r_high = match_clustered_ci(sub, "fwd_6_runs", n_boot=300)
            w_mean, w_low, w_high = match_clustered_ci(sub, "fwd_6_wkts", n_boot=300)
            d_mean, d_low, d_high = match_clustered_ci(sub, "fwd_6_dot_pct", n_boot=300)
            b_mean, b_low, b_high = match_clustered_ci(sub, "fwd_6_bnd_pct", n_boot=300)

            results.append({
                "stratum": s_name,
                "pressure_tier": t_name,
                "delivery_count": n_obs,
                "fwd_6_runs_mean": r_mean,
                "fwd_6_runs_ci95": f"[{r_low}, {r_high}]",
                "fwd_6_wkts_mean": w_mean,
                "fwd_6_wkts_ci95": f"[{w_low}, {w_high}]",
                "fwd_6_dot_pct_mean": d_mean,
                "fwd_6_dot_pct_ci95": f"[{d_low}, {d_high}]",
                "fwd_6_bnd_pct_mean": b_mean,
                "fwd_6_bnd_pct_ci95": f"[{b_low}, {b_high}]",
            })

    df_outcomes = pd.DataFrame(results)

    # Run incremental regression tests
    reg_runs = test_dli_incremental_signal(valid_fwd, "fwd_6_runs")
    reg_wkts = test_dli_incremental_signal(valid_fwd, "fwd_6_wkts")
    reg_dots = test_dli_incremental_signal(valid_fwd, "fwd_6_dot_pct")
    reg_bnds = test_dli_incremental_signal(valid_fwd, "fwd_6_bnd_pct")

    df_increm = pd.DataFrame([reg_runs, reg_wkts, reg_dots, reg_bnds])

    return df_outcomes, df_increm
