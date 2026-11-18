"""
RR ScoutIQ - Match 14130 & 14164 Conditional Sequence Alignment Investigation
Forensically compares local and Cricsheet delivery sequences ball-by-ball.
"""

import json
import zipfile
import pandas as pd
from typing import Dict, Any, List

def load_local_deliveries(match_id: int) -> pd.DataFrame:
    df = pd.read_csv('data/extracted/ball_by_ball.csv')
    sub = df[df['match_id'] == match_id].sort_values(by=['innings', 'overid', 'over_ball_num']).copy()
    return sub

def load_cricsheet_deliveries(zip_path: str, json_file: str) -> List[Dict[str, Any]]:
    with zipfile.ZipFile(zip_path, 'r') as z:
        with z.open(json_file) as f:
            data = json.load(f)
    
    deliveries = []
    for inn_idx, inn in enumerate(data.get('innings', []), start=1):
        team = inn.get('team')
        overs = inn.get('overs', [])
        for over in overs:
            over_num = over.get('over')  # 0-indexed over number (0 = 1st over)
            for ball_idx, deliv in enumerate(over.get('deliveries', []), start=1):
                deliv_record = {
                    'innings': inn_idx,
                    'team': team,
                    'over': over_num,
                    'over_num_1based': over_num + 1,
                    'ball_idx_in_over': ball_idx,
                    'batter': deliv.get('batter'),
                    'bowler': deliv.get('bowler'),
                    'non_striker': deliv.get('non_striker'),
                    'runs_batter': deliv.get('runs', {}).get('batter', 0),
                    'runs_extras': deliv.get('runs', {}).get('extras', 0),
                    'runs_total': deliv.get('runs', {}).get('total', 0),
                    'extras': deliv.get('extras', {}),
                    'wickets': deliv.get('wickets', [])
                }
                deliveries.append(deliv_record)
    return deliveries

def investigate_match(match_id: int, cric_file: str):
    print("=" * 80)
    print(f"INVESTIGATING MATCH {match_id} (Cricsheet: {cric_file})")
    print("=" * 80)
    
    local_df = load_local_deliveries(match_id)
    cric_delivs = load_cricsheet_deliveries('data/external/cricsheet/downloads/ipl_json.zip', cric_file)
    cric_df = pd.DataFrame(cric_delivs)
    
    for inn in sorted(local_df['innings'].unique()):
        loc_inn = local_df[local_df['innings'] == inn].reset_index(drop=True)
        crk_inn = cric_df[cric_df['innings'] == inn].reset_index(drop=True)
        
        print(f"\n--- INNINGS {inn} ---")
        print(f"Local deliveries count: {len(loc_inn)}")
        print(f"Cricsheet deliveries count: {len(crk_inn)}")
        print(f"Delta: {len(loc_inn) - len(crk_inn)}")
        
        loc_overs = loc_inn.groupby('overid').size()
        crk_overs = crk_inn.groupby('over_num_1based').size()
        
        diff_overs = []
        max_over = max(loc_inn['overid'].max(), crk_inn['over_num_1based'].max())
        for o in range(1, max_over + 1):
            l_cnt = loc_overs.get(o, 0)
            c_cnt = crk_overs.get(o, 0)
            if l_cnt != c_cnt:
                print(f"Over {o} MISMATCH: Local has {l_cnt} balls, Cricsheet has {c_cnt} balls.")
                diff_overs.append(o)
                
        # Detailed inspection of differing overs and adjacent overs
        for o in diff_overs:
            print(f"\nDetailed look at Over {o}:")
            l_o = loc_inn[loc_inn['overid'] == o]
            c_o = crk_inn[crk_inn['over_num_1based'] == o]
            
            print("Local over deliveries:")
            for _, r in l_o.iterrows():
                extras_sum = (r['extras1_runs'] or 0) + (r['extras_2_runs'] or 0)
                print(f"  Ball {r['over_ball_num']} (innings_ball {r['innings_ball_num']}): "
                      f"striker={r['striker_name']} ({r['striker_id']}), bowler={r['bowler_name']} ({r['bowler_id']}), "
                      f"runs={r['runs']}, extras={r['extras_type']}:{extras_sum}, "
                      f"wicket={r['is_wicket']} ({r['dismissal_type']})")
                      
            print("Cricsheet over deliveries:")
            for _, r in c_o.iterrows():
                w_str = f"Wicket: {r['wickets']}" if r['wickets'] else "No wicket"
                print(f"  Ball {r['ball_idx_in_over']}: "
                      f"striker={r['batter']}, bowler={r['bowler']}, "
                      f"runs_batter={r['runs_batter']}, extras={r['extras']}, total={r['runs_total']}, "
                      f"{w_str}")

if __name__ == '__main__':
    investigate_match(14130, '1304083.json')
    investigate_match(14164, '1304116.json')
