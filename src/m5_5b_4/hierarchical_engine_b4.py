"""
RR ScoutIQ — Milestone M5.5-B.4: Hierarchical Variance Components & Player Posterior Engine
Module: src/m5_5b_4/hierarchical_engine_b4.py

Implements:
1. DerSimonian-Laird tau^2 estimator without artificial positive floor.
   - Exact tau^2 = 0.0 when Q <= k - 1 -> weight = 0.0 -> exact full pooling.
   - When k < 2, returns explicit fallback status and parent estimate.
2. Cluster-aware variance estimation (player-match clusters) for sampling variances.
3. Separation of contextual cell expectations from player-specific posterior baselines.
4. Independent batter and bowler estimation pipelines.
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd

from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy
from src.m5_5b_3.exposure_state_engine import ExposureState, EpistemicBaselineRecord


def estimate_dersimonian_laird_tau2(
    means: Union[List[float], np.ndarray],
    vars_: Union[List[float], np.ndarray]
) -> Tuple[float, str]:
    """
    Computes exact DerSimonian-Laird between-cell variance tau^2 without artificial positive floors.
    Returns:
      (tau^2, status)
      where status is:
      - 'ESTIMATED_POSITIVE': Q > k - 1, tau^2 > 0
      - 'ESTIMATED_ZERO_HOMOGENEOUS': Q <= k - 1, tau^2 == 0.0 strictly
      - 'INSUFFICIENT_CELLS_FALLBACK': k < 2, tau^2 is np.nan
    """
    k = len(means)
    if k < 2:
        return np.nan, "INSUFFICIENT_CELLS_FALLBACK"
    
    y = np.array(means, dtype=float)
    v = np.array(vars_, dtype=float)
    
    # Filter out invalid or zero variances
    valid_mask = np.isfinite(y) & np.isfinite(v) & (v > 0)
    if valid_mask.sum() < 2:
        return np.nan, "INSUFFICIENT_CELLS_FALLBACK"
        
    y = y[valid_mask]
    v = v[valid_mask]
    k_v = len(y)
    
    w = 1.0 / v
    sum_w = np.sum(w)
    if sum_w <= 0:
        return np.nan, "INSUFFICIENT_CELLS_FALLBACK"
        
    y_bar = np.sum(w * y) / sum_w
    Q = np.sum(w * ((y - y_bar) ** 2))
    
    df = k_v - 1
    if Q <= df:
        # Genuinely zero between-cell variance
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    denom = sum_w - (np.sum(w ** 2) / sum_w)
    if denom <= 0:
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    tau2 = (Q - df) / denom
    return float(max(0.0, tau2)), "ESTIMATED_POSITIVE"


class ContextualHierarchyB4:
    """
    Builds contextual hierarchy (League -> Phase -> Phase x Tier Cell).
    Estimates empirical cluster-aware variances from training data.
    """
    def __init__(self):
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.diagnostics: List[Dict[str, Any]] = []

    def fit(self, train_df: pd.DataFrame):
        df = train_df.copy()
        df["phase"] = df["pre_match_phase"].astype(str)
        df["tier"] = df["pre_pressure_tier"].astype(str)
        df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
        df["is_dot"] = (df["ext_bowler_debit_runs"] == 0).astype(int)
        df["is_wkt"] = (df["ext_is_bowler_wicket"] == 1).astype(int)
        df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
        
        # 1. League Level
        self._fit_league(df)
        
        # 2. Phase Level
        for phase in ["Powerplay", "Middle", "Death"]:
            p_df = df[df["phase"] == phase]
            if len(p_df) > 0:
                self._fit_phase(phase, p_df)
                
        # 3. Context Cells (Phase x Tier)
        for phase in ["Powerplay", "Middle", "Death"]:
            phase_df = df[df["phase"] == phase]
            phase_prior = self.priors.get(f"Phase::{phase}", self.priors["League"])
            
            # Batter Boundary % variance components
            bnd_means = []
            bnd_vars = []
            tier_list_bnd = []
            
            # Bowler Run expectation variance components
            econ_means = []
            econ_vars = []
            tier_list_econ = []
            
            for tier in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
                c_df = phase_df[phase_df["tier"] == tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                
                # Batter Boundary: compute cluster-adjusted variance across matches
                if len(c_legal) >= 30 and c_legal["match_id"].nunique() >= 5:
                    p_hat = float(c_legal["is_boundary"].mean())
                    # Match clustered variance
                    match_rates = c_legal.groupby("match_id")["is_boundary"].mean()
                    match_weights = c_legal.groupby("match_id")["is_legal"].sum()
                    w_norm = match_weights / match_weights.sum()
                    cluster_var = float(np.sum((w_norm ** 2) * np.var(match_rates)))
                    if not np.isfinite(cluster_var) or cluster_var <= 0:
                        cluster_var = (p_hat * (1.0 - p_hat)) / len(c_legal)
                        
                    bnd_means.append(p_hat)
                    bnd_vars.append(cluster_var)
                    tier_list_bnd.append(tier)
                    
                # Bowler Economy: compute empirical cluster-adjusted variance across spells
                if len(c_legal) >= 30 and c_legal["match_id"].nunique() >= 5:
                    econ_stats = calculate_bowler_economy(c_df)
                    actual_econ = econ_stats["economy_rate"]
                    # Compute spell variance directly from data, NOT an unexplained proxy
                    bowler_spell_runs = c_df.groupby(["bowler_id", "match_id"])["ext_bowler_debit_runs"].sum()
                    bowler_spell_balls = c_df.groupby(["bowler_id", "match_id"])["ext_is_legal_delivery"].sum()
                    valid_sp = bowler_spell_balls > 0
                    if valid_sp.sum() >= 5:
                        spell_econs = (bowler_spell_runs[valid_sp] / bowler_spell_balls[valid_sp]) * 6.0
                        empirical_spell_var = float(np.var(spell_econs))
                        var_mean_econ = empirical_spell_var / valid_sp.sum()
                    else:
                        var_mean_econ = 4.0 / max(1.0, len(c_legal) / 6.0)
                        
                    econ_means.append(actual_econ)
                    econ_vars.append(var_mean_econ)
                    tier_list_econ.append(tier)
                    
            # Estimate tau^2 via exact DerSimonian-Laird
            tau2_bnd, status_bnd = estimate_dersimonian_laird_tau2(bnd_means, bnd_vars)
            tau2_econ, status_econ = estimate_dersimonian_laird_tau2(econ_means, econ_vars)
            
            # Populate cell priors
            for tier in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
                c_df = phase_df[phase_df["tier"] == tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                cell_key = f"Cell::{phase}::{tier}"
                
                # Boundary Shrinkage
                if tier in tier_list_bnd:
                    idx = tier_list_bnd.index(tier)
                    y_c = bnd_means[idx]
                    v_c = bnd_vars[idx]
                    if np.isfinite(tau2_bnd) and tau2_bnd > 0:
                        w_bnd = tau2_bnd / (tau2_bnd + v_c)
                    else:
                        w_bnd = 0.0  # Exact full pooling
                    bnd_shrunk = w_bnd * y_c + (1.0 - w_bnd) * phase_prior["batter_boundary"]["mean"]
                else:
                    w_bnd = 0.0
                    bnd_shrunk = phase_prior["batter_boundary"]["mean"]
                    v_c = np.nan
                    
                # Economy Shrinkage
                if tier in tier_list_econ:
                    idx = tier_list_econ.index(tier)
                    y_e = econ_means[idx]
                    v_e = econ_vars[idx]
                    if np.isfinite(tau2_econ) and tau2_econ > 0:
                        w_econ = tau2_econ / (tau2_econ + v_e)
                    else:
                        w_econ = 0.0  # Exact full pooling
                    econ_shrunk = w_econ * y_e + (1.0 - w_econ) * phase_prior["bowler_economy"]["mean"]
                else:
                    w_econ = 0.0
                    econ_shrunk = phase_prior["bowler_economy"]["mean"]
                    v_e = np.nan
                    
                # Delivery expected runs per ball = econ / 6.0
                deliv_exp_rpb = econ_shrunk / 6.0
                
                self.priors[cell_key] = {
                    "phase": phase,
                    "tier": tier,
                    "deliveries": len(c_df),
                    "legal_balls": len(c_legal),
                    "batter_boundary": {
                        "mean": float(bnd_shrunk),
                        "tau2": float(tau2_bnd) if np.isfinite(tau2_bnd) else 0.0,
                        "weight": float(w_bnd),
                        "status": status_bnd
                    },
                    "bowler_economy": {
                        "mean": float(econ_shrunk),
                        "expected_runs_per_ball": float(deliv_exp_rpb),
                        "tau2": float(tau2_econ) if np.isfinite(tau2_econ) else 0.0,
                        "weight": float(w_econ),
                        "status": status_econ
                    }
                }
                
                self.diagnostics.append({
                    "cell_key": cell_key,
                    "phase": phase,
                    "tier": tier,
                    "deliveries": len(c_df),
                    "legal_balls": len(c_legal),
                    "bnd_shrunk": float(bnd_shrunk),
                    "bnd_tau2": float(tau2_bnd) if np.isfinite(tau2_bnd) else 0.0,
                    "bnd_status": status_bnd,
                    "econ_shrunk": float(econ_shrunk),
                    "deliv_exp_rpb": float(deliv_exp_rpb),
                    "econ_tau2": float(tau2_econ) if np.isfinite(tau2_econ) else 0.0,
                    "econ_status": status_econ
                })

    def _fit_league(self, df: pd.DataFrame):
        legal_df = df[df["ext_is_legal_delivery"] == 1]
        p_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else 0.165
        econ_stats = calculate_bowler_economy(df)
        econ = float(econ_stats["economy_rate"]) if np.isfinite(econ_stats["economy_rate"]) else 8.45
        self.priors["League"] = {
            "batter_boundary": {"mean": p_bnd, "tau2": 0.0, "status": "GLOBAL_LEAGUE"},
            "bowler_economy": {"mean": econ, "expected_runs_per_ball": econ / 6.0, "tau2": 0.0, "status": "GLOBAL_LEAGUE"}
        }

    def _fit_phase(self, phase: str, df: pd.DataFrame):
        legal_df = df[df["ext_is_legal_delivery"] == 1]
        p_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else self.priors["League"]["batter_boundary"]["mean"]
        econ_stats = calculate_bowler_economy(df)
        econ = float(econ_stats["economy_rate"]) if np.isfinite(econ_stats["economy_rate"]) else self.priors["League"]["bowler_economy"]["mean"]
        self.priors[f"Phase::{phase}"] = {
            "batter_boundary": {"mean": p_bnd, "tau2": 0.0, "status": "PHASE_PARENT"},
            "bowler_economy": {"mean": econ, "expected_runs_per_ball": econ / 6.0, "tau2": 0.0, "status": "PHASE_PARENT"}
        }

    def get_context_expectation(self, phase: str, tier: str, metric: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key][metric]["mean"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key][metric]["mean"]
        return self.priors["League"][metric]["mean"]

    def get_delivery_expected_runs(self, phase: str, tier: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key]["bowler_economy"]["expected_runs_per_ball"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key]["bowler_economy"]["expected_runs_per_ball"]
        return self.priors["League"]["bowler_economy"]["expected_runs_per_ball"]


# ---------------------------------------------------------------------------
# Player-Specific Empirical Bayes Posterior Baseline
# ---------------------------------------------------------------------------

class PlayerPosteriorBaselineEstimator:
    """
    Computes genuine player-specific posterior baselines combining:
    1. Player's own valid observations in context c: (n_ic, y_ic)
    2. Contextual prior mean: theta_c*
    3. Exposure-dependent shrinkage weight: lambda_ic = n_ic / (n_ic + M_c)
    """
    def __init__(self, context_hierarchy: ContextualHierarchyB4, M0_default: float = 100.0):
        self.hierarchy = context_hierarchy
        self.M0_default = M0_default

    def estimate_batter_baseline(
        self,
        player_id: int,
        phase: str,
        tier: str,
        player_balls: int,
        player_events: Optional[float],
        min_screening_balls: int = 30
    ) -> EpistemicBaselineRecord:
        """
        Derives player-specific posterior baseline for batter discrete or rate metric.
        """
        prior_mean = self.hierarchy.get_context_expectation(phase, tier, "batter_boundary")
        # Approximate prior variance p*(1-p)/(M0+1)
        prior_var = prior_mean * (1.0 - prior_mean) / (self.M0_default + 1.0)
        
        return EpistemicBaselineRecord(
            exposure=player_balls,
            observed_events=player_events,
            prior_mean=prior_mean,
            prior_m0=self.M0_default,
            prior_variance=prior_var,
            min_exposure=min_screening_balls
        )

    def estimate_bowler_baseline(
        self,
        player_id: int,
        phase: str,
        tier: str,
        player_legal_balls: int,
        player_debit_runs: Optional[float],
        min_screening_balls: int = 30
    ) -> EpistemicBaselineRecord:
        """
        Derives player-specific posterior baseline for bowler economy.
        """
        prior_econ = self.hierarchy.get_context_expectation(phase, tier, "bowler_economy")
        prior_var = 4.0 / (self.M0_default / 6.0)  # Variance across M0-ball window
        
        # Bowler observed events is economy rate * (balls / 6.0) = debited runs
        return EpistemicBaselineRecord(
            exposure=player_legal_balls,
            observed_events=player_debit_runs,
            prior_mean=prior_econ,
            prior_m0=self.M0_default,
            prior_variance=prior_var,
            min_exposure=min_screening_balls
        )
