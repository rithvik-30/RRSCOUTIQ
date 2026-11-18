"""
RR ScoutIQ - R1 Investigation A: DLI Distribution, Tier Adequacy & Clamping Analysis.
Analyzes DLI distribution, tier population, phase concentration, and clamping rates
across Chase, Setting, Powerplay, Middle, Death, and Super Overs.
"""

from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def compute_group_stats(df_group: pd.DataFrame, group_name: str, group_category: str) -> Dict:
    """Computes comprehensive distributional metrics for a subset of DLI observations."""
    dli = df_group["pre_dli"].dropna()
    n = len(dli)
    if n == 0:
        return {}

    mean_val = float(dli.mean())
    median_val = float(dli.median())
    std_val = float(dli.std()) if n > 1 else 0.0
    min_val = float(dli.min())
    max_val = float(dli.max())
    q05 = float(dli.quantile(0.05))
    q25 = float(dli.quantile(0.25))
    q75 = float(dli.quantile(0.75))
    q95 = float(dli.quantile(0.95))

    # Tiers
    t1_cnt = int((df_group["pre_pressure_tier"] == "Tier 1: Low").sum())
    t2_cnt = int((df_group["pre_pressure_tier"] == "Tier 2: Medium").sum())
    t3_cnt = int((df_group["pre_pressure_tier"] == "Tier 3: High").sum())
    t4_cnt = int((df_group["pre_pressure_tier"] == "Tier 4: Extreme").sum())

    # Clamping: Chase clamps at 0.10 and 5.00; Setting clamps at 0.20 and 3.50
    # Floating point tolerance
    lower_clamped = int((np.isclose(dli, 0.10, atol=1e-4) | np.isclose(dli, 0.20, atol=1e-4)).sum())
    upper_clamped = int((np.isclose(dli, 5.00, atol=1e-4) | np.isclose(dli, 3.50, atol=1e-4)).sum())

    return {
        "group_category": group_category,
        "group_name": group_name,
        "observation_count": n,
        "mean_dli": round(mean_val, 4),
        "std_dli": round(std_val, 4),
        "median_dli": round(median_val, 4),
        "min_dli": round(min_val, 4),
        "max_dli": round(max_val, 4),
        "q05_dli": round(q05, 4),
        "q25_dli": round(q25, 4),
        "q75_dli": round(q75, 4),
        "q95_dli": round(q95, 4),
        "tier1_count": t1_cnt,
        "tier1_pct": round((t1_cnt / n) * 100, 2),
        "tier2_count": t2_cnt,
        "tier2_pct": round((t2_cnt / n) * 100, 2),
        "tier3_count": t3_cnt,
        "tier3_pct": round((t3_cnt / n) * 100, 2),
        "tier4_count": t4_cnt,
        "tier4_pct": round((t4_cnt / n) * 100, 2),
        "high_leverage_count": t3_cnt + t4_cnt,
        "high_leverage_pct": round(((t3_cnt + t4_cnt) / n) * 100, 2),
        "lower_clamped_count": lower_clamped,
        "lower_clamped_pct": round((lower_clamped / n) * 100, 4),
        "upper_clamped_count": upper_clamped,
        "upper_clamped_pct": round((upper_clamped / n) * 100, 4),
    }


def run_distribution_analysis(df_state: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Executes Investigation A analysis across partitions.
    Returns:
    1. df_tier_dist: Overall population and primary macro-groups
    2. df_phase_comp: Detailed phase x innings breakdown
    3. df_clamping: Dedicated clamping analysis
    """
    valid_df = df_state[df_state["is_dli_valid"] == True].copy()

    records = []

    # 1. Total Valid Population
    records.append(compute_group_stats(valid_df, "All Valid Deliveries", "OVERALL"))

    # 2. Innings Types
    chase_df = valid_df[valid_df["pre_innings_type"] == "Chase"]
    setting_df = valid_df[valid_df["pre_innings_type"] == "Setting"]
    so_df = valid_df[valid_df["is_super_over"] == True]

    records.append(compute_group_stats(chase_df, "Chase Innings (Innings 2)", "INNINGS_TYPE"))
    records.append(compute_group_stats(setting_df, "Setting Innings (Innings 1)", "INNINGS_TYPE"))
    records.append(compute_group_stats(so_df, "Super Overs (Innings 3 & 4)", "INNINGS_TYPE"))

    # 3. Macro Phases (excluding Super Overs)
    reg_df = valid_df[valid_df["is_super_over"] == False]
    pp_df = reg_df[reg_df["pre_match_phase"] == "Powerplay"]
    mid_df = reg_df[reg_df["pre_match_phase"] == "Middle"]
    death_df = reg_df[reg_df["pre_match_phase"] == "Death"]

    records.append(compute_group_stats(pp_df, "Powerplay (Overs 1-6)", "PHASE_MACRO"))
    records.append(compute_group_stats(mid_df, "Middle (Overs 7-15)", "PHASE_MACRO"))
    records.append(compute_group_stats(death_df, "Death (Overs 16-20)", "PHASE_MACRO"))

    df_tier_dist = pd.DataFrame(records)

    # 4. Detailed Phase x Innings Breakdown for R1_PHASE_COMPARISON
    phase_records = []
    # Setting Phases
    phase_records.append(compute_group_stats(setting_df[setting_df["pre_match_phase"] == "Powerplay"], "Setting - Powerplay", "SETTING_PHASES"))
    phase_records.append(compute_group_stats(setting_df[setting_df["pre_match_phase"] == "Middle"], "Setting - Middle", "SETTING_PHASES"))
    phase_records.append(compute_group_stats(setting_df[setting_df["pre_match_phase"] == "Death"], "Setting - Death", "SETTING_PHASES"))
    # Chase Phases
    phase_records.append(compute_group_stats(chase_df[chase_df["pre_match_phase"] == "Powerplay"], "Chase - Powerplay", "CHASE_PHASES"))
    phase_records.append(compute_group_stats(chase_df[chase_df["pre_match_phase"] == "Middle"], "Chase - Middle", "CHASE_PHASES"))
    phase_records.append(compute_group_stats(chase_df[chase_df["pre_match_phase"] == "Death"], "Chase - Death", "CHASE_PHASES"))
    # Super Over
    phase_records.append(compute_group_stats(so_df, "Super Over", "SPECIAL_PHASE"))

    df_phase_comp = pd.DataFrame(phase_records)

    # 5. Dedicated Clamping Analysis for R1_CLAMPING_ANALYSIS
    clamping_records = []
    # Chase lower clamp (0.10)
    chase_dli = chase_df["pre_dli"]
    chase_lower_mask = np.isclose(chase_dli, 0.10, atol=1e-4)
    chase_upper_mask = np.isclose(chase_dli, 5.00, atol=1e-4)
    clamping_records.append({
        "scope": "Chase Innings",
        "clamp_type": "Lower Bound (0.10)",
        "formula_domain": "DLI_chase in [0.10, 5.00]",
        "total_deliveries": len(chase_df),
        "clamped_count": int(chase_lower_mask.sum()),
        "clamped_pct": round(float(chase_lower_mask.sum() / len(chase_df)) * 100, 4),
        "driver_conditions": "Target reached or virtually reached (RRR -> 0, runs required <= 0)",
        "phase_distribution": dict(chase_df[chase_lower_mask]["pre_match_phase"].value_counts()),
    })
    clamping_records.append({
        "scope": "Chase Innings",
        "clamp_type": "Upper Bound (5.00)",
        "formula_domain": "DLI_chase in [0.10, 5.00]",
        "total_deliveries": len(chase_df),
        "clamped_count": int(chase_upper_mask.sum()),
        "clamped_pct": round(float(chase_upper_mask.sum() / len(chase_df)) * 100, 4),
        "driver_conditions": "Severe crisis states: RRR >= 18.0, 1-2 wickets in hand, or final over desperation",
        "phase_distribution": dict(chase_df[chase_upper_mask]["pre_match_phase"].value_counts()),
    })

    # Setting lower clamp (0.20) and upper clamp (3.50)
    setting_dli = setting_df["pre_dli"]
    setting_lower_mask = np.isclose(setting_dli, 0.20, atol=1e-4)
    setting_upper_mask = np.isclose(setting_dli, 3.50, atol=1e-4)
    clamping_records.append({
        "scope": "Setting Innings",
        "clamp_type": "Lower Bound (0.20)",
        "formula_domain": "DLI_setting in [0.20, 3.50]",
        "total_deliveries": len(setting_df),
        "clamped_count": int(setting_lower_mask.sum()),
        "clamped_pct": round(float(setting_lower_mask.sum() / len(setting_df)) * 100, 4),
        "driver_conditions": "Theoretically inactive: min setting DLI is Phi(0) * (10/11)^0.6 = 0.80 * 0.944 = 0.755 > 0.20",
        "phase_distribution": dict(setting_df[setting_lower_mask]["pre_match_phase"].value_counts()),
    })
    clamping_records.append({
        "scope": "Setting Innings",
        "clamp_type": "Upper Bound (3.50)",
        "formula_domain": "DLI_setting in [0.20, 3.50]",
        "total_deliveries": len(setting_df),
        "clamped_count": int(setting_upper_mask.sum()),
        "clamped_pct": round(float(setting_upper_mask.sum() / len(setting_df)) * 100, 4),
        "driver_conditions": "Extreme tail collapse: 8-9 wickets lost in death overs with severe stagnation",
        "phase_distribution": dict(setting_df[setting_upper_mask]["pre_match_phase"].value_counts()),
    })

    df_clamping = pd.DataFrame(clamping_records)

    return df_tier_dist, df_phase_comp, df_clamping
