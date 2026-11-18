"""
Phase 5.12 - Task 5: Outcome Definition Quantitative Analysis
Examines the relationship between the production training objective (Boundary Rate)
and the prospective evaluation metric (Strike Rate).
Computes:
1. Correlation and R^2 between boundary rate and strike rate across players.
2. Percentage of pressure runs derived from boundaries.
3. Out-of-sample prospective evaluation of Top 10 cohorts on BOTH Boundary Rate and Strike Rate.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.abspath("."))

def analyze_outcomes():
    raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    matches = pd.read_csv("data/extracted/matches.csv")
    m_date_map = matches.set_index("match_id")["match_date"].to_dict()
    raw["match_date"] = raw["match_id"].map(m_date_map)
    raw["year"] = pd.to_datetime(raw["match_date"]).dt.year
    clean = raw[(raw["is_dli_valid"] == 1) & (raw["ext_is_legal_delivery"] == 1)].copy()

    clean["is_four"] = (clean["ext_is_four"] == 1).astype(int)
    clean["is_six"] = (clean["ext_is_six"] == 1).astype(int)
    clean["is_boundary"] = ((clean["is_four"] == 1) | (clean["is_six"] == 1)).astype(int)
    clean["is_press"] = clean["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])

    press_df = clean[clean["is_press"]].copy()

    # 1. Macro Pressure Delivery Run Breakdown
    total_press_runs = press_df["ext_batter_runs"].sum()
    four_runs = press_df["is_four"].sum() * 4
    six_runs = press_df["is_six"].sum() * 6
    bnd_runs = four_runs + six_runs
    running_runs = total_press_runs - bnd_runs
    bnd_run_pct = bnd_runs / total_press_runs * 100.0

    print("=== MACRO PRESSURE RUN BREAKDOWN ===")
    print(f"Total Pressure Runs: {total_press_runs}")
    print(f"Boundary Runs: {bnd_runs} ({bnd_run_pct:.2f}%) [4s: {four_runs}, 6s: {six_runs}]")
    print(f"Running Runs (1s, 2s, 3s): {running_runs} ({100 - bnd_run_pct:.2f}%)")

    # 2. Player-Level Correlation between Boundary Rate and Strike Rate
    player_stats = press_df.groupby("striker_id").agg(
        balls=("ext_is_legal_delivery", "count"),
        runs=("ext_batter_runs", "sum"),
        boundaries=("is_boundary", "sum")
    ).reset_index()
    player_stats = player_stats[player_stats["balls"] >= 50].copy()
    player_stats["sr"] = player_stats["runs"] / player_stats["balls"] * 100.0
    player_stats["bnd_pct"] = player_stats["boundaries"] / player_stats["balls"] * 100.0

    corr, p_val = stats.pearsonr(player_stats["bnd_pct"], player_stats["sr"])
    slope, intercept, r_val, p_val_reg, std_err = stats.linregress(player_stats["bnd_pct"], player_stats["sr"])
    r2 = r_val ** 2

    print("\n=== PLAYER-LEVEL CORRELATION (N >= 50 balls) ===")
    print(f"Player Sample Size: {len(player_stats)}")
    print(f"Pearson Correlation (r): {corr:.4f} (p = {p_val:.2e})")
    print(f"R-squared (R^2): {r2:.4f}")
    print(f"Regression: SR = {intercept:.2f} + {slope:.2f} * Bnd%")

    # 3. Prospective Cohort Evaluation on BOTH Boundary Rate AND Strike Rate
    with open("research/phase5_11/prospective_rankings.json", "r") as f:
        prospective = json.load(f)

    cohort_results = {}
    for win_key, test_yr in [("window_a", 2025), ("window_b", 2026)]:
        top10_bat_ids = set([r["player_id"] for r in prospective[win_key]["top10_batters"]])
        eligible_bat_ids = set(prospective[win_key]["all_eligible_batters"])
        nonsel_bat_ids = eligible_bat_ids - top10_bat_ids

        test_press = clean[(clean["year"] == test_yr) & (clean["is_press"])].copy()
        
        # Top 10
        top10_sub = test_press[test_press["striker_id"].isin(top10_bat_ids)]
        t10_b = len(top10_sub)
        t10_r = top10_sub["ext_batter_runs"].sum()
        t10_bnd = top10_sub["is_boundary"].sum()
        t10_sr = t10_r / t10_b * 100.0 if t10_b > 0 else 0.0
        t10_bnd_pct = t10_bnd / t10_b * 100.0 if t10_b > 0 else 0.0

        # League
        lg_b = len(test_press)
        lg_r = test_press["ext_batter_runs"].sum()
        lg_bnd = test_press["is_boundary"].sum()
        lg_sr = lg_r / lg_b * 100.0 if lg_b > 0 else 0.0
        lg_bnd_pct = lg_bnd / lg_b * 100.0 if lg_b > 0 else 0.0

        # Non-selected
        ns_sub = test_press[test_press["striker_id"].isin(nonsel_bat_ids)]
        ns_b = len(ns_sub)
        ns_r = ns_sub["ext_batter_runs"].sum()
        ns_bnd = ns_sub["is_boundary"].sum()
        ns_sr = ns_r / ns_b * 100.0 if ns_b > 0 else 0.0
        ns_bnd_pct = ns_bnd / ns_b * 100.0 if ns_b > 0 else 0.0

        cohort_results[win_key] = {
            "test_year": test_yr,
            "top10": {"balls": t10_b, "runs": int(t10_r), "boundaries": int(t10_bnd), "sr": float(t10_sr), "bnd_pct": float(t10_bnd_pct)},
            "league": {"balls": lg_b, "runs": int(lg_r), "boundaries": int(lg_bnd), "sr": float(lg_sr), "bnd_pct": float(lg_bnd_pct)},
            "nonsel": {"balls": ns_b, "runs": int(ns_r), "boundaries": int(ns_bnd), "sr": float(ns_sr), "bnd_pct": float(ns_bnd_pct)},
            "edge_vs_league": {
                "sr_edge": float(t10_sr - lg_sr),
                "bnd_pct_edge": float(t10_bnd_pct - lg_bnd_pct)
            },
            "edge_vs_nonsel": {
                "sr_edge": float(t10_sr - ns_sr),
                "bnd_pct_edge": float(t10_bnd_pct - ns_bnd_pct)
            }
        }

        print(f"\n=== PROSPECTIVE TEST YEAR {test_yr} DUAL-METRIC EVALUATION ===")
        print(f"Top 10:   SR = {t10_sr:.2f} | Bnd% = {t10_bnd_pct:.2f}%")
        print(f"League:   SR = {lg_sr:.2f} | Bnd% = {lg_bnd_pct:.2f}%")
        print(f"Non-Sel:  SR = {ns_sr:.2f} | Bnd% = {ns_bnd_pct:.2f}%")
        print(f"Edge vs League:  SR = {t10_sr - lg_sr:+.2f} | Bnd% = {t10_bnd_pct - lg_bnd_pct:+.2f}%")
        print(f"Edge vs Non-Sel: SR = {t10_sr - ns_sr:+.2f} | Bnd% = {t10_bnd_pct - ns_bnd_pct:+.2f}%")

    output_data = {
        "macro_pressure_runs": {
            "total_runs": int(total_press_runs),
            "boundary_runs": int(bnd_runs),
            "running_runs": int(running_runs),
            "boundary_run_percentage": float(bnd_run_pct)
        },
        "player_level_correlation": {
            "player_count": len(player_stats),
            "pearson_r": float(corr),
            "p_value": float(p_val),
            "r_squared": float(r2),
            "regression_slope": float(slope),
            "regression_intercept": float(intercept)
        },
        "prospective_evaluations": cohort_results
    }

    out_file = "research/phase5_12/outcome_definition_analysis.json"
    with open(out_file, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"\nSaved Task 5 quantitative data to {out_file}")
    return output_data

if __name__ == "__main__":
    analyze_outcomes()
