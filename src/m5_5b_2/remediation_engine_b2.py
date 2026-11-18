"""
RR ScoutIQ — Milestone M5.5-B.2: Statistical Architecture Correction
Module: src/m5_5b_2/remediation_engine_b2.py

Core corrections implemented:
1. Strict numerator/denominator separation for bowler economy:
   - Numerator = all applicable ext_bowler_debit_runs (including wides and no-balls).
   - Denominator = legal balls only (ext_is_legal_delivery == 1).
2. Explicit zero-exposure and NaN handling:
   - Preserves observed personal baseline as np.nan when exposure == 0.
   - Distinct from prior-based estimate (role prior mean, or hierarchical cell prior).
   - Returns explicit reliability info (exposure=0, is_zero_exposure=True, uncertainty inflated).
3. Hierarchical Empirical Bayes prior fitting & partial pooling:
   - Priors are fitted on Phase x Pressure Tier contextual populations, with fallback to Phase-level or Role-level.
   - Kleinman (1973) corrected MOM fallback for Beta-Binomial models.
   - Strictly trained on training folds (0 leakage).
4. Dual-phase bowler classification:
   - Workload dominance: pp_pct >= 0.40 and death_pct >= 0.30 -> tiebreak pp_pct >= death_pct -> Powerplay Specialist, else Death Specialist.
"""

import os
import sys
import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import scipy.special as sp


# ---------------------------------------------------------------------------
# 1. Bowler Conceded-Runs Accounting & Economy Rate Calculation
# ---------------------------------------------------------------------------

def calculate_bowler_economy(
    df_deliveries: pd.DataFrame
) -> Dict[str, Union[float, int]]:
    """
    Computes bowler economy rate strictly separating:
    - Numerator: ext_bowler_debit_runs across ALL deliveries (legal + wides + no-balls).
      Byes, leg-byes, and penalty runs are excluded from ext_bowler_debit_runs by Law.
    - Denominator: legal balls faced only (ext_is_legal_delivery == 1).
    
    Returns:
      dict with:
        total_deliveries: int
        legal_balls: int
        bowler_debit_runs: int
        wides_count: int
        noballs_count: int
        wide_runs_debited: int
        noball_runs_debited: int
        economy_rate: float (or np.nan if legal_balls == 0)
    """
    if len(df_deliveries) == 0:
        return {
            "total_deliveries": 0,
            "legal_balls": 0,
            "bowler_debit_runs": 0,
            "wides_count": 0,
            "noballs_count": 0,
            "wide_runs_debited": 0,
            "noball_runs_debited": 0,
            "economy_rate": np.nan
        }
    
    total_deliv = len(df_deliveries)
    legal_mask = df_deliveries["ext_is_legal_delivery"] == 1
    legal_balls = int(legal_mask.sum())
    
    # Numerator: ALL debited runs across all deliveries
    total_debit_runs = int(df_deliveries["ext_bowler_debit_runs"].sum())
    
    # Wides and No-balls analysis
    is_wide = df_deliveries["ext_is_wide"] == 1
    is_noball = df_deliveries["ext_is_noball"] == 1
    
    wides_count = int(is_wide.sum())
    noballs_count = int(is_noball.sum())
    
    wide_runs_debited = int(df_deliveries.loc[is_wide, "ext_bowler_debit_runs"].sum())
    noball_runs_debited = int(df_deliveries.loc[is_noball, "ext_bowler_debit_runs"].sum())
    
    econ = (total_debit_runs / legal_balls * 6.0) if legal_balls > 0 else np.nan
    
    return {
        "total_deliveries": total_deliv,
        "legal_balls": legal_balls,
        "bowler_debit_runs": total_debit_runs,
        "wides_count": wides_count,
        "noballs_count": noballs_count,
        "wide_runs_debited": wide_runs_debited,
        "noball_runs_debited": noball_runs_debited,
        "economy_rate": econ
    }


# ---------------------------------------------------------------------------
# 2. Explicit Zero-Exposure & Missingness Handling
# ---------------------------------------------------------------------------

class PersonalBaselineEstimate:
    """
    Encapsulates an individual's baseline estimate, distinguishing:
    - observed_personal_rate: np.nan if exposure == 0 (strictly undefined).
    - prior_expectation: the population prior mean (or hierarchical context mean).
    - shrunk_rate: empirical Bayes posterior mean.
    - posterior_variance: uncertainty associated with the estimate.
    - exposure: number of observed trials/balls.
    - is_zero_exposure: boolean flag.
    - reliability_status: category ('UNOBSERVED', 'VERY_LOW', 'MODERATE', 'ROBUST').
    """
    def __init__(
        self,
        exposure: int,
        observed_events: Optional[float],
        prior_mean: float,
        prior_m0: float,
        prior_var: Optional[float] = None
    ):
        self.exposure = int(exposure)
        self.prior_mean = float(prior_mean)
        self.prior_m0 = float(prior_m0)
        self.prior_var = float(prior_var) if prior_var is not None else (prior_mean * (1 - prior_mean) / (prior_m0 + 1) if prior_mean <= 1.0 else 0.25)
        
        if self.exposure <= 0 or observed_events is None or np.isnan(observed_events):
            self.is_zero_exposure = True
            self.observed_personal_rate = np.nan
            self.shrinkage_weight = 0.0
            self.shrunk_rate = self.prior_mean
            self.posterior_variance = self.prior_var
            self.reliability_status = "UNOBSERVED"
        else:
            self.is_zero_exposure = False
            self.observed_personal_rate = float(observed_events) / float(self.exposure)
            self.shrinkage_weight = float(self.exposure) / (float(self.exposure) + float(self.prior_m0))
            self.shrunk_rate = (
                self.shrinkage_weight * self.observed_personal_rate +
                (1.0 - self.shrinkage_weight) * self.prior_mean
            )
            # Posterior variance decreases with exposure
            self.posterior_variance = self.prior_var * (self.prior_m0 / (self.exposure + self.prior_m0))
            
            if self.exposure < 30:
                self.reliability_status = "VERY_LOW"
            elif self.exposure < 100:
                self.reliability_status = "MODERATE"
            else:
                self.reliability_status = "ROBUST"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exposure": self.exposure,
            "is_zero_exposure": self.is_zero_exposure,
            "observed_personal_rate": self.observed_personal_rate,
            "prior_mean": self.prior_mean,
            "prior_m0": self.prior_m0,
            "shrinkage_weight": self.shrinkage_weight,
            "shrunk_rate": self.shrunk_rate,
            "posterior_variance": self.posterior_variance,
            "reliability_status": self.reliability_status
        }


# ---------------------------------------------------------------------------
# 3. Role Derivation strictly within Training Sets
# ---------------------------------------------------------------------------

def derive_training_batter_roles_b2(train_df: pd.DataFrame) -> pd.Series:
    """
    Derives batter roles strictly from training fold regulation deliveries (innings <= 2).
    M3 Standard Definitions:
      - TopOrderBatter: modal entry position 1-3
      - MiddleOrderAnchor: modal entry position 4-6
      - Finisher: modal entry position 7+
    Fallback for 0 training balls: TopOrderBatter
    """
    reg = train_df[(train_df["innings"] <= 2) & (train_df["ext_is_legal_delivery"] == 1)]
    
    # In canonical dataset, the batter ID is striker_id and position is batting_order
    id_col = "striker_id" if "striker_id" in reg.columns else "batter_id"
    pos_col = "batting_order" if "batting_order" in reg.columns else ("ext_batting_position" if "ext_batting_position" in reg.columns else "overid")
    
    batter_pos = reg.groupby([id_col, pos_col]).size().reset_index(name="count")
    idx_max = batter_pos.groupby(id_col)["count"].idxmax()
    modal_pos = batter_pos.loc[idx_max].set_index(id_col)[pos_col]
    
    def assign_role(p):
        if pos_col == "overid":
            if p <= 6:
                return "TopOrderBatter"
            elif p <= 15:
                return "MiddleOrderAnchor"
            else:
                return "Finisher"
        else:
            if p <= 3:
                return "TopOrderBatter"
            elif p <= 6:
                return "MiddleOrderAnchor"
            else:
                return "Finisher"
                
    return modal_pos.apply(assign_role)


def derive_training_bowler_roles_b2(train_df: pd.DataFrame) -> Tuple[Dict[int, str], pd.DataFrame]:
    """
    Derives bowler roles strictly from training fold regulation legal deliveries (innings <= 2).
    M3 / B.2 Reconciled Rule:
      - Powerplay Specialist: pp_pct >= 0.40
      - Death Specialist: death_pct >= 0.30
      - Dual-phase tiebreak: pp_pct >= death_pct -> Powerplay Specialist, else Death Specialist
      - Remainder: Middle Enforcer
    """
    reg = train_df[(train_df["innings"] <= 2) & (train_df["ext_is_legal_delivery"] == 1)]
    bowler_stats = reg.groupby("bowler_id").agg(
        total_legal=("ext_is_legal_delivery", "sum"),
        pp_balls=("overid", lambda s: (s <= 6).sum()),
        mid_balls=("overid", lambda s: ((s >= 7) & (s <= 15)).sum()),
        death_balls=("overid", lambda s: (s >= 16).sum())
    ).reset_index()
    
    role_map = {}
    records = []
    
    for _, row in bowler_stats.iterrows():
        bid = int(row["bowler_id"])
        total = int(row["total_legal"])
        if total == 0:
            role = "Middle Enforcer"
            pp_pct, death_pct, mid_pct = 0.0, 0.0, 0.0
            is_dual = False
        else:
            pp_pct = row["pp_balls"] / total
            death_pct = row["death_balls"] / total
            mid_pct = row["mid_balls"] / total
            is_pp = pp_pct >= 0.40
            is_death = death_pct >= 0.30
            is_dual = is_pp and is_death
            
            if is_dual:
                # Documented workload dominance tiebreak
                role = "Powerplay Specialist" if pp_pct >= death_pct else "Death Specialist"
            elif is_pp:
                role = "Powerplay Specialist"
            elif is_death:
                role = "Death Specialist"
            else:
                role = "Middle Enforcer"
                
        role_map[bid] = role
        records.append({
            "bowler_id": bid,
            "total_legal": total,
            "pp_balls": row["pp_balls"],
            "mid_balls": row["mid_balls"],
            "death_balls": row["death_balls"],
            "pp_pct": pp_pct,
            "mid_pct": mid_pct,
            "death_pct": death_pct,
            "is_dual_phase": is_dual,
            "assigned_role": role
        })
        
    df_details = pd.DataFrame(records)
    return role_map, df_details


# ---------------------------------------------------------------------------
# 4. Safeguarded Empirical Bayes Prior Fitting
# ---------------------------------------------------------------------------

def kleinman_corrected_mom(k: np.ndarray, n: np.ndarray) -> Tuple[float, float, float]:
    """
    Kleinman (1973) corrected Method of Moments for Beta-Binomial models.
    Guarantees non-negative variance and strictly positive (alpha, beta, M0).
    """
    valid = n > 0
    k, n = k[valid].astype(float), n[valid].astype(float)
    if len(k) < 2:
        return 1.0, 9.0, 10.0
    
    p_hat = k / n
    w = n / n.sum()
    p_bar = np.sum(w * p_hat)
    
    if p_bar <= 1e-6 or p_bar >= 1.0 - 1e-6:
        p_bar = np.clip(p_bar, 0.01, 0.99)
        return p_bar * 10.0, (1.0 - p_bar) * 10.0, 10.0
    
    # Unweighted total variance
    s2 = np.sum(w * (p_hat - p_bar) ** 2)
    binomial_var = p_bar * (1.0 - p_bar) * np.sum(w * (1.0 - w) / n)
    
    denom = np.sum(w * (1.0 - w) * (1.0 - 1.0 / n))
    if denom <= 0:
        tau2 = 0.0
    else:
        tau2 = max(0.0, (s2 - binomial_var) / denom)
    
    var_total = p_bar * (1.0 - p_bar)
    if tau2 <= 1e-8:
        # Homogeneous population / low overdispersion -> moderate default shrinkage
        M0 = 100.0
    else:
        # intraclass correlation rho = tau2 / (p_bar * (1 - p_bar))
        rho = min(0.99, max(0.001, tau2 / var_total))
        M0 = (1.0 - rho) / rho
        M0 = min(2000.0, max(5.0, M0))
        
    alpha0 = max(0.1, p_bar * M0)
    beta0 = max(0.1, (1.0 - p_bar) * M0)
    return alpha0, beta0, M0


def fit_beta_binomial_mle_safeguarded(
    k: np.ndarray,
    n: np.ndarray
) -> Dict[str, Any]:
    """
    Fits Beta-Binomial prior using Marginal Maximum Likelihood (MML),
    with automatic Kleinman MOM fallback on boundary warnings or convergence failure.
    """
    valid = n > 0
    k_v, n_v = k[valid].astype(float), n[valid].astype(float)
    if len(k_v) < 5 or n_v.sum() < 50:
        # Insufficient sample -> Kleinman MOM fallback directly
        a_mom, b_mom, m0_mom = kleinman_corrected_mom(k, n)
        return {
            "alpha": a_mom, "beta": b_mom, "M0": m0_mom,
            "mean": a_mom / (a_mom + b_mom),
            "method": "KLEINMAN_MOM_FALLBACK",
            "converged": True, "sample_size": len(k_v), "total_trials": int(n_v.sum())
        }
    
    # Initial estimate from Kleinman MOM
    a_init, b_init, m_init = kleinman_corrected_mom(k_v, n_v)
    
    def neg_log_lik(params):
        log_a, log_b = params
        a = np.exp(log_a)
        b = np.exp(log_b)
        # Log likelihood of Beta-Binomial
        ll = (
            sp.gammaln(n_v + 1) - sp.gammaln(k_v + 1) - sp.gammaln(n_v - k_v + 1)
            + sp.betaln(k_v + a, n_v - k_v + b) - sp.betaln(a, b)
        )
        return -np.sum(ll)
    
    try:
        res = minimize(
            neg_log_lik,
            x0=[np.log(a_init), np.log(b_init)],
            method="L-BFGS-B",
            bounds=[(np.log(0.05), np.log(5000.0)), (np.log(0.05), np.log(5000.0))]
        )
        if res.success and np.isfinite(res.fun):
            a_fit = np.exp(res.x[0])
            b_fit = np.exp(res.x[1])
            m0_fit = a_fit + b_fit
            # Check boundary conditions
            if m0_fit >= 4900.0 or m0_fit <= 0.15:
                # Boundary hit -> engage Kleinman fallback
                return {
                    "alpha": a_init, "beta": b_init, "M0": m_init,
                    "mean": a_init / (a_init + b_init),
                    "method": "KLEINMAN_MOM_BOUNDARY_FALLBACK",
                    "converged": True, "sample_size": len(k_v), "total_trials": int(n_v.sum())
                }
            return {
                "alpha": a_fit, "beta": b_fit, "M0": m0_fit,
                "mean": a_fit / (a_fit + b_fit),
                "method": "L-BFGS-B_MML",
                "converged": True, "sample_size": len(k_v), "total_trials": int(n_v.sum())
            }
        else:
            return {
                "alpha": a_init, "beta": b_init, "M0": m_init,
                "mean": a_init / (a_init + b_init),
                "method": "KLEINMAN_MOM_NONCONVERGED_FALLBACK",
                "converged": True, "sample_size": len(k_v), "total_trials": int(n_v.sum())
            }
    except Exception:
        return {
            "alpha": a_init, "beta": b_init, "M0": m_init,
            "mean": a_init / (a_init + b_init),
            "method": "KLEINMAN_MOM_EXCEPTION_FALLBACK",
            "converged": True, "sample_size": len(k_v), "total_trials": int(n_v.sum())
        }


def fit_normal_normal_safeguarded(
    y: np.ndarray,
    n: np.ndarray
) -> Dict[str, Any]:
    """
    Fits Normal-Normal prior for continuous rate outcomes (runs per ball or economy).
    y: observed rates (e.g. runs per ball per player)
    n: sample sizes per player
    """
    valid = n > 0
    y_v, n_v = y[valid].astype(float), n[valid].astype(float)
    if len(y_v) < 5:
        return {
            "mu0": 1.35, "sigma2_0": 0.10, "sigma2_e": 1.0, "M0": 50.0,
            "method": "DEFAULT_HEURISTIC", "sample_size": len(y_v)
        }
    
    # Weighted grand mean
    w = n_v / n_v.sum()
    mu0 = np.sum(w * y_v)
    
    # Pooled within-player variance estimate (empirical variance of single delivery runs ~ 1.5 - 2.5)
    sigma2_e = 1.96  # empirical variance of T20 delivery runs
    
    # Between-player variance
    s2_between = np.sum(w * (y_v - mu0) ** 2)
    expected_sample_noise = np.sum(w * (1.0 - w) * (sigma2_e / n_v))
    
    tau2 = max(0.005, s2_between - expected_sample_noise)
    M0 = sigma2_e / tau2
    M0 = min(1000.0, max(10.0, M0))
    
    return {
        "mu0": float(mu0),
        "sigma2_0": float(tau2),
        "sigma2_e": float(sigma2_e),
        "M0": float(M0),
        "method": "WEIGHTED_MOM_NORMAL",
        "sample_size": len(y_v)
    }


# ---------------------------------------------------------------------------
# 5. Hierarchical Contextual Prior & Partial Pooling Architecture
# ---------------------------------------------------------------------------

class HierarchicalContextualPriorEngine:
    """
    Fits and manages hierarchical Empirical Bayes priors strictly within a training fold.
    Hierarchy:
      Level 1 (Cell): Context Cell = Phase x Pressure Tier (e.g., Death x Tier 4)
      Level 2 (Parent): Phase (e.g., Death)
      Level 3 (Grandparent): Global League
      
    Partial Pooling Criterion:
      - If Cell deliveries >= min_cell_deliveries (default: 500) and player count >= 10:
        Use Cell-specific MML prior.
      - Else if Cell deliveries < min_cell_deliveries:
        Partially pool Cell estimate towards Phase-level prior:
        theta_cell_shrunk = w * theta_cell + (1 - w) * theta_phase
      - If Cell empty:
        Fall back directly to Phase-level prior.
    """
    def __init__(self, min_cell_deliveries: int = 500):
        self.min_cell_deliveries = min_cell_deliveries
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.fit_diagnostics: List[Dict[str, Any]] = []

    def fit(self, train_df: pd.DataFrame):
        """
        Fits all continuous and discrete priors across all contextual levels.
        Strictly operates on train_df.
        """
        # Prepare outcomes on train_df
        df = train_df.copy()
        df["phase"] = df["pre_match_phase"].astype(str)
        df["tier"] = df["pre_pressure_tier"].astype(str)
        df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
        df["is_dot"] = (df["ext_bowler_debit_runs"] == 0).astype(int)
        df["is_wkt"] = (df["ext_is_bowler_wicket"] == 1).astype(int)
        df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
        df["is_dismissal"] = (df["ext_is_wicket"] == 1).astype(int)
        
        # 1. League-level Priors
        self._fit_level("League", df, level_type="Grandparent")
        
        # 2. Phase-level Priors
        for phase in df["phase"].unique():
            if phase in ["Super Over", "nan"]:
                continue
            phase_df = df[df["phase"] == phase]
            self._fit_level(f"Phase::{phase}", phase_df, level_type="Parent", parent_key="League")
            
        # 3. Cell-level Priors (Phase x Tier)
        for (phase, tier), cell_df in df.groupby(["phase", "tier"]):
            if phase in ["Super Over", "nan"]:
                continue
            cell_key = f"Cell::{phase}::{tier}"
            parent_key = f"Phase::{phase}"
            self._fit_level(cell_key, cell_df, level_type="Cell", parent_key=parent_key)

    def _fit_level(
        self,
        key: str,
        subset_df: pd.DataFrame,
        level_type: str,
        parent_key: Optional[str] = None
    ):
        deliv_count = len(subset_df)
        legal_df = subset_df[subset_df["is_legal"] == 1]
        legal_count = len(legal_df)
        
        # Bowler player aggregations (using correct economy accounting: numerator=all debits, denom=legal)
        # Note: at cell level, we group by bowler
        b_legal = legal_df.groupby("bowler_id").agg(
            legal_balls=("is_legal", "sum"),
            dots=("is_dot", "sum"),
            wkts=("is_wkt", "sum")
        )
        b_all = subset_df.groupby("bowler_id").agg(
            debit_runs=("ext_bowler_debit_runs", "sum")
        )
        b_agg = b_legal.join(b_all, how="inner").reset_index()
        
        # Batter player aggregations (faced legal balls)
        bat_id_col = "striker_id" if "striker_id" in legal_df.columns else "batter_id"
        bat_agg = legal_df.groupby(bat_id_col).agg(
            balls_faced=("is_legal", "sum"),
            runs_scored=("ext_batter_runs", "sum"),
            boundaries=("is_boundary", "sum"),
            dismissals=("is_dismissal", "sum")
        ).reset_index()
        
        # Fit models or apply partial pooling fallback
        use_partial_pooling = (deliv_count < self.min_cell_deliveries or len(bat_agg) < 10) and (parent_key is not None)
        
        level_priors = {
            "key": key,
            "level_type": level_type,
            "parent_key": parent_key,
            "deliveries": deliv_count,
            "legal_balls": legal_count,
            "unique_batters": len(bat_agg),
            "unique_bowlers": len(b_agg),
            "is_partially_pooled": use_partial_pooling
        }
        
        if use_partial_pooling and parent_key in self.priors:
            parent = self.priors[parent_key]
            # Partially pool cell towards parent
            weight_cell = deliv_count / self.min_cell_deliveries
            
            # Continuous: runs per ball
            c_fit = fit_normal_normal_safeguarded(
                (bat_agg["runs_scored"] / bat_agg["balls_faced"]).values if len(bat_agg) > 0 else np.array([]),
                bat_agg["balls_faced"].values if len(bat_agg) > 0 else np.array([])
            )
            c_mean_pooled = weight_cell * c_fit["mu0"] + (1.0 - weight_cell) * parent["batter_rpb"]["mean"]
            level_priors["batter_rpb"] = {
                "mean": float(c_mean_pooled),
                "M0": float(c_fit["M0"]),
                "method": "PARTIALLY_POOLED_NORMAL"
            }
            
            # Boundary %
            bnd_fit = fit_beta_binomial_mle_safeguarded(
                bat_agg["boundaries"].values if len(bat_agg) > 0 else np.array([]),
                bat_agg["balls_faced"].values if len(bat_agg) > 0 else np.array([])
            )
            bnd_mean_pooled = weight_cell * bnd_fit["mean"] + (1.0 - weight_cell) * parent["batter_boundary"]["mean"]
            level_priors["batter_boundary"] = {
                "mean": float(bnd_mean_pooled),
                "M0": float(bnd_fit["M0"]),
                "alpha": float(bnd_mean_pooled * bnd_fit["M0"]),
                "beta": float((1.0 - bnd_mean_pooled) * bnd_fit["M0"]),
                "method": "PARTIALLY_POOLED_BETABINOM"
            }
            
            # Bowler Wicket %
            wkt_fit = fit_beta_binomial_mle_safeguarded(
                b_agg["wkts"].values if len(b_agg) > 0 else np.array([]),
                b_agg["legal_balls"].values if len(b_agg) > 0 else np.array([])
            )
            wkt_mean_pooled = weight_cell * wkt_fit["mean"] + (1.0 - weight_cell) * parent["bowler_wicket"]["mean"]
            level_priors["bowler_wicket"] = {
                "mean": float(wkt_mean_pooled),
                "M0": float(wkt_fit["M0"]),
                "alpha": float(wkt_mean_pooled * wkt_fit["M0"]),
                "beta": float((1.0 - wkt_mean_pooled) * wkt_fit["M0"]),
                "method": "PARTIALLY_POOLED_BETABINOM"
            }
            
            # Bowler Economy (RPO)
            econ_fit = fit_normal_normal_safeguarded(
                (b_agg["debit_runs"] / b_agg["legal_balls"] * 6.0).values if len(b_agg) > 0 else np.array([]),
                b_agg["legal_balls"].values if len(b_agg) > 0 else np.array([])
            )
            econ_mean_pooled = weight_cell * econ_fit["mu0"] + (1.0 - weight_cell) * parent["bowler_economy"]["mean"]
            level_priors["bowler_economy"] = {
                "mean": float(econ_mean_pooled),
                "M0": float(econ_fit["M0"]),
                "method": "PARTIALLY_POOLED_NORMAL"
            }
        else:
            # Full direct fit
            c_fit = fit_normal_normal_safeguarded(
                (bat_agg["runs_scored"] / bat_agg["balls_faced"]).values if len(bat_agg) > 0 else np.array([]),
                bat_agg["balls_faced"].values if len(bat_agg) > 0 else np.array([])
            )
            level_priors["batter_rpb"] = {
                "mean": float(c_fit["mu0"]), "M0": float(c_fit["M0"]), "method": c_fit["method"]
            }
            
            bnd_fit = fit_beta_binomial_mle_safeguarded(
                bat_agg["boundaries"].values if len(bat_agg) > 0 else np.array([]),
                bat_agg["balls_faced"].values if len(bat_agg) > 0 else np.array([])
            )
            level_priors["batter_boundary"] = {
                "mean": float(bnd_fit["mean"]), "M0": float(bnd_fit["M0"]),
                "alpha": float(bnd_fit["alpha"]), "beta": float(bnd_fit["beta"]),
                "method": bnd_fit["method"]
            }
            
            wkt_fit = fit_beta_binomial_mle_safeguarded(
                b_agg["wkts"].values if len(b_agg) > 0 else np.array([]),
                b_agg["legal_balls"].values if len(b_agg) > 0 else np.array([])
            )
            level_priors["bowler_wicket"] = {
                "mean": float(wkt_fit["mean"]), "M0": float(wkt_fit["M0"]),
                "alpha": float(wkt_fit["alpha"]), "beta": float(wkt_fit["beta"]),
                "method": wkt_fit["method"]
            }
            
            econ_fit = fit_normal_normal_safeguarded(
                (b_agg["debit_runs"] / b_agg["legal_balls"] * 6.0).values if len(b_agg) > 0 else np.array([]),
                b_agg["legal_balls"].values if len(b_agg) > 0 else np.array([])
            )
            level_priors["bowler_economy"] = {
                "mean": float(econ_fit["mu0"]), "M0": float(econ_fit["M0"]), "method": econ_fit["method"]
            }
            
        self.priors[key] = level_priors
        self.fit_diagnostics.append({
            "key": key,
            "level_type": level_type,
            "deliveries": deliv_count,
            "legal_balls": legal_count,
            "bat_rpb_mean": level_priors["batter_rpb"]["mean"],
            "bat_rpb_M0": level_priors["batter_rpb"]["M0"],
            "bnd_mean": level_priors["batter_boundary"]["mean"],
            "bnd_M0": level_priors["batter_boundary"]["M0"],
            "wkt_mean": level_priors["bowler_wicket"]["mean"],
            "wkt_M0": level_priors["bowler_wicket"]["M0"],
            "econ_mean": level_priors["bowler_economy"]["mean"],
            "econ_M0": level_priors["bowler_economy"]["M0"],
            "partially_pooled": level_priors["is_partially_pooled"]
        })

    def get_cell_expectation(self, phase: str, tier: str, metric: str) -> float:
        """
        Retrieves expected prior baseline for a delivery's phase and pressure tier.
        Falls back to Phase -> League if cell unobserved.
        """
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key][metric]["mean"]
        
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key][metric]["mean"]
            
        return self.priors["League"][metric]["mean"]


# ---------------------------------------------------------------------------
# 6. Subgroup Reliability Assessment & Diagnostics
# ---------------------------------------------------------------------------

def compute_subgroup_reliability(
    val_df: pd.DataFrame,
    predictions: np.ndarray,
    actuals: np.ndarray,
    group_cols: List[str],
    is_binary: bool = True
) -> pd.DataFrame:
    """
    Computes rigorous subgroup reliability metrics across combinations of
    Phase, Pressure Tier, Role, or Exposure bins.
    
    Metrics:
      - Sample size (N deliveries, N players)
      - Mean Prediction vs Mean Actual
      - Calibration slope / error
      - Brier Score (if binary) or RMSE (if continuous)
      - Reliability status (SUFFICIENT vs INSUFFICIENT evidence)
    """
    df = val_df[group_cols].copy()
    df["pred"] = predictions
    df["actual"] = actuals
    
    results = []
    for group_vals, grp in df.groupby(group_cols):
        if not isinstance(group_vals, tuple):
            group_vals = (group_vals,)
        n_obs = len(grp)
        y_true = grp["actual"].values
        y_pred = grp["pred"].values
        
        mean_pred = float(np.mean(y_pred))
        mean_actual = float(np.mean(y_true))
        
        if is_binary:
            brier = float(np.mean((y_pred - y_true) ** 2))
            # Log loss with epsilon clipping
            p_clip = np.clip(y_pred, 1e-6, 1.0 - 1e-6)
            log_loss = float(-np.mean(y_true * np.log(p_clip) + (1.0 - y_true) * np.log(1.0 - p_clip)))
            metric_score = brier
            metric_name = "brier_score"
            log_loss_score = log_loss
        else:
            rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
            metric_score = rmse
            metric_name = "rmse"
            log_loss_score = np.nan
            
        # Calibration slope
        var_pred = np.var(y_pred)
        if var_pred > 1e-6 and n_obs >= 30:
            cov = np.cov(y_pred, y_true)[0, 1]
            cal_slope = float(cov / var_pred)
        else:
            cal_slope = np.nan
            
        # Evidence sufficiency rule:
        # Minimum 100 observations required for reliable subgroup validation
        is_sufficient = n_obs >= 100
        status = "SUFFICIENT" if is_sufficient else "INSUFFICIENT_DATA"
        
        row_dict = {col: val for col, val in zip(group_cols, group_vals)}
        row_dict.update({
            "sample_size": n_obs,
            "mean_prediction": mean_pred,
            "mean_actual": mean_actual,
            "prediction_bias": mean_pred - mean_actual,
            "calibration_slope": cal_slope,
            metric_name: metric_score,
            "log_loss": log_loss_score,
            "reliability_status": status
        })
        results.append(row_dict)
        
    return pd.DataFrame(results)
