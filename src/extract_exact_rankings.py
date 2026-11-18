"""
Extract exact rankings and stats for Top 10 Batters and Top 10 Bowlers
"""

import os
import sys
import pandas as pd
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

def main():
    df = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    clean = df[(df["is_dli_valid"] == 1) & (df["ext_is_legal_delivery"] == 1)].copy()

    clean["is_boundary"] = ((clean["ext_is_four"] == 1) | (clean["ext_is_six"] == 1)).astype(int)
    clean["is_six"] = (clean["ext_is_six"] == 1).astype(int)
    clean["is_four"] = (clean["ext_is_four"] == 1).astype(int)
    clean["is_dot_bat"] = (clean["ext_batter_runs"] == 0).astype(int)
    clean["is_dot_bowl"] = (clean["ext_bowler_debit_runs"] == 0).astype(int)
    clean["is_wicket"] = (clean["ext_is_bowler_wicket"] == True).astype(int)
    clean["is_dismissal"] = (clean["dismissed_player_id"].notna() & (clean["dismissed_player_id"] == clean["striker_id"])).astype(int)

    oof = pd.read_csv("audit_reports/M5_5B_4_3_8/M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv")
    crosswalk = pd.read_csv("data/enriched/player_crosswalk_m5_5.csv")
    p_map = crosswalk.set_index("player_id")["canonical_name"].to_dict()
    role_map = crosswalk.set_index("player_id")["role_discipline"].to_dict()

    # 1. Batters
    bat_oof = oof[oof["domain"] == "Batter"].copy()
    bat_oof["is_press"] = bat_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    press_b = bat_oof[bat_oof["is_press"]].copy()
    press_b["val_add"] = press_b["pred_m5"] - press_b["pred_m4"]

    agg_b = press_b.groupby("player_id").agg(
        n_press_balls=("exposure_balls", "count"),
        mean_val_add=("val_add", "mean"),
        se_latent=("se_latent_m5", "mean")
    )
    agg_b["name"] = agg_b.index.map(p_map)
    agg_b["role"] = agg_b.index.map(role_map)
    agg_b["total_career_balls"] = agg_b.index.map(crosswalk.set_index("player_id")["balls_faced"].to_dict())
    agg_b["lb90"] = agg_b["mean_val_add"] - 1.645 * agg_b["se_latent"]

    # Filter: career balls >= 500 (or >= 300) and press balls >= 100
    q_b = agg_b[(agg_b["total_career_balls"] >= 500) & (agg_b["n_press_balls"] >= 100)].sort_values("lb90", ascending=False)
    
    print("=================== TOP 10 BATTERS BY LB90 (balls >= 500) ===================")
    for i, (pid, r) in enumerate(q_b.head(10).iterrows(), 1):
        print(f"{i}. {r['name']} [ID {pid}] | Role: {r['role']} | Career: {r['total_career_balls']}b | Press: {r['n_press_balls']}b | ValAdd: {r['mean_val_add']*100:+.2f}% | se: {r['se_latent']:.4f} | LB90: {r['lb90']*100:+.2f}%")

    # 2. Bowlers
    bowl_oof = oof[oof["domain"] == "Bowler"].copy()
    bowl_oof["is_press"] = bowl_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    press_bw = bowl_oof[bowl_oof["is_press"]].copy()
    press_bw["delta"] = press_bw["pred_m5"] - press_bw["pred_m4"]

    agg_bw = press_bw.groupby("player_id").agg(
        n_press_spells=("exposure_balls", "count"),
        mean_delta=("delta", "mean"),
        se_latent=("se_latent_m5", "mean")
    )
    agg_bw["name"] = agg_bw.index.map(p_map)
    agg_bw["role"] = agg_bw.index.map(role_map)
    agg_bw["total_career_balls"] = agg_bw.index.map(crosswalk.set_index("player_id")["balls_bowled"].to_dict())
    agg_bw["ub90"] = agg_bw["mean_delta"] + 1.645 * agg_bw["se_latent"]

    # Filter: career balls >= 500 and spells >= 20
    q_bw = agg_bw[(agg_bw["total_career_balls"] >= 500) & (agg_bw["n_press_spells"] >= 20)].sort_values("ub90", ascending=True)

    print("\n=================== TOP 10 BOWLERS BY UB90 (balls >= 500) ===================")
    for i, (pid, r) in enumerate(q_bw.head(10).iterrows(), 1):
        print(f"{i}. {r['name']} [ID {pid}] | Role: {r['role']} | Career: {r['total_career_balls']}b | Press Spells: {r['n_press_spells']} | Delta: {r['mean_delta']:+.3f} RPO | se: {r['se_latent']:.4f} | UB90: {r['ub90']:+.3f} RPO")

    return q_b.head(10), q_bw.head(10)

if __name__ == "__main__":
    main()
