"""
Phase 5.10: Independent Walk-Forward Validation & Leakage Audit
Investigates the reported +31.5 SR and -1.50 Economy advantages.
Checks:
1. How Phase 5.6 actually calculated the figures.
2. Whether the evaluated cohort was selected on training data alone or full dataset (Look-Ahead Bias).
3. Executes a genuine, leakage-free walk-forward selection:
   - Window 1: Train on 2022-2024 -> Select Top 10 based ONLY on 2022-2024 -> Test on 2025.
   - Window 2: Train on 2022-2025 -> Select Top 10 based ONLY on 2022-2025 -> Test on 2026.
4. Compares the genuine walk-forward out-of-sample performance against the reported figures.
"""

import pandas as pd
import numpy as np

raw = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
clean = raw[(raw["is_dli_valid"] == 1) & (raw["ext_is_legal_delivery"] == 1)].copy()

matches = pd.read_csv("data/extracted/matches.csv")
m_date_map = matches.set_index("match_id")["match_date"].to_dict()
clean["match_date"] = clean["match_id"].map(m_date_map)
clean["year"] = pd.to_datetime(clean["match_date"]).dt.year

cw = pd.read_csv("data/enriched/player_crosswalk_m5_5.csv")
p_map = cw.set_index("player_id")["canonical_name"].to_dict()

# Official Top 10 from Phase 5
OFFICIAL_BATTERS = [6281, 1699, 50284, 4847, 2367, 5553, 6819, 4117, 6396, 1318]
OFFICIAL_BOWLERS = [781, 2933, 4373, 3644, 2876, 4900, 152, 4101, 2984, 5979]

print("=" * 80)
print("1. AUDITING PHASE 5.6 WALK-FORWARD METHODOLOGY")
print("=" * 80)

# In 2025:
clean_2025 = clean[clean["year"] == 2025]
press_2025 = clean_2025[clean_2025["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]

# League averages in 2025 pressure
league_2025_runs = press_2025["ext_batter_runs"].sum()
league_2025_balls = len(press_2025)
league_2025_sr = league_2025_runs / league_2025_balls * 100
league_2025_debits = press_2025["ext_bowler_debit_runs"].sum()
league_2025_econ = league_2025_debits / league_2025_balls * 6

print(f"2025 League Pressure Context: Balls = {league_2025_balls}, SR = {league_2025_sr:.2f}, Econ = {league_2025_econ:.2f}")

# Official Batters in 2025 pressure
b_2025 = press_2025[press_2025["striker_id"].isin(OFFICIAL_BATTERS)]
b_2025_runs = b_2025["ext_batter_runs"].sum()
b_2025_balls = len(b_2025)
b_2025_sr = b_2025_runs / b_2025_balls * 100
print(f"Official Top 10 Batters in 2025: Balls = {b_2025_balls}, Runs = {b_2025_runs}, Pooled SR = {b_2025_sr:.2f}")
print(f"Reported Phase 5.6 Batters SR = 173.8 vs Recomputed = {b_2025_sr:.2f} | Edge = {b_2025_sr - league_2025_sr:+.2f}")

# Official Bowlers in 2025 pressure
bw_2025 = press_2025[press_2025["bowler_id"].isin(OFFICIAL_BOWLERS)]
bw_2025_debits = bw_2025["ext_bowler_debit_runs"].sum()
bw_2025_balls = len(bw_2025)
bw_2025_econ = bw_2025_debits / bw_2025_balls * 6
print(f"Official Top 10 Bowlers in 2025: Balls = {bw_2025_balls}, Debits = {bw_2025_debits}, Pooled Econ = {bw_2025_econ:.2f}")
print(f"Reported Phase 5.6 Bowlers Econ = 6.91 vs Recomputed = {bw_2025_econ:.2f} | Edge = {bw_2025_econ - league_2025_econ:+.2f}")

# In 2026:
clean_2026 = clean[clean["year"] == 2026]
press_2026 = clean_2026[clean_2026["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]

league_2026_runs = press_2026["ext_batter_runs"].sum()
league_2026_balls = len(press_2026)
league_2026_sr = league_2026_runs / league_2026_balls * 100
league_2026_debits = press_2026["ext_bowler_debit_runs"].sum()
league_2026_econ = league_2026_debits / league_2026_balls * 6

print(f"\n2026 League Pressure Context: Balls = {league_2026_balls}, SR = {league_2026_sr:.2f}, Econ = {league_2026_econ:.2f}")

b_2026 = press_2026[press_2026["striker_id"].isin(OFFICIAL_BATTERS)]
b_2026_runs = b_2026["ext_batter_runs"].sum()
b_2026_balls = len(b_2026)
b_2026_sr = b_2026_runs / b_2026_balls * 100
print(f"Official Top 10 Batters in 2026: Balls = {b_2026_balls}, Runs = {b_2026_runs}, Pooled SR = {b_2026_sr:.2f}")
print(f"Reported Phase 5.6 Batters SR = 185.4 vs Recomputed = {b_2026_sr:.2f} | Edge = {b_2026_sr - league_2026_sr:+.2f}")

bw_2026 = press_2026[press_2026["bowler_id"].isin(OFFICIAL_BOWLERS)]
bw_2026_debits = bw_2026["ext_bowler_debit_runs"].sum()
bw_2026_balls = len(bw_2026)
bw_2026_econ = bw_2026_debits / bw_2026_balls * 6
print(f"Official Top 10 Bowlers in 2026: Balls = {bw_2026_balls}, Debits = {bw_2026_debits}, Pooled Econ = {bw_2026_econ:.2f}")
print(f"Reported Phase 5.6 Bowlers Econ = 7.98 vs Recomputed = {bw_2026_econ:.2f} | Edge = {bw_2026_econ - league_2026_econ:+.2f}")

# Check exposure of Vaibhav Sooryavanshi prior to 2025
v_pre2025 = clean[(clean["striker_id"] == 50284) & (clean["year"] < 2025)]
print(f"\nVaibhav Sooryavanshi legal balls faced pre-2025: {len(v_pre2025)}")
v_pre2026 = clean[(clean["striker_id"] == 50284) & (clean["year"] < 2026)]
print(f"Vaibhav Sooryavanshi legal balls faced pre-2026: {len(v_pre2026)}")

# Check exposure of Abrar Ahmed prior to 2025
a_pre2025 = clean[(clean["bowler_id"] == 5979) & (clean["year"] < 2025)]
print(f"Abrar Ahmed legal balls bowled pre-2025: {len(a_pre2025)}")
a_pre2026 = clean[(clean["bowler_id"] == 5979) & (clean["year"] < 2026)]
print(f"Abrar Ahmed legal balls bowled pre-2026: {len(a_pre2026)}")
