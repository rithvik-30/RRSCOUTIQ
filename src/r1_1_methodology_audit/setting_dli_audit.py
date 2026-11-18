"""
RR ScoutIQ - Milestone R1.1 Investigation 3: Setting DLI Validation Audit.
Evaluates the setting DLI formulation, temporal progression function Phi(t),
Over 1 undefined CRR behavior, upper clamping (3.50), and wicket scarcity effects.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def compute_experimental_phi(t: int, form: str) -> float:
    """Computes experimental time progression factors for sensitivity comparison."""
    frac = max(0.0, min(120.0, float(t))) / 120.0
    if form == "approved_convex_1_2":
        return 0.80 + 0.70 * (frac ** 1.20)
    elif form == "linear":
        return 0.80 + 0.70 * frac
    elif form == "quadratic_2_0":
        return 0.80 + 0.70 * (frac ** 2.0)
    elif form == "flat":
        return 1.00
    elif form == "phase_step":
        if t <= 36:
            return 0.80
        elif t <= 90:
            return 1.15
        else:
            return 1.50
    return 1.00


def analyze_setting_dli_components(df_state: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Analyzes setting DLI components:
    1. Progression curves comparison across overs 1..20
    2. Over 1 undefined CRR and early collapse behavior
    3. Upper clamping (3.50) and tail collapse wicket scarcity
    """
    setting = df_state[
        (df_state["pre_innings_type"] == "Setting") & (df_state["is_dli_valid"] == True)
    ].copy()

    # 1. Progression Curves Evaluation
    overs = list(range(1, 21))
    prog_rows = []
    for ov in overs:
        t_ball = ov * 6
        phi_app = compute_experimental_phi(t_ball, "approved_convex_1_2")
        phi_lin = compute_experimental_phi(t_ball, "linear")
        phi_quad = compute_experimental_phi(t_ball, "quadratic_2_0")
        phi_flat = compute_experimental_phi(t_ball, "flat")
        phi_step = compute_experimental_phi(t_ball, "phase_step")

        # Mean empirical DLI in this over
        sub_ov = setting[setting["overid"] == ov]
        mean_dli = float(sub_ov["pre_dli"].mean()) if len(sub_ov) > 0 else np.nan
        pct_high_lev = float((sub_ov["pre_dli"] >= 1.35).mean() * 100.0) if len(sub_ov) > 0 else np.nan

        prog_rows.append({
            "over": ov,
            "legal_balls_completed": t_ball,
            "phi_approved_convex": round(phi_app, 4),
            "phi_linear": round(phi_lin, 4),
            "phi_quadratic": round(phi_quad, 4),
            "phi_flat": round(phi_flat, 4),
            "phi_phase_step": round(phi_step, 4),
            "empirical_mean_dli": round(mean_dli, 4),
            "pct_high_leverage": round(pct_high_lev, 2),
        })

    df_progression = pd.DataFrame(prog_rows)

    # 2. Over 1 Undefined CRR Analysis
    over1 = setting[setting["overid"] == 1]
    n_over1 = len(over1)
    over1_mean_dli = float(over1["pre_dli"].mean())
    over1_min_dli = float(over1["pre_dli"].min())
    over1_max_dli = float(over1["pre_dli"].max())

    # Wickets lost in Over 1
    over1_wkt_dist = over1["pre_wickets_in_hand"].value_counts().to_dict()

    over1_summary = {
        "analysis_topic": "Over 1 Undefined CRR Stagnation",
        "total_over1_deliveries": n_over1,
        "mean_dli": round(over1_mean_dli, 4),
        "min_dli": round(over1_min_dli, 4),
        "max_dli": round(over1_max_dli, 4),
        "deliveries_with_w_10": over1_wkt_dist.get(10, 0),
        "deliveries_with_w_9": over1_wkt_dist.get(9, 0),
        "deliveries_with_w_le_8": sum(v for k, v in over1_wkt_dist.items() if k <= 8),
        "stagnation_term_value": 0.0,
        "dli_at_w10": round(0.80 * ((10 / 11) ** 0.60), 4),
        "dli_at_w9": round(0.80 * ((10 / 10) ** 0.60), 4),
        "dli_at_w8": round(0.80 * ((10 / 9) ** 0.60), 4),
    }
    df_over1 = pd.DataFrame([over1_summary])

    # 3. Upper Clamping & Tail Wicket Scarcity Analysis
    tail_collapse = setting[setting["pre_wickets_in_hand"] <= 2]
    n_tail = len(tail_collapse)
    n_tail_clamped = int((np.isclose(tail_collapse["pre_dli"], 3.50, atol=1e-4)).sum())
    tail_clamped_pct = (n_tail_clamped / n_tail) * 100.0 if n_tail > 0 else 0.0

    all_setting_clamped = int((np.isclose(setting["pre_dli"], 3.50, atol=1e-4)).sum())
    total_setting = len(setting)

    clamping_summary = {
        "analysis_topic": "Setting Upper Clamping (3.50 Ceiling)",
        "total_setting_deliveries": total_setting,
        "total_upper_clamped": all_setting_clamped,
        "overall_upper_clamped_pct": round((all_setting_clamped / total_setting) * 100.0, 3),
        "deliveries_at_w_hand_le_2": n_tail,
        "tail_upper_clamped_count": n_tail_clamped,
        "tail_upper_clamped_pct": round(tail_clamped_pct, 2),
        "lower_clamped_count": int((np.isclose(setting["pre_dli"], 0.20, atol=1e-4)).sum()),
        "theoretical_min_setting_dli": round(0.80 * ((10 / 11) ** 0.60), 4),
    }
    df_clamping = pd.DataFrame([clamping_summary])

    return df_progression, df_over1, df_clamping
