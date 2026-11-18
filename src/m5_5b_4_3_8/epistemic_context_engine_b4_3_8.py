"""
RR ScoutIQ — Milestone M5.5-B.4.3.8: Coherent Bayesian Epistemic & Posterior Uncertainty Engine
Module: src/m5_5b_4_3_8/epistemic_context_engine_b4_3_8.py

Final Statistical Foundation:
1. Full Joint Conjugate Gaussian Bayesian Model with Leave-Player-and-Matches-Out (LPMO) priors:
   Prior on theta_i before observing Y_{i, c}:
     theta_i ~ N(mu_LPMO, tau2_total) where tau2_total = tau2_player + sigma2_mu_LPMO
   Likelihood:
     Y_{i, c} | theta_i ~ N(theta_i, V_{i, c})
   Bayesian Posterior Distribution:
     lambda_bayes = tau2_total / (tau2_total + V_{i, c})
     posterior_mean = lambda_bayes * Y_{i, c} + (1 - lambda_bayes) * mu_LPMO
     posterior_variance = (tau2_total * V_{i, c}) / (tau2_total + V_{i, c}) = (1 - lambda_bayes) * tau2_total

2. Cluster-Aware Likelihood for Both Domains:
   - Bowler (Economy RPO scale):
     V_{i, c} = (6.0 * sigma2_within / n_ctx) + H_{i, c} * sigma2_match
   - Batter (Boundary% Probability scale [0, 1]):
     Empirically verified residual match clustering (ANOVA F=2.1155, p < 1e-60, ICC=0.00495):
     V_{i, c} = (p_obs * (1 - p_obs) / n_ctx) + H_{i, c} * sigma2_match_batter
     where sigma2_match_batter = 0.00075 is on the true probability scale (no RPO parameter contamination).

3. Strict Separation of Bayesian Posterior Variance from Frequentist Estimator MSE:
   - posterior_variance: True conditional variance Var(theta_i | Y_{i, c}, mu_LPMO) = (1 - lambda_bayes) * tau2_total
   - frequentist_estimator_mse: E[(hat_theta - theta)^2] = (1 - lambda_plugin)^2 * tau2_player + lambda_plugin^2 * V + (1 - lambda_plugin)^2 * sigma2_mu_LPMO

4. Correct Asymptotics & Finite Exposure Floors:
   - Fixed matches M with n -> infinity: V_{i, c} -> H * sigma2_match > 0.
     Match shock prevents observation variance and posterior variance from collapsing to zero.
   - Increasing matches M -> infinity with n -> infinity: V_{i, c} -> 0, posterior variance -> 0.

5. Coherent Posterior Predictive Variance Without Double Counting:
   Var(Y_new | data) = posterior_variance + sigma2_match + sigma2_within_eval
   Prior uncertainty enters strictly through posterior_variance.

6. LPMO Provenance & Match Audit:
   Stores excluded_match_count, remaining_match_count, effective_match_count, and match_concentration_hhi.
"""

import math
from enum import Enum
from typing import Dict, Any, Optional, Union, Tuple, List
import numpy as np


class EpistemicStateB438(Enum):
    ZERO_CAREER_EXPOSURE = "ZERO_CAREER_EXPOSURE"
    ZERO_CONTEXT_EXPOSURE = "ZERO_CONTEXT_EXPOSURE"
    MISSING_OUTCOME = "MISSING_OUTCOME"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VALID_CONTEXT_OBSERVATION = "VALID_CONTEXT_OBSERVATION"
    INVALID_EXPOSURE = "INVALID_EXPOSURE"

# Backward compatibility aliases
EpistemicStateB437 = EpistemicStateB438
EpistemicStateB436 = EpistemicStateB438


class ContextualPlayerBaselineRecordB438:
    """
    Encapsulates a player's context-consistent Bayesian posterior baseline under the
    Joint Conjugate Gaussian model using Leave-Player-and-Matches-Out (LPMO) contextual priors
    and cluster-aware likelihood observation variance.
    """
    def __init__(
        self,
        player_id: int,
        phase: str,
        tier: str,
        context_exposure: Union[int, float],
        context_events: Optional[Union[int, float]],
        context_matches: int,
        career_exposure: int,
        career_events: Optional[Union[int, float]],
        career_matches: int,
        context_prior_mean: float,
        player_heterogeneity_tau2: Optional[float] = None,
        prior_m0: float = 100.0,
        is_economy: bool = False,
        min_context_exposure: int = 30,
        tau2_player: Optional[float] = None,
        context_prior_mean_variance: float = 0.0001,
        sigma2_match: float = 1.45,
        sigma2_within: float = 22.84,
        sigma2_match_batter: float = 0.00075,
        context_match_balls_list: Optional[List[int]] = None,
        match_balls_list: Optional[List[int]] = None,
        prior_provenance: str = "CELL_LPMO_ROBUST",
        prior_population_balls: int = 0,
        excluded_match_count: int = 0,
        remaining_match_count: int = 0,
        effective_match_count: float = 0.0,
        match_concentration_hhi: float = 0.0,
        **kwargs
    ):
        self.player_id = int(player_id)
        self.phase = str(phase)
        self.tier = str(tier)
        self.context_exposure = context_exposure
        self.context_events = context_events
        self.context_matches = int(context_matches)
        self.career_exposure = int(career_exposure)
        self.career_events = career_events
        self.career_matches = int(career_matches)
        self.context_prior_mean = float(context_prior_mean)
        tau2_val = player_heterogeneity_tau2 if player_heterogeneity_tau2 is not None else (tau2_player if tau2_player is not None else (0.465 if is_economy else 0.002))
        self.tau2_player = float(max(1e-6, tau2_val))
        self.prior_m0 = float(max(1.0, prior_m0))
        self.is_economy = bool(is_economy)
        self.min_context_exposure = int(min_context_exposure)
        self.context_prior_mean_variance = float(max(0.0, context_prior_mean_variance))
        self.population_mean_sampling_variance = self.context_prior_mean_variance
        
        # Total marginal prior variance for player i: tau2_total = tau2_player + sigma2_mu_LPMO
        self.tau2_total = float(self.tau2_player + self.context_prior_mean_variance)
        
        # Rigorous crossed-effects variance components
        self.sigma2_within = float(max(0.001, sigma2_within))
        self.sigma2_match = float(max(0.0, sigma2_match))
        if not self.is_economy:
            if sigma2_match_batter != 0.00075:
                self.sigma2_match_batter = float(max(0.0, sigma2_match_batter))
            elif sigma2_match != 1.45:
                self.sigma2_match_batter = float(max(0.0, sigma2_match))
            else:
                self.sigma2_match_batter = float(max(0.0, sigma2_match_batter))
        else:
            self.sigma2_match_batter = float(max(0.0, sigma2_match_batter))
            
        self.context_match_balls_list = context_match_balls_list if context_match_balls_list is not None else match_balls_list
        self.prior_provenance = str(prior_provenance)
        self.prior_population_balls = int(prior_population_balls)
        
        # LPMO Match-Exclusion Audit Metadata
        self.excluded_match_count = int(excluded_match_count)
        self.remaining_match_count = int(remaining_match_count)
        self.effective_match_count = float(effective_match_count)
        self.match_concentration_hhi = float(match_concentration_hhi)
        
        self._classify_and_shrink()

    def _calculate_match_herfindahl(self, n_ctx: int) -> float:
        """
        Calculates the Herfindahl-Hirschman match exposure concentration:
            H = sum_m (n_{im} / n_{i, c})^2
        """
        if self.context_match_balls_list is not None and len(self.context_match_balls_list) > 0:
            arr = np.array(self.context_match_balls_list, dtype=float)
            total = float(np.sum(arr))
            if total > 0:
                return float(np.sum((arr / total) ** 2))
                
        # If match-level breakdown is not provided, use uniform split across context_matches
        n_m = max(1, self.context_matches)
        return float(1.0 / float(n_m))

    def _classify_and_shrink(self):
        # 1. Invalid exposure
        if (
            self.context_exposure is None or
            (isinstance(self.context_exposure, float) and np.isnan(self.context_exposure)) or
            self.context_exposure < 0 or
            not np.isfinite(self.context_exposure)
        ):
            self.state = EpistemicStateB438.INVALID_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = np.nan
            self.frequentist_mse = np.nan
            self.latent_se = np.nan
            self.eligibility_status = "ERROR_INVALID_EXPOSURE"
            return
            
        n_ctx = int(self.context_exposure)
        
        # 2. Zero career exposure
        if self.career_exposure <= 0:
            self.state = EpistemicStateB438.ZERO_CAREER_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = self.tau2_total
            self.frequentist_mse = self.tau2_total
            self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
            self.eligibility_status = "INELIGIBLE_ZERO_CAREER_EXPOSURE"
            return
            
        # 3. Zero context exposure (career > 0, but no deliveries in this specific context)
        if n_ctx == 0:
            self.state = EpistemicStateB438.ZERO_CONTEXT_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = self.tau2_total
            self.frequentist_mse = self.tau2_total
            self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
            self.eligibility_status = "FALLBACK_ZERO_CONTEXT_EXPOSURE"
            return
            
        # 4. Missing outcome in context
        if (
            self.context_events is None or
            (isinstance(self.context_events, float) and np.isnan(self.context_events)) or
            not np.isfinite(self.context_events)
        ):
            self.state = EpistemicStateB438.MISSING_OUTCOME
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = self.tau2_total
            self.frequentist_mse = self.tau2_total
            self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
            self.eligibility_status = "CORRUPTED_MISSING_OUTCOME"
            return
            
        # 5. Positive context exposure with valid observation
        events_float = float(self.context_events)
        self.match_herfindahl = self._calculate_match_herfindahl(n_ctx)
        
        if self.is_economy:
            # Bowler economy in RPO
            self.observed_context_rate = 6.0 * (events_float / float(n_ctx))
            
            # Exact Likelihood observation variance:
            # V_{i, c} = (6.0 * sigma2_within / n_ctx) + H_{i, c} * sigma2_match
            self.var_observation = (6.0 * self.sigma2_within / float(n_ctx)) + (self.match_herfindahl * self.sigma2_match)
            
            # Full Joint Conjugate Bayesian Shrinkage Weight:
            # lambda_bayes = tau2_total / (tau2_total + V_{i, c})
            self.shrinkage_weight = float(self.tau2_total / (self.tau2_total + self.var_observation))
            
            # Plug-in shrinkage weight for frequentist MSE comparison:
            self.lambda_plugin = float(self.tau2_player / (self.tau2_player + self.var_observation))
            self.effective_m0 = float((self.var_observation / self.tau2_player) * float(n_ctx))
        else:
            # Batter Boundary% proportion
            self.observed_context_rate = events_float / float(n_ctx)
            p_obs = float(np.clip(self.observed_context_rate, 0.02, 0.98))
            
            # Cluster-aware batter observation variance on probability scale:
            # V_{i, c} = (p_obs * (1.0 - p_obs) / n_ctx) + H_{i, c} * sigma2_match_batter
            v_sampling = (p_obs * (1.0 - p_obs)) / float(n_ctx)
            v_match_cluster = self.match_herfindahl * self.sigma2_match_batter
            self.var_observation = float(v_sampling + v_match_cluster)
            
            # Full Joint Conjugate Bayesian Shrinkage Weight:
            self.shrinkage_weight = float(self.tau2_total / (self.tau2_total + self.var_observation))
            
            # Plug-in shrinkage weight for frequentist MSE comparison:
            self.lambda_plugin = float(self.tau2_player / (self.tau2_player + self.var_observation))
            self.effective_m0 = float((self.var_observation / max(1e-6, self.tau2_player)) * float(n_ctx))
            
        self.has_observed_rate = True
        
        # Bayesian Posterior Mean:
        # hat_theta = lambda_bayes * Y_obs + (1 - lambda_bayes) * mu_LPMO
        self.shrunk_estimate = (
            self.shrinkage_weight * self.observed_context_rate +
            (1.0 - self.shrinkage_weight) * self.context_prior_mean
        )
        
        # 1. Full Joint Conjugate Bayesian Posterior Variance:
        # Var(theta_i | Y_{i, c}, mu_LPMO) = (tau2_total * V_{i, c}) / (tau2_total + V_{i, c}) = (1 - lambda_bayes) * tau2_total
        self.latent_posterior_variance = float(
            (1.0 - self.shrinkage_weight) * self.tau2_total
        )
        self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
        
        # 2. Frequentist Estimator MSE of two-stage plug-in estimator:
        # MSE = (1 - lambda_plugin)^2 * tau2_player + lambda_plugin^2 * V + (1 - lambda_plugin)^2 * sigma2_mu_LPMO
        w_plugin = 1.0 - self.lambda_plugin
        self.frequentist_mse = float(
            (w_plugin ** 2) * self.tau2_player + (self.lambda_plugin ** 2) * self.var_observation + (w_plugin ** 2) * self.context_prior_mean_variance
        )
        
        if n_ctx < self.min_context_exposure:
            self.state = EpistemicStateB438.INSUFFICIENT_EVIDENCE
            self.eligibility_status = "SCREENED_INSUFFICIENT_SAMPLE"
        else:
            self.state = EpistemicStateB438.VALID_CONTEXT_OBSERVATION
            self.eligibility_status = "ELIGIBLE_ROBUST_OBSERVATION"

    @property
    def shrunk_baseline(self) -> float:
        return self.shrunk_estimate

    @property
    def posterior_mean(self) -> float:
        return self.shrunk_estimate

    @property
    def posterior_variance(self) -> float:
        return self.latent_posterior_variance

    @property
    def posterior_variance_latent(self) -> float:
        return self.latent_posterior_variance

    @property
    def latent_variance(self) -> float:
        return self.latent_posterior_variance

    @property
    def context_observation_variance(self) -> float:
        return self.var_observation

    @property
    def frequentist_plugin_mse(self) -> float:
        return self.frequentist_mse

    @property
    def standard_error(self) -> float:
        return self.latent_se

    def get_predictive_variance(self, n_eval: Union[int, float] = 6) -> float:
        """
        Computes posterior predictive variance for a held-out observation with exposure n_eval.
        """
        n_e = max(1.0, float(n_eval))
        if self.is_economy:
            var_within = (self.sigma2_within * 6.0) / n_e
            return float(self.latent_posterior_variance + self.sigma2_match + var_within)
        else:
            p = float(np.clip(self.shrunk_estimate, 0.01, 0.99))
            var_within = (p * (1.0 - p)) / n_e
            return float(self.latent_posterior_variance + self.sigma2_match_batter + var_within)

    def get_predictive_se(self, n_eval: Union[int, float] = 6) -> float:
        return float(math.sqrt(max(1e-8, self.get_predictive_variance(n_eval))))

    def get_predictive_variance_breakdown(self, n_eval: Union[int, float] = 6) -> Dict[str, float]:
        """
        Returns an exhaustive breakdown of distinct variance components without double counting.
        """
        n_e = max(1.0, float(n_eval))
        if self.is_economy:
            v_match = float(self.sigma2_match)
            v_within = float((self.sigma2_within * 6.0) / n_e)
        else:
            p = float(np.clip(self.shrunk_estimate, 0.01, 0.99))
            v_match = float(self.sigma2_match_batter)
            v_within = float((p * (1.0 - p)) / n_e)
            
        v_latent_post = float(self.latent_posterior_variance)
        v_total_pred = float(v_latent_post + v_match + v_within)
        
        # Breakdown of marginal prior components:
        w_bayes = 1.0 - self.shrinkage_weight
        v_prior_player = float(w_bayes * self.tau2_player)
        v_prior_context = float(w_bayes * self.context_prior_mean_variance)
        
        return {
            "prior_player_component": v_prior_player,
            "prior_context_component": v_prior_context,
            "latent_posterior_variance": v_latent_post,
            "frequentist_estimator_mse": float(self.frequentist_mse),
            "match_environmental_variance": v_match,
            "within_sampling_variance": v_within,
            "total_predictive_variance": v_total_pred,
            "predictive_se": math.sqrt(max(1e-8, v_total_pred))
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "phase": self.phase,
            "tier": self.tier,
            "context_exposure": self.context_exposure,
            "context_events": self.context_events,
            "context_matches": self.context_matches,
            "career_exposure": self.career_exposure,
            "career_matches": self.career_matches,
            "state": self.state.value,
            "has_observed_rate": self.has_observed_rate,
            "observed_context_rate": self.observed_context_rate,
            "context_prior_mean": self.context_prior_mean,
            "context_prior_mean_variance": self.context_prior_mean_variance,
            "tau2_player": self.tau2_player,
            "tau2_total": self.tau2_total,
            "shrinkage_weight": self.shrinkage_weight,
            "shrunk_estimate": self.shrunk_estimate,
            "latent_posterior_variance": self.latent_posterior_variance,
            "latent_se": self.latent_se,
            "frequentist_mse": self.frequentist_mse,
            "var_observation": self.var_observation,
            "match_herfindahl": self.match_herfindahl,
            "prior_provenance": self.prior_provenance,
            "prior_population_balls": self.prior_population_balls,
            "excluded_match_count": self.excluded_match_count,
            "remaining_match_count": self.remaining_match_count,
            "effective_match_count": self.effective_match_count,
            "match_concentration_hhi": self.match_concentration_hhi,
            "eligibility_status": self.eligibility_status
        }


# Backward compatibility aliases
ContextualPlayerBaselineRecordB437 = ContextualPlayerBaselineRecordB438
ContextualPlayerBaselineRecordB436 = ContextualPlayerBaselineRecordB438
