"""
Phase 5.13 — Task 3: Independent Match-Clustered Bootstrap Verification & Holm-Bonferroni Correction
Re-executes independent match-clustered bootstrap (B=10,000, seed=42) on test cohorts (2025 and 2026).
Computes exact two-sided p-values under centered null distribution H0: theta = 0 with +1 finite-sample correction.
Applies Holm-Bonferroni step-down procedure with cumulative maximum to enforce strict monotonicity:
  p_tilde_(i) = max_{j <= i} min((K - j + 1) * p_(j), 1.0)
Categorizes results into:
  - Statistically Significant after Holm Adjustment (p_adj < 0.05)
  - Directional Evidence (unadjusted p < 0.05, but p_adj >= 0.05)
  - Non-Significant (unadjusted p >= 0.05)
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path

def run_bootstrap_and_holm():
    print("=" * 80)
    print("PHASE 5.13 - TASK 3: BOOTSTRAP VERIFICATION & HOLM-BONFERRONI CORRECTION")
    print("=" * 80)

    # 1. Load canonical data
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    matches = pd.read_csv("data/extracted/matches.csv")
    m_date_map = matches.set_index("match_id")["match_date"].to_dict()
    raw["match_date"] = raw["match_id"].map(m_date_map)
    raw["year"] = pd.to_datetime(raw["match_date"]).dt.year
    clean = raw[(raw["is_dli_valid"] == 1) & (raw["ext_is_legal_delivery"] == 1)].copy()

    clean["is_four"] = (clean["ext_is_four"] == 1).astype(int)
    clean["is_six"] = (clean["ext_is_six"] == 1).astype(int)
    clean["is_boundary"] = ((clean["is_four"] == 1) | (clean["is_six"] == 1)).astype(int)

    with open("research/phase5_11/prospective_rankings.json", "r") as f:
        prospective = json.load(f)

    B = 10000
    SEED = 42
    np.random.seed(SEED)
    mc_resolution = 1.0 / (B + 1)

    print(f"Bootstrap settings: B={B:,}, Seed={SEED}, Minimum resolvable p-value={mc_resolution:.6f}")

    def evaluate_season(season_year, window_key):
        w_data = prospective[window_key]
        top10_bat_ids = set([p["player_id"] for p in w_data["top10_batters"]])
        top10_bowl_ids = set([p["player_id"] for p in w_data["top10_bowlers"]])
        all_eligible_bat_ids = set([p["player_id"] for p in w_data["full_batters"]])
        all_eligible_bowl_ids = set([p["player_id"] for p in w_data["full_bowlers"]])

        non_sel_bat_ids = all_eligible_bat_ids - top10_bat_ids
        non_sel_bowl_ids = all_eligible_bowl_ids - top10_bowl_ids

        # Subset season test data
        season_df = clean[clean["year"] == season_year].copy()
        press_df = season_df[season_df["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])].copy()

        unique_matches = press_df["match_id"].unique()
        n_matches = len(unique_matches)
        print(f"\nSeason {season_year}: {len(press_df):,} pressure balls across {n_matches} pressure-contested matches.")

        # Pre-aggregate match-level stats for speed and exact clustering
        # Batters: legal balls & boundaries
        match_bat_stats = press_df.groupby(["match_id", "striker_id"]).agg(
            balls=("ext_is_legal_delivery", "count"),
            boundaries=("is_boundary", "sum")
        ).reset_index()

        # Bowlers: legal balls & debit runs
        match_bowl_stats = press_df.groupby(["match_id", "bowler_id"]).agg(
            balls=("ext_is_legal_delivery", "count"),
            debits=("ext_bowler_debit_runs", "sum")
        ).reset_index()

        # Precompute match dictionaries
        match_data = {}
        for mid in unique_matches:
            m_bat = match_bat_stats[match_bat_stats["match_id"] == mid]
            m_bowl = match_bowl_stats[match_bowl_stats["match_id"] == mid]

            # Bat stats
            top_b_balls = m_bat[m_bat["striker_id"].isin(top10_bat_ids)]["balls"].sum()
            top_b_bnd = m_bat[m_bat["striker_id"].isin(top10_bat_ids)]["boundaries"].sum()

            non_b_balls = m_bat[m_bat["striker_id"].isin(non_sel_bat_ids)]["balls"].sum()
            non_b_bnd = m_bat[m_bat["striker_id"].isin(non_sel_bat_ids)]["boundaries"].sum()

            all_b_balls = m_bat["balls"].sum()
            all_b_bnd = m_bat["boundaries"].sum()

            # Bowl stats
            top_bw_balls = m_bowl[m_bowl["bowler_id"].isin(top10_bowl_ids)]["balls"].sum()
            top_bw_deb = m_bowl[m_bowl["bowler_id"].isin(top10_bowl_ids)]["debits"].sum()

            non_bw_balls = m_bowl[m_bowl["bowler_id"].isin(non_sel_bowl_ids)]["balls"].sum()
            non_bw_deb = m_bowl[m_bowl["bowler_id"].isin(non_sel_bowl_ids)]["debits"].sum()

            all_bw_balls = m_bowl["balls"].sum()
            all_bw_deb = m_bowl["debits"].sum()

            match_data[mid] = (
                top_b_balls, top_b_bnd, non_b_balls, non_b_bnd, all_b_balls, all_b_bnd,
                top_bw_balls, top_bw_deb, non_bw_balls, non_bw_deb, all_bw_balls, all_bw_deb
            )

        match_array = np.array([match_data[mid] for mid in unique_matches], dtype=np.float64)

        # Observed point estimates
        sum_obs = match_array.sum(axis=0)
        # Batters: boundary rate (%)
        obs_bat_top = (sum_obs[1] / sum_obs[0] * 100.0) if sum_obs[0] > 0 else 0.0
        obs_bat_non = (sum_obs[3] / sum_obs[2] * 100.0) if sum_obs[2] > 0 else 0.0
        obs_bat_all = (sum_obs[5] / sum_obs[4] * 100.0) if sum_obs[4] > 0 else 0.0

        obs_diff_bat_vs_league = obs_bat_top - obs_bat_all
        obs_diff_bat_vs_non = obs_bat_top - obs_bat_non

        # Bowlers: economy rate (RPO)
        obs_bowl_top = (sum_obs[7] / sum_obs[6] * 6.0) if sum_obs[6] > 0 else 0.0
        obs_bowl_non = (sum_obs[9] / sum_obs[8] * 6.0) if sum_obs[8] > 0 else 0.0
        obs_bowl_all = (sum_obs[11] / sum_obs[10] * 6.0) if sum_obs[10] > 0 else 0.0

        # Note: Lower economy is better. Effect is defined as (Top 10 - Benchmark)
        obs_diff_bowl_vs_league = obs_bowl_top - obs_bowl_all
        obs_diff_bowl_vs_non = obs_bowl_top - obs_bowl_non

        print(f"Observed Effects in {season_year}:")
        print(f"  Bat Top 10: {obs_bat_top:.2f}% | Non-Sel: {obs_bat_non:.2f}% | League: {obs_bat_all:.2f}%")
        print(f"    Diff vs League:  {obs_diff_bat_vs_league:+.2f} pp")
        print(f"    Diff vs Non-Sel: {obs_diff_bat_vs_non:+.2f} pp")
        print(f"  Bowl Top 10: {obs_bowl_top:.2f} RPO | Non-Sel: {obs_bowl_non:.2f} RPO | League: {obs_bowl_all:.2f} RPO")
        print(f"    Diff vs League:  {obs_diff_bowl_vs_league:+.2f} RPO")
        print(f"    Diff vs Non-Sel: {obs_diff_bowl_vs_non:+.2f} RPO")

        # Cluster bootstrap resampling
        boot_diff_bat_lg = np.empty(B, dtype=np.float64)
        boot_diff_bat_ns = np.empty(B, dtype=np.float64)
        boot_diff_bw_lg = np.empty(B, dtype=np.float64)
        boot_diff_bw_ns = np.empty(B, dtype=np.float64)

        for b in range(B):
            idx = np.random.randint(0, n_matches, size=n_matches)
            sample_sum = match_array[idx].sum(axis=0)

            b_top = (sample_sum[1] / sample_sum[0] * 100.0) if sample_sum[0] > 0 else 0.0
            b_non = (sample_sum[3] / sample_sum[2] * 100.0) if sample_sum[2] > 0 else 0.0
            b_all = (sample_sum[5] / sample_sum[4] * 100.0) if sample_sum[4] > 0 else 0.0

            bw_top = (sample_sum[7] / sample_sum[6] * 6.0) if sample_sum[6] > 0 else 0.0
            bw_non = (sample_sum[9] / sample_sum[8] * 6.0) if sample_sum[8] > 0 else 0.0
            bw_all = (sample_sum[11] / sample_sum[10] * 6.0) if sample_sum[10] > 0 else 0.0

            boot_diff_bat_lg[b] = b_top - b_all
            boot_diff_bat_ns[b] = b_top - b_non
            boot_diff_bw_lg[b] = bw_top - bw_all
            boot_diff_bw_ns[b] = bw_top - bw_non

        def calc_inferential_stats(boot_dist, obs_val):
            # Centered null distribution: theta_null* = theta* - obs_val
            null_dist = boot_dist - obs_val
            ci_low, ci_high = np.percentile(boot_dist, [2.5, 97.5])
            se = float(np.std(boot_dist, ddof=1))
            # Two-sided empirical p-value with plus-one correction
            count_extreme = np.sum(np.abs(null_dist) >= np.abs(obs_val))
            p_val = float((1 + count_extreme) / (B + 1))
            # Monte Carlo Standard Error for p-value
            mc_se = float(np.sqrt(p_val * (1 - p_val) / B))
            return {
                "observed_diff": float(obs_val),
                "bootstrap_mean": float(np.mean(boot_dist)),
                "standard_error": se,
                "ci_95_low": float(ci_low),
                "ci_95_high": float(ci_high),
                "null_centered": True,
                "p_value_two_sided": p_val,
                "mc_se": mc_se,
                "n_extreme_replications": int(count_extreme)
            }

        return {
            "batters_vs_league": calc_inferential_stats(boot_diff_bat_lg, obs_diff_bat_vs_league),
            "batters_vs_non_selected": calc_inferential_stats(boot_diff_bat_ns, obs_diff_bat_vs_non),
            "bowlers_vs_league": calc_inferential_stats(boot_diff_bw_lg, obs_diff_bowl_vs_league),
            "bowlers_vs_non_selected": calc_inferential_stats(boot_diff_bw_ns, obs_diff_bowl_vs_non)
        }

    # Evaluate 2025 and 2026
    res_2025 = evaluate_season(2025, "window_a")
    res_2026 = evaluate_season(2026, "window_b")

    # Combine all 8 primary comparisons
    comparisons = [
        {"id": "2025_batters_vs_league", "season": 2025, "discipline": "batter", "benchmark": "league", "metric": "boundary_rate_pct_diff", **res_2025["batters_vs_league"]},
        {"id": "2025_batters_vs_non_selected", "season": 2025, "discipline": "batter", "benchmark": "non_selected", "metric": "boundary_rate_pct_diff", **res_2025["batters_vs_non_selected"]},
        {"id": "2025_bowlers_vs_league", "season": 2025, "discipline": "bowler", "benchmark": "league", "metric": "economy_rpo_diff", **res_2025["bowlers_vs_league"]},
        {"id": "2025_bowlers_vs_non_selected", "season": 2025, "discipline": "bowler", "benchmark": "non_selected", "metric": "economy_rpo_diff", **res_2025["bowlers_vs_non_selected"]},
        {"id": "2026_batters_vs_league", "season": 2026, "discipline": "batter", "benchmark": "league", "metric": "boundary_rate_pct_diff", **res_2026["batters_vs_league"]},
        {"id": "2026_batters_vs_non_selected", "season": 2026, "discipline": "batter", "benchmark": "non_selected", "metric": "boundary_rate_pct_diff", **res_2026["batters_vs_non_selected"]},
        {"id": "2026_bowlers_vs_league", "season": 2026, "discipline": "bowler", "benchmark": "league", "metric": "economy_rpo_diff", **res_2026["bowlers_vs_league"]},
        {"id": "2026_bowlers_vs_non_selected", "season": 2026, "discipline": "bowler", "benchmark": "non_selected", "metric": "economy_rpo_diff", **res_2026["bowlers_vs_non_selected"]},
    ]

    # Save bootstrap results
    boot_out_path = Path("research/phase5_13/independently_verified_bootstrap.json")
    with open(boot_out_path, "w") as f:
        json.dump({
            "metadata": {
                "task": "Phase 5.13 Task 3 - Independent Bootstrap Verification",
                "replications": B,
                "seed": SEED,
                "resampling_unit": "match_id (match-clustered)",
                "null_hypothesis": "H0: theta = 0 (centered null distribution)",
                "formula": "p = (1 + sum(|theta* - theta_obs| >= |theta_obs|)) / (B + 1)"
            },
            "comparisons": comparisons
        }, f, indent=2)
    print(f"\nSaved independent bootstrap results to {boot_out_path}")

    # -------------------------------------------------------------
    # 2. Holm-Bonferroni Step-Down Correction
    # -------------------------------------------------------------
    print("\nApplying Holm-Bonferroni Step-Down Correction across the 8 primary comparisons...")
    K = len(comparisons)
    # Sort by unadjusted p-value ascending
    sorted_comps = sorted(comparisons, key=lambda x: x["p_value_two_sided"])

    holm_results = []
    running_max = 0.0

    for rank_idx, comp in enumerate(sorted_comps):
        rank = rank_idx + 1
        multiplier = K - rank + 1
        raw_p = comp["p_value_two_sided"]
        step_adj = min(multiplier * raw_p, 1.0)
        # Cumulative maximum enforces monotonicity
        cum_adj_p = max(running_max, step_adj)
        running_max = cum_adj_p

        is_raw_sig = raw_p < 0.05
        is_holm_sig = cum_adj_p < 0.05

        if is_holm_sig:
            status = "STATISTICALLY_SIGNIFICANT"
        elif is_raw_sig:
            status = "DIRECTIONAL_EVIDENCE"
        else:
            status = "NON_SIGNIFICANT"

        holm_item = {
            "rank": rank,
            "comparison_id": comp["id"],
            "season": comp["season"],
            "discipline": comp["discipline"],
            "benchmark": comp["benchmark"],
            "metric": comp["metric"],
            "observed_effect": comp["observed_diff"],
            "ci_95": [comp["ci_95_low"], comp["ci_95_high"]],
            "raw_p_value": raw_p,
            "multiplier": multiplier,
            "step_adjusted_p": float(step_adj),
            "holm_adjusted_p": float(cum_adj_p),
            "raw_significant_05": is_raw_sig,
            "holm_significant_05": is_holm_sig,
            "inference_classification": status
        }
        holm_results.append(holm_item)
        print(f"Rank {rank} (k={multiplier}): {comp['id']:<30} | Raw p={raw_p:.4f} | Holm p={cum_adj_p:.4f} | {status}")

    # Verify monotonicity
    adj_p_values = [item["holm_adjusted_p"] for item in holm_results]
    is_monotonic = all(adj_p_values[i] <= adj_p_values[i+1] for i in range(len(adj_p_values)-1))
    print(f"\nHolm-adjusted p-values strictly non-decreasing: {is_monotonic}")

    holm_summary = {
        "metadata": {
            "total_hypotheses_tested": K,
            "family_wise_error_rate_target": 0.05,
            "adjustment_procedure": "Holm-Bonferroni with cumulative maximum monotonicity enforcement",
            "monotonicity_verified": is_monotonic,
            "summary_counts": {
                "statistically_significant_post_holm": sum(1 for r in holm_results if r["holm_significant_05"]),
                "directional_evidence_post_holm": sum(1 for r in holm_results if r["inference_classification"] == "DIRECTIONAL_EVIDENCE"),
                "non_significant": sum(1 for r in holm_results if r["inference_classification"] == "NON_SIGNIFICANT")
            }
        },
        "ranked_comparisons": holm_results
    }

    holm_out_path = Path("research/phase5_13/holm_adjusted_results.json")
    with open(holm_out_path, "w") as f:
        json.dump(holm_summary, f, indent=2)
    print(f"Saved Holm-adjusted results to {holm_out_path}")

if __name__ == "__main__":
    run_bootstrap_and_holm()
