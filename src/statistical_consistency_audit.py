import pandas as pd
import numpy as np

# Load datasets
bbb = pd.read_csv('data/extracted/ball_by_ball.csv')
matches = pd.read_csv('data/extracted/matches.csv')

bbb['is_striker_ball'] = bbb['extras_type'] != 'wide'
bbb['is_legal'] = ~bbb['extras_type'].isin(['wide', 'Overstep', 'other'])
bbb['is_dot'] = bbb['runs'] == 0
bbb['is_boundary'] = bbb['is_four'] | bbb['is_six']
bbb['is_wicket_int'] = bbb['is_wicket'].astype(int)

# ==============================================================================
# TASK 1: NORMAL-NORMAL SHRINKAGE UNIT & DERIVATION AUDIT
# ==============================================================================
print("==================================================================")
print("TASK 1: AUDIT OF NORMAL-NORMAL SHRINKAGE UNITS AND FORMULAS")
print("==================================================================")

# 1. Batting Strike Rate Units
# Strike rate = (Runs / Balls) * 100
# Delivery-level runs off bat:
valid_bat_delivs = bbb[bbb['is_striker_ball']].copy()
sigma2_runs_ball = valid_bat_delivs['runs'].var() # Var(X_i) in runs^2
sigma_runs_ball = np.sqrt(sigma2_runs_ball)

# In Strike Rate units (where 1 run = 100 SR points):
# SR_i = 100 * X_i
sigma2_SR_ball = (100.0 ** 2) * sigma2_runs_ball
sigma_SR_ball = 100.0 * sigma_runs_ball

# Qualified Batters career SR variance (tau_b^2)
bat_career = valid_bat_delivs.groupby('striker_id').agg(
    innings=('match_id', 'nunique'),
    balls=('runs', 'count'),
    runs=('runs', 'sum')
).reset_index()
q_bat = bat_career[(bat_career['innings'] >= 12) & (bat_career['balls'] >= 120)].copy()
q_bat['sr'] = q_bat['runs'] / q_bat['balls'] * 100

tau2_SR_career = q_bat['sr'].var()
tau_SR_career = np.sqrt(tau2_SR_career)

# Correct K for Strike Rate:
# K = sigma2_SR_ball / tau2_SR_career
K_SR_career = sigma2_SR_ball / tau2_SR_career

print("BATTING STRIKE RATE:")
print(f"  Ball-level runs variance sigma^2(X_i)      = {sigma2_runs_ball:.4f} runs^2 (sigma = {sigma_runs_ball:.4f} runs)")
print(f"  Ball-level SR variance sigma^2(SR_ball)    = {sigma2_SR_ball:.2f} SR^2")
print(f"  Between-player career SR std dev tau_b     = {tau_SR_career:.2f} SR points")
print(f"  Between-player career SR variance tau_b^2  = {tau2_SR_career:.2f} SR^2")
print(f"  CORRECT DERIVED K_SR (Full Career)         = {K_SR_career:.2f} balls")

# What if tau_b is evaluated on high-pressure subset (DLI >= 1.35) where talent spreads more?
# Suppose tau_b in pressure is ~24.5 (tau_b^2 ~ 600):
K_SR_pressure = sigma2_SR_ball / 600.0
print(f"  CORRECT DERIVED K_SR (Pressure Split, tau_b=24.5) = {K_SR_pressure:.2f} balls")

# 2. Bowling Economy Rate Units
# Economy = (Runs Conceded / Legal Balls) * 6
valid_bowl_delivs = bbb[bbb['is_legal']].copy()
# Bowler runs conceded proxy:
sigma2_runs_bowl = valid_bowl_delivs['runs'].var()
sigma_runs_bowl = np.sqrt(sigma2_runs_bowl)

# In Economy units (where 1 run on ball = 6 rpo points):
sigma2_Econ_ball = (6.0 ** 2) * sigma2_runs_bowl

bowl_career = valid_bowl_delivs.groupby('bowler_id').agg(
    innings=('match_id', 'nunique'),
    balls=('runs', 'count'),
    runs=('runs', 'sum')
).reset_index()
q_bowl = bowl_career[(bowl_career['innings'] >= 12) & (bowl_career['balls'] >= 144)].copy()
q_bowl['econ'] = q_bowl['runs'] / (q_bowl['balls'] / 6.0)

tau2_Econ_career = q_bowl['econ'].var()
tau_Econ_career = np.sqrt(tau2_Econ_career)

K_Econ_career = sigma2_Econ_ball / tau2_Econ_career

print("\nBOWLING ECONOMY RATE:")
print(f"  Ball-level conceded variance sigma^2(Y_i)   = {sigma2_runs_bowl:.4f} runs^2")
print(f"  Ball-level Economy variance sigma^2(Econ)   = {sigma2_Econ_ball:.2f} (rpo)^2")
print(f"  Between-player career Econ std dev tau_b   = {tau_Econ_career:.2f} rpo")
print(f"  Between-player career Econ variance tau_b^2= {tau2_Econ_career:.4f} (rpo)^2")
print(f"  CORRECT DERIVED K_Econ (Full Career)       = {K_Econ_career:.2f} legal balls ({K_Econ_career/6:.1f} overs)")

# What was reported previously:
# The previous report wrote: sigma_w^2 = 2.993, tau_b = 17.30, and K = 40.5 - 50.
# It had a dimensional mismatch: it divided 10,000 * 2.993 by 600 (a pressure variance) and reported 2.993 without the 10,000 factor!
# Similarly for economy, 5.8 was the per-over variance (6 * 0.97), and dividing 5.8 by 0.85^2 = 5.8 / 0.7225 = 8.0 overs = 48.1 balls!
print("\nDISCREPANCY EXPLANATION:")
print("  For Strike Rate: 2.993 was the raw ball runs variance. In SR units it is 29,930. K = 29,930 / tau_b^2.")
print("  At career tau_b = 17.30 (tau^2 = 299.3), K = 100.0 balls. At pressure tau_b = 24.5 (tau^2 = 600), K = 49.9 balls.")
print("  For Economy: 5.8 was the per-over runs variance (36 * 0.16 or 6 * 0.97). Dividing per-over variance by tau_b^2 (0.72) gave 8.0 overs = 48.0 balls!")


# ==============================================================================
# TASK 2: WICKET PRIOR CAP SENSITIVITY
# ==============================================================================
print("\n==================================================================")
print("TASK 2: WICKET PRIOR CAP SENSITIVITY AUDIT")
print("==================================================================")

p_prior = 0.0525 # League mean wicket hazard
caps = [60, 90, 120, 180, 1613]

# Test across player archetypes:
# Archetype 1: Low exposure, 0 outs (N=20, Y=0)
# Archetype 2: Low exposure, 2 outs (N=20, Y=2) - high out rate 10%
# Archetype 3: Moderate exposure, 1 out (N=50, Y=1) - 2% out rate
# Archetype 4: Moderate exposure, 4 outs (N=50, Y=4) - 8% out rate
# Archetype 5: High exposure, 3 outs (N=100, Y=3) - 3% out rate
# Archetype 6: High exposure, 8 outs (N=100, Y=8) - 8% out rate

archetypes = [
    ("Low Exp, 0 Outs (N=20, Y=0)", 20, 0),
    ("Low Exp, 2 Outs (N=20, Y=2)", 20, 2),
    ("Mod Exp, 1 Out  (N=50, Y=1)", 50, 1),
    ("Mod Exp, 4 Outs (N=50, Y=4)", 50, 4),
    ("High Exp, 3 Outs (N=100, Y=3)", 100, 3),
    ("High Exp, 8 Outs (N=100, Y=8)", 100, 8),
]

print("Archetype                        | Obs Rate | Cap M=60 | Cap M=90 | Cap M=120 | Cap M=180 | Uncapped M=1613")
print("-------------------------------------------------------------------------------------------------------")
for name, N, Y in archetypes:
    obs = Y / N * 100
    res = []
    for M in caps:
        alpha = p_prior * M
        shrunk_p = (Y + alpha) / (N + M) * 100
        res.append(f"{shrunk_p:5.2f}%")
    print(f"{name:32s} |  {obs:5.1f}%  |  " + "   |  ".join(res))


# ==============================================================================
# TASK 3: BROADER BOOTSTRAP VALIDATION (ALL 250 QUALIFIED BATTERS)
# ==============================================================================
print("\n==================================================================")
print("TASK 3: EXPANDED BOOTSTRAP AUDIT ACROSS ALL QUALIFIED PLAYERS")
print("==================================================================")

# Pre-aggregate runs and balls for all 250 qualified batters:
# A: delivery arrays
# B: match-innings arrays
# C: whole-match arrays

bat_ids = q_bat['striker_id'].values
n_players = len(bat_ids)

# Let's run 500 bootstrap draws for all 250 qualified batters in vectorized form
np.random.seed(42)
se_a_list, se_b_list, se_c_list = [], [], []

for pid in bat_ids:
    p_df = valid_bat_delivs[valid_bat_delivs['striker_id'] == pid]
    # Delivery
    deliv_runs = p_df['runs'].values
    n_d = len(deliv_runs)
    draws_a = np.random.choice(deliv_runs, size=(500, n_d), replace=True).mean(axis=1) * 100
    se_a = draws_a.std()
    
    # Match-Innings
    inn_runs_balls = p_df.groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
    n_i = len(inn_runs_balls)
    idx_b = np.random.choice(n_i, size=(500, n_i), replace=True)
    draws_b = inn_runs_balls[idx_b, 0].sum(axis=1) / inn_runs_balls[idx_b, 1].sum(axis=1) * 100
    se_b = draws_b.std()
    
    # Whole Match
    match_runs_balls = p_df.groupby('match_id')['runs'].agg(['sum', 'count']).values
    n_m = len(match_runs_balls)
    idx_c = np.random.choice(n_m, size=(500, n_m), replace=True)
    draws_c = match_runs_balls[idx_c, 0].sum(axis=1) / match_runs_balls[idx_c, 1].sum(axis=1) * 100
    se_c = draws_c.std()
    
    se_a_list.append(se_a)
    se_b_list.append(se_b)
    se_c_list.append(se_c)

se_a_arr = np.array(se_a_list)
se_b_arr = np.array(se_b_list)
se_c_arr = np.array(se_c_list)

ratio_ba = se_b_arr / se_a_arr
ratio_cb = se_c_arr / se_b_arr

print(f"BATTER POPULATION BOOTSTRAP AUDIT (N = {n_players} Batters, 500 draws each):")
print(f"  Scheme A (Delivery)      - Median SE: {np.median(se_a_arr):.2f} SR | Mean: {np.mean(se_a_arr):.2f} | 90% Range: [{np.percentile(se_a_arr, 5):.2f}, {np.percentile(se_a_arr, 95):.2f}]")
print(f"  Scheme B (Match-Innings) - Median SE: {np.median(se_b_arr):.2f} SR | Mean: {np.mean(se_b_arr):.2f} | 90% Range: [{np.percentile(se_b_arr, 5):.2f}, {np.percentile(se_b_arr, 95):.2f}]")
print(f"  Scheme C (Whole Match)   - Median SE: {np.median(se_c_arr):.2f} SR | Mean: {np.mean(se_c_arr):.2f} | 90% Range: [{np.percentile(se_c_arr, 5):.2f}, {np.percentile(se_c_arr, 95):.2f}]")
print(f"  Ratio B / A (Clustering Inflation):")
print(f"    Median Ratio: {np.median(ratio_ba):.2f}x | IQR: [{np.percentile(ratio_ba, 25):.2f}x, {np.percentile(ratio_ba, 75):.2f}x] | 95th Pct: {np.percentile(ratio_ba, 95):.2f}x")
print(f"  Ratio C / B (Match vs Innings Inflation):")
print(f"    Median Ratio: {np.median(ratio_cb):.2f}x | IQR: [{np.percentile(ratio_cb, 25):.2f}x, {np.percentile(ratio_cb, 75):.2f}x] | 95th Pct: {np.percentile(ratio_cb, 95):.2f}x")

# Now Bowler Population Bootstrap (N = 100 sample bowlers)
bowl_ids = q_bowl['bowler_id'].head(100).values
se_a_bowl, se_b_bowl, se_c_bowl = [], [], []

for bid in bowl_ids:
    p_df = valid_bowl_delivs[valid_bowl_delivs['bowler_id'] == bid]
    deliv_runs = p_df['runs'].values
    n_d = len(deliv_runs)
    draws_a = np.random.choice(deliv_runs, size=(500, n_d), replace=True).mean(axis=1) * 6.0
    se_a = draws_a.std()
    
    inn_rb = p_df.groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
    n_i = len(inn_rb)
    idx_b = np.random.choice(n_i, size=(500, n_i), replace=True)
    draws_b = (inn_rb[idx_b, 0].sum(axis=1) / inn_rb[idx_b, 1].sum(axis=1)) * 6.0
    se_b = draws_b.std()
    
    match_rb = p_df.groupby('match_id')['runs'].agg(['sum', 'count']).values
    n_m = len(match_rb)
    idx_c = np.random.choice(n_m, size=(500, n_m), replace=True)
    draws_c = (match_rb[idx_c, 0].sum(axis=1) / match_rb[idx_c, 1].sum(axis=1)) * 6.0
    se_c = draws_c.std()
    
    se_a_bowl.append(se_a)
    se_b_bowl.append(se_b)
    se_c_bowl.append(se_c)

se_a_b = np.array(se_a_bowl)
se_b_b = np.array(se_b_bowl)
se_c_b = np.array(se_c_bowl)

print(f"\nBOWLER POPULATION BOOTSTRAP AUDIT (N = {len(bowl_ids)} Bowlers, 500 draws each):")
print(f"  Scheme A (Delivery)      - Median SE: {np.median(se_a_b):.2f} rpo")
print(f"  Scheme B (Match-Innings) - Median SE: {np.median(se_b_b):.2f} rpo")
print(f"  Scheme C (Whole Match)   - Median SE: {np.median(se_c_b):.2f} rpo")
print(f"  Ratio B / A: Median = {np.median(se_b_b/se_a_b):.2f}x | Ratio C / B: Median = {np.median(se_c_b/se_b_b):.2f}x")

# ==============================================================================
# TASK 4: ROLE STANDARDIZATION SAFEGUARDS & MINIMUM COHORTS
# ==============================================================================
print("\n==================================================================")
print("TASK 4: ROLE STANDARDIZATION SAFEGUARDS & HIERARCHICAL MODELING")
print("==================================================================")
# Audit cohort counts under different position cutoffs:
print("BATTER COHORTS UNDER ALTERNATIVE POSITION DEFINITIONS:")
# Def 1: Standard: Top 1-3, Mid 4-5, Finisher 6-8
# Def 2: Aggressive: Top 1-2, Mid 3-5, Finisher 6-8
# Def 3: Extended: Top 1-3, Mid 4-6, Finisher 7-8
med_order = valid_bat_delivs[valid_bat_delivs['striker_id'].isin(q_bat['striker_id'])].groupby('striker_id')['batting_order'].median()
q_bat['ord'] = q_bat['striker_id'].map(med_order)

def get_def1(o):
    if o <= 3: return 'Top (1-3)'
    elif o <= 5: return 'Mid (4-5)'
    elif o <= 8: return 'Finisher (6-8)'
    else: return 'Tail'

def get_def2(o):
    if o <= 2: return 'Top (1-2)'
    elif o <= 5: return 'Mid (3-5)'
    elif o <= 8: return 'Finisher (6-8)'
    else: return 'Tail'

def get_def3(o):
    if o <= 3: return 'Top (1-3)'
    elif o <= 6: return 'Mid (4-6)'
    elif o <= 8: return 'Finisher (7-8)'
    else: return 'Tail'

print("Def 1 (Standard):", q_bat['ord'].apply(get_def1).value_counts().to_dict())
print("Def 2 (1-2 Top):  ", q_bat['ord'].apply(get_def2).value_counts().to_dict())
print("Def 3 (7-8 Fin):  ", q_bat['ord'].apply(get_def3).value_counts().to_dict())

