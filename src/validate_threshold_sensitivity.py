import pandas as pd
import numpy as np

# Load ball by ball and players
bbb = pd.read_csv('data/extracted/ball_by_ball.csv')

# Batting participation and metrics
# Legal striker balls
bbb['is_striker_ball'] = bbb['extras_type'] != 'wide'
bbb['is_legal'] = ~bbb['extras_type'].isin(['wide', 'Overstep', 'other'])

# Batter match-level stats
bat_m = bbb.groupby(['striker_id', 'striker_name', 'match_id', 'innings']).agg(
    balls=('is_striker_ball', 'sum'),
    runs=('runs', 'sum'),
    batting_order=('batting_order', 'min')
).reset_index()

# Batter career aggregation
bat_career = bat_m.groupby(['striker_id', 'striker_name']).agg(
    innings=('match_id', 'count'),
    total_balls=('balls', 'sum'),
    total_runs=('runs', 'sum'),
    median_batting_order=('batting_order', 'median')
).reset_index()

# Classify candidate role
def get_bat_role(order):
    if order <= 3.0:
        return 'Top Order (1-3)'
    elif order <= 5.0:
        return 'Middle Order (4-5)'
    elif order <= 8.0:
        return 'Finishers (6-8)'
    else:
        return 'Tail (9-11)'

bat_career['role'] = bat_career['median_batting_order'].apply(get_bat_role)

# Bowler career aggregation
bowl_m = bbb.groupby(['bowler_id', 'bowler_name', 'match_id', 'innings']).agg(
    legal_balls=('is_legal', 'sum'),
    runs_conceded=('runs', 'sum'), # raw proxy for exposure
    wickets=('is_wicket', 'sum')
).reset_index()

bowl_career = bowl_m.groupby(['bowler_id', 'bowler_name']).agg(
    innings=('match_id', 'count'),
    total_legal_balls=('legal_balls', 'sum'),
    total_wickets=('wickets', 'sum')
).reset_index()

# Bowler phase exposure
bbb['over'] = bbb['overid']
def get_bowl_phase(o):
    if o <= 6:
        return 'Powerplay'
    elif o <= 15:
        return 'Middle'
    else:
        return 'Death'

bbb['phase'] = bbb['over'].apply(get_bowl_phase)
bowl_phase_exp = bbb[bbb['is_legal']].groupby(['bowler_id', 'phase']).size().unstack(fill_value=0)
bowl_phase_exp['total'] = bowl_phase_exp.sum(axis=1)
for p in ['Powerplay', 'Middle', 'Death']:
    if p in bowl_phase_exp.columns:
        bowl_phase_exp[p + '_pct'] = bowl_phase_exp[p] / bowl_phase_exp['total']
    else:
        bowl_phase_exp[p + '_pct'] = 0.0

def get_bowl_role(row):
    if row.get('Powerplay_pct', 0) >= 0.40:
        return 'Powerplay Specialist'
    elif row.get('Death_pct', 0) >= 0.30:
        return 'Death Specialist'
    else:
        return 'Middle Enforcer'

bowl_phase_exp['role'] = bowl_phase_exp.apply(get_bowl_role, axis=1)
bowl_career = bowl_career.merge(bowl_phase_exp[['role']], on='bowler_id', how='left')

print("=== TOTAL POPULATION ===")
print("Total unique batters:", len(bat_career))
print("Total unique bowlers:", len(bowl_career))

# Batting Grid
print("\n=== BATTER ELIGIBILITY MATRIX ===")
print("Innings | Total Balls | Eligible Batters | % Pop | Top Order | Middle Order | Finishers | Tail")
for inn in [8, 10, 12, 15]:
    for b in [80, 100, 120, 150]:
        sub = bat_career[(bat_career['innings'] >= inn) & (bat_career['total_balls'] >= b)]
        roles = sub['role'].value_counts()
        top = roles.get('Top Order (1-3)', 0)
        mid = roles.get('Middle Order (4-5)', 0)
        fin = roles.get('Finishers (6-8)', 0)
        tail = roles.get('Tail (9-11)', 0)
        print(f"{inn:7d} | {b:11d} | {len(sub):16d} | {len(sub)/len(bat_career)*100:5.1f}% | {top:9d} | {mid:12d} | {fin:9d} | {tail:4d}")

# Bowling Grid
print("\n=== BOWLER ELIGIBILITY MATRIX ===")
print("Innings | Legal Balls | (Overs) | Eligible Bowlers | % Pop | Powerplay | Middle | Death")
for inn in [8, 10, 12, 15]:
    for b in [96, 120, 144, 180]:
        sub = bowl_career[(bowl_career['innings'] >= inn) & (bowl_career['total_legal_balls'] >= b)]
        roles = sub['role'].value_counts()
        pp = roles.get('Powerplay Specialist', 0)
        mid = roles.get('Middle Enforcer', 0)
        dth = roles.get('Death Specialist', 0)
        print(f"{inn:7d} | {b:11d} | ({b//6:2d} ov) | {len(sub):16d} | {len(sub)/len(bowl_career)*100:5.1f}% | {pp:9d} | {mid:6d} | {dth:5d}")

