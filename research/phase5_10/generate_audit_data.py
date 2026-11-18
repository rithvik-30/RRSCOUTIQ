"""
Phase 5.10: Data Extraction and Verification Script
Prepares exact numbers for all tables in PHASE_5_10_INDEPENDENT_ADVERSARIAL_AUDIT.md.
"""

import pandas as pd
import numpy as np
import json

raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
clean = raw[(raw["is_dli_valid"] == 1) & (raw["ext_is_legal_delivery"] == 1)].copy()

oof = pd.read_csv("audit_reports/M5_5B_4_3_8/M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv")
cw = pd.read_csv("data/enriched/player_crosswalk_m5_5.csv")
p_map = cw.set_index("player_id")["canonical_name"].to_dict()

# Batters
bat_oof = oof[oof["domain"] == "Batter"].copy()
bat_oof["is_press"] = bat_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
press_b = bat_oof[bat_oof["is_press"]].copy()
press_b["val_add"] = press_b["pred_m5"] - press_b["pred_m4"]

actual_bat_balls = clean.groupby("striker_id")["ext_is_legal_delivery"].count().to_dict()

agg_b = press_b.groupby("player_id").agg(
    n_press_balls=("exposure_balls", "count"),
    mean_val_add=("val_add", "mean"),
    se_latent=("se_latent_m5", "mean")
).reset_index()
agg_b["canonical_balls"] = agg_b["player_id"].map(actual_bat_balls).fillna(0).astype(int)
agg_b["name"] = agg_b["player_id"].map(p_map)
agg_b["lb90"] = agg_b["mean_val_add"] - 1.645 * agg_b["se_latent"]
agg_b["eligible"] = (agg_b["canonical_balls"] >= 500) & (agg_b["n_press_balls"] >= 100) & (agg_b["se_latent"] <= 0.035)

top10_b = agg_b[agg_b["eligible"]].sort_values("lb90", ascending=False).reset_index(drop=True).head(10)

# Bowlers
bowl_oof = oof[oof["domain"] == "Bowler"].copy()
bowl_oof["is_press"] = bowl_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
press_bw = bowl_oof[bowl_oof["is_press"]].copy()
press_bw["delta"] = press_bw["pred_m5"] - press_bw["pred_m4"]

actual_bowl_balls = clean.groupby("bowler_id")["ext_is_legal_delivery"].count().to_dict()

agg_bw = press_bw.groupby("player_id").agg(
    n_press_spells=("exposure_balls", "count"),
    mean_delta=("delta", "mean"),
    se_latent=("se_latent_m5", "mean")
).reset_index()
agg_bw["canonical_balls"] = agg_bw["player_id"].map(actual_bowl_balls).fillna(0).astype(int)
agg_bw["name"] = agg_bw["player_id"].map(p_map)
agg_bw["ub90"] = agg_bw["mean_delta"] + 1.645 * agg_bw["se_latent"]
agg_bw["eligible"] = (agg_bw["canonical_balls"] >= 500) & (agg_bw["n_press_spells"] >= 20) & (agg_bw["se_latent"] <= 0.65)

top10_bw = agg_bw[agg_bw["eligible"]].sort_values("ub90", ascending=True).reset_index(drop=True).head(10)

print("Top 10 Batters Lower Bounds:")
for idx, r in top10_b.iterrows():
    print(f"#{idx+1} {r['name']}: delta_eb={r['mean_val_add']*100:+.2f}%, se={r['se_latent']:.4f}, lb90={r['lb90']*100:+.2f}%")

print("\nTop 10 Bowlers Upper Bounds:")
for idx, r in top10_bw.iterrows():
    print(f"#{idx+1} {r['name']}: delta_eb={r['mean_delta']:+.3f} RPO, se={r['se_latent']:.4f}, ub90={r['ub90']:+.3f} RPO")

# Rotation rate average across Top 10 Batters
with open("scratch/phase5/player_validation_summary.json") as f:
    pv = json.load(f)

rot_rates = [p["press_rot_pct"] for p in pv["batters"]]
print(f"\nAverage Top 10 Batter Rotation Rate: {np.mean(rot_rates):.1f}% (Reported: 37.6% - let's check individual: {rot_rates})")
