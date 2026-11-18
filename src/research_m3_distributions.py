import pandas as pd
import numpy as np

# Load ball by ball and matches
bbb = pd.read_csv('data/extracted/ball_by_ball.csv')
matches = pd.read_csv('data/extracted/matches.csv')

# Exclude super overs for phase baseline analysis
reg_bbb = bbb[bbb['innings'].isin([1, 2])].copy()

# Add phase
def get_phase(o):
    if o <= 6:
        return 'Powerplay (1-6)'
    elif o <= 15:
        return 'Middle (7-15)'
    else:
        return 'Death (16-20)'

reg_bbb['phase'] = reg_bbb['overid'].apply(get_phase)

# Legal ball flag
reg_bbb['is_legal'] = ~reg_bbb['extras_type'].isin(['wide', 'Overstep', 'other'])
reg_bbb['is_striker_ball'] = reg_bbb['extras_type'] != 'wide'

# Compute phase-level league averages
phase_stats = reg_bbb.groupby(['innings', 'phase']).agg(
    total_deliveries=('overid', 'count'),
    striker_balls=('is_striker_ball', 'sum'),
    legal_balls=('is_legal', 'sum'),
    runs_off_bat=('runs', 'sum'),
    dot_balls=('runs', lambda x: (x == 0).sum()),
    fours=('is_four', lambda x: (x == True).sum()),
    sixes=('is_six', lambda x: (x == True).sum()),
    wickets=('is_wicket', lambda x: (x == True).sum())
).reset_index()

phase_stats['strike_rate'] = phase_stats['runs_off_bat'] / phase_stats['striker_balls'] * 100
phase_stats['dot_pct'] = phase_stats['dot_balls'] / phase_stats['striker_balls'] * 100
phase_stats['boundary_pct'] = (phase_stats['fours'] + phase_stats['sixes']) / phase_stats['striker_balls'] * 100
phase_stats['wicket_pct'] = phase_stats['wickets'] / phase_stats['striker_balls'] * 100
phase_stats['rpo'] = phase_stats['runs_off_bat'] / (phase_stats['legal_balls'] / 6)

print("=== EMPIRICAL PHASE BASELINES (2022-2026 T20 & IPL) ===")
print(phase_stats[['innings', 'phase', 'legal_balls', 'strike_rate', 'rpo', 'dot_pct', 'boundary_pct', 'wicket_pct']].to_string(index=False))

# Wickets in hand distribution
print("\n=== WICKET HAZARD BY WICKETS IN HAND ===")
# Cumulative wickets lost in innings before delivery
reg_bbb['is_w_int'] = reg_bbb['is_wicket'].astype(int)
reg_bbb['w_lost_before'] = reg_bbb.groupby(['match_id', 'innings'])['is_w_int'].cumsum() - reg_bbb['is_w_int']
reg_bbb['w_in_hand'] = 10 - reg_bbb['w_lost_before']
w_stats = reg_bbb.groupby('w_in_hand').agg(
    legal_balls=('is_legal', 'sum'),
    runs=('runs', 'sum'),
    wickets=('is_w_int', 'sum')
).reset_index()
w_stats['sr'] = w_stats['runs'] / w_stats['legal_balls'] * 100
w_stats['w_pct'] = w_stats['wickets'] / w_stats['legal_balls'] * 100
print(w_stats.to_string(index=False))
