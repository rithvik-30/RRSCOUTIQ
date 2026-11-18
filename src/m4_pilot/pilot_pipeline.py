"""
RR ScoutIQ - Module M4.6: Integrated Controlled Pilot Pipeline
==============================================================
Orchestrates the entire controlled pilot workflow across M4.1 through M4.5:
M4.1 Input Validation -> M4.2 Match State Engine -> M4.3 Batter Engine ->
M4.4 Bowler Engine -> M4.5 Reliability & Ranking Engine.

Produces reproducible pilot datasets, explainable player diagnostic profiles,
match-level causal trace examples, and summary audit metrics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import math
import numpy as np
import pandas as pd

from src.m4_pilot.input_validation import load_and_validate_pilot_data, verify_dataset_immutability
from src.m4_pilot.match_state_engine import reconstruct_pre_delivery_match_state
from src.m4_pilot.batter_engine import (
    run_batter_performance_pipeline,
    compute_delivery_xra,
    assign_batter_roles,
    ROLE_TOP_ORDER_MAX_OVER,
    ROLE_MIDDLE_ORDER_MAX_OVER
)
from src.m4_pilot.bowler_engine import (
    run_bowler_performance_pipeline,
    compute_delivery_xrs,
    assign_bowler_roles
)
from src.m4_pilot.reliability_engine import (
    run_reliability_ranking_pipeline,
    PlayerReliabilityAssessment,
    RoleRankingDossier,
    ReliabilityTier
)


@dataclass
class MatchDeliveryExplainabilityTrace:
    """Traceable delivery-level causal explainability record."""
    match_id: int
    innings: int
    overid: int
    over_ball_num: int
    pre_score: int
    pre_wickets_lost: int
    pre_legal_balls: int
    pre_match_phase: str
    pre_dli: float
    pre_pressure_tier: str
    is_dli_valid: bool
    dli_exclusion_reason: Optional[str]
    striker_id: int
    striker_name: str
    batter_role: str
    bowler_id: int
    bowler_name: str
    bowler_role: str
    runs: int
    bat_runs: int
    bowler_debit_runs: int
    is_legal_delivery: bool
    is_four: int
    is_six: int
    is_wicket: int
    dismissal_type: Optional[str]
    delivery_xra: float
    delivery_xrs: float
    included_in_pressure_metrics: bool
    inclusion_rationale: str


@dataclass
class ControlledPilotReport:
    """Consolidated summary output of the M4 Controlled Pilot."""
    total_matches_processed: int
    total_deliveries_processed: int
    match_ids: List[int]
    total_batters_evaluated: int
    total_bowlers_evaluated: int
    eligible_batters_count: int
    eligible_bowlers_count: int
    batter_tier_distribution: Dict[str, int]
    bowler_tier_distribution: Dict[str, int]
    pressure_deliveries_count: int
    pressure_percentage: float
    raw_hashes_verified: bool
    batter_diagnostics: List[Dict[str, Any]]
    bowler_diagnostics: List[Dict[str, Any]]
    match_traces: List[MatchDeliveryExplainabilityTrace]
    batter_role_rankings: Dict[str, Any]
    bowler_role_rankings: Dict[str, Any]


def generate_match_level_explainability_traces(
    enriched_deliveries_df: pd.DataFrame,
    sample_deliveries: Optional[List[Tuple[int, int, int, int]]] = None
) -> List[MatchDeliveryExplainabilityTrace]:
    """
    Extracts traceable delivery-level causal records demonstrating pre-delivery state,
    DLI, xRA, xRS, and inclusion/exclusion logic without outcome leakage.
    """
    traces = []
    
    # If no specific deliveries requested, pick illustrative samples across diverse matches
    if sample_deliveries is None:
        sample_deliveries = [
            (14094, 1, 9, 2),   # Rayudu vs Narine, Middle overs, Tier 3: High, DLI 1.35
            (14094, 1, 9, 5),   # Jadeja vs Narine, Wicket just fell, DLI 1.51
            (20181, 1, 13, 3),  # Gaikwad boundary vs Little, Tier 3: High, xRA +2.6
            (40725, 1, 13, 6),  # Stubbs vs Archer, Tier 3: High, DLI 1.42
            (40725, 1, 13, 7),  # Porel vs Archer, Tier 3: High, DLI 1.43
            (40725, 3, 1, 1),   # Super Over delivery, fixed DLI 3.50, Tier 4: Extreme
        ]
        
    for m_id, inn, ov, b_num in sample_deliveries:
        sub = enriched_deliveries_df[
            (enriched_deliveries_df["match_id"] == m_id) &
            (enriched_deliveries_df["innings"] == inn) &
            (enriched_deliveries_df["overid"] == ov) &
            (enriched_deliveries_df["over_ball_num"] == b_num)
        ]
        if len(sub) == 0:
            continue
            
        r = sub.iloc[0]
        
        # Determine inclusion rationale
        dli = float(r.get("pre_dli", 1.0))
        valid = bool(r.get("is_dli_valid", True))
        tier = str(r.get("pre_pressure_tier", "Tier 2: Medium"))
        is_legal = bool(r.get("ext_is_legal_delivery", True))
        
        is_high_p = (dli >= 1.35) and valid
        
        if not valid:
            rationale = f"Excluded: DLI marked invalid ({r.get('dli_exclusion_reason', 'Unspecified')})."
        elif is_high_p:
            rationale = f"Included in High-Pressure Scope: Pre-delivery DLI={dli:.2f} >= 1.35 ({tier})."
        else:
            rationale = f"Included in Baseline Normal Scope: Pre-delivery DLI={dli:.2f} < 1.35 ({tier})."
            
        trace = MatchDeliveryExplainabilityTrace(
            match_id=int(r["match_id"]),
            innings=int(r["innings"]),
            overid=int(r["overid"]),
            over_ball_num=int(r["over_ball_num"]),
            pre_score=int(r.get("pre_score", 0)),
            pre_wickets_lost=int(r.get("pre_wickets_lost", 0)),
            pre_legal_balls=int(r.get("pre_legal_balls_bowled", 0)),
            pre_match_phase=str(r.get("pre_match_phase", "Middle")),
            pre_dli=round(dli, 4),
            pre_pressure_tier=tier,
            is_dli_valid=valid,
            dli_exclusion_reason=r.get("dli_exclusion_reason"),
            striker_id=int(r["striker_id"]),
            striker_name=str(r.get("striker_name", "")),
            batter_role=str(r.get("innings_role", r.get("primary_role", "Middle Order"))),
            bowler_id=int(r["bowler_id"]),
            bowler_name=str(r.get("bowler_name", "")),
            bowler_role=str(r.get("bowler_primary_role", "Middle Enforcer")),
            runs=int(r["runs"]),
            bat_runs=int(r.get("bat_runs", r["runs"])),
            bowler_debit_runs=int(r.get("ext_bowler_debit_runs", r["runs"])),
            is_legal_delivery=is_legal,
            is_four=int(r.get("is_four", 0)),
            is_six=int(r.get("is_six", 0)),
            is_wicket=int(r.get("is_wicket", 0)),
            dismissal_type=r.get("dismissal_type"),
            delivery_xra=round(float(r.get("xra", 0.0)), 4),
            delivery_xrs=round(float(r.get("xrs", 0.0)), 4),
            included_in_pressure_metrics=is_high_p,
            inclusion_rationale=rationale
        )
        traces.append(trace)
        
    return traces


def run_controlled_pilot_pipeline(
    run_bootstrap: bool = False,
    allow_pilot_ineligible_ranking: bool = False
) -> ControlledPilotReport:
    """
    Master entry point executing the entire M4 Controlled Pilot workflow:
    M4.1 -> M4.2 -> M4.3 -> M4.4 -> M4.5.
    
    Returns a unified ControlledPilotReport encapsulating all validated pilot outputs.
    """
    # -----------------------------------------------------------------------
    # Step 1: M4.1 Input Validation
    # -----------------------------------------------------------------------
    raw_df, val_report = load_and_validate_pilot_data()
    raw_hashes_ok, diffs = verify_dataset_immutability()
    if not raw_hashes_ok:
        raise ValueError(f"Dataset immutability failure in pilot pipeline: {diffs}")

    # -----------------------------------------------------------------------
    # Step 2: M4.2 Pre-Delivery Match State Reconstruction
    # -----------------------------------------------------------------------
    state_df = reconstruct_pre_delivery_match_state(raw_df)

    # -----------------------------------------------------------------------
    # Step 3: M4.3 Batter Performance Engine
    # -----------------------------------------------------------------------
    batter_results = run_batter_performance_pipeline(state_df, run_bootstrap=run_bootstrap)
    batter_perf_df = batter_results["batter_performance_df"]
    batter_boot_results = batter_results.get("bootstrap_results", {})
    xra_df = batter_results["enriched_deliveries_with_xra"]

    # -----------------------------------------------------------------------
    # Step 4: M4.4 Bowler Performance Engine
    # -----------------------------------------------------------------------
    # Consume deliveries enriched with match state and xra
    bowler_results = run_bowler_performance_pipeline(xra_df, run_bootstrap=run_bootstrap)
    bowler_perf_df = bowler_results["bowler_performance_df"]
    bowler_boot_results = bowler_results.get("bootstrap_results", {})
    xrs_df = bowler_results["enriched_deliveries_with_xrs"]

    # -----------------------------------------------------------------------
    # Step 5: M4.5 Reliability & Ranking Engine
    # -----------------------------------------------------------------------
    reliability_results = run_reliability_ranking_pipeline(
        batter_df=batter_perf_df,
        bowler_df=bowler_perf_df,
        batter_bootstrap_results=batter_boot_results,
        bowler_bootstrap_results=bowler_boot_results,
        allow_pilot_ineligible_ranking=allow_pilot_ineligible_ranking
    )

    # -----------------------------------------------------------------------
    # Step 6: Diagnostic Formatting & Match Traces
    # -----------------------------------------------------------------------
    batter_diagnostics = []
    for a in reliability_results["batter_assessments"]:
        # Find raw performance row
        p_row = batter_perf_df[batter_perf_df["striker_id"] == a.player_id].iloc[0]
        
        lower_bound_val = a.ci_percentile_90[0]
        lower_bound_status = (
            "AVAILABLE" if not math.isnan(lower_bound_val)
            else "UNAVAILABLE_INSUFFICIENT_BOOTSTRAP_DRAWS"
        )
        
        b_diag = {
            "player_id": a.player_id,
            "player_name": a.player_name,
            "primary_role": a.primary_role,
            "bppi_score": round(a.point_score, 4),
            "component_z_scores": {
                "z_xra": round(float(p_row.get("z_xra", 0.0)), 3),
                "z_delta_sr": round(float(p_row.get("z_delta_sr", 0.0)), 3),
                "z_delta_bnd": round(float(p_row.get("z_delta_bnd", 0.0)), 3),
                "z_delta_dot": round(float(p_row.get("z_delta_dot", 0.0)), 3),
                "z_delta_survival": round(float(p_row.get("z_delta_survival", 0.0)), 3),
            },
            "attribution_positives": a.attribution_positives,
            "attribution_negatives": a.attribution_negatives,
            "innings_count": a.innings_count,
            "total_balls_faced": a.total_balls,
            "pressure_balls": a.pressure_balls,
            "reliability_tier": a.reliability_tier.value,
            "reliability_note": a.reliability_note,
            "is_eligible": a.is_eligible,
            "exclusion_reasons": a.exclusion_reasons,
            "bootstrap_se": a.bootstrap_se,
            "ci_percentile_90": a.ci_percentile_90,
            "credible_interval_90": a.credible_interval_90,
            "lower_bound_90": lower_bound_val,
            "lower_bound_status": lower_bound_status,
            "data_quality_warnings": (
                ["INSUFFICIENT_SAMPLE_SIZE_FOR_COMPETITION_EVALUATION"] if not a.is_eligible else []
            )
        }
        batter_diagnostics.append(b_diag)

    bowler_diagnostics = []
    for a in reliability_results["bowler_assessments"]:
        p_row = bowler_perf_df[bowler_perf_df["bowler_id"] == a.player_id].iloc[0]
        
        lower_bound_val = a.ci_percentile_90[0]
        lower_bound_status = (
            "AVAILABLE" if not math.isnan(lower_bound_val)
            else "UNAVAILABLE_INSUFFICIENT_BOOTSTRAP_DRAWS"
        )
        
        bw_diag = {
            "player_id": a.player_id,
            "player_name": a.player_name,
            "primary_role": a.primary_role,
            "ppbi_score": round(a.point_score, 4),
            "component_z_scores": {
                "z_xrs": round(float(p_row.get("z_xrs", 0.0)), 3),
                "z_delta_econ": round(float(p_row.get("z_delta_econ", 0.0)), 3),
                "z_delta_wkt": round(float(p_row.get("z_delta_wkt", 0.0)), 3),
                "z_delta_dot": round(float(p_row.get("z_delta_dot", 0.0)), 3),
                "z_delta_bnd_con": round(float(p_row.get("z_delta_bnd_con", 0.0)), 3),
            },
            "attribution_positives": a.attribution_positives,
            "attribution_negatives": a.attribution_negatives,
            "innings_count": a.innings_count,
            "total_legal_balls": a.total_balls,
            "pressure_legal_balls": a.pressure_balls,
            "reliability_tier": a.reliability_tier.value,
            "reliability_note": a.reliability_note,
            "is_eligible": a.is_eligible,
            "exclusion_reasons": a.exclusion_reasons,
            "bootstrap_se": a.bootstrap_se,
            "ci_percentile_90": a.ci_percentile_90,
            "credible_interval_90": a.credible_interval_90,
            "lower_bound_90": lower_bound_val,
            "lower_bound_status": lower_bound_status,
            "data_quality_warnings": (
                ["INSUFFICIENT_SAMPLE_SIZE_FOR_COMPETITION_EVALUATION"] if not a.is_eligible else []
            )
        }
        bowler_diagnostics.append(bw_diag)

    # Generate match-level explainability traces
    match_traces = generate_match_level_explainability_traces(xrs_df)

    # Compute overall pilot metrics
    n_deliveries = len(xrs_df)
    n_pressure = int((xrs_df["pre_dli"] >= 1.35).sum())
    p_pct = round(n_pressure / n_deliveries * 100.0, 2) if n_deliveries > 0 else 0.0

    return ControlledPilotReport(
        total_matches_processed=len(state_df["match_id"].unique()),
        total_deliveries_processed=n_deliveries,
        match_ids=sorted(state_df["match_id"].unique().tolist()),
        total_batters_evaluated=len(batter_diagnostics),
        total_bowlers_evaluated=len(bowler_diagnostics),
        eligible_batters_count=reliability_results["eligible_batters_count"],
        eligible_bowlers_count=reliability_results["eligible_bowlers_count"],
        batter_tier_distribution=reliability_results["batter_tier_counts"],
        bowler_tier_distribution=reliability_results["bowler_tier_counts"],
        pressure_deliveries_count=n_pressure,
        pressure_percentage=p_pct,
        raw_hashes_verified=raw_hashes_ok,
        batter_diagnostics=batter_diagnostics,
        bowler_diagnostics=bowler_diagnostics,
        match_traces=match_traces,
        batter_role_rankings=reliability_results["batter_role_rankings"],
        bowler_role_rankings=reliability_results["bowler_role_rankings"]
    )
