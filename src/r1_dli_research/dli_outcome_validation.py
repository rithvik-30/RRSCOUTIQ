"""
RR ScoutIQ - R1 Investigation C: Empirical Construct Validity.
Evaluates forward 6-ball subsequent outcomes (runs, wickets, dots, boundaries, chase win rate)
across pressure tiers, stratified by innings type and phase, with match-clustered bootstrap.
"""

from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def compute_forward_outcomes(df_state: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    """Computes strictly forward 6-ball subsequent outcomes without outcome leakage."""
    legal = df_state[df_state["ext_is_legal_delivery"] == True].copy()
    legal["is_dot"] = (legal["ext_delivery_total_runs"] == 0).astype(int)
    legal["is_bnd"] = (legal["ext_is_four"] | legal["ext_is_six"]).astype(int)

    # Vectorized forward 6-ball rolling sums within (match_id, innings)
    # Using shift(-1) to strictly exclude current delivery outcome
    for col in ["ext_delivery_total_runs", "ext_is_wicket", "is_dot", "is_bnd"]:
        legal["fwd_6_" + col] = legal.groupby(["match_id", "innings"])[col].transform(
            lambda s: s.shift(-1).iloc[::-1].rolling(window=6, min_periods=3).sum().iloc[::-1]
        )

    legal["fwd_count"] = legal.groupby(["match_id", "innings"])["ext_delivery_total_runs"].transform(
        lambda s: s.shift(-1).iloc[::-1].rolling(window=6, min_periods=3).count().iloc[::-1]
    )

    # Normalize metrics to standard 6-ball window
    legal["fwd_6_runs_scaled"] = (legal["fwd_6_ext_delivery_total_runs"] / legal["fwd_count"]) * 6.0
    legal["fwd_6_wkts_scaled"] = (legal["fwd_6_ext_is_wicket"] / legal["fwd_count"]) * 6.0
    legal["fwd_6_dot_pct"] = (legal["fwd_6_is_dot"] / legal["fwd_count"]) * 100.0
    legal["fwd_6_bnd_pct"] = (legal["fwd_6_is_bnd"] / legal["fwd_count"]) * 100.0

    # Merge match outcome for chase win rate
    matches_sub = matches_df[["match_id", "win_team_id"]].drop_duplicates()
    legal = legal.merge(matches_sub, on="match_id", how="left")
    legal["chase_won"] = (legal["batting_team_id"] == legal["win_team_id"]).astype(float)

    # Filter strictly valid DLI and sufficient forward window (at least 3 balls)
    valid_fwd = legal[(legal["is_dli_valid"] == True) & (legal["fwd_count"] >= 3)].copy()
    return valid_fwd


def match_clustered_bootstrap_mean(
    df_sub: pd.DataFrame, metric_col: str, n_boot: int = 500, random_seed: int = 42
) -> Tuple[float, float, float]:
    """Computes point mean and 95% confidence interval via match-level clustered bootstrap."""
    rng = np.random.default_rng(random_seed)
    unique_matches = df_sub["match_id"].unique()
    n_matches = len(unique_matches)
    if n_matches == 0:
        return np.nan, np.nan, np.nan

    vals = df_sub[metric_col].to_numpy()
    point_mean = float(np.nanmean(vals))

    # Fast mapping from match to local integer positions (0..len(df_sub)-1)
    # Using numpy array of positions for each match
    match_arr = df_sub["match_id"].to_numpy()
    match_positions = {}
    for pos, m in enumerate(match_arr):
        if m not in match_positions:
            match_positions[m] = []
        match_positions[m].append(pos)
    for m in match_positions:
        match_positions[m] = np.array(match_positions[m], dtype=np.int32)

    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        sampled_matches = rng.choice(unique_matches, size=n_matches, replace=True)
        sampled_pos = np.concatenate([match_positions[m] for m in sampled_matches])
        boot_means[b] = np.nanmean(vals[sampled_pos])

    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    return point_mean, ci_lower, ci_upper


def run_outcome_validation_battery(df_fwd: pd.DataFrame) -> pd.DataFrame:
    """Executes full stratified outcome validation across tiers, phases, and innings."""
    tiers = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
    strata = [
        ("Overall Population", df_fwd),
        ("Chase Innings", df_fwd[df_fwd["pre_innings_type"] == "Chase"]),
        ("Setting Innings", df_fwd[df_fwd["pre_innings_type"] == "Setting"]),
        ("Chase - Powerplay", df_fwd[(df_fwd["pre_innings_type"] == "Chase") & (df_fwd["pre_match_phase"] == "Powerplay")]),
        ("Chase - Middle", df_fwd[(df_fwd["pre_innings_type"] == "Chase") & (df_fwd["pre_match_phase"] == "Middle")]),
        ("Chase - Death", df_fwd[(df_fwd["pre_innings_type"] == "Chase") & (df_fwd["pre_match_phase"] == "Death")]),
        ("Setting - Powerplay", df_fwd[(df_fwd["pre_innings_type"] == "Setting") & (df_fwd["pre_match_phase"] == "Powerplay")]),
        ("Setting - Middle", df_fwd[(df_fwd["pre_innings_type"] == "Setting") & (df_fwd["pre_match_phase"] == "Middle")]),
        ("Setting - Death", df_fwd[(df_fwd["pre_innings_type"] == "Setting") & (df_fwd["pre_match_phase"] == "Death")]),
    ]

    records = []
    for stratum_name, df_strat in strata:
        if len(df_strat) == 0:
            continue

        for tier in tiers:
            df_tier = df_strat[df_strat["pre_pressure_tier"] == tier]
            n_obs = len(df_tier)
            if n_obs == 0:
                continue

            n_matches = df_tier["match_id"].nunique()

            # 1. Forward 6 runs
            mean_runs, ci_l_runs, ci_u_runs = match_clustered_bootstrap_mean(df_tier, "fwd_6_runs_scaled", n_boot=200)
            # 2. Forward 6 wickets
            mean_wkts, ci_l_wkts, ci_u_wkts = match_clustered_bootstrap_mean(df_tier, "fwd_6_wkts_scaled", n_boot=200)
            # 3. Forward dot %
            mean_dot, ci_l_dot, ci_u_dot = match_clustered_bootstrap_mean(df_tier, "fwd_6_dot_pct", n_boot=200)
            # 4. Forward boundary %
            mean_bnd, ci_l_bnd, ci_u_bnd = match_clustered_bootstrap_mean(df_tier, "fwd_6_bnd_pct", n_boot=200)

            # 5. Chase win rate (chase only)
            if "Chase" in stratum_name or stratum_name == "Overall Population":
                chase_sub = df_tier[df_tier["pre_innings_type"] == "Chase"]
                if len(chase_sub) > 0:
                    mean_win, ci_l_win, ci_u_win = match_clustered_bootstrap_mean(chase_sub, "chase_won", n_boot=200)
                else:
                    mean_win, ci_l_win, ci_u_win = np.nan, np.nan, np.nan
            else:
                mean_win, ci_l_win, ci_u_win = np.nan, np.nan, np.nan

            records.append({
                "stratum": stratum_name,
                "pressure_tier": tier,
                "delivery_count": n_obs,
                "match_count": n_matches,
                "fwd_6_runs_mean": round(mean_runs, 3),
                "fwd_6_runs_ci95": f"[{ci_l_runs:.2f}, {ci_u_runs:.2f}]",
                "fwd_6_wkts_mean": round(mean_wkts, 3),
                "fwd_6_wkts_ci95": f"[{ci_l_wkts:.2f}, {ci_u_wkts:.2f}]",
                "fwd_6_dot_pct_mean": round(mean_dot, 2),
                "fwd_6_dot_pct_ci95": f"[{ci_l_dot:.1f}, {ci_u_dot:.1f}]",
                "fwd_6_bnd_pct_mean": round(mean_bnd, 2),
                "fwd_6_bnd_pct_ci95": f"[{ci_l_bnd:.1f}, {ci_u_bnd:.1f}]",
                "chase_win_rate": round(mean_win * 100, 2) if not np.isnan(mean_win) else np.nan,
                "chase_win_rate_ci95": f"[{ci_l_win * 100:.1f}%, {ci_u_win * 100:.1f}%]" if not np.isnan(mean_win) else "N/A",
            })

    return pd.DataFrame(records)
