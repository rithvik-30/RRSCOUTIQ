"""
Forensic investigation of Player IDs 6645 and 29075:
- Local appearances and match contexts
- Cricsheet scorecard matching
- Collision checks across local dataset and Cricsheet people registry
"""

import os
import json
import zipfile
import pandas as pd

ctpm = pd.read_csv('data/extracted/competition_team_player_mapping.csv')
p11 = pd.read_csv('data/extracted/playing_eleven.csv')
matches = pd.read_csv('data/extracted/matches.csv')
teams = pd.read_csv('data/extracted/teams.csv')
competitions = pd.read_csv('data/extracted/competitions.csv')

print("=" * 80)
print("1. INVESTIGATING PLAYER ID 6645 (Mohammad Sheikh)")
print("=" * 80)
p6645_ctpm = ctpm[ctpm['player_id'] == 6645]
print("CTPM entries for 6645:")
print(p6645_ctpm[['comp_id', 'comp_name', 'team_id', 'team_name', 'player_id', 'player_name']])

# Matches played
p6645_matches = p11[(p11['player_id'] == 6645) & (p11['is_played'] == 1)]
print(f"\nMatches played by 6645: {len(p6645_matches)}")
m_details_6645 = p6645_matches.merge(matches, left_on='match_id', right_on='match_id')
print(m_details_6645[['match_id', 'match_date', 'comp_id', 'home_team', 'away_team', 'batting_order']])

# Check Cricsheet match files for these matches
# Let's see mapping in m5_match_coverage_audit.csv
audit_df = pd.read_csv('data/enriched/m5_match_coverage_audit.csv')
for mid in m_details_6645['match_id']:
    row = audit_df[audit_df['local_match_id'] == mid]
    if not row.empty and pd.notna(row.iloc[0]['cricsheet_archive']):
        cric_file = row.iloc[0]['cricsheet_file']
        cric_arch = row.iloc[0]['cricsheet_archive']
        print(f"\nLocal match {mid} -> Cricsheet {cric_file} in {cric_arch}")
        # Look inside cricsheet json
        zip_path = os.path.join('data/external/cricsheet/downloads', str(cric_arch))
        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as z:
                with z.open(cric_file) as f:
                    cdata = json.load(f)
            # Find players in info
            players = cdata.get('info', {}).get('players', {})
            registry = cdata.get('info', {}).get('registry', {}).get('people', {})
            print(f"  Teams: {list(players.keys())}")
            for t, plist in players.items():
                print(f"  Team {t} players: {plist}")
            print(f"  Registry entries matching 'Naim' or 'Sheikh':")
            for name, pid in registry.items():
                if any(x in name.lower() for x in ['naim', 'sheikh']):
                    print(f"    Registry: {name} -> {pid}")

print("\n" + "=" * 80)
print("2. INVESTIGATING PLAYER ID 29075 (Aadil Ansari)")
print("=" * 80)
p29075_ctpm = ctpm[ctpm['player_id'] == 29075]
print("CTPM entries for 29075:")
print(p29075_ctpm[['comp_id', 'comp_name', 'team_id', 'team_name', 'player_id', 'player_name']])

p29075_matches = p11[(p11['player_id'] == 29075) & (p11['is_played'] == 1)]
print(f"\nMatches played by 29075: {len(p29075_matches)}")
m_details_29075 = p29075_matches.merge(matches, left_on='match_id', right_on='match_id')
print(m_details_29075[['match_id', 'match_date', 'comp_id', 'home_team', 'away_team', 'batting_order']])

for mid in m_details_29075['match_id']:
    row = audit_df[audit_df['local_match_id'] == mid]
    if not row.empty and pd.notna(row.iloc[0]['cricsheet_archive']):
        cric_file = row.iloc[0]['cricsheet_file']
        cric_arch = row.iloc[0]['cricsheet_archive']
        print(f"\nLocal match {mid} -> Cricsheet {cric_file} in {cric_arch}")
        zip_path = os.path.join('data/external/cricsheet/downloads', str(cric_arch))
        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as z:
                with z.open(cric_file) as f:
                    cdata = json.load(f)
            players = cdata.get('info', {}).get('players', {})
            registry = cdata.get('info', {}).get('registry', {}).get('people', {})
            print(f"  Teams: {list(players.keys())}")
            for t, plist in players.items():
                print(f"  Team {t} players: {plist}")
            print(f"  Registry entries matching 'Aadil' or 'Ansari' or 'Alam':")
            for name, pid in registry.items():
                if any(x in name.lower() for x in ['aadil', 'ansari', 'alam']):
                    print(f"    Registry: {name} -> {pid}")

print("\n" + "=" * 80)
print("3. COLLISION CHECKS IN LOCAL DATASET")
print("=" * 80)
# Check for any other players with similar names
sheikh_players = ctpm[ctpm['player_name'].str.lower().str.contains('sheikh|naim', na=False)]
print("Players in CTPM with 'sheikh' or 'naim':")
print(sheikh_players[['player_id', 'player_name']].drop_duplicates())

ansari_players = ctpm[ctpm['player_name'].str.lower().str.contains('aadil|ansari|alam', na=False)]
print("\nPlayers in CTPM with 'aadil', 'ansari', or 'alam':")
print(ansari_players[['player_id', 'player_name']].drop_duplicates())
