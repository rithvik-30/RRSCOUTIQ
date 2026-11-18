# RR ScoutIQ — Comprehensive Statistical Methodology
**Document ID:** METHOD-RR-SCOUTIQ-CORE-V2  
**Project:** Rajasthan Royals SupeRR Selector Season 2 — Competition Submission  
**Scope:** Mathematical Foundations, Estimation Algorithms, and Validation Protocols  
**Verification Date:** November 2026  

---

## 1. Introduction: The Need for Contextual Pressure Evaluation

In modern T20 cricket, traditional metrics such as batting strike rate or bowling economy rate evaluate events in the aggregate without accounting for the game state in which those events occurred. A boundary hit when a team needs 12 runs off 18 balls with 8 wickets in hand is treated identically to a boundary hit needing 18 runs off the final 6 balls against elite death bowling.

RR ScoutIQ establishes a delivery-level Bayesian evaluation system that addresses three foundational challenges:
1. **Dynamic Match Context:** Quantifying the situational leverage of every ball using pre-delivery variables.
2. **Environmental Confounding:** Accounting for unequal match exposure, pitch conditions, phase difficulty, and opposition strength.
3. **Small-Sample Distortion:** Distinguishing genuine player skill from random binomial delivery variance through hierarchical Bayesian shrinkage.

---

## 2. Pre-delivery Match-State Reconstruction

### 2.1 The Shift-1 Anti-Leakage Protocol
To guarantee causal timing and prevent post-hoc bias, the match state for delivery $t$ is reconstructed strictly from information known prior to the bowler releasing the ball:
$$\mathcal{S}_t = f(\{d_1, d_2, \dots, d_{t-1}\})$$
Where $d_k$ represents the complete observed outcome of delivery $k$.

The state representation incorporates:
- $t$: Cumulative legal balls bowled in the innings ($0 \le t \le 120$).
- $B_{\text{rem}}$: Remaining legal balls ($120 - t$, clamped $\ge 1$).
- $W_{\text{lost}}$ and $W_{\text{hand}}$: Wickets fallen ($0 \dots 9$) and wickets remaining ($10 - W_{\text{lost}}$, clamped $\ge 1$).
- $S$: Cumulative runs scored by the batting team prior to ball $t$.
- $\text{CRR}$: Current run rate ($S / (t / 6)$, evaluated for $t \ge 6$).
- $\text{Target}$: Regulation chase target ($S_{\text{Innings 1}} + 1$).
- $\text{RRR}$: Required run rate ($(\text{Target} - S) / (B_{\text{rem}} / 6)$, clamped $\ge 1$ ball remaining).
- Phase: Powerplay (Overs 1–6, $0 \le t \le 35$), Middle (Overs 7–15, $36 \le t \le 89$), Death (Overs 16–20, $90 \le t \le 119$).

### 2.2 Temporal Discipline vs. Causal Inference
The shift-1 sequence strictly prevents future-information leakage: no event resulting from delivery $t$ (such as runs scored, wickets taken, or boundary hits) can enter the match-state representation $\mathcal{S}_t$. While this ensures proper temporal ordering, **temporal sequence alone does not constitute or claim causal inference of player impact.** It simply guarantees that contextual leverage is evaluated strictly from the perspective of the game state before the delivery was bowled.

---

## 3. Dynamic Delivery Leverage Index (DLI)

### 3.1 Definition and Conceptual Scope
The **Dynamic Delivery Leverage Index (DLI)** is the approved **contextual measure of delivery-level match pressure**. It quantifies the operational pressure surrounding each delivery based on required scoring rates, wickets in hand, match phase, and remaining deliveries.

> [!IMPORTANT]
> **Contextual Measure vs. Match Prediction:**
> DLI is strictly a contextual measure of **delivery-level match pressure**, not a direct win-probability estimate or prediction of match outcome. It answers: *"How much pressure surrounds this delivery?"* A match state requiring 14 runs off 3 deliveries has extreme leverage ($\text{DLI} > 2.5$) regardless of whether the batting or bowling team ultimately wins the match.

### 3.2 Mathematical Formulations

#### Innings 2: Chase Leverage
In a run chase, pressure escalates as required run rate diverges from historical par, exacerbated by dwindling wickets and balls:
$$\text{DLI}_{\text{chase}} = \text{Clamp}\left[ \left(\frac{\text{RRR}}{\text{CRR}_{\text{phase}}}\right) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.50} \times \left(1 + \frac{24}{B_{\text{rem}} + 12}\right)^{0.50}, \; 0.10, \; 5.00 \right]$$
Where:
- $\text{CRR}_{\text{phase}}$ represents the historical empirical scoring par: Powerplay = $8.15$ RPO, Middle = $8.00$ RPO, Death = $9.30$ RPO.
- $W_{\text{hand}}$ is clamped $\ge 1$ and $B_{\text{rem}}$ is clamped $\ge 1$.
- Clamping limits the chase DLI strictly to $[0.10, 5.00]$.

#### Innings 1: Setting Leverage
In the first innings, pressure accumulates with time progression, wickets lost, and run-rate stagnation:
$$\text{DLI}_{\text{setting}} = \text{Clamp}\left[ \Phi(t) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.60} \times \left(1 + \max\left(0, \; \frac{\text{CRR}_{\text{phase}} - \text{CRR}}{6}\right)\right)^{0.50}, \; 0.20, \; 3.50 \right]$$
Where:
- $\Phi(t) = 0.80 + 0.70 \times (t / 120)^{1.20}$ models continuous baseline pressure growth as the first innings progresses.
- The wicket sensitivity exponent ($0.60$) is higher than in chases ($0.50$) because early wickets in Innings 1 severely compromise the batting team's ability to attack at the death.
- The stagnation penalty term $\max\left(0, \frac{\text{CRR}_{\text{phase}} - \text{CRR}}{6}\right)$ is active for $t \ge 6$ (defined as $0$ for $t < 6$), measuring the cumulative scoring slowdown relative to empirical phase par $\text{CRR}_{\text{phase}}$.
- Clamping limits the setting DLI strictly to $[0.20, 3.50]$.

#### Super Over:
Fixed by tournament rule at $\text{DLI} = 3.50$.

---

## 4. The Four Operational Leverage Tiers

Continuous DLI values map into four operational tiers:
- **Tier 1: Low Pressure ($\text{DLI} < 0.90$):** Uncontested, low-stakes game states. Serves as the player's **normal performance baseline**.
- **Tier 2: Medium Pressure ($0.90 \le \text{DLI} < 1.35$):** Standard competitive match play.
- **Tier 3: High Pressure ($1.35 \le \text{DLI} < 2.25$):** High-leverage junctures (wickets cluster, phase transitions, death defense).
- **Tier 4: Extreme Pressure ($\text{DLI} \ge 2.25$):** Terminal crunch time (final overs, narrow-margin chases).
- **Combined Pressure (Tiers 2–4, $\text{DLI} \ge 0.90$):** Evaluates all deliveries contested under elevated leverage.
- **High Pressure (Tiers 3–4, $\text{DLI} \ge 1.35$):** Isolates the top quintile of elevated match moments.

---

## 5. Discipline-Specific Performance Evaluation

Batting and bowling evaluate fundamentally distinct skills under pressure and are analyzed independently:

### 5.1 Batting: Contextual Batting Value-Add
- The primary batter ranking metric is the conservative lower credible bound of contextual batting value-add:
  $$\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$$
- The outcome of delivery $t$ for batter $i$ is modeled against the Leave-Player-and-Matches-Out (LPMO) baseline expectation $\mu_{\text{phase}(t), \text{tier}(t)}$.
- The Empirical Bayes posterior point estimate is:
  $$\Delta_{\text{EB}} = \mathbb{E}[\hat{\theta}_{i, \text{pressure}} - \mu_{\text{context, pressure}}]$$
- **Statistical Confirmation vs. Relative Leaders:**
  - Only three batters possess positive lower bounds ($\text{LB}_{90\% \text{ CI}} > 0$): **Abhishek Sharma (+2.72%)**, **Suryakumar Yadav (+1.05%)**, and **Vaibhav Sooryavanshi (+0.78%)**. These three are confirmed positive contextual batting value-add performers.
  - The other seven batters (Finn Allen through Andre Russell) are included on relative ranking merit within the qualified cohort; their lower bounds cross zero.
- **Supporting Evidence Role:** Raw observed metrics—boundary percentage, pressure strike rate ($SR_{T2-T4}$), and dot-ball percentage—serve as valuable supporting empirical evidence across leverage tiers, but do not substitute for the primary contextual estimate $\Delta_{\text{EB}}$ and its credible bound $\text{LB}_{90\% \text{ CI}}$.
- **Ranking Logic:** Batters are ranked in descending order of their conservative lower bound ($\text{LB}_{90\% \text{ CI}}$).

### 5.2 Bowling: Contextual Economy Suppression
- The primary bowler ranking metric is the conservative upper credible bound of contextual economy delta:
  $$\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$$
  *(Lower values are superior; negative delta indicates runs saved relative to context).*
- The expected contextual economy baseline is established via the LPMO model: $\mathbb{E}[R_{jt}] = R_{\text{context, pressure}}$.
- The bowler's contextual economy delta is:
  $$\Delta_{\text{EB}} = \mathbb{E}[\hat{\theta}_{j, \text{pressure}} - R_{\text{context, pressure}}]$$
- **Statistical Status:** All ten selected bowlers are relative leaders within the eligible pool. Because death bowling involves high-variance run volatility, zero shortlisted bowlers have an upper bound below zero ($\text{UB}_{90\% \text{ CI}}$ ranges from $+0.296$ to $+0.697$ RPO). Therefore, none of the ten is described as a statistically confirmed economy suppressor below contextual baseline; they represent the strongest relative suppressors in the canonical database.
- **Combined Pressure vs. Tier 4 Distinction:** The framework strictly distinguishes performance across delivery subsets:
  - **Combined Pressure (T2–T4):** Evaluates all deliveries bowled under $\text{DLI} \ge 0.90$ (e.g., Sunil Narine: 1,394 balls, 6.63 RPO economy).
  - **Extreme Crunch (Tier 4):** Isolates terminal pressure deliveries under $\text{DLI} \ge 2.25$ (e.g., Sunil Narine: 158 balls, 5.85 RPO economy).
- **Ranking Logic:** Bowlers are ranked in ascending order of their conservative upper bound ($\text{UB}_{90\% \text{ CI}}$).

---

## 6. Hierarchical Empirical Bayes Estimation

### 6.1 Leave-Player-and-Matches-Out (LPMO) Benchmarking
To prevent data leakage, when estimating the contextual baseline expectation for player $i$, all deliveries from matches in which player $i$ participated are excluded from the training split. This guarantees that environmental factors or dominant individual displays do not contaminate the benchmark.

### 6.2 Crossed-Effects Variance Decomposition
Raw observed performances conflate player talent with match-level environmental variance (pitch conditions, weather, boundary dimensions) and delivery-level noise:
$$\text{Var}(\text{Observed}) = \tau_{\text{player}}^2 + \sigma_{\text{match}}^2 + \sigma_{\text{noise}}^2$$
Our hierarchical model residualizes fixed contextual effects (match phase, pressure tier, innings type) and partitions random components using iterative least-squares and residual variance decomposition.

### 6.3 Bayesian Shrinkage
The Empirical Bayes estimator shrinks raw observed performance toward the contextual prior:
$$\hat{\theta}_i = \lambda_i \bar{y}_i + (1 - \lambda_i) \mu_{\text{context}}$$
Where the shrinkage weight is:
$$\lambda_i = \frac{\tau^2}{\tau^2 + \text{SE}_i^2}$$
Players with high exposure and consistent evidence retain their observed performance ($\lambda_i \to 1$), while players with limited exposure or high variance shrink toward the contextual baseline ($\lambda_i \to 0$).

---

## 7. Statistical Uncertainty & The 1.645 Multiplier

### 7.1 Mathematical Definition of Ranking Bounds
Under our approved statistical sign-off convention (`FINAL_STATISTICAL_SIGNOFF.md`), rankings are based on the **conservative endpoint of the 90% two-sided credible interval, which is mathematically equivalent to a 95% one-sided credible bound under the Gaussian posterior convention** using standard normal multiplier $Z = 1.645$:
- **Batters:** $\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$ serves as the 95% one-sided lower posterior credible bound for contextual batting value-add under the Gaussian posterior convention ($Z = 1.645$). Batters rank in descending order.
- **Bowlers:** $\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$ serves as the 95% one-sided upper posterior credible bound for contextual economy delta under the Gaussian posterior convention ($Z = 1.645$). Bowlers rank in ascending order (lower economy indicates superior run prevention).

### 7.2 Why Conservative Bounds are Necessary
Ranking by point estimates ($\Delta_{\text{EB}}$) rewards high-variance volatility. Ranking by conservative credible bounds ensures that a player must demonstrate both **high performance** and **sufficient evidence** to achieve a high rank.

---

## 8. Eligibility Criteria & Cohort Selection

Candidates are evaluated against three pre-ranking filters:
1. **Career Exposure:** $\ge 500$ career legal deliveries faced (batters) or bowled (bowlers).
2. **Pressure Exposure:** $\ge 100$ legal deliveries faced or bowled under elevated leverage ($\text{DLI} \ge 0.90$).
3. **Epistemic Standard Error:** $se_{\text{latent}} \le 0.035$ for batters; $se_{\text{latent}} \le 0.65$ RPO for bowlers.

*Historical Origin Note:* The 500-ball filter was established during shortlist construction from empirical sensitivity analysis to ensure parameter stability. It was not pre-specified in the earlier pilot milestone.

---

## 9. Transparent Limitations & Statistical Disclosures

In compliance with rigorous sports analytics governance, the model's limitations are explicitly disclosed:

1. **Batter Statistical Confidence:** Only 3 of the 10 batters (**Abhishek Sharma**, **Suryakumar Yadav**, **Vaibhav Sooryavanshi**) possess positive lower bounds ($\text{LB}_{90\% \text{ CI}} > 0$). The remaining 7 batters are included on relative ranking merit within the eligible cohort; their credible intervals cross zero, meaning their positive value-add does not establish a positive 95% one-sided lower posterior credible bound for contextual batting value-add.
2. **Bowler Statistical Confidence:** Zero bowlers possess negative upper bounds ($\text{UB}_{90\% \text{ CI}} < 0$). All 10 bowlers have positive upper bounds ($+0.296$ to $+0.697$ RPO). They represent the strongest relative suppressors in the database, but economy suppression below context is not established under a negative 95% one-sided upper posterior credible bound for contextual economy delta.
3. **Tier 4 Exposure Flags:** Four top batters (**Vaibhav Sooryavanshi**, **Finn Allen**, **Travis Head**, **Yashasvi Jaiswal**) have **exactly 0 Tier 4 deliveries**. Their pressure ratings reflect performance in Tier 2 and Tier 3. Extreme-pressure crunch execution cannot be statistically asserted for them.
4. **Dataset Provenance & Scope:** The evaluation is conducted across **744 clean modeling matches across IPL, T20I and regional T20 cricket, comprising 168,104 clean legal deliveries** (362 IPL matches [48.66%], 381 T20I matches [51.21%], 1 regional T20 match [0.13%], from 776 canonical fixtures). Results reflect integrated elite T20 performance and are not IPL-only.
5. **Predictive Scope:** The model evaluates relative historical performance under conservative Bayesian shrinkage. It does not provide deterministic guarantees of future performance.
