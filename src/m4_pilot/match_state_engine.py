"""
RR ScoutIQ - Module M4.2: Pre-Delivery Match-State Engine
=========================================================

Authoritative match-state reconstruction engine for Milestone M4 Controlled Pilot.
Reconstructs the cricket match context available strictly BEFORE each delivery is released.
Implements causal shift-1 anti-leakage invariants, pressure metrics (CRR, RRR, DLI),
phase boundaries, and explicit eligibility/exclusion classifications.

Evidence Level: IMPLEMENTATION CORRECTNESS
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Authoritative Domain & Cricket Constants (MCC Laws & M3 Specification)
# ---------------------------------------------------------------------------

REGULATION_OVERS_PER_INNINGS: int = 20
REGULATION_LEGAL_BALLS_PER_INNINGS: int = 120
INITIAL_WICKETS_IN_HAND: int = 10
SUPER_OVER_FIXED_DLI: float = 3.50

# Historical empirical baseline scoring rates by match phase (M3 Specification)
PHASE_PAR_CRR: Dict[str, float] = {
    "Powerplay": 8.15,  # Overs 1-6 (legal balls 0-35)
    "Middle": 8.00,     # Overs 7-15 (legal balls 36-89)
    "Death": 9.30       # Overs 16-20 (legal balls 90-119)
}

# DLI Clamping bounds (M3 Task 2 & M4.2 Specification)
DLI_CHASE_MIN: float = 0.10
DLI_CHASE_MAX: float = 5.00
DLI_SETTING_MIN: float = 0.20
DLI_SETTING_MAX: float = 3.50

# Pressure tier thresholds (Approved M3 Recalibrated Master Specification)
# Tier 1: Low Leverage (DLI < 0.90)
# Tier 2: Medium / Standard Leverage (0.90 <= DLI < 1.35)
# Tier 3: High Leverage (1.35 <= DLI < 2.25)
# Tier 4: Extreme / Maximum Leverage (DLI >= 2.25)
PRESSURE_TIER_1_CUTOFF: float = 0.90
PRESSURE_TIER_2_CUTOFF: float = 1.35
PRESSURE_TIER_3_CUTOFF: float = 2.25


# ---------------------------------------------------------------------------
# Pure Helper Functions (Stateless & Mathematically Deterministic)
# ---------------------------------------------------------------------------

def determine_match_phase(overid: int) -> str:
    """
    Assigns match phase based on 1-indexed over number:
    - Powerplay: Overs 1–6 (overid 1..6)
    - Middle: Overs 7–15 (overid 7..15)
    - Death: Overs 16–20 (overid 16..20)
    """
    if overid <= 6:
        return "Powerplay"
    elif overid <= 15:
        return "Middle"
    else:
        return "Death"


def compute_phi_setting(t: int) -> float:
    """
    Computes continuous power-law time progression factor for setting innings:
    Phi(t) = 0.80 + 0.70 * (t / 120)^1.20
    Strictly convex superlinear power function (M3 Task 1 correction).
    """
    t_clamped = max(0, min(REGULATION_LEGAL_BALLS_PER_INNINGS, t))
    return 0.80 + 0.70 * ((t_clamped / 120.0) ** 1.20)


def compute_dli_chase(rrr: float, phase: str, wkt_hand: int, balls_rem: int) -> float:
    """
    Computes Innings 2 chase Delivery Leverage Index (Eq. 1 in M3):
    DLI = Clamp[ (RRR / CRR_phase) * (10 / (wkt_hand + 1))^0.5 * (1 + 24 / (balls_rem + 12))^0.5, 0.10, 5.00 ]
    """
    crr_par = PHASE_PAR_CRR.get(phase, 8.00)
    rrr_factor = max(0.0, rrr) / crr_par
    wkt_factor = (10.0 / (max(1, wkt_hand) + 1.0)) ** 0.50
    time_factor = (1.0 + (24.0 / (max(1, balls_rem) + 12.0))) ** 0.50
    raw_dli = rrr_factor * wkt_factor * time_factor
    return max(DLI_CHASE_MIN, min(DLI_CHASE_MAX, raw_dli))


def compute_dli_setting(t: int, wkt_hand: int, crr: Optional[float], phase: str) -> float:
    """
    Computes Innings 1 setting Delivery Leverage Index (Eq. 2 in M3):
    DLI = Clamp[ Phi(t) * (10 / (wkt_hand + 1))^0.60 * (1 + stag)^0.50, 0.20, 3.50 ]
    where stag = max(0, (CRR_phase - CRR) / 6.0) if CRR is defined (t >= 6).
    """
    phi_t = compute_phi_setting(t)
    wkt_factor = (10.0 / (max(1, wkt_hand) + 1.0)) ** 0.60
    crr_par = PHASE_PAR_CRR.get(phase, 8.00)

    if crr is not None and not math.isnan(crr) and t >= 6:
        stagnation = max(0.0, (crr_par - crr) / 6.0)
    else:
        stagnation = 0.0

    stag_factor = (1.0 + stagnation) ** 0.50
    raw_dli = phi_t * wkt_factor * stag_factor
    return max(DLI_SETTING_MIN, min(DLI_SETTING_MAX, raw_dli))


def classify_pressure_tier(dli: float) -> str:
    """
    Classifies continuous DLI into four discrete leverage tiers using the approved M3 recalibrated thresholds:
    - Tier 1: Low Leverage (DLI < 0.90)
    - Tier 2: Medium / Standard Leverage (0.90 <= DLI < 1.35)
    - Tier 3: High Leverage (1.35 <= DLI < 2.25)
    - Tier 4: Extreme / Maximum Leverage (DLI >= 2.25)
    """
    if dli < PRESSURE_TIER_1_CUTOFF:
        return "Tier 1: Low"
    elif dli < PRESSURE_TIER_2_CUTOFF:
        return "Tier 2: Medium"
    elif dli < PRESSURE_TIER_3_CUTOFF:
        return "Tier 3: High"
    else:
        return "Tier 4: Extreme"


# ---------------------------------------------------------------------------
# Core Engine: Causal Shift-1 Match-State Reconstruction
# ---------------------------------------------------------------------------

def reconstruct_pre_delivery_match_state(
    deliveries_df: pd.DataFrame,
    matches_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Reconstructs pre-delivery match context for every delivery in the input DataFrame.
    
    CRITICAL ANTI-LEAKAGE ARCHITECTURE:
    - Data is strictly partitioned by (match_id, innings).
    - Deliveries are ordered by stored sequence (overid, over_ball_num, innings_ball_num).
    - All state variables for delivery t are computed strictly from cumulative outcomes of deliveries < t.
    - Uses canonical run attribution contract established in M4.1:
      * Team runs: ext_delivery_total_runs
      * Bowler debit: ext_bowler_debit_runs
      * Legal balls: ext_is_legal_delivery
      * Batter balls faced: ext_batter_balls_faced
      * Team wickets: is_wicket == True and not ext_is_retired_hurt
    """
    orig_index = deliveries_df.index
    df = deliveries_df.copy()
    df["__orig_order__"] = np.arange(len(df))

    # Pre-sort to guarantee reproducible delivery progression
    sort_cols = ["match_id", "innings", "overid", "over_ball_num", "innings_ball_num"]
    df = df.sort_values(sort_cols).reset_index(drop=True)

    # Pre-compute Match-level targets for Innings 2 chases
    # Target = First innings total score + 1
    inn1_totals: Dict[int, int] = {}
    for mid, grp in df[df["innings"] == 1].groupby("match_id"):
        inn1_totals[int(mid)] = int(grp["ext_delivery_total_runs"].sum())

    # Build match metadata lookup (for DLS revised targets and revised overs)
    dls_revised_targets: Dict[int, float] = {}
    revised_overs_lookup: Dict[int, bool] = {}
    if matches_df is not None:
        for _, row in matches_df.iterrows():
            m_id = int(row["match_id"])
            if pd.notna(row.get("revised_target")):
                dls_revised_targets[m_id] = float(row["revised_target"])
            has_revised_overs = (
                pd.notna(row.get("first_inn_revised_overs")) or
                pd.notna(row.get("second_inn_revised_overs"))
            )
            revised_overs_lookup[m_id] = has_revised_overs

    # Allocate output pre-delivery feature arrays
    n = len(df)
    pre_score = np.zeros(n, dtype=int)
    pre_wickets_lost = np.zeros(n, dtype=int)
    pre_wickets_in_hand = np.zeros(n, dtype=int)
    pre_legal_balls_bowled = np.zeros(n, dtype=int)
    pre_legal_balls_rem = np.zeros(n, dtype=int)
    pre_crr = [np.nan] * n
    pre_target = [np.nan] * n
    pre_runs_required = [np.nan] * n
    pre_rrr = [np.nan] * n
    pre_match_phase = [""] * n
    pre_dli = np.zeros(n, dtype=float)
    pre_pressure_tier = [""] * n
    is_dli_valid = [True] * n
    dli_exclusion_reason = [""] * n
    is_super_over = np.zeros(n, dtype=bool)

    # Process each match-innings partition independently
    grouped = df.groupby(["match_id", "innings"], sort=False)

    for (match_id, innings), group_indices in grouped.groups.items():
        match_id = int(match_id)
        innings = int(innings)
        idx_list = list(group_indices)

        # Innings classification
        is_so = innings > 2
        is_chase = (innings == 2)
        is_setting = (innings == 1)

        # Check DLS and shortened-innings status
        has_dls_target = match_id in dls_revised_targets
        has_shortened_overs = revised_overs_lookup.get(match_id, False)

        # Determine target for chase
        target_val = None
        if is_chase:
            if has_dls_target:
                target_val = int(dls_revised_targets[match_id])
            elif match_id in inn1_totals:
                target_val = inn1_totals[match_id] + 1

        # Running pre-delivery state variables (start at zero for ball 1 of innings)
        curr_score = 0
        curr_wickets = 0
        curr_legal_balls = 0

        for row_idx in idx_list:
            row = df.iloc[row_idx]

            # 1. State assignment for delivery t (BEFORE processing delivery t)
            w_in_hand = max(0, INITIAL_WICKETS_IN_HAND - curr_wickets)
            b_rem = max(0, REGULATION_LEGAL_BALLS_PER_INNINGS - curr_legal_balls) if not is_so else max(0, 6 - curr_legal_balls)
            phase = determine_match_phase(int(row["overid"])) if not is_so else "Super Over"

            # Pre-delivery CRR (defined once >= 6 legal balls bowled)
            if curr_legal_balls >= 6:
                crr_val = curr_score / (curr_legal_balls / 6.0)
            else:
                crr_val = np.nan

            # Pre-delivery target, runs required, and RRR
            runs_req_val = np.nan
            rrr_val = np.nan
            if is_chase and target_val is not None:
                runs_req_val = max(0, target_val - curr_score)
                # Compute RRR floored at 1 ball remaining to avoid zero-division
                effective_b_rem = max(1, b_rem)
                rrr_val = runs_req_val / (effective_b_rem / 6.0)

            # DLI calculation and validity classification
            dli_val = 1.00
            valid_flag = True
            excl_reason = ""

            if is_so:
                # Super Over: Deterministic fixed maximum leverage (M3 Task 2)
                dli_val = SUPER_OVER_FIXED_DLI
                valid_flag = True
                excl_reason = "Super Over: Fixed leverage 3.50"
            elif has_dls_target and is_chase:
                # Rain-affected chase with revised target: excluded from continuous RRR modeling (M3 Task 2)
                dli_val = 1.00
                valid_flag = False
                excl_reason = "DLS Revised Target: Excluded from continuous RRR chase DLI"
            elif has_shortened_overs:
                # Shortened-innings match: excluded from standard 20-over phase benchmarks
                dli_val = 1.00
                valid_flag = False
                excl_reason = "Shortened Match: Excluded from regulation 20-over phase benchmarks"
            elif is_chase:
                # Standard Innings 2 chase
                effective_b_rem = max(1, b_rem)
                dli_val = compute_dli_chase(rrr_val if not math.isnan(rrr_val) else 8.0, phase, w_in_hand, effective_b_rem)
            elif is_setting:
                # Standard Innings 1 setting
                dli_val = compute_dli_setting(curr_legal_balls, w_in_hand, crr_val, phase)
            else:
                dli_val = 1.00
                valid_flag = False
                excl_reason = f"Unclassified innings {innings}"

            # Assign to output arrays
            pre_score[row_idx] = curr_score
            pre_wickets_lost[row_idx] = curr_wickets
            pre_wickets_in_hand[row_idx] = w_in_hand
            pre_legal_balls_bowled[row_idx] = curr_legal_balls
            pre_legal_balls_rem[row_idx] = b_rem
            pre_crr[row_idx] = crr_val
            pre_target[row_idx] = target_val if target_val is not None else np.nan
            pre_runs_required[row_idx] = runs_req_val
            pre_rrr[row_idx] = rrr_val
            pre_match_phase[row_idx] = phase
            pre_dli[row_idx] = dli_val
            pre_pressure_tier[row_idx] = classify_pressure_tier(dli_val)
            is_dli_valid[row_idx] = valid_flag
            dli_exclusion_reason[row_idx] = excl_reason
            is_super_over[row_idx] = is_so

            # 2. State transition for delivery t+1 (INCORPORATE delivery t outcome)
            # Runs: ext_delivery_total_runs (canonical contract)
            del_runs = int(row["ext_delivery_total_runs"])
            curr_score += del_runs

            # Legal ball: ext_is_legal_delivery (canonical contract)
            if bool(row["ext_is_legal_delivery"]):
                curr_legal_balls += 1

            # Wicket: is_wicket == True and not retired hurt (Law 25.4.2)
            # Retired out is a valid wicket loss (M2.4 & M4.1)
            is_wkt = bool(row["is_wicket"])
            is_ret_hurt = bool(row.get("ext_is_retired_hurt", False))
            if is_wkt and not is_ret_hurt:
                curr_wickets += 1

    # Attach derived pre-delivery state columns to DataFrame
    df["pre_innings"] = df["innings"]
    df["pre_score"] = pre_score
    df["pre_wickets_lost"] = pre_wickets_lost
    df["pre_wickets_in_hand"] = pre_wickets_in_hand
    df["pre_legal_balls_bowled"] = pre_legal_balls_bowled
    df["pre_legal_balls_rem"] = pre_legal_balls_rem
    df["pre_crr"] = pre_crr
    df["pre_target"] = pre_target
    df["pre_runs_required"] = pre_runs_required
    df["pre_rrr"] = pre_rrr
    df["pre_match_phase"] = pre_match_phase
    df["pre_dli"] = pre_dli
    df["pre_pressure_tier"] = pre_pressure_tier
    df["is_dli_valid"] = is_dli_valid
    df["dli_exclusion_reason"] = dli_exclusion_reason
    df["is_super_over"] = is_super_over

    # Restore original input ordering and index
    df = df.sort_values("__orig_order__").drop(columns=["__orig_order__"])
    df.index = orig_index

    return df


if __name__ == "__main__":
    print("=" * 70)
    print("Running M4.2 Pre-Delivery Match-State Engine...")
    print("=" * 70)
    from src.m4_pilot.input_validation import load_and_validate_pilot_data

    deliveries, val_report = load_and_validate_pilot_data()
    matches_meta = pd.read_csv("data/extracted/matches.csv")

    state_df = reconstruct_pre_delivery_match_state(deliveries, matches_meta)
    print(f"Match-state reconstruction complete: {len(state_df)} deliveries processed.")
    print("\nSample Columns:")
    sample_cols = [
        "match_id", "innings", "overid", "over_ball_num", "striker_name",
        "pre_score", "pre_wickets_lost", "pre_legal_balls_bowled",
        "pre_rrr", "pre_dli", "pre_pressure_tier"
    ]
    print(state_df[sample_cols].head(10).to_string())
    print("\n>>> M4.2 PRE-DELIVERY MATCH-STATE ENGINE EXECUTION SUCCESSFUL <<<")
