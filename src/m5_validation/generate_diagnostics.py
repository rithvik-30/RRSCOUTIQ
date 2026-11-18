"""
Script to generate M5_4_1_DISTRIBUTION_DIAGNOSTICS.csv with complete distribution parameters.
"""

from pathlib import Path
import numpy as np
import pandas as pd


def generate_diagnostics():
    project_root = Path(__file__).resolve().parents[2]
    match_state_path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    out_path = project_root / "audit_reports" / "M5_4_1_DISTRIBUTION_DIAGNOSTICS.csv"

    print("Loading match_state_full.csv...")
    df = pd.read_csv(match_state_path, low_memory=False)

    delivery_metrics = [
        "ext_batter_runs", "runs", "ext_extra_runs", "ext_wide_runs", "ext_noball_runs",
        "ext_bye_runs", "ext_legbye_runs", "ext_penalty_runs", "ext_bowler_debit_runs",
        "ext_delivery_total_runs", "pre_score", "pre_wickets_lost", "pre_wickets_in_hand",
        "pre_legal_balls_bowled", "pre_legal_balls_rem", "pre_crr", "pre_target",
        "pre_runs_required", "pre_rrr", "pre_dli"
    ]

    results = []
    for m in delivery_metrics:
        s = df[m].dropna()
        total = len(df[m])
        missing = int(df[m].isna().sum())
        mean_val = float(s.mean()) if len(s) > 0 else np.nan
        std_val = float(s.std()) if len(s) > 0 else np.nan
        min_val = float(s.min()) if len(s) > 0 else np.nan
        q25 = float(s.quantile(0.25)) if len(s) > 0 else np.nan
        median_val = float(s.median()) if len(s) > 0 else np.nan
        q75 = float(s.quantile(0.75)) if len(s) > 0 else np.nan
        q90 = float(s.quantile(0.90)) if len(s) > 0 else np.nan
        q95 = float(s.quantile(0.95)) if len(s) > 0 else np.nan
        q99 = float(s.quantile(0.99)) if len(s) > 0 else np.nan
        max_val = float(s.max()) if len(s) > 0 else np.nan

        if len(s) > 0:
            top_idx = s.nlargest(3).index
            extreme_str = "; ".join([f"Match {df.loc[i, 'match_id']}: {df.loc[i, m]}" for i in top_idx])
        else:
            extreme_str = "None"

        results.append({
            "scope": "DELIVERY_LEVEL",
            "variable": m,
            "total_count": total,
            "valid_count": len(s),
            "missing_count": missing,
            "missing_pct": round((missing / total) * 100, 4),
            "min": min_val,
            "q25": q25,
            "median": median_val,
            "q75": q75,
            "q90": q90,
            "q95": q95,
            "q99": q99,
            "max": max_val,
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "extreme_observations": extreme_str,
        })

    # Innings level metrics
    inn_runs = df.groupby(["match_id", "innings"])["ext_delivery_total_runs"].sum()
    inn_wkts = df.groupby(["match_id", "innings"])["ext_is_wicket"].sum()
    inn_balls = df.groupby(["match_id", "innings"])["ext_is_legal_delivery"].sum()

    for s, name in [(inn_runs, "innings_total_runs"), (inn_wkts, "innings_total_wickets"), (inn_balls, "innings_legal_balls")]:
        total = len(s)
        top_idx = s.nlargest(3).index
        extreme_str = "; ".join([f"Match {mid} Inn {inn}: {s.loc[(mid, inn)]}" for mid, inn in top_idx])
        results.append({
            "scope": "INNINGS_LEVEL",
            "variable": name,
            "total_count": total,
            "valid_count": total,
            "missing_count": 0,
            "missing_pct": 0.0,
            "min": float(s.min()),
            "q25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "q75": float(s.quantile(0.75)),
            "q90": float(s.quantile(0.90)),
            "q95": float(s.quantile(0.95)),
            "q99": float(s.quantile(0.99)),
            "max": float(s.max()),
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "extreme_observations": extreme_str,
        })

    # Match level metrics
    m_runs = df.groupby("match_id")["ext_delivery_total_runs"].sum()
    m_wkts = df.groupby("match_id")["ext_is_wicket"].sum()
    m_balls = df.groupby("match_id")["ext_is_legal_delivery"].sum()

    for s, name in [(m_runs, "match_total_runs"), (m_wkts, "match_total_wickets"), (m_balls, "match_total_legal_balls")]:
        total = len(s)
        top_idx = s.nlargest(3).index
        extreme_str = "; ".join([f"Match {mid}: {s.loc[mid]}" for mid in top_idx])
        results.append({
            "scope": "MATCH_LEVEL",
            "variable": name,
            "total_count": total,
            "valid_count": total,
            "missing_count": 0,
            "missing_pct": 0.0,
            "min": float(s.min()),
            "q25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "q75": float(s.quantile(0.75)),
            "q90": float(s.quantile(0.90)),
            "q95": float(s.quantile(0.95)),
            "q99": float(s.quantile(0.99)),
            "max": float(s.max()),
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "extreme_observations": extreme_str,
        })

    # Player level workloads
    bf = df.groupby("striker_id")["ext_batter_balls_faced"].sum()
    bw = df[df["ext_is_legal_delivery"] == True].groupby("bowler_id").size()

    all_player_matches = pd.concat([
        df[["match_id", "striker_id"]].rename(columns={"striker_id": "pid"}),
        df[["match_id", "non_striker_id"]].rename(columns={"non_striker_id": "pid"}),
        df[["match_id", "bowler_id"]].rename(columns={"bowler_id": "pid"})
    ]).drop_duplicates().groupby("pid").size()

    for s, name in [(bf, "batter_career_balls_faced"), (bw, "bowler_career_legal_balls"), (all_player_matches, "player_tournament_matches")]:
        total = len(s)
        top_idx = s.nlargest(3).index
        extreme_str = "; ".join([f"Player {pid}: {s.loc[pid]}" for pid in top_idx])
        results.append({
            "scope": "PLAYER_LEVEL",
            "variable": name,
            "total_count": total,
            "valid_count": total,
            "missing_count": 0,
            "missing_pct": 0.0,
            "min": float(s.min()),
            "q25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "q75": float(s.quantile(0.75)),
            "q90": float(s.quantile(0.90)),
            "q95": float(s.quantile(0.95)),
            "q99": float(s.quantile(0.99)),
            "max": float(s.max()),
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "extreme_observations": extreme_str,
        })

    diag_df = pd.DataFrame(results)
    diag_df.to_csv(out_path, index=False)
    print(f"Generated {out_path} successfully. Total rows: {len(diag_df)}")


if __name__ == "__main__":
    generate_diagnostics()
