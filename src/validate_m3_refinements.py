import numpy as np
import pandas as pd

# 1. Full 1-120 Legal-Ball Validation of Setting DLI
def phi_smooth(t):
    return 0.80 + 0.70 * ((t / 120.0) ** 1.20)

def dli_setting_smooth(t, w_hand, crr, crr_phase):
    phi = phi_smooth(t)
    term_wkt = (10.0 / (w_hand + 1.0)) ** 0.60
    stag = max(0.0, (crr_phase - crr) / 6.0)
    term_stag = (1.0 + stag) ** 0.50
    raw = phi * term_wkt * term_stag
    return min(3.50, max(0.20, raw)), raw, phi

# Evaluate across t = 1 to 120 for 3 distinct match trajectories:
# Trajectory A: Par trajectory (CRR = 8.0, W_lost increases gradually from 0 at t=1 to 6 at t=120)
# Trajectory B: Dominant trajectory (CRR = 10.0, W_lost = 1 throughout)
# Trajectory C: Collapse trajectory (CRR = 5.0, W_lost = 4 at t=36, 7 at t=90, 9 at t=120)

t_vals = np.arange(1, 121)
records = []
for t in t_vals:
    # Phase baseline
    if t <= 36:
        phase = 'Powerplay'
        cp = 8.15
    elif t <= 90:
        phase = 'Middle'
        cp = 8.00
    else:
        phase = 'Death'
        cp = 9.30
        
    # Traj A: Par
    w_lost_a = int(6.0 * (t / 120.0))
    dli_a, raw_a, phi = dli_setting_smooth(t, 10 - w_lost_a, 8.0, cp)
    
    # Traj B: Dominant
    dli_b, raw_b, _ = dli_setting_smooth(t, 9, 10.0, cp)
    
    # Traj C: Collapse
    if t <= 36:
        w_lost_c = int(4.0 * (t / 36.0))
        crr_c = 5.5
    elif t <= 90:
        w_lost_c = 4 + int(3.0 * ((t - 36) / 54.0))
        crr_c = 5.0
    else:
        w_lost_c = 7 + int(2.0 * ((t - 90) / 30.0))
        crr_c = 5.0
    dli_c, raw_c, _ = dli_setting_smooth(t, 10 - w_lost_c, crr_c, cp)
    
    records.append({
        'ball': t, 'phase': phase, 'phi': round(phi, 3),
        'dli_par': round(dli_a, 3), 'dli_dom': round(dli_b, 3), 'dli_col': round(dli_c, 3)
    })

df_setting = pd.DataFrame(records)

# Check at key transitions: 35, 36, 37, 89, 90, 91
key_balls = [1, 18, 36, 37, 60, 90, 91, 105, 120]
print("=== SETTING DLI AT KEY LEGAL BALLS (1-120) ===")
print(df_setting[df_setting['ball'].isin(key_balls)].to_string(index=False))

# Check continuity / derivative jump across phase boundaries (t=36 to 37, t=90 to 91)
print("\n=== BOUNDARY CONTINUITY CHECK ===")
for b in [36, 90]:
    row_pre = df_setting[df_setting['ball'] == b].iloc[0]
    row_post = df_setting[df_setting['ball'] == b+1].iloc[0]
    delta_phi = row_post['phi'] - row_pre['phi']
    delta_dli = row_post['dli_par'] - row_pre['dli_par']
    print(f"Ball {b} -> {b+1}: Delta Phi = {delta_phi:.4f}, Delta DLI (Par) = {delta_dli:.4f}")

# 2. Revised Tier Analysis on Pilot Data
pilot = pd.read_csv('data/enriched/pilot/enriched_ball_by_ball_pilot.csv')
reg = pilot[pilot['innings'].isin([1, 2])].copy()
reg['is_legal'] = reg['ext_is_legal_delivery']
reg['delivery_runs'] = reg['ext_delivery_total_runs']
reg['is_wicket_int'] = reg['is_wicket'].astype(int)
reg = reg.sort_values(['match_id', 'innings', 'overid', 'over_ball_num']).reset_index(drop=True)

reg['legal_bowled_before'] = reg.groupby(['match_id', 'innings'])['is_legal'].cumsum() - reg['is_legal']
reg['score_before'] = reg.groupby(['match_id', 'innings'])['delivery_runs'].cumsum() - reg['delivery_runs']
reg['wickets_lost_before'] = reg.groupby(['match_id', 'innings'])['is_wicket_int'].cumsum() - reg['is_wicket_int']
reg['w_hand'] = 10 - reg['wickets_lost_before']
reg['b_rem'] = np.maximum(0, 120 - reg['legal_bowled_before'])
reg['crr'] = np.where(reg['legal_bowled_before'] > 0, reg['score_before'] / (reg['legal_bowled_before'] / 6.0), 0.0)

def get_phase(o):
    if o <= 6:
        return 'Powerplay'
    elif o <= 15:
        return 'Middle'
    else:
        return 'Death'
reg['phase'] = reg['overid'].apply(get_phase)
crr_phase_map = {'Powerplay': 8.15, 'Middle': 8.00, 'Death': 9.30}
reg['crr_phase'] = reg['phase'].map(crr_phase_map)

inn1_totals = reg[reg['innings'] == 1].groupby('match_id')['delivery_runs'].sum().reset_index()
inn1_totals['target'] = inn1_totals['delivery_runs'] + 1
reg = reg.merge(inn1_totals[['match_id', 'target']], on='match_id', how='left')
reg['runs_needed'] = np.maximum(0, reg['target'] - reg['score_before'])
reg['rrr'] = np.where(reg['b_rem'] > 0, reg['runs_needed'] / (reg['b_rem'] / 6.0), np.nan)

# Compute smooth DLI
def calc_dli_refined(row):
    if row['innings'] == 1:
        t = row['legal_bowled_before'] + 1 # 1-indexed ball
        dli, _, _ = dli_setting_smooth(t, row['w_hand'], row['crr'], row['crr_phase'])
        return dli
    else:
        term_rate = row['rrr'] / row['crr_phase']
        term_wkt = (10.0 / (row['w_hand'] + 1.0)) ** 0.50
        term_time = (1.0 + 24.0 / (row['b_rem'] + 12.0)) ** 0.50
        raw = term_rate * term_wkt * term_time
        return min(5.00, max(0.10, raw))

reg['dli'] = reg.apply(calc_dli_refined, axis=1)

so = pilot[pilot['innings'].isin([3, 4])].copy()
so['dli'] = 3.50
so['phase'] = 'Death'

all_b = pd.concat([reg, so], ignore_index=True)

# Revised Tiers: Tier 1 < 0.90, Tier 2 [0.90, 1.35), Tier 3 [1.35, 2.25), Tier 4 >= 2.25
def get_tier_revised(d):
    if d < 0.90:
        return 'Tier 1: Low (<0.90)'
    elif d < 1.35:
        return 'Tier 2: Medium [0.90-1.35)'
    elif d < 2.25:
        return 'Tier 3: High [1.35-2.25)'
    else:
        return 'Tier 4: Extreme (>=2.25)'

all_b['tier_revised'] = all_b['dli'].apply(get_tier_revised)
t_counts = all_b['tier_revised'].value_counts().sort_index()
print("\n=== REVISED TIER DISTRIBUTION (PILOT 1,994 DELIVERIES) ===")
print(pd.DataFrame({'Count': t_counts, 'Pct': t_counts / len(all_b) * 100}))

print("\n=== REVISED TIERS BY INNINGS ===")
print(pd.crosstab(all_b['innings'], all_b['tier_revised'], normalize='index') * 100)

