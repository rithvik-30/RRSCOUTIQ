"""
Display formatted top pressure performers
"""

import os
import sys
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.analyze_pressure_players import run_analysis

def main():
    bat_df, bowl_df = run_analysis()

    print("=== TOP 10 BATTERS BY CREDIBLE VALUE ADD (LB90) ===")
    for i, r in bat_df.sort_values("lb90", ascending=False).head(10).reset_index().iterrows():
        print(f"{i+1}. {r['name']} [ID {r['player_id']}] | Role: {r['role']} | Matches: {r['matches']} | Balls: {r['total_balls']} (Press: {r['pressure_balls']}, High: {r['high_pressure_balls']})")
        print(f"   SR: Norm {r['normal_sr']} -> Press {r['pressure_sr']} (Delta: {r['delta_sr']:+0.2f}, High: {r['high_pressure_sr']}) | Bnd%: Norm {r['normal_bnd_pct']}% -> Press {r['pressure_bnd_pct']}% (High: {r['high_pressure_bnd_pct']}%) | Dot%: {r['pressure_dot_pct']}% | Hazard: {r['pressure_hazard']}%")
        print(f"   EB Value Add: {r['eb_add_pressure']:+0.2f}% | se_latent: {r['se_latent']:.4f} | LB90: {r['lb90']:+0.2f}%\n")

    print("=== TOP 10 BOWLERS BY CREDIBLE ECONOMY SUPPRESSION (UB90) ===")
    for i, r in bowl_df.sort_values("ub90", ascending=True).head(10).reset_index().iterrows():
        print(f"{i+1}. {r['name']} [ID {r['player_id']}] | Role: {r['role']} | Matches: {r['matches']} | Balls: {r['total_balls']} (Press: {r['pressure_balls']}, High: {r['high_pressure_balls']})")
        print(f"   Econ: Norm {r['normal_econ']} -> Press {r['pressure_econ']} (Delta: {r['delta_econ']:+0.2f}, High: {r['high_pressure_econ']}) | Dot%: Norm {r['normal_dot_pct']}% -> Press {r['pressure_dot_pct']}% | Bnd Conceded%: {r['pressure_bnd_pct']}%")
        print(f"   Wkts: {r['pressure_wkts']} (SR: {r['pressure_sr']:.1f}) | EB Econ Delta: {r['eb_suppression_pressure']:+0.3f} RPO | se_latent: {r['se_latent']:.4f} | UB90: {r['ub90']:+0.3f} RPO\n")

if __name__ == "__main__":
    main()
