"""
Forensic inspection of Matches 13613 and 21176 across local source, audit crosswalks, and Cricsheet.
"""

import json
import zipfile
import pandas as pd

matches = pd.read_csv('data/extracted/matches.csv')
comps = pd.read_csv('data/extracted/competitions.csv')
audit = pd.read_csv('data/enriched/m5_match_coverage_audit.csv')
bbb = pd.read_csv('data/extracted/ball_by_ball.csv')
m_df = matches.merge(comps, on='comp_id')

for mid in [13613, 21176]:
    print("=" * 80)
    print(f"MATCH ID: {mid}")
    print("=" * 80)
    loc_m = m_df[m_df['match_id'] == mid].iloc[0]
    aud_m = audit[audit['local_match_id'] == mid].iloc[0]
    loc_bbb_m = bbb[bbb['match_id'] == mid]
    
    print("LOCAL RECORD (matches.csv):")
    print(f"  Match Date: {loc_m['match_date']}")
    print(f"  Competition: {loc_m['comp_name']} (ID: {loc_m['comp_id']})")
    print(f"  Home Team: {loc_m['home_team']} (ID: {loc_m['home_team_id']})")
    print(f"  Away Team: {loc_m['away_team']} (ID: {loc_m['away_team_id']})")
    print(f"  Result: {loc_m['result']}")
    print(f"  Win Team ID: {loc_m['win_team_id']}")
    print(f"  Local Delivery Count: {len(loc_bbb_m)}")
    for inn in sorted(loc_bbb_m['innings'].unique()):
        sub_inn = loc_bbb_m[loc_bbb_m['innings'] == inn]
        print(f"    Inn {inn}: Deliveries={len(sub_inn)}, Total Runs={sub_inn['runs'].sum()}")
    
    print("\nAUDIT CSV RECORD (m5_match_coverage_audit.csv):")
    print(f"  Cricsheet Match ID: {aud_m['cricsheet_match_id']}")
    print(f"  Cricsheet Archive: {aud_m['cricsheet_archive']}")
    print(f"  Cricsheet File: {aud_m['cricsheet_file']}")
    print(f"  Warning Disposition: {aud_m['warning_disposition']}")
    print(f"  Local Delivery Count: {aud_m['local_delivery_count']}")
    print(f"  Cricsheet Delivery Count: {aud_m['cricsheet_delivery_count']}")
    print(f"  Provenance Notes: {aud_m['provenance_notes']}")

    arch = aud_m['cricsheet_archive']
    fname = aud_m['cricsheet_file']
    zip_path = f"data/external/cricsheet/downloads/{arch}"
    with zipfile.ZipFile(zip_path, 'r') as z:
        with z.open(fname) as f:
            cdata = json.load(f)
            
    cinfo = cdata.get('info', {})
    print("\nCRICSHEET JSON RECORD:")
    print(f"  Dates: {cinfo.get('dates')}")
    print(f"  Event: {cinfo.get('event', {}).get('name')}")
    print(f"  Teams: {cinfo.get('teams')}")
    print(f"  Outcome: {cinfo.get('outcome')}")
    print(f"  Innings Count: {len(cdata.get('innings', []))}")
    for inn_idx, inn_obj in enumerate(cdata.get('innings', []), start=1):
        team = inn_obj.get('team')
        is_so = inn_obj.get('super_over', False)
        deliv_cnt = sum(len(o.get('deliveries', [])) for o in inn_obj.get('overs', []))
        total_runs = sum(sum(d.get('runs', {}).get('total', 0) for d in o.get('deliveries', [])) for o in inn_obj.get('overs', []))
        print(f"    Inn {inn_idx}: Team={team}, SuperOver={is_so}, Deliveries={deliv_cnt}, TotalRuns={total_runs}")
