"""
RR ScoutIQ — Comprehensive Pressure Player Identification Engine
Evaluates Batting and Bowling pressure performance across DLI tiers,
computing empirical stats, Bayesian posteriors, pressure deltas, and uncertainty.
"""

import os
import sys
import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

def run_analysis():
    print("Loading canonical dataset and OOF predictions...")
    data_path = os.path.join(REPO_ROOT, "data", "processed", "m5_3", "match_state_full.csv")
    oof_path = os.path.join(REPO_ROOT, "audit_reports", "M5_5B_4_3_8", "M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv")
    crosswalk_path = os.path.join(REPO_ROOT, "data", "enriched", "player_crosswalk_m5_5.csv")

    df = pd.read_csv(data_path, low_memory=False)
    clean = df[(df["is_dli_valid"] == 1) & (df["ext_is_legal_delivery"] == 1)].copy()

    crosswalk = pd.read_csv(crosswalk_path)
    p_map = crosswalk.set_index("player_id")["canonical_name"].to_dict()
    role_map = crosswalk.set_index("player_id")["role_discipline"].to_dict()

    oof = pd.read_csv(oof_path)
    bat_oof = oof[oof["domain"] == "Batter"].copy()
    bowl_oof = oof[oof["domain"] == "Bowler"].copy()

    # Feature engineering on delivery data
    clean["is_boundary"] = ((clean["ext_is_four"] == 1) | (clean["ext_is_six"] == 1)).astype(int)
    clean["is_six"] = (clean["ext_is_six"] == 1).astype(int)
    clean["is_four"] = (clean["ext_is_four"] == 1).astype(int)
    clean["is_dot_bat"] = (clean["ext_batter_runs"] == 0).astype(int)
    clean["is_dot_bowl"] = (clean["ext_bowler_debit_runs"] == 0).astype(int)
    clean["is_wicket"] = (clean["ext_is_bowler_wicket"] == True).astype(int)
    clean["is_dismissal"] = (clean["dismissed_player_id"].notna() & (clean["dismissed_player_id"] == clean["striker_id"])).astype(int)

    # Pressure flags
    clean["is_pressure"] = clean["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]).astype(int)
    clean["is_high_pressure"] = clean["pre_pressure_tier"].isin(["Tier 3: High", "Tier 4: Extreme"]).astype(int)
    clean["is_normal"] = (clean["pre_pressure_tier"] == "Tier 1: Low").astype(int)

    # ------------------------------------------------------------------------
    # 1. BATTER EVALUATION
    # ------------------------------------------------------------------------
    print("\n--- Computing Batter Pressure Profiles ---")
    bat_oof["is_pressure"] = bat_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    bat_oof["eb_val_add"] = bat_oof["pred_m5"] - bat_oof["pred_m4"]
    bat_oof["emp_val_add"] = bat_oof["actual"] - bat_oof["pred_m4"]

    # Bayesian posterior metrics per batter
    bat_bayesian = bat_oof.groupby("player_id").agg(
        total_balls=("exposure_balls", "sum"),
        pressure_balls=("is_pressure", "sum"),
        eb_add_pressure=("eb_val_add", lambda x: float(x[bat_oof.loc[x.index, "is_pressure"]].mean())),
        emp_add_pressure=("emp_val_add", lambda x: float(x[bat_oof.loc[x.index, "is_pressure"]].mean())),
        pred_m4_mean=("pred_m4", lambda x: float(x[bat_oof.loc[x.index, "is_pressure"]].mean())),
        pred_m5_mean=("pred_m5", lambda x: float(x[bat_oof.loc[x.index, "is_pressure"]].mean())),
        se_latent=("se_latent_m5", "mean")
    )

    # Detailed empirical metrics per batter from clean deliveries
    def get_bat_stats(sub):
        b = len(sub)
        if b == 0:
            return {"balls": 0, "runs": 0, "sr": 0.0, "bnd_pct": 0.0, "dot_pct": 0.0, "outs": 0, "hazard": 0.0}
        r = sub["ext_batter_runs"].sum()
        bnd = sub["is_boundary"].sum()
        dots = sub["is_dot_bat"].sum()
        outs = sub["is_dismissal"].sum()
        return {
            "balls": b,
            "runs": r,
            "sr": round((r / b) * 100.0, 2),
            "bnd_pct": round((bnd / b) * 100.0, 2),
            "dot_pct": round((dots / b) * 100.0, 2),
            "outs": outs,
            "hazard": round((outs / b) * 100.0, 2)
        }

    bat_records = []
    for pid in bat_bayesian.index:
        sub_all = clean[clean["striker_id"] == pid]
        if len(sub_all) < 300:
            continue
            
        sub_norm = sub_all[sub_all["is_normal"] == 1]
        sub_press = sub_all[sub_all["is_pressure"] == 1]
        sub_t2 = sub_all[sub_all["pre_pressure_tier"] == "Tier 2: Medium"]
        sub_t3 = sub_all[sub_all["pre_pressure_tier"] == "Tier 3: High"]
        sub_t4 = sub_all[sub_all["pre_pressure_tier"] == "Tier 4: Extreme"]
        sub_high = sub_all[sub_all["is_high_pressure"] == 1]

        if len(sub_press) < 100:
            continue

        st_all = get_bat_stats(sub_all)
        st_norm = get_bat_stats(sub_norm)
        st_press = get_bat_stats(sub_press)
        st_t2 = get_bat_stats(sub_t2)
        st_t3 = get_bat_stats(sub_t3)
        st_t4 = get_bat_stats(sub_t4)
        st_high = get_bat_stats(sub_high)

        b_row = bat_bayesian.loc[pid]

        # Lower bound of 90% credible interval on EB value add
        lb90 = b_row["eb_add_pressure"] - 1.645 * b_row["se_latent"]

        # DLI elasticity (linear regression slope of runs per ball or boundary on pre_dli)
        dli_slope = np.polyfit(sub_all["pre_dli"].values, sub_all["is_boundary"].values, 1)[0] if len(sub_all) > 50 else 0.0

        bat_records.append({
            "player_id": pid,
            "name": p_map.get(pid, "Unknown"),
            "role": role_map.get(pid, "Unknown"),
            "matches": sub_all["match_id"].nunique(),
            "total_balls": len(sub_all),
            "normal_balls": len(sub_norm),
            "pressure_balls": len(sub_press),
            "high_pressure_balls": len(sub_high),
            "t1_balls": len(sub_norm),
            "t2_balls": len(sub_t2),
            "t3_balls": len(sub_t3),
            "t4_balls": len(sub_t4),
            # Normal stats
            "normal_sr": st_norm["sr"],
            "normal_bnd_pct": st_norm["bnd_pct"],
            "normal_dot_pct": st_norm["dot_pct"],
            # Pressure stats
            "pressure_runs": st_press["runs"],
            "pressure_sr": st_press["sr"],
            "pressure_bnd_pct": st_press["bnd_pct"],
            "pressure_dot_pct": st_press["dot_pct"],
            "pressure_hazard": st_press["hazard"],
            # High pressure stats (Tiers 3+4)
            "high_pressure_sr": st_high["sr"],
            "high_pressure_bnd_pct": st_high["bnd_pct"],
            # Tier breakdowns
            "t2_sr": st_t2["sr"],
            "t2_bnd_pct": st_t2["bnd_pct"],
            "t3_sr": st_t3["sr"],
            "t3_bnd_pct": st_t3["bnd_pct"],
            "t4_sr": st_t4["sr"],
            "t4_bnd_pct": st_t4["bnd_pct"],
            # Deltas (Pressure - Normal)
            "delta_sr": round(st_press["sr"] - st_norm["sr"], 2) if len(sub_norm) > 0 else 0.0,
            "delta_bnd_pct": round(st_press["bnd_pct"] - st_norm["bnd_pct"], 2) if len(sub_norm) > 0 else 0.0,
            # Bayesian Posterior Value Add
            "eb_add_pressure": round(b_row["eb_add_pressure"] * 100.0, 2),  # in %
            "emp_add_pressure": round(b_row["emp_add_pressure"] * 100.0, 2),
            "se_latent": round(b_row["se_latent"], 4),
            "lb90": round(lb90 * 100.0, 2),
            "dli_slope": round(dli_slope * 100.0, 3)
        })

    bat_df = pd.DataFrame(bat_records)
    print(f"Qualified Batters evaluated: {len(bat_df)}")
    print("\nTop 10 Batters by Credible Lower Bound (LB90):")
    print(bat_df.sort_values("lb90", ascending=False)[["player_id", "name", "role", "matches", "pressure_balls", "normal_sr", "pressure_sr", "high_pressure_sr", "pressure_bnd_pct", "eb_add_pressure", "lb90"]].head(10))

    # ------------------------------------------------------------------------
    # 2. BOWLER EVALUATION
    # ------------------------------------------------------------------------
    print("\n--- Computing Bowler Pressure Profiles ---")
    bowl_oof["is_pressure"] = bowl_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    bowl_oof["eb_suppression"] = bowl_oof["pred_m5"] - bowl_oof["pred_m4"]
    bowl_oof["emp_suppression"] = bowl_oof["actual"] - bowl_oof["pred_m4"]

    bowl_bayesian = bowl_oof.groupby("player_id").agg(
        total_spells=("exposure_balls", "count"),
        pressure_spells=("is_pressure", "sum"),
        eb_suppression_pressure=("eb_suppression", lambda x: float(x[bowl_oof.loc[x.index, "is_pressure"]].mean())),
        emp_suppression_pressure=("emp_suppression", lambda x: float(x[bowl_oof.loc[x.index, "is_pressure"]].mean())),
        pred_m4_mean=("pred_m4", lambda x: float(x[bowl_oof.loc[x.index, "is_pressure"]].mean())),
        pred_m5_mean=("pred_m5", lambda x: float(x[bowl_oof.loc[x.index, "is_pressure"]].mean())),
        se_latent=("se_latent_m5", "mean")
    )

    def get_bowl_stats(sub):
        b = len(sub)
        if b == 0:
            return {"balls": 0, "runs": 0, "econ": 0.0, "dot_pct": 0.0, "bnd_pct": 0.0, "wkts": 0, "sr": 0.0}
        r = sub["ext_bowler_debit_runs"].sum()
        w = sub["is_wicket"].sum()
        dots = sub["is_dot_bowl"].sum()
        bnd = sub["is_boundary"].sum()
        return {
            "balls": b,
            "runs": r,
            "econ": round((r / b) * 6.0, 2),
            "dot_pct": round((dots / b) * 100.0, 2),
            "bnd_pct": round((bnd / b) * 100.0, 2),
            "wkts": w,
            "sr": round(b / max(1, w), 2)
        }

    bowl_records = []
    for pid in bowl_bayesian.index:
        sub_all = clean[clean["bowler_id"] == pid]
        if len(sub_all) < 300:
            continue

        sub_norm = sub_all[sub_all["is_normal"] == 1]
        sub_press = sub_all[sub_all["is_pressure"] == 1]
        sub_t2 = sub_all[sub_all["pre_pressure_tier"] == "Tier 2: Medium"]
        sub_t3 = sub_all[sub_all["pre_pressure_tier"] == "Tier 3: High"]
        sub_t4 = sub_all[sub_all["pre_pressure_tier"] == "Tier 4: Extreme"]
        sub_high = sub_all[sub_all["is_high_pressure"] == 1]

        if len(sub_press) < 100:
            continue

        st_all = get_bowl_stats(sub_all)
        st_norm = get_bowl_stats(sub_norm)
        st_press = get_bowl_stats(sub_press)
        st_t2 = get_bowl_stats(sub_t2)
        st_t3 = get_bowl_stats(sub_t3)
        st_t4 = get_bowl_stats(sub_t4)
        st_high = get_bowl_stats(sub_high)

        b_row = bowl_bayesian.loc[pid]

        # Upper bound of 90% credible interval on EB economy delta (lower is better, so lowest UB90 is most suppressive)
        ub90 = b_row["eb_suppression_pressure"] + 1.645 * b_row["se_latent"]

        bowl_records.append({
            "player_id": pid,
            "name": p_map.get(pid, "Unknown"),
            "role": role_map.get(pid, "Unknown"),
            "matches": sub_all["match_id"].nunique(),
            "total_balls": len(sub_all),
            "normal_balls": len(sub_norm),
            "pressure_balls": len(sub_press),
            "high_pressure_balls": len(sub_high),
            "t1_balls": len(sub_norm),
            "t2_balls": len(sub_t2),
            "t3_balls": len(sub_t3),
            "t4_balls": len(sub_t4),
            # Normal stats
            "normal_econ": st_norm["econ"],
            "normal_dot_pct": st_norm["dot_pct"],
            "normal_bnd_pct": st_norm["bnd_pct"],
            # Pressure stats
            "pressure_runs": st_press["runs"],
            "pressure_econ": st_press["econ"],
            "pressure_dot_pct": st_press["dot_pct"],
            "pressure_bnd_pct": st_press["bnd_pct"],
            "pressure_wkts": st_press["wkts"],
            "pressure_sr": st_press["sr"],
            # High pressure stats (Tiers 3+4)
            "high_pressure_econ": st_high["econ"],
            "high_pressure_dot_pct": st_high["dot_pct"],
            # Tier breakdowns
            "t2_econ": st_t2["econ"],
            "t3_econ": st_t3["econ"],
            "t4_econ": st_t4["econ"],
            # Deltas (Pressure - Normal)
            "delta_econ": round(st_press["econ"] - st_norm["econ"], 2) if len(sub_norm) > 0 else 0.0,
            "delta_dot_pct": round(st_press["dot_pct"] - st_norm["dot_pct"], 2) if len(sub_norm) > 0 else 0.0,
            # Bayesian Posterior Economy Suppression
            "eb_suppression_pressure": round(b_row["eb_suppression_pressure"], 3),
            "emp_suppression_pressure": round(b_row["emp_suppression_pressure"], 3),
            "se_latent": round(b_row["se_latent"], 4),
            "ub90": round(ub90, 3)
        })

    bowl_df = pd.DataFrame(bowl_records)
    print(f"Qualified Bowlers evaluated: {len(bowl_df)}")
    print("\nTop 10 Bowlers by Credible Upper Bound (UB90 - lower is better):")
    print(bowl_df.sort_values("ub90", ascending=True)[["player_id", "name", "role", "matches", "pressure_balls", "normal_econ", "pressure_econ", "high_pressure_econ", "pressure_dot_pct", "eb_suppression_pressure", "ub90"]].head(10))

    return bat_df, bowl_df

if __name__ == "__main__":
    run_analysis()
