"""
Unit Tests for Chronological Venue Par Estimator
Phase 4.4 Controlled Shadow-Mode Pilot
"""

import pytest
import pandas as pd
import numpy as np

from src.models.cspm.venue_par import ChronologicalVenueParEstimator
from src.models.cspm.config import GLOBAL_PAR_DEFAULT


@pytest.fixture
def sample_historical_matches():
    data = [
        # Venue 1, Comp 10
        {"match_id": 1, "match_date": "2024-01-01", "venue_id": 1, "comp_id": 10, "first_innings_runs": 160.0, "is_complete_first_innings": True},
        {"match_id": 2, "match_date": "2024-01-02", "venue_id": 1, "comp_id": 10, "first_innings_runs": 170.0, "is_complete_first_innings": True},
        {"match_id": 3, "match_date": "2024-01-03", "venue_id": 1, "comp_id": 10, "first_innings_runs": 165.0, "is_complete_first_innings": True},
        {"match_id": 4, "match_date": "2024-01-04", "venue_id": 1, "comp_id": 10, "first_innings_runs": 175.0, "is_complete_first_innings": True},
        {"match_id": 5, "match_date": "2024-01-05", "venue_id": 1, "comp_id": 10, "first_innings_runs": 180.0, "is_complete_first_innings": True},
        {"match_id": 6, "match_date": "2024-01-06", "venue_id": 1, "comp_id": 10, "first_innings_runs": 185.0, "is_complete_first_innings": True},
        # Venue 2, Comp 10 (only 2 matches)
        {"match_id": 7, "match_date": "2024-01-07", "venue_id": 2, "comp_id": 10, "first_innings_runs": 190.0, "is_complete_first_innings": True},
        {"match_id": 8, "match_date": "2024-01-08", "venue_id": 2, "comp_id": 10, "first_innings_runs": 200.0, "is_complete_first_innings": True},
        # Additional matches to reach >= 10 total
        {"match_id": 9, "match_date": "2024-01-09", "venue_id": 3, "comp_id": 20, "first_innings_runs": 150.0, "is_complete_first_innings": True},
        {"match_id": 10, "match_date": "2024-01-10", "venue_id": 3, "comp_id": 20, "first_innings_runs": 155.0, "is_complete_first_innings": True},
        {"match_id": 11, "match_date": "2024-01-11", "venue_id": 3, "comp_id": 20, "first_innings_runs": 160.0, "is_complete_first_innings": True},
        # Incomplete / abandoned match (must be ignored)
        {"match_id": 12, "match_date": "2024-01-12", "venue_id": 1, "comp_id": 10, "first_innings_runs": 45.0, "is_complete_first_innings": False},
        # Future match
        {"match_id": 13, "match_date": "2024-01-20", "venue_id": 1, "comp_id": 10, "first_innings_runs": 220.0, "is_complete_first_innings": True},
    ]
    return pd.DataFrame(data)


def test_future_match_invariance(sample_historical_matches):
    """
    Adding future matches must NOT change the historical venue par estimate.
    """
    estimator = ChronologicalVenueParEstimator(m_shrunk=8.0, min_venue_matches=5, min_comp_matches=5)
    estimator.fit_database(sample_historical_matches)

    # Estimate par on 2024-01-15 for Venue 1
    est1 = estimator.estimate_par(
        match_date=pd.Timestamp("2024-01-15"),
        venue_id=1,
        comp_id=10,
        current_match_id=99
    )

    # Now add a future match on 2024-02-01 with an extreme score (300 runs)
    extended_matches = sample_historical_matches.copy()
    future_row = pd.DataFrame([{
        "match_id": 999,
        "match_date": "2024-02-01",
        "venue_id": 1,
        "comp_id": 10,
        "first_innings_runs": 300.0,
        "is_complete_first_innings": True
    }])
    extended_matches = pd.concat([extended_matches, future_row], ignore_index=True)

    estimator_ext = ChronologicalVenueParEstimator(m_shrunk=8.0, min_venue_matches=5, min_comp_matches=5)
    estimator_ext.fit_database(extended_matches)

    est2 = estimator_ext.estimate_par(
        match_date=pd.Timestamp("2024-01-15"),
        venue_id=1,
        comp_id=10,
        current_match_id=99
    )

    assert est1["venue_par"] == pytest.approx(est2["venue_par"], abs=1e-7), \
        "Future match contaminated the historical venue par estimate!"
    assert est1["source"] == est2["source"] == "venue"


def test_evaluated_match_self_exclusion(sample_historical_matches):
    """
    A match cannot use its own result to estimate its venue par.
    """
    estimator = ChronologicalVenueParEstimator(m_shrunk=8.0, min_venue_matches=5)
    estimator.fit_database(sample_historical_matches)

    # Match 6 is on 2024-01-06 with 185 runs
    est_without_self = estimator.estimate_par(
        match_date=pd.Timestamp("2024-01-06"),
        venue_id=1,
        comp_id=10,
        current_match_id=6
    )

    # Prior venue matches must be strictly 5 (matches 1 to 5)
    assert est_without_self["venue_matches_count"] == 5
    # The mean of matches 1-5 is (160+170+165+175+180)/5 = 170.0
    # It does not include 185.0 from Match 6


def test_incomplete_match_exclusion(sample_historical_matches):
    """
    Truncated/abandoned matches (is_complete=False) must be excluded from venue par.
    """
    estimator = ChronologicalVenueParEstimator()
    estimator.fit_database(sample_historical_matches)

    # Check database inside estimator
    db_match_ids = estimator.db["match_id"].tolist()
    assert 12 not in db_match_ids, "Incomplete match 12 was not excluded from estimator DB!"


def test_hierarchical_fallback_tiers(sample_historical_matches):
    """
    Tests the 3 fallback tiers: venue (N>=5) -> competition (N>=5) -> global.
    """
    estimator = ChronologicalVenueParEstimator(min_venue_matches=5, min_comp_matches=5)
    estimator.fit_database(sample_historical_matches)

    # 1. Venue 1 has 6 prior matches => Source: 'venue'
    est_venue = estimator.estimate_par(pd.Timestamp("2024-01-15"), venue_id=1, comp_id=10)
    assert est_venue["source"] == "venue"

    # 2. Venue 2 has only 2 prior matches, but Comp 10 has 8 matches => Source: 'competition'
    est_comp = estimator.estimate_par(pd.Timestamp("2024-01-15"), venue_id=2, comp_id=10)
    assert est_comp["source"] == "competition"

    # 3. Venue 99 has 0 matches, Comp 99 has 0 matches => Source: 'global'
    est_global = estimator.estimate_par(pd.Timestamp("2024-01-15"), venue_id=99, comp_id=99)
    assert est_global["source"] == "global"


def test_cold_start_fallback():
    """
    When total prior matches < 10, falls back to global cold-start default.
    """
    few_matches = pd.DataFrame([
        {"match_id": 1, "match_date": "2024-01-01", "venue_id": 1, "comp_id": 10, "first_innings_runs": 160.0, "is_complete_first_innings": True},
        {"match_id": 2, "match_date": "2024-01-02", "venue_id": 1, "comp_id": 10, "first_innings_runs": 170.0, "is_complete_first_innings": True}
    ])
    estimator = ChronologicalVenueParEstimator()
    estimator.fit_database(few_matches)

    est = estimator.estimate_par(pd.Timestamp("2024-01-03"), venue_id=1, comp_id=10)
    assert est["source"] == "global_cold_start"
    assert est["venue_par"] == pytest.approx(165.0, abs=1e-5)
