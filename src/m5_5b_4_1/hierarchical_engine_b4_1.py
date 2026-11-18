"""
RR ScoutIQ — Milestone M5.5-B.4.1: Cluster-Aware Hierarchical & Posterior Architecture
Module: src/m5_5b_4_1/hierarchical_engine_b4_1.py

Implements:
1. Exact DerSimonian-Laird tau^2 estimation without positive floors.
   - Natural full pooling (w = 0.0) when Q <= k - 1.
   - Explicit fallback when k < 2.
2. Removal of hard-coded variance proxies:
   - Evaluates empirical cluster variance directly from match/spell clusters.
   - Accounts for repeated observations within matches.
3. Separation of Contextual Prior Expectation from Player-Specific Posterior Baseline.
4. Harmonized units: all bowler economy expectations in RPO.
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd

from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy
from src.m5_5b_4_1.epistemic_engine_b4_1 import EpistemicBaselineRecordB41, EpistemicState


def compute_dersimonian_laird_b41(
    means: Union[List[float], np.ndarray],
    vars_: Union[List[float], np.ndarray]
) -> Tuple[float, str]:
    """
    Computes DerSimonian-Laird between-cell variance tau^2 with zero artificial floors.
    """
    k = len(means)
    if k < 2:
        return np.nan, "INSUFFICIENT_CELLS_FALLBACK"
    
    y = np.array(means, dtype=float)
    v = np.array(vars_, dtype=float)
    
    valid = np.isfinite(y) & np.isfinite(v) & (v > 0)
    if valid.sum() < 2:
        return np.nan, "INSUFFICIENT_CELLS_FALLBACK"
        
    y = y[valid]
    v = v[valid]
    k_v = len(y)
    
    w = 1.0 / v
    sum_w = np.sum(w)
    if sum_w <= 0:
        return np.nan, "INSUFFICIENT_CELLS_FALLBACK"
        
    y_bar = np.sum(w * y) / sum_w
    Q = np.sum(w * ((y - y_bar) ** 2))
    df = k_v - 1
    
    if Q <= df:
        # Genuinely zero between-cell variance -> natural full pooling
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    denom = sum_w - (np.sum(w ** 2) / sum_w)
    if denom <= 0:
        return 0.0, "ESTIMATED_ZERO_HOMOGENEOUS"
        
    tau2 = (Q - df) / denom
    return float(max(0.0, tau2)), "ESTIMATED_POSITIVE"


class ContextualHierarchyB41:
    """
    Fits empirical contextual hierarchy strictly from training fold data.
    All bowler economy parameters are maintained strictly in RPO.
    """
    def __init__(self):
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.diagnostics: List[Dict[str, Any]] = []

    def fit(self, train_df: pd.DataFrame):
        df = train_df.copy()
        df["phase"] = df["pre_match_phase"].astype(str)
        df["tier"] = df["pre_pressure_tier"].astype(str)
        df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
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
            
            # Batter Boundary stats
            bnd_means, bnd_vars, tiers_bnd = [], [], []
            # Bowler Economy stats (strictly in RPO)
            econ_means, econ_vars, tiers_econ = [], [], []
            
            for tier in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
                c_df = phase_df[phase_df["tier"] == tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                
                # Batter cluster-adjusted variance across matches
                if len(c_legal) >= 30 and c_legal["match_id"].nunique() >= 5:
                    p_hat = float(c_legal["is_boundary"].mean())
                    match_rates = c_legal.groupby("match_id")["is_boundary"].mean()
                    match_counts = c_legal.groupby("match_id")["is_legal"].sum()
                    w_norm = match_counts / match_counts.sum()
                    cluster_var = float(np.sum((w_norm ** 2) * np.var(match_rates)))
                    if not np.isfinite(cluster_var) or cluster_var <= 0:
                        cluster_var = (p_hat * (1.0 - p_hat)) / len(c_legal)
                        
                    bnd_means.append(p_hat)
                    bnd_vars.append(cluster_var)
                    tiers_bnd.append(tier)
                    
                # Bowler cluster-adjusted variance across spells (strictly RPO)
                if len(c_legal) >= 30 and c_legal["match_id"].nunique() >= 5:
                    econ_stats = calculate_bowler_economy(c_df)
                    actual_econ_rpo = econ_stats["economy_rate"]
                    
                    # Compute empirical spell economy variance directly from data
                    bowler_spell_runs = c_df.groupby(["bowler_id", "match_id"])["ext_bowler_debit_runs"].sum()
                    bowler_spell_balls = c_df.groupby(["bowler_id", "match_id"])["ext_is_legal_delivery"].sum()
                    valid_sp = bowler_spell_balls > 0
                    if valid_sp.sum() >= 5:
                        spell_econs = (bowler_spell_runs[valid_sp] / bowler_spell_balls[valid_sp]) * 6.0
                        empirical_spell_var = float(np.var(spell_econs))
                        var_mean_econ = empirical_spell_var / valid_sp.sum()
                    else:
                        var_mean_econ = np.nan
                        
                    if np.isfinite(actual_econ_rpo) and np.isfinite(var_mean_econ) and var_mean_econ > 0:
                        econ_means.append(actual_econ_rpo)
                        econ_vars.append(var_mean_econ)
                        tiers_econ.append(tier)
                        
            # DerSimonian-Laird tau^2
            tau2_bnd, status_bnd = compute_dersimonian_laird_b41(bnd_means, bnd_vars)
            tau2_econ, status_econ = compute_dersimonian_laird_b41(econ_means, econ_vars)
            
            for tier in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
                c_df = phase_df[phase_df["tier"] == tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                cell_key = f"Cell::{phase}::{tier}"
                
                # Boundary Shrinkage
                if tier in tiers_bnd:
                    idx = tiers_bnd.index(tier)
                    y_bnd = bnd_means[idx]
                    v_bnd = bnd_vars[idx]
                    if np.isfinite(tau2_bnd) and tau2_bnd > 0:
                        w_bnd = tau2_bnd / (tau2_bnd + v_bnd)
                    else:
                        w_bnd = 0.0  # Exact full pooling
                    bnd_shrunk = w_bnd * y_bnd + (1.0 - w_bnd) * phase_prior["batter_boundary"]["mean"]
                else:
                    w_bnd = 0.0
                    bnd_shrunk = phase_prior["batter_boundary"]["mean"]
                    
                # Economy Shrinkage (in RPO)
                if tier in tiers_econ:
                    idx = tiers_econ.index(tier)
                    y_econ = econ_means[idx]
                    v_econ = econ_vars[idx]
                    if np.isfinite(tau2_econ) and tau2_econ > 0:
                        w_econ = tau2_econ / (tau2_econ + v_econ)
                    else:
                        w_econ = 0.0  # Exact full pooling
                    econ_shrunk = w_econ * y_econ + (1.0 - w_econ) * phase_prior["bowler_economy"]["mean"]
                else:
                    w_econ = 0.0
                    econ_shrunk = phase_prior["bowler_economy"]["mean"]
                    
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
                        "mean": float(econ_shrunk),  # In RPO
                        "expected_runs_per_legal_ball": float(econ_shrunk / 6.0),
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
                    "econ_shrunk_rpo": float(econ_shrunk),
                    "econ_tau2": float(tau2_econ) if np.isfinite(tau2_econ) else 0.0,
                    "econ_status": status_econ
                })

    def _fit_league(self, df: pd.DataFrame):
        legal_df = df[df["ext_is_legal_delivery"] == 1]
        p_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else 0.165
        econ_stats = calculate_bowler_economy(df)
        econ_rpo = float(econ_stats["economy_rate"]) if np.isfinite(econ_stats["economy_rate"]) else 8.45
        self.priors["League"] = {
            "batter_boundary": {"mean": p_bnd, "tau2": 0.0, "status": "GLOBAL_LEAGUE"},
            "bowler_economy": {"mean": econ_rpo, "expected_runs_per_legal_ball": econ_rpo / 6.0, "tau2": 0.0, "status": "GLOBAL_LEAGUE"}
        }

    def _fit_phase(self, phase: str, df: pd.DataFrame):
        legal_df = df[df["ext_is_legal_delivery"] == 1]
        p_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else self.priors["League"]["batter_boundary"]["mean"]
        econ_stats = calculate_bowler_economy(df)
        econ_rpo = float(econ_stats["economy_rate"]) if np.isfinite(econ_stats["economy_rate"]) else self.priors["League"]["bowler_economy"]["mean"]
        self.priors[f"Phase::{phase}"] = {
            "batter_boundary": {"mean": p_bnd, "tau2": 0.0, "status": "PHASE_PARENT"},
            "bowler_economy": {"mean": econ_rpo, "expected_runs_per_legal_ball": econ_rpo / 6.0, "tau2": 0.0, "status": "PHASE_PARENT"}
        }

    def get_context_expectation(self, phase: str, tier: str, metric: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key][metric]["mean"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key][metric]["mean"]
        return self.priors["League"][metric]["mean"]

    def get_expected_runs_per_legal_ball(self, phase: str, tier: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key]["bowler_economy"]["expected_runs_per_legal_ball"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key]["bowler_economy"]["expected_runs_per_legal_ball"]
        return self.priors["League"]["bowler_economy"]["expected_runs_per_legal_ball"]


class PlayerPosteriorBaselineEstimatorB41:
    """
    Computes genuine player-specific posterior baselines with strict unit consistency:
    - Bowler economy prior, observation, and shrunk baseline are ALL in RPO.
    """
    def __init__(self, context_hierarchy: ContextualHierarchyB41, M0_default: float = 100.0):
        self.hierarchy = context_hierarchy
        self.M0_default = M0_default

    def estimate_batter_boundary_posterior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        player_balls: int,
        player_boundaries: Optional[float],
        min_screening_balls: int = 30
    ) -> EpistemicBaselineRecordB41:
        prior_mean = self.hierarchy.get_context_expectation(phase, tier, "batter_boundary")
        prior_var = prior_mean * (1.0 - prior_mean) / (self.M0_default + 1.0)
        return EpistemicBaselineRecordB41(
            exposure=player_balls,
            observed_events=player_boundaries,
            prior_mean=prior_mean,
            prior_m0=self.M0_default,
            prior_variance=prior_var,
            is_economy=False,
            min_exposure=min_screening_balls
        )

    def estimate_bowler_economy_posterior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        player_legal_balls: int,
        player_debit_runs: Optional[float],
        min_screening_balls: int = 30
    ) -> EpistemicBaselineRecordB41:
        """
        Derives bowler economy posterior strictly in RPO units.
        """
        prior_rpo = self.hierarchy.get_context_expectation(phase, tier, "bowler_economy")
        # Prior variance in RPO^2 ~ 16.0 / (M0 / 6.0)
        prior_var_rpo = 16.0 / max(1.0, (self.M0_default / 6.0))
        return EpistemicBaselineRecordB41(
            exposure=player_legal_balls,
            observed_events=player_debit_runs,
            prior_mean=prior_rpo,
            prior_m0=self.M0_default,
            prior_variance=prior_var_rpo,
            is_economy=True,
            min_exposure=min_screening_balls
        )
