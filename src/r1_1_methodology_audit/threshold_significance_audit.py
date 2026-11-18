"""
RR ScoutIQ - Milestone R1.1 Investigation 5: Threshold Sensitivity Statistical Significance Audit.
Tests the statistical and practical significance of the 0.001 wicket hazard inversion in Candidate E,
computes match-clustered bootstrap standard errors for the difference, and evaluates effect size.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from src.r1_dli_research.dli_threshold_sensitivity import classify_experimental_tiers


def bootstrap_hazard_difference(
    df_eval: pd.DataFrame, t1_cut: float, t2_cut: float, t3_cut: float, n_boot: int = 1000, random_seed: int = 42
) -> Dict:
    """
    Computes match-clustered bootstrap difference test between Tier 2 and Tier 1 wicket hazard:
    Delta = Hazard(Tier 2) - Hazard(Tier 1).
    A positive Delta indicates correct monotonicity (Tier 2 hazard > Tier 1 hazard).
    A negative Delta indicates an inversion (Tier 1 hazard > Tier 2 hazard).
    """
    rng = np.random.default_rng(random_seed)
    df = df_eval.copy()
    col = "fwd_6_wkts_scaled" if "fwd_6_wkts_scaled" in df.columns else "fwd_6_wkts"
    df["temp_tier"] = classify_experimental_tiers(df["pre_dli"], t1_cut, t2_cut, t3_cut)

    t1_df = df[df["temp_tier"] == "Tier 1: Low"]
    t2_df = df[df["temp_tier"] == "Tier 2: Medium"]

    n1 = len(t1_df)
    n2 = len(t2_df)
    mean1 = float(t1_df[col].mean()) if n1 > 0 else np.nan
    mean2 = float(t2_df[col].mean()) if n2 > 0 else np.nan
    observed_diff = mean2 - mean1

    # Match-clustered resampling
    unique_matches = df["match_id"].unique()
    n_matches = len(unique_matches)

    # Index lookups
    match_to_t1 = {}
    match_to_t2 = {}
    for m, group in df.groupby("match_id"):
        match_to_t1[m] = group[group["temp_tier"] == "Tier 1: Low"][col].to_numpy()
        match_to_t2[m] = group[group["temp_tier"] == "Tier 2: Medium"][col].to_numpy()

    boot_diffs = []
    for _ in range(n_boot):
        sampled_matches = rng.choice(unique_matches, size=n_matches, replace=True)
        t1_boot_vals = []
        t2_boot_vals = []
        for sm in sampled_matches:
            t1_boot_vals.extend(match_to_t1[sm])
            t2_boot_vals.extend(match_to_t2[sm])

        b_m1 = np.nanmean(t1_boot_vals) if len(t1_boot_vals) > 0 else np.nan
        b_m2 = np.nanmean(t2_boot_vals) if len(t2_boot_vals) > 0 else np.nan
        boot_diffs.append(b_m2 - b_m1)

    boot_diffs = np.array(boot_diffs)
    se_diff = float(np.nanstd(boot_diffs))
    ci_low = float(np.percentile(boot_diffs, 2.5))
    ci_high = float(np.percentile(boot_diffs, 97.5))

    # Two-sided p-value against null hypothesis of Delta = 0
    z_score = observed_diff / se_diff if se_diff > 0 else 0.0
    p_val = 2.0 * (1.0 - stats.norm.cdf(abs(z_score)))

    # Cohen's d effect size
    pooled_sd = float(np.nanstd(df[col]))
    cohens_d = observed_diff / pooled_sd if pooled_sd > 0 else 0.0

    return {
        "candidate": f"[{t1_cut} / {t2_cut} / {t3_cut}]",
        "t1_sample_size": n1,
        "t2_sample_size": n2,
        "t1_hazard_mean": round(mean1, 4),
        "t2_hazard_mean": round(mean2, 4),
        "hazard_diff_t2_minus_t1": round(observed_diff, 4),
        "se_cluster_bootstrap": round(se_diff, 4),
        "ci95_low": round(ci_low, 4),
        "ci95_high": round(ci_high, 4),
        "z_score": round(z_score, 3),
        "p_value": round(p_val, 4),
        "cohens_d": round(cohens_d, 4),
        "statistically_significant": p_val < 0.05,
        "inversion_distinguishable_from_noise": (observed_diff < 0) and (ci_high < 0),
    }


def run_threshold_significance_audit(df_fwd: pd.DataFrame) -> pd.DataFrame:
    """Evaluates the statistical and practical significance of hazard differences across all candidate cutoffs."""
    candidates = [
        ("Approved M3 Baseline", 0.90, 1.35, 2.25),
        ("Candidate A (Narrow: -0.05/-0.05/-0.10)", 0.85, 1.30, 2.15),
        ("Candidate B (Wide: +0.05/+0.05/+0.10)", 0.95, 1.40, 2.35),
        ("Candidate C (Conservative Low: 0.80/1.25/2.00)", 0.80, 1.25, 2.00),
        ("Candidate D (Aggressive High: 1.00/1.50/2.50)", 1.00, 1.50, 2.50),
        ("Candidate E (Draft 0.70/1.30/2.00)", 0.70, 1.30, 2.00),
    ]

    rows = []
    for name, t1, t2, t3 in candidates:
        res = bootstrap_hazard_difference(df_fwd, t1, t2, t3, n_boot=500)
        res["candidate_name"] = name
        rows.append(res)

    df_out = pd.DataFrame(rows)
    # Reorder columns
    cols = [
        "candidate_name",
        "candidate",
        "t1_sample_size",
        "t2_sample_size",
        "t1_hazard_mean",
        "t2_hazard_mean",
        "hazard_diff_t2_minus_t1",
        "se_cluster_bootstrap",
        "ci95_low",
        "ci95_high",
        "z_score",
        "p_value",
        "cohens_d",
        "statistically_significant",
        "inversion_distinguishable_from_noise",
    ]
    return df_out[cols]
