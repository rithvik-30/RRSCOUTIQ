"""
CSPM Shadow Pipeline Execution Engine
Phase 4.4 Controlled Shadow-Mode Pilot

Runs the complete CSPM engine alongside production DLI in shadow mode.
Saves experimental evaluation artifacts under data/experimental/cspm/.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.models.cspm.config import (
    SIGMA_0,
    MIN_UNCERTAINTY,
    VENUE_SHRINKAGE_M,
    OFFICIAL_SCOUTING_PRESSURE_CUTOFF,
    BATTER_MIN_CAREER_BALLS,
    BATTER_MIN_PRESSURE_BALLS,
    BOWLER_MIN_CAREER_BALLS,
    BOWLER_MIN_PRESSURE_SPELLS,
    OUTCOME_CATEGORIES
)
from src.models.cspm.venue_par import ChronologicalVenueParEstimator
from src.models.cspm.first_innings import FirstInningsPressureEngine
from src.models.cspm.chase_win_probability import ChaseWinProbabilityModel
from src.models.cspm.outcome_model import ConditionalOutcomeModel
from src.models.cspm.leverage_engine import ExpectedLeverageEngine
from src.models.cspm.pressure_engine import CricketStatePressureEngine


def build_completed_matches_database(
    canonical_df: pd.DataFrame,
    matches_meta_df: pd.DataFrame,
    competitions_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Identifies all 1st-innings completed matches eligible for walk-forward venue par.
    """
    valid = canonical_df[(canonical_df["is_dli_valid"] == 1) & (canonical_df["ext_is_legal_delivery"] == 1)]
    inn1 = valid[valid["innings"] == 1]

    agg = inn1.groupby("match_id").agg(
        n_balls=("ext_is_legal_delivery", "sum"),
        runs=("ext_delivery_total_runs", "sum"),
        wkts=("ext_is_wicket", "sum")
    ).reset_index()

    # Completed if 120 legal balls or 10 wickets
    agg["is_complete_first_innings"] = (agg["n_balls"] == 120) | (agg["wkts"] == 10)
    agg.rename(columns={"runs": "first_innings_runs"}, inplace=True)

    meta = matches_meta_df[["match_id", "comp_id", "match_date", "venue_id"]].drop_duplicates("match_id")
    merged = agg.merge(meta, on="match_id", how="left")
    merged["match_date"] = pd.to_datetime(merged["match_date"])
    return merged


def run_cspm_shadow_pipeline(
    data_dir: str = "data/processed/m5_3",
    extracted_dir: str = "data/extracted",
    output_dir: str = "data/experimental/cspm"
) -> Dict[str, Any]:
    """
    Executes the full CSPM shadow scoring pipeline.
    """
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "match_state_full.csv")
    matches_path = os.path.join(extracted_dir, "matches.csv")
    comps_path = os.path.join(extracted_dir, "competitions.csv")
    crosswalk_path = "data/enriched/player_crosswalk_m5_5.csv"

    print(f"Loading canonical dataset: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    m_df = pd.read_csv(matches_path)
    c_df = pd.read_csv(comps_path)
    cw_df = pd.read_csv(crosswalk_path)

    p_map = cw_df.set_index("player_id")["canonical_name"].to_dict()
    career_b_balls = cw_df.set_index("player_id")["balls_faced"].to_dict()
    career_bw_balls = cw_df.set_index("player_id")["balls_bowled"].to_dict()

    valid_mask = (df["is_dli_valid"] == 1) & (df["ext_is_legal_delivery"] == 1)
    clean = df[valid_mask].copy().sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

    m_meta = m_df[["match_id", "comp_id", "match_date", "venue_id", "win_team_id"]].drop_duplicates("match_id")
    clean = clean.merge(m_meta, on="match_id", how="left")
    clean = clean.merge(c_df[["comp_id", "comp_name", "season"]], on="comp_id", how="left")
    clean["match_date"] = pd.to_datetime(clean["match_date"])

    # Build and fit venue par estimator on completed 1st innings
    comp_matches_db = build_completed_matches_database(clean, m_df, c_df)
    v_par_estimator = ChronologicalVenueParEstimator()
    v_par_estimator.fit_database(comp_matches_db)

    # 1. First-Innings Score Projection (5-Fold Out-of-Fold)
    print("Fitting First-Innings score-projection engine...")
    set_mask = (clean["innings"] == 1)
    set_df = clean[set_mask].copy()
    inn_totals = clean.groupby(["match_id", "innings"])["ext_delivery_total_runs"].sum().reset_index()
    inn_totals.rename(columns={"ext_delivery_total_runs": "final_inn_runs"}, inplace=True)
    set_df = set_df.merge(inn_totals, on=["match_id", "innings"], how="left")

    set_df["balls_rem"] = set_df["pre_legal_balls_rem"].clip(lower=0, upper=120)
    set_df["curr_score"] = set_df["pre_score"]
    set_df["runs_rem_actual"] = set_df["final_inn_runs"] - set_df["curr_score"]
    set_df["wkts_in_hand"] = set_df["pre_wickets_in_hand"].clip(lower=0, upper=10)
    set_df["crr"] = set_df["pre_crr"].fillna(8.0).clip(lower=0.0, upper=36.0)

    # Walk-forward venue par for each match
    par_vals = []
    par_srcs = []
    for mid, mgrp in set_df.groupby("match_id", sort=False):
        row = mgrp.iloc[0]
        p_info = v_par_estimator.estimate_par(row["match_date"], row["venue_id"], row["comp_id"], current_match_id=mid)
        par_vals.extend([p_info["venue_par"]] * len(mgrp))
        par_srcs.extend([p_info["source"]] * len(mgrp))

    set_df["venue_par"] = par_vals
    set_df["venue_par_source"] = par_srcs

    gkf = GroupKFold(n_splits=5)
    groups_set = set_df["match_id"].to_numpy()
    X_set = set_df[["balls_rem", "wkts_in_hand", "curr_score", "crr", "venue_par"]].to_numpy()
    y_set = set_df["runs_rem_actual"].to_numpy()

    set_pred_rem = np.empty(len(y_set))
    for tr, val in gkf.split(set_df, groups=groups_set):
        gbt = HistGradientBoostingRegressor(max_iter=150, min_samples_leaf=50, random_state=42)
        gbt.fit(X_set[tr], y_set[tr])
        set_pred_rem[val] = gbt.predict(X_set[val])

    first_inn_engine = FirstInningsPressureEngine()
    first_inn_engine.fit(X_set, y_set)

    set_df["pred_runs_rem"] = set_pred_rem
    set_df["pred_final_score"] = set_df["curr_score"] + set_pred_rem
    set_sigma = first_inn_engine.compute_uncertainty(set_df["balls_rem"].to_numpy())
    set_z = (set_df["venue_par"] - set_df["pred_final_score"]) / set_sigma
    from scipy.stats import norm
    set_df["bps"] = np.clip(100.0 * norm.cdf(set_z), 0.0, 100.0)
    set_df["bops"] = 100.0 - set_df["bps"]
    set_df["expected_leverage"] = set_sigma / 5.0
    set_df["win_probability"] = np.nan

    # 2. Second-Innings Chase Engine (5-Fold Out-of-Fold)
    print("Fitting Chase Win Probability & Leverage engines...")
    clean["batting_team_won"] = (clean["batting_team_id"] == clean["win_team_id"]).astype(float)
    chase_mask = (clean["innings"] == 2)
    chase_df = clean[chase_mask].copy()

    chase_df["balls_rem"] = chase_df["pre_legal_balls_rem"].clip(lower=1)
    chase_df["runs_req"] = chase_df["pre_runs_required"].clip(lower=1)
    chase_df["wkts_in_hand"] = chase_df["pre_wickets_in_hand"].clip(lower=0, upper=10)
    chase_df["crr"] = chase_df["pre_crr"].fillna(8.0).clip(lower=0.0, upper=36.0)

    chase_model = ChaseWinProbabilityModel()
    X_ch = chase_model.construct_features(
        chase_df["runs_req"].to_numpy(),
        chase_df["balls_rem"].to_numpy(),
        chase_df["wkts_in_hand"].to_numpy(),
        chase_df["crr"].to_numpy()
    )
    y_ch = chase_df["batting_team_won"].fillna(0).to_numpy().astype(int)
    groups_ch = chase_df["match_id"].to_numpy()

    ch_wp_oof = np.empty(len(y_ch))
    for tr, val in gkf.split(chase_df, groups=groups_ch):
        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_ch[tr])
        X_va_s = sc.transform(X_ch[val])
        lr = LogisticRegression(max_iter=1000, C=0.5, random_state=42)
        lr.fit(X_tr_s, y_ch[tr])
        ch_wp_oof[val] = lr.predict_proba(X_va_s)[:, 1]

    chase_model.fit(X_ch, y_ch)
    chase_df["win_probability"] = ch_wp_oof
    chase_df["bps"] = np.clip(100.0 * (1.0 - ch_wp_oof), 0.0, 100.0)
    chase_df["bops"] = 100.0 - chase_df["bps"]
    chase_df["venue_par"] = np.nan
    chase_df["venue_par_source"] = "chase_state"

    # Outcome Model for Chase
    outcome_model = ConditionalOutcomeModel()
    leverage_engine = ExpectedLeverageEngine(chase_model, outcome_model)

    print("Computing Expected Delivery Leverage across chase deliveries...")
    lev_vals = []
    # Vectorized fast leverage approximation for batch performance
    # L_t approx = sum_k p_k |Delta WP|
    wp_now = chase_df["win_probability"].to_numpy()
    r_arr = chase_df["runs_req"].to_numpy()
    b_arr = chase_df["balls_rem"].to_numpy()
    w_arr = chase_df["wkts_in_hand"].to_numpy()
    c_arr = chase_df["crr"].to_numpy()

    # Pre-evaluate next state swings across standard outcomes (dot, 1, 2, 4, 6, wicket)
    wp_dot = chase_model.predict_win_probability(r_arr, np.maximum(0, b_arr - 1), w_arr, c_arr)
    wp_one = chase_model.predict_win_probability(np.maximum(0, r_arr - 1), np.maximum(0, b_arr - 1), w_arr, c_arr)
    wp_four = chase_model.predict_win_probability(np.maximum(0, r_arr - 4), np.maximum(0, b_arr - 1), w_arr, c_arr)
    wp_six = chase_model.predict_win_probability(np.maximum(0, r_arr - 6), np.maximum(0, b_arr - 1), w_arr, c_arr)
    wp_wkt = chase_model.predict_win_probability(r_arr, np.maximum(0, b_arr - 1), np.maximum(0, w_arr - 1), c_arr)

    lev_chase = (
        0.302 * np.abs(wp_dot - wp_now) +
        0.384 * np.abs(wp_one - wp_now) +
        0.126 * np.abs(wp_four - wp_now) +
        0.066 * np.abs(wp_six - wp_now) +
        0.056 * np.abs(wp_wkt - wp_now)
    ) * 100.0
    chase_df["expected_leverage"] = lev_chase

    # Combine back into full clean delivery dataframe
    print("Combining delivery pressure scores...")
    set_cols = ["match_id", "innings", "innings_ball_num", "bps", "bops", "expected_leverage", "venue_par", "venue_par_source", "win_probability"]
    comb = pd.concat([set_df[set_cols], chase_df[set_cols]], ignore_index=True)

    clean_scored = clean.merge(comb, on=["match_id", "innings", "innings_ball_num"], how="left")
    clean_scored.loc[clean_scored["is_super_over"] == 1, "bps"] = 75.0
    clean_scored.loc[clean_scored["is_super_over"] == 1, "bops"] = 75.0

    # Assign pressure tier
    clean_scored["cspm_tier"] = "Low"
    clean_scored.loc[clean_scored["bps"] >= 30.0, "cspm_tier"] = "Medium"
    clean_scored.loc[clean_scored["bps"] >= 60.0, "cspm_tier"] = "High"
    clean_scored.loc[clean_scored["bps"] >= 80.0, "cspm_tier"] = "Extreme"

    # Export delivery pressure dataset
    delivery_out_path = os.path.join(output_dir, "delivery_pressure_cspm.csv")
    export_cols = [
        "match_id", "innings", "overid", "over_ball_num", "innings_ball_num",
        "striker_id", "bowler_id", "pre_match_phase", "pre_dli", "pre_pressure_tier",
        "bps", "bops", "cspm_tier", "expected_leverage", "venue_par", "venue_par_source", "win_probability"
    ]
    print(f"Exporting delivery-level shadow scores to: {delivery_out_path}")
    clean_scored[export_cols].to_csv(delivery_out_path, index=False)

    # 3. Integrate with Production Empirical Bayes
    print("Integrating CSPM scores with Production Empirical Bayes pipeline...")
    oof_path = "audit_reports/M5_5B_4_3_8/M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv"
    oof = pd.read_csv(oof_path)

    # Batter EB Rankings
    clean_clean_for_merge = df[df["is_dli_valid"] == 1].copy().reset_index(drop=True)
    clean_clean_for_merge["orig_idx"] = clean_clean_for_merge.index
    clean_groups = clean_clean_for_merge["match_id"].to_numpy()
    fold_indices = []
    for tr, val in gkf.split(clean_clean_for_merge, groups=clean_groups):
        v_df = clean_clean_for_merge.iloc[val]
        v_leg = v_df[v_df["ext_is_legal_delivery"] == 1]
        fold_indices.extend(v_leg["orig_idx"].tolist())

    clean_aligned = clean_clean_for_merge.iloc[fold_indices].reset_index(drop=True)
    clean_aligned = clean_aligned.merge(
        clean_scored[["match_id", "innings", "innings_ball_num", "bps", "bops"]],
        on=["match_id", "innings", "innings_ball_num"],
        how="left"
    )

    bat_oof = oof[oof["domain"] == "Batter"].copy().reset_index(drop=True)
    bat_oof["bps"] = clean_aligned["bps"].values
    bat_oof["val_add"] = bat_oof["pred_m5"] - bat_oof["pred_m4"]
    bat_oof["career_balls"] = bat_oof["player_id"].map(career_b_balls).fillna(0)

    # CSPM BPS >= 60 ranking
    bat_cspm = bat_oof[bat_oof["bps"] >= OFFICIAL_SCOUTING_PRESSURE_CUTOFF].copy()
    agg_b = bat_cspm.groupby("player_id").agg(
        press_balls=("exposure_balls", "count"),
        mean_val_add=("val_add", "mean"),
        se_latent=("se_latent_m5", "mean"),
        career_balls=("career_balls", "first")
    ).reset_index()
    agg_b["name"] = agg_b["player_id"].map(p_map)
    agg_b["lb90"] = agg_b["mean_val_add"] - 1.645 * agg_b["se_latent"]
    q_b = agg_b[(agg_b["career_balls"] >= BATTER_MIN_CAREER_BALLS) & (agg_b["press_balls"] >= BATTER_MIN_PRESSURE_BALLS)].sort_values("lb90", ascending=False).reset_index(drop=True)
    q_b["rank_cspm"] = q_b.index + 1

    # Bowler EB Rankings
    bowl_oof = oof[oof["domain"] == "Bowler"].copy().reset_index(drop=True)
    bowl_oof["career_balls"] = bowl_oof["player_id"].map(career_bw_balls).fillna(0)
    bowl_oof["delta"] = bowl_oof["pred_m5"] - bowl_oof["pred_m4"]

    spell_bops = clean_scored.groupby(["bowler_id", "match_id", "pre_match_phase"])["bops"].mean().reset_index()
    spell_bops.rename(columns={"pre_match_phase": "phase", "bops": "spell_mean_bops"}, inplace=True)
    bowl_oof = bowl_oof.merge(spell_bops, left_on=["player_id", "match_id", "phase"], right_on=["bowler_id", "match_id", "phase"], how="left")
    bowl_oof["spell_mean_bops"] = bowl_oof["spell_mean_bops"].fillna(50.0)

    bowl_cspm = bowl_oof[bowl_oof["spell_mean_bops"] >= OFFICIAL_SCOUTING_PRESSURE_CUTOFF].copy()
    agg_bw = bowl_cspm.groupby("player_id").agg(
        press_spells=("exposure_balls", "count"),
        mean_delta=("delta", "mean"),
        se_latent=("se_latent_m5", "mean"),
        career_balls=("career_balls", "first")
    ).reset_index()
    agg_bw["name"] = agg_bw["player_id"].map(p_map)
    agg_bw["ub90"] = agg_bw["mean_delta"] + 1.645 * agg_bw["se_latent"]
    q_bw = agg_bw[(agg_bw["career_balls"] >= BOWLER_MIN_CAREER_BALLS) & (agg_bw["press_spells"] >= BOWLER_MIN_PRESSURE_SPELLS)].sort_values("ub90", ascending=True).reset_index(drop=True)
    q_bw["rank_cspm"] = q_bw.index + 1

    # Export Empirical Bayes Rankings
    rankings_out_path = os.path.join(output_dir, "empirical_bayes_shadow_rankings.csv")
    q_b["discipline"] = "Batter"
    q_bw["discipline"] = "Bowler"
    comb_rankings = pd.concat([q_b, q_bw], ignore_index=True)
    print(f"Exporting Empirical Bayes shadow rankings to: {rankings_out_path}")
    comb_rankings.to_csv(rankings_out_path, index=False)

    summary_meta = {
        "pipeline_status": "SUCCESS",
        "total_deliveries_scored": len(clean_scored),
        "total_first_innings_balls": len(set_df),
        "total_chase_balls": len(chase_df),
        "qualified_batters_cspm": len(q_b),
        "qualified_bowlers_cspm": len(q_bw),
        "top_5_batters_cspm": q_b.head(5)[["rank_cspm", "name", "lb90"]].to_dict(orient="records"),
        "top_5_bowlers_cspm": q_bw.head(5)[["rank_cspm", "name", "ub90"]].to_dict(orient="records")
    }

    summary_path = os.path.join(output_dir, "shadow_comparison_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_meta, f, indent=2)

    print(f"Shadow summary written to: {summary_path}")
    return summary_meta


if __name__ == "__main__":
    run_cspm_shadow_pipeline()
