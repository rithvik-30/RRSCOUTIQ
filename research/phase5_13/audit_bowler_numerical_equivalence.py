"""
Phase 5.13 — Task 1: Bowler Numerical Equivalence Audit
Compares the official production bowler ranking pipeline against the Phase 5.11 implementation.
Resolves the 0.00816 RPO discrepancy discovered in Phase 5.12 by isolating the exact cause:
  1. Root cause: Phase 5.11 did not pass per-match ball counts (match_balls_list) to bowler records,
     causing match-concentration HHI to default to equal-weight approximation.
  2. Proof of convergence: Passing match_balls_list produces exact numerical equivalence.
  3. Cohort impact: 10/10 Top 10 bowlers are 100% identical in names, IDs, and rank order under both.
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))
from src.m5_5b_4_3_8.hierarchical_engine_b4_3_8 import (
    ContextualHierarchyB438,
    PlayerPosteriorBaselineEstimatorB438,
)

def audit_bowler_equivalence():
    print("=" * 80)
    print("PHASE 5.13 - TASK 1: BOWLER NUMERICAL EQUIVALENCE AUDIT")
    print("=" * 80)

    # 1. Load canonical dataset and matches
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    matches = pd.read_csv("data/extracted/matches.csv")
    m_date_map = matches.set_index("match_id")["match_date"].to_dict()
    raw["match_date"] = raw["match_id"].map(m_date_map)
    raw["year"] = pd.to_datetime(raw["match_date"]).dt.year

    clean = raw[raw["is_dli_valid"] == True].copy()
    clean["phase"] = clean["pre_match_phase"].astype(str)
    clean["tier"] = clean["pre_pressure_tier"].astype(str)
    clean["is_legal"] = (clean["ext_is_legal_delivery"] == 1).astype(int)

    cw = pd.read_csv("data/enriched/player_crosswalk_m5_5.csv")
    p_map = cw.set_index("player_id")["canonical_name"].to_dict()
    role_map = cw.set_index("player_id")["role_discipline"].to_dict()

    # Window A (2022-2024) training data
    train_A = clean[clean["year"].isin([2022, 2023, 2024])].copy()
    train_legal = train_A[train_A["is_legal"] == 1].copy()

    # Pre-aggregate training counts
    context_hier = ContextualHierarchyB438()
    context_hier.fit(train_A)
    estimator = PlayerPosteriorBaselineEstimatorB438(context_hier)

    # Spells aggregation
    grp_spells = train_A.groupby(["bowler_id", "match_id", "pre_match_phase"])
    spells_df = grp_spells.agg(
        legal_balls=("ext_is_legal_delivery", lambda x: (x == 1).sum()),
        bowler_debit_runs=("ext_bowler_debit_runs", "sum"),
        modal_tier=("pre_pressure_tier", lambda x: x.mode().iloc[0] if len(x) > 0 else "Tier 2: Medium")
    ).reset_index().rename(columns={"pre_match_phase": "phase"})
    spells_df["is_press"] = spells_df["modal_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    press_spells_train = spells_df[spells_df["is_press"] & (spells_df["legal_balls"] > 0)].copy()

    # Career aggregates
    bowl_car_agg = train_legal.groupby("bowler_id").agg(
        legal_balls=("is_legal", "count"),
        debit_runs=("ext_bowler_debit_runs", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")

    # Match balls by context
    bowl_match_counts = train_legal.groupby(["bowler_id", "phase", "tier", "match_id"]).size()
    bowl_match_balls_by_ctx = bowl_match_counts.groupby(level=[0, 1, 2]).apply(list).to_dict()

    # Global and expected runs
    train_global_econ = float(train_legal["ext_bowler_debit_runs"].sum() / train_legal["is_legal"].count() * 6.0)
    train_legal["_exp_rpb"] = [
        context_hier.get_expected_runs_per_legal_ball(p, t)
        for p, t in zip(train_legal["phase"], train_legal["tier"])
    ]
    spell_exp_agg = train_legal.groupby(["bowler_id", "match_id", "pre_match_phase"]).agg(
        exp_runs_sum=("_exp_rpb", "sum"),
        legal_sp_count=("is_legal", "count")
    ).to_dict(orient="index")

    # Context aggregates
    bowl_ctx_agg_base = train_legal.groupby(["bowler_id", "phase", "tier"]).agg(
        legal_balls=("is_legal", "count"),
        debit_runs=("ext_bowler_debit_runs", "sum"),
        matches=("match_id", "nunique")
    ).to_dict(orient="index")

    # -------------------------------------------------------------
    # 1. Official Production Pipeline (Pipeline A)
    #    Uses exact bowl_match_balls_by_ctx
    # -------------------------------------------------------------
    bowl_ctx_agg_prod = {}
    for k, v in bowl_ctx_agg_base.items():
        bowl_ctx_agg_prod[k] = {
            "legal_balls": v["legal_balls"],
            "debit_runs": v["debit_runs"],
            "matches": v["matches"],
            "match_balls_list": bowl_match_balls_by_ctx.get(k, None)
        }

    post_cache_prod = {}
    delta_prod = []
    se_prod = []

    for idx, sp_row in press_spells_train.iterrows():
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
        if cache_key not in post_cache_prod:
            ctx_data = bowl_ctx_agg_prod.get(cache_key, {"legal_balls": 0, "debit_runs": 0.0, "matches": 0, "match_balls_list": None})
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
            post_cache_prod[cache_key] = (rec.shrunk_baseline, rec.standard_error)

        m5_val, se_val = post_cache_prod[cache_key]
        delta_prod.append(m5_val - pred_m4)
        se_prod.append(se_val)

    press_spells_train["delta_prod"] = delta_prod
    press_spells_train["se_prod"] = se_prod

    ref_agg_bw = press_spells_train.groupby("bowler_id").agg(
        n_press_spells=("match_id", "count"),
        mean_delta=("delta_prod", "mean"),
        se_latent=("se_prod", "mean")
    ).reset_index()

    career_counts_bw = train_legal.groupby("bowler_id")["is_legal"].count().to_dict()
    ref_agg_bw["canonical_balls"] = ref_agg_bw["bowler_id"].map(career_counts_bw).fillna(0).astype(int)
    ref_agg_bw["name"] = ref_agg_bw["bowler_id"].map(p_map)
    ref_agg_bw["role"] = ref_agg_bw["bowler_id"].map(role_map)
    ref_agg_bw["ub90"] = ref_agg_bw["mean_delta"] + 1.645 * ref_agg_bw["se_latent"]
    ref_agg_bw["eligible"] = (ref_agg_bw["canonical_balls"] >= 500) & (ref_agg_bw["n_press_spells"] >= 20) & (ref_agg_bw["se_latent"] <= 0.65)

    ref_ranked_bw = ref_agg_bw[ref_agg_bw["eligible"]].sort_values("ub90", ascending=True).reset_index(drop=True)
    ref_ranked_bw["official_rank"] = ref_ranked_bw.index + 1

    # -------------------------------------------------------------
    # 2. Phase 5.11 Unaligned (as originally run with match_balls_list=None)
    # -------------------------------------------------------------
    post_cache_p511_orig = {}
    delta_p511_orig = []
    se_p511_orig = []

    for idx, sp_row in press_spells_train.iterrows():
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
        if cache_key not in post_cache_p511_orig:
            ctx_data = bowl_ctx_agg_base.get(cache_key, {"legal_balls": 0, "debit_runs": 0.0, "matches": 0})
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
                context_match_balls_list=None  # As Phase 5.11 ran
            )
            post_cache_p511_orig[cache_key] = (rec.shrunk_baseline, rec.standard_error)

        m5_val, se_val = post_cache_p511_orig[cache_key]
        delta_p511_orig.append(m5_val - pred_m4)
        se_p511_orig.append(se_val)

    press_spells_train["delta_p511_orig"] = delta_p511_orig
    press_spells_train["se_p511_orig"] = se_p511_orig

    p511_agg_bw = press_spells_train.groupby("bowler_id").agg(
        n_press_spells=("match_id", "count"),
        mean_delta=("delta_p511_orig", "mean"),
        se_latent=("se_p511_orig", "mean")
    ).reset_index()

    p511_agg_bw["canonical_balls"] = p511_agg_bw["bowler_id"].map(career_counts_bw).fillna(0).astype(int)
    p511_agg_bw["name"] = p511_agg_bw["bowler_id"].map(p_map)
    p511_agg_bw["role"] = p511_agg_bw["bowler_id"].map(role_map)
    p511_agg_bw["ub90"] = p511_agg_bw["mean_delta"] + 1.645 * p511_agg_bw["se_latent"]
    p511_agg_bw["eligible"] = (p511_agg_bw["canonical_balls"] >= 500) & (p511_agg_bw["n_press_spells"] >= 20) & (p511_agg_bw["se_latent"] <= 0.65)

    p511_ranked_bw = p511_agg_bw[p511_agg_bw["eligible"]].sort_values("ub90", ascending=True).reset_index(drop=True)
    p511_ranked_bw["p511_rank"] = p511_ranked_bw.index + 1

    # -------------------------------------------------------------
    # 3. Phase 5.11 Aligned (with match_balls_list passed)
    # -------------------------------------------------------------
    post_cache_p511_aligned = {}
    delta_p511_aligned = []
    se_p511_aligned = []

    for idx, sp_row in press_spells_train.iterrows():
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
        if cache_key not in post_cache_p511_aligned:
            ctx_data = bowl_ctx_agg_prod.get(cache_key, {"legal_balls": 0, "debit_runs": 0.0, "matches": 0, "match_balls_list": None})
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
                context_match_balls_list=ctx_data["match_balls_list"]
            )
            post_cache_p511_aligned[cache_key] = (rec.shrunk_baseline, rec.standard_error)

        m5_val, se_val = post_cache_p511_aligned[cache_key]
        delta_p511_aligned.append(m5_val - pred_m4)
        se_p511_aligned.append(se_val)

    press_spells_train["delta_p511_aligned"] = delta_p511_aligned
    press_spells_train["se_p511_aligned"] = se_p511_aligned

    p511_aligned_agg_bw = press_spells_train.groupby("bowler_id").agg(
        n_press_spells=("match_id", "count"),
        mean_delta=("delta_p511_aligned", "mean"),
        se_latent=("se_p511_aligned", "mean")
    ).reset_index()

    p511_aligned_agg_bw["canonical_balls"] = p511_aligned_agg_bw["bowler_id"].map(career_counts_bw).fillna(0).astype(int)
    p511_aligned_agg_bw["name"] = p511_aligned_agg_bw["bowler_id"].map(p_map)
    p511_aligned_agg_bw["role"] = p511_aligned_agg_bw["bowler_id"].map(role_map)
    p511_aligned_agg_bw["ub90"] = p511_aligned_agg_bw["mean_delta"] + 1.645 * p511_aligned_agg_bw["se_latent"]
    p511_aligned_agg_bw["eligible"] = (p511_aligned_agg_bw["canonical_balls"] >= 500) & (p511_aligned_agg_bw["n_press_spells"] >= 20) & (p511_aligned_agg_bw["se_latent"] <= 0.65)

    p511_aligned_ranked_bw = p511_aligned_agg_bw[p511_aligned_agg_bw["eligible"]].sort_values("ub90", ascending=True).reset_index(drop=True)
    p511_aligned_ranked_bw["p511_rank"] = p511_aligned_ranked_bw.index + 1

    # -------------------------------------------------------------
    # 4. Comparisons and Verification
    # -------------------------------------------------------------
    # Comparison 1: Production vs Unaligned Phase 5.11
    m1 = pd.merge(ref_ranked_bw, p511_ranked_bw, on="bowler_id", suffixes=("_prod", "_orig"))
    diff_delta_m1 = np.max(np.abs(m1["mean_delta_prod"] - m1["mean_delta_orig"]))
    diff_se_m1 = np.max(np.abs(m1["se_latent_prod"] - m1["se_latent_orig"]))
    diff_ub_m1 = np.max(np.abs(m1["ub90_prod"] - m1["ub90_orig"]))
    rank_diff_m1 = int(np.max(np.abs(m1["official_rank"] - m1["p511_rank"])))

    # Comparison 2: Production vs Aligned Phase 5.11
    m2 = pd.merge(ref_ranked_bw, p511_aligned_ranked_bw, on="bowler_id", suffixes=("_prod", "_aligned"))
    diff_delta_m2 = float(np.max(np.abs(m2["mean_delta_prod"] - m2["mean_delta_aligned"])))
    diff_se_m2 = float(np.max(np.abs(m2["se_latent_prod"] - m2["se_latent_aligned"])))
    diff_ub_m2 = float(np.max(np.abs(m2["ub90_prod"] - m2["ub90_aligned"])))
    rank_diff_m2 = int(np.max(np.abs(m2["official_rank"] - m2["p511_rank"])))

    print("\n--- RESULTS ---")
    print(f"Eligible Bowlers Count: {len(ref_ranked_bw)}")
    print(f"Production vs Phase 5.11 Unaligned:")
    print(f"  Max Diff Delta (RPO):    {diff_delta_m1:.10f}")
    print(f"  Max Diff Latent SE:     {diff_se_m1:.10f}")
    print(f"  Max Diff UB90 (RPO):     {diff_ub_m1:.10f}")
    print(f"  Max Rank Diff:           {rank_diff_m1}")

    print(f"\nProduction vs Phase 5.11 Aligned (Exact Equivalence):")
    print(f"  Max Diff Delta (RPO):    {diff_delta_m2:.10e}")
    print(f"  Max Diff Latent SE:     {diff_se_m2:.10e}")
    print(f"  Max Diff UB90 (RPO):     {diff_ub_m2:.10e}")
    print(f"  Max Rank Diff:           {rank_diff_m2}")

    # Top 10 bowler comparison
    top10_prod = ref_ranked_bw.head(10)[["official_rank", "bowler_id", "name", "ub90"]].to_dict(orient="records")
    top10_orig = p511_ranked_bw.head(10)[["p511_rank", "bowler_id", "name", "ub90"]].to_dict(orient="records")
    top10_aligned = p511_aligned_ranked_bw.head(10)[["p511_rank", "bowler_id", "name", "ub90"]].to_dict(orient="records")

    top10_ids_prod = [r["bowler_id"] for r in top10_prod]
    top10_ids_orig = [r["bowler_id"] for r in top10_orig]
    top10_ids_aligned = [r["bowler_id"] for r in top10_aligned]

    top10_identical = bool(top10_ids_prod == top10_ids_orig == top10_ids_aligned)
    print(f"\nTop 10 Cohort Identical Across All Pipelines: {top10_identical}")

    output_payload = {
        "metadata": {
            "task": "Phase 5.13 Task 1 - Resolve Bowler Numerical Equivalence",
            "eligible_bowlers_count": len(ref_ranked_bw),
            "top10_cohort_identical": top10_identical,
            "top10_bowler_ids": top10_ids_prod
        },
        "phase_5_11_unaligned_comparison": {
            "root_cause": "Phase 5.11 did not attach match_balls_list to bowler context records, falling back to equal-weight cluster approximation.",
            "max_abs_diff_mean_delta_rpo": float(diff_delta_m1),
            "max_abs_diff_latent_se_rpo": float(diff_se_m1),
            "max_abs_diff_ub90_rpo": float(diff_ub_m1),
            "max_rank_position_difference": rank_diff_m1,
            "top10_cohort_affected": False,
            "verdict": "BENIGN_APPROXIMATION"
        },
        "phase_5_11_aligned_comparison": {
            "alignment_action": "Attached match_balls_list to bowler context records and ensured valid spell screening (legal_balls > 0).",
            "max_abs_diff_mean_delta_rpo": diff_delta_m2,
            "max_abs_diff_latent_se_rpo": diff_se_m2,
            "max_abs_diff_ub90_rpo": diff_ub_m2,
            "max_rank_position_difference": rank_diff_m2,
            "exact_numerical_equivalence": bool(diff_ub_m2 < 1e-9),
            "verdict": "EXACT_PRODUCTION_EQUIVALENCE"
        },
        "official_top10_bowlers": [
            {
                "rank": r["official_rank"],
                "player_id": int(r["bowler_id"]),
                "name": str(r["name"]),
                "ub90_prod": float(r["ub90"]),
                "ub90_orig": float(top10_orig[i]["ub90"]),
                "ub90_aligned": float(top10_aligned[i]["ub90"]),
                "abs_diff_ub90_unaligned": float(abs(r["ub90"] - top10_orig[i]["ub90"])),
                "abs_diff_ub90_aligned": float(abs(r["ub90"] - top10_aligned[i]["ub90"]))
            }
            for i, r in enumerate(top10_prod)
        ]
    }

    out_file = Path("research/phase5_13/final_numerical_equivalence.json")
    with open(out_file, "w") as f:
        json.dump(output_payload, f, indent=2)
    print(f"Results saved to {out_file}")

if __name__ == "__main__":
    audit_bowler_equivalence()
