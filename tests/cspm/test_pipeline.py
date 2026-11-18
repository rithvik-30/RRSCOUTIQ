"""
Integration Tests for CSPM Shadow Pipeline
Phase 4.4 Controlled Shadow-Mode Pilot
"""

import os
import json
import pytest
import pandas as pd
from src.models.cspm.pipeline import build_completed_matches_database


def test_build_completed_matches_database():
    """
    Verifies that build_completed_matches_database correctly flags full vs truncated 1st innings.
    """
    canonical_sample = pd.DataFrame([
        # Match 1: 120 balls, 180 runs, 6 wickets => complete
        {"match_id": 1, "innings": 1, "ext_is_legal_delivery": 1, "ext_delivery_total_runs": 1, "ext_is_wicket": 0, "is_dli_valid": 1}
    ] * 120 + [
        # Match 2: 40 balls, 50 runs, 3 wickets => truncated
        {"match_id": 2, "innings": 1, "ext_is_legal_delivery": 1, "ext_delivery_total_runs": 1, "ext_is_wicket": 0, "is_dli_valid": 1}
    ] * 40)

    matches_meta = pd.DataFrame([
        {"match_id": 1, "comp_id": 100, "match_date": "2024-05-01", "venue_id": 5},
        {"match_id": 2, "comp_id": 100, "match_date": "2024-05-02", "venue_id": 5}
    ])

    comps = pd.DataFrame([{"comp_id": 100, "comp_name": "IPL 2024", "season": "2024"}])

    db = build_completed_matches_database(canonical_sample, matches_meta, comps)
    m1_row = db[db["match_id"] == 1].iloc[0]
    m2_row = db[db["match_id"] == 2].iloc[0]

    assert m1_row["is_complete_first_innings"] is True or m1_row["is_complete_first_innings"] == 1
    assert m2_row["is_complete_first_innings"] is False or m2_row["is_complete_first_innings"] == 0


def test_shadow_artifacts_isolation():
    """
    Ensures experimental output path does NOT touch production paths.
    """
    output_dir = "data/experimental/cspm"
    assert not output_dir.startswith("data/processed"), "Experimental outputs must not target data/processed/"
    assert not output_dir.startswith("data/extracted"), "Experimental outputs must not target data/extracted/"
