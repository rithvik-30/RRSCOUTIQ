import pandas as pd
import numpy as np

# Load pilot deliveries to estimate clustering & ICC
pilot = pd.read_csv('data/enriched/pilot/enriched_ball_by_ball_pilot.csv')

# Cluster ICC estimation: ANOVA on runs_off_bat grouped by match_innings
pilot['cluster_id'] = pilot['match_id'].astype(str) + '_' + pilot['innings'].astype(str)
clusters = pilot.groupby('cluster_id')

m_k = clusters['runs'].count()
m_bar = m_k.mean()
k = len(m_k)
N = len(pilot)

grand_mean = pilot['runs'].mean()
ss_between = (clusters['runs'].mean() - grand_mean)**2 * m_k
ssb = ss_between.sum()
msb = ssb / (k - 1)

ss_within = clusters['runs'].apply(lambda x: ((x - x.mean())**2).sum()).sum()
msw = ss_within / (N - k)

# ANOVA estimate of s_b^2 and s_w^2
# m_0 accounts for unequal cluster sizes
m_0 = (N - (m_k**2).sum() / N) / (k - 1)
s_b2 = max(0, (msb - msw) / m_0)
s_w2 = msw
icc = s_b2 / (s_b2 + s_w2)

deff = 1 + (m_bar - 1) * icc
variance_inflation = deff
se_underestimation = np.sqrt(deff)

print("=== CLUSTER EFFECT (ICC & DESIGN EFFECT) ===")
print(f"Total Clusters (Match-Innings): {k}")
print(f"Average Cluster Size (Deliveries/Innings): {m_bar:.1f}")
print(f"Intra-Class Correlation (ICC, rho): {icc:.4f}")
print(f"Design Effect (DEFF): {deff:.3f}")
print(f"Standard Error Underestimation Factor (if unclustered): {se_underestimation:.2f}x")

# Cohort Variance Analysis
bbb = pd.read_csv('data/extracted/ball_by_ball.csv')
bbb['is_striker_ball'] = bbb['extras_type'] != 'wide'
bat_m = bbb.groupby(['striker_id', 'match_id']).agg(
    balls=('is_striker_ball', 'sum'),
    runs=('runs', 'sum'),
    order=('batting_order', 'min')
).reset_index()

bat_c = bat_m.groupby('striker_id').agg(
    innings=('match_id', 'count'),
    balls=('balls', 'sum'),
    runs=('runs', 'sum'),
    order=('order', 'median')
).reset_index()

bat_c['sr'] = np.where(bat_c['balls'] > 0, bat_c['runs'] / bat_c['balls'] * 100, np.nan)
def get_role(o):
    if o <= 3: return 'Top Order (1-3)'
    elif o <= 5: return 'Middle Order (4-5)'
    elif o <= 8: return 'Finishers (6-8)'
    else: return 'Tail (9-11)'
bat_c['role'] = bat_c['order'].apply(get_role)

# Qualified batters
q_bat = bat_c[(bat_c['innings'] >= 12) & (bat_c['balls'] >= 120)]
print("\n=== BATTER COHORT VARIANCE COMPARISON ===")
for r, g in q_bat.groupby('role'):
    print(f"Role: {r:20s} | N: {len(g):3d} | Mean SR: {g['sr'].mean():5.1f} | Std SR: {g['sr'].std():5.1f} | IQR SR: {g['sr'].quantile(0.75) - g['sr'].quantile(0.25):5.1f}")

