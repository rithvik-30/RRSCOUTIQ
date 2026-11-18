import pandas as pd
import numpy as np

# Load pilot enriched dataset
pilot = pd.read_csv('data/enriched/pilot/enriched_ball_by_ball_pilot.csv')

# Exclude super overs for standard DLI
reg = pilot[pilot['innings'].isin([1, 2])].copy()

# Compute pre-delivery match state
reg['is_legal'] = reg['ext_is_legal_delivery']
reg['delivery_runs'] = reg['ext_delivery_total_runs']
reg['is_wicket_int'] = reg['is_wicket'].astype(int)

# Sort
reg = reg.sort_values(['match_id', 'innings', 'overid', 'over_ball_num']).reset_index(drop=True)

# Cumulative balls and score
reg['legal_bowled_before'] = reg.groupby(['match_id', 'innings'])['is_legal'].cumsum() - reg['is_legal']
reg['score_before'] = reg.groupby(['match_id', 'innings'])['delivery_runs'].cumsum() - reg['delivery_runs']
reg['wickets_lost_before'] = reg.groupby(['match_id', 'innings'])['is_wicket_int'].cumsum() - reg['is_wicket_int']
reg['w_hand'] = 10 - reg['wickets_lost_before']
reg['b_rem'] = np.maximum(0, 120 - reg['legal_bowled_before'])
reg['crr'] = np.where(reg['legal_bowled_before'] > 0, reg['score_before'] / (reg['legal_bowled_before'] / 6.0), 0.0)

# Determine phase
def get_phase(o):
    if o <= 6:
        return 'Powerplay'
    elif o <= 15:
        return 'Middle'
    else:
        return 'Death'
reg['phase'] = reg['overid'].apply(get_phase)

# Phase baseline constants
crr_phase_map = {'Powerplay': 8.15, 'Middle': 8.00, 'Death': 9.30}
reg['crr_phase'] = reg['phase'].map(crr_phase_map)

# Target for Innings 2: sum of innings 1 total + 1
inn1_totals = reg[reg['innings'] == 1].groupby('match_id')['delivery_runs'].sum().reset_index()
inn1_totals['target'] = inn1_totals['delivery_runs'] + 1
reg = reg.merge(inn1_totals[['match_id', 'target']], on='match_id', how='left')

reg['runs_needed'] = np.maximum(0, reg['target'] - reg['score_before'])
reg['rrr'] = np.where(reg['b_rem'] > 0, reg['runs_needed'] / (reg['b_rem'] / 6.0), np.nan)

# Compute DLI
def calc_dli(row):
    if row['innings'] == 1:
        phi_map = {'Powerplay': 0.90, 'Middle': 1.00, 'Death': 1.50}
        phi = phi_map[row['phase']]
        term_wkt = (10.0 / (row['w_hand'] + 1.0)) ** 0.60
        stag = max(0.0, (row['crr_phase'] - row['crr']) / 6.0)
        term_stag = (1.0 + stag) ** 0.50
        raw = phi * term_wkt * term_stag
        return min(3.50, max(0.20, raw))
    else: # innings 2
        term_rate = row['rrr'] / row['crr_phase']
        term_wkt = (10.0 / (row['w_hand'] + 1.0)) ** 0.50
        term_time = (1.0 + 24.0 / (row['b_rem'] + 12.0)) ** 0.50
        raw = term_rate * term_wkt * term_time
        return min(5.00, max(0.10, raw))

reg['dli'] = reg.apply(calc_dli, axis=1)

# Add super overs back
so = pilot[pilot['innings'].isin([3, 4])].copy()
so['dli'] = 3.50
so['phase'] = 'Death'
so['phase_label'] = 'Super Over'

all_balls = pd.concat([reg, so], ignore_index=True)

# Tier assignment
def get_tier(d):
    if d < 0.75:
        return 'Tier 1: Low (<0.75)'
    elif d < 1.35:
        return 'Tier 2: Medium (0.75-1.35)'
    elif d < 2.25:
        return 'Tier 3: High (1.35-2.25)'
    else:
        return 'Tier 4: Extreme (>=2.25)'

all_balls['tier'] = all_balls['dli'].apply(get_tier)

print("=== OVERALL PILOT TIER DISTRIBUTION (1,994 DELIVERIES) ===")
tier_counts = all_balls['tier'].value_counts().sort_index()
print(pd.DataFrame({'Count': tier_counts, 'Pct': tier_counts / len(all_balls) * 100}))

print("\n=== TIER DISTRIBUTION BY INNINGS ===")
print(pd.crosstab(all_balls['innings'], all_balls['tier'], normalize='index') * 100)

print("\n=== TIER DISTRIBUTION BY PHASE ===")
print(pd.crosstab(all_balls['phase'], all_balls['tier'], normalize='index') * 100)

print("\n=== PRESSURE POPULATION SENSITIVITY TO CUTOFF BOUNDARIES ===")
for cutoff in [1.10, 1.20, 1.30, 1.35, 1.40, 1.50, 1.75, 2.00, 2.25]:
    ge = (all_balls['dli'] >= cutoff).sum()
    print(f"DLI >= {cutoff:4.2f}: {ge:4d} deliveries ({ge/len(all_balls)*100:5.1f}%)")

