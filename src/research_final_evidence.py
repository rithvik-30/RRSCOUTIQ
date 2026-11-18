import pandas as pd
import numpy as np

# Load ball by ball and matches
bbb = pd.read_csv('data/extracted/ball_by_ball.csv')
matches = pd.read_csv('data/extracted/matches.csv')

# Legal balls & flags
bbb['is_striker_ball'] = bbb['extras_type'] != 'wide'
bbb['is_legal'] = ~bbb['extras_type'].isin(['wide', 'Overstep', 'other'])
bbb['is_dot'] = bbb['runs'] == 0
bbb['is_boundary'] = bbb['is_four'] | bbb['is_six']
bbb['is_wicket_int'] = bbb['is_wicket'].astype(int)

# --- TASK 1: SETTING DLI SENSITIVITY ---
def phi_power(t):
    return 0.80 + 0.70 * ((t / 120.0) ** 1.20)

def dli_setting(t, w_hand, crr, crr_phase):
    phi = phi_power(t)
    term_wkt = (10.0 / (w_hand + 1.0)) ** 0.60
    stag = max(0.0, (crr_phase - crr) / 6.0)
    term_stag = (1.0 + stag) ** 0.50
    raw = phi * term_wkt * term_stag
    return min(3.50, max(0.20, raw)), raw, phi

scenarios = [
    ("Over 20 (Ball 120) - Dominant Setting", 120, 9, 10.5, 9.30),
    ("Over 20 (Ball 120) - Steady Setting", 120, 6, 8.5, 9.30),
    ("Over 20 (Ball 120) - Tail Collapse", 120, 2, 6.5, 9.30),
    ("Over 5 (Ball 30) - Early Collapse (20/6)", 30, 4, 4.0, 8.15),
    ("Over 5 (Ball 30) - Normal PP (40/1)", 30, 9, 8.0, 8.15),
    ("Over 10 (Ball 60) - Middle Collapse (50/5)", 60, 5, 5.0, 8.00),
    ("Over 10 (Ball 60) - Dominant Middle (95/1)", 60, 9, 9.5, 8.00),
    ("Over 16 (Ball 96) - Death Launch (145/3)", 96, 7, 9.0, 9.30),
]

print("=== TASK 1: SETTING DLI SENSITIVITY AUDIT ===")
for name, t, w, crr, cp in scenarios:
    dli, raw, phi = dli_setting(t, w, crr, cp)
    print(f"{name:45s} | t={t:3d} (Phi={phi:.3f}) | W_hand={w:1d} | CRR={crr:4.1f} | Raw DLI={raw:.3f} | Clamped={dli:.3f}")

# --- TASK 2: BAYESIAN PRIOR ESTIMATION ---
bat_m = bbb.groupby(['striker_id', 'match_id', 'innings']).agg(
    balls=('is_striker_ball', 'sum'),
    runs=('runs', 'sum'),
    dots=('is_dot', 'sum'),
    bnds=('is_boundary', 'sum'),
    outs=('is_wicket_int', 'sum')
).reset_index()

bat_c = bat_m.groupby('striker_id').agg(
    innings=('match_id', 'count'),
    balls=('balls', 'sum'),
    runs=('runs', 'sum'),
    dots=('dots', 'sum'),
    bnds=('bnds', 'sum'),
    outs=('outs', 'sum')
).reset_index()

q_bat = bat_c[(bat_c['innings'] >= 12) & (bat_c['balls'] >= 120)].copy()
q_bat['dot_rate'] = q_bat['dots'] / q_bat['balls']
q_bat['bnd_rate'] = q_bat['bnds'] / q_bat['balls']
q_bat['out_rate'] = q_bat['outs'] / q_bat['balls']
q_bat['sr'] = q_bat['runs'] / q_bat['balls'] * 100

print(f"\n=== TASK 2: QUALIFIED BATTER POPULATION (N = {len(q_bat)}) ===")

def estimate_beta_params(p_obs, n_obs):
    p_bar = np.average(p_obs, weights=n_obs)
    s2 = np.average((p_obs - p_bar)**2, weights=n_obs)
    samp_var = np.mean(p_obs * (1 - p_obs) / n_obs)
    tau2 = max(1e-5, s2 - samp_var)
    M = max(5.0, p_bar * (1 - p_bar) / tau2 - 1.0)
    alpha = p_bar * M
    beta = (1 - p_bar) * M
    return p_bar, tau2, M, alpha, beta

print("\n--- BETA-BINOMIAL EMPIRICAL PRIOR ESTIMATES ---")
for name, col in [('Dot %', 'dot_rate'), ('Boundary %', 'bnd_rate'), ('Wicket Hazard %', 'out_rate')]:
    p_bar, tau2, M, a, b = estimate_beta_params(q_bat[col], q_bat['balls'])
    print(f"Metric: {name:16s} | Prior Mean (p): {p_bar:.4f} | Between Var (tau^2): {tau2:.6f} | Prior M: {M:5.1f} | Alpha: {a:5.2f} | Beta: {b:5.2f}")

sr_bar = np.average(q_bat['sr'], weights=q_bat['balls'])
sr_s2 = np.average((q_bat['sr'] - sr_bar)**2, weights=q_bat['balls'])
ball_var = bbb['runs'].var() * 10000
k_sr = ball_var / max(1.0, sr_s2)
print(f"\n--- NORMAL-NORMAL EMPIRICAL STRIKE RATE PRIOR ---")
print(f"Mean SR: {sr_bar:.2f} | Between Std (tau): {np.sqrt(sr_s2):.2f} | Ball-level Var: {bbb['runs'].var():.3f} | Derived K: {k_sr:.1f}")

# --- TASK 3: FAST VECTORIZED BOOTSTRAP RESAMPLING SIMULATION ---
top_bat_ids = q_bat.sort_values('balls', ascending=False)['striker_id'].head(5).values

print("\n=== TASK 3: BOOTSTRAP SCHEME COMPARISON (5 SAMPLE PLAYERS, 1,000 DRAWS) ===")
print("Player ID | Scheme A (Delivery) SE | Scheme B (Match-Innings) SE | Scheme C (Whole Match) SE | Ratio B/A | Ratio C/B")

np.random.seed(42)
for pid in top_bat_ids:
    p_df = bbb[bbb['striker_id'] == pid].copy()
    valid_delivs = p_df[p_df['extras_type'] != 'wide']['runs'].values
    n_delivs = len(valid_delivs)
    
    # Scheme A: Delivery Bootstrap
    boot_a_draws = np.random.choice(valid_delivs, size=(1000, n_delivs), replace=True)
    boot_a_sr = boot_a_draws.mean(axis=1) * 100
    se_a = boot_a_sr.std()
    
    # Scheme B: Match-Innings Bootstrap
    # Pre-aggregate runs and balls per innings
    inn_agg = p_df[p_df['extras_type'] != 'wide'].groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
    n_inn = len(inn_agg)
    draw_idx_b = np.random.choice(n_inn, size=(1000, n_inn), replace=True)
    # inn_agg has shape (n_inn, 2): [:, 0] is runs, [:, 1] is balls
    sampled_runs_b = inn_agg[draw_idx_b, 0].sum(axis=1)
    sampled_balls_b = inn_agg[draw_idx_b, 1].sum(axis=1)
    boot_b_sr = sampled_runs_b / sampled_balls_b * 100
    se_b = boot_b_sr.std()
    
    # Scheme C: Whole Match Bootstrap
    match_agg = p_df[p_df['extras_type'] != 'wide'].groupby('match_id')['runs'].agg(['sum', 'count']).values
    n_match = len(match_agg)
    draw_idx_c = np.random.choice(n_match, size=(1000, n_match), replace=True)
    sampled_runs_c = match_agg[draw_idx_c, 0].sum(axis=1)
    sampled_balls_c = match_agg[draw_idx_c, 1].sum(axis=1)
    boot_c_sr = sampled_runs_c / sampled_balls_c * 100
    se_c = boot_c_sr.std()
    
    print(f"Player {pid:5d} | SE_A: {se_a:6.2f}            | SE_B: {se_b:6.2f}                 | SE_C: {se_c:6.2f}             | {se_b/se_a:5.2f}x    | {se_c/se_b:5.2f}x")

# --- TASK 5: ROLE STANDARDIZATION ---
bat_median_order = bbb[bbb['striker_id'].isin(q_bat['striker_id'])].groupby('striker_id')['batting_order'].median()
q_bat['median_order'] = q_bat['striker_id'].map(bat_median_order)

def get_b_role(order):
    if order <= 3.0: return 'Top Order (1-3)'
    elif order <= 5.0: return 'Middle Order (4-5)'
    elif order <= 8.0: return 'Finishers (6-8)'
    else: return 'Tail (9-11)'

q_bat['role'] = q_bat['median_order'].apply(get_b_role)

print("\n=== TASK 5: ROLE STANDARDIZATION SUMMARY (BATTERS) ===")
for r, g in q_bat.groupby('role'):
    print(f"Role: {r:20s} | N: {len(g):3d} | Mean SR: {g['sr'].mean():6.2f} | Std SR: {g['sr'].std():5.2f} | Mean Dot%: {g['dot_rate'].mean()*100:5.1f}% | Std Dot%: {g['dot_rate'].std()*100:4.1f}% | Mean Bnd%: {g['bnd_rate'].mean()*100:5.1f}%")

# Bowlers
bowl_m = bbb.groupby(['bowler_id', 'match_id', 'innings']).agg(
    legal_balls=('is_legal', 'sum'),
    runs=('runs', 'sum'),
    wickets=('is_wicket_int', 'sum')
).reset_index()

bowl_c = bowl_m.groupby('bowler_id').agg(
    innings=('match_id', 'count'),
    balls=('legal_balls', 'sum'),
    runs=('runs', 'sum'),
    wickets=('wickets', 'sum')
).reset_index()

q_bowl = bowl_c[(bowl_c['innings'] >= 12) & (bowl_c['balls'] >= 144)].copy()
q_bowl['econ'] = q_bowl['runs'] / (q_bowl['balls'] / 6.0)
q_bowl['wkt_rate'] = q_bowl['wickets'] / q_bowl['balls'] * 100

bbb['over'] = bbb['overid']
def get_bowl_phase(o):
    if o <= 6: return 'PP'
    elif o <= 15: return 'Mid'
    else: return 'Death'
bbb['b_phase'] = bbb['over'].apply(get_bowl_phase)
b_phase_counts = bbb[bbb['is_legal']].groupby(['bowler_id', 'b_phase']).size().unstack(fill_value=0)
b_phase_counts['total'] = b_phase_counts.sum(axis=1)
for p in ['PP', 'Mid', 'Death']:
    b_phase_counts[p + '_pct'] = b_phase_counts[p] / b_phase_counts['total']

def get_b_role_bowl(row):
    if row.get('PP_pct', 0) >= 0.40: return 'Powerplay Specialist'
    elif row.get('Death_pct', 0) >= 0.30: return 'Death Specialist'
    else: return 'Middle Enforcer'

q_bowl = q_bowl.merge(b_phase_counts.apply(get_b_role_bowl, axis=1).rename('role'), on='bowler_id', how='left')

print("\n=== TASK 5: ROLE STANDARDIZATION SUMMARY (BOWLERS) ===")
for r, g in q_bowl.groupby('role'):
    print(f"Role: {r:22s} | N: {len(g):3d} | Mean Econ: {g['econ'].mean():5.2f} | Std Econ: {g['econ'].std():4.2f} | Mean Wkt%: {g['wkt_rate'].mean():5.2f}% | Std Wkt%: {g['wkt_rate'].std():4.2f}%")
