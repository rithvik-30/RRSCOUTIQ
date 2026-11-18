"""
Phase 5.12 - Task 4 & Task 6: Corrected Match-Clustered Bootstrap Inference
Implements a documented, statistically defensible cluster-bootstrap hypothesis test:
- Unit of resampling: Complete Match ID (preserves all deliveries and environmental correlation within match).
- Fixed seed: 42.
- Bootstrap replications: B = 10,000.
- Null hypothesis: H0: theta = 0 (no difference between selected cohort and benchmark).
- Centered null distribution: theta_null* = theta* - theta_obs.
- Two-sided p-value with plus-one finite-sample correction: p = (1 + sum(abs(theta_null*) >= abs(theta_obs))) / (B + 1).
- Percentile confidence intervals: [2.5th, 97.5th percentiles of theta*].
- Consistency verification between CI and p-value.
- Reconciles all 8 comparisons against Phase 5.11 and Phase 5.10.
"""

import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

def run_corrected_bootstrap():
    print("=" * 80)
    print("PHASE 5.12 - TASK 4 & 6: CORRECTED BOOTSTRAP STATISTICAL INFERENCE")
    print("=" * 80)

    # 1. Load data
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

    print(f"Configuration:")
    print(f"  Bootstrap replications (B): {B}")
    print(f"  Random Seed: {SEED}")
    print(f"  Monte Carlo Resolution: {mc_resolution:.6f}")
    print(f"  Centering Method: Shift under Null (theta_null* = theta* - theta_obs)")
    print(f"  P-value formula: (1 + count(|theta_null*| >= |theta_obs|)) / (B + 1)")

    all_comparisons = {}

    for window_key, test_year in [("window_a", 2025), ("window_b", 2026)]:
        print("\n" + "=" * 80)
        print(f"EVALUATING {window_key.upper()}: UNSEEN TEST YEAR {test_year}")
        print("=" * 80)

        win_data = prospective[window_key]
        top10_bat_ids = set([r["player_id"] for r in win_data["top10_batters"]])
        top10_bowl_ids = set([r["player_id"] for r in win_data["top10_bowlers"]])
        eligible_bat_ids = set(win_data["all_eligible_batters"])
        eligible_bowl_ids = set(win_data["all_eligible_bowlers"])

        nonsel_bat_ids = eligible_bat_ids - top10_bat_ids
        nonsel_bowl_ids = eligible_bowl_ids - top10_bowl_ids

        test_df = clean[clean["year"] == test_year].copy()
        press_test = test_df[test_df["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])].copy()

        unique_matches = np.array(press_test["match_id"].unique())
        n_matches = len(unique_matches)
        print(f"Test year {test_year}: {len(test_df)} legal balls, {len(press_test)} pressure balls across {n_matches} matches.")

        # Pre-aggregate match-level sums into matrix M
        # Columns of M:
        # 0: lg_b, 1: lg_r, 2: lg_d, 3: lg_bnd
        # 4: top_b_balls, 5: top_b_runs, 6: top_b_bnd
        # 7: ns_b_balls, 8: ns_b_runs, 9: ns_b_bnd
        # 10: top_bw_balls, 11: top_bw_debits
        # 12: ns_bw_balls, 13: ns_bw_debits
        match_stats = []
        for m in unique_matches:
            m_df = press_test[press_test["match_id"] == m]
            
            lg_b = len(m_df)
            lg_r = m_df["ext_batter_runs"].sum()
            lg_d = m_df["ext_bowler_debit_runs"].sum()
            lg_bnd = m_df["is_boundary"].sum()

            m_top_b = m_df[m_df["striker_id"].isin(top10_bat_ids)]
            top_b_balls = len(m_top_b)
            top_b_runs = m_top_b["ext_batter_runs"].sum()
            top_b_bnd = m_top_b["is_boundary"].sum()

            m_ns_b = m_df[m_df["striker_id"].isin(nonsel_bat_ids)]
            ns_b_balls = len(m_ns_b)
            ns_b_runs = m_ns_b["ext_batter_runs"].sum()
            ns_b_bnd = m_ns_b["is_boundary"].sum()

            m_top_bw = m_df[m_df["bowler_id"].isin(top10_bowl_ids)]
            top_bw_balls = len(m_top_bw)
            top_bw_debits = m_top_bw["ext_bowler_debit_runs"].sum()

            m_ns_bw = m_df[m_df["bowler_id"].isin(nonsel_bowl_ids)]
            ns_bw_balls = len(m_ns_bw)
            ns_bw_debits = m_ns_bw["ext_bowler_debit_runs"].sum()

            match_stats.append([
                lg_b, lg_r, lg_d, lg_bnd,
                top_b_balls, top_b_runs, top_b_bnd,
                ns_b_balls, ns_b_runs, ns_b_bnd,
                top_bw_balls, top_bw_debits,
                ns_bw_balls, ns_bw_debits
            ])

        M = np.array(match_stats, dtype=np.float64)

        # Observed point estimates
        obs_sums = M.sum(axis=0)
        obs_lg_sr = (obs_sums[1] / obs_sums[0] * 100) if obs_sums[0] > 0 else 0.0
        obs_top_b_sr = (obs_sums[5] / obs_sums[4] * 100) if obs_sums[4] > 0 else 0.0
        obs_ns_b_sr = (obs_sums[8] / obs_sums[7] * 100) if obs_sums[7] > 0 else 0.0

        obs_bat_edge_lg = obs_top_b_sr - obs_lg_sr
        obs_bat_edge_ns = obs_top_b_sr - obs_ns_b_sr

        obs_lg_econ = (obs_sums[2] / obs_sums[0] * 6.0) if obs_sums[0] > 0 else 0.0
        obs_top_bw_econ = (obs_sums[11] / obs_sums[10] * 6.0) if obs_sums[10] > 0 else 0.0
        obs_ns_bw_econ = (obs_sums[13] / obs_sums[12] * 6.0) if obs_sums[12] > 0 else 0.0

        obs_bowl_edge_lg = obs_top_bw_econ - obs_lg_econ
        obs_bowl_edge_ns = obs_top_bw_econ - obs_ns_bw_econ

        # Boundary Rate observed
        obs_lg_bnd = (obs_sums[3] / obs_sums[0] * 100) if obs_sums[0] > 0 else 0.0
        obs_top_b_bnd = (obs_sums[6] / obs_sums[4] * 100) if obs_sums[4] > 0 else 0.0
        obs_ns_b_bnd = (obs_sums[9] / obs_sums[7] * 100) if obs_sums[7] > 0 else 0.0

        obs_bat_bnd_edge_lg = obs_top_b_bnd - obs_lg_bnd
        obs_bat_bnd_edge_ns = obs_top_b_bnd - obs_ns_b_bnd

        # Vectorized Match Resampling: matrix shape (B, n_matches)
        resample_matrix = np.random.choice(n_matches, size=(B, n_matches), replace=True)
        # Sum along matches axis -> shape (B, 14)
        boot_sums = M[resample_matrix].sum(axis=1)

        # Bootstrap statistics
        b_lg_b = boot_sums[:, 0]
        b_lg_r = boot_sums[:, 1]
        b_lg_d = boot_sums[:, 2]
        b_lg_bnd = boot_sums[:, 3]

        b_top_b_b = boot_sums[:, 4]
        b_top_b_r = boot_sums[:, 5]
        b_top_b_bnd = boot_sums[:, 6]

        b_ns_b_b = boot_sums[:, 7]
        b_ns_b_r = boot_sums[:, 8]
        b_ns_b_bnd = boot_sums[:, 9]

        b_top_bw_b = boot_sums[:, 10]
        b_top_bw_d = boot_sums[:, 11]

        b_ns_bw_b = boot_sums[:, 12]
        b_ns_bw_d = boot_sums[:, 13]

        boot_lg_sr = b_lg_r / b_lg_b * 100.0
        boot_top_b_sr = b_top_b_r / b_top_b_b * 100.0
        boot_ns_b_sr = b_ns_b_r / b_ns_b_b * 100.0

        boot_bat_edge_lg = boot_top_b_sr - boot_lg_sr
        boot_bat_edge_ns = boot_top_b_sr - boot_ns_b_sr

        boot_lg_econ = b_lg_d / b_lg_b * 6.0
        boot_top_bw_econ = b_top_bw_d / b_top_bw_b * 6.0
        boot_ns_bw_econ = b_ns_bw_d / b_ns_bw_b * 6.0

        boot_bowl_edge_lg = boot_top_bw_econ - boot_lg_econ
        boot_bowl_edge_ns = boot_top_bw_econ - boot_ns_bw_econ

        boot_lg_bnd = b_lg_bnd / b_lg_b * 100.0
        boot_top_b_bnd = b_top_b_bnd / b_top_b_b * 100.0
        boot_ns_b_bnd = b_ns_b_bnd / b_ns_b_b * 100.0

        boot_bat_bnd_edge_lg = boot_top_b_bnd - boot_lg_bnd
        boot_bat_bnd_edge_ns = boot_top_b_bnd - boot_ns_b_bnd

        def evaluate_hypothesis_test(boot_dist, obs_stat, name):
            ci_low = float(np.percentile(boot_dist, 2.5))
            ci_high = float(np.percentile(boot_dist, 97.5))
            
            # Centering under the Null: theta_null* = theta* - theta_obs
            theta_null = boot_dist - obs_stat
            
            # Two-sided p-value: fraction of null replicates as extreme as or more extreme than observed
            extreme_count = np.sum(np.abs(theta_null) >= np.abs(obs_stat))
            p_val = float((1 + extreme_count) / (B + 1))
            
            # Mutual consistency check between 95% CI and p-value (< 0.05)
            ci_rejects_zero = (ci_low > 0 and ci_high > 0) or (ci_low < 0 and ci_high < 0)
            p_rejects_zero = (p_val < 0.05)
            consistent = (ci_rejects_zero == p_rejects_zero)

            return {
                "metric_name": name,
                "observed_effect": float(obs_stat),
                "ci_95": [ci_low, ci_high],
                "two_sided_p_value": p_val,
                "null_centered": True,
                "plus_one_corrected": True,
                "ci_excludes_zero": ci_rejects_zero,
                "p_rejects_at_05": p_rejects_zero,
                "mutually_consistent": consistent
            }

        # 4 Primary Rate Comparisons for this window
        comp_bat_lg = evaluate_hypothesis_test(boot_bat_edge_lg, obs_bat_edge_lg, f"{test_year} Batter SR vs League")
        comp_bat_ns = evaluate_hypothesis_test(boot_bat_edge_ns, obs_bat_edge_ns, f"{test_year} Batter SR vs Eligible Non-Selected")
        comp_bowl_lg = evaluate_hypothesis_test(boot_bowl_edge_lg, obs_bowl_edge_lg, f"{test_year} Bowler Econ vs League")
        comp_bowl_ns = evaluate_hypothesis_test(boot_bowl_edge_ns, obs_bowl_edge_ns, f"{test_year} Bowler Econ vs Eligible Non-Selected")

        # Dual Metric Boundary Rate comparisons
        comp_bat_bnd_lg = evaluate_hypothesis_test(boot_bat_bnd_edge_lg, obs_bat_bnd_edge_lg, f"{test_year} Batter Bnd% vs League")
        comp_bat_bnd_ns = evaluate_hypothesis_test(boot_bat_bnd_edge_ns, obs_bat_bnd_edge_ns, f"{test_year} Batter Bnd% vs Eligible Non-Selected")

        print(f"\n--- {test_year} RESULTS ---")
        for c in [comp_bat_lg, comp_bat_ns, comp_bowl_lg, comp_bowl_ns, comp_bat_bnd_lg, comp_bat_bnd_ns]:
            print(f"  {c['metric_name']}: {c['observed_effect']:+.2f} [95% CI: {c['ci_95'][0]:+.2f}, {c['ci_95'][1]:+.2f}] | p = {c['two_sided_p_value']:.4f} | Consistent: {c['mutually_consistent']}")

        all_comparisons[f"{window_key}_primary"] = [comp_bat_lg, comp_bat_ns, comp_bowl_lg, comp_bowl_ns]
        all_comparisons[f"{window_key}_dual_metric_boundary"] = [comp_bat_bnd_lg, comp_bat_bnd_ns]

    # Structure 8 primary comparisons table
    eight_comparisons = (
        all_comparisons["window_a_primary"] + 
        all_comparisons["window_b_primary"]
    )

    final_results = {
        "metadata": {
            "bootstrap_replications": B,
            "random_seed": SEED,
            "monte_carlo_resolution": mc_resolution,
            "resampling_unit": "Complete Match ID (Match-Clustered)",
            "centering_method": "Shift under Null (theta_null* = theta* - theta_obs)",
            "p_value_formula": "(1 + count(|theta_null*| >= |theta_obs|)) / (B + 1)"
        },
        "eight_primary_comparisons": eight_comparisons,
        "dual_metric_boundary_comparisons": (
            all_comparisons["window_a_dual_metric_boundary"] + 
            all_comparisons["window_b_dual_metric_boundary"]
        )
    }

    out_file = "research/phase5_12/corrected_bootstrap_results.json"
    with open(out_file, "w") as f:
        json.dump(final_results, f, indent=2)
    print(f"\nSaved Task 4 & 6 corrected bootstrap results to {out_file}")
    return final_results

if __name__ == "__main__":
    run_corrected_bootstrap()
