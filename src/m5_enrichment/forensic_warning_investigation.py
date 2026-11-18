"""
Forensic investigation script for the 9 warning matches and player crosswalk reconciliation.
"""

import zipfile
import json
import os
import pandas as pd

def run_forensic_investigation():
    mc = pd.read_csv('data/enriched/m5_match_coverage_audit.csv')
    mapping = pd.read_csv('data/extracted/competition_team_player_mapping.csv')
    p11 = pd.read_csv('data/extracted/playing_eleven.csv')

    mids = [13613, 14130, 14164, 21176, 32618, 37349, 37352, 46250, 50504]
    
    chunks = []
    for c in pd.read_csv('data/extracted/ball_by_ball.csv', chunksize=20000):
        sub = c[c['match_id'].isin(mids)]
        if len(sub) > 0:
            chunks.append(sub)
    bbb_warn = pd.concat(chunks, ignore_index=True)

    p_names = mapping.drop_duplicates('player_id').set_index('player_id')['player_name'].to_dict()

    ipl_zip = 'data/external/cricsheet/downloads/ipl_json.zip'
    t20i_zip = 'data/external/cricsheet/downloads/t20s_male_json.zip'
    z_ipl = zipfile.ZipFile(ipl_zip, 'r')
    z_t20i = zipfile.ZipFile(t20i_zip, 'r')

    for mid in mids:
        r = mc[mc['local_match_id'] == mid].iloc[0]
        archive = r['cricsheet_archive']
        cfile = r['cricsheet_file']
        z = z_ipl if archive == 'ipl_json.zip' else z_t20i
        d = json.loads(z.read(cfile).decode('utf-8'))
        
        local_m = bbb_warn[bbb_warn['match_id'] == mid].sort_values(['innings', 'innings_ball_num'])
        c_info = d.get('info', {})
        c_inns = d.get('innings', [])
        
        print('='*75)
        print('MATCH', mid, '| Date:', r['match_date'], '(Cric:', c_info.get('dates', []), ')')
        print('  Local:', r['home_team'], 'vs', r['away_team'], '|', r['competition_name'])
        print('  Cric :', c_info.get('teams'), '| Event:', c_info.get('event', {}).get('name'))
        print('  Local Result:', r['local_result'])
        print('  Cric Outcome:', c_info.get('outcome'))
        
        local_inn_groups = {inn: df for inn, df in local_m.groupby('innings')}
        max_inns = max(len(c_inns), max(local_inn_groups.keys(), default=0))
        
        for inn_idx in range(1, max_inns + 1):
            loc_df = local_inn_groups.get(inn_idx, pd.DataFrame())
            n_loc = len(loc_df)
            
            c_inn = c_inns[inn_idx - 1] if inn_idx <= len(c_inns) else {}
            c_dels = [deliv for o in c_inn.get('overs', []) for deliv in o.get('deliveries', [])]
            n_cric = len(c_dels)
            
            loc_runs = loc_df['runs'].sum() if n_loc > 0 else 0
            loc_extras = (loc_df['extras1_runs'].sum() + loc_df['extras_2_runs'].sum()) if n_loc > 0 else 0
            loc_wkts = loc_df['is_wicket'].sum() if n_loc > 0 else 0
            
            cric_runs_bat = sum(deliv.get('runs', {}).get('batter', 0) for deliv in c_dels)
            cric_extras = sum(deliv.get('runs', {}).get('extras', 0) for deliv in c_dels)
            cric_total = sum(deliv.get('runs', {}).get('total', 0) for deliv in c_dels)
            cric_wkts = sum(len(deliv.get('wickets', [])) for deliv in c_dels)
            
            print(f'  Inn {inn_idx} ({c_inn.get("team", "N/A")}): Loc balls={n_loc}, Cric balls={n_cric} | Loc runs={loc_runs}, Cric bat runs={cric_runs_bat}, Cric tot={cric_total} | Loc wkts={loc_wkts}, Cric wkts={cric_wkts}')

    z_ipl.close()
    z_t20i.close()

if __name__ == '__main__':
    run_forensic_investigation()
