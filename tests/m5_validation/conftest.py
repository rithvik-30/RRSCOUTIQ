"""
Pytest configuration and session-scoped fixtures for M5.4 validation tests.
"""

from pathlib import Path
import pytest
import pandas as pd


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def enriched_df(project_root) -> pd.DataFrame:
    path = project_root / "data" / "enriched" / "full" / "enriched_ball_by_ball_full.csv"
    assert path.exists(), f"Enriched dataset missing: {path}"
    return pd.read_csv(path, low_memory=False)


@pytest.fixture(scope="session")
def match_state_df(project_root) -> pd.DataFrame:
    path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    assert path.exists(), f"Match state dataset missing: {path}"
    return pd.read_csv(path, low_memory=False)


@pytest.fixture(scope="session")
def crosswalk_df(project_root) -> pd.DataFrame:
    path = project_root / "data" / "enriched" / "m5_player_crosswalk_audit.csv"
    assert path.exists(), f"Crosswalk missing: {path}"
    return pd.read_csv(path, low_memory=False)
