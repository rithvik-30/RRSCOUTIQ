"""
RR ScoutIQ - R1 Investigation B: Monotonicity & Sensitivity Analysis.
Tests response of DLI to independent variation of RRR, wickets in hand, and balls remaining (chase),
and CRR stagnation, wickets in hand, and over progression (setting).
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


# Phase par run rates from M3 methodology
PHASE_PAR_CRR = {
    "Powerplay": 7.50,
    "Middle": 8.00,
    "Death": 10.00,
}


def compute_chase_dli(rrr: float, w_hand: int, b_rem: int, phase_par: float = 8.0) -> float:
    """Computes chase DLI according to approved M3 formula."""
    if b_rem <= 0:
        return 5.00
    term_rrr = rrr / phase_par
    term_w = (10.0 / (w_hand + 1.0)) ** 0.50
    term_b = (1.0 + 24.0 / (b_rem + 12.0)) ** 0.50
    raw_dli = term_rrr * term_w * term_b
    return float(np.clip(raw_dli, 0.10, 5.00))


def compute_setting_dli(t: int, w_hand: int, crr: float, phase_par: float = 8.0) -> float:
    """Computes setting DLI according to approved M3 formula."""
    phi_t = 0.80 + 0.70 * ((t / 120.0) ** 1.20)
    term_w = (10.0 / (w_hand + 1.0)) ** 0.60
    stag = max(0.0, (phase_par - crr) / 6.0)
    term_stag = (1.0 + stag) ** 0.50
    raw_dli = phi_t * term_w * term_stag
    return float(np.clip(raw_dli, 0.20, 3.50))


def run_chase_sensitivity_grid() -> pd.DataFrame:
    """Tests chase DLI sensitivity across controlled hypothetical grid."""
    rrr_vals = [4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0]
    w_vals = [10, 8, 6, 4, 2, 1]
    b_vals = [120, 90, 60, 36, 24, 12, 6]

    rows = []
    # 1. Vary RRR at baseline (w=8, b=60, par=8.0)
    baseline_w = 8
    baseline_b = 60
    for r in rrr_vals:
        dli = compute_chase_dli(r, baseline_w, baseline_b, phase_par=8.0)
        rows.append({
            "test_domain": "CHASE_RRR_SENSITIVITY",
            "varying_parameter": "RRR",
            "param_value": r,
            "fixed_parameters": f"W={baseline_w}, B_rem={baseline_b}, Par=8.0",
            "dli": dli,
            "tier": "Tier 1: Low" if dli < 0.90 else ("Tier 2: Medium" if dli < 1.35 else ("Tier 3: High" if dli < 2.25 else "Tier 4: Extreme")),
            "is_clamped": dli in [0.10, 5.00],
        })

    # 2. Vary Wickets in Hand at baseline (rrr=9.0, b=60)
    baseline_rrr = 9.0
    for w in w_vals:
        dli = compute_chase_dli(baseline_rrr, w, baseline_b, phase_par=8.0)
        rows.append({
            "test_domain": "CHASE_WICKET_SENSITIVITY",
            "varying_parameter": "W_hand",
            "param_value": w,
            "fixed_parameters": f"RRR={baseline_rrr}, B_rem={baseline_b}, Par=8.0",
            "dli": dli,
            "tier": "Tier 1: Low" if dli < 0.90 else ("Tier 2: Medium" if dli < 1.35 else ("Tier 3: High" if dli < 2.25 else "Tier 4: Extreme")),
            "is_clamped": dli in [0.10, 5.00],
        })

    # 3. Vary Balls Remaining at baseline (rrr=9.0, w=8)
    for b in b_vals:
        dli = compute_chase_dli(baseline_rrr, baseline_w, b, phase_par=8.0)
        rows.append({
            "test_domain": "CHASE_BALLS_REM_SENSITIVITY",
            "varying_parameter": "B_rem",
            "param_value": b,
            "fixed_parameters": f"RRR={baseline_rrr}, W={baseline_w}, Par=8.0",
            "dli": dli,
            "tier": "Tier 1: Low" if dli < 0.90 else ("Tier 2: Medium" if dli < 1.35 else ("Tier 3: High" if dli < 2.25 else "Tier 4: Extreme")),
            "is_clamped": dli in [0.10, 5.00],
        })

    return pd.DataFrame(rows)


def run_setting_sensitivity_grid() -> pd.DataFrame:
    """Tests setting DLI sensitivity across controlled hypothetical grid."""
    crr_vals = [4.0, 6.0, 7.5, 8.0, 10.0, 12.0]
    w_vals = [10, 8, 6, 4, 2, 1]
    t_vals = [6, 24, 48, 72, 96, 114, 120]

    rows = []
    # 1. Vary Over Progression t (w=8, crr=8.0, par=8.0)
    baseline_w = 8
    baseline_crr = 8.0
    for t in t_vals:
        dli = compute_setting_dli(t, baseline_w, baseline_crr, phase_par=8.0)
        rows.append({
            "test_domain": "SETTING_OVER_PROGRESSION_SENSITIVITY",
            "varying_parameter": "t_balls_bowled",
            "param_value": t,
            "fixed_parameters": f"W={baseline_w}, CRR={baseline_crr}, Par=8.0",
            "dli": dli,
            "tier": "Tier 1: Low" if dli < 0.90 else ("Tier 2: Medium" if dli < 1.35 else ("Tier 3: High" if dli < 2.25 else "Tier 4: Extreme")),
            "is_clamped": dli in [0.20, 3.50],
        })

    # 2. Vary Wickets in Hand (t=60, crr=8.0)
    baseline_t = 60
    for w in w_vals:
        dli = compute_setting_dli(baseline_t, w, baseline_crr, phase_par=8.0)
        rows.append({
            "test_domain": "SETTING_WICKET_SENSITIVITY",
            "varying_parameter": "W_hand",
            "param_value": w,
            "fixed_parameters": f"t={baseline_t}, CRR={baseline_crr}, Par=8.0",
            "dli": dli,
            "tier": "Tier 1: Low" if dli < 0.90 else ("Tier 2: Medium" if dli < 1.35 else ("Tier 3: High" if dli < 2.25 else "Tier 4: Extreme")),
            "is_clamped": dli in [0.20, 3.50],
        })

    # 3. Vary CRR Stagnation (t=60, w=8, par=8.0)
    for crr in crr_vals:
        dli = compute_setting_dli(baseline_t, baseline_w, crr, phase_par=8.0)
        rows.append({
            "test_domain": "SETTING_CRR_STAGNATION_SENSITIVITY",
            "varying_parameter": "CRR",
            "param_value": crr,
            "fixed_parameters": f"t={baseline_t}, W={baseline_w}, Par=8.0",
            "dli": dli,
            "tier": "Tier 1: Low" if dli < 0.90 else ("Tier 2: Medium" if dli < 1.35 else ("Tier 3: High" if dli < 2.25 else "Tier 4: Extreme")),
            "is_clamped": dli in [0.20, 3.50],
        })

    return pd.DataFrame(rows)
