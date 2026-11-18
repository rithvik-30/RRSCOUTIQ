"""
RR ScoutIQ — Milestone M5.5-B.4.2: Hierarchical Context Engine & Hyperparameter Estimator
Module: src/m5_5b_4_2/hierarchical_engine_b4_2.py

Implements:
1. Training-fold-only estimation of contextual priors across League, Phase, and Context Cells.
2. Cross-tier covariance integration via match-block bootstrap and multivariate DerSimonian-Laird.
3. Training-fold-only hyperparameter estimation:
   - Between-player heterogeneity tau^2_player
   - Empirical Bayes shrinkage strength M_0 (no arbitrary hardcoded 100)
4. Context-consistent player posterior baseline estimation with strict context isolation.
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd

from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy
from src.m5_5b_4_2.cluster_variance_b4_2 import (
    compute_match_block_bootstrap_covariance,
    compute_multivariate_dersimonian_laird_b42
)
from src.m5_5b_4_2.epistemic_context_engine_b4_2 import (
    ContextualPlayerBaselineRecordB42,
    EpistemicStateB42
)


class ContextualHierarchyB42:
    """
    Fits contextual priors and estimates empirical Bayes hyperparameters
    strictly from training fold deliveries.
    """
    def __init__(self, n_boot: int = 100):
        self.n_boot = n_boot
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.hyperparameters: Dict[str, float] = {}
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
                
        # 3. Context Cells with Match-Block Bootstrap Covariance
        tiers = ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]
        for phase in ["Powerplay", "Middle", "Death"]:
            phase_df = df[df["phase"] == phase]
            phase_prior = self.priors.get(f"Phase::{phase}", self.priors["League"])
            
            # Batter Boundary: Bootstrap Covariance Matrix
            cov_bnd, _, status_cov_bnd = compute_match_block_bootstrap_covariance(
                df, phase=phase, metric_type="batter_boundary", n_boot=self.n_boot
            )
            # Bowler Economy: Bootstrap Covariance Matrix
            cov_econ, _, status_cov_econ = compute_match_block_bootstrap_covariance(
                df, phase=phase, metric_type="bowler_economy", n_boot=self.n_boot
            )
            
            # Cell point estimates
            means_bnd = []
            means_econ = []
            valid_tiers_bnd = []
            valid_tiers_econ = []
            
            for tier in tiers:
                c_df = phase_df[phase_df["tier"] == tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                if len(c_legal) >= 30 and c_legal["match_id"].nunique() >= 5:
                    means_bnd.append(float(c_legal["is_boundary"].mean()))
                    valid_tiers_bnd.append(tier)
                else:
                    means_bnd.append(phase_prior["batter_boundary"]["mean"])
                    
                if len(c_legal) >= 30 and c_legal["match_id"].nunique() >= 5:
                    ec_stats = calculate_bowler_economy(c_df)
                    means_econ.append(float(ec_stats["economy_rate"]))
                    valid_tiers_econ.append(tier)
                else:
                    means_econ.append(phase_prior["bowler_economy"]["mean"])
                    
            means_bnd_arr = np.array(means_bnd)
            means_econ_arr = np.array(means_econ)
            
            # Multivariate DerSimonian-Laird without positive floors
            tau2_bnd, status_tau_bnd = compute_multivariate_dersimonian_laird_b42(means_bnd_arr, cov_bnd)
            tau2_econ, status_tau_econ = compute_multivariate_dersimonian_laird_b42(means_econ_arr, cov_econ)
            
            for idx, tier in enumerate(tiers):
                cell_key = f"Cell::{phase}::{tier}"
                c_df = phase_df[phase_df["tier"] == tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                
                # Boundary Shrinkage
                v_bnd_cell = cov_bnd[idx, idx] if (cov_bnd is not None and np.isfinite(cov_bnd[idx, idx]) and cov_bnd[idx, idx] > 0) else 0.001
                if np.isfinite(tau2_bnd) and tau2_bnd > 0:
                    w_bnd = tau2_bnd / (tau2_bnd + v_bnd_cell)
                else:
                    w_bnd = 0.0  # Exact natural full pooling
                bnd_shrunk = w_bnd * means_bnd_arr[idx] + (1.0 - w_bnd) * phase_prior["batter_boundary"]["mean"]
                
                # Economy Shrinkage (strictly in RPO)
                v_econ_cell = cov_econ[idx, idx] if (cov_econ is not None and np.isfinite(cov_econ[idx, idx]) and cov_econ[idx, idx] > 0) else 0.5
                if np.isfinite(tau2_econ) and tau2_econ > 0:
                    w_econ = tau2_econ / (tau2_econ + v_econ_cell)
                else:
                    w_econ = 0.0  # Exact natural full pooling
                econ_shrunk = w_econ * means_econ_arr[idx] + (1.0 - w_econ) * phase_prior["bowler_economy"]["mean"]
                
                self.priors[cell_key] = {
                    "phase": phase,
                    "tier": tier,
                    "deliveries": len(c_df),
                    "legal_balls": len(c_legal),
                    "batter_boundary": {
                        "mean": float(bnd_shrunk),
                        "variance": float(v_bnd_cell),
                        "tau2": float(tau2_bnd) if np.isfinite(tau2_bnd) else 0.0,
                        "weight": float(w_bnd),
                        "status": status_tau_bnd
                    },
                    "bowler_economy": {
                        "mean": float(econ_shrunk),  # In RPO
                        "expected_runs_per_legal_ball": float(econ_shrunk / 6.0),
                        "variance": float(v_econ_cell),
                        "tau2": float(tau2_econ) if np.isfinite(tau2_econ) else 0.0,
                        "weight": float(w_econ),
                        "status": status_tau_econ
                    }
                }
                
        # 4. Training-Fold-Only Hyperparameter Estimation (M0 and Between-Player Variances)
        self._estimate_hyperparameters(df)

    def _fit_league(self, df: pd.DataFrame):
        legal_df = df[df["ext_is_legal_delivery"] == 1]
        p_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else 0.165
        econ_stats = calculate_bowler_economy(df)
        econ_rpo = float(econ_stats["economy_rate"]) if np.isfinite(econ_stats["economy_rate"]) else 8.45
        self.priors["League"] = {
            "batter_boundary": {"mean": p_bnd, "variance": 0.0001, "tau2": 0.0, "status": "GLOBAL_LEAGUE"},
            "bowler_economy": {"mean": econ_rpo, "expected_runs_per_legal_ball": econ_rpo / 6.0, "variance": 0.05, "tau2": 0.0, "status": "GLOBAL_LEAGUE"}
        }

    def _fit_phase(self, phase: str, df: pd.DataFrame):
        legal_df = df[df["ext_is_legal_delivery"] == 1]
        p_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else self.priors["League"]["batter_boundary"]["mean"]
        econ_stats = calculate_bowler_economy(df)
        econ_rpo = float(econ_stats["economy_rate"]) if np.isfinite(econ_stats["economy_rate"]) else self.priors["League"]["bowler_economy"]["mean"]
        self.priors[f"Phase::{phase}"] = {
            "batter_boundary": {"mean": p_bnd, "variance": 0.0005, "tau2": 0.0, "status": "PHASE_PARENT"},
            "bowler_economy": {"mean": econ_rpo, "expected_runs_per_legal_ball": econ_rpo / 6.0, "variance": 0.10, "tau2": 0.0, "status": "PHASE_PARENT"}
        }

    def _estimate_hyperparameters(self, df: pd.DataFrame):
        """
        Estimates M0 and player prior variances solely from training fold.
        """
        bat_id_col = "striker_id" if "striker_id" in df.columns else "batter_id"
        legal_df = df[df["ext_is_legal_delivery"] == 1]
        
        # Batter boundary rate empirical Bayes variance components
        bat_agg = legal_df.groupby(bat_id_col).agg(
            boundaries=("is_boundary", "sum"),
            balls=("is_legal", "sum")
        )
        bat_qual = bat_agg[bat_agg["balls"] >= 60].copy()
        if len(bat_qual) >= 10:
            bat_qual["rate"] = bat_qual["boundaries"] / bat_qual["balls"]
            s2_bat = float(np.var(bat_qual["rate"], ddof=1))
            mean_sample_var_bat = float(np.mean(bat_qual["rate"] * (1.0 - bat_qual["rate"]) / bat_qual["balls"]))
            tau2_player_bat = max(0.0005, s2_bat - mean_sample_var_bat)
            mu_bat = float(self.priors["League"]["batter_boundary"]["mean"])
            m0_bat = float(np.clip((mu_bat * (1.0 - mu_bat)) / tau2_player_bat, 20.0, 200.0))
        else:
            tau2_player_bat = 0.002
            m0_bat = 75.0
            
        # Bowler economy empirical Bayes variance components
        bowl_agg = df.groupby("bowler_id").apply(lambda b: pd.Series(calculate_bowler_economy(b)))
        bowl_qual = bowl_agg[bowl_agg["legal_balls"] >= 60].copy()
        if len(bowl_qual) >= 10:
            s2_bowl = float(np.var(bowl_qual["economy_rate"], ddof=1))
            # Average sampling variance: ~ 16 / (legal_balls / 6)
            mean_sample_var_bowl = float(np.mean(16.0 / (bowl_qual["legal_balls"] / 6.0)))
            tau2_player_bowl = max(0.10, s2_bowl - mean_sample_var_bowl)
            # M0 corresponds to prior legal balls: 16.0 / (tau2 / 6)
            m0_bowl = float(np.clip(16.0 / (tau2_player_bowl / 6.0), 30.0, 250.0))
        else:
            tau2_player_bowl = 0.80
            m0_bowl = 120.0
            
        self.hyperparameters = {
            "batter_m0": m0_bat,
            "batter_tau2_player": tau2_player_bat,
            "bowler_m0": m0_bowl,
            "bowler_tau2_player": tau2_player_bowl
        }

    def get_context_expectation(self, phase: str, tier: str, metric: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key][metric]["mean"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key][metric]["mean"]
        return self.priors["League"][metric]["mean"]

    def get_context_variance(self, phase: str, tier: str, metric: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key][metric]["variance"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key][metric]["variance"]
        return self.priors["League"][metric]["variance"]

    def get_expected_runs_per_legal_ball(self, phase: str, tier: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key]["bowler_economy"]["expected_runs_per_legal_ball"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key]["bowler_economy"]["expected_runs_per_legal_ball"]
        return self.priors["League"]["bowler_economy"]["expected_runs_per_legal_ball"]


class PlayerPosteriorBaselineEstimatorB42:
    """
    Computes context-consistent player posterior baselines with strict context isolation.
    """
    def __init__(self, context_hierarchy: ContextualHierarchyB42):
        self.hierarchy = context_hierarchy

    def estimate_batter_boundary_posterior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        context_balls: int,
        context_boundaries: Optional[float],
        context_matches: int,
        career_balls: int,
        career_boundaries: Optional[float],
        career_matches: int,
        min_context_screening_balls: int = 30
    ) -> ContextualPlayerBaselineRecordB42:
        prior_mean = self.hierarchy.get_context_expectation(phase, tier, "batter_boundary")
        prior_var = self.hierarchy.get_context_variance(phase, tier, "batter_boundary")
        m0 = self.hierarchy.hyperparameters.get("batter_m0", 75.0)
        
        return ContextualPlayerBaselineRecordB42(
            player_id=player_id,
            phase=phase,
            tier=tier,
            context_exposure=context_balls,
            context_events=context_boundaries,
            context_matches=context_matches,
            career_exposure=career_balls,
            career_events=career_boundaries,
            career_matches=career_matches,
            context_prior_mean=prior_mean,
            context_prior_variance=prior_var,
            prior_m0=m0,
            is_economy=False,
            min_context_exposure=min_context_screening_balls
        )

    def estimate_bowler_economy_posterior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        context_legal_balls: int,
        context_debit_runs: Optional[float],
        context_matches: int,
        career_legal_balls: int,
        career_debit_runs: Optional[float],
        career_matches: int,
        min_context_screening_balls: int = 30
    ) -> ContextualPlayerBaselineRecordB42:
        prior_rpo = self.hierarchy.get_context_expectation(phase, tier, "bowler_economy")
        prior_var_rpo = self.hierarchy.get_context_variance(phase, tier, "bowler_economy")
        m0 = self.hierarchy.hyperparameters.get("bowler_m0", 120.0)
        
        return ContextualPlayerBaselineRecordB42(
            player_id=player_id,
            phase=phase,
            tier=tier,
            context_exposure=context_legal_balls,
            context_events=context_debit_runs,
            context_matches=context_matches,
            career_exposure=career_legal_balls,
            career_events=career_debit_runs,
            career_matches=career_matches,
            context_prior_mean=prior_rpo,
            context_prior_variance=prior_var_rpo,
            prior_m0=m0,
            is_economy=True,
            min_context_exposure=min_context_screening_balls
        )
