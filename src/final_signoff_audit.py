import pandas as pd
import numpy as np

# Load data
bbb = pd.read_csv('data/extracted/ball_by_ball.csv')
matches = pd.read_csv('data/extracted/matches.csv')

# Flags
bbb['is_striker_ball'] = bbb['extras_type'] != 'wide'
bbb['is_legal'] = ~bbb['extras_type'].isin(['wide', 'Overstep', 'other'])
bbb['is_dot'] = bbb['runs'] == 0
bbb['is_boundary'] = bbb['is_four'] | bbb['is_six']
bbb['is_wicket_int'] = bbb['is_wicket'].astype(int)

# ==============================================================================
# TASK 1: EXACT ARITHMETIC & ESTIMATION AUDIT FOR NORMAL-NORMAL
# ==============================================================================
print("==================================================================")
print("TASK 1: NORMAL-NORMAL SHRINKAGE ARITHMETIC & PRECISION AUDIT")
print("==================================================================")

valid_bat = bbb[bbb['is_striker_ball']].copy()
runs_var_float = valid_bat['runs'].var()
scaled_var_float = 10000.0 * runs_var_float

print(f"Unrounded ball-level runs variance: {runs_var_float:.8f}")
print(f"Rounded to 4 decimals for display:  {runs_var_float:.4f}")
print(f"Direct product with unrounded float: 10,000 * {runs_var_float:.8f} = {scaled_var_float:.2f}")
print(f"Product if using rounded 3.0382:     10,000 * 3.0382 = {10000.0 * 3.0382:.2f}")
print(f"Discrepancy explanation: {scaled_var_float:.2f} was calculated from unrounded float ({runs_var_float:.6f}), but displayed alongside rounded 3.0382, causing apparent 0.34 difference.")

# Batting career
bat_m = valid_bat.groupby(['striker_id', 'match_id', 'innings']).agg(
    balls=('runs', 'count'),
    runs=('runs', 'sum'),
    outs=('is_wicket_int', 'sum')
).reset_index()

bat_c = bat_m.groupby('striker_id').agg(
    innings=('match_id', 'count'),
    balls=('balls', 'sum'),
    runs=('runs', 'sum'),
    outs=('outs', 'sum')
).reset_index()

q_bat = bat_c[(bat_c['innings'] >= 12) & (bat_c['balls'] >= 120)].copy()
q_bat['sr'] = q_bat['runs'] / q_bat['balls'] * 100
q_bat['out_rate'] = q_bat['outs'] / q_bat['balls']

# Bowling career
valid_bowl = bbb[bbb['is_legal']].copy()
bowl_m = valid_bowl.groupby(['bowler_id', 'match_id', 'innings']).agg(
    balls=('runs', 'count'),
    runs=('runs', 'sum'),
    wickets=('is_wicket_int', 'sum')
).reset_index()

bowl_c = bowl_m.groupby('bowler_id').agg(
    innings=('match_id', 'count'),
    balls=('balls', 'sum'),
    runs=('runs', 'sum'),
    wickets=('wickets', 'sum')
).reset_index()

q_bowl = bowl_c[(bowl_c['innings'] >= 12) & (bowl_c['balls'] >= 144)].copy()
q_bowl['econ'] = q_bowl['runs'] / (q_bowl['balls'] / 6.0)

print(f"\nPopulation counts: Qualified Batters N = {len(q_bat)}, Qualified Bowlers N = {len(q_bowl)}")

# ==============================================================================
# TASK 2: WICKET PRIOR CAP SENSITIVITY ACROSS ENTIRE QUALIFIED POPULATION
# ==============================================================================
print("\n==================================================================")
print("TASK 2: WICKET PRIOR CAP SENSITIVITY (ALL 250 QUALIFIED BATTERS)")
print("==================================================================")

p_prior = q_bat['outs'].sum() / q_bat['balls'].sum()
print(f"Overall Qualified Population Wicket Hazard Mean: {p_prior*100:.3f}%")

caps = [60, 90, 120, 180, 1613]
results_caps = {}

for M in caps:
    alpha = p_prior * M
    q_bat[f'shrunk_p_{M}'] = (q_bat['outs'] + alpha) / (q_bat['balls'] + M) * 100
    results_caps[M] = {
        'mean': q_bat[f'shrunk_p_{M}'].mean(),
        'median': q_bat[f'shrunk_p_{M}'].median(),
        'std': q_bat[f'shrunk_p_{M}'].std(),
        'iqr': q_bat[f'shrunk_p_{M}'].quantile(0.75) - q_bat[f'shrunk_p_{M}'].quantile(0.25),
        'p5': q_bat[f'shrunk_p_{M}'].quantile(0.05),
        'p95': q_bat[f'shrunk_p_{M}'].quantile(0.95),
    }

df_caps = pd.DataFrame(results_caps).T
print("DISTRIBUTION OF POSTERIOR WICKET HAZARD ESTIMATES ACROSS 250 BATTERS (%):")
print(df_caps.round(3))

# Rank correlations between caps
print("\nSPEARMAN RANK CORRELATIONS BETWEEN ALTERNATIVE CAPS:")
for m1 in [60, 90, 120, 180]:
    for m2 in [60, 90, 120, 180]:
        if m1 < m2:
            corr = q_bat[f'shrunk_p_{m1}'].corr(q_bat[f'shrunk_p_{m2}'], method='spearman')
            print(f"  Corr(M={m1}, M={m2}): {corr:.5f}")

# Exposure strata sensitivity
q_bat['vol_group'] = pd.qcut(q_bat['balls'], q=3, labels=['Low Volume (120-220b)', 'Mid Volume (221-420b)', 'High Volume (>420b)'])
print("\nMEAN POSTERIOR WICKET HAZARD BY EXPOSURE STRATUM (%):")
for M in [60, 90, 120, 180]:
    grp_means = q_bat.groupby('vol_group')[f'shrunk_p_{M}'].mean()
    print(f"Cap M={M:3d} | " + " | ".join([f"{k}: {v:.3f}%" for k, v in grp_means.items()]))


# ==============================================================================
# TASK 3: FULL POPULATION BOOTSTRAP (250 BATTERS & ALL 227 BOWLERS, 1000 DRAWS)
# ==============================================================================
print("\n==================================================================")
print("TASK 3: COMPLETE BOOTSTRAP AUDIT (250 BATTERS & ALL 227 BOWLERS, 1,000 DRAWS)")
print("==================================================================")

np.random.seed(42)

# Batters Bootstrap (1,000 draws)
bat_ids = q_bat['striker_id'].values
b_se_a, b_se_b, b_se_c = [], [], []

for pid in bat_ids:
    p_df = valid_bat[valid_bat['striker_id'] == pid]
    # Scheme A (Delivery)
    runs_d = p_df['runs'].values
    nd = len(runs_d)
    se_a = np.random.choice(runs_d, size=(1000, nd), replace=True).mean(axis=1).std() * 100
    
    # Scheme B (Match-Innings)
    inn_agg = p_df.groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
    ni = len(inn_agg)
    idx_b = np.random.choice(ni, size=(1000, ni), replace=True)
    se_b = (inn_agg[idx_b, 0].sum(axis=1) / inn_agg[idx_b, 1].sum(axis=1) * 100).std()
    
    # Scheme C (Whole Match)
    m_agg = p_df.groupby('match_id')['runs'].agg(['sum', 'count']).values
    nm = len(m_agg)
    idx_c = np.random.choice(nm, size=(1000, nm), replace=True)
    se_c = (m_agg[idx_c, 0].sum(axis=1) / m_agg[idx_c, 1].sum(axis=1) * 100).std()
    
    b_se_a.append(se_a)
    b_se_b.append(se_b)
    b_se_c.append(se_c)

b_se_a = np.array(b_se_a)
b_se_b = np.array(b_se_b)
b_se_c = np.array(b_se_c)
r_ba_bat = b_se_b / b_se_a
r_cb_bat = b_se_c / b_se_b

print(f"BATTER POPULATION AUDIT (N = {len(b_se_a)} Batters):")
print(f"  Scheme A (Delivery)      - Mean SE: {np.mean(b_se_a):.2f} SR | Median SE: {np.median(b_se_a):.2f} SR | 25th: {np.percentile(b_se_a, 25):.2f} | 75th: {np.percentile(b_se_a, 75):.2f} | 95th: {np.percentile(b_se_a, 95):.2f}")
print(f"  Scheme B (Match-Innings) - Mean SE: {np.mean(b_se_b):.2f} SR | Median SE: {np.median(b_se_b):.2f} SR | 25th: {np.percentile(b_se_b, 25):.2f} | 75th: {np.percentile(b_se_b, 75):.2f} | 95th: {np.percentile(b_se_b, 95):.2f}")
print(f"  Scheme C (Whole Match)   - Mean SE: {np.mean(b_se_c):.2f} SR | Median SE: {np.median(b_se_c):.2f} SR | 25th: {np.percentile(b_se_c, 25):.2f} | 75th: {np.percentile(b_se_c, 75):.2f} | 95th: {np.percentile(b_se_c, 95):.2f}")
print(f"  Ratio B / A: Median = {np.median(r_ba_bat):.2f}x | 25th = {np.percentile(r_ba_bat, 25):.2f}x | 75th = {np.percentile(r_ba_bat, 75):.2f}x | 95th = {np.percentile(r_ba_bat, 95):.2f}x")
print(f"  Ratio C / B: Median = {np.median(r_cb_bat):.2f}x | 25th = {np.percentile(r_cb_bat, 25):.2f}x | 75th = {np.percentile(r_cb_bat, 75):.2f}x | 95th = {np.percentile(r_cb_bat, 95):.2f}x")

# Bowlers Bootstrap (ALL 227 Qualified Bowlers, 1,000 draws)
bowl_ids = q_bowl['bowler_id'].values
bw_se_a, bw_se_b, bw_se_c = [], [], []

for bid in bowl_ids:
    p_df = valid_bowl[valid_bowl['bowler_id'] == bid]
    runs_d = p_df['runs'].values
    nd = len(runs_d)
    se_a = np.random.choice(runs_d, size=(1000, nd), replace=True).mean(axis=1).std() * 6.0
    
    inn_agg = p_df.groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
    ni = len(inn_agg)
    idx_b = np.random.choice(ni, size=(1000, ni), replace=True)
    se_b = (inn_agg[idx_b, 0].sum(axis=1) / inn_agg[idx_b, 1].sum(axis=1) * 6.0).std()
    
    m_agg = p_df.groupby('match_id')['runs'].agg(['sum', 'count']).values
    nm = len(m_agg)
    idx_c = np.random.choice(nm, size=(1000, nm), replace=True)
    se_c = (m_agg[idx_c, 0].sum(axis=1) / m_agg[idx_c, 1].sum(axis=1) * 6.0).std()
    
    bw_se_a.append(se_a)
    bw_se_b.append(se_b)
    bw_se_c.append(se_c)

bw_se_a = np.array(bw_se_a)
bw_se_b = np.array(bw_se_b)
bw_se_c = np.array(bw_se_c)
r_ba_bowl = bw_se_b / bw_se_a
r_cb_bowl = bw_se_c / bw_se_b

print(f"\nBOWLER POPULATION AUDIT (ALL N = {len(bw_se_a)} Bowlers):")
print(f"  Scheme A (Delivery)      - Mean SE: {np.mean(bw_se_a):.2f} rpo | Median SE: {np.median(bw_se_a):.2f} rpo | 25th: {np.percentile(bw_se_a, 25):.2f} | 75th: {np.percentile(bw_se_a, 75):.2f} | 95th: {np.percentile(bw_se_a, 95):.2f}")
print(f"  Scheme B (Match-Innings) - Mean SE: {np.mean(bw_se_b):.2f} rpo | Median SE: {np.median(bw_se_b):.2f} rpo | 25th: {np.percentile(bw_se_b, 25):.2f} | 75th: {np.percentile(bw_se_b, 75):.2f} | 95th: {np.percentile(bw_se_b, 95):.2f}")
print(f"  Scheme C (Whole Match)   - Mean SE: {np.mean(bw_se_c):.2f} rpo | Median SE: {np.median(bw_se_c):.2f} rpo | 25th: {np.percentile(bw_se_c, 25):.2f} | 75th: {np.percentile(bw_se_c, 75):.2f} | 95th: {np.percentile(bw_se_c, 95):.2f}")
print(f"  Ratio B / A: Median = {np.median(r_ba_bowl):.2f}x | 25th = {np.percentile(r_ba_bowl, 25):.2f}x | 75th = {np.percentile(r_ba_bowl, 75):.2f}x | 95th = {np.percentile(r_ba_bowl, 95):.2f}x")
print(f"  Ratio C / B: Median = {np.median(r_cb_bowl):.2f}x | 25th = {np.percentile(r_cb_bowl, 25):.2f}x | 75th = {np.percentile(r_cb_bowl, 75):.2f}x | 95th = {np.percentile(r_cb_bowl, 95):.2f}x")

# ==============================================================================
# TASK 4: ROLE STANDARDIZATION SAFEGUARD AUDIT
# ==============================================================================
print("\n==================================================================")
print("TASK 4: ROLE STANDARDIZATION SAFEGUARDS & ALTERNATIVE ROLE CUTOFFS")
print("==================================================================")

# Bowler role cutoffs sensitivity:
# Def B1: PP >= 40%, Death >= 30%
# Def B2: PP >= 35%, Death >= 25%
# Def B3: PP >= 45%, Death >= 35%
bbb['over'] = bbb['overid']
def get_bp(o):
    if o <= 6: return 'PP'
    elif o <= 15: return 'Mid'
    else: return 'Death'
bbb['bp'] = bbb['over'].apply(get_bp)
b_shares = bbb[bbb['is_legal']].groupby(['bowler_id', 'bp']).size().unstack(fill_value=0)
b_shares['tot'] = b_shares.sum(axis=1)
for p in ['PP', 'Mid', 'Death']:
    b_shares[p+'_pct'] = b_shares[p] / b_shares['tot']

q_bowl_shares = b_shares.loc[q_bowl['bowler_id']].copy()

def role_b1(r):
    if r['PP_pct'] >= 0.40: return 'Powerplay'
    elif r['Death_pct'] >= 0.30: return 'Death'
    else: return 'Middle'

def role_b2(r):
    if r['PP_pct'] >= 0.35: return 'Powerplay'
    elif r['Death_pct'] >= 0.25: return 'Death'
    else: return 'Middle'

def role_b3(r):
    if r['PP_pct'] >= 0.45: return 'Powerplay'
    elif r['Death_pct'] >= 0.35: return 'Death'
    else: return 'Middle'

print("BOWLER COHORT COUNTS UNDER ALTERNATIVE ROLE CUTOFFS:")
print("  Cutoff B1 (Standard: PP>=40%, Death>=30%):", q_bowl_shares.apply(role_b1, axis=1).value_counts().to_dict())
print("  Cutoff B2 (Relaxed:  PP>=35%, Death>=25%):", q_bowl_shares.apply(role_b2, axis=1).value_counts().to_dict())
print("  Cutoff B3 (Strict:   PP>=45%, Death>=35%):", q_bowl_shares.apply(role_b3, axis=1).value_counts().to_dict())

