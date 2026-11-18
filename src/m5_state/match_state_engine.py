"""
RR ScoutIQ - Module M5.3: Full-Scale Pre-Delivery Match-State Engine
===================================================================

Authoritative match-state reconstruction engine for Milestone M5.3 Full-Scale Pipeline.
Reconstructs the cricket match context available strictly BEFORE each delivery is released
across all 776 approved matches and 179,837 deliveries in the full enriched dataset.

Core Capabilities:
- Causal shift-1 anti-leakage invariants (zero outcome contamination).
- Running score, wickets lost/in-hand, legal balls bowled/remaining.
- Pre-delivery CRR (defined for legal balls >= 6).
- Target reconstruction (Innings 1 total + 1 for regulation chase).
- Pre-delivery RRR floored at 1 ball remaining.
- Match phase assignment (Powerplay, Middle, Death, Super Over, Shortened).
- Approved M3 DLI formulas for Setting and Chase.
- Fixed 3.50 DLI for Super Overs.
- Explicit exclusion classifications for DLS chases and shortened matches.
- Pressure tier categorization (Tier 1 Low, Tier 2 Medium, Tier 3 High, Tier 4 Extreme).

Evidence Level: IMPLEMENTATION CORRECTNESS & REPRODUCIBILITY
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

# DLI Clamping bounds (M3 Master Specification)
DLI_CHASE_MIN: float = 0.10
DLI_CHASE_MAX: float = 5.00
DLI_SETTING_MIN: float = 0.20
DLI_SETTING_MAX: float = 3.50

# Pressure tier thresholds (Approved M3 Recalibrated Master Specification)
PRESSURE_TIER_1_CUTOFF: float = 0.90
PRESSURE_TIER_2_CUTOFF: float = 1.35
PRESSURE_TIER_3_CUTOFF: float = 2.25

# Quarantined match IDs strictly forbidden from processing
QUARANTINED_MATCH_IDS: Set[int] = {32618, 37349, 37352, 46250, 50504}


# ---------------------------------------------------------------------------
# Pure Helper Functions (Stateless & Deterministic)
# ---------------------------------------------------------------------------

def determine_match_phase(overid: int, is_shortened: bool = False, is_super_over: bool = False) -> str:
    """
    Assigns match phase based on cricket rules:
    - Super Over: 'Super Over'
    - Shortened match: 'Shortened Match' (20-over boundaries do not apply)
    - Regulation Powerplay: Overs 1–6 (overid 1..6)
    - Regulation Middle: Overs 7–15 (overid 7..15)
    - Regulation Death: Overs 16–20 (overid 16..20)
    """
    if is_super_over:
        return "Super Over"
    if is_shortened:
        return "Shortened Match"
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
    Strictly convex superlinear power function (M3 Task 1).
    """
    t_clamped = max(0, min(REGULATION_LEGAL_BALLS_PER_INNINGS, t))
    return 0.80 + 0.70 * ((t_clamped / 120.0) ** 1.20)


def compute_dli_chase(rrr: float, phase: str, wkt_hand: int, balls_rem: int) -> float:
    """
    Computes Innings 2 chase Delivery Leverage Index (Eq. 1 in M3):
    DLI = Clamp[ (RRR / CRR_phase) * (10 / (wkt_hand + 1))^0.50 * (1 + 24 / (balls_rem + 12))^0.50, 0.10, 5.00 ]
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


def classify_pressure_tier(dli: Optional[float]) -> Optional[str]:
    """
    Classifies continuous DLI into four discrete leverage tiers using approved M3 thresholds:
    - Tier 1: Low Leverage (DLI < 0.90)
    - Tier 2: Medium / Standard Leverage (0.90 <= DLI < 1.35)
    - Tier 3: High Leverage (1.35 <= DLI < 2.25)
    - Tier 4: Extreme / Maximum Leverage (DLI >= 2.25)

    Returns None for invalid/excluded deliveries (NaN DLI).
    """
    if dli is None or (isinstance(dli, float) and math.isnan(dli)):
        return None
    if dli < PRESSURE_TIER_1_CUTOFF:
        return "Tier 1: Low"
    elif dli < PRESSURE_TIER_2_CUTOFF:
        return "Tier 2: Medium"
    elif dli < PRESSURE_TIER_3_CUTOFF:
        return "Tier 3: High"
    else:
        return "Tier 4: Extreme"


# ---------------------------------------------------------------------------
# Core Engine: Full-Scale Match-State Reconstruction
# ---------------------------------------------------------------------------

class MatchStateEngine:
    """
    Full-scale pre-delivery match state reconstruction engine for Milestone M5.3.
    """

    def __init__(self, matches_df: Optional[pd.DataFrame] = None):
        self.matches_df = matches_df
        self.dls_revised_targets: Dict[int, float] = {}
        self.revised_overs_lookup: Dict[int, bool] = {}
        self._init_match_lookups()

    def _init_match_lookups(self):
        """Builds lookup dictionaries for DLS targets and shortened overs from matches.csv."""
        if self.matches_df is not None:
            for _, row in self.matches_df.iterrows():
                m_id = int(row["match_id"])
                if pd.notna(row.get("revised_target")):
                    self.dls_revised_targets[m_id] = float(row["revised_target"])
                has_revised_overs = (
                    pd.notna(row.get("first_inn_revised_overs")) or
                    pd.notna(row.get("second_inn_revised_overs"))
                )
                self.revised_overs_lookup[m_id] = has_revised_overs

    def reconstruct_match_state(self, deliveries_df: pd.DataFrame) -> pd.DataFrame:
        """
        Reconstructs causal pre-delivery match context across all deliveries.
        Guarantees strict causal ordering and zero outcome leakage.
        """
        # Assert no quarantined matches are present
        present_mids = set(deliveries_df["match_id"].unique())
        quarantined_found = present_mids.intersection(QUARANTINED_MATCH_IDS)
        if quarantined_found:
            raise ValueError(f"Quarantined matches detected in input dataset: {quarantined_found}")

        orig_index = deliveries_df.index
        df = deliveries_df.copy()
        df["__orig_order__"] = np.arange(len(df))

        # Enforce deterministic sequence ordering
        sort_cols = ["match_id", "innings", "overid", "over_ball_num", "innings_ball_num"]
        df = df.sort_values(sort_cols).reset_index(drop=True)

        # Pre-calculate Innings 1 totals for standard regulation chase target
        inn1_totals: Dict[int, int] = {}
        for mid, grp in df[df["innings"] == 1].groupby("match_id"):
            inn1_totals[int(mid)] = int(grp["ext_delivery_total_runs"].sum())

        n = len(df)
        pre_score = np.zeros(n, dtype=int)
        pre_wickets_lost = np.zeros(n, dtype=int)
        pre_wickets_in_hand = np.zeros(n, dtype=int)
        pre_legal_balls_bowled = np.zeros(n, dtype=int)
        pre_legal_balls_rem = np.zeros(n, dtype=int)
        pre_crr = np.full(n, np.nan, dtype=float)
        pre_target = np.full(n, np.nan, dtype=float)
        pre_runs_required = np.full(n, np.nan, dtype=float)
        pre_rrr = np.full(n, np.nan, dtype=float)
        pre_innings_type = [""] * n
        pre_match_phase = [""] * n
        pre_dli = np.full(n, np.nan, dtype=float)
        pre_pressure_tier = [None] * n
        is_dli_valid = np.zeros(n, dtype=bool)
        dli_exclusion_reason = [""] * n
        is_super_over = np.zeros(n, dtype=bool)
        is_shortened_match = np.zeros(n, dtype=bool)
        is_dls_match = np.zeros(n, dtype=bool)

        # Process each (match_id, innings) independently
        grouped = df.groupby(["match_id", "innings"], sort=False)

        for (match_id, innings), group_indices in grouped.groups.items():
            match_id = int(match_id)
            innings = int(innings)
            idx_list = list(group_indices)

            is_so = (innings > 2)
            is_chase = (innings == 2)
            is_setting = (innings == 1)

            has_dls_target = (match_id in self.dls_revised_targets)
            has_shortened_overs = self.revised_overs_lookup.get(match_id, False)

            # Determine chase target
            target_val = None
            if is_chase:
                if has_dls_target:
                    target_val = int(self.dls_revised_targets[match_id])
                elif match_id in inn1_totals:
                    target_val = inn1_totals[match_id] + 1

            # Running state variables for the innings
            curr_score = 0
            curr_wickets = 0
            curr_legal_balls = 0

            inn_type = "Super Over" if is_so else ("Chase" if is_chase else ("Setting" if is_setting else f"Innings_{innings}"))

            for row_idx in idx_list:
                row = df.iloc[row_idx]

                # 1. State assignment for delivery t (BEFORE processing delivery t)
                w_in_hand = max(0, INITIAL_WICKETS_IN_HAND - curr_wickets)
                if is_so:
                    b_rem = max(0, 6 - curr_legal_balls)
                else:
                    b_rem = max(0, REGULATION_LEGAL_BALLS_PER_INNINGS - curr_legal_balls)

                phase = determine_match_phase(int(row["overid"]), is_shortened=has_shortened_overs, is_super_over=is_so)

                # Pre-delivery CRR (defined when legal balls >= 6)
                if curr_legal_balls >= 6:
                    crr_val = curr_score / (curr_legal_balls / 6.0)
                else:
                    crr_val = np.nan

                # Chase metrics
                runs_req_val = np.nan
                rrr_val = np.nan
                if is_chase and target_val is not None:
                    runs_req_val = max(0, target_val - curr_score)
                    if not has_dls_target:
                        effective_b_rem = max(1, b_rem)
                        rrr_val = runs_req_val / (effective_b_rem / 6.0)
                    else:
                        # DLS match without interruption timestamps: RRR excluded
                        rrr_val = np.nan

                # DLI calculation & validity
                dli_val = np.nan
                valid_flag = True
                excl_reason = "VALID_REGULATION"

                if is_so:
                    dli_val = SUPER_OVER_FIXED_DLI
                    valid_flag = True
                    excl_reason = "SUPER_OVER_FIXED"
                elif has_dls_target and is_chase:
                    dli_val = np.nan
                    valid_flag = False
                    excl_reason = "DLS_REVISED_TARGET_UNAVAILABLE_TIMING"
                elif has_shortened_overs:
                    dli_val = np.nan
                    valid_flag = False
                    excl_reason = "SHORTENED_MATCH_NON_STANDARD_PHASE"
                elif is_chase:
                    effective_b_rem = max(1, b_rem)
                    dli_val = compute_dli_chase(rrr_val if not math.isnan(rrr_val) else 8.0, phase, w_in_hand, effective_b_rem)
                    valid_flag = True
                elif is_setting:
                    dli_val = compute_dli_setting(curr_legal_balls, w_in_hand, crr_val, phase)
                    valid_flag = True
                else:
                    dli_val = np.nan
                    valid_flag = False
                    excl_reason = f"UNCLASSIFIED_INNINGS_{innings}"

                # Assign pre-delivery features
                pre_score[row_idx] = curr_score
                pre_wickets_lost[row_idx] = curr_wickets
                pre_wickets_in_hand[row_idx] = w_in_hand
                pre_legal_balls_bowled[row_idx] = curr_legal_balls
                pre_legal_balls_rem[row_idx] = b_rem
                pre_crr[row_idx] = crr_val
                pre_target[row_idx] = target_val if target_val is not None else np.nan
                pre_runs_required[row_idx] = runs_req_val
                pre_rrr[row_idx] = rrr_val
                pre_innings_type[row_idx] = inn_type
                pre_match_phase[row_idx] = phase
                pre_dli[row_idx] = dli_val
                pre_pressure_tier[row_idx] = classify_pressure_tier(dli_val) if valid_flag else None
                is_dli_valid[row_idx] = valid_flag
                dli_exclusion_reason[row_idx] = excl_reason
                is_super_over[row_idx] = is_so
                is_shortened_match[row_idx] = has_shortened_overs
                is_dls_match[row_idx] = has_dls_target

                # 2. State transition for delivery t+1 (AFTER delivery t)
                del_runs = int(row["ext_delivery_total_runs"])
                curr_score += del_runs

                if bool(row["ext_is_legal_delivery"]):
                    curr_legal_balls += 1

                is_wkt = bool(row["is_wicket"])
                is_ret_hurt = bool(row.get("ext_is_retired_hurt", False))
                if is_wkt and not is_ret_hurt:
                    curr_wickets += 1

        # Attach new columns
        df["pre_innings"] = df["innings"]
        df["pre_innings_type"] = pre_innings_type
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
        df["is_shortened_match"] = is_shortened_match
        df["is_dls_match"] = is_dls_match

        # Restore original row ordering
        df = df.sort_values("__orig_order__").drop(columns=["__orig_order__"])
        df.index = orig_index

        return df
