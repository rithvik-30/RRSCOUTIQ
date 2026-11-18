import pandas as pd
import numpy as np

bbb = pd.read_csv('data/extracted/ball_by_ball.csv')

# Batting summary
bat_inn = bbb.groupby(['striker_id', 'match_id', 'innings']).agg(
    runs=('runs', 'sum'),
    balls=('extras_type', lambda x: (x != 'wide').sum()),
    dismissed=('is_wicket', 'max')
).reset_index()

bat_summary = bat_inn.groupby('striker_id').agg(
    innings=('match_id', 'count'),
    total_runs=('runs', 'sum'),
    total_balls=('balls', 'sum')
).reset_index()

bat_summary['strike_rate'] = np.where(bat_summary['total_balls'] > 0, bat_summary['total_runs'] / bat_summary['total_balls'] * 100, np.nan)

# Bowling summary
bowl_inn = bbb.groupby(['bowler_id', 'match_id', 'innings']).agg(
    legal_balls=('extras_type', lambda x: (~x.isin(['wide', 'Overstep', 'other'])).sum()),
    wickets=('is_wicket', 'sum')
).reset_index()

bowl_summary = bowl_inn.groupby('bowler_id').agg(
    innings=('match_id', 'count'),
    total_legal_balls=('legal_balls', 'sum'),
    total_wickets=('wickets', 'sum')
).reset_index()

print("=== BATTING THRESHOLDS (Total: %d batters) ===" % len(bat_summary))
for inn_t in [1, 5, 10, 15, 20]:
    sub = bat_summary[bat_summary['innings'] >= inn_t]
    sr_mean = sub['strike_rate'].mean()
    sr_std = sub['strike_rate'].std()
    print("Innings >= %2d: %3d batters (%5.1f%%) | median balls: %4d | mean SR: %5.1f | std SR: %5.1f" % 
          (inn_t, len(sub), len(sub)/len(bat_summary)*100, sub['total_balls'].median(), sr_mean, sr_std))

print("\n=== BALLS FACED THRESHOLDS ===")
for b_t in [20, 50, 100, 150, 200]:
    sub = bat_summary[bat_summary['total_balls'] >= b_t]
    sr_mean = sub['strike_rate'].mean()
    sr_std = sub['strike_rate'].std()
    print("Balls >= %3d: %3d batters (%5.1f%%) | median inn: %3d | mean SR: %5.1f | std SR: %5.1f" % 
          (b_t, len(sub), len(sub)/len(bat_summary)*100, sub['innings'].median(), sr_mean, sr_std))

print("\n=== BOWLING THRESHOLDS (Total: %d bowlers) ===" % len(bowl_summary))
for inn_t in [1, 5, 10, 15, 20]:
    sub = bowl_summary[bowl_summary['innings'] >= inn_t]
    print("Innings >= %2d: %3d bowlers (%5.1f%%) | median balls: %4d" % 
          (inn_t, len(sub), len(sub)/len(bowl_summary)*100, sub['total_legal_balls'].median()))

print("\n=== LEGAL BALLS BOWLED THRESHOLDS ===")
for b_t in [30, 60, 120, 180, 240]:
    sub = bowl_summary[bowl_summary['total_legal_balls'] >= b_t]
    print("Balls >= %3d (%2d overs): %3d bowlers (%5.1f%%) | median inn: %3d" % 
          (b_t, b_t//6, len(sub), len(sub)/len(bowl_summary)*100, sub['innings'].median()))

