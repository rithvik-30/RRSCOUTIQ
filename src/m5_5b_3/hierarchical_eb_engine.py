"""
RR ScoutIQ — Milestone M5.5-B.3: Hierarchical Empirical Bayes Engine
Module: src/m5_5b_3/hierarchical_eb_engine.py

Replaces heuristic N_cell / 500 partial pooling with statistically grounded
Variance-Components Empirical Bayes Shrinkage (James-Stein / empirical Bayes).

Formulation:
Level 1: Context Cell c = (Phase, Pressure Tier)
Level 2: Parent Phase p = Phase (Powerplay, Middle, Death)
Level 3: Global League g

Between-cell variance tau^2 is estimated via DerSimonian-Laird / restricted MML.
Cell shrinkage weight:
w_c = tau^2 / (tau^2 + SE_c^2)
where SE_c^2 = s_c^2 / N_c.
If cell is empty or N_c == 0, w_c = 0.0 (full pooling to phase).
If between-cell variance tau^2 == 0, w_c = 0.0 (homogeneous phase).
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import scipy.special as sp

from src.m5_5b_2.remediation_engine_b2 import (
    kleinman_corrected_mom,
    fit_beta_binomial_mle_safeguarded,
    fit_normal_normal_safeguarded,
    calculate_bowler_economy
)


class VarianceComponentsHierarchicalEngine:
    """
    Fits hierarchical contextual priors strictly from training fold deliveries.
    Evaluates batters and bowlers completely independently.
    """
    def __init__(self):
        self.priors: Dict[str, Dict[str, Any]] = {}
        self.diagnostics: List[Dict[str, Any]] = []

    def fit(self, train_df: pd.DataFrame):
        """
        Fits 3-tier hierarchy:
        1. Global League
        2. Phase (Powerplay, Middle, Death)
        3. Cells (Phase x Pressure Tier)
        """
        df = train_df.copy()
        df["phase"] = df["pre_match_phase"].astype(str)
        df["tier"] = df["pre_pressure_tier"].astype(str)
        df["is_boundary"] = ((df["ext_is_four"] == 1) | (df["ext_is_six"] == 1)).astype(int)
        df["is_dot"] = (df["ext_bowler_debit_runs"] == 0).astype(int)
        df["is_wkt"] = (df["ext_is_bowler_wicket"] == 1).astype(int)
        df["is_legal"] = (df["ext_is_legal_delivery"] == 1).astype(int)
        df["is_dismissal"] = (df["ext_is_wicket"] == 1).astype(int)
        
        # 1. Fit Global League Level
        self._fit_single_population("League", df, level="League")
        
        # 2. Fit Phase Level
        for phase in ["Powerplay", "Middle", "Death"]:
            p_df = df[df["phase"] == phase]
            if len(p_df) > 0:
                self._fit_single_population(f"Phase::{phase}", p_df, level="Phase", parent="League")
                
        # 3. Fit Context Cells with Variance-Components Shrinkage
        for phase in ["Powerplay", "Middle", "Death"]:
            phase_df = df[df["phase"] == phase]
            phase_prior = self.priors.get(f"Phase::{phase}", self.priors["League"])
            
            # Estimate between-cell variance tau^2 across the 4 pressure tiers in this phase
            cell_dfs = {}
            cell_means_bnd = []
            cell_vars_bnd = []
            cell_ns_bnd = []
            
            cell_means_econ = []
            cell_vars_econ = []
            cell_ns_econ = []
            
            for tier in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
                c_df = phase_df[phase_df["tier"] == tier]
                cell_dfs[tier] = c_df
                c_legal = c_df[c_df["is_legal"] == 1]
                
                # Boundary sample stats
                if len(c_legal) > 10:
                    p_hat = c_legal["is_boundary"].mean()
                    s2 = p_hat * (1.0 - p_hat)
                    cell_means_bnd.append(p_hat)
                    cell_vars_bnd.append(s2 / len(c_legal))
                    cell_ns_bnd.append(len(c_legal))
                    
                # Bowler economy sample stats
                if len(c_legal) > 10:
                    econ_stats = calculate_bowler_economy(c_df)
                    cell_means_econ.append(econ_stats["economy_rate"])
                    # Spell level variance proxy ~ 4.0 RPO^2
                    cell_vars_econ.append(4.0 / (econ_stats["legal_balls"] / 6.0))
                    cell_ns_econ.append(econ_stats["legal_balls"])
                    
            # DerSimonian-Laird estimate of between-cell variance tau^2
            tau2_bnd = self._estimate_tau2(cell_means_bnd, cell_vars_bnd)
            tau2_econ = self._estimate_tau2(cell_means_econ, cell_vars_econ)
            
            for tier in ["Tier 1: Low", "Tier 2: Medium", "Tier 3: High", "Tier 4: Extreme"]:
                c_df = cell_dfs[tier]
                c_legal = c_df[c_df["is_legal"] == 1]
                cell_key = f"Cell::{phase}::{tier}"
                
                n_bnd = len(c_legal)
                if n_bnd > 10:
                    p_hat_bnd = c_legal["is_boundary"].mean()
                    se2_bnd = (p_hat_bnd * (1.0 - p_hat_bnd)) / n_bnd
                    w_bnd = tau2_bnd / (tau2_bnd + se2_bnd) if (tau2_bnd + se2_bnd) > 0 else 0.0
                    bnd_shrunk = w_bnd * p_hat_bnd + (1.0 - w_bnd) * phase_prior["batter_boundary"]["mean"]
                else:
                    w_bnd = 0.0
                    bnd_shrunk = phase_prior["batter_boundary"]["mean"]
                    
                n_econ = len(c_legal)
                if n_econ > 10:
                    econ_stats = calculate_bowler_economy(c_df)
                    actual_econ = econ_stats["economy_rate"]
                    se2_econ = 4.0 / max(1.0, econ_stats["legal_balls"] / 6.0)
                    w_econ = tau2_econ / (tau2_econ + se2_econ) if (tau2_econ + se2_econ) > 0 else 0.0
                    econ_shrunk = w_econ * actual_econ + (1.0 - w_econ) * phase_prior["bowler_economy"]["mean"]
                else:
                    w_econ = 0.0
                    econ_shrunk = phase_prior["bowler_economy"]["mean"]
                    
                self.priors[cell_key] = {
                    "phase": phase,
                    "tier": tier,
                    "deliveries": len(c_df),
                    "legal_balls": n_bnd,
                    "batter_boundary": {
                        "mean": float(bnd_shrunk),
                        "tau2_between": float(tau2_bnd),
                        "weight": float(w_bnd),
                        "M0": 100.0
                    },
                    "bowler_economy": {
                        "mean": float(econ_shrunk),
                        "tau2_between": float(tau2_econ),
                        "weight": float(w_econ),
                        "M0": 100.0
                    }
                }
                
                self.diagnostics.append({
                    "key": cell_key,
                    "phase": phase,
                    "tier": tier,
                    "deliveries": len(c_df),
                    "legal_balls": n_bnd,
                    "bnd_mean_shrunk": float(bnd_shrunk),
                    "bnd_tau2": float(tau2_bnd),
                    "bnd_weight": float(w_bnd),
                    "econ_mean_shrunk": float(econ_shrunk),
                    "econ_tau2": float(tau2_econ),
                    "econ_weight": float(w_econ)
                })

    def _estimate_tau2(self, means: List[float], vars_: List[float]) -> float:
        """DerSimonian-Laird estimator for between-group heterogeneity."""
        k = len(means)
        if k < 2:
            return 0.001
        y = np.array(means)
        v = np.array(vars_)
        w = 1.0 / np.maximum(v, 1e-6)
        y_bar = np.sum(w * y) / np.sum(w)
        Q = np.sum(w * (y - y_bar) ** 2)
        denom = np.sum(w) - (np.sum(w ** 2) / np.sum(w))
        if denom <= 0:
            return 0.001
        tau2 = max(0.0001, (Q - (k - 1)) / denom)
        return float(tau2)

    def _fit_single_population(self, key: str, df: pd.DataFrame, level: str, parent: Optional[str] = None):
        legal_df = df[df["is_legal"] == 1]
        
        # Batter Boundary
        p_bnd = legal_df["is_boundary"].mean() if len(legal_df) > 0 else 0.165
        # Bowler Economy (Law-compliant: numerator=all debits, denom=legal)
        econ_stats = calculate_bowler_economy(df)
        econ_rate = econ_stats["economy_rate"] if np.isfinite(econ_stats["economy_rate"]) else 8.45
        
        self.priors[key] = {
            "level": level,
            "deliveries": len(df),
            "legal_balls": len(legal_df),
            "batter_boundary": {"mean": float(p_bnd), "M0": 100.0},
            "bowler_economy": {"mean": float(econ_rate), "M0": 100.0}
        }

    def get_expectation(self, phase: str, tier: str, metric: str) -> float:
        cell_key = f"Cell::{phase}::{tier}"
        if cell_key in self.priors:
            return self.priors[cell_key][metric]["mean"]
        phase_key = f"Phase::{phase}"
        if phase_key in self.priors:
            return self.priors[phase_key][metric]["mean"]
        return self.priors["League"][metric]["mean"]
