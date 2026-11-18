"""
CSPM (Cricket State Pressure Model) Configuration and Constants
Phase 4.4 Controlled Shadow-Mode Pilot Specification
"""

from typing import List, Dict

# First-Innings Projection & Uncertainty Constants
SIGMA_0: float = 34.0
MIN_UNCERTAINTY: float = 5.0
MAX_BALLS: int = 120
MAX_WICKETS: int = 10

# Venue Par Hierarchical Shrinkage Constants
VENUE_SHRINKAGE_M: float = 8.0
VENUE_MIN_MATCHES: int = 5
COMP_MIN_MATCHES: int = 5
GLOBAL_PAR_DEFAULT: float = 170.81

# Chase Win Probability Model Feature Specification
CHASE_FEATURE_COLS: List[str] = [
    "runs_req",
    "balls_rem",
    "wkts_in_hand",
    "rrr",
    "crr",
    "rrr_minus_crr",
    "balls_per_wicket",
    "runs_per_wicket"
]

# Pressure Tiers and Official Scouting Filters
PRESSURE_TIER_BOUNDS: Dict[str, float] = {
    "Low": 0.0,
    "Medium": 30.0,
    "High": 60.0,
    "Extreme": 80.0
}
OFFICIAL_SCOUTING_PRESSURE_CUTOFF: float = 60.0

# Empirical Bayes Eligibility Thresholds (Preserving Production Parity)
BATTER_MIN_CAREER_BALLS: int = 500
BATTER_MIN_PRESSURE_BALLS: int = 100
BATTER_EMERGING_PRESSURE_BALLS: int = 60

BOWLER_MIN_CAREER_BALLS: int = 500
BOWLER_MIN_PRESSURE_SPELLS: int = 20
BOWLER_EMERGING_PRESSURE_SPELLS: int = 15

# Terminal Crunch Fallback
SUPER_OVER_FIXED_SCORE: float = 75.0

# Outcome Simplex Categories
OUTCOME_CATEGORIES: List[str] = [
    "dot",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "wicket"
]
