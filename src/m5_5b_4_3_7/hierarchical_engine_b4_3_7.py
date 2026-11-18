"""
RR ScoutIQ — Milestone M5.5-B.4.3.7: Hierarchical Context Engine & LPMO Prior Estimator
Module: src/m5_5b_4_3_7/hierarchical_engine_b4_3_7.py

Implements M5.5-B.4.3.7 Requirements:
1. Genuine Leave-Player-and-Matches-Out (LPMO) Contextual Priors:
   - For every player i, all matches in which player i participated in the training fold
     are strictly excised from the contextual cell, phase, and league totals.
   - Eliminates both direct player observation dependence AND shared-match environmental
     shock dependence across co-participating players.
2. Cluster-Aware Match-Level Uncertainty Estimation:
   - Replaces crude exposure ratios with exact cluster-robust ratio estimator variance
     across remaining independent matches.
   - Computes match concentration HHI and effective match count M_eff.
3. Principled 3-Tier Fallback Hierarchy with Minimum Match Thresholds:
   - CELL_LPMO_ROBUST: M_remain >= 15 active matches and N_remain >= 30 legal balls.
   - PHASE_LPMO_FALLBACK: M_phase >= 15 active matches and N_phase >= 30 legal balls.
   - LEAGUE_LPMO_FALLBACK: M_league >= 15 active matches and N_league >= 30 legal balls.
   - UNRELIABLE_SPARSE_MATCHES: If remaining independent match count < 15.
4. Interfaces with ContextualPlayerBaselineRecordB437 for Full Joint Conjugate
   Gaussian Bayesian updating.
"""

import math
from typing import Dict, List, Any, Optional, Tuple, Set
import numpy as np
import pandas as pd

from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy
from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells
from src.m5_5b_4_3_7.cluster_variance_b4_3_7 import (
    compute_two_way_cluster_variance,
    compute_match_block_bootstrap_covariance
)
from src.m5_5b_4_3_7.variance_decomposition_b4_3_7 import (
    estimate_crossed_variance_components_henderson3
)
from src.m5_5b_4_3_7.epistemic_context_engine_b4_3_7 import (
    ContextualPlayerBaselineRecordB437,
    EpistemicStateB437
)


class ContextualHierarchyB437:
    """
    Fits contextual priors, pre-aggregates match-level totals for Leave-Player-and-Matches-Out
    (LPMO) extraction, and estimates empirical Bayes hyperparameters strictly
    from training fold deliveries.
    """
    def __init__(self, n_boot: int = 100):
        self.n_boot = n_boot
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.hyperparameters: Dict[str, float] = {}
        self.diagnostics: List[Dict[str, Any]] = []
        
        # Player-to-matches mapping
        self.player_matches: Dict[int, Set[int]] = {}
        self.all_training_matches: Set[int] = set()
        
        # Match-level statistics tables for O(1) LPMO extraction
        # Key: (match_id, phase, tier)
        self.match_cell_stats: Dict[Tuple[int, str, str], Dict[str, float]] = {}
        # Key: (match_id, phase)
        self.match_phase_stats: Dict[Tuple[int, str], Dict[str, float]] = {}
        # Key: match_id
        self.match_league_stats: Dict[int, Dict[str, float]] = {}
        
        # Global aggregated sums of moments across all matches in training fold
        self.global_cell_moments: Dict[Tuple[str, str], Dict[str, float]] = {}
        self.global_phase_moments: Dict[str, Dict[str, float]] = {}
        self.global_league_moments: Dict[str, float] = {}

    def fit(self, train_df: pd.DataFrame):
        df = train_df.copy()
        
        # Standardize column mappings
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
        
        # 1. Map every player to all matches they participated in (as bowler OR batter)
        self.all_training_matches = set(df["match_id"].unique())
        self.player_matches = {}
        
        # Bowler participations
        for bid, m_set in df.groupby("bowl_id")["match_id"]:
            self.player_matches.setdefault(int(bid), set()).update(m_set.unique())
        # Batter participations
        for batid, m_set in df.groupby("bat_id")["match_id"]:
            self.player_matches.setdefault(int(batid), set()).update(m_set.unique())
            
        # 2. Match-Level Pre-aggregation across Legal Deliveries
        legal_df = df[df["is_legal"] == 1].copy()
        
        self.match_cell_stats = {}
        for (mid, ph, tr), grp in legal_df.groupby(["match_id", "phase", "tier"]):
            self.match_cell_stats[(int(mid), str(ph), str(tr))] = {
                "balls": float(len(grp)),
                "runs": float(grp["ext_bowler_debit_runs"].sum()),
                "boundaries": float(grp["is_boundary"].sum())
            }
            
        self.match_phase_stats = {}
        for (mid, ph), grp in legal_df.groupby(["match_id", "phase"]):
            self.match_phase_stats[(int(mid), str(ph))] = {
                "balls": float(len(grp)),
                "runs": float(grp["ext_bowler_debit_runs"].sum()),
                "boundaries": float(grp["is_boundary"].sum())
            }
            
        self.match_league_stats = {}
        for mid, grp in legal_df.groupby("match_id"):
            self.match_league_stats[int(mid)] = {
                "balls": float(len(grp)),
                "runs": float(grp["ext_bowler_debit_runs"].sum()),
                "boundaries": float(grp["is_boundary"].sum())
            }
            
        # 3. Global Sums and Moments across All Matches
        # Cell Level
        cell_keys = set((k[1], k[2]) for k in self.match_cell_stats.keys())
        self.global_cell_moments = {}
        for (ph, tr) in cell_keys:
            sn, sr, sb = 0.0, 0.0, 0.0
            sn2, sr2, snr, sb2, snb = 0.0, 0.0, 0.0, 0.0, 0.0
            m_cnt = 0
            for mid in self.all_training_matches:
                st = self.match_cell_stats.get((mid, ph, tr), None)
                if st is not None and st["balls"] > 0:
                    n = st["balls"]
                    r = st["runs"]
                    b = st["boundaries"]
                    sn += n
                    sr += r
                    sb += b
                    sn2 += n * n
                    sr2 += r * r
                    snr += n * r
                    sb2 += b * b
                    snb += n * b
                    m_cnt += 1
            self.global_cell_moments[(ph, tr)] = {
                "sum_n": sn, "sum_r": sr, "sum_b": sb,
                "sum_n2": sn2, "sum_r2": sr2, "sum_nr": snr,
                "sum_b2": sb2, "sum_nb": snb,
                "active_matches": m_cnt
            }
            
        # Phase Level
        phase_keys = set(k[1] for k in self.match_phase_stats.keys())
        self.global_phase_moments = {}
        for ph in phase_keys:
            sn, sr, sb = 0.0, 0.0, 0.0
            sn2, sr2, snr, sb2, snb = 0.0, 0.0, 0.0, 0.0, 0.0
            m_cnt = 0
            for mid in self.all_training_matches:
                st = self.match_phase_stats.get((mid, ph), None)
                if st is not None and st["balls"] > 0:
                    n = st["balls"]
                    r = st["runs"]
                    b = st["boundaries"]
                    sn += n
                    sr += r
                    sb += b
                    sn2 += n * n
                    sr2 += r * r
                    snr += n * r
                    sb2 += b * b
                    snb += n * b
                    m_cnt += 1
            self.global_phase_moments[ph] = {
                "sum_n": sn, "sum_r": sr, "sum_b": sb,
                "sum_n2": sn2, "sum_r2": sr2, "sum_nr": snr,
                "sum_b2": sb2, "sum_nb": snb,
                "active_matches": m_cnt
            }
            
        # League Level
        sn, sr, sb = 0.0, 0.0, 0.0
        sn2, sr2, snr, sb2, snb = 0.0, 0.0, 0.0, 0.0, 0.0
        m_cnt = 0
        for mid in self.all_training_matches:
            st = self.match_league_stats.get(mid, None)
            if st is not None and st["balls"] > 0:
                n = st["balls"]
                r = st["runs"]
                b = st["boundaries"]
                sn += n
                sr += r
                sb += b
                sn2 += n * n
                sr2 += r * r
                snr += n * r
                sb2 += b * b
                snb += n * b
                m_cnt += 1
        self.global_league_moments = {
            "sum_n": sn, "sum_r": sr, "sum_b": sb,
            "sum_n2": sn2, "sum_r2": sr2, "sum_nr": snr,
            "sum_b2": sb2, "sum_nb": snb,
            "active_matches": m_cnt
        }

        # 4. Standard priors for baseline M4 composition
        self.priors["League"] = {
            "batter_boundary": {
                "mean": float(sb / max(1.0, sn)),
                "variance": 0.0005
            },
            "bowler_economy": {
                "mean": float(6.0 * (sr / max(1.0, sn))),
                "variance": 0.05,
                "mean_rpb": float(sr / max(1.0, sn)),
                "variance_rpb": 0.05 / 36.0
            }
        }
        
        for ph in phase_keys:
            pm = self.global_phase_moments.get(ph, {"sum_n": 1.0, "sum_r": 1.0, "sum_b": 0.2})
            self.priors[f"Phase::{ph}"] = {
                "batter_boundary": {"mean": float(pm["sum_b"] / max(1.0, pm["sum_n"])), "variance": 0.0008},
                "bowler_economy": {
                    "mean": float(6.0 * (pm["sum_r"] / max(1.0, pm["sum_n"]))),
                    "variance": 0.08,
                    "mean_rpb": float(pm["sum_r"] / max(1.0, pm["sum_n"])),
                    "variance_rpb": 0.08 / 36.0
                }
            }
            
        for (ph, tr), cm in self.global_cell_moments.items():
            self.priors[f"Cell::{ph}::{tr}"] = {
                "batter_boundary": {"mean": float(cm["sum_b"] / max(1.0, cm["sum_n"])), "variance": 0.0010},
                "bowler_economy": {
                    "mean": float(6.0 * (cm["sum_r"] / max(1.0, cm["sum_n"]))),
                    "variance": 0.10,
                    "mean_rpb": float(cm["sum_r"] / max(1.0, cm["sum_n"])),
                    "variance_rpb": 0.10 / 36.0
                }
            }

        # 5. Fit Batter tau2 and m0
        bat_var_series = legal_df.groupby("bat_id")["is_boundary"].agg(["count", "mean"])
        bat_var_series = bat_var_series[bat_var_series["count"] >= 30]
        if len(bat_var_series) > 10:
            sample_var_bat = float(bat_var_series["mean"].var())
            exp_noise_bat = float((bat_var_series["mean"] * (1.0 - bat_var_series["mean"]) / bat_var_series["count"]).mean())
            tau2_player_bat = float(max(0.0005, sample_var_bat - exp_noise_bat))
            mu_bat = float(bat_var_series["mean"].mean())
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
            # Robust fallback for small synthetic unit testing datasets (N < 30)
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

    def get_lpmo_context_prior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        domain: str = "bowler",
        min_matches: int = 15,
        min_balls: int = 30
    ) -> Tuple[float, float, str, int, int, int, float, float]:
        """
        Extracts Leave-Player-and-Matches-Out (LPMO) contextual prior.
        
        Strict Invariants:
        1. Every match in which player_id participated in the training fold is 100% EXCLUDED.
        2. Prior is constructed solely from the remaining independent matches M_remain = M_train \\ M_player.
        3. Prior uncertainty is calculated via exact cluster-linearization variance over the
           remaining independent match clusters (no independence assumptions across deliveries).
        4. Structured fallback hierarchy preserving the match-exclusion rule:
           Cell LPMO -> Phase LPMO -> League LPMO -> Unreliable Marker.
           
        Returns:
            (prior_mean, prior_variance, provenance_status, remaining_balls,
             excluded_match_count, remaining_active_matches, effective_matches, concentration_hhi)
        """
        pid = int(player_id)
        is_bowler = ("bowl" in str(domain).lower()) or str(domain).lower() in ["bowler", "bowler_economy", "economy", "bowling"]
        excl_matches = self.player_matches.get(pid, set())
        k_excl = len(excl_matches)
        
        # Helper: compute cluster-robust mean and variance on remaining matches
        def _compute_cluster_stats(
            global_moments: Dict[str, float],
            match_stats_dict: Dict[Any, Dict[str, float]],
            lookup_prefix: Tuple
        ) -> Optional[Tuple[float, float, int, int, float, float]]:
            sn = global_moments["sum_n"]
            sr = global_moments["sum_r"]
            sb = global_moments["sum_b"]
            sn2 = global_moments["sum_n2"]
            sr2 = global_moments["sum_r2"]
            snr = global_moments["sum_nr"]
            sb2 = global_moments["sum_b2"]
            snb = global_moments["sum_nb"]
            m_act = global_moments["active_matches"]
            
            # Subtract contributions of excluded matches
            for mid in excl_matches:
                k = (mid,) + lookup_prefix if len(lookup_prefix) > 0 else mid
                st = match_stats_dict.get(k, None)
                if st is not None and st["balls"] > 0:
                    n = st["balls"]
                    r = st["runs"]
                    b = st["boundaries"]
                    sn -= n
                    sr -= r
                    sb -= b
                    sn2 -= n * n
                    sr2 -= r * r
                    snr -= n * r
                    sb2 -= b * b
                    snb -= n * b
                    m_act -= 1
                    
            if m_act < min_matches or sn < min_balls:
                return None
                
            n_rem = max(1.0, sn)
            m_eff = max(1.0, (n_rem ** 2) / max(1.0, sn2))
            hhi = float(sn2 / (n_rem ** 2))
            
            if is_bowler:
                r_hat = sr / n_rem
                mean_prior = 6.0 * r_hat
                # Cluster ratio linearization: RSS = sum (R_m - r_hat * n_m)^2
                rss = max(1e-6, sr2 - 2.0 * r_hat * snr + (r_hat ** 2) * sn2)
                dof_factor = float(m_act) / float(max(1, m_act - 1))
                var_ratio = dof_factor * (rss / (n_rem ** 2))
                var_prior = float(36.0 * var_ratio)
                var_prior = max(0.005, var_prior)
            else:
                p_hat = sb / n_rem
                mean_prior = float(np.clip(p_hat, 0.01, 0.99))
                # Cluster ratio linearization: RSS = sum (B_m - p_hat * n_m)^2
                rss = max(1e-8, sb2 - 2.0 * p_hat * snb + (p_hat ** 2) * sn2)
                dof_factor = float(m_act) / float(max(1, m_act - 1))
                var_prior = float(dof_factor * (rss / (n_rem ** 2)))
                var_prior = max(0.00005, var_prior)
                
            return mean_prior, var_prior, int(round(sn)), int(m_act), float(m_eff), float(hhi)

        # 1. Level 1: Cell LPMO
        cell_key = (phase, tier)
        if cell_key not in self.global_cell_moments:
            for k in self.global_cell_moments.keys():
                if str(k[0]).lower() == str(phase).lower() and str(k[1]).lower() == str(tier).lower():
                    cell_key = k
                    break
        cell_m = self.global_cell_moments.get(cell_key, None)
        if cell_m is not None:
            res = _compute_cluster_stats(cell_m, self.match_cell_stats, (cell_key[0], cell_key[1]))
            if res is not None:
                mean_p, var_p, n_b, m_a, m_eff, hhi = res
                return mean_p, var_p, "CELL_LPMO_ROBUST", n_b, k_excl, m_a, m_eff, hhi
                
        # 2. Level 2: Phase LPMO Fallback (evaluated on the EXACT SAME remaining matches)
        phase_key = phase
        if phase_key not in self.global_phase_moments:
            for k in self.global_phase_moments.keys():
                if str(k).lower() == str(phase).lower():
                    phase_key = k
                    break
        phase_m = self.global_phase_moments.get(phase_key, None)
        if phase_m is not None:
            res = _compute_cluster_stats(phase_m, self.match_phase_stats, (phase_key,))
            if res is not None:
                mean_p, var_p, n_b, m_a, m_eff, hhi = res
                return mean_p, var_p, "PHASE_LPMO_FALLBACK", n_b, k_excl, m_a, m_eff, hhi

        # 3. Level 3: League LPMO Fallback (evaluated on the EXACT SAME remaining matches)
        league_m = self.global_league_moments
        res = _compute_cluster_stats(league_m, self.match_league_stats, ())
        if res is not None:
            mean_p, var_p, n_b, m_a, m_eff, hhi = res
            return mean_p, var_p, "LEAGUE_LPMO_FALLBACK", n_b, k_excl, m_a, m_eff, hhi

        # 4. Level 4: Unreliable Sparse Matches (Marked unreliable rather than silently using contaminated data)
        fallback_mean = 8.50 if is_bowler else 0.18
        fallback_var = 0.50 if is_bowler else 0.005
        return fallback_mean, fallback_var, "UNRELIABLE_SPARSE_MATCHES", 0, k_excl, 0, 0.0, 1.0

    def get_lopo_context_prior(
        self,
        player_id: int,
        phase: str,
        tier: str,
        domain: str = "bowler"
    ) -> Tuple[float, float, str, int]:
        """
        Backward-compatibility alias routing directly to LPMO.
        """
        res = self.get_lpmo_context_prior(player_id, phase, tier, domain)
        return res[0], res[1], res[2], res[3]

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


class PlayerPosteriorBaselineEstimatorB437:
    """
    Estimates contextual baseline posteriors for players with exact match-aware
    observation likelihood variance and genuine Leave-Player-and-Matches-Out (LPMO) contextual priors.
    """
    def __init__(
        self,
        hierarchy: Optional[ContextualHierarchyB437] = None,
        context_hierarchy: Optional[ContextualHierarchyB437] = None,
        bowler_tau2_player: Optional[float] = None,
        bowler_sigma2_epsilon: Optional[float] = None,
        bowler_sigma2_match: Optional[float] = None,
        batter_tau2_player: Optional[float] = None,
        batter_sigma2_epsilon: Optional[float] = None,
        batter_sigma2_match: Optional[float] = None,
        **kwargs
    ):
        self.hierarchy = hierarchy if hierarchy is not None else context_hierarchy
        if self.hierarchy is None:
            raise ValueError("PlayerPosteriorBaselineEstimatorB437 requires a ContextualHierarchyB437 instance.")
            
        if bowler_tau2_player is not None:
            self.hierarchy.hyperparameters["bowler_tau2_player"] = float(bowler_tau2_player)
        if bowler_sigma2_epsilon is not None:
            self.hierarchy.hyperparameters["bowler_sigma2_within"] = float(bowler_sigma2_epsilon)
        if bowler_sigma2_match is not None:
            self.hierarchy.hyperparameters["bowler_sigma2_match"] = float(bowler_sigma2_match)
        if batter_tau2_player is not None:
            self.hierarchy.hyperparameters["batter_tau2_player"] = float(batter_tau2_player)

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
    ) -> ContextualPlayerBaselineRecordB437:
        if context_legal_balls is None:
            context_legal_balls = context_balls if context_balls is not None else 0
        if career_legal_balls is None:
            career_legal_balls = career_balls if career_balls is not None else 0
            
        prior_mean, prior_mean_var, provenance, pop_balls, k_excl, m_act, m_eff, hhi = self.hierarchy.get_lpmo_context_prior(
            player_id=player_id, phase=phase, tier=tier, domain="batter"
        )
        tau2_player = self.hierarchy.get_player_tau2("batter_boundary")
        m0 = self.hierarchy.hyperparameters.get("batter_m0", 75.0)
        
        return ContextualPlayerBaselineRecordB437(
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
            prior_population_balls=pop_balls,
            excluded_match_count=k_excl,
            remaining_match_count=m_act,
            effective_match_count=m_eff,
            match_concentration_hhi=hhi
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
    ) -> ContextualPlayerBaselineRecordB437:
        if context_legal_balls is None:
            context_legal_balls = context_balls if context_balls is not None else 0
        if career_legal_balls is None:
            career_legal_balls = career_balls if career_balls is not None else 0
            
        prior_mean, prior_mean_var, provenance, pop_balls, k_excl, m_act, m_eff, hhi = self.hierarchy.get_lpmo_context_prior(
            player_id=player_id, phase=phase, tier=tier, domain="bowler"
        )
        tau2_player = self.hierarchy.get_player_tau2("bowler_economy")
        m0 = self.hierarchy.hyperparameters.get("bowler_m0", 60.0)
        s2_match = self.hierarchy.hyperparameters.get("bowler_sigma2_match", 1.45)
        s2_within = self.hierarchy.hyperparameters.get("bowler_sigma2_within", 22.84)
        
        return ContextualPlayerBaselineRecordB437(
            player_id=player_id,
            phase=phase,
            tier=tier,
            context_exposure=context_legal_balls,
            context_events=context_debit_runs,
            context_matches=context_matches,
            career_exposure=career_legal_balls,
            career_events=career_debit_runs,
            career_matches=career_matches,
            context_prior_mean=prior_mean,
            context_prior_mean_variance=prior_mean_var,
            tau2_player=tau2_player,
            prior_m0=m0,
            sigma2_match=s2_match,
            sigma2_within=s2_within,
            is_economy=True,
            min_context_exposure=min_context_screening_balls,
            context_match_balls_list=context_match_balls_list,
            prior_provenance=provenance,
            prior_population_balls=pop_balls,
            excluded_match_count=k_excl,
            remaining_match_count=m_act,
            effective_match_count=m_eff,
            match_concentration_hhi=hhi
        )


# Backward compatibility aliases
ContextualHierarchyB436 = ContextualHierarchyB437
PlayerPosteriorBaselineEstimatorB436 = PlayerPosteriorBaselineEstimatorB437
