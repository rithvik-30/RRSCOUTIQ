"""
RR ScoutIQ - Milestone R1.1 Investigation 6: Clamping and Venue Effects Audit.
Analyzes upper clamping (5.00 chase, 3.50 setting) and empirical scoring environments
using verified venue metadata (venue_id) and authentic match scorecards.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def prepare_match_scoring_environment(df_state: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    """Computes verified 1st innings total per match and links authentic venue metadata."""
    # Compute authentic 1st innings total for each match
    inn1 = df_state[(df_state["innings"] == 1) & (df_state["is_shortened_match"] == False) & (df_state["is_dls_match"] == False)]
    inn1_totals = inn1.groupby("match_id")["ext_delivery_total_runs"].sum().reset_index()
    inn1_totals.rename(columns={"ext_delivery_total_runs": "inn1_actual_score"}, inplace=True)

    # Merge venue metadata from matches_df
    venue_meta = matches_df[["match_id", "venue_id", "venue_country"]].drop_duplicates()
    merged = inn1_totals.merge(venue_meta, on="match_id", how="left")

    # Classify verified match scoring environment
    # Low: < 155, Medium: 155-175, High: > 175
    conditions = [
        merged["inn1_actual_score"] < 155,
        (merged["inn1_actual_score"] >= 155) & (merged["inn1_actual_score"] <= 175),
        merged["inn1_actual_score"] > 175,
    ]
    choices = ["Low-Scoring (<155)", "Medium-Scoring (155-175)", "High-Scoring (>175)"]
    merged["scoring_env"] = np.select(conditions, choices, default="Unknown")

    return merged


def run_clamping_and_venue_audit(df_state: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    """Analyzes DLI clamping frequencies and tier distributions across authentic scoring environments and venues."""
    match_env = prepare_match_scoring_environment(df_state, matches_df)

    # Attach scoring environment to state dataframe
    df_merged = df_state.merge(match_env[["match_id", "inn1_actual_score", "venue_id", "venue_country", "scoring_env"]], on="match_id", how="left")
    valid = df_merged[df_merged["is_dli_valid"] == True].copy()

    records = []

    # 1. Stratified by Scoring Environment
    for env in ["Low-Scoring (<155)", "Medium-Scoring (155-175)", "High-Scoring (>175)"]:
        sub = valid[valid["scoring_env"] == env]
        n_obs = len(sub)
        n_matches = sub["match_id"].nunique()

        mean_dli = float(sub["pre_dli"].mean()) if n_obs > 0 else np.nan
        std_dli = float(sub["pre_dli"].std()) if n_obs > 0 else np.nan

        # Chase clamping (5.00)
        chase_sub = sub[sub["pre_innings_type"] == "Chase"]
        n_chase = len(chase_sub)
        chase_clamped = int((np.isclose(chase_sub["pre_dli"], 5.00, atol=1e-4)).sum())
        chase_clamp_pct = (chase_clamped / n_chase) * 100.0 if n_chase > 0 else 0.0

        # Setting clamping (3.50)
        setting_sub = sub[sub["pre_innings_type"] == "Setting"]
        n_setting = len(setting_sub)
        setting_clamped = int((np.isclose(setting_sub["pre_dli"], 3.50, atol=1e-4)).sum())
        setting_clamp_pct = (setting_clamped / n_setting) * 100.0 if n_setting > 0 else 0.0

        # Tier proportions
        t_counts = sub["pre_pressure_tier"].value_counts().to_dict()
        t1_pct = (t_counts.get("Tier 1: Low", 0) / n_obs) * 100.0 if n_obs > 0 else 0.0
        t2_pct = (t_counts.get("Tier 2: Medium", 0) / n_obs) * 100.0 if n_obs > 0 else 0.0
        t3_pct = (t_counts.get("Tier 3: High", 0) / n_obs) * 100.0 if n_obs > 0 else 0.0
        t4_pct = (t_counts.get("Tier 4: Extreme", 0) / n_obs) * 100.0 if n_obs > 0 else 0.0

        records.append({
            "category_level": "Scoring Environment",
            "group_name": env,
            "match_count": n_matches,
            "delivery_count": n_obs,
            "mean_dli": round(mean_dli, 4),
            "std_dli": round(std_dli, 4),
            "chase_deliveries": n_chase,
            "chase_clamped_count": chase_clamped,
            "chase_clamped_pct": round(chase_clamp_pct, 2),
            "setting_deliveries": n_setting,
            "setting_clamped_count": setting_clamped,
            "setting_clamped_pct": round(setting_clamp_pct, 2),
            "tier1_pct": round(t1_pct, 2),
            "tier2_pct": round(t2_pct, 2),
            "tier3_pct": round(t3_pct, 2),
            "tier4_pct": round(t4_pct, 2),
            "high_leverage_pct": round(t3_pct + t4_pct, 2),
        })

    # 2. Stratified by Top Venues (venue_id with >= 25 matches)
    top_venues = valid["venue_id"].value_counts()[lambda x: x >= 25 * 200].index.tolist()
    for v_id in top_venues[:8]:
        sub_v = valid[valid["venue_id"] == v_id]
        n_obs = len(sub_v)
        n_matches = sub_v["match_id"].nunique()
        v_country = sub_v["venue_country"].iloc[0] if len(sub_v) > 0 else "Unknown"

        mean_dli = float(sub_v["pre_dli"].mean())
        std_dli = float(sub_v["pre_dli"].std())

        chase_sub = sub_v[sub_v["pre_innings_type"] == "Chase"]
        n_chase = len(chase_sub)
        chase_clamped = int((np.isclose(chase_sub["pre_dli"], 5.00, atol=1e-4)).sum())
        chase_clamp_pct = (chase_clamped / n_chase) * 100.0 if n_chase > 0 else 0.0

        setting_sub = sub_v[sub_v["pre_innings_type"] == "Setting"]
        n_setting = len(setting_sub)
        setting_clamped = int((np.isclose(setting_sub["pre_dli"], 3.50, atol=1e-4)).sum())
        setting_clamp_pct = (setting_clamped / n_setting) * 100.0 if n_setting > 0 else 0.0

        t_counts = sub_v["pre_pressure_tier"].value_counts().to_dict()
        t1_pct = (t_counts.get("Tier 1: Low", 0) / n_obs) * 100.0
        t2_pct = (t_counts.get("Tier 2: Medium", 0) / n_obs) * 100.0
        t3_pct = (t_counts.get("Tier 3: High", 0) / n_obs) * 100.0
        t4_pct = (t_counts.get("Tier 4: Extreme", 0) / n_obs) * 100.0

        records.append({
            "category_level": f"Top Verified Venue (ID: {v_id})",
            "group_name": f"Venue ID {v_id} ({v_country})",
            "match_count": n_matches,
            "delivery_count": n_obs,
            "mean_dli": round(mean_dli, 4),
            "std_dli": round(std_dli, 4),
            "chase_deliveries": n_chase,
            "chase_clamped_count": chase_clamped,
            "chase_clamped_pct": round(chase_clamp_pct, 2),
            "setting_deliveries": n_setting,
            "setting_clamped_count": setting_clamped,
            "setting_clamped_pct": round(setting_clamp_pct, 2),
            "tier1_pct": round(t1_pct, 2),
            "tier2_pct": round(t2_pct, 2),
            "tier3_pct": round(t3_pct, 2),
            "tier4_pct": round(t4_pct, 2),
            "high_leverage_pct": round(t3_pct + t4_pct, 2),
        })

    return pd.DataFrame(records)
