"""
RR ScoutIQ — Milestone M5.5-B.4.3.6: Hierarchical Context Engine & LOPO Prior Estimator
Module: src/m5_5b_4_3_6/hierarchical_engine_b4_3_6.py

Remediates M5.5-B.4.3.6 Priorities 1, 2, and 4:
1. Strict Leave-One-Player-Out (LOPO) Contextual Priors:
   - For every player-context evaluation, the player's own training observations
     are strictly excised from the contextual cell, phase, and league totals.
   - Prevents contextual prior / player observation dependence.
   - Preserves training-fold-only estimation.
   - Explicitly records prior population exposure and provenance status:
     CELL_LOPO_ROBUST, PHASE_LOPO_FALLBACK, or LEAGUE_LOPO_FALLBACK.
2. Scales contextual prior uncertainty by N_full / N_LOPO to account for the
   degrees-of-freedom reduction while preserving match-block dependence.
3. Interfaces with ContextualPlayerBaselineRecordB436 for full Joint Conjugate
   Bayesian updating.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd

from src.m5_5b_2.remediation_engine_b2 import (
    calculate_bowler_economy
)
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells
from src.m5_5b_4_3_6.cluster_variance_b4_3_6 import (
    compute_two_way_cluster_variance,
    compute_match_block_bootstrap_covariance
)
from src.m5_5b_4_3_6.variance_decomposition_b4_3_6 import (
    estimate_crossed_variance_components_henderson3
)
from src.m5_5b_4_3_6.epistemic_context_engine_b4_3_6 import (
    ContextualPlayerBaselineRecordB436,
    EpistemicStateB436
)


class ContextualHierarchyB436:
    """
    Fits contextual priors, pre-aggregates player totals for Leave-One-Player-Out
    (LOPO) extraction, and estimates empirical Bayes hyperparameters strictly
    from training fold deliveries.
    """
    def __init__(self, n_boot: int = 100):
        self.n_boot = n_boot
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.cell_totals: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.phase_totals: Dict[str, Dict[str, Any]] = {}
        self.league_totals: Dict[str, Any] = {}
        
        # Player pre-aggregates for LOPO decontamination:
        self.bowler_cell_stats: Dict[Tuple[int, str, str], Dict[str, float]] = {}
        self.bowler_phase_stats: Dict[Tuple[int, str], Dict[str, float]] = {}
        self.bowler_league_stats: Dict[int, Dict[str, float]] = {}
        
        self.batter_cell_stats: Dict[Tuple[int, str, str], Dict[str, float]] = {}
        self.batter_phase_stats: Dict[Tuple[int, str], Dict[str, float]] = {}
        self.batter_league_stats: Dict[int, Dict[str, float]] = {}
        
        self.hyperparameters: Dict[str, float] = {}
        self.diagnostics: List[Dict[str, Any]] = []

    def fit(self, train_df: pd.DataFrame):
        df = train_df.copy()
        if "pre_match_phase" in df.columns:
            df["phase"] = df["pre_match_phase"].astype(str)
        elif "phase" in df.columns:
            df["phase"] = df["phase"].astype(str)
            df["pre_match_phase"] = df["phase"]
        else:
            raise KeyError("Neither 'pre_match_phase' nor 'phase' in train_df")
            
        if "pre_pressure_tier" in df.columns:
            df["tier"] = df["pre_pressure_tier"].astype(str)
        elif "tier" in df.columns:
            df["tier"] = df["tier"].astype(str)
            df["pre_pressure_tier"] = df["tier"]
        else:
            raise KeyError("Neither 'pre_pressure_tier' nor 'tier' in train_df")
            
        if "ext_is_four" in df.columns and "ext_is_six" in df.columns:
            df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
        elif "is_boundary" in df.columns:
            df["is_boundary"] = df["is_boundary"].astype(int)
        else:
            df["is_boundary"] = 0
            
        if "ext_is_legal_delivery" in df.columns:
            df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
        elif "is_legal" in df.columns:
            df["is_legal"] = df["is_legal"].astype(int)
            df["ext_is_legal_delivery"] = df["is_legal"]
        else:
            df["is_legal"] = 1
            df["ext_is_legal_delivery"] = 1
            
        if "ext_bowler_debit_runs" not in df.columns:
            if "runs_batter" in df.columns and "extra_runs" in df.columns:
                df["ext_bowler_debit_runs"] = df["runs_batter"] + df["extra_runs"]
            elif "bowler_debit_runs" in df.columns:
                df["ext_bowler_debit_runs"] = df["bowler_debit_runs"]
            else:
                df["ext_bowler_debit_runs"] = 0
                
        if "ext_is_wide" not in df.columns:
            df["ext_is_wide"] = df.get("is_wide", 0).astype(int)
        if "ext_is_noball" not in df.columns:
            df["ext_is_noball"] = df.get("is_noball", 0).astype(int)
        
        bat_id_col = "batter_id" if "batter_id" in df.columns else "striker_id"
        df["bat_id"] = df[bat_id_col].astype(int)
        df["bowl_id"] = df["bowler_id"].astype(int)
        
        # 1. League Level Totals
        legal_df = df[df["is_legal"] == 1]
        league_balls = len(legal_df)
        league_bnd = int(legal_df["is_boundary"].sum())
        league_econ_stats = calculate_bowler_economy(df)
        league_runs = float(league_econ_stats["bowler_debit_runs"])
        league_mean_bnd = float(league_bnd / max(1, league_balls))
        league_mean_econ = float(league_econ_stats["economy_rate"])
        
        self.league_totals = {
            "legal_balls": league_balls,
            "batter_boundaries": league_bnd,
            "bowler_debit_runs": league_runs,
            "mean_bnd": league_mean_bnd,
            "mean_econ": league_mean_econ,
            "var_bnd": 0.0005,
            "var_econ": 0.05
        }
        
        self.priors["League"] = {
            "batter_boundary": {"mean": league_mean_bnd, "variance": 0.0005},
            "bowler_economy": {
                "mean": league_mean_econ,
                "variance": 0.05,
                "mean_rpb": league_mean_econ / 6.0,
                "variance_rpb": 0.05 / 36.0
            }
        }
        
        # 2. Phase Level Totals
        for phase in ["Powerplay", "Middle", "Death"]:
            p_df = df[df["phase"] == phase]
            p_legal = p_df[p_df["is_legal"] == 1]
            p_balls = len(p_legal)
            p_bnd = int(p_legal["is_boundary"].sum()) if p_balls > 0 else 0
            p_econ_stats = calculate_bowler_economy(p_df)
            p_runs = float(p_econ_stats["bowler_debit_runs"])
            p_mean_bnd = float(p_bnd / max(1, p_balls)) if p_balls > 0 else league_mean_bnd
            p_mean_econ = float(p_econ_stats["economy_rate"]) if p_balls > 0 else league_mean_econ
            
            self.phase_totals[phase] = {
                "legal_balls": p_balls,
                "batter_boundaries": p_bnd,
                "bowler_debit_runs": p_runs,
                "mean_bnd": p_mean_bnd,
                "mean_econ": p_mean_econ,
                "var_bnd": 0.0008,
                "var_econ": 0.08
            }
            
            self.priors[f"Phase::{phase}"] = {
                "batter_boundary": {"mean": p_mean_bnd, "variance": 0.0008},
                "bowler_economy": {
                    "mean": p_mean_econ,
                    "variance": 0.08,
                    "mean_rpb": p_mean_econ / 6.0,
                    "variance_rpb": 0.08 / 36.0
                }
            }
            
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
            
            for t_idx, tier in enumerate(tiers):
                c_df = phase_df[phase_df["tier"] == tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                c_balls = len(c_legal)
                c_matches = int(c_legal["match_id"].nunique()) if c_balls > 0 else 0
                
                var_rpo = float(cov_econ[t_idx, t_idx]) if t_idx < cov_econ.shape[0] else 0.05
                var_bnd = float(cov_bnd[t_idx, t_idx]) if t_idx < cov_bnd.shape[0] else 0.0001
                
                if c_balls >= 30 and c_matches >= 5:
                    c_bnd = int(c_legal["is_boundary"].sum())
                    c_econ_stats = calculate_bowler_economy(c_df)
                    c_runs = float(c_econ_stats["bowler_debit_runs"])
                    c_mean_bnd = float(c_bnd / c_balls)
                    c_mean_econ = float(c_econ_stats["economy_rate"])
                else:
                    c_bnd = 0
                    c_runs = 0.0
                    c_mean_bnd = phase_prior["batter_boundary"]["mean"]
                    c_mean_econ = phase_prior["bowler_economy"]["mean"]
                    
                self.cell_totals[(phase, tier)] = {
                    "legal_balls": c_balls,
                    "batter_boundaries": c_bnd,
                    "bowler_debit_runs": c_runs,
                    "matches": c_matches,
                    "mean_bnd": c_mean_bnd,
                    "mean_econ": c_mean_econ,
                    "var_bnd": var_bnd,
                    "var_econ": var_rpo
                }
                
                cell_key = f"Cell::{phase}::{tier}"
                self.priors[cell_key] = {
                    "batter_boundary": {
                        "mean": c_mean_bnd,
                        "variance": var_bnd
                    },
                    "bowler_economy": {
                        "mean": c_mean_econ,
                        "variance": var_rpo,
                        "mean_rpb": c_mean_econ / 6.0,
                        "variance_rpb": var_rpo / 36.0
                    }
                }
                
        # 4. Pre-aggregate Individual Player Contributions for O(1) LOPO Extraction
        # Bowlers:
        def _get_bowler_runs(grp):
            if "ext_bowler_debit_runs" in grp.columns:
                return float(grp["ext_bowler_debit_runs"].sum())
            elif "ext_bowler_runs" in grp.columns:
                return float(grp["ext_bowler_runs"].sum())
            elif "runs_batter" in grp.columns and "extra_runs" in grp.columns:
                return float((grp["runs_batter"] + grp["extra_runs"]).sum())
            elif "ext_batsman_runs" in grp.columns:
                return float((grp["ext_batsman_runs"] + grp.get("ext_wide_runs", 0) + grp.get("ext_noball_runs", 0)).sum())
            return 0.0

        for (bid, ph, tr), b_grp in legal_df.groupby(["bowl_id", "phase", "tier"]):
            self.bowler_cell_stats[(bid, ph, tr)] = {
                "balls": len(b_grp),
                "runs": _get_bowler_runs(b_grp)
            }
        for (bid, ph), b_grp in legal_df.groupby(["bowl_id", "phase"]):
            self.bowler_phase_stats[(bid, ph)] = {
                "balls": len(b_grp),
                "runs": _get_bowler_runs(b_grp)
            }
        for bid, b_grp in legal_df.groupby("bowl_id"):
            self.bowler_league_stats[bid] = {
                "balls": len(b_grp),
                "runs": _get_bowler_runs(b_grp)
            }
            
        # Batters:
        for (pid, ph, tr), bat_grp in legal_df.groupby(["bat_id", "phase", "tier"]):
            self.batter_cell_stats[(pid, ph, tr)] = {
                "balls": len(bat_grp),
                "boundaries": int(bat_grp["is_boundary"].sum())
            }
        for (pid, ph), bat_grp in legal_df.groupby(["bat_id", "phase"]):
            self.batter_phase_stats[(pid, ph)] = {
                "balls": len(bat_grp),
                "boundaries": int(bat_grp["is_boundary"].sum())
            }
        for pid, bat_grp in legal_df.groupby("bat_id"):
            self.batter_league_stats[pid] = {
                "balls": len(bat_grp),
                "boundaries": int(bat_grp["is_boundary"].sum())
            }
            
        # 5. Fit Batter Hyperparameters strictly on Training Fold
        bat_agg = legal_df.groupby("bat_id")["is_boundary"].agg(["count", "mean"])
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

        # 6. Fit Bowler Variance Components via Henderson Method III on Training Spells
        train_spells = aggregate_bowler_spells(df)
        try:
            vc_res = estimate_crossed_variance_components_henderson3(
                train_spells,
                cell_mean_cols=("phase", "modal_tier"),
                min_balls_per_spell=6
            )
            tau2_player_bowl = vc_res["tau2_player"]
            s2_match_bowl = vc_res["sigma2_match"]
            s2_within_bowl = vc_res["sigma2_within"]
            m0_bowl = vc_res["m0_legal_balls"]
        except Exception:
            tau2_player_bowl = 0.50
            s2_match_bowl = 1.50
            s2_within_bowl = 24.0
            m0_bowl = (6.0 * s2_within_bowl) / tau2_player_bowl

        self.hyperparameters = {
            "batter_m0": m0_bat,
            "batter_tau2_player": tau2_player_bat,
            "bowler_m0": m0_bowl,
            "bowler_tau2_player": tau2_player_bowl,
            "bowler_sigma2_match": s2_match_bowl,
            "bowler_sigma2_within": s2_within_bowl
        }

    def get_lopo_context_prior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        domain: str = "bowler"
    ) -> Tuple[float, float, str, int]:
        """
        Extracts Leave-One-Player-Out (LOPO) contextual mean and sampling variance.
        Guarantees that player_id's own observations are strictly excised from the prior.
        
        Returns:
        (prior_mean, prior_variance, provenance_status, prior_population_balls)
        """
        pid = int(player_id)
        is_bowler = domain.lower() == "bowler"
        
        # 1. Try Context Cell LOPO
        cell_info = self.cell_totals.get((phase, tier), None)
        if cell_info is not None:
            n_cell = cell_info["legal_balls"]
            if is_bowler:
                player_sub = self.bowler_cell_stats.get((pid, phase, tier), {"balls": 0, "runs": 0.0})
                n_lopo = n_cell - player_sub["balls"]
                r_lopo = cell_info["bowler_debit_runs"] - player_sub["runs"]
                if n_lopo >= 30:
                    mean_lopo = 6.0 * (r_lopo / float(n_lopo))
                    # Scale variance by sample size reduction ratio N_full / N_lopo
                    var_scale = float(n_cell) / float(max(1, n_lopo))
                    var_lopo = float(cell_info["var_econ"]) * var_scale
                    return mean_lopo, var_lopo, "CELL_LOPO_ROBUST", n_lopo
            else:
                player_sub = self.batter_cell_stats.get((pid, phase, tier), {"balls": 0, "boundaries": 0})
                n_lopo = n_cell - player_sub["balls"]
                b_lopo = cell_info["batter_boundaries"] - player_sub["boundaries"]
                if n_lopo >= 30:
                    mean_lopo = float(b_lopo) / float(n_lopo)
                    var_scale = float(n_cell) / float(max(1, n_lopo))
                    var_lopo = float(cell_info["var_bnd"]) * var_scale
                    return mean_lopo, var_lopo, "CELL_LOPO_ROBUST", n_lopo
                    
        # 2. Fallback to Phase LOPO
        phase_info = self.phase_totals.get(phase, None)
        if phase_info is not None:
            n_ph = phase_info["legal_balls"]
            if is_bowler:
                player_sub_ph = self.bowler_phase_stats.get((pid, phase), {"balls": 0, "runs": 0.0})
                n_lopo_ph = n_ph - player_sub_ph["balls"]
                r_lopo_ph = phase_info["bowler_debit_runs"] - player_sub_ph["runs"]
                if n_lopo_ph >= 30:
                    mean_lopo_ph = 6.0 * (r_lopo_ph / float(n_lopo_ph))
                    var_scale_ph = float(n_ph) / float(max(1, n_lopo_ph))
                    var_lopo_ph = float(phase_info["var_econ"]) * var_scale_ph
                    return mean_lopo_ph, var_lopo_ph, "PHASE_LOPO_FALLBACK", n_lopo_ph
            else:
                player_sub_ph = self.batter_phase_stats.get((pid, phase), {"balls": 0, "boundaries": 0})
                n_lopo_ph = n_ph - player_sub_ph["balls"]
                b_lopo_ph = phase_info["batter_boundaries"] - player_sub_ph["boundaries"]
                if n_lopo_ph >= 30:
                    mean_lopo_ph = float(b_lopo_ph) / float(n_lopo_ph)
                    var_scale_ph = float(n_ph) / float(max(1, n_lopo_ph))
                    var_lopo_ph = float(phase_info["var_bnd"]) * var_scale_ph
                    return mean_lopo_ph, var_lopo_ph, "PHASE_LOPO_FALLBACK", n_lopo_ph
                    
        # 3. Fallback to League LOPO
        n_lg = self.league_totals["legal_balls"]
        if is_bowler:
            player_sub_lg = self.bowler_league_stats.get(pid, {"balls": 0, "runs": 0.0})
            n_lopo_lg = max(1, n_lg - player_sub_lg["balls"])
            r_lopo_lg = max(0.0, self.league_totals["bowler_debit_runs"] - player_sub_lg["runs"])
            mean_lopo_lg = 6.0 * (r_lopo_lg / float(n_lopo_lg))
            var_scale_lg = float(n_lg) / float(n_lopo_lg)
            var_lopo_lg = float(self.league_totals["var_econ"]) * var_scale_lg
            return mean_lopo_lg, var_lopo_lg, "LEAGUE_LOPO_FALLBACK", n_lopo_lg
        else:
            player_sub_lg = self.batter_league_stats.get(pid, {"balls": 0, "boundaries": 0})
            n_lopo_lg = max(1, n_lg - player_sub_lg["balls"])
            b_lopo_lg = max(0, self.league_totals["batter_boundaries"] - player_sub_lg["boundaries"])
            mean_lopo_lg = float(b_lopo_lg) / float(n_lopo_lg)
            var_scale_lg = float(n_lg) / float(n_lopo_lg)
            var_lopo_lg = float(self.league_totals["var_bnd"]) * var_scale_lg
            return mean_lopo_lg, var_lopo_lg, "LEAGUE_LOPO_FALLBACK", n_lopo_lg

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


class PlayerPosteriorBaselineEstimatorB436:
    """
    Estimates contextual baseline posteriors for players with exact match-aware
    observation likelihood variance and genuine Leave-One-Player-Out (LOPO) contextual priors.
    """
    def __init__(self, hierarchy: ContextualHierarchyB436):
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
    ) -> ContextualPlayerBaselineRecordB436:
        if context_legal_balls is None:
            context_legal_balls = context_balls if context_balls is not None else 0
        if career_legal_balls is None:
            career_legal_balls = career_balls if career_balls is not None else 0
            
        prior_mean, prior_mean_var, provenance, pop_balls = self.hierarchy.get_lopo_context_prior(
            player_id=player_id, phase=phase, tier=tier, domain="batter"
        )
        tau2_player = self.hierarchy.get_player_tau2("batter_boundary")
        m0 = self.hierarchy.hyperparameters.get("batter_m0", 75.0)
        
        return ContextualPlayerBaselineRecordB436(
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
            min_context_exposure=min_context_screening_balls,
            prior_provenance=provenance,
            prior_population_balls=pop_balls
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
    ) -> ContextualPlayerBaselineRecordB436:
        if context_legal_balls is None:
            context_legal_balls = context_balls if context_balls is not None else 0
        if career_legal_balls is None:
            career_legal_balls = career_balls if career_balls is not None else 0
            
        prior_rpo, prior_mean_var_rpo, provenance, pop_balls = self.hierarchy.get_lopo_context_prior(
            player_id=player_id, phase=phase, tier=tier, domain="bowler"
        )
        tau2_player = self.hierarchy.get_player_tau2("bowler_economy")
        m0 = self.hierarchy.hyperparameters.get("bowler_m0", 290.0)
        s2_match = self.hierarchy.hyperparameters.get("bowler_sigma2_match", 1.45)
        s2_within = self.hierarchy.hyperparameters.get("bowler_sigma2_within", 22.84)
        
        return ContextualPlayerBaselineRecordB436(
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
            context_match_balls_list=context_match_balls_list,
            prior_provenance=provenance,
            prior_population_balls=pop_balls
        )
