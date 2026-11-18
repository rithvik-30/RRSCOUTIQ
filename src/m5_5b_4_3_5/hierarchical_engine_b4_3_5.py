"""
RR ScoutIQ — Milestone M5.5-B.4.3.5: Hierarchical Context Engine & Hyperparameter Estimator
Module: src/m5_5b_4_3_5/hierarchical_engine_b4_3_5.py

Remediates Priority 1 audit requirements:
1. Fits contextual priors and Crossed Henderson Method III mixed-model variance components
   strictly from training-fold data.
2. Accommodates match-level variance and contextual prior-mean uncertainty in player posterior shrinkage:
   Passes exact match exposure breakdowns and context_prior_mean_variance to
   ContextualPlayerBaselineRecordB435.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd

from src.m5_5b_2.remediation_engine_b2 import (
    calculate_bowler_economy
)
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells
from src.m5_5b_4_3_5.cluster_variance_b4_3_5 import (
    compute_two_way_cluster_variance,
    compute_match_block_bootstrap_covariance
)
from src.m5_5b_4_3_5.variance_decomposition_b4_3_5 import (
    estimate_crossed_variance_components_henderson3
)
from src.m5_5b_4_3_5.epistemic_context_engine_b4_3_5 import (
    ContextualPlayerBaselineRecordB435,
    EpistemicStateB435
)


class ContextualHierarchyB435:
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
            
            cov_bnd, meta_bnd = compute_match_block_bootstrap_covariance(
                df, domain="batter", phase=phase, n_boot=self.n_boot
            )
            cov_econ, meta_econ = compute_match_block_bootstrap_covariance(
                df, domain="bowler", phase=phase, n_boot=self.n_boot
            )
            
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
                    
            for t_idx, tier in enumerate(tiers):
                cell_key = f"Cell::{phase}::{tier}"
                exp_rpb = means_econ[t_idx] / 6.0
                var_rpo = float(cov_econ[t_idx, t_idx]) if t_idx < cov_econ.shape[0] else 0.05
                var_rpb = var_rpo / 36.0
                var_bnd = float(cov_bnd[t_idx, t_idx]) if t_idx < cov_bnd.shape[0] else 0.0001
                
                self.priors[cell_key] = {
                    "batter_boundary": {
                        "mean": means_bnd[t_idx],
                        "variance": var_bnd
                    },
                    "bowler_economy": {
                        "mean": means_econ[t_idx],
                        "variance": var_rpo,
                        "mean_rpb": exp_rpb,
                        "variance_rpb": var_rpb
                    }
                }

        # 4. Fit Batter Hyperparameters strictly on Training Fold
        bat_agg = df[df["is_legal"] == 1].groupby("striker_id")["is_boundary"].agg(["count", "mean"])
        bat_agg = bat_agg[bat_agg["count"] >= 30]
        if len(bat_agg) >= 10:
            s2_bat = float(bat_agg["mean"].var())
            mu_bat = float(bat_agg["mean"].mean())
            mean_sample_var_bat = float(((bat_agg["mean"] * (1.0 - bat_agg["mean"])) / bat_agg["count"]).mean())
            tau2_player_bat = max(0.0005, s2_bat - mean_sample_var_bat)
            m0_bat = float(np.clip((mu_bat * (1.0 - mu_bat)) / tau2_player_bat, 20.0, 300.0))
        else:
            tau2_player_bat = 0.0025
            m0_bat = 75.0

        # 5. Fit Bowler Variance Components via Henderson Method III on Training Spells
        train_spells = aggregate_bowler_spells(df)
        vc_res = estimate_crossed_variance_components_henderson3(
            train_spells,
            cell_mean_cols=("phase", "modal_tier"),
            min_balls_per_spell=6
        )
        
        tau2_player_bowl = vc_res["tau2_player"]
        s2_match_bowl = vc_res["sigma2_match"]
        s2_within_bowl = vc_res["sigma2_within"]
        m0_bowl = vc_res["m0_legal_balls"]

        self.hyperparameters = {
            "batter_m0": m0_bat,
            "batter_tau2_player": tau2_player_bat,
            "bowler_m0": m0_bowl,
            "bowler_tau2_player": tau2_player_bowl,
            "bowler_sigma2_match": s2_match_bowl,
            "bowler_sigma2_within": s2_within_bowl
        }

    def _fit_league(self, df: pd.DataFrame):
        legal_df = df[df["is_legal"] == 1]
        mean_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else 0.18
        ec_stats = calculate_bowler_economy(df)
        mean_econ = float(ec_stats["economy_rate"])
        
        self.priors["League"] = {
            "batter_boundary": {"mean": mean_bnd, "variance": 0.0005},
            "bowler_economy": {
                "mean": mean_econ,
                "variance": 0.05,
                "mean_rpb": mean_econ / 6.0,
                "variance_rpb": 0.05 / 36.0
            }
        }

    def _fit_phase(self, phase: str, df: pd.DataFrame):
        legal_df = df[df["is_legal"] == 1]
        mean_bnd = float(legal_df["is_boundary"].mean()) if len(legal_df) > 0 else 0.18
        ec_stats = calculate_bowler_economy(df)
        mean_econ = float(ec_stats["economy_rate"])
        
        self.priors[f"Phase::{phase}"] = {
            "batter_boundary": {"mean": mean_bnd, "variance": 0.0008},
            "bowler_economy": {
                "mean": mean_econ,
                "variance": 0.08,
                "mean_rpb": mean_econ / 6.0,
                "variance_rpb": 0.08 / 36.0
            }
        }

    def get_context_expectation(self, phase: str, tier: str, metric: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return float(self.priors[cell_key][metric]["mean"])
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return float(self.priors[phase_key][metric]["mean"])
        return float(self.priors["League"][metric]["mean"])

    def get_context_mean_variance(self, phase: str, tier: str, metric: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return float(self.priors[cell_key][metric]["variance"])
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return float(self.priors[phase_key][metric]["variance"])
        return float(self.priors["League"][metric]["variance"])

    def get_player_tau2(self, metric: str) -> float:
        if metric == "batter_boundary":
            return float(self.hyperparameters.get("batter_tau2_player", 0.0025))
        elif metric == "bowler_economy":
            return float(self.hyperparameters.get("bowler_tau2_player", 0.465))
        return 0.01

    def get_expected_runs_per_legal_ball(self, phase: str, tier: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return float(self.priors[cell_key]["bowler_economy"].get("mean_rpb", self.priors[cell_key]["bowler_economy"]["mean"] / 6.0))
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return float(self.priors[phase_key]["bowler_economy"].get("mean_rpb", self.priors[phase_key]["bowler_economy"]["mean"] / 6.0))
        return float(self.priors["League"]["bowler_economy"].get("mean_rpb", self.priors["League"]["bowler_economy"]["mean"] / 6.0))


class PlayerPosteriorBaselineEstimatorB435:
    """
    Estimates contextual baseline posteriors for players with exact match-aware
    observation likelihood variance and coherent contextual prior-mean uncertainty.
    """
    def __init__(self, hierarchy: ContextualHierarchyB435):
        self.hierarchy = hierarchy

    def estimate_batter_boundary_posterior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        context_legal_balls: Optional[int] = None,
        context_boundaries: Optional[int] = None,
        context_matches: int = 0,
        career_legal_balls: Optional[int] = None,
        career_boundaries: Optional[int] = None,
        career_matches: int = 0,
        min_context_screening_balls: int = 30,
        context_balls: Optional[int] = None,
        career_balls: Optional[int] = None
    ) -> ContextualPlayerBaselineRecordB435:
        if context_legal_balls is None:
            context_legal_balls = context_balls if context_balls is not None else 0
        if career_legal_balls is None:
            career_legal_balls = career_balls if career_balls is not None else 0
        prior_mean = self.hierarchy.get_context_expectation(phase, tier, "batter_boundary")
        prior_mean_var = self.hierarchy.get_context_mean_variance(phase, tier, "batter_boundary")
        tau2_player = self.hierarchy.get_player_tau2("batter_boundary")
        m0 = self.hierarchy.hyperparameters.get("batter_m0", 75.0)
        
        return ContextualPlayerBaselineRecordB435(
            player_id=player_id,
            phase=phase,
            tier=tier,
            context_exposure=context_legal_balls,
            context_events=context_boundaries,
            context_matches=context_matches,
            career_exposure=career_legal_balls,
            career_events=career_boundaries,
            career_matches=career_matches,
            context_prior_mean=prior_mean,
            context_prior_mean_variance=prior_mean_var,
            tau2_player=tau2_player,
            prior_m0=m0,
            is_economy=False,
            min_context_exposure=min_context_screening_balls
        )

    def estimate_bowler_economy_posterior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        context_legal_balls: Optional[int] = None,
        context_debit_runs: Optional[float] = None,
        context_matches: int = 0,
        career_legal_balls: Optional[int] = None,
        career_debit_runs: Optional[float] = None,
        career_matches: int = 0,
        min_context_screening_balls: int = 30,
        context_match_balls_list: Optional[List[int]] = None,
        context_balls: Optional[int] = None,
        career_balls: Optional[int] = None
    ) -> ContextualPlayerBaselineRecordB435:
        if context_legal_balls is None:
            context_legal_balls = context_balls if context_balls is not None else 0
        if career_legal_balls is None:
            career_legal_balls = career_balls if career_balls is not None else 0
        prior_rpo = self.hierarchy.get_context_expectation(phase, tier, "bowler_economy")
        prior_mean_var_rpo = self.hierarchy.get_context_mean_variance(phase, tier, "bowler_economy")
        tau2_player = self.hierarchy.get_player_tau2("bowler_economy")
        m0 = self.hierarchy.hyperparameters.get("bowler_m0", 290.0)
        s2_match = self.hierarchy.hyperparameters.get("bowler_sigma2_match", 1.45)
        s2_within = self.hierarchy.hyperparameters.get("bowler_sigma2_within", 22.84)
        
        return ContextualPlayerBaselineRecordB435(
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
            context_prior_mean_variance=prior_mean_var_rpo,
            tau2_player=tau2_player,
            prior_m0=m0,
            is_economy=True,
            min_context_exposure=min_context_screening_balls,
            sigma2_match=s2_match,
            sigma2_within=s2_within,
            context_match_balls_list=context_match_balls_list
        )
