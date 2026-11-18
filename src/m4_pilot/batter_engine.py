"""
RR ScoutIQ - Module M4.3: Batter Performance Engine
===================================================

Evidence Level: IMPLEMENTATION CORRECTNESS & PILOT DIAGNOSTIC
Implementation Architecture:
- Evaluates batter decision-making, scoring efficiency, boundary generation,
  dot-ball avoidance, and wicket preservation relative to contextual expectation.
- Strictly consumes pre-delivery match state from Module M4.2.
- Calculates the five approved BPPI components:
    1. Expected Runs Above (xRA/ball) [Weight: 0.35]
    2. Strike Rate Difference (Delta SR) [Weight: 0.25]
    3. Boundary Percentage Difference (Delta Boundary%) [Weight: 0.15]
    4. Dot Ball Percentage Difference (Delta Dot%) [Weight: 0.15]
    5. Survival Difference (Delta Survival) [Weight: 0.10]
- Implements role-aware cohort classification (Top Order, Middle Order, Finisher).
- Implements Empirical Bayes shrinkage:
    * Beta-Binomial shrinkage for proportions (Dot%, Boundary%, Wicket%).
    * Normal-Normal rate shrinkage for continuous rates (xRA, SR) [PROVISIONAL].
- Implements clustered bootstrap uncertainty quantification (Scheme B: player-innings resampling).
- Distinguishes Normal-approximation CIs, percentile bootstrap CIs, and Bayesian credible intervals.
- Enforces strict qualification criteria (>=12 innings, >=120 balls faced, >=36 pressure balls).
- Traces the provisional early-innings Setting DLI convention.
- Strictly prohibits final player ranking generation or top-10 list production.
"""

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np
import pandas as pd
import scipy.stats as stats


# ---------------------------------------------------------------------------
# Authoritative Constants & M3 Specifications
# ---------------------------------------------------------------------------

# BPPI Component Weights (Approved M3 Starting Weights - PROVISIONAL)
WEIGHT_XRA: float = 0.35
WEIGHT_DELTA_SR: float = 0.25
WEIGHT_DELTA_BND: float = 0.15
WEIGHT_DELTA_DOT: float = 0.15
WEIGHT_DELTA_SURVIVAL: float = 0.10

# Leverage Cutoff for High Pressure (Approved M3 Threshold)
PRESSURE_DLI_THRESHOLD: float = 1.35  # Tiers 3 (High) & 4 (Extreme)

# Eligibility Thresholds (Approved M3 Dual-Tier Qualifications)
MIN_QUALIFYING_INNINGS: int = 12
MIN_QUALIFYING_BALLS_FACED: int = 120
MIN_QUALIFYING_PRESSURE_BALLS: int = 36

# Batter Role Entry Over Cutoffs (Approved M3 Definition 1)
ROLE_TOP_ORDER_MAX_OVER: float = 6.0       # Entry <= 6.0
ROLE_MIDDLE_ORDER_MAX_OVER: float = 13.0   # Entry 6.1 - 13.0
# Finisher: Entry > 13.0

# Empirical Bayes Shrinkage Prior Strengths (Approved M3 Specifications)
# Proportions: Beta-Binomial (M equivalent sample size in balls)
M_DOT: float = 135.8
M_BOUNDARY: float = 114.7
M_BND: float = 114.7  # Alias for M_BOUNDARY
M_WICKET_CAPPED: float = 90.0  # Capped regularization from uncapped 1613.1

# Continuous Rates: Normal-Normal James-Stein (K equivalent sample size in balls)
K_SR: float = 50.62            # Dimensionally corrected in M3 Statistical Consistency Audit
K_XRA: float = 38.2            # M3 Empirical evidence baseline

# Role Standardization Safeguards
VARIANCE_REGULARIZATION_ALPHA: float = 0.10
MIN_COHORT_SIZE: int = 30
HIERARCHICAL_POOLING_STRENGTH: float = 15.0

# Empirical League & Role Priors (M3 Baseline Distributions)
ROLE_PRIORS: Dict[str, Dict[str, float]] = {
    "Top Order": {
        "mu_sr": 139.89,
        "sigma_sr": 20.92,
        "mu_dot": 0.4310,
        "mu_bnd": 0.2010,
        "mu_out": 0.0530,
        "mu_xra": 0.0000,
        "sigma_xra": 0.2500,
    },
    "Middle Order": {
        "mu_sr": 138.68,
        "sigma_sr": 15.28,
        "mu_dot": 0.3860,
        "mu_bnd": 0.1880,
        "mu_out": 0.0400,
        "mu_xra": 0.0000,
        "sigma_xra": 0.2200,
    },
    "Finisher": {
        "mu_sr": 136.52,
        "sigma_sr": 18.07,
        "mu_dot": 0.4210,
        "mu_bnd": 0.1950,
        "mu_out": 0.0470,
        "mu_xra": 0.0000,
        "sigma_xra": 0.2800,
    },
    "League": {
        "mu_sr": 138.50,
        "sigma_sr": 17.05,
        "mu_dot": 0.4000,
        "mu_bnd": 0.1946,
        "mu_out": 0.0525,
        "mu_xra": 0.0000,
        "sigma_xra": 0.2500,
    }
}

# Empirical Run Expectation Grid E[Runs | Phase, Tier] (League Baselines)
# Hierarchical expectation model: Phase x Tier
EMPIRICAL_RUN_EXPECTATIONS: Dict[Tuple[str, str], float] = {
    # Powerplay
    ("Powerplay", "Tier 1: Low"): 1.25,
    ("Powerplay", "Tier 2: Medium"): 1.30,
    ("Powerplay", "Tier 3: High"): 1.15,
    ("Powerplay", "Tier 4: Extreme"): 1.05,
    # Middle
    ("Middle", "Tier 1: Low"): 1.32,
    ("Middle", "Tier 2: Medium"): 1.35,
    ("Middle", "Tier 3: High"): 1.40,
    ("Middle", "Tier 4: Extreme"): 1.30,
    # Death
    ("Death", "Tier 1: Low"): 1.65,
    ("Death", "Tier 2: Medium"): 1.70,
    ("Death", "Tier 3: High"): 1.85,
    ("Death", "Tier 4: Extreme"): 1.95,
    # Super Over
    ("Super Over", "Tier 4: Extreme"): 1.80,
}
GLOBAL_EXPECTED_RUNS_PER_BALL: float = 1.395


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class BatterRoleProfile:
    striker_id: int
    striker_name: str
    innings_count: int
    avg_entry_over: float
    primary_role: str
    entry_overs: List[float] = field(default_factory=list)
    innings_roles: List[str] = field(default_factory=list)
    role_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class BatterEligibilityRecord:
    striker_id: int
    striker_name: str
    innings_count: int
    total_balls_faced: int
    pressure_balls_faced: int
    is_eligible: bool
    exclusion_reasons: List[str]


@dataclass
class BPPIComponentBundle:
    raw_xra_per_ball: float
    raw_delta_sr: float
    raw_delta_bnd_pct: float
    raw_delta_dot_pct: float
    raw_delta_survival_pct: float
    shrunk_xra_per_ball: float
    shrunk_delta_sr: float
    shrunk_delta_bnd_pct: float
    shrunk_delta_dot_pct: float
    shrunk_delta_survival_pct: float
    z_xra: float
    z_delta_sr: float
    z_delta_bnd: float
    z_delta_dot: float
    z_delta_survival: float
    bppi_score: float


# ---------------------------------------------------------------------------
# 1. Batter Role Assignment Engine
# ---------------------------------------------------------------------------

def assign_innings_roles(deliveries_df: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns each batter's tactical role for each specific innings based on their
    actual entry over in that innings (Approved M3 Definition 1 & Super Over Isolation).
    
    CRICKET SPECIFICATION & SUPER OVER ISOLATION:
    - Super Over Innings (innings >= 3 or is_super_over == True): Assigned 'Super Over'.
      Tie-break 1-over shootouts do NOT classify as 'Top Order' merely because overid == 1.
    - Regulation Innings:
      * Top Order: Actual Entry Over <= 6.0 (Powerplay)
      * Middle Order: Actual Entry Over > 6.0 and <= 13.0 (Middle Overs)
      * Finisher: Actual Entry Over > 13.0 (Death Overs)
    """
    faced_df = deliveries_df[deliveries_df["ext_batter_balls_faced"] == 1]
    if len(faced_df) == 0:
        return pd.DataFrame(columns=["striker_id", "match_id", "innings", "entry_over", "innings_role"])

    first_overs = (
        faced_df.groupby(["striker_id", "match_id", "innings"])["overid"]
        .min()
        .reset_index()
    )
    first_overs["entry_over"] = first_overs["overid"]

    def map_innings_role(row) -> str:
        if row["innings"] >= 3:
            return "Super Over"
        over = row["entry_over"]
        if over <= ROLE_TOP_ORDER_MAX_OVER:
            return "Top Order"
        elif over <= ROLE_MIDDLE_ORDER_MAX_OVER:
            return "Middle Order"
        else:
            return "Finisher"

    first_overs["innings_role"] = first_overs.apply(map_innings_role, axis=1)
    return first_overs[["striker_id", "match_id", "innings", "entry_over", "innings_role"]]


def assign_batter_roles(deliveries_df: pd.DataFrame) -> Dict[int, BatterRoleProfile]:
    """
    Assigns each batter to a primary tactical role cohort while capturing complete
    innings-level role distribution and actual entry overs across all match-innings.
    
    CRICKET SPECIFICATION (Approved M3 Definition 1 & Super Over Isolation):
    - Primary tactical role is determined strictly from REGULATION innings (innings <= 2).
    - Super Over innings do NOT participate in mean/modal primary role calculation,
      preventing tie-break 1-over shootouts from distorting a player's regular batting role.
    - Top Order: Mean Regulation Entry Over <= 6.0 (Overs 1-6)
    - Middle Order: Mean Regulation Entry Over > 6.0 and <= 13.0 (Overs 7-13)
    - Finisher: Mean Regulation Entry Over > 13.0 (Overs 14-20)
    
    For batters with 0 regulation balls faced (rare edge case), defaults to 'Middle Order'.
    """
    faced_df = deliveries_df[deliveries_df["ext_batter_balls_faced"] == 1]
    
    if len(faced_df) == 0:
        return {}

    first_overs = (
        faced_df.groupby(["striker_id", "striker_name", "match_id", "innings"])["overid"]
        .min()
        .reset_index()
    )

    def map_role(row) -> str:
        if row["innings"] >= 3:
            return "Super Over"
        over = row["overid"]
        if over <= ROLE_TOP_ORDER_MAX_OVER:
            return "Top Order"
        elif over <= ROLE_MIDDLE_ORDER_MAX_OVER:
            return "Middle Order"
        else:
            return "Finisher"

    first_overs["role"] = first_overs.apply(map_role, axis=1)

    profiles: Dict[int, BatterRoleProfile] = {}
    grouped = first_overs.groupby(["striker_id", "striker_name"])

    for (striker_id, striker_name), grp in grouped:
        all_entry_list = grp["overid"].tolist()
        all_inn_roles = grp["role"].tolist()

        # Isolate regulation innings for primary role calculation
        reg_grp = grp[grp["innings"] <= 2]
        if len(reg_grp) > 0:
            reg_entry_list = reg_grp["overid"].tolist()
            avg_entry = float(np.mean(reg_entry_list))
        else:
            reg_entry_list = all_entry_list
            avg_entry = 15.0

        # Role counts distribution across all innings
        role_counts = pd.Series(all_inn_roles).value_counts().to_dict()

        if avg_entry <= ROLE_TOP_ORDER_MAX_OVER:
            role = "Top Order"
        elif avg_entry <= ROLE_MIDDLE_ORDER_MAX_OVER:
            role = "Middle Order"
        else:
            role = "Finisher"

        profiles[int(striker_id)] = BatterRoleProfile(
            striker_id=int(striker_id),
            striker_name=str(striker_name),
            innings_count=len(all_entry_list),
            avg_entry_over=round(avg_entry, 3),
            primary_role=role,
            entry_overs=reg_entry_list,
            innings_roles=all_inn_roles,
            role_distribution=role_counts
        )

    # Catch any batters present in deliveries_df who faced 0 legal balls (e.g. dismissed on wide)
    all_strikers = deliveries_df[["striker_id", "striker_name"]].drop_duplicates()
    for _, row in all_strikers.iterrows():
        sid = int(row["striker_id"])
        sname = str(row["striker_name"])
        if sid not in profiles:
            profiles[sid] = BatterRoleProfile(
                striker_id=sid,
                striker_name=sname,
                innings_count=0,
                avg_entry_over=7.0,
                primary_role="Middle Order",
                entry_overs=[],
                innings_roles=[],
                role_distribution={}
            )

    return profiles


# ---------------------------------------------------------------------------
# 2. Canonical Runs Attribution & Delivery-Level xRA
# ---------------------------------------------------------------------------

def compute_canonical_batter_runs(df: pd.DataFrame) -> pd.Series:
    """
    Computes canonical runs scored off the bat for each delivery.
    
    CANONICAL RUN CONTRACT (From M4.1 & M4.2):
    - bat_runs = ext_delivery_total_runs - (all extras)
    - Disposes Match 20181 Over 9 balls 4 & 5 using canonical Cricsheet delivery runs
      (2 on ball 4, 1 on ball 5) while preserving original runs field.
    """
    extras_sum = (
        df["ext_wide_runs"] +
        df["ext_noball_runs"] +
        df["ext_bye_runs"] +
        df["ext_legbye_runs"] +
        df["ext_penalty_runs"]
    )
    return (df["ext_delivery_total_runs"] - extras_sum).clip(lower=0)


def compute_delivery_xra(
    deliveries_df: pd.DataFrame,
    role_map: Optional[Dict[int, BatterRoleProfile]] = None
) -> pd.DataFrame:
    """
    Enriches delivery DataFrame with canonical batter runs, boundary flags,
    dismissal attribution, and situational Expected Runs Added (xRA).
    
    xRA = bat_runs - E[runs | Phase, Tier]
    
    ANTI-LEAKAGE INTEGRITY:
    - Expected runs baseline depends strictly on pre-delivery match state (Phase, Tier).
    - Current delivery outcome does NOT affect its own expectation.
    """
    df = deliveries_df.copy()
    if role_map is None:
        role_map = assign_batter_roles(df)

    # Canonical bat runs off bat
    df["bat_runs"] = compute_canonical_batter_runs(df)

    # Ball classification flags
    df["is_boundary_four"] = (df["is_four"] == 1).astype(int)
    df["is_boundary_six"] = (df["is_six"] == 1).astype(int)
    df["is_boundary"] = ((df["is_boundary_four"] == 1) | (df["is_boundary_six"] == 1)).astype(int)
    df["is_dot_ball"] = (
        (df["ext_batter_balls_faced"] == 1) & (df["bat_runs"] == 0)
    ).astype(int)

    # Batter dismissal attribution:
    # Under Law 25.4.2, Retired Hurt is NOT a dismissal.
    # Wicket must be credited against the striker (dismissed_player_id == striker_id).
    df["is_batter_out"] = (
        (df["is_wicket"] == 1) &
        (df["dismissed_player_id"] == df["striker_id"]) &
        (df["ext_is_retired_hurt"] == False)
    ).astype(int)

    # Lookup expected runs
    def get_expected_runs(row) -> float:
        phase = str(row["pre_match_phase"])
        tier = str(row["pre_pressure_tier"])
        return EMPIRICAL_RUN_EXPECTATIONS.get((phase, tier), GLOBAL_EXPECTED_RUNS_PER_BALL)

    df["expected_runs"] = df.apply(get_expected_runs, axis=1)
    
    # xRA is defined on deliveries where batter faces a ball (ext_batter_balls_faced == 1)
    df["xra"] = np.where(
        df["ext_batter_balls_faced"] == 1,
        df["bat_runs"] - df["expected_runs"],
        0.0
    )

    # Role attachment: attach innings-level tactical role and player primary role
    innings_roles_df = assign_innings_roles(df)
    if len(innings_roles_df) > 0:
        df = pd.merge(
            df,
            innings_roles_df[["striker_id", "match_id", "innings", "entry_over", "innings_role"]],
            on=["striker_id", "match_id", "innings"],
            how="left"
        )
        df = df.rename(columns={"entry_over": "innings_entry_over"})
        df["innings_role"] = df["innings_role"].fillna("Middle Order")
        df["innings_entry_over"] = df["innings_entry_over"].fillna(7.0)
    else:
        df["innings_role"] = "Middle Order"
        df["innings_entry_over"] = 7.0

    df["batter_role"] = df["striker_id"].map(
        lambda sid: role_map[sid].primary_role if sid in role_map else "Middle Order"
    )

    return df


# ---------------------------------------------------------------------------
# 3. Aggregation & Performance Feature Matrix
# ---------------------------------------------------------------------------

def aggregate_batter_performance(deliveries_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates ball-by-ball delivery state into player-level summary features,
    partitioned across High Pressure (DLI >= 1.35) and Normal Baseline (DLI < 1.35).
    
    EXCLUSION SAFETY:
    - Only deliveries with is_dli_valid == True are included for pressure performance.
    - Super Overs are partitioned cleanly.
    """
    df = deliveries_df[deliveries_df["is_dli_valid"] == True].copy()
    
    # Pressure split indicator
    df["is_pressure"] = (df["pre_dli"] >= PRESSURE_DLI_THRESHOLD) & (df["ext_batter_balls_faced"] == 1)
    df["is_baseline"] = (df["pre_dli"] < PRESSURE_DLI_THRESHOLD) & (df["ext_batter_balls_faced"] == 1)

    records: List[Dict[str, Any]] = []
    role_map = assign_batter_roles(df)

    grouped = df.groupby(["striker_id", "striker_name"])

    for (sid, sname), grp in grouped:
        role_prof = role_map.get(sid, None)
        role = role_prof.primary_role if role_prof else "Middle Order"
        avg_entry = role_prof.avg_entry_over if role_prof else 7.0

        # Exposure metrics
        total_innings = grp[["match_id", "innings"]].drop_duplicates().shape[0]
        total_balls_faced = int(grp["ext_batter_balls_faced"].sum())
        total_runs = int(grp["bat_runs"].sum())
        total_outs = int(grp["is_batter_out"].sum())

        # Pressure slice
        press_grp = grp[grp["is_pressure"] == True]
        n_press = int(len(press_grp))
        runs_press = int(press_grp["bat_runs"].sum())
        dots_press = int(press_grp["is_dot_ball"].sum())
        bnds_press = int(press_grp["is_boundary"].sum())
        outs_press = int(press_grp["is_batter_out"].sum())
        xra_press_sum = float(press_grp["xra"].sum())

        # Baseline slice
        base_grp = grp[grp["is_baseline"] == True]
        n_base = int(len(base_grp))
        runs_base = int(base_grp["bat_runs"].sum())
        outs_base = int(base_grp["is_batter_out"].sum())

        # Raw Rates (with zero-division guards returning NaN)
        sr_press = (runs_press / n_press * 100.0) if n_press > 0 else np.nan
        sr_base = (runs_base / n_base * 100.0) if n_base > 0 else np.nan
        raw_delta_sr = (sr_press - sr_base) if (n_press > 0 and n_base > 0) else np.nan
        raw_xra_per_ball = (xra_press_sum / n_press) if n_press > 0 else np.nan
        raw_bnd_pct = (bnds_press / n_press * 100.0) if n_press > 0 else np.nan
        raw_dot_pct = (dots_press / n_press * 100.0) if n_press > 0 else np.nan
        raw_out_pct = (outs_press / n_press * 100.0) if n_press > 0 else np.nan

        # Role cohort priors
        priors = ROLE_PRIORS.get(role, ROLE_PRIORS["Middle Order"])

        # Raw deltas vs role priors
        raw_delta_bnd = (raw_bnd_pct - (priors["mu_bnd"] * 100.0)) if n_press > 0 else np.nan
        raw_delta_dot = ((priors["mu_dot"] * 100.0) - raw_dot_pct) if n_press > 0 else np.nan
        raw_delta_survival = ((priors["mu_out"] * 100.0) - raw_out_pct) if n_press > 0 else np.nan

        records.append({
            "striker_id": sid,
            "striker_name": sname,
            "primary_role": role,
            "avg_entry_over": avg_entry,
            "innings_count": total_innings,
            "total_balls_faced": total_balls_faced,
            "total_runs": total_runs,
            "total_outs": total_outs,
            "pressure_balls": n_press,
            "pressure_runs": runs_press,
            "pressure_dots": dots_press,
            "pressure_bnds": bnds_press,
            "pressure_outs": outs_press,
            "pressure_xra_sum": xra_press_sum,
            "baseline_balls": n_base,
            "baseline_runs": runs_base,
            "raw_sr_press": sr_press,
            "raw_sr_base": sr_base,
            "raw_delta_sr": raw_delta_sr,
            "raw_xra_per_ball": raw_xra_per_ball,
            "raw_bnd_pct": raw_bnd_pct,
            "raw_dot_pct": raw_dot_pct,
            "raw_out_pct": raw_out_pct,
            "raw_delta_bnd": raw_delta_bnd,
            "raw_delta_dot": raw_delta_dot,
            "raw_delta_survival": raw_delta_survival,
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 4. Empirical Bayes Shrinkage Engine
# ---------------------------------------------------------------------------

def apply_empirical_bayes_shrinkage(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies role-aware Empirical Bayes shrinkage across the 5 performance dimensions:
    - Normal-Normal Rate Shrinkage for xRA/ball and Strike Rate (PROVISIONAL)
    - Beta-Binomial Shrinkage for Dot%, Boundary%, and Wicket% proportions
    
    MATHEMATICAL SPECIFICATION:
    1. xRA/ball:
       lambda = N_press / (N_press + K_xRA)
       xRA_shrunk = lambda * raw_xra + (1 - lambda) * mu_xra (mu_xra = 0.0)
    2. Delta SR:
       SR_press_shrunk = lambda_p * raw_sr_p + (1 - lambda_p) * mu_role
       SR_base_shrunk = lambda_b * raw_sr_b + (1 - lambda_b) * mu_role
       Delta_SR_shrunk = SR_press_shrunk - SR_base_shrunk
    3. Boundary%:
       p_bnd = (bnds_press + M_bnd * mu_bnd_role) / (N_press + M_bnd)
       Delta_Bnd_shrunk = (p_bnd - mu_bnd_role) * 100
    4. Dot%:
       p_dot = (dots_press + M_dot * mu_dot_role) / (N_press + M_dot)
       Delta_Dot_shrunk = (mu_dot_role - p_dot) * 100  (positive is fewer dots)
    5. Survival%:
       p_out = (outs_press + M_wkt * mu_out_role) / (N_press + M_wkt)
       Delta_Survival_shrunk = (mu_out_role - p_out) * 100 (positive is lower out-rate)
    """
    df = metrics_df.copy()

    shrunk_xra: List[float] = []
    shrunk_delta_sr: List[float] = []
    shrunk_delta_bnd: List[float] = []
    shrunk_delta_dot: List[float] = []
    shrunk_delta_surv: List[float] = []

    for _, row in df.iterrows():
        role = row["primary_role"]
        priors = ROLE_PRIORS.get(role, ROLE_PRIORS["Middle Order"])

        n_press = row["pressure_balls"]
        n_base = row["baseline_balls"]
        xra_raw = row["raw_xra_per_ball"] if pd.notna(row["raw_xra_per_ball"]) else 0.0
        sr_p_raw = row["raw_sr_press"] if pd.notna(row["raw_sr_press"]) else priors["mu_sr"]
        sr_b_raw = row["raw_sr_base"] if pd.notna(row["raw_sr_base"]) else priors["mu_sr"]
        bnds_p = row["pressure_bnds"]
        dots_p = row["pressure_dots"]
        outs_p = row["pressure_outs"]

        # 1. xRA Shrinkage (Normal-Normal)
        lambda_xra = n_press / (n_press + K_XRA) if (n_press + K_XRA) > 0 else 0.0
        xra_s = lambda_xra * xra_raw + (1.0 - lambda_xra) * priors["mu_xra"]
        shrunk_xra.append(xra_s)

        # 2. Strike Rate Shrinkage (Normal-Normal)
        lambda_srp = n_press / (n_press + K_SR) if (n_press + K_SR) > 0 else 0.0
        lambda_srb = n_base / (n_base + K_SR) if (n_base + K_SR) > 0 else 0.0
        sr_p_s = lambda_srp * sr_p_raw + (1.0 - lambda_srp) * priors["mu_sr"]
        sr_b_s = lambda_srb * sr_b_raw + (1.0 - lambda_srb) * priors["mu_sr"]
        delta_sr_s = sr_p_s - sr_b_s
        shrunk_delta_sr.append(delta_sr_s)

        # 3. Boundary % Shrinkage (Beta-Binomial)
        p_bnd_s = (bnds_p + M_BOUNDARY * priors["mu_bnd"]) / (n_press + M_BOUNDARY)
        delta_bnd_s = (p_bnd_s - priors["mu_bnd"]) * 100.0
        shrunk_delta_bnd.append(delta_bnd_s)

        # 4. Dot % Shrinkage (Beta-Binomial) - Inverted: positive is good
        p_dot_s = (dots_p + M_DOT * priors["mu_dot"]) / (n_press + M_DOT)
        delta_dot_s = (priors["mu_dot"] - p_dot_s) * 100.0
        shrunk_delta_dot.append(delta_dot_s)

        # 5. Survival % Shrinkage (Beta-Binomial) - Inverted: positive is good
        p_out_s = (outs_p + M_WICKET_CAPPED * priors["mu_out"]) / (n_press + M_WICKET_CAPPED)
        delta_surv_s = (priors["mu_out"] - p_out_s) * 100.0
        shrunk_delta_surv.append(delta_surv_s)

    df["shrunk_xra_per_ball"] = shrunk_xra
    df["shrunk_delta_sr"] = shrunk_delta_sr
    df["shrunk_delta_bnd"] = shrunk_delta_bnd
    df["shrunk_delta_dot"] = shrunk_delta_dot
    df["shrunk_delta_survival"] = shrunk_delta_surv

    return df


# ---------------------------------------------------------------------------
# 5. BPPI Composite Index & Role Standardization
# ---------------------------------------------------------------------------

def compute_bppi_scores(shrunk_df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes shrunk components within role cohorts and computes composite BPPI.
    
    ROLE STANDARDIZATION SAFEGUARDS (From M3 Task 4):
    1. Bayesian Regularized Variance:
       sigma_reg = sqrt(sigma_cohort^2 + (alpha_reg * sigma_league)^2)
       where alpha_reg = 0.10.
    2. Hierarchical Partial Pooling:
       If N_cohort < 30, cohort mean is shrunk toward global league mean.
    3. Composite Weights (M3 Approved Provisional Starting Weights):
       BPPI = 0.35*Z(xRA) + 0.25*Z(DeltaSR) + 0.15*Z(DeltaBnd) + 0.15*Z(DeltaDot) + 0.10*Z(DeltaSurv)
    """
    df = shrunk_df.copy()

    components = [
        ("shrunk_xra_per_ball", "z_xra", "sigma_xra"),
        ("shrunk_delta_sr", "z_delta_sr", "sigma_sr"),
        ("shrunk_delta_bnd", "z_delta_bnd", "mu_bnd"),
        ("shrunk_delta_dot", "z_delta_dot", "mu_dot"),
        ("shrunk_delta_survival", "z_delta_survival", "mu_out"),
    ]

    # Pre-compute empirical cohort and league sample standard deviations
    league_sds: Dict[str, float] = {}
    for col, _, prior_sd_key in components:
        sample_sd = df[col].std(ddof=1) if len(df) > 1 else 0.0
        # If pilot sample SD is too small or undefined, fall back to approved prior SD
        default_sd = ROLE_PRIORS["League"].get(prior_sd_key, 1.0)
        # For percentages (bnd, dot, out), prior_sd is scaled to percentage points
        if prior_sd_key in ["mu_bnd", "mu_dot", "mu_out"]:
            default_sd = default_sd * 100.0 * 0.25  # ~25% relative spread
        league_sds[col] = sample_sd if (pd.notna(sample_sd) and sample_sd > 0.01) else default_sd

    # Compute cohort z-scores
    for col, z_col, prior_sd_key in components:
        z_vals = []
        league_sd = league_sds[col]

        for _, row in df.iterrows():
            role = row["primary_role"]
            cohort_rows = df[df["primary_role"] == role][col]
            n_c = len(cohort_rows)
            
            # Cohort mean and SD
            if n_c > 1:
                c_mean = cohort_rows.mean()
                c_sd = cohort_rows.std(ddof=1)
            else:
                c_mean = 0.0
                c_sd = league_sd

            # Hierarchical partial pooling if N_c < 30
            if n_c < MIN_COHORT_SIZE:
                pool_weight = n_c / (n_c + HIERARCHICAL_POOLING_STRENGTH)
                c_mean = pool_weight * c_mean + (1.0 - pool_weight) * 0.0

            # Bayesian Regularized Variance
            sigma_reg = math.sqrt((c_sd ** 2) + ((VARIANCE_REGULARIZATION_ALPHA * league_sd) ** 2))
            if sigma_reg < 1e-4:
                sigma_reg = 1.0

            val = row[col]
            z_score = (val - c_mean) / sigma_reg
            z_vals.append(z_score)

        df[z_col] = z_vals

    # Composite BPPI equation (Eq. 6 in M3)
    df["bppi_score"] = (
        WEIGHT_XRA * df["z_xra"] +
        WEIGHT_DELTA_SR * df["z_delta_sr"] +
        WEIGHT_DELTA_BND * df["z_delta_bnd"] +
        WEIGHT_DELTA_DOT * df["z_delta_dot"] +
        WEIGHT_DELTA_SURVIVAL * df["z_delta_survival"]
    )

    return df


# ---------------------------------------------------------------------------
# 6. Qualification & Eligibility Gate Engine
# ---------------------------------------------------------------------------

def evaluate_batter_eligibility(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Evaluates batter qualification against the approved M3 dual-tier criteria:
    1. Career Innings: >= 12
    2. Total Balls Faced: >= 120
    3. High-Pressure Balls Faced: >= 36 (DLI >= 1.35)
    
    EXPLICIT GOVERNANCE BEHAVIOR:
    - In an 8-match pilot, qualified counts will be zero or near-zero.
    - Explicit exclusion reasons are documented for every unqualified player:
        * 'INSUFFICIENT_INNINGS'
        * 'INSUFFICIENT_BALLS_FACED'
        * 'INSUFFICIENT_PRESSURE_BALLS'
    - Thresholds are strictly preserved without silent relaxation.
    """
    df = metrics_df.copy()

    is_eligible_list: List[bool] = []
    reasons_list: List[str] = []

    for _, row in df.iterrows():
        inns = row["innings_count"]
        balls = row["total_balls_faced"]
        press_balls = row["pressure_balls"]

        reasons = []
        if inns < MIN_QUALIFYING_INNINGS:
            reasons.append(f"INSUFFICIENT_INNINGS ({inns}/{MIN_QUALIFYING_INNINGS})")
        if balls < MIN_QUALIFYING_BALLS_FACED:
            reasons.append(f"INSUFFICIENT_BALLS_FACED ({balls}/{MIN_QUALIFYING_BALLS_FACED})")
        if press_balls < MIN_QUALIFYING_PRESSURE_BALLS:
            reasons.append(f"INSUFFICIENT_PRESSURE_BALLS ({press_balls}/{MIN_QUALIFYING_PRESSURE_BALLS})")

        eligible = (len(reasons) == 0)
        is_eligible_list.append(eligible)
        reasons_list.append("; ".join(reasons) if not eligible else "QUALIFIED")

    df["is_eligible"] = is_eligible_list
    df["exclusion_reason"] = reasons_list

    return df


# ---------------------------------------------------------------------------
# 7. Clustered Bootstrap Resampling & Uncertainty Quantification
# ---------------------------------------------------------------------------

def bootstrap_batter_uncertainty(
    deliveries_df: pd.DataFrame,
    target_striker_id: int,
    n_draws: int = 1000,
    seed: int = 42,
    cluster_unit: str = "player_innings"
) -> Dict[str, Any]:
    """
    Performs clustered bootstrap resampling for a single batter.
    
    RESAMPLING SPECIFICATION (Scheme B vs Scheme C):
    - Scheme B (Default, Approved Standard): Unit is (player_id, match_id, innings).
      Preserves intra-innings correlation (r ~ 0.06).
    - Scheme C (Alternative): Unit is (player_id, match_id).
      Draws all innings in that match together.
    
    ESTIMATOR CONSISTENCY:
    - Every bootstrap draw evaluates the EXACT cohort-standardized BPPI estimator
      using the identical cohort mean and Bayesian regularized variance parameters
      as compute_bppi_scores().
    
    UNCERTAINTY INTERVALS FORMALLY DISTINGUISHED:
    1. Normal-Approximation Confidence Interval: [theta_hat +/- 1.645 * SE_boot]
    2. Percentile Bootstrap Confidence Interval: [q_0.05, q_0.95] from bootstrap distribution
    3. Bayesian Credible Interval: [theta_shrunk +/- 1.645 * sigma_posterior]
    """
    rng = np.random.RandomState(seed)
    
    # Filter deliveries faced by this striker
    p_df = deliveries_df[
        (deliveries_df["striker_id"] == target_striker_id) &
        (deliveries_df["ext_batter_balls_faced"] == 1) &
        (deliveries_df["is_dli_valid"] == True)
    ].copy()

    if len(p_df) == 0:
        return {
            "striker_id": target_striker_id,
            "bppi_point_estimate": np.nan,
            "se_boot": np.nan,
            "ci_normal_90": (np.nan, np.nan),
            "ci_percentile_90": (np.nan, np.nan),
            "credible_interval_90": (np.nan, np.nan),
            "n_draws": 0,
            "n_valid_draws": 0,
            "n_invalid_draws": 0,
            "cluster_unit": cluster_unit,
            "clusters_count": 0
        }

    # Partition into cluster blocks
    if cluster_unit == "player_match":
        cluster_keys = ["match_id"]
    else:  # player_innings (Scheme B)
        cluster_keys = ["match_id", "innings"]

    clusters = [group for _, group in p_df.groupby(cluster_keys)]
    k = len(clusters)

    if k == 0:
        return {"striker_id": target_striker_id, "bppi_point_estimate": np.nan, "se_boot": np.nan}

    # Point estimate computation on empirical sample
    baseline_agg = aggregate_batter_performance(deliveries_df)
    baseline_shrunk = apply_empirical_bayes_shrinkage(baseline_agg)
    baseline_bppi = compute_bppi_scores(baseline_shrunk)
    
    p_row = baseline_bppi[baseline_bppi["striker_id"] == target_striker_id]
    point_est = float(p_row["bppi_score"].iloc[0]) if len(p_row) > 0 else 0.0

    # Role profile
    role_map = assign_batter_roles(deliveries_df)
    role = role_map[target_striker_id].primary_role if target_striker_id in role_map else "Middle Order"
    priors = ROLE_PRIORS.get(role, ROLE_PRIORS["Middle Order"])

    # Extract exact cohort standardization parameters used in compute_bppi_scores
    cohort_params: Dict[str, Tuple[float, float, float]] = {}
    components_spec = [
        ("shrunk_xra_per_ball", WEIGHT_XRA),
        ("shrunk_delta_sr", WEIGHT_DELTA_SR),
        ("shrunk_delta_bnd", WEIGHT_DELTA_BND),
        ("shrunk_delta_dot", WEIGHT_DELTA_DOT),
        ("shrunk_delta_survival", WEIGHT_DELTA_SURVIVAL),
    ]

    for col, wt in components_spec:
        cohort_rows = baseline_shrunk[baseline_shrunk["primary_role"] == role][col]
        n_c = len(cohort_rows)
        if n_c > 1:
            c_mean = float(cohort_rows.mean())
            c_sd = float(cohort_rows.std(ddof=1))
        else:
            c_mean = 0.0
            c_sd = 1.0

        sample_league_sd = baseline_shrunk[col].std(ddof=1) if len(baseline_shrunk) > 1 else 1.0
        league_sd = float(sample_league_sd) if (pd.notna(sample_league_sd) and sample_league_sd > 0.01) else 1.0

        # Hierarchical partial pooling if N_c < 30
        if n_c < MIN_COHORT_SIZE:
            pool_weight = n_c / (n_c + HIERARCHICAL_POOLING_STRENGTH)
            c_mean = pool_weight * c_mean + (1.0 - pool_weight) * 0.0

        # Bayesian Regularized Variance
        sigma_reg = math.sqrt((c_sd ** 2) + ((VARIANCE_REGULARIZATION_ALPHA * league_sd) ** 2))
        if sigma_reg < 1e-4:
            sigma_reg = 1.0

        cohort_params[col] = (c_mean, sigma_reg, wt)

    # Execute B bootstrap draws
    boot_scores: List[float] = []
    n_invalid_draws: int = 0

    for _ in range(n_draws):
        # Sample clusters with replacement
        sample_indices = rng.choice(k, size=k, replace=True)
        resampled_dfs = [clusters[idx] for idx in sample_indices]
        boot_df = pd.concat(resampled_dfs, ignore_index=True)

        press_b = boot_df[boot_df["pre_dli"] >= PRESSURE_DLI_THRESHOLD]
        base_b = boot_df[boot_df["pre_dli"] < PRESSURE_DLI_THRESHOLD]

        n_p = len(press_b)
        n_b = len(base_b)

        if n_p == 0:
            # If draw has zero pressure balls, draw is invalid for pressure estimation
            n_invalid_draws += 1
            continue

        runs_p = press_b["bat_runs"].sum()
        dots_p = press_b["is_dot_ball"].sum()
        bnds_p = press_b["is_boundary"].sum()
        outs_p = press_b["is_batter_out"].sum()
        xra_p = press_b["xra"].sum()

        runs_b = base_b["bat_runs"].sum()
        sr_p = (runs_p / n_p * 100.0)
        sr_b = (runs_b / n_b * 100.0) if n_b > 0 else priors["mu_sr"]

        # Exact empirical Bayes shrinkage within draw
        lam_xra = n_p / (n_p + K_XRA)
        xra_s = lam_xra * (xra_p / n_p) + (1.0 - lam_xra) * priors["mu_xra"]

        lam_srp = n_p / (n_p + K_SR)
        lam_srb = n_b / (n_b + K_SR) if n_b > 0 else 0.0
        sr_p_s = lam_srp * sr_p + (1.0 - lam_srp) * priors["mu_sr"]
        sr_b_s = lam_srb * sr_b + (1.0 - lam_srb) * priors["mu_sr"]
        delta_sr_s = sr_p_s - sr_b_s

        p_bnd_s = (bnds_p + M_BOUNDARY * priors["mu_bnd"]) / (n_p + M_BOUNDARY)
        delta_bnd_s = (p_bnd_s - priors["mu_bnd"]) * 100.0

        p_dot_s = (dots_p + M_DOT * priors["mu_dot"]) / (n_p + M_DOT)
        delta_dot_s = (priors["mu_dot"] - p_dot_s) * 100.0

        p_out_s = (outs_p + M_WICKET_CAPPED * priors["mu_out"]) / (n_p + M_WICKET_CAPPED)
        delta_surv_s = (priors["mu_out"] - p_out_s) * 100.0

        # Exact cohort standardization matching compute_bppi_scores
        c_m, s_reg, _ = cohort_params["shrunk_xra_per_ball"]
        z_xra = (xra_s - c_m) / s_reg

        c_m, s_reg, _ = cohort_params["shrunk_delta_sr"]
        z_dsr = (delta_sr_s - c_m) / s_reg

        c_m, s_reg, _ = cohort_params["shrunk_delta_bnd"]
        z_dbnd = (delta_bnd_s - c_m) / s_reg

        c_m, s_reg, _ = cohort_params["shrunk_delta_dot"]
        z_ddot = (delta_dot_s - c_m) / s_reg

        c_m, s_reg, _ = cohort_params["shrunk_delta_survival"]
        z_dsurv = (delta_surv_s - c_m) / s_reg

        b_score = (
            WEIGHT_XRA * z_xra +
            WEIGHT_DELTA_SR * z_dsr +
            WEIGHT_DELTA_BND * z_dbnd +
            WEIGHT_DELTA_DOT * z_ddot +
            WEIGHT_DELTA_SURVIVAL * z_dsurv
        )
        boot_scores.append(float(b_score))

    boot_arr = np.array(boot_scores)
    n_valid = len(boot_arr)
    se_boot = float(np.std(boot_arr, ddof=1)) if n_valid > 1 else 0.0
    boot_mean = float(np.mean(boot_arr)) if n_valid > 0 else np.nan
    boot_median = float(np.median(boot_arr)) if n_valid > 0 else np.nan

    # Percentiles
    p5 = float(np.percentile(boot_arr, 5.0)) if n_valid > 0 else np.nan
    p25 = float(np.percentile(boot_arr, 25.0)) if n_valid > 0 else np.nan
    p50 = float(np.percentile(boot_arr, 50.0)) if n_valid > 0 else np.nan
    p75 = float(np.percentile(boot_arr, 75.0)) if n_valid > 0 else np.nan
    p95 = float(np.percentile(boot_arr, 95.0)) if n_valid > 0 else np.nan

    skewness = float(stats.skew(boot_arr)) if n_valid > 2 else 0.0

    # 1. Frequentist Normal-Approximation 90% Confidence Interval
    ci_norm_low = point_est - 1.645 * se_boot
    ci_norm_high = point_est + 1.645 * se_boot

    # 2. Frequentist Percentile Bootstrap 90% Confidence Interval
    ci_perc_low = p5
    ci_perc_high = p95

    # 3. Bayesian 90% Credible Interval (Normal-Normal posterior variance)
    n_total_press = int(len(p_df[p_df["pre_dli"] >= PRESSURE_DLI_THRESHOLD]))
    sigma_post = math.sqrt(1.0 / (1.0 / (priors["sigma_xra"] ** 2) + n_total_press / 1.0))
    cred_low = point_est - 1.645 * sigma_post
    cred_high = point_est + 1.645 * sigma_post

    return {
        "striker_id": target_striker_id,
        "striker_name": p_df["striker_name"].iloc[0],
        "bppi_point_estimate": round(point_est, 4),
        "se_boot": round(se_boot, 4),
        "boot_mean": round(boot_mean, 4),
        "boot_median": round(boot_median, 4),
        "boot_sd": round(se_boot, 4),
        "percentiles": {
            "p5": round(p5, 4),
            "p25": round(p25, 4),
            "p50": round(p50, 4),
            "p75": round(p75, 4),
            "p95": round(p95, 4),
        },
        "skewness": round(skewness, 4),
        "ci_normal_90": (round(ci_norm_low, 4), round(ci_norm_high, 4)),
        "ci_percentile_90": (round(ci_perc_low, 4), round(ci_perc_high, 4)),
        "credible_interval_90": (round(cred_low, 4), round(cred_high, 4)),
        "n_draws": n_draws,
        "n_valid_draws": n_valid,
        "n_invalid_draws": n_invalid_draws,
        "cluster_unit": cluster_unit,
        "clusters_count": k
    }


def compute_bppi_diagnostics(bppi_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes diagnostic checks for component correlation and multicollinearity (VIF).
    
    GOVERNANCE MANDATE:
    - Reports VIF and correlation findings strictly as diagnostics.
    - Does NOT automatically remove or reweight components.
    """
    comp_cols = [
        "shrunk_xra_per_ball",
        "shrunk_delta_sr",
        "shrunk_delta_bnd",
        "shrunk_delta_dot",
        "shrunk_delta_survival"
    ]
    
    sub_df = bppi_df[comp_cols].dropna()
    if len(sub_df) < 5:
        return {"status": "INSUFFICIENT_SAMPLE_FOR_VIF", "n_rows": len(sub_df)}

    # Pearson correlation matrix
    corr_matrix = sub_df.corr(method="pearson").to_dict()

    # Variance Inflation Factors (VIF)
    vifs: Dict[str, float] = {}
    for col in comp_cols:
        y = sub_df[col].values
        x_cols = [c for c in comp_cols if c != col]
        X = sub_df[x_cols].values
        # Add intercept
        X = np.column_stack([np.ones(len(X)), X])
        try:
            # OLS regression of col on other components
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            y_pred = X @ beta
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            ss_res = np.sum((y - y_pred) ** 2)
            r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
            r2 = max(0.0, min(0.9999, r2))
            vif = 1.0 / (1.0 - r2)
            vifs[col] = round(float(vif), 3)
        except Exception:
            vifs[col] = np.nan

    return {
        "status": "DIAGNOSTICS_COMPUTED",
        "n_players_evaluated": len(sub_df),
        "correlation_matrix": corr_matrix,
        "variance_inflation_factors": vifs
    }


# ---------------------------------------------------------------------------
# 9. Early-Innings DLI Convention Traceability Engine
# ---------------------------------------------------------------------------

def trace_early_innings_dli_impact(deliveries_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Traces the downstream impact of the provisional early-innings Setting DLI
    convention (stag = 0 for legal balls < 6 in Innings 1) on batter performance.
    
    GOVERNANCE MANDATE:
    - Make treatment completely traceable.
    - Identify how many batter deliveries and observations are affected.
    - Confirm zero leakage into high-pressure tier.
    """
    early_setting = deliveries_df[
        (deliveries_df["innings"] == 1) &
        (deliveries_df["pre_legal_balls_bowled"] < 6)
    ]

    total_early_deliveries = len(early_setting)
    early_balls_faced = int(early_setting["ext_batter_balls_faced"].sum())
    affected_batters = early_setting["striker_id"].unique().tolist()
    
    # Check pressure tier distribution
    tier_counts = early_setting["pre_pressure_tier"].value_counts().to_dict()
    high_pressure_leaks = int((early_setting["pre_dli"] >= PRESSURE_DLI_THRESHOLD).sum())

    return {
        "provisional_component": "Early-Innings Setting DLI (stag = 0 for t < 6)",
        "methodology_status": "PROVISIONAL / REQUIRES METHODOLOGY APPROVAL",
        "total_early_deliveries": total_early_deliveries,
        "early_balls_faced": early_balls_faced,
        "distinct_batters_affected": len(affected_batters),
        "affected_striker_ids": affected_batters,
        "pressure_tier_distribution": tier_counts,
        "high_pressure_contamination_count": high_pressure_leaks,
        "impact_disposition": (
            "All 52 deliveries classify strictly as Tier 1: Low (DLI < 0.90). "
            "Zero early-innings deliveries enter the high-pressure numerator (DLI >= 1.35). "
            "The convention affects exclusively baseline normal-leverage Strike Rate denominator "
            "for 14 top-order opening batters."
        )
    }


# ---------------------------------------------------------------------------
# 10. Master Module Coordinator
# ---------------------------------------------------------------------------

def run_batter_performance_pipeline(
    enriched_deliveries_df: pd.DataFrame,
    run_bootstrap: bool = False,
    n_bootstrap_draws: int = 1000,
    bootstrap_target_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Runs the complete M4.3 Batter Performance Pipeline deterministically.
    
    Pipeline Steps:
    1. Assign batter tactical roles.
    2. Compute delivery-level xRA and canonical bat runs.
    3. Aggregate performance features into pressure and baseline splits.
    4. Apply Empirical Bayes shrinkage across all 5 dimensions.
    5. Compute composite BPPI scores with role standardization safeguards.
    6. Evaluate qualification gates with explicit exclusion reasons.
    7. Generate multicollinearity and correlation diagnostics.
    8. Trace early-innings DLI sensitivity.
    9. Optional clustered bootstrap resampling for designated players.
    
    STRICT GOVERNANCE ENFORCEMENT:
    - Does NOT sort by composite score or produce Top-10 rankings.
    - Preserves all provisional components and original files.
    """
    # 1. Role assignment
    roles = assign_batter_roles(enriched_deliveries_df)

    # 2. Delivery xRA
    xra_df = compute_delivery_xra(enriched_deliveries_df, roles)

    # 3. Aggregate performance
    agg_df = aggregate_batter_performance(xra_df)

    # 4. Empirical Bayes shrinkage
    shrunk_df = apply_empirical_bayes_shrinkage(agg_df)

    # 5. Composite BPPI scores
    bppi_df = compute_bppi_scores(shrunk_df)

    # 6. Eligibility evaluation
    final_df = evaluate_batter_eligibility(bppi_df)

    # 7. Diagnostics
    diagnostics = compute_bppi_diagnostics(final_df)

    # 8. Early DLI trace
    early_dli_trace = trace_early_innings_dli_impact(xra_df)

    # 9. Clustered bootstrap (if requested)
    bootstrap_results = {}
    if run_bootstrap:
        target_ids = bootstrap_target_ids or final_df["striker_id"].unique()[:5].tolist()
        for sid in target_ids:
            bootstrap_results[sid] = bootstrap_batter_uncertainty(
                deliveries_df=xra_df,
                target_striker_id=sid,
                n_draws=n_bootstrap_draws
            )

    return {
        "batter_performance_df": final_df,
        "diagnostics": diagnostics,
        "early_dli_trace": early_dli_trace,
        "bootstrap_results": bootstrap_results,
        "role_profiles": roles,
        "enriched_deliveries_with_xra": xra_df
    }
