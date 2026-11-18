"""
RR ScoutIQ - R1 Investigation D: Tier Threshold Sensitivity Analysis.
Tests stability, population distribution, win rate separation, and subsequent wicket hazard
under experimental threshold perturbations (0.80 - 1.00, 1.25 - 1.50, 2.00 - 2.50).
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def classify_experimental_tiers(dli_series: pd.Series, t1_cut: float, t2_cut: float, t3_cut: float) -> pd.Series:
    """Classifies DLI series into 4 tiers using arbitrary threshold cutoffs."""
    conditions = [
        dli_series < t1_cut,
        (dli_series >= t1_cut) & (dli_series < t2_cut),
        (dli_series >= t2_cut) & (dli_series < t3_cut),
        dli_series >= t3_cut,
    ]
    choices = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
    return pd.Series(np.select(conditions, choices, default="Unclassified"), index=dli_series.index)


def evaluate_threshold_candidate(
    df_eval: pd.DataFrame, candidate_name: str, t1_cut: float, t2_cut: float, t3_cut: float
) -> Dict:
    """Evaluates tier distribution, win rate gradient, and wicket hazard for a threshold candidate."""
    dli = df_eval["pre_dli"]
    tiers = classify_experimental_tiers(dli, t1_cut, t2_cut, t3_cut)
    df_eval = df_eval.copy()
    df_eval["exp_tier"] = tiers

    n_total = len(df_eval)

    # Counts and percentages
    t_counts = tiers.value_counts().to_dict()
    t1_n = t_counts.get("Tier 1: Low", 0)
    t2_n = t_counts.get("Tier 2: Medium", 0)
    t3_n = t_counts.get("Tier 3: High", 0)
    t4_n = t_counts.get("Tier 4: Extreme", 0)

    # Chase win rate gradient
    chase = df_eval[df_eval["pre_innings_type"] == "Chase"]
    win_by_tier = chase.groupby("exp_tier")["chase_won"].mean().to_dict()

    # Subsequent 6-ball wicket hazard
    wkt_by_tier = df_eval.groupby("exp_tier")["fwd_6_wkts_scaled"].mean().to_dict()

    # Monotonicity checks: Win rate should strictly decrease; Wickets should strictly increase
    win_mono = (
        win_by_tier.get("Tier 1: Low", 1) >= win_by_tier.get("Tier 2: Medium", 0.5) >=
        win_by_tier.get("Tier 3: High", 0.3) >= win_by_tier.get("Tier 4: Extreme", 0.1)
    )
    wkt_mono = (
        wkt_by_tier.get("Tier 1: Low", 0) <= wkt_by_tier.get("Tier 2: Medium", 0.3) <=
        wkt_by_tier.get("Tier 3: High", 0.4) <= wkt_by_tier.get("Tier 4: Extreme", 0.6)
    )

    return {
        "candidate_name": candidate_name,
        "t1_t2_cutoff": t1_cut,
        "t2_t3_cutoff": t2_cut,
        "t3_t4_cutoff": t3_cut,
        "tier1_pct": round((t1_n / n_total) * 100, 2),
        "tier2_pct": round((t2_n / n_total) * 100, 2),
        "tier3_pct": round((t3_n / n_total) * 100, 2),
        "tier4_pct": round((t4_n / n_total) * 100, 2),
        "tier1_win_rate": round(win_by_tier.get("Tier 1: Low", np.nan) * 100, 2),
        "tier2_win_rate": round(win_by_tier.get("Tier 2: Medium", np.nan) * 100, 2),
        "tier3_win_rate": round(win_by_tier.get("Tier 3: High", np.nan) * 100, 2),
        "tier4_win_rate": round(win_by_tier.get("Tier 4: Extreme", np.nan) * 100, 2),
        "win_rate_spread_t1_minus_t4": round(
            (win_by_tier.get("Tier 1: Low", 0) - win_by_tier.get("Tier 4: Extreme", 0)) * 100, 2
        ),
        "tier1_wkt_hazard": round(wkt_by_tier.get("Tier 1: Low", np.nan), 3),
        "tier2_wkt_hazard": round(wkt_by_tier.get("Tier 2: Medium", np.nan), 3),
        "tier3_wkt_hazard": round(wkt_by_tier.get("Tier 3: High", np.nan), 3),
        "tier4_wkt_hazard": round(wkt_by_tier.get("Tier 4: Extreme", np.nan), 3),
        "wkt_hazard_ratio_t4_to_t1": round(
            wkt_by_tier.get("Tier 4: Extreme", 1) / max(0.001, wkt_by_tier.get("Tier 1: Low", 1)), 2
        ),
        "win_rate_strictly_monotonic": win_mono,
        "wkt_hazard_strictly_monotonic": wkt_mono,
    }


def run_threshold_sensitivity_battery(df_fwd: pd.DataFrame) -> pd.DataFrame:
    """Evaluates approved M3 thresholds and experimental perturbation candidates."""
    candidates = [
        ("Approved M3 Baseline", 0.90, 1.35, 2.25),
        ("Candidate A (Narrowed: -0.05 / -0.05 / -0.10)", 0.85, 1.30, 2.15),
        ("Candidate B (Widened: +0.05 / +0.05 / +0.10)", 0.95, 1.40, 2.35),
        ("Candidate C (Conservative Low: 0.80 / 1.25 / 2.00)", 0.80, 1.25, 2.00),
        ("Candidate D (Aggressive High: 1.00 / 1.50 / 2.50)", 1.00, 1.50, 2.50),
        ("Candidate E (Exploratory Historical Draft: 0.70 / 1.30 / 2.00)", 0.70, 1.30, 2.00),
    ]

    records = []
    for name, t1, t2, t3 in candidates:
        rec = evaluate_threshold_candidate(df_fwd, name, t1, t2, t3)
        records.append(rec)

    return pd.DataFrame(records)
