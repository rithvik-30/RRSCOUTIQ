"""
Phase 5.10: Genuine Leakage-Free Walk-Forward Simulation
Implements a strict, leakage-free prospective evaluation:
1. Training Window 1: 2022-2024.
   - Filter eligible players (career balls >= 500, press balls >= 100) using ONLY 2022-2024 deliveries.
   - Rank batters by conservative lower bound, bowlers by upper bound based ONLY on 2022-2024 data.
   - Evaluate this prospectively selected Top 10 cohort in unseen 2025.
2. Training Window 2: 2022-2025.
   - Filter and rank based ONLY on 2022-2025 data.
   - Evaluate this cohort in unseen 2026.
3. Compare against the contaminated Phase 5.6 reported numbers.
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

def prospective_ranking_batters(train_clean, min_career=500, min_press=100, z=1.645):
    # Career stats in training
    c_balls = train_clean.groupby("striker_id")["ext_is_legal_delivery"].count()
    c_runs = train_clean.groupby("striker_id")["ext_batter_runs"].sum()
    c_sr = (c_runs / c_balls * 100)
    
    # Pressure stats in training
    press_train = train_clean[train_clean["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
    p_balls = press_train.groupby("striker_id")["ext_is_legal_delivery"].count()
    p_runs = press_train.groupby("striker_id")["ext_batter_runs"].sum()
    p_sr = (p_runs / p_balls * 100)
    
    df = pd.DataFrame({
        "career_balls": c_balls,
        "career_sr": c_sr,
        "press_balls": p_balls,
        "press_sr": p_sr
    }).dropna().reset_index()
    
    # Eligibility
    df = df[(df["career_balls"] >= min_career) & (df["press_balls"] >= min_press)].copy()
    
    # Raw delta (pressure SR - career SR)
    df["raw_delta"] = (df["press_sr"] - df["career_sr"]) / 100.0
    
    # Standard error approximation: sqrt(p*(1-p)/n) or empirical variance
    # Using binomial/rate SE: se = (press_sr/100) / sqrt(press_balls)
    df["se"] = (df["press_sr"] / 100.0) / np.sqrt(df["press_balls"])
    
    # Empirical Bayes shrinkage: grand mean mu0 and tau2
    mu0 = df["raw_delta"].mean()
    var_raw = df["raw_delta"].var()
    mean_se2 = (df["se"]**2).mean()
    tau2 = max(0.0001, var_raw - mean_se2)
    
    df["B"] = tau2 / (tau2 + df["se"]**2)
    df["delta_eb"] = df["B"] * df["raw_delta"] + (1 - df["B"]) * mu0
    df["lb"] = df["delta_eb"] - z * df["se"]
    
    df["name"] = df["striker_id"].map(p_map)
    return df.sort_values("lb", ascending=False).reset_index(drop=True)

def prospective_ranking_bowlers(train_clean, min_career=500, min_press_balls=100, z=1.645):
    # Career stats in training
    c_balls = train_clean.groupby("bowler_id")["ext_is_legal_delivery"].count()
    c_debits = train_clean.groupby("bowler_id")["ext_bowler_debit_runs"].sum()
    c_econ = (c_debits / c_balls * 6)
    
    # Pressure stats in training
    press_train = train_clean[train_clean["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]
    p_balls = press_train.groupby("bowler_id")["ext_is_legal_delivery"].count()
    p_debits = press_train.groupby("bowler_id")["ext_bowler_debit_runs"].sum()
    p_econ = (p_debits / p_balls * 6)
    
    df = pd.DataFrame({
        "career_balls": c_balls,
        "career_econ": c_econ,
        "press_balls": p_balls,
        "press_econ": p_econ
    }).dropna().reset_index()
    
    # Eligibility
    df = df[(df["career_balls"] >= min_career) & (df["press_balls"] >= min_press_balls)].copy()
    
    # Raw delta (pressure econ - career econ) in RPO
    df["raw_delta"] = df["press_econ"] - df["career_econ"]
    
    df["se"] = (df["press_econ"]) / np.sqrt(df["press_balls"])
    
    mu0 = df["raw_delta"].mean()
    var_raw = df["raw_delta"].var()
    mean_se2 = (df["se"]**2).mean()
    tau2 = max(0.01, var_raw - mean_se2)
    
    df["B"] = tau2 / (tau2 + df["se"]**2)
    df["delta_eb"] = df["B"] * df["raw_delta"] + (1 - df["B"]) * mu0
    df["ub"] = df["delta_eb"] + z * df["se"]
    
    df["name"] = df["bowler_id"].map(p_map)
    return df.sort_values("ub", ascending=True).reset_index(drop=True)

print("=" * 80)
print("HORIZON 1: TRAIN 2022-2024 -> PROSPECTIVE TEST 2025")
print("=" * 80)

train_2024 = clean[clean["year"].isin([2022, 2023, 2024])]
test_2025 = clean[clean["year"] == 2025]
press_test_2025 = test_2025[test_2025["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]

bat_ranked_2024 = prospective_ranking_batters(train_2024)
top10_bat_2024 = bat_ranked_2024.head(10)
print("Genuinely Selected Top 10 Batters (Trained ONLY on 2022-2024):")
for idx, r in top10_bat_2024.iterrows():
    print(f"  #{idx+1}: {r['name']} (ID: {r['striker_id']}) | PressBalls 2022-24: {r['press_balls']} | LB: {r['lb']*100:+.2f}%")

# Measure performance of THIS cohort in 2025:
prospective_bat_ids_1 = top10_bat_2024["striker_id"].tolist()
b_sub_2025 = press_test_2025[press_test_2025["striker_id"].isin(prospective_bat_ids_1)]
p_runs_25 = b_sub_2025["ext_batter_runs"].sum()
p_balls_25 = len(b_sub_2025)
p_sr_25 = p_runs_25 / p_balls_25 * 100
league_sr_25 = press_test_2025["ext_batter_runs"].sum() / len(press_test_2025) * 100

print(f"\nGENUINE Out-of-Sample Performance in 2025:")
print(f"  Prospective Top 10 Batters: {p_balls_25} balls, {p_runs_25} runs, SR = {p_sr_25:.2f}")
print(f"  League Average Pressure SR: {league_sr_25:.2f}")
print(f"  Genuine Out-of-Sample SR Edge: {p_sr_25 - league_sr_25:+.2f} runs/100 balls")
print(f"  (Contaminated Reported Edge in Phase 5.6 was: +31.7 runs/100 balls)")

bowl_ranked_2024 = prospective_ranking_bowlers(train_2024)
top10_bowl_2024 = bowl_ranked_2024.head(10)
print("\nGenuinely Selected Top 10 Bowlers (Trained ONLY on 2022-2024):")
for idx, r in top10_bowl_2024.iterrows():
    print(f"  #{idx+1}: {r['name']} (ID: {r['bowler_id']}) | PressBalls 2022-24: {r['press_balls']} | UB: {r['ub']:+.3f}")

prospective_bowl_ids_1 = top10_bowl_2024["bowler_id"].tolist()
bw_sub_2025 = press_test_2025[press_test_2025["bowler_id"].isin(prospective_bowl_ids_1)]
p_debits_25 = bw_sub_2025["ext_bowler_debit_runs"].sum()
p_bw_balls_25 = len(bw_sub_2025)
p_econ_25 = p_debits_25 / p_bw_balls_25 * 6
league_econ_25 = press_test_2025["ext_bowler_debit_runs"].sum() / len(press_test_2025) * 6

print(f"\nGENUINE Out-of-Sample Performance in 2025:")
print(f"  Prospective Top 10 Bowlers: {p_bw_balls_25} balls, {p_debits_25} runs, Econ = {p_econ_25:.2f}")
print(f"  League Average Pressure Econ: {league_econ_25:.2f}")
print(f"  Genuine Out-of-Sample Economy Edge: {p_econ_25 - league_econ_25:+.2f} RPO")
print(f"  (Contaminated Reported Edge in Phase 5.6 was: -1.73 RPO)")

print("\n" + "=" * 80)
print("HORIZON 2: TRAIN 2022-2025 -> PROSPECTIVE TEST 2026")
print("=" * 80)

train_2025 = clean[clean["year"].isin([2022, 2023, 2024, 2025])]
test_2026 = clean[clean["year"] == 2026]
press_test_2026 = test_2026[test_2026["pre_pressure_tier"].isin(["Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"])]

bat_ranked_2025 = prospective_ranking_batters(train_2025)
top10_bat_2025 = bat_ranked_2025.head(10)
print("Genuinely Selected Top 10 Batters (Trained ONLY on 2022-2025):")
for idx, r in top10_bat_2025.iterrows():
    print(f"  #{idx+1}: {r['name']} (ID: {r['striker_id']}) | PressBalls 2022-25: {r['press_balls']} | LB: {r['lb']*100:+.2f}%")

prospective_bat_ids_2 = top10_bat_2025["striker_id"].tolist()
b_sub_2026 = press_test_2026[press_test_2026["striker_id"].isin(prospective_bat_ids_2)]
p_runs_26 = b_sub_2026["ext_batter_runs"].sum()
p_balls_26 = len(b_sub_2026)
p_sr_26 = p_runs_26 / p_balls_26 * 100
league_sr_26 = press_test_2026["ext_batter_runs"].sum() / len(press_test_2026) * 100

print(f"\nGENUINE Out-of-Sample Performance in 2026:")
print(f"  Prospective Top 10 Batters: {p_balls_26} balls, {p_runs_26} runs, SR = {p_sr_26:.2f}")
print(f"  League Average Pressure SR: {league_sr_26:.2f}")
print(f"  Genuine Out-of-Sample SR Edge: {p_sr_26 - league_sr_26:+.2f} runs/100 balls")
print(f"  (Contaminated Reported Edge in Phase 5.6 was: +31.2 runs/100 balls)")

bowl_ranked_2025 = prospective_ranking_bowlers(train_2025)
top10_bowl_2025 = bowl_ranked_2025.head(10)
print("\nGenuinely Selected Top 10 Bowlers (Trained ONLY on 2022-2025):")
for idx, r in top10_bowl_2025.iterrows():
    print(f"  #{idx+1}: {r['name']} (ID: {r['bowler_id']}) | PressBalls 2022-25: {r['press_balls']} | UB: {r['ub']:+.3f}")

prospective_bowl_ids_2 = top10_bowl_2025["bowler_id"].tolist()
bw_sub_2026 = press_test_2026[press_test_2026["bowler_id"].isin(prospective_bowl_ids_2)]
p_debits_26 = bw_sub_2026["ext_bowler_debit_runs"].sum()
p_bw_balls_26 = len(bw_sub_2026)
p_econ_26 = p_debits_26 / p_bw_balls_26 * 6
league_econ_26 = press_test_2026["ext_bowler_debit_runs"].sum() / len(press_test_2026) * 6

print(f"\nGENUINE Out-of-Sample Performance in 2026:")
print(f"  Prospective Top 10 Bowlers: {p_bw_balls_26} balls, {p_debits_26} runs, Econ = {p_econ_26:.2f}")
print(f"  League Average Pressure Econ: {league_econ_26:.2f}")
print(f"  Genuine Out-of-Sample Economy Edge: {p_econ_26 - league_econ_26:+.2f} RPO")
print(f"  (Contaminated Reported Edge in Phase 5.6 was: -1.20 RPO)")
