"""
RR ScoutIQ - Milestone M2.4 External Source Verification
Script: src/external_source_verification.py

Comprehensive reproducible audit and verification of Cricsheet external data:
1. License and provenance capture.
2. 9-match scorecard reconciliation against Cricsheet ball-by-ball records.
3. Player and team identity crosswalk validation with two-pass initial disambiguation.
4. Batter-level and bowler-level statistics reconciliation.
5. Legal delivery (Wide and Overstep/No-ball exclusion) and bowler-conceded runs rule validation.
6. Overall dataset coverage quantification (accounting for team renames, IST/local timezone date shifts, and editorial policies).
"""

import os
import zipfile
import json
import csv
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import pandas as pd

# Paths
BASE_DIR = os.path.abspath(".")
DATA_EXTRACTED = os.path.join(BASE_DIR, "data", "extracted")
CRICSHEET_DIR = os.path.join(BASE_DIR, "data", "external", "cricsheet", "downloads")
REPORTS_DIR = os.path.join(BASE_DIR, "audit_reports", "performance_metrics")
os.makedirs(REPORTS_DIR, exist_ok=True)

IPL_ZIP = os.path.join(CRICSHEET_DIR, "ipl_json.zip")
T20I_ZIP = os.path.join(CRICSHEET_DIR, "t20s_male_json.zip")
PEOPLE_CSV = os.path.join(CRICSHEET_DIR, "people.csv")
NAMES_CSV = os.path.join(CRICSHEET_DIR, "names.csv")

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

TEAM_ALIASES = {
    "Royal Challengers Bengaluru": "Royal Challengers Bangalore",
    "Punjab Kings": "Kings XI Punjab",
    "Delhi Capitals": "Delhi Daredevils"
}

def normalize_team(name):
    clean = str(name).strip()
    return TEAM_ALIASES.get(clean, clean)

def run_verification():
    print("=== RR ScoutIQ - M2.4 External Source Verification (Refined) ===")
    
    # 1. Verify files exist and check hashes
    required_files = [IPL_ZIP, T20I_ZIP, PEOPLE_CSV, NAMES_CSV]
    file_hashes = {}
    for rf in required_files:
        if not os.path.exists(rf):
            raise FileNotFoundError(f"Missing required file: {rf}")
        h = sha256_file(rf)
        file_hashes[os.path.basename(rf)] = h

    # Load local data
    print("Loading local dataset...")
    matches_df = pd.read_csv(os.path.join(DATA_EXTRACTED, "matches.csv"))
    comps_df = pd.read_csv(os.path.join(DATA_EXTRACTED, "competitions.csv"))
    teams_df = pd.read_csv(os.path.join(DATA_EXTRACTED, "teams.csv"))
    players_df = pd.read_csv(os.path.join(DATA_EXTRACTED, "competition_team_player_mapping.csv"))
    p11_df = pd.read_csv(os.path.join(DATA_EXTRACTED, "playing_eleven.csv"))
    bbb_df = pd.read_csv(os.path.join(DATA_EXTRACTED, "ball_by_ball.csv"))
    
    merged_matches = matches_df.merge(comps_df, on="comp_id")

    # 2. Define the 9 target reconciliation matches
    targets = [
        {"match_id": 14113, "date": "2022-04-10", "teams": ["Rajasthan Royals", "Lucknow Super Giants"], "comp": "IPL 2022", "format": "T20", "type": "ipl"},
        {"match_id": 14094, "date": "2022-03-26", "teams": ["Chennai Super Kings", "Kolkata Knight Riders"], "comp": "IPL 2022", "format": "T20", "type": "ipl"},
        {"match_id": 20181, "date": "2023-03-31", "teams": ["Gujarat Titans", "Chennai Super Kings"], "comp": "IPL 2023", "format": "T20", "type": "ipl"},
        {"match_id": 30058, "date": "2024-03-23", "teams": ["Kolkata Knight Riders", "Sunrisers Hyderabad"], "comp": "IPL 2024", "format": "T20", "type": "ipl"},
        {"match_id": 40725, "date": "2025-04-16", "teams": ["Delhi Capitals", "Rajasthan Royals"], "comp": "IPL 2025", "format": "T20", "type": "ipl"},
        {"match_id": 13513, "date": "2022-01-26", "teams": ["West Indies", "England"], "comp": "England in West Indies T20I Series 2022", "format": "T20I", "type": "t20i"},
        {"match_id": 28962, "date": "2024-01-17", "teams": ["India", "Afghanistan"], "comp": "Afghanistan in India T20I Series 2024", "format": "T20I", "type": "t20i"},
        {"match_id": 34429, "date": "2024-07-30", "teams": ["Sri Lanka", "India"], "comp": "India in Sri Lanka T20I Series 2024", "format": "T20I", "type": "t20i"},
        {"match_id": 40037, "date": "2025-01-25", "teams": ["India", "England"], "comp": "England in India T20I Series 2025", "format": "T20I", "type": "t20i"}
    ]

    # Pre-index Cricsheet match files by date and teams
    print("Indexing Cricsheet matches...")
    ipl_index = []
    with zipfile.ZipFile(IPL_ZIP, "r") as z:
        for fname in z.namelist():
            if fname.endswith(".json"):
                data = json.loads(z.read(fname).decode("utf-8"))
                info = data.get("info", {})
                ipl_index.append({
                    "file": fname,
                    "dates": info.get("dates", []),
                    "teams": info.get("teams", []),
                    "normalized_teams": set(normalize_team(t) for t in info.get("teams", [])),
                    "season": str(info.get("season", "")),
                    "event": info.get("event", {}).get("name", ""),
                    "raw_data": data
                })

    t20i_index = []
    with zipfile.ZipFile(T20I_ZIP, "r") as z:
        for fname in z.namelist():
            if fname.endswith(".json"):
                data = json.loads(z.read(fname).decode("utf-8"))
                info = data.get("info", {})
                t20i_index.append({
                    "file": fname,
                    "dates": info.get("dates", []),
                    "teams": info.get("teams", []),
                    "normalized_teams": set(normalize_team(t) for t in info.get("teams", [])),
                    "season": str(info.get("season", "")),
                    "event": info.get("event", {}).get("name", ""),
                    "raw_data": data
                })

    # 3. Match search and reconciliation for the 9 targets
    print("\nReconciling 9 sample matches with refined two-pass player resolution...")
    match_reconciliations = []
    innings_reconciliations = []
    batter_reconciliations = []
    bowler_reconciliations = []
    player_crosswalk_records = []

    for target in targets:
        m_id = target["match_id"]
        t_date = target["date"]
        t_teams = set(normalize_team(t) for t in target["teams"])
        t_type = target["type"]
        
        index_pool = ipl_index if t_type == "ipl" else t20i_index
        candidates = [m for m in index_pool if t_date in m["dates"] and t_teams.issubset(m["normalized_teams"])]
        
        if not candidates:
            # Check +/- 1 day for timezone difference
            dt = datetime.strptime(t_date, "%Y-%m-%d")
            adjacent_dates = [(dt - timedelta(days=1)).strftime("%Y-%m-%d"), (dt + timedelta(days=1)).strftime("%Y-%m-%d")]
            candidates = [m for m in index_pool if any(ad in m["dates"] for ad in adjacent_dates) and t_teams.issubset(m["normalized_teams"])]

        if not candidates:
            status = "UNMATCHED"
            reason = "Withheld by Cricsheet policy (Afghanistan men's match)" if "Afghanistan" in target["teams"] else "Not found in Cricsheet archive"
            match_reconciliations.append({
                "local_match_id": m_id,
                "cricsheet_file": "NONE",
                "match_date": t_date,
                "teams": " vs ".join(target["teams"]),
                "format": target["format"],
                "match_status": status,
                "reason": reason
            })
            continue

        c_match = candidates[0]
        c_file = c_match["file"]
        c_data = c_match["raw_data"]
        c_info = c_data["info"]
        
        match_reconciliations.append({
            "local_match_id": m_id,
            "cricsheet_file": c_file,
            "match_date": t_date,
            "teams": " vs ".join(target["teams"]),
            "format": target["format"],
            "match_status": "EXACT_MATCH",
            "reason": f"Matched on date {t_date} and teams {target['teams']}"
        })

        # Local match deliveries and lineups
        m_local_bbb = bbb_df[bbb_df["match_id"] == m_id]
        m_local_p11 = p11_df[p11_df["match_id"] == m_id]
        local_match_players = m_local_p11.merge(players_df, on=["team_id", "player_id"], how="left").drop_duplicates(["team_id", "player_id"])
        
        # Player crosswalk within match using two-pass bipartite matching
        c_players_by_team = c_info.get("players", {})
        c_registry = c_info.get("registry", {}).get("people", {})
        
        local_name_to_cric = {}
        
        for c_team_name, c_plist in c_players_by_team.items():
            avail_cric = list(c_plist)
            avail_local = local_match_players.copy()
            
            # Pass 1: Exact string match
            for _, lp in avail_local.iterrows():
                lp_name = str(lp["player_name"]).strip()
                for cp in list(avail_cric):
                    if cp.strip().lower() == lp_name.lower():
                        cid = c_registry.get(cp, "")
                        local_name_to_cric[lp_name] = {"cric_name": cp, "cric_id": cid, "local_id": lp["player_id"], "team_id": lp["team_id"]}
                        player_crosswalk_records.append({
                            "local_match_id": m_id, "local_player_id": lp["player_id"], "local_player_name": lp_name,
                            "cricsheet_player_id": cid, "cricsheet_player_name": cp, "match_type": "EXACT"
                        })
                        avail_cric.remove(cp)
                        break

            # Pass 2: Unique surname within remaining
            for _, lp in avail_local.iterrows():
                lp_name = str(lp["player_name"]).strip()
                if lp_name in local_name_to_cric:
                    continue
                lp_surname = lp_name.split()[-1].lower()
                surname_cands = [cp for cp in avail_cric if cp.strip().split()[-1].lower() == lp_surname]
                if len(surname_cands) == 1:
                    cp = surname_cands[0]
                    cid = c_registry.get(cp, "")
                    local_name_to_cric[lp_name] = {"cric_name": cp, "cric_id": cid, "local_id": lp["player_id"], "team_id": lp["team_id"]}
                    player_crosswalk_records.append({
                        "local_match_id": m_id, "local_player_id": lp["player_id"], "local_player_name": lp_name,
                        "cricsheet_player_id": cid, "cricsheet_player_name": cp, "match_type": "SURNAME_UNIQUE"
                    })
                    avail_cric.remove(cp)

            # Pass 3: Initial disambiguation for duplicate surnames
            for _, lp in avail_local.iterrows():
                lp_name = str(lp["player_name"]).strip()
                if lp_name in local_name_to_cric:
                    continue
                lp_parts = lp_name.split()
                lp_initial = lp_parts[0][0].lower()
                lp_surname = lp_parts[-1].lower()
                
                surname_cands = [cp for cp in avail_cric if cp.strip().split()[-1].lower() == lp_surname]
                for cp in surname_cands:
                    cp_initials = [part[0].lower() for part in cp.strip().split()[:-1]]
                    if lp_initial in cp_initials or (len(cp.split()[0]) > 1 and cp.split()[0].lower() == lp_parts[0].lower()):
                        cid = c_registry.get(cp, "")
                        local_name_to_cric[lp_name] = {"cric_name": cp, "cric_id": cid, "local_id": lp["player_id"], "team_id": lp["team_id"]}
                        player_crosswalk_records.append({
                            "local_match_id": m_id, "local_player_id": lp["player_id"], "local_player_name": lp_name,
                            "cricsheet_player_id": cid, "cricsheet_player_name": cp, "match_type": "DISAMBIGUATED_INITIAL"
                        })
                        avail_cric.remove(cp)
                        break

        # Process each innings in Cricsheet
        for inn_idx, c_inn in enumerate(c_data.get("innings", []), start=1):
            c_team = c_inn["team"]
            local_inn_bbb = m_local_bbb[m_local_bbb["innings"] == inn_idx]
            
            c_team_total = 0
            c_team_extras = 0
            c_team_wickets = 0
            c_extras_breakdown = defaultdict(int)
            c_batter_stats = defaultdict(lambda: {"runs": 0, "balls_faced": 0, "fours": 0, "sixes": 0, "non_boundary_fours": 0, "dismissal": None})
            c_bowler_stats = defaultdict(lambda: {"legal_balls": 0, "total_balls": 0, "runs_conceded": 0, "wickets": 0, "wides": 0, "noballs": 0})
            
            c_dels = []
            for over_data in c_inn.get("overs", []):
                for d in over_data.get("deliveries", []):
                    c_dels.append(d)
                    batter = d["batter"]
                    bowler = d["bowler"]
                    runs = d["runs"]
                    b_runs = runs["batter"]
                    e_runs = runs["extras"]
                    t_runs = runs["total"]
                    extras = d.get("extras", {})
                    
                    is_wide = "wides" in extras
                    is_noball = "noballs" in extras
                    
                    if not is_wide:
                        c_batter_stats[batter]["balls_faced"] += 1
                    c_batter_stats[batter]["runs"] += b_runs
                    if b_runs == 4:
                        if runs.get("non_boundary", False):
                            c_batter_stats[batter]["non_boundary_fours"] += 1
                        else:
                            c_batter_stats[batter]["fours"] += 1
                    elif b_runs == 6:
                        c_batter_stats[batter]["sixes"] += 1
                        
                    c_bowler_stats[bowler]["total_balls"] += 1
                    if not is_wide and not is_noball:
                        c_bowler_stats[bowler]["legal_balls"] += 1
                    
                    bowler_debit = b_runs
                    if is_wide:
                        bowler_debit += extras["wides"]
                        c_bowler_stats[bowler]["wides"] += extras["wides"]
                    if is_noball:
                        bowler_debit += extras["noballs"]
                        c_bowler_stats[bowler]["noballs"] += extras["noballs"]
                    c_bowler_stats[bowler]["runs_conceded"] += bowler_debit
                    
                    c_team_total += t_runs
                    c_team_extras += e_runs
                    for ek, ev in extras.items():
                        c_extras_breakdown[ek] += ev
                        
                    if "wickets" in d:
                        for w in d["wickets"]:
                            kind = w["kind"]
                            p_out = w["player_out"]
                            c_batter_stats[p_out]["dismissal"] = kind
                            # Only true dismissals count as team wickets (retired hurt is not out)
                            if kind != "retired hurt":
                                c_team_wickets += 1
                            if kind in ["bowled", "caught", "lbw", "stumped", "hit wicket", "caught and bowled"]:
                                c_bowler_stats[bowler]["wickets"] += 1

            local_deliveries_count = len(local_inn_bbb)
            local_runs_sum = int(local_inn_bbb["runs"].sum()) if local_deliveries_count > 0 else 0
            local_wickets_sum = int(local_inn_bbb["is_wicket"].sum()) if local_deliveries_count > 0 else 0
            
            if local_deliveries_count == 0:
                inn_status = "LOCAL_MISSING_SCOPE"
                discrepancy = "Super Over innings not present in local ball_by_ball.csv"
            else:
                inn_status = "EXACT_RECONCILED"
                discrepancy = ""
                cric_batter_sum = sum(b["runs"] for b in c_batter_stats.values())
                if local_runs_sum != cric_batter_sum:
                    inn_status = "RUNS_MISMATCH"
                    discrepancy = f"Local runs {local_runs_sum} != Cricsheet batter runs {cric_batter_sum}"
                if local_wickets_sum != c_team_wickets:
                    inn_status = "WICKETS_MISMATCH"
                    discrepancy += f"; Local wickets {local_wickets_sum} != Cricsheet wickets {c_team_wickets}"

            innings_reconciliations.append({
                "local_match_id": m_id, "cricsheet_file": c_file, "innings": inn_idx, "batting_team": c_team,
                "local_deliveries": local_deliveries_count, "cricsheet_deliveries": len(c_dels),
                "local_runs_sum": local_runs_sum, "cricsheet_batter_runs_sum": sum(b["runs"] for b in c_batter_stats.values()),
                "cricsheet_extras_total": c_team_extras, "cricsheet_team_total": c_team_total,
                "local_is_wicket_count": local_wickets_sum, "cricsheet_team_wickets": c_team_wickets,
                "cricsheet_legal_overs": f"{sum(b['legal_balls'] for b in c_bowler_stats.values())//6}.{sum(b['legal_balls'] for b in c_bowler_stats.values())%6}",
                "status": inn_status, "discrepancy": discrepancy
            })

            # Reconcile batters
            if local_deliveries_count > 0:
                for c_pname, c_bstats in c_batter_stats.items():
                    matched_lp = None
                    for lp_name, c_info_map in local_name_to_cric.items():
                        if c_info_map["cric_name"] == c_pname:
                            matched_lp = (lp_name, c_info_map["local_id"])
                            break
                    
                    l_pid = matched_lp[1] if matched_lp else None
                    l_pname = matched_lp[0] if matched_lp else None
                    
                    l_bstats = local_inn_bbb[local_inn_bbb["striker_id"] == l_pid] if l_pid else pd.DataFrame()
                    l_runs = int(l_bstats["runs"].sum()) if len(l_bstats) > 0 else 0
                    l_fours = int(l_bstats["is_four"].sum()) if len(l_bstats) > 0 else 0
                    l_sixes = int(l_bstats["is_six"].sum()) if len(l_bstats) > 0 else 0
                    l_rows = len(l_bstats)
                    l_wides_faced = int((l_bstats["extras_type"] == "wide").sum()) if len(l_bstats) > 0 else 0
                    l_balls_faced = l_rows - l_wides_faced
                    
                    batter_reconciliations.append({
                        "local_match_id": m_id, "innings": inn_idx, "cricsheet_name": c_pname,
                        "local_player_id": l_pid, "local_player_name": l_pname,
                        "cric_runs": c_bstats["runs"], "local_runs": l_runs, "runs_match": (c_bstats["runs"] == l_runs),
                        "cric_balls_faced": c_bstats["balls_faced"], "local_balls_faced_formula": l_balls_faced,
                        "balls_faced_match": (c_bstats["balls_faced"] == l_balls_faced),
                        "cric_fours": c_bstats["fours"], "local_fours": l_fours,
                        "cric_non_boundary_fours": c_bstats["non_boundary_fours"],
                        "cric_sixes": c_bstats["sixes"], "local_sixes": l_sixes,
                        "cric_dismissal": c_bstats["dismissal"]
                    })

                # Reconcile bowlers
                for c_pname, c_bwstats in c_bowler_stats.items():
                    matched_lp = None
                    for lp_name, c_info_map in local_name_to_cric.items():
                        if c_info_map["cric_name"] == c_pname:
                            matched_lp = (lp_name, c_info_map["local_id"])
                            break
                    
                    l_pid = matched_lp[1] if matched_lp else None
                    l_pname = matched_lp[0] if matched_lp else None
                    
                    l_bwstats = local_inn_bbb[local_inn_bbb["bowler_id"] == l_pid] if l_pid else pd.DataFrame()
                    l_rows = len(l_bwstats)
                    l_wides = int((l_bwstats["extras_type"] == "wide").sum()) if len(l_bwstats) > 0 else 0
                    l_nb = int((l_bwstats["extras_type"] == "Overstep").sum()) if len(l_bwstats) > 0 else 0
                    l_legal = l_rows - l_wides - l_nb
                    l_striker_runs = int(l_bwstats["runs"].sum()) if len(l_bwstats) > 0 else 0
                    
                    bowler_reconciliations.append({
                        "local_match_id": m_id, "innings": inn_idx, "cricsheet_name": c_pname,
                        "local_player_id": l_pid, "local_player_name": l_pname,
                        "cric_legal_balls": c_bwstats["legal_balls"], "local_legal_balls_formula": l_legal,
                        "legal_balls_match": (c_bwstats["legal_balls"] == l_legal),
                        "cric_runs_conceded": c_bwstats["runs_conceded"],
                        "local_striker_runs_only": l_striker_runs,
                        "cric_wickets": c_bwstats["wickets"],
                        "cric_wides": c_bwstats["wides"], "cric_noballs": c_bwstats["noballs"]
                    })

    # Save output tables
    pd.DataFrame(match_reconciliations).to_csv(os.path.join(REPORTS_DIR, "cricsheet_match_reconciliation.csv"), index=False)
    pd.DataFrame(innings_reconciliations).to_csv(os.path.join(REPORTS_DIR, "cricsheet_innings_reconciliation.csv"), index=False)
    pd.DataFrame(batter_reconciliations).to_csv(os.path.join(REPORTS_DIR, "cricsheet_batter_reconciliation.csv"), index=False)
    pd.DataFrame(bowler_reconciliations).to_csv(os.path.join(REPORTS_DIR, "cricsheet_bowler_reconciliation.csv"), index=False)
    pd.DataFrame(player_crosswalk_records).drop_duplicates().to_csv(os.path.join(REPORTS_DIR, "cricsheet_player_crosswalk.csv"), index=False)

    # 4. Overall Dataset Coverage Quantification with Alias & Timezone Tolerance
    print("\nQuantifying overall Cricsheet coverage with aliases and timezone tolerance...")
    coverage_records = []
    
    cric_all_matches = []
    for m in ipl_index:
        cric_all_matches.append({"source": "ipl", "file": m["file"], "dates": m["dates"], "teams": m["normalized_teams"]})
    for m in t20i_index:
        cric_all_matches.append({"source": "t20i", "file": m["file"], "dates": m["dates"], "teams": m["normalized_teams"]})

    covered_count = 0
    abandoned_count = 0
    policy_withheld_count = 0
    missing_count = 0

    for _, r in merged_matches.iterrows():
        mid = r["match_id"]
        mdate = r["match_date"]
        comp_name = r["comp_name"]
        m_format = r["match_format"]
        home_team = r["home_team"]
        away_team = r["away_team"]
        res = str(r["result"])
        
        target_teams = {normalize_team(home_team), normalize_team(away_team)}
        
        # Check exact date
        matched_cric = None
        for cm in cric_all_matches:
            if mdate in cm["dates"] and target_teams.issubset(cm["teams"]):
                matched_cric = cm
                break
                
        # If not, check date +/- 1 day (for host local vs IST night matches)
        if not matched_cric:
            dt = datetime.strptime(mdate, "%Y-%m-%d")
            adj = [(dt - timedelta(days=1)).strftime("%Y-%m-%d"), (dt + timedelta(days=1)).strftime("%Y-%m-%d")]
            for cm in cric_all_matches:
                if any(ad in cm["dates"] for ad in adj) and target_teams.issubset(cm["teams"]):
                    matched_cric = cm
                    break

        if matched_cric:
            covered_count += 1
            cov_status = "COVERED"
            cov_notes = f"Matched Cricsheet {matched_cric['source']} {matched_cric['file']}"
        elif "Match Abandoned" in res:
            abandoned_count += 1
            cov_status = "ABANDONED_UNPLAYED"
            cov_notes = "Match abandoned; no play or deliveries expected"
        elif "Afghanistan" in home_team or "Afghanistan" in away_team:
            policy_withheld_count += 1
            cov_status = "CRICSHEET_POLICY_WITHHELD"
            cov_notes = "Withheld by Cricsheet editorial policy regarding Afghanistan men's team"
        else:
            missing_count += 1
            cov_status = "MISSING_IN_CRICSHEET"
            cov_notes = "Not found in IPL or T20I Cricsheet downloads"

        coverage_records.append({
            "match_id": mid, "match_date": mdate, "comp_name": comp_name, "match_format": m_format,
            "home_team": home_team, "away_team": away_team, "result": res,
            "coverage_status": cov_status, "notes": cov_notes
        })

    coverage_df = pd.DataFrame(coverage_records)
    coverage_df.to_csv(os.path.join(REPORTS_DIR, "cricsheet_overall_coverage_audit.csv"), index=False)
    
    print("\nRefined Coverage Summary:")
    print(coverage_df["coverage_status"].value_counts())
    print(f"\nTotal matches: {len(coverage_df)}")
    print(f"Covered: {covered_count} ({covered_count/len(coverage_df)*100:.1f}%)")
    print(f"Abandoned: {abandoned_count}")
    print(f"Policy Withheld: {policy_withheld_count}")
    print(f"Missing in Cricsheet: {missing_count}")

    print("\n=== Refined Verification Complete ===")

if __name__ == "__main__":
    run_verification()
