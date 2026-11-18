"""
Phase 5.12 - Task 2: Production Ranking Equivalence Audit
Compares official production ranking pipeline (from run_validation_b4_3_8.py & extract_exact_rankings.py)
against Phase 5.11 (run_production_walk_forward.py) on an identical historical training dataset (Window A: 2022-2024).

Verifies:
- Contextual hierarchy fitting
- Training-only data construction
- Batter context aggregation
- Batter career aggregation
- Bowler spell aggregation
- Posterior calculations
- Contextual expectations
- Standard error aggregation
- Eligibility filters
- Conservative bounds
- Ranking order and deterministic tie-breaking
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_4_3_8.hierarchical_engine_b4_3_8 import (
    ContextualHierarchyB438,
    PlayerPosteriorBaselineEstimatorB438
)
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells

def audit_ranking_equivalence():
    print("=" * 80)
    print("PHASE 5.12 - TASK 2: PRODUCTION RANKING EQUIVALENCE AUDIT")
    print("=" * 80)

    # 1. Load canonical data
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    matches = pd.read_csv("data/extracted/matches.csv")
    m_date_map = matches.set_index("match_id")["match_date"].to_dict()
    raw["match_date"] = raw["match_id"].map(m_date_map)
    raw["year"] = pd.to_datetime(raw["match_date"]).dt.year

    clean = raw[raw["is_dli_valid"] == True].copy()
    clean["phase"] = clean["pre_match_phase"].astype(str)
    clean["tier"] = clean["pre_pressure_tier"].astype(str)
    clean["is_boundary"] = ((clean["ext_is_four"] == 1) | (clean["ext_is_six"] == 1)).astype(int)
    clean["is_legal"] = (clean["ext_is_legal_delivery"] == 1).astype(int)

    cw = pd.read_csv("data/enriched/player_crosswalk_m5_5.csv")
    p_map = cw.set_index("player_id")["canonical_name"].to_dict()
    role_map = cw.set_index("player_id")["role_discipline"].to_dict()

    # Training data for Window A (2022-2024)
    train_A = clean[clean["year"].isin([2022, 2023, 2024])].copy()
    train_legal = train_A[train_A["is_legal"] == 1].copy()
    print(f"Identical Training Dataset: {len(train_A)} deliveries, {len(train_legal)} legal, {train_A['match_id'].nunique()} matches.")

    # 2. Run Official Production Reference Pipeline
    print("\nRunning Official Production Reference Pipeline...")
    t0 = time.time()
    np.random.seed(42)
    context_hier = ContextualHierarchyB438(n_boot=20)
    context_hier.fit(train_A)
    estimator = PlayerPosteriorBaselineEstimatorB438(context_hier)

    # Batters Reference Pipeline
    bat_id_col = "striker_id"
    bat_car_agg = train_legal.groupby(bat_id_col).agg(
        career_balls=("is_legal", "count"),
        career_boundaries=("is_boundary", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")

    bat_match_counts = train_legal.groupby([bat_id_col, "phase", "tier", "match_id"]).size()
    bat_match_balls_by_ctx = bat_match_counts.groupby(level=[0, 1, 2]).apply(list).to_dict()

    bat_ctx_agg = train_legal.groupby([bat_id_col, "phase", "tier"]).agg(
        context_balls=("is_legal", "count"),
        context_boundaries=("is_boundary", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")

    for k in bat_ctx_agg:
        bat_ctx_agg[k]["match_balls_list"] = bat_match_balls_by_ctx.get(k, [])

    train_legal["is_press"] = train_legal["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    press_bat_train = train_legal[train_legal["is_press"]].copy()

    post_cache_bat = {}
    val_add_list = []
    se_latent_bat_list = []

    for idx, r in press_bat_train.iterrows():
        pid = r[bat_id_col]
        ph = r["phase"]
        tr = r["tier"]

        pred_m4 = context_hier.get_context_expectation(ph, tr, "batter_boundary")
        cache_key = (pid, ph, tr)
        if cache_key not in post_cache_bat:
            ctx_data = bat_ctx_agg.get(cache_key, {"context_balls": 0, "context_boundaries": None, "matches": 0, "match_balls_list": None})
            car_data = bat_car_agg.get(pid, {"career_balls": 0, "career_boundaries": None, "matches": 0})
            rec = estimator.estimate_batter_boundary_posterior(
                player_id=pid,
                phase=ph,
                tier=tr,
                context_legal_balls=ctx_data["context_balls"],
                context_boundaries=ctx_data["context_boundaries"],
                context_matches=ctx_data["matches"],
                career_legal_balls=car_data["career_balls"],
                career_boundaries=car_data["career_boundaries"],
                career_matches=car_data["matches"],
                min_context_screening_balls=30,
                context_match_balls_list=ctx_data.get("match_balls_list", None)
            )
            post_cache_bat[cache_key] = (rec.shrunk_baseline, rec.standard_error)

        m5_val, se_val = post_cache_bat[cache_key]
        val_add_list.append(m5_val - pred_m4)
        se_latent_bat_list.append(se_val)

    press_bat_train["val_add"] = val_add_list
    press_bat_train["se_latent"] = se_latent_bat_list

    ref_agg_b = press_bat_train.groupby(bat_id_col).agg(
        n_press_balls=("is_legal", "count"),
        mean_val_add=("val_add", "mean"),
        se_latent=("se_latent", "mean")
    ).reset_index()

    career_counts_b = train_legal.groupby(bat_id_col)["is_legal"].count().to_dict()
    ref_agg_b["canonical_balls"] = ref_agg_b[bat_id_col].map(career_counts_b).fillna(0).astype(int)
    ref_agg_b["name"] = ref_agg_b[bat_id_col].map(p_map)
    ref_agg_b["role"] = ref_agg_b[bat_id_col].map(role_map)
    ref_agg_b["lb90"] = ref_agg_b["mean_val_add"] - 1.645 * ref_agg_b["se_latent"]
    ref_agg_b["eligible"] = (ref_agg_b["canonical_balls"] >= 500) & (ref_agg_b["n_press_balls"] >= 100) & (ref_agg_b["se_latent"] <= 0.035)

    ref_ranked_b = ref_agg_b[ref_agg_b["eligible"]].sort_values("lb90", ascending=False).reset_index(drop=True)
    ref_ranked_b["official_rank"] = ref_ranked_b.index + 1

    # Bowlers Reference Pipeline (strictly using official aggregate_bowler_spells and is_valid_spell)
    spells_df = aggregate_bowler_spells(train_A)
    # Strictly filter valid spells with legal_balls > 0
    spells_valid = spells_df[spells_df["is_valid_spell"]].copy()
    spells_valid["is_press"] = spells_valid["modal_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    ref_press_spells = spells_valid[spells_valid["is_press"]].copy()

    bowl_car_agg = train_legal.groupby("bowler_id").agg(
        legal_balls=("is_legal", "count"),
        debit_runs=("ext_bowler_debit_runs", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")

    bowl_match_counts = train_legal.groupby(["bowler_id", "phase", "tier", "match_id"]).size()
    bowl_match_balls_by_ctx = bowl_match_counts.groupby(level=[0, 1, 2]).apply(list).to_dict()

    bowl_ctx_agg = train_legal.groupby(["bowler_id", "phase", "tier"]).agg(
        legal_balls=("is_legal", "count"),
        debit_runs=("ext_bowler_debit_runs", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")

    for k in bowl_ctx_agg:
        bowl_ctx_agg[k]["match_balls_list"] = bowl_match_balls_by_ctx.get(k, [])

    train_global_econ = float(train_legal["ext_bowler_debit_runs"].sum() / train_legal["is_legal"].count() * 6.0)

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

    for idx, sp_row in ref_press_spells.iterrows():
        bid = sp_row["bowler_id"]
        mid = sp_row["match_id"]
        ph = sp_row["phase"]
        modal_t = sp_row["modal_tier"]

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

    ref_press_spells["delta"] = delta_list
    ref_press_spells["se_latent"] = se_latent_bowl_list

    ref_agg_bw = ref_press_spells.groupby("bowler_id").agg(
        n_press_spells=("match_id", "count"),
        mean_delta=("delta", "mean"),
        se_latent=("se_latent", "mean")
    ).reset_index()

    career_counts_bw = train_legal.groupby("bowler_id")["is_legal"].count().to_dict()
    ref_agg_bw["canonical_balls"] = ref_agg_bw["bowler_id"].map(career_counts_bw).fillna(0).astype(int)
    ref_agg_bw["name"] = ref_agg_bw["bowler_id"].map(p_map)
    ref_agg_bw["role"] = ref_agg_bw["bowler_id"].map(role_map)
    ref_agg_bw["ub90"] = ref_agg_bw["mean_delta"] + 1.645 * ref_agg_bw["se_latent"]
    ref_agg_bw["eligible"] = (ref_agg_bw["canonical_balls"] >= 500) & (ref_agg_bw["n_press_spells"] >= 20) & (ref_agg_bw["se_latent"] <= 0.65)

    ref_ranked_bw = ref_agg_bw[ref_agg_bw["eligible"]].sort_values("ub90", ascending=True).reset_index(drop=True)
    ref_ranked_bw["official_rank"] = ref_ranked_bw.index + 1
    print(f"Reference pipeline execution completed in {time.time()-t0:.2f}s.")

    # 3. Load Phase 5.11 outputs for comparison
    with open("research/phase5_11/prospective_rankings.json", "r") as f:
        p511_data = json.load(f)["window_a"]

    p511_bat = pd.DataFrame(p511_data["full_batters"])
    p511_bat["p511_rank"] = p511_bat.index + 1
    p511_bowl = pd.DataFrame(p511_data["full_bowlers"])
    p511_bowl["p511_rank"] = p511_bowl.index + 1

    # 4. Compare Batters
    print("\n--- COMPARING ELIGIBLE BATTERS ---")
    print(f"Reference eligible batters count: {len(ref_ranked_b)}")
    print(f"Phase 5.11 eligible batters count: {len(p511_bat)}")

    merged_bat = pd.merge(
        ref_ranked_b,
        p511_bat,
        left_on="striker_id",
        right_on="player_id",
        suffixes=("_ref", "_p511")
    )

    max_diff_val_add_b = np.max(np.abs(merged_bat["mean_val_add_ref"] - merged_bat["mean_val_add_p511"]))
    max_diff_se_b = np.max(np.abs(merged_bat["se_latent_ref"] - merged_bat["se_latent_p511"]))
    max_diff_lb90_b = np.max(np.abs(merged_bat["lb90_ref"] - merged_bat["lb_90"]))
    rank_diff_b = np.max(np.abs(merged_bat["official_rank"] - merged_bat["p511_rank"]))

    print(f"Max abs diff in Batter ValAdd:   {max_diff_val_add_b:.10e}")
    print(f"Max abs diff in Batter SE:       {max_diff_se_b:.10e}")
    print(f"Max abs diff in Batter LB90:     {max_diff_lb90_b:.10e}")
    print(f"Max rank position difference:    {rank_diff_b}")

    # 5. Compare Bowlers
    print("\n--- COMPARING ELIGIBLE BOWLERS ---")
    print(f"Reference eligible bowlers count: {len(ref_ranked_bw)}")
    print(f"Phase 5.11 eligible bowlers count: {len(p511_bowl)}")

    merged_bowl = pd.merge(
        ref_ranked_bw,
        p511_bowl,
        left_on="bowler_id",
        right_on="player_id",
        suffixes=("_ref", "_p511")
    )

    max_diff_delta_bw = np.max(np.abs(merged_bowl["mean_delta_ref"] - merged_bowl["mean_delta_p511"]))
    max_diff_se_bw = np.max(np.abs(merged_bowl["se_latent_ref"] - merged_bowl["se_latent_p511"]))
    max_diff_ub90_bw = np.max(np.abs(merged_bowl["ub90_ref"] - merged_bowl["ub_90"]))
    rank_diff_bw = np.max(np.abs(merged_bowl["official_rank"] - merged_bowl["p511_rank"]))

    print(f"Max abs diff in Bowler Delta:    {max_diff_delta_bw:.10e}")
    print(f"Max abs diff in Bowler SE:       {max_diff_se_bw:.10e}")
    print(f"Max abs diff in Bowler UB90:     {max_diff_ub90_bw:.10e}")
    print(f"Max rank position difference:    {rank_diff_bw}")

    # Top 10 Comparison Table Batters
    print("\n=== TOP 10 BATTERS COMPARISON ===")
    bat_comp_records = []
    for i in range(10):
        r_ref = ref_ranked_b.iloc[i]
        r_p = p511_bat.iloc[i]
        diff_lb = abs(r_ref["lb90"] - r_p["lb_90"])
        print(f"#{i+1}: Ref={r_ref['name']} (ID {r_ref['striker_id']}, LB={r_ref['lb90']*100:+.2f}%) | P511={r_p['name']} (ID {r_p['player_id']}, LB={r_p['lb_90']*100:+.2f}%) | Diff={diff_lb:.2e}")
        bat_comp_records.append({
            "rank": i + 1,
            "ref_name": r_ref["name"],
            "ref_id": int(r_ref["striker_id"]),
            "ref_lb90": float(r_ref["lb90"]),
            "p511_name": r_p["name"],
            "p511_id": int(r_p["player_id"]),
            "p511_lb90": float(r_p["lb_90"]),
            "abs_diff_lb90": float(diff_lb)
        })

    # Top 10 Comparison Table Bowlers
    print("\n=== TOP 10 BOWLERS COMPARISON ===")
    bowl_comp_records = []
    for i in range(10):
        r_ref = ref_ranked_bw.iloc[i]
        r_p = p511_bowl.iloc[i]
        diff_ub = abs(r_ref["ub90"] - r_p["ub_90"])
        print(f"#{i+1}: Ref={r_ref['name']} (ID {r_ref['bowler_id']}, UB={r_ref['ub90']:+.3f}) | P511={r_p['name']} (ID {r_p['player_id']}, UB={r_p['ub_90']:+.3f}) | Diff={diff_ub:.2e}")
        bowl_comp_records.append({
            "rank": i + 1,
            "ref_name": r_ref["name"],
            "ref_id": int(r_ref["bowler_id"]),
            "ref_ub90": float(r_ref["ub90"]),
            "p511_name": r_p["name"],
            "p511_id": int(r_p["player_id"]),
            "p511_ub90": float(r_p["ub_90"]),
            "abs_diff_ub90": float(diff_ub)
        })

    results = {
        "dataset_deliveries": len(train_A),
        "dataset_matches": int(train_A["match_id"].nunique()),
        "batters": {
            "eligible_count_ref": int(len(ref_ranked_b)),
            "eligible_count_p511": int(len(p511_bat)),
            "max_abs_diff_val_add": float(max_diff_val_add_b),
            "max_abs_diff_se": float(max_diff_se_b),
            "max_abs_diff_lb90": float(max_diff_lb90_b),
            "max_rank_position_difference": int(rank_diff_b),
            "top10_comparison": bat_comp_records
        },
        "bowlers": {
            "eligible_count_ref": int(len(ref_ranked_bw)),
            "eligible_count_p511": int(len(p511_bowl)),
            "max_abs_diff_delta": float(max_diff_delta_bw),
            "max_abs_diff_se": float(max_diff_se_bw),
            "max_abs_diff_ub90": float(max_diff_ub90_bw),
            "max_rank_position_difference": int(rank_diff_bw),
            "top10_comparison": bowl_comp_records
        }
    }

    out_file = "research/phase5_12/production_ranking_equivalence.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved Task 2 audit results to {out_file}")
    return results

if __name__ == "__main__":
    audit_ranking_equivalence()
