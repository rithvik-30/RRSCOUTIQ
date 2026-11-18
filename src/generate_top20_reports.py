"""
Generate Top 10 Batters, Top 10 Bowlers, and Validation Report
"""

import os
import sys
import pandas as pd
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

AUDIT_DIR = os.path.join(REPO_ROOT, "audit_reports", "M5_5B_4_3_8")
os.makedirs(AUDIT_DIR, exist_ok=True)

def generate_reports():
    print("Loading data...")
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

    # ------------------------------------------------------------------------
    # 1. Top 10 Batters
    # ------------------------------------------------------------------------
    bat_pids = [6281, 1699, 50284, 4847, 2367, 5553, 6819, 4117, 6396, 1318]
    
    bat_oof = oof[oof["domain"] == "Batter"].copy()
    bat_oof["is_press"] = bat_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    press_b = bat_oof[bat_oof["is_press"]].copy()
    press_b["val_add"] = press_b["pred_m5"] - press_b["pred_m4"]

    agg_b = press_b.groupby("player_id").agg(
        n_press_balls=("exposure_balls", "count"),
        mean_val_add=("val_add", "mean"),
        se_latent=("se_latent_m5", "mean")
    )
    agg_b["lb90"] = agg_b["mean_val_add"] - 1.645 * agg_b["se_latent"]

    bat_data = []
    for rank, pid in enumerate(bat_pids, 1):
        sub = clean[clean["striker_id"] == pid]
        name = p_map.get(pid, "Unknown")
        role = role_map.get(pid, "Unknown")
        matches = sub["match_id"].nunique()
        total_b = len(sub)

        norm = sub[sub["pre_pressure_tier"] == "Tier 1: Low"]
        press = sub[sub["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
        high = sub[sub["pre_pressure_tier"].isin(["Tier 3: High", "Tier 4: Extreme"])]
        t2 = sub[sub["pre_pressure_tier"] == "Tier 2: Medium"]
        t3 = sub[sub["pre_pressure_tier"] == "Tier 3: High"]
        t4 = sub[sub["pre_pressure_tier"] == "Tier 4: Extreme"]

        def b_stat(s):
            b = len(s)
            if b == 0:
                return {"balls": 0, "runs": 0, "sr": 0.0, "bnd": 0, "bnd_pct": 0.0, "dots": 0, "dot_pct": 0.0, "outs": 0, "hazard": 0.0}
            r = s["ext_batter_runs"].sum()
            bnd = s["is_boundary"].sum()
            dots = s["is_dot_bat"].sum()
            outs = s["is_dismissal"].sum()
            return {
                "balls": b, "runs": r, "sr": round(r/b*100.0, 2),
                "bnd": bnd, "bnd_pct": round(bnd/b*100.0, 2),
                "dots": dots, "dot_pct": round(dots/b*100.0, 2),
                "outs": outs, "hazard": round(outs/b*100.0, 2)
            }

        st_all = b_stat(sub)
        st_norm = b_stat(norm)
        st_press = b_stat(press)
        st_high = b_stat(high)
        st_t2 = b_stat(t2)
        st_t3 = b_stat(t3)
        st_t4 = b_stat(t4)

        b_eb = agg_b.loc[pid]

        bat_data.append({
            "rank": rank,
            "player_id": pid,
            "name": name,
            "role": role,
            "matches": matches,
            "total_balls": total_b,
            "normal": st_norm,
            "pressure": st_press,
            "high": st_high,
            "t2": st_t2,
            "t3": st_t3,
            "t4": st_t4,
            "delta_sr": round(st_press["sr"] - st_norm["sr"], 2) if st_norm["balls"] > 0 else 0.0,
            "delta_bnd": round(st_press["bnd_pct"] - st_norm["bnd_pct"], 2) if st_norm["balls"] > 0 else 0.0,
            "delta_dot": round(st_press["dot_pct"] - st_norm["dot_pct"], 2) if st_norm["balls"] > 0 else 0.0,
            "val_add": round(b_eb["mean_val_add"] * 100.0, 2),
            "se_latent": round(b_eb["se_latent"], 4),
            "lb90": round(b_eb["lb90"] * 100.0, 2)
        })

    # ------------------------------------------------------------------------
    # 2. Top 10 Bowlers
    # ------------------------------------------------------------------------
    bowl_pids = [781, 2933, 4373, 3644, 2876, 4900, 152, 4101, 2984, 5979]

    bowl_oof = oof[oof["domain"] == "Bowler"].copy()
    bowl_oof["is_press"] = bowl_oof["tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])
    press_bw = bowl_oof[bowl_oof["is_press"]].copy()
    press_bw["delta"] = press_bw["pred_m5"] - press_bw["pred_m4"]

    agg_bw = press_bw.groupby("player_id").agg(
        n_press_spells=("exposure_balls", "count"),
        mean_delta=("delta", "mean"),
        se_latent=("se_latent_m5", "mean")
    )
    agg_bw["ub90"] = agg_bw["mean_delta"] + 1.645 * agg_bw["se_latent"]

    bowl_data = []
    for rank, pid in enumerate(bowl_pids, 1):
        sub = clean[clean["bowler_id"] == pid]
        name = p_map.get(pid, "Unknown")
        role = role_map.get(pid, "Unknown")
        matches = sub["match_id"].nunique()
        total_b = len(sub)

        norm = sub[sub["pre_pressure_tier"] == "Tier 1: Low"]
        press = sub[sub["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
        high = sub[sub["pre_pressure_tier"].isin(["Tier 3: High", "Tier 4: Extreme"])]
        t2 = sub[sub["pre_pressure_tier"] == "Tier 2: Medium"]
        t3 = sub[sub["pre_pressure_tier"] == "Tier 3: High"]
        t4 = sub[sub["pre_pressure_tier"] == "Tier 4: Extreme"]

        def bw_stat(s):
            b = len(s)
            if b == 0:
                return {"balls": 0, "runs": 0, "econ": 0.0, "bnd": 0, "bnd_pct": 0.0, "dots": 0, "dot_pct": 0.0, "wkts": 0, "sr": 0.0}
            r = s["ext_bowler_debit_runs"].sum()
            bnd = s["is_boundary"].sum()
            dots = s["is_dot_bowl"].sum()
            w = s["is_wicket"].sum()
            return {
                "balls": b, "runs": r, "econ": round(r/b*6.0, 2),
                "bnd": bnd, "bnd_pct": round(bnd/b*100.0, 2),
                "dots": dots, "dot_pct": round(dots/b*100.0, 2),
                "wkts": w, "sr": round(b/max(1, w), 2)
            }

        st_all = bw_stat(sub)
        st_norm = bw_stat(norm)
        st_press = bw_stat(press)
        st_high = bw_stat(high)
        st_t2 = bw_stat(t2)
        st_t3 = bw_stat(t3)
        st_t4 = bw_stat(t4)

        bw_eb = agg_bw.loc[pid]

        bowl_data.append({
            "rank": rank,
            "player_id": pid,
            "name": name,
            "role": role,
            "matches": matches,
            "total_balls": total_b,
            "normal": st_norm,
            "pressure": st_press,
            "high": st_high,
            "t2": st_t2,
            "t3": st_t3,
            "t4": st_t4,
            "delta_econ": round(st_press["econ"] - st_norm["econ"], 2) if st_norm["balls"] > 0 else 0.0,
            "delta_dot": round(st_press["dot_pct"] - st_norm["dot_pct"], 2) if st_norm["balls"] > 0 else 0.0,
            "delta_bnd": round(st_press["bnd_pct"] - st_norm["bnd_pct"], 2) if st_norm["balls"] > 0 else 0.0,
            "delta_rpo": round(bw_eb["mean_delta"], 3),
            "se_latent": round(bw_eb["se_latent"], 4),
            "ub90": round(bw_eb["ub90"], 3)
        })

    print("Data processed for 10 batters and 10 bowlers.")
    return bat_data, bowl_data

if __name__ == "__main__":
    generate_reports()
