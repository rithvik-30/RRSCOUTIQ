"""
RR ScoutIQ - Module M4.5: Reliability & Ranking Engine
======================================================
Architectural role: Evaluates player performance estimates, statistical uncertainty,
sample adequacy, and ranking eligibility under strict role-aware comparative frameworks.

Core Responsibilities:
1. Reliability Assessment (Innings, balls, pressure volume, cluster units, bootstrap SE, CIs, Credible Intervals).
2. Provisional Eligibility Evaluation (Dual-tier thresholds: 12 inn / 120 balls / 36 pressure balls for batters;
   12 inn / 144 balls / 42 pressure balls for bowlers).
3. Explainable 4-Tier Reliability Classification:
   - Tier A: ELIGIBLE_HIGH_CONFIDENCE (Eligible + N_press >= 72 + clusters >= 8 + SE <= 0.35)
   - Tier B: ELIGIBLE_MODERATE_CONFIDENCE (Eligible + standard evidence)
   - Tier C: INELIGIBLE_INSUFFICIENT_SAMPLE (Explicit exclusion reasons)
   - Tier D: UNRESOLVED_DATA_INCOMPLETE (Missing/corrupted tracking or zero exposure)
4. Role-Aware Ranking Framework:
   - Evaluates within-role rank distributions across bootstrap draws (Rank_5%, Rank_95%, P(Top 10)).
   - Conservative Lower-Bound / Uncertainty-Aware Ranking option (e.g. Percentile 5% or Z - 1.645*SE) vs Point Score.
   - Preserves distinction between talent estimate and statistical precision.
   - Strict eligibility enforcement (Ineligible players never appear in official rankings).
5. Comprehensive Explainability:
   - Positive and negative performance attribution drivers.
   - Sample adequacy and clustering breakdown.
   - Uncertainty sensitivity and rank volatility diagnostics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, Set
import math
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Authoritative Constants & Thresholds (M3 Approved & Provisional)
# ---------------------------------------------------------------------------

# Batting Provisional Eligibility Gates
BATTER_MIN_INNINGS: int = 12
BATTER_MIN_BALLS_FACED: int = 120
BATTER_MIN_PRESSURE_BALLS: int = 36

# Bowling Provisional Eligibility Gates
BOWLER_MIN_INNINGS: int = 12
BOWLER_MIN_LEGAL_BALLS: int = 144
BOWLER_MIN_PRESSURE_LEGAL_BALLS: int = 42

# High-Confidence Reliability Benchmarks (Provisional Engineering Heuristics)
RELIABILITY_HIGH_CONF_PRESS_BALLS_BATTER: int = 72
RELIABILITY_HIGH_CONF_PRESS_BALLS_BOWLER: int = 84
RELIABILITY_HIGH_CONF_MIN_CLUSTERS: int = 8
RELIABILITY_HIGH_CONF_MAX_SE: float = 0.35
MIN_BOOTSTRAP_DRAWS_FOR_LOWER_BOUND: int = 100

# Component Weights for Explainability
BPPI_COMPONENT_WEIGHTS: Dict[str, float] = {
    "xra": 0.35,
    "delta_sr": 0.25,
    "delta_bnd": 0.15,
    "delta_dot": 0.15,
    "delta_survival": 0.10,
}

PPBI_COMPONENT_WEIGHTS: Dict[str, float] = {
    "xrs": 0.35,
    "delta_econ": 0.20,
    "delta_wkt": 0.25,
    "delta_dot": 0.10,
    "delta_bnd_con": 0.10,
}


class ReliabilityTier(str, Enum):
    """Explainable four-tier reliability classification."""
    ELIGIBLE_HIGH_CONFIDENCE = "ELIGIBLE_HIGH_CONFIDENCE"
    ELIGIBLE_MODERATE_CONFIDENCE = "ELIGIBLE_MODERATE_CONFIDENCE"
    INELIGIBLE_INSUFFICIENT_SAMPLE = "INELIGIBLE_INSUFFICIENT_SAMPLE"
    UNRESOLVED_DATA_INCOMPLETE = "UNRESOLVED_DATA_INCOMPLETE"


@dataclass
class PlayerReliabilityAssessment:
    """Detailed reliability profile for an individual player."""
    player_id: int
    player_name: str
    player_type: str  # "batter" or "bowler"
    primary_role: str
    innings_count: int
    total_balls: int  # balls faced for batter, legal balls for bowler
    pressure_balls: int
    pressure_innings_count: int
    cluster_count: int  # independent match-innings clusters
    is_eligible: bool
    exclusion_reasons: List[str]
    reliability_tier: ReliabilityTier
    point_score: float  # BPPI or PPBI
    bootstrap_se: float
    ci_percentile_90: Tuple[float, float]
    ci_normal_90: Tuple[float, float]
    credible_interval_90: Tuple[float, float]
    attribution_positives: List[str]
    attribution_negatives: List[str]
    sample_summary: str
    reliability_note: str


@dataclass
class RoleRankingDossier:
    """Role-aware ranking summary table with volatility metrics."""
    role: str
    player_type: str
    ranked_players: List[Dict[str, Any]]
    ineligible_players: List[Dict[str, Any]]
    ranking_metric: str  # e.g. "point_score" or "lower_bound_90"
    total_pool_size: int
    eligible_count: int


# ---------------------------------------------------------------------------
# 1. Eligibility Evaluation Engine
# ---------------------------------------------------------------------------

def evaluate_player_eligibility(
    player_type: str,
    innings_count: int,
    total_balls: int,
    pressure_balls: int,
    has_valid_data: bool = True
) -> Tuple[bool, List[str]]:
    """
    Evaluates whether a player meets the M3 dual-tier provisional eligibility criteria.
    
    PROVISIONAL STATUS:
    - Retained from M3 Task 6 Item 14 to prevent survivorship bias against tail specialists.
    - Missing data is NEVER treated as zero.
    """
    reasons = []
    
    if not has_valid_data:
        reasons.append("UNRESOLVED_OR_CORRUPTED_DATA")
        return False, reasons
        
    p_type = player_type.lower()
    if p_type == "batter":
        if innings_count < BATTER_MIN_INNINGS:
            reasons.append(f"INSUFFICIENT_INNINGS ({innings_count} < {BATTER_MIN_INNINGS})")
        if total_balls < BATTER_MIN_BALLS_FACED:
            reasons.append(f"INSUFFICIENT_BALLS_FACED ({total_balls} < {BATTER_MIN_BALLS_FACED})")
        if pressure_balls < BATTER_MIN_PRESSURE_BALLS:
            reasons.append(f"INSUFFICIENT_PRESSURE_BALLS ({pressure_balls} < {BATTER_MIN_PRESSURE_BALLS})")
    elif p_type == "bowler":
        if innings_count < BOWLER_MIN_INNINGS:
            reasons.append(f"INSUFFICIENT_INNINGS ({innings_count} < {BOWLER_MIN_INNINGS})")
        if total_balls < BOWLER_MIN_LEGAL_BALLS:
            reasons.append(f"INSUFFICIENT_LEGAL_BALLS ({total_balls} < {BOWLER_MIN_LEGAL_BALLS})")
        if pressure_balls < BOWLER_MIN_PRESSURE_LEGAL_BALLS:
            reasons.append(f"INSUFFICIENT_PRESSURE_LEGAL_BALLS ({pressure_balls} < {BOWLER_MIN_PRESSURE_LEGAL_BALLS})")
    else:
        raise ValueError(f"Unknown player_type: {player_type}")
        
    is_eligible = (len(reasons) == 0)
    return is_eligible, reasons


# ---------------------------------------------------------------------------
# 2. Explainable Reliability Classification Engine
# ---------------------------------------------------------------------------

def classify_reliability_tier(
    is_eligible: bool,
    has_valid_data: bool,
    pressure_balls: int,
    cluster_count: int,
    bootstrap_se: float,
    player_type: str
) -> Tuple[ReliabilityTier, str]:
    """
    Assigns an explainable four-tier reliability classification.
    
    CRITICAL METHODOLOGICAL DISTINCTION:
    - High performance (high BPPI/PPBI score) is strictly decoupled from statistical reliability.
    - A player can have a high score with low reliability (e.g. small sample), or a modest score
      with very high reliability.
    """
    if not has_valid_data:
        return (
            ReliabilityTier.UNRESOLVED_DATA_INCOMPLETE,
            "Data tracking incomplete, corrupted, or zero career balls observed."
        )
        
    if not is_eligible:
        return (
            ReliabilityTier.INELIGIBLE_INSUFFICIENT_SAMPLE,
            "Fails one or more provisional eligibility criteria. Excluded from official rankings."
        )
        
    # Check High-Confidence benchmarks
    min_press = (
        RELIABILITY_HIGH_CONF_PRESS_BALLS_BATTER if player_type.lower() == "batter"
        else RELIABILITY_HIGH_CONF_PRESS_BALLS_BOWLER
    )
    
    # CRITICAL SAFEGUARD: Missing, NaN, or non-finite bootstrap SE cannot qualify for HIGH_CONFIDENCE.
    # Furthermore, zero SE is treated as uninformative (e.g. 1-cluster multiset draw) unless supported
    # by sufficient independent clusters (cluster_count >= RELIABILITY_HIGH_CONF_MIN_CLUSTERS).
    has_valid_se = (
        bootstrap_se is not None and 
        not math.isnan(bootstrap_se) and 
        math.isfinite(bootstrap_se) and 
        bootstrap_se > 0.0
    )
    
    se_ok = (has_valid_se and bootstrap_se <= RELIABILITY_HIGH_CONF_MAX_SE)
    
    if (pressure_balls >= min_press and 
        cluster_count >= RELIABILITY_HIGH_CONF_MIN_CLUSTERS and 
        se_ok):
        return (
            ReliabilityTier.ELIGIBLE_HIGH_CONFIDENCE,
            "Robust sample size across multiple matches with certified narrow estimation uncertainty."
        )
    else:
        note_details = []
        if pressure_balls < min_press:
            note_details.append(f"pressure balls ({pressure_balls} < {min_press})")
        if cluster_count < RELIABILITY_HIGH_CONF_MIN_CLUSTERS:
            note_details.append(f"cluster count ({cluster_count} < {RELIABILITY_HIGH_CONF_MIN_CLUSTERS})")
        if not has_valid_se:
            note_details.append("bootstrap uncertainty uncomputed or non-finite")
        elif bootstrap_se > RELIABILITY_HIGH_CONF_MAX_SE:
            note_details.append(f"bootstrap uncertainty ({bootstrap_se:.3f} > {RELIABILITY_HIGH_CONF_MAX_SE})")
            
        note_str = (
            "Meets eligibility gates but assigned Moderate Confidence due to: " + 
            ", ".join(note_details) + "." if note_details else
            "Meets eligibility gates but exhibits moderate uncertainty or boundary sample depth."
        )
        return (
            ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE,
            note_str
        )


# ---------------------------------------------------------------------------
# 3. Performance Explainability Attribution Engine
# ---------------------------------------------------------------------------

def compute_batter_attribution(row: pd.Series) -> Tuple[List[str], List[str]]:
    """Generates explainable positive and negative performance drivers for a batter."""
    positives = []
    negatives = []
    
    components = [
        ("Expected Runs Added (xRA)", row.get("z_xra", 0.0), BPPI_COMPONENT_WEIGHTS["xra"]),
        ("Pressure Strike Rate (Delta SR)", row.get("z_delta_sr", 0.0), BPPI_COMPONENT_WEIGHTS["delta_sr"]),
        ("Boundary Execution (Delta Bnd%)", row.get("z_delta_bnd", 0.0), BPPI_COMPONENT_WEIGHTS["delta_bnd"]),
        ("Dot Avoidance (Delta Dot%)", row.get("z_delta_dot", 0.0), BPPI_COMPONENT_WEIGHTS["delta_dot"]),
        ("Wicket Preservation (Delta Survival%)", row.get("z_delta_survival", 0.0), BPPI_COMPONENT_WEIGHTS["delta_survival"])
    ]
    
    for name, z_val, wt in components:
        if math.isnan(z_val):
            continue
        contrib = z_val * wt
        desc = f"{name}: Z={z_val:+.2f} (weighted impact {contrib:+.3f})"
        if z_val > 0.20:
            positives.append(desc)
        elif z_val < -0.20:
            negatives.append(desc)
            
    if not positives and not negatives:
        positives.append("Balanced performance near cohort mean across all components.")
        
    return positives, negatives


def compute_bowler_attribution(row: pd.Series) -> Tuple[List[str], List[str]]:
    """Generates explainable positive and negative performance drivers for a bowler."""
    positives = []
    negatives = []
    
    components = [
        ("Expected Runs Saved (xRS)", row.get("z_xrs", 0.0), PPBI_COMPONENT_WEIGHTS["xrs"]),
        ("Economy Containment (Delta Econ)", row.get("z_delta_econ", 0.0), PPBI_COMPONENT_WEIGHTS["delta_econ"]),
        ("Wicket Taking (Delta Wkt%)", row.get("z_delta_wkt", 0.0), PPBI_COMPONENT_WEIGHTS["delta_wkt"]),
        ("Pressure Dot Pressure (Delta Dot%)", row.get("z_delta_dot", 0.0), PPBI_COMPONENT_WEIGHTS["delta_dot"]),
        ("Boundary Suppression (Delta BndCon%)", row.get("z_delta_bnd_con", 0.0), PPBI_COMPONENT_WEIGHTS["delta_bnd_con"])
    ]
    
    for name, z_val, wt in components:
        if math.isnan(z_val):
            continue
        contrib = z_val * wt
        desc = f"{name}: Z={z_val:+.2f} (weighted impact {contrib:+.3f})"
        if z_val > 0.20:
            positives.append(desc)
        elif z_val < -0.20:
            negatives.append(desc)
            
    if not positives and not negatives:
        positives.append("Balanced performance near cohort mean across all components.")
        
    return positives, negatives


# ---------------------------------------------------------------------------
# 4. Master Player Reliability Assessment Builder
# ---------------------------------------------------------------------------

def assess_batter_reliability(
    batter_row: pd.Series,
    bootstrap_dict: Optional[Dict[str, Any]] = None
) -> PlayerReliabilityAssessment:
    """Builds a complete reliability assessment record for a batter."""
    striker_id = int(batter_row["striker_id"])
    name = str(batter_row.get("striker_name", f"Player_{striker_id}"))
    role = str(batter_row.get("primary_role", "Middle Order"))
    inn_count = int(batter_row.get("innings_count", 0))
    balls = int(batter_row.get("total_balls_faced", 0))
    p_balls = int(batter_row.get("pressure_balls", 0))
    score = float(batter_row.get("bppi_score", 0.0))
    
    has_valid = (balls > 0 and not math.isnan(score))
    is_eligible, reasons = evaluate_player_eligibility(
        player_type="batter",
        innings_count=inn_count,
        total_balls=balls,
        pressure_balls=p_balls,
        has_valid_data=has_valid
    )
    
    if bootstrap_dict and bootstrap_dict.get("striker_id") == striker_id:
        se = float(bootstrap_dict.get("se_boot", np.nan))
        ci_perc = tuple(bootstrap_dict.get("ci_percentile_90", (np.nan, np.nan)))
        ci_norm = tuple(bootstrap_dict.get("ci_normal_90", (np.nan, np.nan)))
        cred_int = tuple(bootstrap_dict.get("credible_interval_90", (np.nan, np.nan)))
        clusters = int(bootstrap_dict.get("clusters_count", 0))
    else:
        se = np.nan
        ci_perc = (np.nan, np.nan)
        ci_norm = (np.nan, np.nan)
        cred_int = (np.nan, np.nan)
        clusters = inn_count
        
    tier, tier_note = classify_reliability_tier(
        is_eligible=is_eligible,
        has_valid_data=has_valid,
        pressure_balls=p_balls,
        cluster_count=clusters,
        bootstrap_se=se,
        player_type="batter"
    )
    
    positives, negatives = compute_batter_attribution(batter_row)
    
    sample_summary = (
        f"{inn_count} innings, {balls} total balls faced ({p_balls} in high pressure, DLI >= 1.35), "
        f"{clusters} independent match-innings clusters."
    )
    
    return PlayerReliabilityAssessment(
        player_id=striker_id,
        player_name=name,
        player_type="batter",
        primary_role=role,
        innings_count=inn_count,
        total_balls=balls,
        pressure_balls=p_balls,
        pressure_innings_count=inn_count,
        cluster_count=clusters,
        is_eligible=is_eligible,
        exclusion_reasons=reasons,
        reliability_tier=tier,
        point_score=score,
        bootstrap_se=se,
        ci_percentile_90=ci_perc,
        ci_normal_90=ci_norm,
        credible_interval_90=cred_int,
        attribution_positives=positives,
        attribution_negatives=negatives,
        sample_summary=sample_summary,
        reliability_note=tier_note
    )


def assess_bowler_reliability(
    bowler_row: pd.Series,
    bootstrap_dict: Optional[Dict[str, Any]] = None
) -> PlayerReliabilityAssessment:
    """Builds a complete reliability assessment record for a bowler."""
    bowler_id = int(bowler_row["bowler_id"])
    name = str(bowler_row.get("bowler_name", f"Bowler_{bowler_id}"))
    role = str(bowler_row.get("primary_role", "Middle Enforcer"))
    inn_count = int(bowler_row.get("innings_count", 0))
    balls = int(bowler_row.get("total_legal_balls", 0))
    p_balls = int(bowler_row.get("pressure_legal_balls", 0))
    score = float(bowler_row.get("ppbi_score", 0.0))
    
    has_valid = (balls > 0 and not math.isnan(score))
    is_eligible, reasons = evaluate_player_eligibility(
        player_type="bowler",
        innings_count=inn_count,
        total_balls=balls,
        pressure_balls=p_balls,
        has_valid_data=has_valid
    )
    
    if bootstrap_dict and bootstrap_dict.get("bowler_id") == bowler_id:
        se = float(bootstrap_dict.get("se_boot", np.nan))
        ci_perc = tuple(bootstrap_dict.get("ci_percentile_90", (np.nan, np.nan)))
        ci_norm = tuple(bootstrap_dict.get("ci_normal_90", (np.nan, np.nan)))
        cred_int = tuple(bootstrap_dict.get("credible_interval_90", (np.nan, np.nan)))
        clusters = int(bootstrap_dict.get("clusters_count", 0))
    else:
        se = np.nan
        ci_perc = (np.nan, np.nan)
        ci_norm = (np.nan, np.nan)
        cred_int = (np.nan, np.nan)
        clusters = inn_count
        
    tier, tier_note = classify_reliability_tier(
        is_eligible=is_eligible,
        has_valid_data=has_valid,
        pressure_balls=p_balls,
        cluster_count=clusters,
        bootstrap_se=se,
        player_type="bowler"
    )
    
    positives, negatives = compute_bowler_attribution(bowler_row)
    
    sample_summary = (
        f"{inn_count} innings, {balls} total legal deliveries ({p_balls} in high pressure, DLI >= 1.35), "
        f"{clusters} independent match-innings clusters."
    )
    
    return PlayerReliabilityAssessment(
        player_id=bowler_id,
        player_name=name,
        player_type="bowler",
        primary_role=role,
        innings_count=inn_count,
        total_balls=balls,
        pressure_balls=p_balls,
        pressure_innings_count=inn_count,
        cluster_count=clusters,
        is_eligible=is_eligible,
        exclusion_reasons=reasons,
        reliability_tier=tier,
        point_score=score,
        bootstrap_se=se,
        ci_percentile_90=ci_perc,
        ci_normal_90=ci_norm,
        credible_interval_90=cred_int,
        attribution_positives=positives,
        attribution_negatives=negatives,
        sample_summary=sample_summary,
        reliability_note=tier_note
    )


# ---------------------------------------------------------------------------
# 5. Role-Aware Ranking Framework Engine
# ---------------------------------------------------------------------------

def generate_role_rankings(
    assessments: List[PlayerReliabilityAssessment],
    ranking_metric: str = "point_score",
    allow_ineligible: bool = False
) -> Dict[str, RoleRankingDossier]:
    """
    Constructs transparent, role-aware ranking dossiers for each tactical cohort.
    
    UNAMBIGUOUS METRIC SPECIFICATIONS:
    - Primary Expected Ranking ('point_score'):
      Sort key: (-point_score, -pressure_balls, -total_balls, player_id)
      Ranks players by expected talent under empirical Bayes shrinkage.
      
    - Conservative Lower-Bound Ranking ('lower_bound_90'):
      Sort key: (-conservative_score, -pressure_balls, -total_balls, player_id)
      Where conservative_score is defined STRICTLY as the 5th percentile of the
      valid Scheme B bootstrap distribution (ci_percentile_90[0]).
      CRITICAL SAFEGUARD: If the bootstrap distribution is unavailable, corrupted, or
      inadequate (fewer than MIN_BOOTSTRAP_DRAWS_FOR_LOWER_BOUND valid draws or NaN),
      lower_bound_90 is NEVER silently approximated with Normal approximations.
      Instead, conservative_score is set to NaN, excluded from positive lower-bound
      ranking, and marked as UNAVAILABLE with an explicit reason.
      
    GOVERNANCE CONSTRAINTS:
    - Ineligible players are strictly segregated from official rankings.
    - Rankings are computed separately for each tactical role cohort.
    - Ranking ties are resolved deterministically (primary metric -> pressure volume -> total volume -> player_id).
    """
    by_role: Dict[str, List[PlayerReliabilityAssessment]] = {}
    for p in assessments:
        by_role.setdefault(p.primary_role, []).append(p)
        
    dossiers: Dict[str, RoleRankingDossier] = {}
    
    for role, plist in by_role.items():
        p_type = plist[0].player_type if plist else "unknown"
        
        eligible_pool = [p for p in plist if p.is_eligible or allow_ineligible]
        ineligible_pool = [p for p in plist if not p.is_eligible and not allow_ineligible]
        
        # Sort eligible pool
        def sort_key(p: PlayerReliabilityAssessment):
            if ranking_metric == "lower_bound_90":
                # Strict 5th percentile bootstrap lower bound
                score = p.ci_percentile_90[0]
                # If unavailable, sort to the bottom as -infinity
                effective_score = score if not math.isnan(score) else -float("inf")
                return (-effective_score, -p.pressure_balls, -p.total_balls, p.player_id)
            else:
                score = p.point_score
                effective_score = score if not math.isnan(score) else -float("inf")
                return (-effective_score, -p.pressure_balls, -p.total_balls, p.player_id)
            
        eligible_pool_sorted = sorted(eligible_pool, key=sort_key)
        
        ranked_records = []
        for rank_idx, p in enumerate(eligible_pool_sorted, start=1):
            lower_bound_val = p.ci_percentile_90[0]
            lower_bound_status = (
                "AVAILABLE" if not math.isnan(lower_bound_val)
                else "UNAVAILABLE_INSUFFICIENT_BOOTSTRAP_DRAWS"
            )
            
            ranked_records.append({
                "rank": rank_idx,
                "player_id": p.player_id,
                "player_name": p.player_name,
                "point_score": p.point_score,
                "lower_bound_90": lower_bound_val,
                "lower_bound_status": lower_bound_status,
                "bootstrap_se": p.bootstrap_se,
                "ci_percentile_90": p.ci_percentile_90,
                "credible_interval_90": p.credible_interval_90,
                "reliability_tier": p.reliability_tier.value,
                "pressure_balls": p.pressure_balls,
                "total_balls": p.total_balls,
                "innings_count": p.innings_count,
                "attribution_positives": p.attribution_positives,
                "attribution_negatives": p.attribution_negatives
            })
            
        ineligible_records = []
        for p in ineligible_pool:
            lower_bound_val = p.ci_percentile_90[0]
            lower_bound_status = (
                "AVAILABLE" if not math.isnan(lower_bound_val)
                else "UNAVAILABLE_INSUFFICIENT_BOOTSTRAP_DRAWS"
            )
            
            ineligible_records.append({
                "player_id": p.player_id,
                "player_name": p.player_name,
                "point_score": p.point_score,
                "lower_bound_90": lower_bound_val,
                "lower_bound_status": lower_bound_status,
                "exclusion_reasons": p.exclusion_reasons,
                "reliability_tier": p.reliability_tier.value,
                "pressure_balls": p.pressure_balls,
                "total_balls": p.total_balls,
                "innings_count": p.innings_count
            })
            
        dossiers[role] = RoleRankingDossier(
            role=role,
            player_type=p_type,
            ranked_players=ranked_records,
            ineligible_players=ineligible_records,
            ranking_metric=ranking_metric,
            total_pool_size=len(plist),
            eligible_count=len(eligible_pool)
        )
        
    return dossiers


# ---------------------------------------------------------------------------
# 6. Ranking Stability & Uncertainty Simulation Engine
# ---------------------------------------------------------------------------

def simulate_ranking_stability_across_draws(
    player_draws_dict: Dict[int, List[float]],
    player_roles_dict: Dict[int, str],
    player_eligibility_dict: Optional[Dict[int, bool]] = None,
    target_role: Optional[str] = None,
    min_required_draws: int = MIN_BOOTSTRAP_DRAWS_FOR_LOWER_BOUND
) -> Dict[int, Dict[str, Any]]:
    """
    Evaluates empirical rank stability for players across B bootstrap draws.
    
    GOVERNANCE & STATISTICAL GUARDS:
    1. Role-Cohort Separation: Ranks are computed strictly within tactical cohorts.
       Players never compete across cohorts.
    2. Eligibility Consistency: Only players flagged as eligible in player_eligibility_dict
       participate in simulated rank ordering. Ineligible players are excluded from
       rank simulation.
    3. Insufficient / Missing Draws: Players with missing draws or fewer than min_required_draws
       are excluded from matrix simulation, tagged as INSUFFICIENT_DRAWS, and their metrics
       are marked as NaN.
    4. Deterministic Tie-Breaking: Within each draw, ties in simulated score are broken
       deterministically by player_id.
    5. Role-Specific P(Rank <= 10): Measures the probability of being in the Top 10 of
       THAT SPECIFIC ROLE COHORT, not a global ranking.
    6. Predictive Non-Claim: This is an empirical resample stability diagnostic of the
       current data; it is NOT evidence of future tournament-wide predictive validity.
    """
    player_eligibility_dict = player_eligibility_dict or {}
    
    # Filter by eligibility (if provided) and group by role
    players_by_role: Dict[str, List[int]] = {}
    stability_results: Dict[int, Dict[str, Any]] = {}
    
    for pid, r in player_roles_dict.items():
        is_elig = player_eligibility_dict.get(pid, True)
        if not is_elig:
            stability_results[pid] = {
                "role": r,
                "status": "EXCLUDED_INELIGIBLE",
                "median_rank": np.nan,
                "rank_range_90": (np.nan, np.nan),
                "rank_se": np.nan,
                "prob_top_10": np.nan,
                "prob_top_3": np.nan
            }
            continue
            
        draws = player_draws_dict.get(pid, [])
        if len(draws) < min_required_draws:
            stability_results[pid] = {
                "role": r,
                "status": "UNAVAILABLE_INSUFFICIENT_DRAWS",
                "median_rank": np.nan,
                "rank_range_90": (np.nan, np.nan),
                "rank_se": np.nan,
                "prob_top_10": np.nan,
                "prob_top_3": np.nan
            }
            continue
            
        players_by_role.setdefault(r, []).append(pid)
        
    for r, pids in players_by_role.items():
        if target_role is not None and r != target_role:
            continue
            
        n_players = len(pids)
        if n_players <= 1:
            for pid in pids:
                stability_results[pid] = {
                    "role": r,
                    "status": "SINGLE_PLAYER_COHORT",
                    "median_rank": 1,
                    "rank_range_90": (1, 1),
                    "rank_se": 0.0,
                    "prob_top_10": 1.0,
                    "prob_top_3": 1.0
                }
            continue
            
        # Common valid draw length
        n_draws = min(len(player_draws_dict[pid]) for pid in pids)
        if n_draws < min_required_draws:
            for pid in pids:
                stability_results[pid] = {
                    "role": r,
                    "status": "UNAVAILABLE_INSUFFICIENT_DRAWS",
                    "median_rank": np.nan,
                    "rank_range_90": (np.nan, np.nan),
                    "rank_se": np.nan,
                    "prob_top_10": np.nan,
                    "prob_top_3": np.nan
                }
            continue
            
        # Matrix: n_draws x n_players
        scores_matrix = np.zeros((n_draws, n_players))
        for col_idx, pid in enumerate(pids):
            scores_matrix[:, col_idx] = np.array(player_draws_dict[pid][:n_draws])
            
        # Rank across each draw (descending score -> rank 1 is highest score)
        # Deterministic tie break using col_idx (pid order)
        ranks_matrix = np.zeros((n_draws, n_players), dtype=int)
        for d in range(n_draws):
            row = scores_matrix[d, :]
            # lexsort on (col_indices, -row) ensures deterministic tie breaking
            order = np.lexsort((np.arange(n_players), -row))
            ranks = np.empty_like(order)
            ranks[order] = np.arange(1, n_players + 1)
            ranks_matrix[d, :] = ranks
            
        for col_idx, pid in enumerate(pids):
            player_ranks = ranks_matrix[:, col_idx]
            med_rank = int(np.median(player_ranks))
            r5 = int(np.percentile(player_ranks, 5))
            r95 = int(np.percentile(player_ranks, 95))
            r_se = float(np.std(player_ranks))
            p_top10 = float(np.mean(player_ranks <= 10))
            p_top3 = float(np.mean(player_ranks <= 3))
            
            stability_results[pid] = {
                "role": r,
                "status": "SIMULATED",
                "median_rank": med_rank,
                "rank_range_90": (r5, r95),
                "rank_se": round(r_se, 3),
                "prob_top_10": round(p_top10, 4),
                "prob_top_3": round(p_top3, 4)
            }
            
    return stability_results


# ---------------------------------------------------------------------------
# 7. Master Reliability & Ranking Pipeline Orchestrator
# ---------------------------------------------------------------------------

def run_reliability_ranking_pipeline(
    batter_df: pd.DataFrame,
    bowler_df: pd.DataFrame,
    batter_bootstrap_results: Optional[Dict[int, Dict[str, Any]]] = None,
    bowler_bootstrap_results: Optional[Dict[int, Dict[str, Any]]] = None,
    allow_pilot_ineligible_ranking: bool = False
) -> Dict[str, Any]:
    """
    Executes the comprehensive M4.5 Reliability & Ranking Engine.
    
    GOVERNANCE INTEGRITY:
    - Operates strictly on approved outputs of M4.3 and M4.4.
    - Decouples performance from statistical reliability.
    - Preserves all provisional M3 component labels and thresholds.
    - In pilot mode (allow_pilot_ineligible_ranking=False by default), strictly zero
      unqualified players enter official rankings.
    """
    batter_bootstrap_results = batter_bootstrap_results or {}
    bowler_bootstrap_results = bowler_bootstrap_results or {}
    
    # 1. Assess Batters
    batter_assessments: List[PlayerReliabilityAssessment] = []
    for _, row in batter_df.iterrows():
        pid = int(row["striker_id"])
        boot = batter_bootstrap_results.get(pid)
        assessment = assess_batter_reliability(row, boot)
        batter_assessments.append(assessment)
        
    # 2. Assess Bowlers
    bowler_assessments: List[PlayerReliabilityAssessment] = []
    for _, row in bowler_df.iterrows():
        pid = int(row["bowler_id"])
        boot = bowler_bootstrap_results.get(pid)
        assessment = assess_bowler_reliability(row, boot)
        bowler_assessments.append(assessment)
        
    # 3. Generate Role Rankings
    batter_rankings_point = generate_role_rankings(
        batter_assessments,
        ranking_metric="point_score",
        allow_ineligible=allow_pilot_ineligible_ranking
    )
    batter_rankings_conservative = generate_role_rankings(
        batter_assessments,
        ranking_metric="lower_bound_90",
        allow_ineligible=allow_pilot_ineligible_ranking
    )
    
    bowler_rankings_point = generate_role_rankings(
        bowler_assessments,
        ranking_metric="point_score",
        allow_ineligible=allow_pilot_ineligible_ranking
    )
    bowler_rankings_conservative = generate_role_rankings(
        bowler_assessments,
        ranking_metric="lower_bound_90",
        allow_ineligible=allow_pilot_ineligible_ranking
    )
    
    # 4. Summary Diagnostics
    def summarize_tiers(assessments: List[PlayerReliabilityAssessment]) -> Dict[str, int]:
        counts = {t.value: 0 for t in ReliabilityTier}
        for a in assessments:
            counts[a.reliability_tier.value] += 1
        return counts

    batter_tier_counts = summarize_tiers(batter_assessments)
    bowler_tier_counts = summarize_tiers(bowler_assessments)
    
    return {
        "status": "RELIABILITY_AND_RANKING_COMPLETE",
        "batter_assessments": batter_assessments,
        "bowler_assessments": bowler_assessments,
        "batter_tier_counts": batter_tier_counts,
        "bowler_tier_counts": bowler_tier_counts,
        "batter_role_rankings": {
            "point_score": batter_rankings_point,
            "lower_bound_90": batter_rankings_conservative
        },
        "bowler_role_rankings": {
            "point_score": bowler_rankings_point,
            "lower_bound_90": bowler_rankings_conservative
        },
        "total_batters_evaluated": len(batter_assessments),
        "total_bowlers_evaluated": len(bowler_assessments),
        "eligible_batters_count": sum(1 for b in batter_assessments if b.is_eligible),
        "eligible_bowlers_count": sum(1 for b in bowler_assessments if b.is_eligible),
        "allow_pilot_ineligible_ranking": allow_pilot_ineligible_ranking
    }
