"""
RR ScoutIQ - Module M4.4: Bowler Performance Engine
===================================================

Evidence Level: IMPLEMENTATION CORRECTNESS & PILOT DIAGNOSTIC
Implementation Architecture:
- Evaluates bowler execution, run restriction, and breakthrough creation decoupling
  situational difficulty from bowler skill.
- Strictly consumes pre-delivery match state from Module M4.2.
- Calculates the five approved PPBI components (M3 Section 6.3 & Eq. 8):
    1. Expected Runs Saved per Ball (xRS/ball) [Weight: 0.35]
    2. Economy Rate Delta (Delta Econ) [Weight: 0.20]
    3. Wicket Breakthrough Percentage Delta (Delta Wkt%) [Weight: 0.25]
    4. Dot Ball Creation Percentage Delta (Delta Dot%) [Weight: 0.10]
    5. Boundary Concession Suppression Percentage Delta (Delta BndCon%) [Weight: 0.10]
- Implements cricket accounting:
    * Bowler debit runs strictly uses ext_bowler_debit_runs (Law-compliant).
    * Legal deliveries strictly uses ext_is_legal_delivery.
    * Wicket attribution credits direct modes (Bowled, Caught, LBW, Stumped, Hit Wicket).
      Run Out and Retired Out are not credited to the bowler; Retired Hurt is not a wicket.
- Implements role-aware cohort classification:
    * Powerplay Specialist (>= 40% of regulation workload in overs 1-6).
    * Death Specialist (>= 30% of regulation workload in overs 16-20).
    * Middle Enforcer (remainder).
    * Multi-role tie-break resolution: Bowling workloads exceeding both PP and Death thresholds
      are assigned using primary workload dominance (e.g. PP% vs Death%), ensuring exhaustive
      and mutually exclusive cohort partitioning.
- Implements Empirical Bayes shrinkage:
    * Beta-Binomial shrinkage for proportions (Dot%, Boundary Concession%, Wicket Breakthrough%).
    * Normal-Normal rate shrinkage for continuous rates (xRS/ball, Economy Rate) [PROVISIONAL].
- Implements clustered bootstrap uncertainty quantification (Scheme B: player-innings resampling).
- Distinguishes Normal-approximation CIs, percentile bootstrap CIs, and Bayesian credible intervals.
- Enforces strict qualification criteria (>=12 innings, >=144 legal balls, >=42 pressure balls).
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

# PPBI Component Weights (Approved M3 Starting Weights - Section 6.3.2)
WEIGHT_XRS: float = 0.35
WEIGHT_DELTA_ECON: float = 0.20
WEIGHT_DELTA_WKT: float = 0.25
WEIGHT_DELTA_DOT: float = 0.10
WEIGHT_DELTA_BND_CON: float = 0.10

# Leverage Cutoff for High Pressure (Approved M3 Threshold)
PRESSURE_DLI_THRESHOLD: float = 1.35  # Tiers 3 (High) & 4 (Extreme)

# Eligibility Thresholds (Approved M3 Dual-Tier Qualifications for Bowlers)
MIN_QUALIFYING_INNINGS: int = 12
MIN_QUALIFYING_LEGAL_BALLS: int = 144
MIN_QUALIFYING_PRESSURE_BALLS: int = 42

# Bowling Role Cutoffs (Approved M3 Definition B1)
ROLE_POWERPLAY_MIN_PCT: float = 0.40  # Workload >= 40% in overs 1-6
ROLE_DEATH_MIN_PCT: float = 0.30       # Workload >= 30% in overs 16-20
# Middle Enforcer: Remainder

# Empirical Bayes Shrinkage Prior Strengths (Approved M3 Specifications)
# Proportions: Beta-Binomial (M equivalent sample size in balls)
M_DOT: float = 135.8
M_BOUNDARY: float = 114.7
M_BND_CON: float = 114.7  # Alias for M_BOUNDARY
M_WICKET_CAPPED: float = 90.0  # Capped regularization from uncapped 1613.1

# Continuous Rates: Normal-Normal James-Stein (K equivalent sample size in balls)
# In high-pressure splits, talent variance expands (tau_Econ = 1.50 rpo, K_Econ = 48.56 balls)
K_ECON: float = 48.56           # Dimensionally corrected in M3 Statistical Consistency Audit
K_XRS: float = 42.2             # M3 Empirical evidence baseline

# Role Standardization Safeguards
VARIANCE_REGULARIZATION_ALPHA: float = 0.10
MIN_COHORT_SIZE: int = 30
HIERARCHICAL_POOLING_STRENGTH: float = 15.0

# Empirical League & Role Priors (M3 Baseline Distributions)
ROLE_PRIORS: Dict[str, Dict[str, float]] = {
    "Powerplay Specialist": {
        "mu_econ": 8.52,
        "sigma_econ": 0.88,
        "mu_dot": 0.4500,
        "mu_bnd": 0.1800,
        "mu_wkt": 0.0571,
        "mu_xrs": 0.0000,
        "sigma_xrs": 0.2500,
    },
    "Middle Enforcer": {
        "mu_econ": 8.30,
        "sigma_econ": 0.99,
        "mu_dot": 0.3800,
        "mu_bnd": 0.1600,
        "mu_wkt": 0.0545,
        "mu_xrs": 0.0000,
        "sigma_xrs": 0.2200,
    },
    "Death Specialist": {
        "mu_econ": 9.00,
        "sigma_econ": 0.79,
        "mu_dot": 0.3200,
        "mu_bnd": 0.2200,
        "mu_wkt": 0.0622,
        "mu_xrs": 0.0000,
        "sigma_xrs": 0.2800,
    },
    "League": {
        "mu_econ": 8.45,
        "sigma_econ": 0.925,
        "mu_dot": 0.4000,
        "mu_bnd": 0.1946,
        "mu_wkt": 0.0525,
        "mu_xrs": 0.0000,
        "sigma_xrs": 0.2500,
    }
}

# Empirical Run Expectation Grid E[Runs Conceded | Phase, Tier] (League Baselines)
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
class BowlerRoleProfile:
    bowler_id: int
    bowler_name: str
    innings_count: int
    total_legal_balls: int
    powerplay_balls: int
    middle_balls: int
    death_balls: int
    powerplay_pct: float
    middle_pct: float
    death_pct: float
    primary_role: str


@dataclass
class BowlerEligibilityRecord:
    bowler_id: int
    bowler_name: str
    innings_count: int
    total_legal_balls: int
    pressure_legal_balls: int
    is_eligible: bool
    exclusion_reasons: List[str]


@dataclass
class PPBIComponentBundle:
    raw_xrs_per_ball: float
    raw_delta_econ: float
    raw_delta_wkt: float
    raw_delta_dot: float
    raw_delta_bnd_con: float
    shrunk_xrs_per_ball: float
    shrunk_delta_econ: float
    shrunk_delta_wkt: float
    shrunk_delta_dot: float
    shrunk_delta_bnd_con: float
    z_xrs: float
    z_delta_econ: float
    z_delta_wkt: float
    z_delta_dot: float
    z_delta_bnd_con: float
    ppbi_score: float


# ---------------------------------------------------------------------------
# 1. Bowler Role Classification Engine
# ---------------------------------------------------------------------------

def assign_bowler_roles(deliveries_df: pd.DataFrame) -> Dict[int, BowlerRoleProfile]:
    """
    Assigns career tactical bowling roles based on actual legal-ball workload across phases.
    
    CRICKET SPECIFICATION & SUPER OVER ISOLATION:
    - Workload is computed strictly on regulation innings (innings <= 2, is_super_over == False).
    - Super Over deliveries are excluded from Powerplay and Death percentages.
    
    ROLE CUTOFFS (Approved M3 Definition B1):
    - Powerplay Specialist: Powerplay workload >= 40.0%
    - Death Specialist: Death workload >= 30.0%
    - Middle Enforcer: Remainder
    
    MULTI-ROLE RESOLUTION LOGIC:
    - If a bowler qualifies for both Powerplay (>=40%) and Death (>=30%), the role
      is resolved by workload dominance:
      If Powerplay_pct >= Death_pct -> Powerplay Specialist
      Else -> Death Specialist
    - If a bowler has 0 regulation legal deliveries, assigned 'Middle Enforcer'.
    """
    reg_df = deliveries_df[
        (deliveries_df["ext_is_legal_delivery"] == True) &
        (deliveries_df["innings"] <= 2)
    ].copy()

    role_profiles: Dict[int, BowlerRoleProfile] = {}
    
    # Get all unique bowlers in full delivery set
    all_bowler_ids = deliveries_df[["bowler_id", "bowler_name"]].drop_duplicates()

    for _, b_row in all_bowler_ids.iterrows():
        bid = int(b_row["bowler_id"])
        bname = str(b_row["bowler_name"])

        b_reg = reg_df[reg_df["bowler_id"] == bid]
        tot_legal = len(b_reg)
        inns_count = len(b_reg[["match_id", "innings"]].drop_duplicates())

        if tot_legal == 0:
            role_profiles[bid] = BowlerRoleProfile(
                bowler_id=bid,
                bowler_name=bname,
                innings_count=0,
                total_legal_balls=0,
                powerplay_balls=0,
                middle_balls=0,
                death_balls=0,
                powerplay_pct=0.0,
                middle_pct=0.0,
                death_pct=0.0,
                primary_role="Middle Enforcer"
            )
            continue

        pp_balls = int((b_reg["pre_match_phase"] == "Powerplay").sum())
        mid_balls = int((b_reg["pre_match_phase"] == "Middle").sum())
        death_balls = int((b_reg["pre_match_phase"] == "Death").sum())

        pp_pct = pp_balls / tot_legal
        mid_pct = mid_balls / tot_legal
        death_pct = death_balls / tot_legal

        # Role resolution
        is_pp = pp_pct >= ROLE_POWERPLAY_MIN_PCT
        is_death = death_pct >= ROLE_DEATH_MIN_PCT

        if is_pp and is_death:
            # Overlap tie-break: assign to dominant phase
            primary_role = "Powerplay Specialist" if pp_pct >= death_pct else "Death Specialist"
        elif is_pp:
            primary_role = "Powerplay Specialist"
        elif is_death:
            primary_role = "Death Specialist"
        else:
            primary_role = "Middle Enforcer"

        role_profiles[bid] = BowlerRoleProfile(
            bowler_id=bid,
            bowler_name=bname,
            innings_count=inns_count,
            total_legal_balls=tot_legal,
            powerplay_balls=pp_balls,
            middle_balls=mid_balls,
            death_balls=death_balls,
            powerplay_pct=round(pp_pct, 4),
            middle_pct=round(mid_pct, 4),
            death_pct=round(death_pct, 4),
            primary_role=primary_role
        )

    return role_profiles


# ---------------------------------------------------------------------------
# 2. Delivery-Level Feature Enrichment & Expected Runs Saved (xRS)
# ---------------------------------------------------------------------------

def compute_delivery_xrs(
    deliveries_df: pd.DataFrame,
    role_map: Optional[Dict[int, BowlerRoleProfile]] = None
) -> pd.DataFrame:
    """
    Enriches delivery DataFrame with canonical bowler debit runs, boundary concession flags,
    bowler wicket attribution, and situational Expected Runs Saved (xRS).
    
    xRS = E[runs_conceded | Phase, Tier] - ext_bowler_debit_runs
    
    ANTI-LEAKAGE INTEGRITY:
    - Expected runs baseline depends strictly on pre-delivery match state (Phase, Tier).
    - Current delivery outcome does NOT affect its own expectation.
    - Bowler wicket attribution strictly credits direct modes (Bowled, Caught, LBW, Stumped, Hit Wicket).
    """
    df = deliveries_df.copy()
    if role_map is None:
        role_map = assign_bowler_roles(df)

    # Ball classification flags
    df["is_boundary_conceded_four"] = (df["is_four"] == 1).astype(int)
    df["is_boundary_conceded_six"] = (df["is_six"] == 1).astype(int)
    df["is_boundary_conceded"] = (
        (df["is_boundary_conceded_four"] == 1) | (df["is_boundary_conceded_six"] == 1)
    ).astype(int)

    # Bowler dot ball: legal delivery with zero bowler debit runs
    df["is_bowler_dot"] = (
        (df["ext_is_legal_delivery"] == True) & (df["ext_bowler_debit_runs"] == 0)
    ).astype(int)

    # Bowler wicket attribution (Law-compliant: Bowled, Caught, LBW, Stumped, Hit Wicket)
    # Direct creditable modes
    creditable_dismissal_types = {"Bowled", "Caught", "LBW", "Stump", "Stumped", "Hit Wicket"}
    df["is_bowler_wicket_law"] = (
        (df["is_wicket"] == 1) &
        (df["dismissal_type"].isin(creditable_dismissal_types)) &
        (df["ext_is_retired_hurt"] == False)
    ).astype(int)

    # Fallback to enriched ext_is_bowler_wicket if present, otherwise law-derived
    if "ext_is_bowler_wicket" in df.columns:
        df["is_bowler_wicket_final"] = (
            (df["ext_is_bowler_wicket"] == True) & (df["ext_is_retired_hurt"] == False)
        ).astype(int)
    else:
        df["is_bowler_wicket_final"] = df["is_bowler_wicket_law"]

    # Expected runs conceded baseline
    def get_expected_runs(row) -> float:
        phase = str(row["pre_match_phase"])
        tier = str(row["pre_pressure_tier"])
        return EMPIRICAL_RUN_EXPECTATIONS.get((phase, tier), GLOBAL_EXPECTED_RUNS_PER_BALL)

    df["expected_runs_conceded"] = df.apply(get_expected_runs, axis=1)

    # xRS is defined on legal deliveries bowled (ext_is_legal_delivery == True)
    df["xrs"] = np.where(
        df["ext_is_legal_delivery"] == True,
        df["expected_runs_conceded"] - df["ext_bowler_debit_runs"],
        0.0
    )

    # Attach bowler tactical primary role
    df["bowler_role"] = df["bowler_id"].map(
        lambda bid: role_map[bid].primary_role if bid in role_map else "Middle Enforcer"
    )

    return df


# ---------------------------------------------------------------------------
# 3. Aggregation & Performance Feature Matrix
# ---------------------------------------------------------------------------

def aggregate_bowler_performance(enriched_deliveries_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates delivery-level records into player-level features partitioned by
    high-pressure (DLI >= 1.35) and baseline leverage (DLI < 1.35).
    
    EXCLUSIONS RESPECTED:
    - Deliveries with is_dli_valid == False (e.g. synthetic DLS curtailment) are excluded
      from high-pressure metrics.
    - Super Over deliveries are included in high-pressure aggregations.
    """
    df = enriched_deliveries_df.copy()

    records: List[Dict[str, Any]] = []

    for (bid, bname), p_df in df.groupby(["bowler_id", "bowler_name"]):
        role = p_df["bowler_role"].iloc[0] if "bowler_role" in p_df.columns else "Middle Enforcer"

        # Legal balls
        legal_df = p_df[p_df["ext_is_legal_delivery"] == True]
        total_legal = len(legal_df)
        total_inns = len(p_df[["match_id", "innings"]].drop_duplicates())
        total_runs = int(legal_df["ext_bowler_debit_runs"].sum())
        total_wkts = int(legal_df["is_bowler_wicket_final"].sum())

        # Pressure partition (DLI >= 1.35 and is_dli_valid == True)
        press_df = legal_df[
            (legal_df["pre_dli"] >= PRESSURE_DLI_THRESHOLD) &
            (legal_df["is_dli_valid"] == True)
        ]
        n_press = len(press_df)
        runs_press = int(press_df["ext_bowler_debit_runs"].sum())
        wkts_press = int(press_df["is_bowler_wicket_final"].sum())
        dots_press = int(press_df["is_bowler_dot"].sum())
        bnds_press = int(press_df["is_boundary_conceded"].sum())
        xrs_press_sum = float(press_df["xrs"].sum())

        # Baseline leverage partition (DLI < 1.35 and is_dli_valid == True)
        base_df = legal_df[
            (legal_df["pre_dli"] < PRESSURE_DLI_THRESHOLD) &
            (legal_df["is_dli_valid"] == True)
        ]
        n_base = len(base_df)
        runs_base = int(base_df["ext_bowler_debit_runs"].sum())
        wkts_base = int(base_df["is_bowler_wicket_final"].sum())
        dots_base = int(base_df["is_bowler_dot"].sum())
        bnds_base = int(base_df["is_boundary_conceded"].sum())

        # Raw rate calculations
        # Economy rates (runs / (legal_balls / 6.0))
        raw_econ_press = (runs_press / (n_press / 6.0)) if n_press > 0 else np.nan
        raw_econ_base = (runs_base / (n_base / 6.0)) if n_base > 0 else np.nan
        # Delta Economy: Econ_base - Econ_press (positive = lower economy under fire = GOOD)
        raw_delta_econ = (raw_econ_base - raw_econ_press) if (pd.notna(raw_econ_base) and pd.notna(raw_econ_press)) else np.nan

        # xRS per ball: xrs_press_sum / n_press (positive = runs saved = GOOD)
        raw_xrs_per_ball = (xrs_press_sum / n_press) if n_press > 0 else np.nan

        # Percentages
        raw_wkt_pct_press = (wkts_press / n_press * 100.0) if n_press > 0 else np.nan
        raw_dot_pct_press = (dots_press / n_press * 100.0) if n_press > 0 else np.nan
        raw_bnd_con_pct_press = (bnds_press / n_press * 100.0) if n_press > 0 else np.nan

        # Baseline expectations from role priors
        priors = ROLE_PRIORS.get(role, ROLE_PRIORS["Middle Enforcer"])
        e_wkt_pct = priors["mu_wkt"] * 100.0
        e_dot_pct = priors["mu_dot"] * 100.0
        e_bnd_con_pct = priors["mu_bnd"] * 100.0

        # Raw deltas relative to baselines
        raw_delta_wkt = (raw_wkt_pct_press - e_wkt_pct) if n_press > 0 else np.nan
        raw_delta_dot = (raw_dot_pct_press - e_dot_pct) if n_press > 0 else np.nan
        raw_delta_bnd_con = (e_bnd_con_pct - raw_bnd_con_pct_press) if n_press > 0 else np.nan

        records.append({
            "bowler_id": bid,
            "bowler_name": bname,
            "primary_role": role,
            "innings_count": total_inns,
            "total_legal_balls": total_legal,
            "total_runs_conceded": total_runs,
            "total_wickets": total_wkts,
            "pressure_legal_balls": n_press,
            "pressure_runs": runs_press,
            "pressure_dots": dots_press,
            "pressure_bnds": bnds_press,
            "pressure_wickets": wkts_press,
            "pressure_xrs_sum": xrs_press_sum,
            "baseline_legal_balls": n_base,
            "baseline_runs": runs_base,
            "baseline_dots": dots_base,
            "baseline_bnds": bnds_base,
            "baseline_wickets": wkts_base,
            "raw_econ_press": raw_econ_press,
            "raw_econ_base": raw_econ_base,
            "raw_delta_econ": raw_delta_econ,
            "raw_xrs_per_ball": raw_xrs_per_ball,
            "raw_wkt_pct_press": raw_wkt_pct_press,
            "raw_dot_pct_press": raw_dot_pct_press,
            "raw_bnd_con_pct_press": raw_bnd_con_pct_press,
            "raw_delta_wkt": raw_delta_wkt,
            "raw_delta_dot": raw_delta_dot,
            "raw_delta_bnd_con": raw_delta_bnd_con,
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 4. Empirical Bayes Shrinkage Sub-Engine
# ---------------------------------------------------------------------------

def apply_empirical_bayes_shrinkage(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies role-aware Empirical Bayes shrinkage across the 5 performance dimensions:
    - Normal-Normal Rate Shrinkage for xRS/ball and Economy Rate (PROVISIONAL)
    - Beta-Binomial Shrinkage for Dot%, Boundary Concession%, and Wicket Breakthrough% proportions
    
    MATHEMATICAL SPECIFICATION:
    1. xRS/ball:
       lambda = N_press / (N_press + K_xRS)
       xRS_shrunk = lambda * raw_xrs + (1 - lambda) * mu_xrs (mu_xrs = 0.0)
    2. Delta Econ:
       Econ_press_shrunk = lambda_p * raw_econ_p + (1 - lambda_p) * mu_role
       Econ_base_shrunk = lambda_b * raw_econ_b + (1 - lambda_b) * mu_role
       Delta_Econ_shrunk = Econ_base_shrunk - Econ_press_shrunk (positive is good)
    3. Wicket Breakthrough%:
       p_wkt = (wkts_press + M_wkt * mu_wkt_role) / (N_press + M_wkt)
       Delta_Wkt_shrunk = (p_wkt - mu_wkt_role) * 100.0 (positive is higher wicket rate)
    4. Dot%:
       p_dot = (dots_press + M_dot * mu_dot_role) / (N_press + M_dot)
       Delta_Dot_shrunk = (p_dot - mu_dot_role) * 100.0 (positive is more dots forced)
    5. Boundary Concession%:
       p_bnd = (bnds_press + M_bnd * mu_bnd_role) / (N_press + M_bnd)
       Delta_BndCon_shrunk = (mu_bnd_role - p_bnd) * 100.0 (positive is fewer boundaries conceded)
    """
    df = metrics_df.copy()

    shrunk_xrs: List[float] = []
    shrunk_delta_econ: List[float] = []
    shrunk_delta_wkt: List[float] = []
    shrunk_delta_dot: List[float] = []
    shrunk_delta_bnd_con: List[float] = []

    for _, row in df.iterrows():
        role = row["primary_role"]
        priors = ROLE_PRIORS.get(role, ROLE_PRIORS["Middle Enforcer"])

        n_press = row["pressure_legal_balls"]
        n_base = row["baseline_legal_balls"]
        xrs_raw = row["raw_xrs_per_ball"] if pd.notna(row["raw_xrs_per_ball"]) else 0.0
        econ_p_raw = row["raw_econ_press"] if pd.notna(row["raw_econ_press"]) else priors["mu_econ"]
        econ_b_raw = row["raw_econ_base"] if pd.notna(row["raw_econ_base"]) else priors["mu_econ"]
        dots_p = row["pressure_dots"]
        bnds_p = row["pressure_bnds"]
        wkts_p = row["pressure_wickets"]

        # 1. Normal-Normal xRS shrinkage
        lambda_xrs = n_press / (n_press + K_XRS) if (n_press + K_XRS) > 0 else 0.0
        xrs_s = lambda_xrs * xrs_raw + (1.0 - lambda_xrs) * priors["mu_xrs"]
        shrunk_xrs.append(round(xrs_s, 4))

        # 2. Normal-Normal Economy shrinkage
        lambda_econ_p = n_press / (n_press + K_ECON) if (n_press + K_ECON) > 0 else 0.0
        lambda_econ_b = n_base / (n_base + K_ECON) if (n_base + K_ECON) > 0 else 0.0
        econ_p_s = lambda_econ_p * econ_p_raw + (1.0 - lambda_econ_p) * priors["mu_econ"]
        econ_b_s = lambda_econ_b * econ_b_raw + (1.0 - lambda_econ_b) * priors["mu_econ"]
        delta_econ_s = econ_b_s - econ_p_s
        shrunk_delta_econ.append(round(delta_econ_s, 4))

        # 3. Beta-Binomial Wicket Breakthrough% shrinkage (capped prior strength M = 90.0)
        p_wkt = (wkts_p + M_WICKET_CAPPED * priors["mu_wkt"]) / (n_press + M_WICKET_CAPPED)
        delta_wkt_s = (p_wkt - priors["mu_wkt"]) * 100.0
        shrunk_delta_wkt.append(round(delta_wkt_s, 4))

        # 4. Beta-Binomial Dot% shrinkage (M = 135.8)
        p_dot = (dots_p + M_DOT * priors["mu_dot"]) / (n_press + M_DOT)
        delta_dot_s = (p_dot - priors["mu_dot"]) * 100.0
        shrunk_delta_dot.append(round(delta_dot_s, 4))

        # 5. Beta-Binomial Boundary Concession% shrinkage (M = 114.7)
        p_bnd = (bnds_p + M_BND_CON * priors["mu_bnd"]) / (n_press + M_BND_CON)
        delta_bnd_s = (priors["mu_bnd"] - p_bnd) * 100.0
        shrunk_delta_bnd_con.append(round(delta_bnd_s, 4))

    df["shrunk_xrs_per_ball"] = shrunk_xrs
    df["shrunk_delta_econ"] = shrunk_delta_econ
    df["shrunk_delta_wkt"] = shrunk_delta_wkt
    df["shrunk_delta_dot"] = shrunk_delta_dot
    df["shrunk_delta_bnd_con"] = shrunk_delta_bnd_con

    return df


# ---------------------------------------------------------------------------
# 5. Role Cohort Standardization & Composite PPBI Engine
# ---------------------------------------------------------------------------

def compute_ppbi_scores(shrunk_df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes shrunk components within role cohorts and computes composite PPBI.
    
    ROLE STANDARDIZATION SAFEGUARDS (From M3 Task 4):
    1. Bayesian Regularized Variance:
       sigma_reg = sqrt(sigma_cohort^2 + (alpha_reg * sigma_league)^2)
       where alpha_reg = 0.10.
    2. Hierarchical Partial Pooling:
       If N_cohort < 30, cohort mean is shrunk toward global league mean.
    3. Composite Weights (M3 Section 6.3.2 Starting Weights - PROVISIONAL):
       PPBI = 0.35*Z(xRS) + 0.20*Z(DeltaEcon) + 0.25*Z(DeltaWkt) + 0.10*Z(DeltaDot) + 0.10*Z(DeltaBndCon)
    """
    df = shrunk_df.copy()

    components = [
        ("shrunk_xrs_per_ball", "z_xrs", "sigma_xrs"),
        ("shrunk_delta_econ", "z_delta_econ", "sigma_econ"),
        ("shrunk_delta_wkt", "z_delta_wkt", "mu_wkt"),
        ("shrunk_delta_dot", "z_delta_dot", "mu_dot"),
        ("shrunk_delta_bnd_con", "z_delta_bnd_con", "mu_bnd"),
    ]

    # Pre-compute empirical cohort and league sample standard deviations
    league_sds: Dict[str, float] = {}
    for col, _, prior_sd_key in components:
        sample_sd = df[col].std(ddof=1) if len(df) > 1 else 0.0
        default_sd = ROLE_PRIORS["League"].get(prior_sd_key, 1.0)
        if prior_sd_key in ["mu_wkt", "mu_dot", "mu_bnd"]:
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

    # Composite PPBI equation (Eq. 8 in M3)
    df["ppbi_score"] = (
        WEIGHT_XRS * df["z_xrs"] +
        WEIGHT_DELTA_ECON * df["z_delta_econ"] +
        WEIGHT_DELTA_WKT * df["z_delta_wkt"] +
        WEIGHT_DELTA_DOT * df["z_delta_dot"] +
        WEIGHT_DELTA_BND_CON * df["z_delta_bnd_con"]
    )

    return df


# ---------------------------------------------------------------------------
# 6. Qualification & Eligibility Gate Engine
# ---------------------------------------------------------------------------

def evaluate_bowler_eligibility(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Evaluates bowler qualification against the approved M3 dual-tier criteria:
    1. Career Innings: >= 12
    2. Total Legal Balls: >= 144 (24 overs)
    3. High-Pressure Legal Balls: >= 42 (DLI >= 1.35)
    
    EXPLICIT GOVERNANCE BEHAVIOR:
    - In an 8-match pilot, qualified counts will be zero or near-zero.
    - Explicit exclusion reasons are documented for every unqualified player:
        * 'INSUFFICIENT_INNINGS'
        * 'INSUFFICIENT_LEGAL_BALLS'
        * 'INSUFFICIENT_PRESSURE_BALLS'
    - Thresholds are strictly preserved without silent relaxation.
    """
    df = metrics_df.copy()

    is_eligible_list: List[bool] = []
    reasons_list: List[str] = []

    for _, row in df.iterrows():
        inns = row["innings_count"]
        balls = row["total_legal_balls"]
        press_balls = row["pressure_legal_balls"]

        reasons = []
        if inns < MIN_QUALIFYING_INNINGS:
            reasons.append(f"INSUFFICIENT_INNINGS ({inns}/{MIN_QUALIFYING_INNINGS})")
        if balls < MIN_QUALIFYING_LEGAL_BALLS:
            reasons.append(f"INSUFFICIENT_LEGAL_BALLS ({balls}/{MIN_QUALIFYING_LEGAL_BALLS})")
        if press_balls < MIN_QUALIFYING_PRESSURE_BALLS:
            reasons.append(f"INSUFFICIENT_PRESSURE_BALLS ({press_balls}/{MIN_QUALIFYING_PRESSURE_BALLS})")

        eligible = (len(reasons) == 0)
        is_eligible_list.append(eligible)
        reasons_list.append("; ".join(reasons) if not eligible else "QUALIFIED")

    df["is_eligible"] = is_eligible_list
    df["exclusion_reason"] = reasons_list

    return df


# ---------------------------------------------------------------------------
# 7. Clustered Bootstrap Resampling & Uncertainty Engine (Scheme B)
# ---------------------------------------------------------------------------

def bootstrap_bowler_uncertainty(
    deliveries_df: pd.DataFrame,
    target_bowler_id: int,
    n_draws: int = 1000,
    seed: int = 42,
    cluster_unit: str = "player_innings"
) -> Dict[str, Any]:
    """
    Performs clustered bootstrap resampling for a single bowler.
    
    RESAMPLING SPECIFICATION (Scheme B vs Scheme C):
    - Scheme B (Default, Approved Standard): Unit is (bowler_id, match_id, innings).
      Preserves intra-innings correlation.
    - Scheme C (Alternative): Unit is (bowler_id, match_id).
    
    ESTIMATOR CONSISTENCY:
    - Every bootstrap draw evaluates the EXACT cohort-standardized PPBI estimator
      using the identical cohort mean and regularized variance parameters.
    """
    rng = np.random.RandomState(seed)

    # Filter deliveries bowled by target bowler (legal deliveries only)
    b_df = deliveries_df[
        (deliveries_df["bowler_id"] == target_bowler_id) &
        (deliveries_df["ext_is_legal_delivery"] == True) &
        (deliveries_df["is_dli_valid"] == True)
    ].copy()

    if len(b_df) == 0:
        return {
            "bowler_id": target_bowler_id,
            "ppbi_point_estimate": np.nan,
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

    # Partition into clusters
    if cluster_unit == "player_match":
        cluster_keys = ["match_id"]
    else:  # Scheme B
        cluster_keys = ["match_id", "innings"]

    clusters = [group for _, group in b_df.groupby(cluster_keys)]
    k = len(clusters)

    if k == 0:
        return {"bowler_id": target_bowler_id, "ppbi_point_estimate": np.nan, "se_boot": np.nan}

    # Baseline point estimate computation
    baseline_agg = aggregate_bowler_performance(deliveries_df)
    baseline_shrunk = apply_empirical_bayes_shrinkage(baseline_agg)
    baseline_ppbi = compute_ppbi_scores(baseline_shrunk)

    p_row = baseline_ppbi[baseline_ppbi["bowler_id"] == target_bowler_id]
    point_est = float(p_row["ppbi_score"].iloc[0]) if len(p_row) > 0 else 0.0
    bowler_name = str(p_row["bowler_name"].iloc[0]) if len(p_row) > 0 else "Unknown"
    role = str(p_row["primary_role"].iloc[0]) if len(p_row) > 0 else "Middle Enforcer"
    priors = ROLE_PRIORS.get(role, ROLE_PRIORS["Middle Enforcer"])

    # Extract cohort moments for standardization
    cohort_params: Dict[str, Tuple[float, float]] = {}
    components_info = [
        ("shrunk_xrs_per_ball", WEIGHT_XRS),
        ("shrunk_delta_econ", WEIGHT_DELTA_ECON),
        ("shrunk_delta_wkt", WEIGHT_DELTA_WKT),
        ("shrunk_delta_dot", WEIGHT_DELTA_DOT),
        ("shrunk_delta_bnd_con", WEIGHT_DELTA_BND_CON),
    ]

    for col, _ in components_info:
        cohort_rows = baseline_ppbi[baseline_ppbi["primary_role"] == role][col]
        n_c = len(cohort_rows)
        sample_sd = baseline_ppbi[col].std(ddof=1) if len(baseline_ppbi) > 1 else 1.0
        c_mean = cohort_rows.mean() if n_c > 1 else 0.0
        c_sd = cohort_rows.std(ddof=1) if n_c > 1 else sample_sd

        if n_c < MIN_COHORT_SIZE:
            pool_weight = n_c / (n_c + HIERARCHICAL_POOLING_STRENGTH)
            c_mean = pool_weight * c_mean + (1.0 - pool_weight) * 0.0

        sigma_reg = math.sqrt((c_sd ** 2) + ((VARIANCE_REGULARIZATION_ALPHA * sample_sd) ** 2))
        if sigma_reg < 1e-4:
            sigma_reg = 1.0
        cohort_params[col] = (c_mean, sigma_reg)

    # Execute bootstrap draws
    boot_scores: List[float] = []
    valid_draws = 0

    for _ in range(n_draws):
        selected_indices = rng.choice(k, size=k, replace=True)
        sample_deliveries = pd.concat([clusters[i] for i in selected_indices], ignore_index=True)

        press_sample = sample_deliveries[sample_deliveries["pre_dli"] >= PRESSURE_DLI_THRESHOLD]
        base_sample = sample_deliveries[sample_deliveries["pre_dli"] < PRESSURE_DLI_THRESHOLD]

        n_p = len(press_sample)
        n_b = len(base_sample)

        runs_p = int(press_sample["ext_bowler_debit_runs"].sum())
        runs_b = int(base_sample["ext_bowler_debit_runs"].sum())
        wkts_p = int(press_sample["is_bowler_wicket_final"].sum())
        dots_p = int(press_sample["is_bowler_dot"].sum())
        bnds_p = int(press_sample["is_boundary_conceded"].sum())
        xrs_sum = float(press_sample["xrs"].sum())

        xrs_raw = (xrs_sum / n_p) if n_p > 0 else 0.0
        econ_p = (runs_p / (n_p / 6.0)) if n_p > 0 else priors["mu_econ"]
        econ_b = (runs_b / (n_b / 6.0)) if n_b > 0 else priors["mu_econ"]

        # Shrunk components
        lambda_xrs = n_p / (n_p + K_XRS) if (n_p + K_XRS) > 0 else 0.0
        xrs_s = lambda_xrs * xrs_raw + (1.0 - lambda_xrs) * priors["mu_xrs"]

        lambda_econ_p = n_p / (n_p + K_ECON) if (n_p + K_ECON) > 0 else 0.0
        lambda_econ_b = n_b / (n_b + K_ECON) if (n_b + K_ECON) > 0 else 0.0
        econ_p_s = lambda_econ_p * econ_p + (1.0 - lambda_econ_p) * priors["mu_econ"]
        econ_b_s = lambda_econ_b * econ_b + (1.0 - lambda_econ_b) * priors["mu_econ"]
        delta_econ_s = econ_b_s - econ_p_s

        p_wkt = (wkts_p + M_WICKET_CAPPED * priors["mu_wkt"]) / (n_p + M_WICKET_CAPPED)
        delta_wkt_s = (p_wkt - priors["mu_wkt"]) * 100.0

        p_dot = (dots_p + M_DOT * priors["mu_dot"]) / (n_p + M_DOT)
        delta_dot_s = (p_dot - priors["mu_dot"]) * 100.0

        p_bnd = (bnds_p + M_BND_CON * priors["mu_bnd"]) / (n_p + M_BND_CON)
        delta_bnd_s = (priors["mu_bnd"] - p_bnd) * 100.0

        # Exact cohort standardization
        z_xrs = (xrs_s - cohort_params["shrunk_xrs_per_ball"][0]) / cohort_params["shrunk_xrs_per_ball"][1]
        z_decon = (delta_econ_s - cohort_params["shrunk_delta_econ"][0]) / cohort_params["shrunk_delta_econ"][1]
        z_dwkt = (delta_wkt_s - cohort_params["shrunk_delta_wkt"][0]) / cohort_params["shrunk_delta_wkt"][1]
        z_ddot = (delta_dot_s - cohort_params["shrunk_delta_dot"][0]) / cohort_params["shrunk_delta_dot"][1]
        z_dbnd = (delta_bnd_s - cohort_params["shrunk_delta_bnd_con"][0]) / cohort_params["shrunk_delta_bnd_con"][1]

        draw_score = (
            WEIGHT_XRS * z_xrs +
            WEIGHT_DELTA_ECON * z_decon +
            WEIGHT_DELTA_WKT * z_dwkt +
            WEIGHT_DELTA_DOT * z_ddot +
            WEIGHT_DELTA_BND_CON * z_dbnd
        )
        boot_scores.append(draw_score)
        valid_draws += 1

    boot_arr = np.array(boot_scores)
    se_boot = float(np.std(boot_arr, ddof=1)) if len(boot_arr) > 1 else 0.0
    boot_mean = float(np.mean(boot_arr))
    boot_median = float(np.median(boot_arr))
    boot_skewness = float(stats.skew(boot_arr)) if len(boot_arr) > 2 else 0.0

    # 1. Normal approximation 90% CI: [point_est +/- 1.645 * se_boot]
    ci_normal_90 = (round(point_est - 1.645 * se_boot, 4), round(point_est + 1.645 * se_boot, 4))

    # 2. Percentile bootstrap 90% CI: [p5, p95]
    p5 = float(np.percentile(boot_arr, 5))
    p25 = float(np.percentile(boot_arr, 25))
    p50 = float(np.percentile(boot_arr, 50))
    p75 = float(np.percentile(boot_arr, 75))
    p95 = float(np.percentile(boot_arr, 95))
    ci_percentile_90 = (round(p5, 4), round(p95, 4))

    # 3. Bayesian 90% Credible Interval (conjugate normal posterior)
    prior_tau = priors.get("sigma_xrs", 0.25)
    n_total_press = len(b_df[b_df["pre_dli"] >= PRESSURE_DLI_THRESHOLD])
    sigma_posterior = math.sqrt(1.0 / ((1.0 / (prior_tau ** 2)) + (n_total_press / (prior_tau ** 2)))) if n_total_press > 0 else prior_tau
    credible_interval_90 = (round(point_est - 1.645 * sigma_posterior, 4), round(point_est + 1.645 * sigma_posterior, 4))

    return {
        "bowler_id": target_bowler_id,
        "bowler_name": bowler_name,
        "ppbi_point_estimate": round(point_est, 4),
        "se_boot": round(se_boot, 4),
        "boot_mean": round(boot_mean, 4),
        "boot_median": round(boot_median, 4),
        "boot_sd": round(se_boot, 4),
        "percentiles": {
            "p5": round(p5, 4),
            "p25": round(p25, 4),
            "p50": round(p50, 4),
            "p75": round(p75, 4),
            "p95": round(p95, 4)
        },
        "skewness": round(boot_skewness, 4),
        "ci_normal_90": ci_normal_90,
        "ci_percentile_90": ci_percentile_90,
        "credible_interval_90": credible_interval_90,
        "n_draws": n_draws,
        "n_valid_draws": valid_draws,
        "n_invalid_draws": n_draws - valid_draws,
        "cluster_unit": cluster_unit,
        "clusters_count": k,
        "draws": boot_scores
    }


# ---------------------------------------------------------------------------
# 8. Multicollinearity & Diagnostic Engine
# ---------------------------------------------------------------------------

def compute_ppbi_diagnostics(ppbi_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes diagnostic checks for component correlation and multicollinearity (VIF).
    
    GOVERNANCE MANDATE:
    - Reports VIF and correlation findings strictly as diagnostics.
    - Does NOT automatically remove or reweight components.
    """
    comp_cols = [
        "shrunk_xrs_per_ball",
        "shrunk_delta_econ",
        "shrunk_delta_wkt",
        "shrunk_delta_dot",
        "shrunk_delta_bnd_con"
    ]

    sub_df = ppbi_df[comp_cols].dropna()
    if len(sub_df) < 5:
        return {"status": "INSUFFICIENT_SAMPLE_FOR_VIF", "n_rows": len(sub_df)}

    corr_matrix = sub_df.corr(method="pearson").to_dict()

    vifs: Dict[str, float] = {}
    for col in comp_cols:
        y = sub_df[col].values
        x_cols = [c for c in comp_cols if c != col]
        X = sub_df[x_cols].values
        X = np.column_stack([np.ones(len(X)), X])
        try:
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
    convention (stagnation = 0 when legal balls < 6 in Innings 1) on bowling metrics.
    """
    df = deliveries_df[deliveries_df["ext_is_legal_delivery"] == True].copy()
    early_balls = df[(df["innings"] == 1) & (df["pre_legal_balls_bowled"] < 6)]

    total_early = len(early_balls)
    bowler_ids = early_balls["bowler_id"].unique().tolist()
    tiers = early_balls["pre_pressure_tier"].value_counts().to_dict() if total_early > 0 else {}
    high_press_count = int((early_balls["pre_dli"] >= PRESSURE_DLI_THRESHOLD).sum())

    return {
        "status": "EARLY_DLI_TRACED",
        "total_early_setting_deliveries": total_early,
        "distinct_bowlers_affected": len(bowler_ids),
        "affected_bowler_ids": bowler_ids,
        "pressure_tier_distribution": tiers,
        "high_pressure_contamination_count": high_press_count,
        "is_cleanly_isolated": (high_press_count == 0)
    }


# ---------------------------------------------------------------------------
# 10. Pipeline Orchestrator
# ---------------------------------------------------------------------------

def run_bowler_performance_pipeline(
    enriched_deliveries_df: pd.DataFrame,
    run_bootstrap: bool = False,
    n_bootstrap_draws: int = 1000,
    bootstrap_target_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Runs the complete M4.4 Bowler Performance Pipeline deterministically.
    
    Pipeline Steps:
    1. Assign bowler tactical roles (Powerplay Specialist, Death Specialist, Middle Enforcer).
    2. Compute delivery-level xRS, boundary concession, and bowler wickets.
    3. Aggregate performance features into pressure and baseline splits.
    4. Apply Empirical Bayes shrinkage across all 5 dimensions.
    5. Compute composite PPBI scores with role standardization safeguards.
    6. Evaluate qualification gates with explicit exclusion reasons.
    7. Generate multicollinearity and correlation diagnostics.
    8. Trace early-innings DLI sensitivity.
    9. Optional clustered bootstrap resampling for designated players.
    
    STRICT GOVERNANCE ENFORCEMENT:
    - Does NOT sort by composite score or produce Top-10 rankings.
    - Preserves all provisional components and original files.
    """
    # 1. Role assignment
    roles = assign_bowler_roles(enriched_deliveries_df)

    # 2. Delivery xRS
    xrs_df = compute_delivery_xrs(enriched_deliveries_df, roles)

    # 3. Aggregate performance
    agg_df = aggregate_bowler_performance(xrs_df)

    # 4. Empirical Bayes shrinkage
    shrunk_df = apply_empirical_bayes_shrinkage(agg_df)

    # 5. Composite PPBI scores
    ppbi_df = compute_ppbi_scores(shrunk_df)

    # 6. Eligibility evaluation
    final_df = evaluate_bowler_eligibility(ppbi_df)

    # 7. Diagnostics
    diagnostics = compute_ppbi_diagnostics(final_df)

    # 8. Early DLI trace
    early_dli_trace = trace_early_innings_dli_impact(xrs_df)

    # 9. Clustered bootstrap (if requested)
    bootstrap_results = {}
    if run_bootstrap:
        target_ids = bootstrap_target_ids or final_df["bowler_id"].unique()[:5].tolist()
        for bid in target_ids:
            bootstrap_results[bid] = bootstrap_bowler_uncertainty(
                deliveries_df=xrs_df,
                target_bowler_id=bid,
                n_draws=n_bootstrap_draws
            )

    return {
        "bowler_performance_df": final_df,
        "diagnostics": diagnostics,
        "early_dli_trace": early_dli_trace,
        "bootstrap_results": bootstrap_results,
        "role_profiles": roles,
        "enriched_deliveries_with_xrs": xrs_df
    }

