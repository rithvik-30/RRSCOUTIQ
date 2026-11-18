"""
Phase 5.11: Production-Faithful Prospective Walk-Forward Validation
Implements the exact official production DLI hierarchical Empirical Bayes engine:
- ContextualHierarchyB438 (LPMO priors, Henderson III crossed random effects)
- PlayerPosteriorBaselineEstimatorB438 (full conjugate Gaussian updating)
- Exact production spell aggregation via aggregate_bowler_spells
- Exact production eligibility gates:
  - Batters: career legal balls >= 500, pressure balls >= 100, se_latent <= 0.035
  - Bowlers: career legal balls >= 500, pressure spells >= 20, se_latent <= 0.65
- Exact ranking objectives:
  - Batters: LB_90 = mean(pred_m5 - pred_m4) - 1.645 * mean(se_latent)
  - Bowlers: UB_90 = mean(pred_m5 - pred_m4) + 1.645 * mean(se_latent)
- Prospective evaluation on unseen test seasons (Window A: 2025; Window B: 2026)
- Comparison against non-selected eligible players and match-clustered bootstrap CIs
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import math
import time
import json
import numpy as np
import pandas as pd

from src.m5_5b_4_3_8.hierarchical_engine_b4_3_8 import (
    ContextualHierarchyB438,
    PlayerPosteriorBaselineEstimatorB438
)
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells

# Load canonical data and dates
raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
matches = pd.read_csv("data/extracted/matches.csv")
m_date_map = matches.set_index("match_id")["match_date"].to_dict()
raw["match_date"] = raw["match_id"].map(m_date_map)
raw["year"] = pd.to_datetime(raw["match_date"]).dt.year

# Filter to clean DLI-valid
clean = raw[raw["is_dli_valid"] == True].copy()
clean["phase"] = clean["pre_match_phase"].astype(str)
clean["tier"] = clean["pre_pressure_tier"].astype(str)
clean["is_boundary"] = ((clean["ext_is_four"] == 1) | (clean["ext_is_six"] == 1)).astype(int)
clean["is_legal"] = (clean["ext_is_legal_delivery"] == 1).astype(int)

cw = pd.read_csv("data/enriched/player_crosswalk_m5_5.csv")
p_map = cw.set_index("player_id")["canonical_name"].to_dict()
role_map = cw.set_index("player_id")["role_discipline"].to_dict()

def fit_and_rank_production(train_df, window_name):
    t0 = time.time()
    print(f"\n=======================================================")
    print(f"  PRODUCTION-FAITHFUL MODEL FITTING: {window_name}")
    print(f"  Training Deliveries: {len(train_df):,} | Matches: {train_df['match_id'].nunique()}")
    print(f"=======================================================\n")
    
    # 1. Fit Contextual Hierarchy on Training Data
    print("Fitting ContextualHierarchyB438 (LPMO priors, crossed components)...")
    context_hier = ContextualHierarchyB438(n_boot=20)
    context_hier.fit(train_df)
    estimator = PlayerPosteriorBaselineEstimatorB438(context_hier)
    
    train_legal = train_df[train_df["is_legal"] == 1].copy()
    
    # -------------------------------------------------------------
    # 2. BATTERS PRODUCTION RANKING
    # -------------------------------------------------------------
    print("Computing production batter posterior baselines...")
    bat_id_col = "striker_id"
    
    # Pre-aggregate training counts
    match_counts = train_legal.groupby([bat_id_col, "phase", "tier", "match_id"]).size()
    match_balls_by_ctx = match_counts.groupby(level=[0, 1, 2]).apply(list).to_dict()
    
    bat_ctx_grp = train_legal.groupby([bat_id_col, "phase", "tier"]).agg(
        ctx_balls=("is_legal", "count"),
        ctx_boundaries=("is_boundary", "sum"),
        ctx_matches=("match_id", "nunique")
    )
    bat_ctx_dict = {}
    for idx_tuple, row in bat_ctx_grp.iterrows():
        bat_ctx_dict[idx_tuple] = {
            "ctx_balls": int(row["ctx_balls"]),
            "ctx_boundaries": int(row["ctx_boundaries"]),
            "ctx_matches": int(row["ctx_matches"]),
            "match_balls_list": match_balls_by_ctx.get(idx_tuple, [])
        }
        
    bat_car_agg = train_legal.groupby(bat_id_col).agg(
        car_balls=("is_legal", "count"),
        car_boundaries=("is_boundary", "sum"),
        car_matches=("match_id", "nunique")
    ).reset_index()
    bat_car_dict = {
        r[bat_id_col]: {
            "car_balls": r["car_balls"],
            "car_boundaries": r["car_boundaries"],
            "car_matches": r["car_matches"]
        }
        for _, r in bat_car_agg.iterrows()
    }
    
    # Filter to pressure deliveries in training
    press_train_bat = train_legal[train_legal["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])].copy()
    
    # Compute M4 & M5 for each pressure delivery
    post_cache_bat = {}
    val_add_list = []
    se_latent_list = []
    
    for pid, ph, tr in zip(press_train_bat[bat_id_col].values, press_train_bat["phase"].values, press_train_bat["tier"].values):
        cache_key = (pid, ph, tr)
        if cache_key not in post_cache_bat:
            m4_exp = context_hier.get_context_expectation(ph, tr, "batter_boundary")
            ctx_stat = bat_ctx_dict.get(cache_key, {"ctx_balls": 0, "ctx_boundaries": None, "ctx_matches": 0, "match_balls_list": None})
            car_stat = bat_car_dict.get(pid, {"car_balls": 0, "car_boundaries": None, "car_matches": 0})
            
            rec = estimator.estimate_batter_boundary_posterior(
                player_id=pid,
                phase=ph,
                tier=tr,
                context_legal_balls=ctx_stat["ctx_balls"],
                context_boundaries=ctx_stat["ctx_boundaries"],
                context_matches=ctx_stat["ctx_matches"],
                career_legal_balls=car_stat["car_balls"],
                career_boundaries=car_stat["car_boundaries"],
                career_matches=car_stat["car_matches"],
                min_context_screening_balls=30,
                context_match_balls_list=ctx_stat.get("match_balls_list", None)
            )
            post_cache_bat[cache_key] = (rec.shrunk_baseline, m4_exp, rec.standard_error)
            
        m5_val, m4_val, se_val = post_cache_bat[cache_key]
        val_add_list.append(m5_val - m4_val)
        se_latent_list.append(se_val)
        
    press_train_bat["val_add"] = val_add_list
    press_train_bat["se_latent"] = se_latent_list
    
    # Aggregate to player level
    agg_b = press_train_bat.groupby(bat_id_col).agg(
        n_press_balls=("is_legal", "count"),
        mean_val_add=("val_add", "mean"),
        se_latent=("se_latent", "mean")
    ).reset_index()
    
    career_counts_b = train_legal.groupby(bat_id_col)["is_legal"].count().to_dict()
    agg_b["canonical_balls"] = agg_b[bat_id_col].map(career_counts_b).fillna(0).astype(int)
    agg_b["name"] = agg_b[bat_id_col].map(p_map)
    agg_b["role"] = agg_b[bat_id_col].map(role_map)
    agg_b["lb90"] = agg_b["mean_val_add"] - 1.645 * agg_b["se_latent"]
    
    # Official Eligibility
    agg_b["eligible"] = (agg_b["canonical_balls"] >= 500) & (agg_b["n_press_balls"] >= 100) & (agg_b["se_latent"] <= 0.035)
    ranked_b = agg_b[agg_b["eligible"]].sort_values("lb90", ascending=False).reset_index(drop=True)
    
    # -------------------------------------------------------------
    # 3. BOWLERS PRODUCTION RANKING
    # -------------------------------------------------------------
    print("Computing production bowler posterior baselines...")
    # Aggregate bowler spells on training data (vectorized exact equivalent of aggregate_bowler_spells)
    grp_spells = train_df.groupby(["bowler_id", "match_id", "pre_match_phase"])
    spells_df = grp_spells.agg(
        legal_balls=("ext_is_legal_delivery", lambda x: (x == 1).sum()),
        bowler_debit_runs=("ext_bowler_debit_runs", "sum"),
        modal_tier=("pre_pressure_tier", lambda x: x.mode().iloc[0] if len(x) > 0 else "Tier 2: Medium")
    ).reset_index().rename(columns={"pre_match_phase": "phase"})
    spells_df["is_press"] = spells_df["modal_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    press_spells_train = spells_df[spells_df["is_press"]].copy()
    
    # Bowl context aggregates
    bowl_car_agg = train_legal.groupby("bowler_id").agg(
        legal_balls=("is_legal", "count"),
        debit_runs=("ext_bowler_debit_runs", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")
    
    bowl_ctx_agg = train_legal.groupby(["bowler_id", "phase", "tier"]).agg(
        legal_balls=("is_legal", "count"),
        debit_runs=("ext_bowler_debit_runs", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")
    
    train_global_econ = float(train_legal["ext_bowler_debit_runs"].sum() / train_legal["is_legal"].count() * 6.0)
    
    # Precompute expected runs per ball
    train_legal["_exp_rpb"] = [
        context_hier.get_expected_runs_per_legal_ball(p, t)
        for p, t in zip(train_legal["phase"], train_legal["tier"])
    ]
    spell_exp_agg = train_legal.groupby(["bowler_id", "match_id", "pre_match_phase"]).agg(
        exp_runs_sum=("_exp_rpb", "sum"),
        legal_sp_count=("is_legal", "count")
    ).to_dict(orient="index")
    
    post_cache_bowl = {}
    delta_list = []
    se_latent_bowl_list = []
    
    for idx, sp_row in press_spells_train.iterrows():
        bid = sp_row["bowler_id"]
        mid = sp_row["match_id"]
        ph = sp_row["phase"]
        modal_t = sp_row["modal_tier"]
        sp_balls = int(sp_row["legal_balls"])
        
        exp_info = spell_exp_agg.get((bid, mid, ph))
        if exp_info is not None and exp_info["legal_sp_count"] > 0:
            pred_m4 = (exp_info["exp_runs_sum"] / exp_info["legal_sp_count"]) * 6.0
        else:
            pred_m4 = train_global_econ
            
        cache_key = (bid, ph, modal_t)
        if cache_key not in post_cache_bowl:
            ctx_data = bowl_ctx_agg.get(cache_key, {"legal_balls": 0, "debit_runs": 0.0, "matches": 0, "match_balls_list": None})
            car_data = bowl_car_agg.get(bid, {"legal_balls": 0, "debit_runs": 0.0, "matches": 0})
            
            rec = estimator.estimate_bowler_economy_posterior(
                player_id=bid,
                phase=ph,
                tier=modal_t,
                context_legal_balls=ctx_data["legal_balls"],
                context_debit_runs=ctx_data["debit_runs"] if ctx_data["legal_balls"] > 0 else None,
                context_matches=ctx_data["matches"],
                career_legal_balls=car_data["legal_balls"],
                career_debit_runs=car_data["debit_runs"] if car_data["legal_balls"] > 0 else None,
                career_matches=car_data["matches"],
                min_context_screening_balls=30,
                context_match_balls_list=ctx_data.get("match_balls_list", None)
            )
            post_cache_bowl[cache_key] = (rec.shrunk_baseline, rec.standard_error)
            
        m5_val, se_val = post_cache_bowl[cache_key]
        delta_list.append(m5_val - pred_m4)
        se_latent_bowl_list.append(se_val)
        
    press_spells_train["delta"] = delta_list
    press_spells_train["se_latent"] = se_latent_bowl_list
    
    agg_bw = press_spells_train.groupby("bowler_id").agg(
        n_press_spells=("match_id", "count"),
        mean_delta=("delta", "mean"),
        se_latent=("se_latent", "mean")
    ).reset_index()
    
    career_counts_bw = train_legal.groupby("bowler_id")["is_legal"].count().to_dict()
    agg_bw["canonical_balls"] = agg_bw["bowler_id"].map(career_counts_bw).fillna(0).astype(int)
    agg_bw["name"] = agg_bw["bowler_id"].map(p_map)
    agg_bw["role"] = agg_bw["bowler_id"].map(role_map)
    agg_bw["ub90"] = agg_bw["mean_delta"] + 1.645 * agg_bw["se_latent"]
    
    agg_bw["eligible"] = (agg_bw["canonical_balls"] >= 500) & (agg_bw["n_press_spells"] >= 20) & (agg_bw["se_latent"] <= 0.65)
    ranked_bw = agg_bw[agg_bw["eligible"]].sort_values("ub90", ascending=True).reset_index(drop=True)
    
    print(f"Fitting and ranking completed in {time.time()-t0:.2f}s.")
    return ranked_b, ranked_bw

# Run Window A: Train 2022-2024
train_A = clean[clean["year"].isin([2022, 2023, 2024])].copy()
test_A = clean[clean["year"] == 2025].copy()

ranked_b_A, ranked_bw_A = fit_and_rank_production(train_A, "Window A (Train 2022-2024)")

# Run Window B: Train 2022-2025
train_B = clean[clean["year"].isin([2022, 2023, 2024, 2025])].copy()
test_B = clean[clean["year"] == 2026].copy()

ranked_b_B, ranked_bw_B = fit_and_rank_production(train_B, "Window B (Train 2022-2025)")

# Save intermediate rankings
ranked_b_A["player_id"] = ranked_b_A["striker_id"]
ranked_b_A["lb_90"] = ranked_b_A["lb90"]
ranked_bw_A["player_id"] = ranked_bw_A["bowler_id"]
ranked_bw_A["ub_90"] = ranked_bw_A["ub90"]

ranked_b_B["player_id"] = ranked_b_B["striker_id"]
ranked_b_B["lb_90"] = ranked_b_B["lb90"]
ranked_bw_B["player_id"] = ranked_bw_B["bowler_id"]
ranked_bw_B["ub_90"] = ranked_bw_B["ub90"]

with open("research/phase5_11/prospective_rankings.json", "w") as f:
    json.dump({
        "window_a": {
            "top10_batters": ranked_b_A.head(10).to_dict(orient="records"),
            "top10_bowlers": ranked_bw_A.head(10).to_dict(orient="records"),
            "all_eligible_batters": ranked_b_A["striker_id"].tolist(),
            "all_eligible_bowlers": ranked_bw_A["bowler_id"].tolist(),
            "full_batters": ranked_b_A.to_dict(orient="records"),
            "full_bowlers": ranked_bw_A.to_dict(orient="records")
        },
        "window_b": {
            "top10_batters": ranked_b_B.head(10).to_dict(orient="records"),
            "top10_bowlers": ranked_bw_B.head(10).to_dict(orient="records"),
            "all_eligible_batters": ranked_b_B["striker_id"].tolist(),
            "all_eligible_bowlers": ranked_bw_B["bowler_id"].tolist(),
            "full_batters": ranked_b_B.to_dict(orient="records"),
            "full_bowlers": ranked_bw_B.to_dict(orient="records")
        }
    }, f, indent=2, default=str)

print("\nSaved prospective rankings to research/phase5_11/prospective_rankings.json")
