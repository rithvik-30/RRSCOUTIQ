"""
RR ScoutIQ — Canonical SHA-256 Integrity Reconciliation Engine
Module: src/m5_enrichment/canonical_integrity_audit.py

Performs forensic hash verification against the M4.6 authoritative baseline
and verifies row-level, cell-level preservation of all 33 original local columns.
"""

import hashlib
import os
import time
import pandas as pd
import numpy as np

M4_6_CANONICAL_BASELINE = {
    "data/data_pack.zip.zip": "788f681b538ba95fb61bcaba7b7280e59a7789d043e7964ac3472c3d08291853",
    "data/extracted/ball_by_ball.csv": "a3926f49d2c684dca2a5d2de535a02c5ee46ea654ca1e79dd31c69e7544e9889",
    "data/extracted/matches.csv": "bb100ab84b8b9a15160c1f2315cf675210131a30e779ec5079fd5403dcf56eef",
    "data/extracted/competitions.csv": "507ceb7189f972d4e4f299ddcfc97f3c3247af1913f6291106f161fa8353fd9b",
    "data/extracted/teams.csv": "a65e5922a9b3bf49247b24fc9471782e700efb31f8dcc5042923238b87c50a5d",
    "data/extracted/playing_eleven.csv": "7517c73722a28d5d61c808ccf0cbed315a8780586d02e946eb9a7f5daf011c27",
    "data/extracted/competition_team_player_mapping.csv": "1ded4e42a933618572d6e2c3a521c3257eb1844fab4456d567d77cbb2d3bbb12",
    "data/enriched/pilot/enriched_ball_by_ball_pilot.csv": "a71f3ca75d3ba7aab60b797f78726f7d19551bde1221a3c97ed342c7fb0f9878"
}

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def verify_all_hashes():
    print("=" * 80)
    print("1. CANONICAL SHA-256 HASH VERIFICATION")
    print("=" * 80)
    results = []
    all_match = True
    for path, expected_hash in M4_6_CANONICAL_BASELINE.items():
        if not os.path.exists(path):
            results.append({
                "path": path,
                "expected": expected_hash,
                "computed": "FILE_NOT_FOUND",
                "size": 0,
                "mtime": "N/A",
                "status": "MISSING"
            })
            all_match = False
            continue
        computed = compute_sha256(path)
        size = os.path.getsize(path)
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(path)))
        status = "MATCH" if computed == expected_hash else "MISMATCH"
        if status != "MATCH":
            all_match = False
        results.append({
            "path": path,
            "expected": expected_hash,
            "computed": computed,
            "size": size,
            "mtime": mtime,
            "status": status
        })
        print(f"{path} | Size: {size:,} | Mtime: {mtime} | Status: {status}")
        if status != "MATCH":
            print(f"  EXPECTED: {expected_hash}")
            print(f"  COMPUTED: {computed}")
    print(f"\nAll 8 files match canonical baseline: {all_match}")
    return results, all_match

def verify_local_column_preservation():
    print("\n" + "=" * 80)
    print("2. LOCAL SOURCE PRESERVATION VERIFICATION (33 COLUMNS, ROW-BY-ROW)")
    print("=" * 80)
    
    raw_path = "data/extracted/ball_by_ball.csv"
    enr_path = "data/enriched/full/enriched_ball_by_ball_full.csv"
    manifest_path = "data/enriched/full/match_enrichment_manifest.csv"
    
    print("Loading datasets...")
    raw_df = pd.read_csv(raw_path)
    enr_df = pd.read_csv(enr_path)
    manifest = pd.read_csv(manifest_path)
    
    raw_cols = list(raw_df.columns)
    print(f"Original ball_by_ball.csv rows: {len(raw_df):,}, columns: {len(raw_cols)}")
    print(f"Enriched dataset rows: {len(enr_df):,}, columns: {len(enr_df.columns)}")
    
    # Check column existence
    missing_cols = [c for c in raw_cols if c not in enr_df.columns]
    print(f"Raw columns missing in enriched: {missing_cols}")
    assert len(missing_cols) == 0, f"Missing columns: {missing_cols}"
    
    # Filter raw_df to eligible match deliveries (excluding Super Overs for 13613 and 21176, exactly as defined by analytical scope)
    # Get enriched matches
    enriched_match_ids = set(manifest[manifest["processing_status"] == "ENRICHED_AND_VALIDATED"]["local_match_id"])
    print(f"Enriched eligible matches count: {len(enriched_match_ids)}")
    
    # Slice raw_df for these 776 matches
    raw_sliced = raw_df[raw_df["match_id"].isin(enriched_match_ids)].copy()
    
    # For regulation-only matches (13613, 21176), exclude innings > 2 (Super Overs)
    reg_only_matches = {13613, 21176}
    raw_in_scope = raw_sliced[~(raw_sliced["match_id"].isin(reg_only_matches) & (raw_sliced["innings"] > 2))].copy()
    
    print(f"Raw in-scope rows: {len(raw_in_scope):,}")
    print(f"Enriched dataset rows: {len(enr_df):,}")
    assert len(raw_in_scope) == len(enr_df), f"Row count mismatch: raw {len(raw_in_scope)} vs enr {len(enr_df)}"
    
    # To compare row-by-row regardless of match iteration order, sort both deterministically:
    sort_cols = ["match_id", "innings", "overid", "over_ball_num", "innings_ball_num"]
    raw_sorted = raw_in_scope.sort_values(by=sort_cols).reset_index(drop=True)
    enr_sorted = enr_df[raw_cols].sort_values(by=sort_cols).reset_index(drop=True)
    
    # Compare row-by-row across each column
    column_discrepancies = {}
    for col in raw_cols:
        raw_vals = raw_sorted[col]
        enr_vals = enr_sorted[col]
        
        # Handle NA equivalence
        both_na = raw_vals.isna() & enr_vals.isna()
        value_match = (raw_vals == enr_vals) | both_na
        
        mismatches = (~value_match).sum()
        if mismatches > 0:
            column_discrepancies[col] = mismatches
            print(f"Column '{col}': {mismatches} mismatches!")
        else:
            print(f"Column '{col}': EXACT MATCH across all {len(raw_vals):,} rows.")
            
    print(f"\nTotal columns with discrepancies: {len(column_discrepancies)}")
    return column_discrepancies

if __name__ == "__main__":
    verify_all_hashes()
    verify_local_column_preservation()
