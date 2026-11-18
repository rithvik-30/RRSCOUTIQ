"""
Generate detailed tier breakdown for shortlisted players
"""

import os
import sys
import pandas as pd
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

def main():
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

    bat_pids = [6281, 1699, 2367, 5553, 6819]
    bowl_pids = [781, 2933, 3644, 4373, 4101]

    print("================================================================================")
    print("BATTERS DETAILED BREAKDOWN")
    print("================================================================================")
    for pid in bat_pids:
        sub = clean[clean["striker_id"] == pid]
        sub_oof = oof[(oof["domain"] == "Batter") & (oof["player_id"] == pid)]
        name = p_map.get(pid, "Unknown")
        role = role_map.get(pid, "Unknown")
        matches = sub["match_id"].nunique()
        total_b = len(sub)
        print(f"\n### {name} [ID: {pid}] — Role: {role}")
        print(f"- Matches: {matches} | Total Legal Balls: {total_b}")
        
        # Overall and Pressure vs Normal
        norm = sub[sub["pre_pressure_tier"] == "Tier 1: Low"]
        press = sub[sub["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
        high = sub[sub["pre_pressure_tier"].isin(["Tier 3: High", "Tier 4: Extreme"])]
        
        sr_norm = round(norm["ext_batter_runs"].sum() / max(1, len(norm)) * 100.0, 2)
        sr_press = round(press["ext_batter_runs"].sum() / max(1, len(press)) * 100.0, 2)
        sr_high = round(high["ext_batter_runs"].sum() / max(1, len(high)) * 100.0, 2)
        
        bnd_norm = round(norm["is_boundary"].sum() / max(1, len(norm)) * 100.0, 2)
        bnd_press = round(press["is_boundary"].sum() / max(1, len(press)) * 100.0, 2)
        bnd_high = round(high["is_boundary"].sum() / max(1, len(high)) * 100.0, 2)
        
        dot_norm = round(norm["is_dot_bat"].sum() / max(1, len(norm)) * 100.0, 2)
        dot_press = round(press["is_dot_bat"].sum() / max(1, len(press)) * 100.0, 2)
        
        print(f"- Normal (Tier 1): {len(norm)} balls | SR: {sr_norm} | Boundary%: {bnd_norm}% | Dot%: {dot_norm}%")
        print(f"- Pressure (Tiers 2-4): {len(press)} balls | SR: {sr_press} (Delta: {sr_press - sr_norm:+.2f}) | Boundary%: {bnd_press}% (Delta: {bnd_press - bnd_norm:+.2f}%) | Dot%: {dot_press}%")
        print(f"- High Pressure (Tiers 3-4): {len(high)} balls | SR: {sr_high} | Boundary%: {bnd_high}%")
        
        # Bayesian estimates
        eb_add = (sub_oof["pred_m5"] - sub_oof["pred_m4"]).mean() * 100.0
        se_lat = sub_oof["se_latent_m5"].mean()
        lb90 = eb_add - 1.645 * se_lat * 100.0
        print(f"- Empirical Bayes Posterior Value-Add: {eb_add:+.2f}% | se_latent: {se_lat:.4f} | 90% Lower Bound: {lb90:+.2f}%")
        
        # Tiers
        for t in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
            st = sub[sub["pre_pressure_tier"] == t]
            b = len(st)
            if b > 0:
                r = st["ext_batter_runs"].sum()
                sr = round((r / b) * 100.0, 2)
                bnd = st["is_boundary"].sum()
                bnd_pct = round((bnd / b) * 100.0, 2)
                dots = st["is_dot_bat"].sum()
                dot_pct = round((dots / b) * 100.0, 2)
                outs = st["is_dismissal"].sum()
                print(f"  * {t}: {b} balls, {r} runs, SR: {sr}, Bnd: {bnd_pct}%, Dot: {dot_pct}%, Outs: {outs}")

    print("\n================================================================================")
    print("BOWLERS DETAILED BREAKDOWN")
    print("================================================================================")
    for pid in bowl_pids:
        sub = clean[clean["bowler_id"] == pid]
        sub_oof = oof[(oof["domain"] == "Bowler") & (oof["player_id"] == pid)]
        name = p_map.get(pid, "Unknown")
        role = role_map.get(pid, "Unknown")
        matches = sub["match_id"].nunique()
        total_b = len(sub)
        print(f"\n### {name} [ID: {pid}] — Role: {role}")
        print(f"- Matches: {matches} | Total Legal Balls: {total_b} ({total_b // 6} overs, {total_b % 6} balls)")
        
        norm = sub[sub["pre_pressure_tier"] == "Tier 1: Low"]
        press = sub[sub["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
        high = sub[sub["pre_pressure_tier"].isin(["Tier 3: High", "Tier 4: Extreme"])]
        
        econ_norm = round(norm["ext_bowler_debit_runs"].sum() / max(1, len(norm)) * 6.0, 2)
        econ_press = round(press["ext_bowler_debit_runs"].sum() / max(1, len(press)) * 6.0, 2)
        econ_high = round(high["ext_bowler_debit_runs"].sum() / max(1, len(high)) * 6.0, 2)
        
        dot_norm = round(norm["is_dot_bowl"].sum() / max(1, len(norm)) * 100.0, 2)
        dot_press = round(press["is_dot_bowl"].sum() / max(1, len(press)) * 100.0, 2)
        
        bnd_norm = round(norm["is_boundary"].sum() / max(1, len(norm)) * 100.0, 2)
        bnd_press = round(press["is_boundary"].sum() / max(1, len(press)) * 100.0, 2)
        
        wkts_press = press["is_wicket"].sum()
        sr_press = round(len(press) / max(1, wkts_press), 2)
        
        print(f"- Normal (Tier 1): {len(norm)} balls | Econ: {econ_norm} RPO | Dot%: {dot_norm}% | Boundary Conceded%: {bnd_norm}%")
        print(f"- Pressure (Tiers 2-4): {len(press)} balls | Econ: {econ_press} RPO (Delta: {econ_press - econ_norm:+.2f}) | Dot%: {dot_press}% (Delta: {dot_press - dot_norm:+.2f}%) | Boundary Conceded%: {bnd_press}% | Wkts: {wkts_press} (SR: {sr_press})")
        print(f"- High Pressure (Tiers 3-4): {len(high)} balls | Econ: {econ_high} RPO")
        
        # Bayesian estimates
        eb_supp = (sub_oof["pred_m5"] - sub_oof["pred_m4"]).mean()
        se_lat = sub_oof["se_latent_m5"].mean()
        ub90 = eb_supp + 1.645 * se_lat
        print(f"- Empirical Bayes Posterior Economy Suppression: {eb_supp:+.3f} RPO | se_latent: {se_lat:.4f} RPO | 90% Upper Bound: {ub90:+.3f} RPO")
        
        # Tiers
        for t in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
            st = sub[sub["pre_pressure_tier"] == t]
            b = len(st)
            if b > 0:
                r = st["ext_bowler_debit_runs"].sum()
                econ = round((r / b) * 6.0, 2)
                bnd = st["is_boundary"].sum()
                bnd_pct = round((bnd / b) * 100.0, 2)
                dots = st["is_dot_bowl"].sum()
                dot_pct = round((dots / b) * 100.0, 2)
                wkts = st["is_wicket"].sum()
                print(f"  * {t}: {b} balls, {r} runs, Econ: {econ} RPO, Bnd: {bnd_pct}%, Dot: {dot_pct}%, Wkts: {wkts}")

if __name__ == "__main__":
    main()
