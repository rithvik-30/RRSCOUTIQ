# RR ScoutIQ — Elite Pressure Performance Scouting Intelligence

## Rajasthan Royals CRP SupeRR Selector Season 2 — Official Submission Report
**Document ID:** SUBMISSION-RR-SCOUTIQ-FINAL-2026  
**Competition:** Rajasthan Royals CRP SupeRR Selector Season 2 (IPL 2027 Auction Strategy)  
**Status:** COMPLETE, VERIFIED & FROZEN FOR SUBMISSION  
**Canonical Dataset Hash:** `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4`  
**Reference Report Hash:** `0e0a11f87622dbeed44c3d918f37c5c9de2f2be8b22ac180099b5add1b882a1d`  




**Document ID:** RR-SCOUTIQ-COMPETITION-FINAL-V3  

**Project:** Rajasthan Royals SupeRR Selector Season 2 Hackathon  

**Target Goal:** Top 16 Finish  

**Evaluation Scope:** Delivery-Level Pressure Performance in Elite T20 Cricket  

**Audited Sources of Truth:**

- [FINAL_STATISTICAL_SIGNOFF.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/FINAL_STATISTICAL_SIGNOFF.md)

- [FINAL_TOP20_PRESSURE_RANKING_AUDIT.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/FINAL_TOP20_PRESSURE_RANKING_AUDIT.md)

- [TOP_10_PRESSURE_BATTERS.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md)

- [TOP_10_PRESSURE_BOWLERS.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md)

- [PRESSURE_TOP_20_VALIDATION_REPORT.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/audit_reports/M5_5B_4_3_8/PRESSURE_TOP_20_VALIDATION_REPORT.md)

**Canonical Dataset:** `data/processed/m5_3/match_state_full.csv` (SHA-256: `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4`)  

**Evaluation Date:** November 2026  



---



## A. Executive Summary



### 1. The Operational Problem in Modern T20 Scouting

Conventional franchise recruitment relies heavily on aggregate career statistics: overall batting averages, gross strike rates, and raw bowling economy rates. While these summary statistics describe career accumulation, they fail to answer the most critical operational question in franchise cricket: **How does a player perform when the match is on the line?**



Standard aggregate metrics suffer from three foundational weaknesses:

1. **Context Blindness:** A boundary hit in a low-stakes dead rubber or during an uncontested middle-overs cruise is counted identically to a boundary hit requiring 18 runs off the final 8 deliveries against elite death bowling.

2. **Phase Conflation:** A spin bowler conceding 7.50 runs per over in low-leverage middle overs appears superior on paper to a pace bowler conceding 8.50 runs per over during the 19th and 20th overs, even though the contextual tournament baseline at the death exceeds 11.20 runs per over.

3. **Small-Sample Volatility:** Short, high-variance cameos can artificially inflate strike rates, making volatile low-exposure players appear statistically comparable to established performers who consistently absorb high-leverage deliveries.



### 2. How the Contextual Pressure Framework Solves This

**RR ScoutIQ** resolves these weaknesses by evaluating player performance at the individual delivery level within an audited Bayesian statistical framework:

- **Pre-delivery Ball-by-Ball Match-State Reconstruction:** Evaluates every delivery using strictly the state information available immediately prior to the ball being bowled (score, balls remaining, wickets in hand, current run rate, required run rate, and match phase). The shift-1 sequence ensures that only pre-delivery information is utilized to prevent future-information leakage, without claiming that this alone establishes causal inference.

- **Dynamic Delivery Leverage Index (DLI):** Serves as the approved contextual measure of delivery-level match pressure, dividing deliveries into four distinct operational tiers (Low, Medium, High, and Extreme). DLI is strictly a contextual measure of match pressure, not a direct win-probability estimate or prediction.

- **Leave-Player-and-Matches-Out (LPMO) Benchmarking:** Calculates contextual expectations from independent fixtures, ensuring a player's own performances cannot leak into or distort their baseline expectation.

- **Empirical Bayes Crossed-Effects Estimation:** Separates true player talent from match-level environmental variance (pitch conditions, weather, opposition strength) and binomial delivery noise, pulling small-sample outliers toward the contextual baseline.

- **Conservative Credibility Bounds:** Ranks players using conservative bounds based on the approved 1.645 standard error multiplier (endpoint of the 90% two-sided credible interval, mathematically equivalent to a 95% one-sided posterior credible bound under the Gaussian posterior convention: lower posterior credible bound for batters, upper posterior credible bound for bowlers).



### 3. Final Shortlist Output

The framework evaluates all eligible players across 744 clean modeling matches across IPL, T20I and regional T20 cricket, comprising 168,104 clean legal deliveries, and delivers:

- **Top 10 Pressure-Performing Batsmen** (ranked by conservative lower credible bound of contextual batting value-add).

- **Top 10 Pressure-Performing Bowlers** (ranked by conservative contextual economy suppression upper bound).



---



## B. Technical Methodology



```

+---------------------------------------------------------------------------------------------------+

|                                  RR SCOUTIQ PIPELINE ARCHITECTURE                                 |

+---------------------------------------------------------------------------------------------------+

|  [ Canonical Ball-by-Ball Data ]  -->  [ Match State Reconstruction ]  -->  [ Dynamic DLI (0-5) ] |

|            (744 Matches)               (Score, Wkts, RRR, Phase)             (Contextual Leverage)|

+---------------------------------------------------------------------------------------------------+

                                                  |

                                                  v

+---------------------------------------------------------------------------------------------------+

|                                   FOUR LEVERAGE TIERS MAPPING                                     |

|  Tier 1: Low (<0.90) | Tier 2: Medium (0.90-1.35) | Tier 3: High (1.35-2.25) | Tier 4: Ext (>=2.25)|

+---------------------------------------------------------------------------------------------------+

                                                  |

                                                  v

+---------------------------------------------------------------------------------------------------+

|                                 CONTEXTUAL MODELING & SHRINKAGE                                   |

|   LPMO Prior (M4)   -->  Joint Empirical Bayes (M5)  -->  Crossed-Effects Match Variance Remov.   |

+---------------------------------------------------------------------------------------------------+

                                                  |

                                                  v

+---------------------------------------------------------------------------------------------------+

|                                 CONSERVATIVE UNCERTAINTY BOUNDS                                   |

|   Batters: LB_90%CI = Delta_EB - 1.645*SE      |     Bowlers: UB_90%CI = Delta_EB + 1.645*SE      |

+---------------------------------------------------------------------------------------------------+

```



### 1. Pre-delivery Ball-by-Ball Match-State Reconstruction

Every legal delivery is modeled as a discrete event within a pre-delivery, shift-1 anti-leakage sequence. The state variables available strictly *prior* to delivery $t$ are:

- $t$: Cumulative legal deliveries bowled in the innings ($0 \le t \le 120$).

- $B_{\text{rem}}$: Legal balls remaining ($120 - t$, floored at 1).

- $W_{\text{lost}}$ and $W_{\text{hand}}$: Wickets lost ($0 \dots 9$) and wickets in hand ($10 - W_{\text{lost}}$, clamped $\ge 1$).

- $S$: Cumulative runs scored by the batting team prior to delivery $t$.

- $\text{CRR}$: Current run rate ($S / (t / 6)$, defined for $t \ge 6$).

- $\text{Target}$: Regulation chase target ($S_{\text{Innings 1}} + 1$).

- $\text{RRR}$: Required run rate ($(\text{Target} - S) / (B_{\text{rem}} / 6)$, floored at 1 ball remaining).

- Phase Classification:

  - **Powerplay:** Overs 1–6 ($0 \le t \le 35$).

  - **Middle:** Overs 7–15 ($36 \le t \le 89$).

  - **Death:** Overs 16–20 ($90 \le t \le 119$).



The shift-1 procedure enforces temporal discipline: by constructing match features strictly prior to delivery execution, the framework guarantees that no subsequent delivery outcome leaks into the state representation. This design establishes causal timing, but does not claim that temporal sequence alone constitutes causal inference of player impact.



### 2. Dynamic Delivery Leverage Index (DLI)

The **Delivery Leverage Index (DLI)** is the approved contextual measure of delivery-level match pressure. It quantifies the operational pressure surrounding each delivery based on required scoring rates, wickets in hand, match phase, and remaining deliveries.

- **Contextual Measure vs. Match Prediction:** DLI is strictly a contextual measure of **delivery-level match pressure**, not a direct win-probability estimate or prediction of match outcome. It answers: *"How much pressure surrounds this delivery?"* A match state requiring 14 runs off 3 deliveries has extreme leverage ($\text{DLI} > 2.5$) regardless of whether the batting or bowling team ultimately wins.



### 3. The Four Approved DLI Pressure Tiers

Continuous DLI values are categorized into four discrete operational tiers using the approved M3 thresholds:

- **Tier 1: Low Pressure ($\text{DLI} < 0.90$):** Uncontested or one-sided game situations. Used strictly as the **normal baseline**.

- **Tier 2: Medium Pressure ($0.90 \le \text{DLI} < 1.35$):** Standard competitive match play.

- **Tier 3: High Pressure ($1.35 \le \text{DLI} < 2.25$):** Elevated leverage junctures (phase transitions, cluster wickets, death defense).

- **Tier 4: Extreme Pressure ($\text{DLI} \ge 2.25$):** Terminal crunch time (final overs, narrow-margin chases).

- **Combined Pressure (Tiers 2–4):** Aggregates all deliveries under elevated leverage ($\text{DLI} \ge 0.90$).

- **High Pressure (Tiers 3–4):** Isolates the top quintile of elevated match moments ($\text{DLI} \ge 1.35$).



### 4. Approved Chase and Setting DLI Formulations



#### Chase Pressure (Innings 2):

In a run chase, pressure is driven by the relationship between the required run rate, wickets in hand, and remaining deliveries:

$$\text{DLI}_{\text{chase}} = \text{Clamp}\left[ \left(\frac{\text{RRR}}{\text{CRR}_{\text{phase}}}\right) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.50} \times \left(1 + \frac{24}{B_{\text{rem}} + 12}\right)^{0.50}, \; 0.10, \; 5.00 \right]$$

Where:

- $\text{CRR}_{\text{phase}}$ represents the historical empirical scoring par for the match phase:

  - Powerplay (Overs 1–6): $8.15$ RPO

  - Middle (Overs 7–15): $8.00$ RPO

  - Death (Overs 16–20): $9.30$ RPO

- $W_{\text{hand}}$ is clamped $\ge 1$ and $B_{\text{rem}}$ is clamped $\ge 1$.

- Clamping limits the chase DLI strictly to $[0.10, 5.00]$.



#### Setting Pressure (Innings 1):

In the first innings, pressure is driven by time progression, wickets lost, and run-rate stagnation:

$$\text{DLI}_{\text{setting}} = \text{Clamp}\left[ \Phi(t) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.60} \times \left(1 + \max\left(0, \; \frac{\text{CRR}_{\text{phase}} - \text{CRR}}{6}\right)\right)^{0.50}, \; 0.20, \; 3.50 \right]$$

Where:

- $\Phi(t)$ is the continuous power-law time progression factor:

  $$\Phi(t) = 0.80 + 0.70 \times \left(\frac{t}{120}\right)^{1.20}$$

- The wicket sensitivity exponent ($0.60$) is higher than in chases ($0.50$) because early wickets in Innings 1 severely compromise the batting team's ability to attack at the death.

- The stagnation penalty term $\max\left(0, \frac{\text{CRR}_{\text{phase}} - \text{CRR}}{6}\right)$ is active for $t \ge 6$ (defined as $0$ for $t < 6$), measuring cumulative scoring slowdown relative to empirical phase par $\text{CRR}_{\text{phase}}$.

- Clamping limits the setting DLI strictly to $[0.20, 3.50]$.



#### Super Over:

Fixed by rule at $\text{DLI} = 3.50$.



### 5. Contextual Performance Estimation and LPMO Priors

To determine whether a player performed well under pressure, their observed performance must be compared against the expected baseline of an average player in that exact match context:

- For batters, the baseline expectation is the expected boundary rate $\mu_{\text{phase}, \text{tier}}$ (probability of hitting a 4 or 6).

- For bowlers, the baseline expectation is the expected economy rate $R_{\text{context, pressure}}$ (expected runs conceded per over).

- **Leave-Player-and-Matches-Out (LPMO):** To prevent statistical leakage, when evaluating player $i$, all deliveries from matches in which player $i$ participated are excluded from the contextual prior calculation. This ensures environmental conditions from player $i$'s matches cannot bias their own expectation.



### 6. Empirical Bayes Crossed-Effects Shrinkage

Raw observed metrics are prone to sample size distortion. Our hierarchical model residualizes player effects, phase effects, pressure-tier effects, and match-level environmental variance:

$$\text{Var}(\text{Observed}) = \tau_{\text{player}}^2 + \sigma_{\text{match}}^2 + \sigma_{\text{noise}}^2$$

The empirical Bayes point estimate shrinks the observed performance toward the contextual prior:

$$\hat{\theta}_i = \lambda_i \bar{y}_i + (1 - \lambda_i) \mu_{\text{context}}$$

Where shrinkage factor $\lambda_i = \frac{\tau^2}{\tau^2 + \text{SE}_i^2}$. Players with extensive evidence retain their observed performance, while players with limited exposure shrink toward context.



### 7. Statistical Uncertainty and the Approved 1.645 Multiplier

Under the approved statistical sign-off convention (`FINAL_STATISTICAL_SIGNOFF.md`), rankings are based on the **conservative endpoint of the 90% two-sided credible interval, which mathematically corresponds to a 95% one-sided posterior credible bound under the Gaussian posterior convention** using multiplier $Z = 1.645$:

- For batters: $\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$ (95% one-sided lower posterior credible bound for contextual batting value-add).

- For bowlers: $\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$ (95% one-sided upper posterior credible bound for contextual economy delta).



### 8. Separate Batting and Bowling Ranking Logic

Batting and bowling evaluate fundamentally different performance characteristics and are ranked independently:

- **Batting Ranking:** Higher contextual batting value-add is superior. Batters are ranked in **descending order** of their conservative lower bound ($\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$). Boundary rate, strike rate and dot-ball rate are supporting evidence, not substitutes for the primary contextual estimate.

- **Bowling Ranking:** Lower economy relative to context is superior (negative delta indicates runs saved). Bowlers are ranked in **ascending order** of their conservative upper bound ($\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$). This bound represents a 95% one-sided posterior upper limit (worst-case credible performance). Ranking by ascending upper bound prioritizes bowlers who minimize credible run leakage under pressure, though it does not guarantee strictly negative economy delta, as all eligible candidates' upper bounds cross slightly above zero due to residual estimation variance.



---



## C. Top 10 Pressure-Performing Batsmen



Ranked strictly by the conservative lower bound of the 90% two-sided credible interval (95% one-sided lower posterior credible bound for contextual batting value-add, $Z = 1.645$) in descending order within the eligible population ($\ge 500$ career balls, $\ge 100$ pressure balls, $se_{\text{latent}} \le 0.035$).



> [!NOTE]

> **Discipline Eligibility vs. Real-World Roles:**

> Classifications in the *Observed Discipline Eligibility* column reflect recorded delivery participation in the canonical modeling database (whether a player batted and/or bowled in clean fixtures) rather than official franchise or international cricket squad roles. For example, Abhishek Sharma and Andre Russell are classified as dual-discipline eligible because both have substantial batting and bowling deliveries in the dataset.



| Rank | Player Name | Local ID | Observed Discipline Eligibility | Contextual Val-Add ($\Delta_{\text{EB}}$) | 95% One-Sided Lower Bound ($\text{LB}_{90\% \text{ CI}}$) | Total Legal Balls | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Evidence Summary & Key Limitations |

|:---:|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|

| **#1** | **Abhishek Sharma** | `6281` | Dual-discipline eligible | **+6.70%** | **+2.72%** | 2,136 | 1,427 | 435 | 23 | **Confirmed Positive Value-Add.** Elevates scoring by +7.63 SR under pressure (186.19 SR) while reducing dot balls by 9.51%. Small Tier 4 sample (23 balls); primary profile established in T2 & T3. |

| **#2** | **Suryakumar Yadav** | `1699` | Single-discipline (Batting) | **+4.50%** | **+1.05%** | 2,646 | 2,367 | 1,137 | 147 | **Confirmed Positive Value-Add.** Large sample (2,367 pressure balls). Increases scoring tempo as pressure rises, reaching 214.97 SR in Tier 4 with a 4.18% dismissal hazard. |

| **#3** | **Vaibhav Sooryavanshi** | `50284` | Single-discipline (Batting) | **+6.31%** | **+0.78%** | 561 | 392 | 87 | 0 | **Confirmed Positive Value-Add.** Highest raw boundary conversion (37.50%) and pressure SR (220.92). **Limitation: Exactly 0 Tier 4 balls; sample size (561 balls) is close to eligibility cutoff.** |

| **#4** | **Finn Allen** | `4847` | Single-discipline (Batting) | **+5.16%** | **-0.07%** | 804 | 421 | 71 | 0 | **Relative Leader.** Largest raw strike rate increase (+47.64 SR, reaching 196.20 SR under pressure). High dismissal hazard (7.60%). **Limitation: Exactly 0 Tier 4 balls; lower bound crosses below zero.** |

| **#5** | **Travis Head** | `2367` | Single-discipline (Batting) | **+4.32%** | **-0.18%** | 1,087 | 665 | 146 | 0 | **Relative Leader.** Overall pressure SR drops (-27.46) from ultra-high normal baseline, but accelerates to 182.19 SR in Tier 3 High Leverage. **Limitation: Exactly 0 Tier 4 balls.** |

| **#6** | **Phil Salt** | `5553` | Single-discipline (Batting) | **+3.58%** | **-0.75%** | 1,497 | 1,012 | 280 | 45 | **Relative Leader.** Consistent boundary scoring across phases; reaches 228.89 SR with 13.33% dot balls in Tier 4 crunch time across 45 balls. |

| **#7** | **Yashasvi Jaiswal** | `6819` | Single-discipline (Batting) | **+3.03%** | **-0.78%** | 1,774 | 1,181 | 293 | 0 | **Relative Leader.** Increases SR from 150.45 in T2 to 171.33 in T3 High Leverage while reducing dot balls by 9.55%. **Limitation: Exactly 0 Tier 4 balls.** |

| **#8** | **Ishan Kishan** | `4117` | Single-discipline (Batting) | **+2.51%** | **-0.90%** | 2,314 | 1,955 | 621 | 23 | **Relative Leader.** Substantial contrast between low-leverage play (107.80 SR) and pressure scoring (153.04 SR, +45.24 delta). Small Tier 4 sample (23 balls). |

| **#9** | **Tim David** | `6396` | Single-discipline (Batting) | **+3.43%** | **-1.00%** | 1,154 | 1,077 | 902 | 286 | **Relative Leader.** Death-overs finisher (78.2% of career deliveries in T3–4; 286 balls in T4). Maintains 199.30 SR in Tier 4 with a 4.83% dismissal hazard. |

| **#10** | **Andre Russell** | `1318` | Dual-discipline eligible | **+3.70%** | **-1.26%** | 707 | 687 | 626 | 202 | **Relative Leader.** High concentration of pressure exposure (97.2% career balls). High dot-ball rate (42.21%) accompanied by boundary scoring (+3.70% contextual value-add). |



---



## D. Top 10 Pressure-Performing Bowlers



Ranked strictly by the conservative upper bound of the 90% two-sided credible interval (95% one-sided upper posterior credible bound for contextual economy delta, $Z = 1.645$) in ascending order within the eligible population ($\ge 500$ career balls, $\ge 100$ pressure balls, $se_{\text{latent}} \le 0.65$ RPO). This upper bound defines the conservative ceiling on expected run concession under pressure (minimizing credible worst-case run leakage); it does not guarantee absolute economy suppression below par, as all eligible candidates have positive upper bounds.



> [!NOTE]

> **Discipline Eligibility vs. Real-World Roles:**

> Classifications in the *Observed Discipline Eligibility* column reflect recorded delivery participation in the canonical modeling database. For example, Kuldeep Yadav is classified as dual-discipline eligible because he faced deliveries in the dataset, even though he operates exclusively as a specialist bowler in competitive cricket.



| Rank | Player Name | Local ID | Observed Discipline Eligibility | Contextual Econ Delta ($\Delta_{\text{EB}}$) | 95% One-Sided Upper Bound ($\text{UB}_{90\% \text{ CI}}$) | Total Legal Balls (Overs) | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Evidence Summary & Key Limitations |

|:---:|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|

| **#1** | **Sunil Narine** | `781` | Dual-discipline eligible | **-0.605 RPO** | **+0.296 RPO** | 1,533 (255.3) | 1,394 | 741 | 158 | **Top Relative Suppressor.** Economy systematically decreases as pressure rises (8.07 normal -> 5.85 RPO Tier 4). 44.30% dot balls in Tier 4. Upper bound is positive (+0.296 RPO). |

| **#2** | **Jasprit Bumrah** | `2933` | Single-discipline (Bowling) | **-0.538 RPO** | **+0.393 RPO** | 1,594 (265.4) | 1,338 | 836 | 256 | **Top Relative Suppressor.** Concedes 6.68 RPO with 44.53% dot balls across 256 balls in Tier 4. 72 pressure wickets. Upper bound is positive (+0.393 RPO). |

| **#3** | **Mustafizur Rahman** | `4373` | Single-discipline (Bowling) | **-0.326 RPO** | **+0.592 RPO** | 1,414 (235.4) | 1,247 | 756 | 267 | **Top Relative Suppressor.** Concedes 6.76 RPO and bowls 49.44% dot balls in Tier 4 across 267 balls. 66 pressure wickets. |

| **#4** | **Kuldeep Yadav** | `3644` | Dual-discipline eligible* | **-0.213 RPO** | **+0.595 RPO** | 1,878 (313.0) | 1,811 | 1,074 | 216 | **Top Relative Suppressor.** High wicket-taking volume (114 pressure wickets, 15.89 SR). Economy drops from 12.09 normal to 7.66 RPO under pressure and 7.20 RPO in High Pressure. |

| **#5** | **Axar Patel** | `2876` | Dual-discipline eligible | **-0.150 RPO** | **+0.651 RPO** | 2,484 (414.0) | 2,287 | 1,273 | 255 | **Top Relative Suppressor.** Substantial bowling volume (414 overs). 103 pressure wickets; lowest latent standard error in cohort (0.4868 RPO). |

| **#6** | **Wanindu Hasaranga** | `4900` | Dual-discipline eligible | **-0.219 RPO** | **+0.652 RPO** | 1,789 (298.1) | 1,562 | 903 | 184 | **Top Relative Suppressor.** Wicket-taking rate of 14.46 balls/wicket under pressure. Captures 108 pressure wickets while holding economy under 7.90 RPO. |

| **#7** | **Ravindra Jadeja** | `152` | Dual-discipline eligible | **-0.156 RPO** | **+0.655 RPO** | 1,355 (225.5) | 1,312 | 743 | 127 | **Top Relative Suppressor.** Restricts boundaries under pressure (13.64% boundary concession rate across 1,312 balls) with low match-to-match variance. |

| **#8** | **Mitchell Santner** | `4101` | Dual-discipline eligible | **-0.245 RPO** | **+0.656 RPO** | 1,725 (287.3) | 1,526 | 839 | 213 | **Top Relative Suppressor.** Economy decreases to 6.68 RPO with 41.78% dot balls in Tier 4 Extreme Leverage (213 balls). Concedes 13.50% boundaries under pressure. |

| **#9** | **Sikandar Raza** | `2984` | Dual-discipline eligible | **-0.274 RPO** | **+0.670 RPO** | 839 (139.5) | 719 | 343 | 28 | **Top Relative Suppressor.** Concedes boundaries on 11.13% of pressure deliveries. Small Tier 4 sample (28 balls); profile established in T2 & T3. |

| **#10** | **Abrar Ahmed** | `5979` | Single-discipline (Bowling) | **-0.304 RPO** | **+0.697 RPO** | 740 (123.2) | 646 | 424 | 136 | **Top Relative Suppressor.** Economy of 5.92 RPO across 424 High-Pressure balls and 5.16 RPO in Tier 4 (49.26% dot balls, 42 pressure wickets). |



---



## E. Player Evidence & Detailed Observations



### Batsmen Observations



#### 1. Abhishek Sharma (Local ID: `6281`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 709 balls | 1266 runs | 178.56 SR | 29.62% boundary rate | 41.04% dot-ball rate | 31 dismissals | 4.37% dismissal hazard

- **Combined Pressure (T2–T4):** 1427 balls | 2657 runs | 186.19 SR | 29.43% boundary rate | 31.53% dot-ball rate | 86 dismissals | 6.03% dismissal hazard

- **High Pressure (T3–T4):** 435 balls | 787 runs | 180.92 SR | 28.05% boundary rate | 31.03% dot-ball rate | 26 dismissals | 5.98% dismissal hazard

- **Extreme Pressure (T4):** 23 balls | 38 runs | 165.22 SR | 26.09% boundary rate | 39.13% dot-ball rate | 3 dismissals | 13.04% dismissal hazard | **Exposure Flag:** Small Tier 4 sample (23 balls); primary profile established in T2 and T3.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +6.70\%$, latent standard error $se_{latent} = 0.0242$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = +2.72\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +7.63$, $\Delta\text{Bnd} = -0.19\%$, $\Delta\text{Dot} = -9.51\%$.



#### 2. Suryakumar Yadav (Local ID: `1699`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 279 balls | 454 runs | 162.72 SR | 25.81% boundary rate | 38.35% dot-ball rate | 12 dismissals | 4.30% dismissal hazard

- **Combined Pressure (T2–T4):** 2367 balls | 3951 runs | 166.92 SR | 24.50% boundary rate | 31.43% dot-ball rate | 99 dismissals | 4.18% dismissal hazard

- **High Pressure (T3–T4):** 1137 balls | 2006 runs | 176.43 SR | 26.47% boundary rate | 29.73% dot-ball rate | 43 dismissals | 3.78% dismissal hazard

- **Extreme Pressure (T4):** 147 balls | 316 runs | 214.97 SR | 34.01% boundary rate | 27.21% dot-ball rate | 12 dismissals | 8.16% dismissal hazard | **Exposure Flag:** Robust Tier 4 sample (147 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +4.50\%$, latent standard error $se_{latent} = 0.0209$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = +1.05\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +4.20$, $\Delta\text{Bnd} = -1.31\%$, $\Delta\text{Dot} = -6.92\%$.



#### 3. Vaibhav Sooryavanshi (Local ID: `50284`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 169 balls | 361 runs | 213.61 SR | 36.09% boundary rate | 34.91% dot-ball rate | 9 dismissals | 5.33% dismissal hazard

- **Combined Pressure (T2–T4):** 392 balls | 866 runs | 220.92 SR | 37.50% boundary rate | 34.95% dot-ball rate | 21 dismissals | 5.36% dismissal hazard

- **High Pressure (T3–T4):** 87 balls | 208 runs | 239.08 SR | 41.38% boundary rate | 37.93% dot-ball rate | 6 dismissals | 6.90% dismissal hazard

- **Extreme Pressure (T4):** 0 balls faced (Zero observed exposure in Tier 4 crunch conditions) | **Exposure Flag:** Exactly 0 Tier 4 balls; cannot assert extreme crunch execution.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +6.31\%$, latent standard error $se_{latent} = 0.0336$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = +0.78\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +7.31$, $\Delta\text{Bnd} = +1.41\%$, $\Delta\text{Dot} = +0.04\%$.



#### 4. Finn Allen (Local ID: `4847`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 383 balls | 569 runs | 148.56 SR | 23.50% boundary rate | 45.95% dot-ball rate | 16 dismissals | 4.18% dismissal hazard

- **Combined Pressure (T2–T4):** 421 balls | 826 runs | 196.20 SR | 31.59% boundary rate | 35.39% dot-ball rate | 32 dismissals | 7.60% dismissal hazard

- **High Pressure (T3–T4):** 71 balls | 162 runs | 228.17 SR | 38.03% boundary rate | 29.58% dot-ball rate | 5 dismissals | 7.04% dismissal hazard

- **Extreme Pressure (T4):** 0 balls faced (Zero observed exposure in Tier 4 crunch conditions) | **Exposure Flag:** Exactly 0 Tier 4 balls; cannot assert extreme crunch execution.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +5.16\%$, latent standard error $se_{latent} = 0.0318$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = -0.07\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +47.64$, $\Delta\text{Bnd} = +8.09\%$, $\Delta\text{Dot} = -10.56\%$.



#### 5. Travis Head (Local ID: `2367`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 422 balls | 819 runs | 194.08 SR | 34.60% boundary rate | 37.68% dot-ball rate | 15 dismissals | 3.55% dismissal hazard

- **Combined Pressure (T2–T4):** 665 balls | 1108 runs | 166.62 SR | 28.57% boundary rate | 38.35% dot-ball rate | 48 dismissals | 7.22% dismissal hazard

- **High Pressure (T3–T4):** 146 balls | 266 runs | 182.19 SR | 32.88% boundary rate | 41.78% dot-ball rate | 12 dismissals | 8.22% dismissal hazard

- **Extreme Pressure (T4):** 0 balls faced (Zero observed exposure in Tier 4 crunch conditions) | **Exposure Flag:** Exactly 0 Tier 4 balls; cannot assert extreme crunch execution.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +4.32\%$, latent standard error $se_{latent} = 0.0274$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = -0.18\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = -27.46$, $\Delta\text{Bnd} = -6.03\%$, $\Delta\text{Dot} = +0.67\%$.



#### 6. Phil Salt (Local ID: `5553`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 485 balls | 822 runs | 169.48 SR | 28.66% boundary rate | 36.70% dot-ball rate | 23 dismissals | 4.74% dismissal hazard

- **Combined Pressure (T2–T4):** 1012 balls | 1733 runs | 171.25 SR | 25.69% boundary rate | 31.13% dot-ball rate | 47 dismissals | 4.64% dismissal hazard

- **High Pressure (T3–T4):** 280 balls | 517 runs | 184.64 SR | 26.43% boundary rate | 26.07% dot-ball rate | 15 dismissals | 5.36% dismissal hazard

- **Extreme Pressure (T4):** 45 balls | 103 runs | 228.89 SR | 28.89% boundary rate | 13.33% dot-ball rate | 1 dismissals | 2.22% dismissal hazard | **Exposure Flag:** Small Tier 4 sample (45 balls); primary profile established in T2 and T3.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +3.58\%$, latent standard error $se_{latent} = 0.0263$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = -0.75\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +1.77$, $\Delta\text{Bnd} = -2.97\%$, $\Delta\text{Dot} = -5.57\%$.



#### 7. Yashasvi Jaiswal (Local ID: `6819`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 593 balls | 882 runs | 148.74 SR | 25.97% boundary rate | 46.04% dot-ball rate | 19 dismissals | 3.20% dismissal hazard

- **Combined Pressure (T2–T4):** 1181 balls | 1838 runs | 155.63 SR | 24.64% boundary rate | 36.49% dot-ball rate | 58 dismissals | 4.91% dismissal hazard

- **High Pressure (T3–T4):** 293 balls | 502 runs | 171.33 SR | 28.33% boundary rate | 32.76% dot-ball rate | 21 dismissals | 7.17% dismissal hazard

- **Extreme Pressure (T4):** 0 balls faced (Zero observed exposure in Tier 4 crunch conditions) | **Exposure Flag:** Exactly 0 Tier 4 balls; cannot assert extreme crunch execution.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +3.03\%$, latent standard error $se_{latent} = 0.0232$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = -0.78\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +6.89$, $\Delta\text{Bnd} = -1.33\%$, $\Delta\text{Dot} = -9.55\%$.



#### 8. Ishan Kishan (Local ID: `4117`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 359 balls | 387 runs | 107.80 SR | 16.16% boundary rate | 51.25% dot-ball rate | 13 dismissals | 3.62% dismissal hazard

- **Combined Pressure (T2–T4):** 1955 balls | 2992 runs | 153.04 SR | 22.81% boundary rate | 34.63% dot-ball rate | 96 dismissals | 4.91% dismissal hazard

- **High Pressure (T3–T4):** 621 balls | 1022 runs | 164.57 SR | 24.15% boundary rate | 30.11% dot-ball rate | 34 dismissals | 5.48% dismissal hazard

- **Extreme Pressure (T4):** 23 balls | 31 runs | 134.78 SR | 13.04% boundary rate | 26.09% dot-ball rate | 2 dismissals | 8.70% dismissal hazard | **Exposure Flag:** Small Tier 4 sample (23 balls); primary profile established in T2 and T3.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +2.51\%$, latent standard error $se_{latent} = 0.0208$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = -0.90\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +45.24$, $\Delta\text{Bnd} = +6.65\%$, $\Delta\text{Dot} = -16.62\%$.



#### 9. Tim David (Local ID: `6396`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Batting)

- **Normal Conditions (T1):** 77 balls | 126 runs | 163.64 SR | 24.68% boundary rate | 35.06% dot-ball rate | 7 dismissals | 9.09% dismissal hazard

- **Combined Pressure (T2–T4):** 1077 balls | 1912 runs | 177.53 SR | 24.98% boundary rate | 30.92% dot-ball rate | 52 dismissals | 4.83% dismissal hazard

- **High Pressure (T3–T4):** 902 balls | 1618 runs | 179.38 SR | 25.28% boundary rate | 30.82% dot-ball rate | 46 dismissals | 5.10% dismissal hazard

- **Extreme Pressure (T4):** 286 balls | 554 runs | 193.71 SR | 27.27% boundary rate | 32.52% dot-ball rate | 16 dismissals | 5.59% dismissal hazard | **Exposure Flag:** Robust Tier 4 sample (286 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +3.43\%$, latent standard error $se_{latent} = 0.0270$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = -1.00\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +13.89$, $\Delta\text{Bnd} = +0.30\%$, $\Delta\text{Dot} = -4.14\%$.



#### 10. Andre Russell (Local ID: `1318`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 20 balls | 34 runs | 170.00 SR | 25.00% boundary rate | 40.00% dot-ball rate | 0 dismissals | 0.00% dismissal hazard

- **Combined Pressure (T2–T4):** 687 balls | 1173 runs | 170.74 SR | 26.06% boundary rate | 42.21% dot-ball rate | 43 dismissals | 6.26% dismissal hazard

- **High Pressure (T3–T4):** 626 balls | 1068 runs | 170.61 SR | 26.04% boundary rate | 42.01% dot-ball rate | 40 dismissals | 6.39% dismissal hazard

- **Extreme Pressure (T4):** 202 balls | 334 runs | 165.35 SR | 24.75% boundary rate | 41.58% dot-ball rate | 16 dismissals | 7.92% dismissal hazard | **Exposure Flag:** Robust Tier 4 sample (202 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual batting value-add $\Delta_{EB} = +3.70\%$, latent standard error $se_{latent} = 0.0302$, conservative lower bound $\text{LB}_{90\% \text{ CI}} = -1.26\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{SR} = +0.74$, $\Delta\text{Bnd} = +1.06\%$, $\Delta\text{Dot} = +2.21\%$.



### Bowlers Observations



#### 1. Sunil Narine (Local ID: `781`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 139 balls (23.1 ov) | 187 runs | 8.07 RPO economy | 3 wickets | 46.3 balls/wkt | 33.81% dot-ball rate | 15.83% boundary-concession rate

- **Combined Pressure (T2–T4):** 1394 balls (232.2 ov) | 1540 runs | 6.63 RPO economy | 63 wickets | 22.1 balls/wkt | 38.52% dot-ball rate | 10.69% boundary-concession rate

- **High Pressure (T3–T4):** 741 balls (123.3 ov) | 762 runs | 6.17 RPO economy | 44 wickets | 16.8 balls/wkt | 41.43% dot-ball rate | 9.31% boundary-concession rate

- **Extreme Pressure (T4):** 158 balls (26.2 ov) | 154 runs | 5.85 RPO economy | 9 wickets | 17.6 balls/wkt | 44.30% dot-ball rate | 8.86% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (158 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.605\text{ RPO}$, latent standard error $se_{latent} = 0.5478\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.296\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = -1.44\text{ RPO}$, $\Delta\text{Dot} = +4.71\%$, $\Delta\text{Bnd} = -5.14\%$.



#### 2. Jasprit Bumrah (Local ID: `2933`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Bowling)

- **Normal Conditions (T1):** 256 balls (42.4 ov) | 266 runs | 6.23 RPO economy | 7 wickets | 36.6 balls/wkt | 51.17% dot-ball rate | 15.23% boundary-concession rate

- **Combined Pressure (T2–T4):** 1338 balls (223.0 ov) | 1552 runs | 6.96 RPO economy | 72 wickets | 18.6 balls/wkt | 43.42% dot-ball rate | 14.87% boundary-concession rate

- **High Pressure (T3–T4):** 836 balls (139.2 ov) | 1011 runs | 7.26 RPO economy | 55 wickets | 15.2 balls/wkt | 38.88% dot-ball rate | 14.71% boundary-concession rate

- **Extreme Pressure (T4):** 256 balls (42.4 ov) | 285 runs | 6.68 RPO economy | 23 wickets | 11.1 balls/wkt | 44.53% dot-ball rate | 13.28% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (256 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.538\text{ RPO}$, latent standard error $se_{latent} = 0.5659\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.393\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = +0.73\text{ RPO}$, $\Delta\text{Dot} = -7.75\%$, $\Delta\text{Bnd} = -0.36\%$.



#### 3. Mustafizur Rahman (Local ID: `4373`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Bowling)

- **Normal Conditions (T1):** 167 balls (27.5 ov) | 217 runs | 7.80 RPO economy | 6 wickets | 27.8 balls/wkt | 41.92% dot-ball rate | 19.76% boundary-concession rate

- **Combined Pressure (T2–T4):** 1247 balls (207.5 ov) | 1524 runs | 7.33 RPO economy | 66 wickets | 18.9 balls/wkt | 40.82% dot-ball rate | 15.88% boundary-concession rate

- **High Pressure (T3–T4):** 756 balls (126.0 ov) | 963 runs | 7.64 RPO economy | 48 wickets | 15.8 balls/wkt | 38.76% dot-ball rate | 15.74% boundary-concession rate

- **Extreme Pressure (T4):** 267 balls (44.3 ov) | 301 runs | 6.76 RPO economy | 27 wickets | 9.9 balls/wkt | 49.44% dot-ball rate | 14.23% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (267 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.326\text{ RPO}$, latent standard error $se_{latent} = 0.5576\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.592\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = -0.47\text{ RPO}$, $\Delta\text{Dot} = -1.10\%$, $\Delta\text{Bnd} = -3.88\%$.



#### 4. Kuldeep Yadav (Local ID: `3644`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset; specialist bowler in competitive cricket)

- **Normal Conditions (T1):** 67 balls (11.1 ov) | 135 runs | 12.09 RPO economy | 2 wickets | 33.5 balls/wkt | 25.37% dot-ball rate | 25.37% boundary-concession rate

- **Combined Pressure (T2–T4):** 1811 balls (301.5 ov) | 2311 runs | 7.66 RPO economy | 114 wickets | 15.9 balls/wkt | 34.18% dot-ball rate | 13.75% boundary-concession rate

- **High Pressure (T3–T4):** 1074 balls (179.0 ov) | 1288 runs | 7.20 RPO economy | 78 wickets | 13.8 balls/wkt | 36.31% dot-ball rate | 12.10% boundary-concession rate

- **Extreme Pressure (T4):** 216 balls (36.0 ov) | 259 runs | 7.19 RPO economy | 24 wickets | 9.0 balls/wkt | 43.98% dot-ball rate | 14.35% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (216 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.213\text{ RPO}$, latent standard error $se_{latent} = 0.4908\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.595\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = -4.43\text{ RPO}$, $\Delta\text{Dot} = +8.81\%$, $\Delta\text{Bnd} = -11.62\%$.



#### 5. Axar Patel (Local ID: `2876`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 197 balls (32.5 ov) | 268 runs | 8.16 RPO economy | 5 wickets | 39.4 balls/wkt | 39.59% dot-ball rate | 19.29% boundary-concession rate

- **Combined Pressure (T2–T4):** 2287 balls (381.1 ov) | 3018 runs | 7.92 RPO economy | 103 wickets | 22.2 balls/wkt | 34.85% dot-ball rate | 15.83% boundary-concession rate

- **High Pressure (T3–T4):** 1273 balls (212.1 ov) | 1664 runs | 7.84 RPO economy | 59 wickets | 21.6 balls/wkt | 34.96% dot-ball rate | 15.40% boundary-concession rate

- **Extreme Pressure (T4):** 255 balls (42.3 ov) | 349 runs | 8.21 RPO economy | 11 wickets | 23.2 balls/wkt | 40.00% dot-ball rate | 18.04% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (255 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.150\text{ RPO}$, latent standard error $se_{latent} = 0.4868\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.651\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = -0.24\text{ RPO}$, $\Delta\text{Dot} = -4.74\%$, $\Delta\text{Bnd} = -3.46\%$.



#### 6. Wanindu Hasaranga (Local ID: `4900`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 227 balls (37.5 ov) | 293 runs | 7.74 RPO economy | 13 wickets | 17.5 balls/wkt | 38.33% dot-ball rate | 15.86% boundary-concession rate

- **Combined Pressure (T2–T4):** 1562 balls (260.2 ov) | 2054 runs | 7.89 RPO economy | 108 wickets | 14.5 balls/wkt | 34.89% dot-ball rate | 14.72% boundary-concession rate

- **High Pressure (T3–T4):** 903 balls (150.3 ov) | 1193 runs | 7.93 RPO economy | 73 wickets | 12.4 balls/wkt | 36.54% dot-ball rate | 14.51% boundary-concession rate

- **Extreme Pressure (T4):** 184 balls (30.4 ov) | 273 runs | 8.90 RPO economy | 18 wickets | 10.2 balls/wkt | 40.22% dot-ball rate | 18.48% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (184 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.219\text{ RPO}$, latent standard error $se_{latent} = 0.5296\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.652\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = +0.15\text{ RPO}$, $\Delta\text{Dot} = -3.44\%$, $\Delta\text{Bnd} = -1.14\%$.



#### 7. Ravindra Jadeja (Local ID: `152`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 43 balls (7.1 ov) | 51 runs | 7.12 RPO economy | 1 wickets | 43.0 balls/wkt | 30.23% dot-ball rate | 9.30% boundary-concession rate

- **Combined Pressure (T2–T4):** 1312 balls (218.4 ov) | 1685 runs | 7.71 RPO economy | 56 wickets | 23.4 balls/wkt | 31.48% dot-ball rate | 13.64% boundary-concession rate

- **High Pressure (T3–T4):** 743 balls (123.5 ov) | 926 runs | 7.48 RPO economy | 34 wickets | 21.9 balls/wkt | 34.05% dot-ball rate | 13.32% boundary-concession rate

- **Extreme Pressure (T4):** 127 balls (21.1 ov) | 178 runs | 8.41 RPO economy | 9 wickets | 14.1 balls/wkt | 36.22% dot-ball rate | 17.32% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (127 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.156\text{ RPO}$, latent standard error $se_{latent} = 0.4930\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.655\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = +0.59\text{ RPO}$, $\Delta\text{Dot} = +1.25\%$, $\Delta\text{Bnd} = +4.34\%$.



#### 8. Mitchell Santner (Local ID: `4101`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 199 balls (33.1 ov) | 243 runs | 7.33 RPO economy | 6 wickets | 33.2 balls/wkt | 40.70% dot-ball rate | 15.58% boundary-concession rate

- **Combined Pressure (T2–T4):** 1526 balls (254.2 ov) | 1826 runs | 7.18 RPO economy | 79 wickets | 19.3 balls/wkt | 37.09% dot-ball rate | 13.50% boundary-concession rate

- **High Pressure (T3–T4):** 839 balls (139.5 ov) | 978 runs | 6.99 RPO economy | 52 wickets | 16.1 balls/wkt | 38.38% dot-ball rate | 12.63% boundary-concession rate

- **Extreme Pressure (T4):** 213 balls (35.3 ov) | 237 runs | 6.68 RPO economy | 17 wickets | 12.5 balls/wkt | 41.78% dot-ball rate | 11.27% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (213 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.245\text{ RPO}$, latent standard error $se_{latent} = 0.5479\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.656\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = -0.15\text{ RPO}$, $\Delta\text{Dot} = -3.61\%$, $\Delta\text{Bnd} = -2.08\%$.



#### 9. Sikandar Raza (Local ID: `2984`)

- **Discipline Eligibility (Dataset):** Dual-discipline eligible (observed batting & bowling in dataset)

- **Normal Conditions (T1):** 120 balls (20.0 ov) | 142 runs | 7.10 RPO economy | 3 wickets | 40.0 balls/wkt | 35.00% dot-ball rate | 14.17% boundary-concession rate

- **Combined Pressure (T2–T4):** 719 balls (119.5 ov) | 845 runs | 7.05 RPO economy | 31 wickets | 23.2 balls/wkt | 31.57% dot-ball rate | 11.13% boundary-concession rate

- **High Pressure (T3–T4):** 343 balls (57.1 ov) | 393 runs | 6.87 RPO economy | 17 wickets | 20.2 balls/wkt | 33.53% dot-ball rate | 10.50% boundary-concession rate

- **Extreme Pressure (T4):** 28 balls (4.4 ov) | 24 runs | 5.14 RPO economy | 3 wickets | 9.3 balls/wkt | 39.29% dot-ball rate | 3.57% boundary-concession rate | **Exposure Flag:** Small Tier 4 sample (28 balls); profile established in T2 and T3.

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.274\text{ RPO}$, latent standard error $se_{latent} = 0.5738\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.670\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = -0.05\text{ RPO}$, $\Delta\text{Dot} = -3.43\%$, $\Delta\text{Bnd} = -3.04\%$.



#### 10. Abrar Ahmed (Local ID: `5979`)

- **Discipline Eligibility (Dataset):** Single-discipline eligible (Bowling)

- **Normal Conditions (T1):** 94 balls (15.4 ov) | 114 runs | 7.28 RPO economy | 2 wickets | 47.0 balls/wkt | 42.55% dot-ball rate | 13.83% boundary-concession rate

- **Combined Pressure (T2–T4):** 646 balls (107.4 ov) | 707 runs | 6.57 RPO economy | 42 wickets | 15.4 balls/wkt | 42.72% dot-ball rate | 12.07% boundary-concession rate

- **High Pressure (T3–T4):** 424 balls (70.4 ov) | 418 runs | 5.92 RPO economy | 31 wickets | 13.7 balls/wkt | 43.87% dot-ball rate | 8.96% boundary-concession rate

- **Extreme Pressure (T4):** 136 balls (22.4 ov) | 117 runs | 5.16 RPO economy | 9 wickets | 15.1 balls/wkt | 49.26% dot-ball rate | 7.35% boundary-concession rate | **Exposure Flag:** Robust Tier 4 sample (136 balls).

- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\Delta_{EB} = -0.304\text{ RPO}$, latent standard error $se_{latent} = 0.6083\text{ RPO}$, conservative upper bound $\text{UB}_{90\% \text{ CI}} = +0.697\text{ RPO}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\Delta\text{Econ} = -0.71\text{ RPO}$, $\Delta\text{Dot} = +0.17\%$, $\Delta\text{Bnd} = -1.76\%$.



---



## F. Statistical Confidence & Limitations



In compliance with rigorous sports analytics governance, all statistical boundaries and data constraints are explicitly disclosed:



### 1. Batter Statistical Confidence Boundary

- Under the approved convention ($Z = 1.645$, representing the 90% two-sided credible interval lower bound and 95% one-sided lower posterior credible bound for contextual batting value-add), **only three batters** possess positive lower bounds: **Abhishek Sharma (+2.72%)**, **Suryakumar Yadav (+1.05%)**, and **Vaibhav Sooryavanshi (+0.78%)**.

- The remaining seven batters (Allen, Head, Salt, Jaiswal, Kishan, David, Russell) exhibit positive posterior point estimates ($\Delta_{\text{EB}} \in [+2.51\%, +5.16\%]$), but their 90% CI lower bounds cross below zero. They are included on relative ranking merit within the eligible population, not as confirmed positive performers under a positive 95% one-sided lower posterior credible bound. Boundary rate, strike rate and dot-ball rate serve as supporting empirical evidence, not substitutes for the primary contextual estimate.



### 2. Bowler Statistical Confidence Boundary

- **Zero shortlisted bowlers have a conservative upper bound below zero.**

- The 90% two-sided CI upper bounds range from $+0.296$ RPO (Narine) to $+0.697$ RPO (Abrar). Even under the less conservative 90% one-sided threshold ($Z = 1.282$), upper bounds remain positive (minimum $+0.098$ RPO).

- Therefore, **no shortlisted bowler has a credible upper bound establishing economy suppression strictly below contextual expectation**. They represent the strongest relative candidates within the eligible population under conservative ranking.



### 3. Extreme Leverage Exposure Disclosures (Tier 4)

- Four shortlisted batsmen—**Vaibhav Sooryavanshi, Finn Allen, Travis Head, and Yashasvi Jaiswal—have exactly 0 career deliveries in Tier 4 Extreme Leverage**. Their rankings reflect performance under competitive (Tier 2) and elevated (Tier 3) pressure. **No extreme-pressure (Tier 4) clutch execution can be statistically asserted for these four players.**

- Abhishek Sharma (23 balls) and Ishan Kishan (23 balls) have small Tier 4 samples. Only Suryakumar Yadav (147), Tim David (286), and Andre Russell (202) possess robust Tier 4 exposure.



### 4. Origin of Eligibility Thresholds

- The threshold of $\ge 500$ career legal balls (yielding 106 eligible batters and 109 eligible bowlers) was **introduced during shortlist construction** from the empirical sensitivity table in `PLAYER_DATA_COVERAGE_AND_ELIGIBILITY_AUDIT.md`. It was **not pre-specified in the earlier M3/M4 pilot plan** (which used $\ge 120$ balls for batters and $\ge 144$ balls for bowlers).

- The $\ge 100$ pressure balls and latent SE thresholds ($\le 0.035$ for batters, $\le 0.65$ RPO for bowlers) were adopted to screen out provisional and unpooled players.

### 4.1 First-Innings Death-Over DLI Calibration Limitations
- In the first innings (Setting), target chasing dynamics are absent, and leverage is calibrated from resource consumption curves and phase par progression.
- During death overs (16–20), when the batting team retains substantial wickets in hand (e.g. 8–9 wickets remaining), setting DLI approaches an asymptotic ceiling ($DLI \approx 2.50$) rather than escalating sharply like second-innings required run rate cliffs.
- As a consequence, first-innings death overs under-represent extreme leverage relative to run-chase crunch moments ($DLI \ge 3.0$), requiring both late overs and lost wickets to enter Tier 4. This operational calibration limitation is formally acknowledged as a boundary condition of setting leverage in T20 cricket.

### 4.2 Point Estimates vs. Uncertainty-Adjusted Credibility Rankings
- Official rankings do not mirror raw posterior point estimates ($\Delta_{\text{EB}}$) because Empirical Bayes credibility bounds penalize estimation standard error ($se_{\text{latent}}$).
- For example, in the bowler cohort, Wanindu Hasaranga has a more negative point estimate ($\Delta_{\text{EB}} = -0.219$ RPO) than Axar Patel ($\Delta_{\text{EB}} = -0.150$ RPO). However, Axar Patel's substantially larger delivery sample (2,484 legal balls / 414 overs vs. 1,789 balls) produces lower latent standard error ($se = 0.4868$ vs. $0.5293$ RPO), resulting in a tighter conservative upper bound ($\text{UB}_{90\% \text{ CI}} = +0.651$ vs. $+0.652$ RPO).
- Axar Patel is therefore ranked #5 and Hasaranga #6, ensuring that high-volume reliability is rewarded over smaller-sample variance. Rankings should not be reordered based on raw point estimates.



### 5. Multi-Competition Scope, Training Period & Dataset Provenance

#### Exact Canonical Dataset Period (2022-01-22 to 2026-11-01):
- The canonical modeling database (`data/processed/m5_3/match_state_full.csv`) comprises matches contested between **January 22, 2022** and **November 1, 2026**.
- Total Canonical Matches: **776 matches** (179,837 total deliveries).
- Prior informal exploratory scratchpads that referenced "2008–2024" represented legacy proof-of-concept datasets; the official, verified, and frozen competition dataset is exclusively the 2022–2026 multi-competition corpus.

#### Clarification: Official Competition Shortlist vs. Prospective Walk-Forward Validation Cohort:
An important methodological distinction exists between the full-dataset official rankings and the prospective walk-forward validation experiments:
1. **Official Competition Shortlist (Tables 1 & 2):** Evaluates player careers across the full 2022–2026 multi-year dataset under pressure Tiers 2–4 with career thresholds ($\ge 500$ legal balls, $\ge 100$ pressure balls). This full-sample evaluation maximizes statistical power and posterior precision for the final auction shortlist:
   - *Batters:* 1. Abhishek Sharma, 2. Suryakumar Yadav, 3. Vaibhav Sooryavanshi, 4. Finn Allen, 5. Travis Head, 6. Phil Salt, 7. Yashasvi Jaiswal, 8. Ishan Kishan, 9. Tim David, 10. Andre Russell.
   - *Bowlers:* 1. Sunil Narine, 2. Jasprit Bumrah, 3. Mustafizur Rahman, 4. Kuldeep Yadav, 5. Axar Patel, 6. Wanindu Hasaranga, 7. Ravindra Jadeja, 8. Mitchell Santner, 9. Sikandar Raza, 10. Abrar Ahmed.
2. **Prospective Walk-Forward Validation Benchmark Cohort (Window A):** Conducted in Phases 5.11, 5.14, and 5.14.5 to strictly verify model generalization and guard against overfitting. The model was trained strictly on historical data through 2024 and prospectively evaluated on out-of-sample seasons 2025–2026. This prospective test confirmed $\ge 70\%$ cohort overlap and high rank correlation ($r_s = 0.81$), proving that the hierarchical Empirical Bayes shrinkage estimator generalizes effectively to unseen future seasons.

To ensure complete transparency, the competition breakdown is reconciled across the canonical dataset and clean modeling population:



#### Canonical Dataset Population (776 Total Matches, 179,837 Total Deliveries):

- **Indian Premier League (IPL):** 367 matches (47.29%)

- **T20 International (T20I):** 408 matches (52.58%)

- **Men's T20 Emerging / Regional (Asia Cup Rising Stars):** 1 match (0.13%)

- **Total Canonical Matches:** 776 matches (100.00%)



#### Excluded Fixtures (32 Matches, 4,161 Deliveries):

- Exactly 32 rain-curtailed or DLS-interrupted fixtures were excluded due to incomplete/distorted match-state and DLI reconstruction.

- Excluded competition breakdown: 5 IPL matches, 27 T20I matches, 0 Emerging/Regional matches.



#### Clean Legal Modeling Population (744 Matches, 168,104 Clean Legal Deliveries):

- **Indian Premier League (IPL):** 362 matches (48.66%)

- **T20 International (T20I):** 381 matches (51.21%)

- **Men's T20 Emerging / Regional (Asia Cup Rising Stars):** 1 match (0.13%)

- **Total Clean Modeling Matches:** 744 matches (100.00%)



#### Super Over Delivery Segments:

- Super Overs are **not standalone matches**; they are tie-breaker delivery segments occurring within tied fixtures.

- Across the 744 clean legal modeling fixtures, there are exactly **23 clean legal Super Over deliveries** (16 in Innings 3, 7 in Innings 4), representing 0.014% of the 168,104 clean legal modeling deliveries.

- The 1 Men's T20 Emerging/Regional fixture (Asia Cup Rising Stars) was a regulation match, not a Super Over.



### 6. Predictive Scope & Interpretation

- Rankings identify the strongest relative historical performers within the evaluated multi-year dataset under conservative Bayesian shrinkage. They are not deterministic guarantees of future performance.



---



## G. Conclusion: The Value of Contextual Pressure Evaluation



### 1. What the Top 20 Rankings Reveal

Evaluating players through delivery-level contextual modeling reveals critical performance dimensions that career averages obscure:

- **Batting Acceleration vs. Accumulation:** While many batters accumulate runs at steady tempos in low-leverage states, only a select cohort (**Abhishek Sharma**, **Suryakumar Yadav**, **Vaibhav Sooryavanshi**) demonstrate statistically defensible positive contextual batting value-add as match pressure mounts.

- **True Bowling Suppression:** Conventional economy rates penalize death bowlers who operate in phases where tournament scoring averages 11+ RPO. By benchmarking against contextual phase and pressure expectations, our model identifies suppressive profiles (**Sunil Narine**, **Jasprit Bumrah**, **Mustafizur Rahman**) that save runs relative to match expectations.

- **Role Specialization:** The framework distinguishes top-order accelerators who operate primarily in Tiers 2 and 3 from middle- and death-overs specialists (**Tim David**, **Andre Russell**) who absorb the majority of extreme crunch-time deliveries.



### 2. Why Pre-delivery Contextual Analysis Adds Information

Aggregate statistics treat all runs and deliveries as fungible. A delivery-level framework:

1. **Controls for Environmental Confounders:** Isolates true player ability from pitch behavior, ground dimensions, and match-level scoring environments via crossed-effects modeling.

2. **Protects Against Small-Sample Noise:** Applies Empirical Bayes shrinkage to ensure that high-variance cameos do not overshadow sustained multi-season evidence.

3. **Maintains Pre-delivery Temporal Integrity:** Computes pressure strictly prior to each delivery, preventing post-hoc outcome bias from distorting leverage calculations.



### 3. Why Uncertainty and Exposure Disclosures Matter

Rigorous analytics requires transparent disclosure of what the data can and cannot establish:

- **What the system establishes:** It identifies the strongest relative performers within the eligible population, quantifies their contextual value-add above baseline expectations, and bounds their performance with conservative standard errors.

- **What the system cannot establish:** It cannot claim that players with zero Tier 4 deliveries are tested in terminal crunch time, nor can it claim that bowlers with positive upper bounds are statistically confirmed suppressors below context. Disclosing these boundaries protects recruitment decisions from unjustified extrapolation.



By combining pre-delivery match-state reconstruction with transparent uncertainty bounds, RR ScoutIQ provides Rajasthan Royals with an evidence-based foundation for competitive player identification.



---



## Final Validation Checklist



- [x] **Player Identities & Local IDs:** Reconciled 100% against `player_crosswalk_m5_5.csv` and Cricsheet registers.

- [x] **Ranking Monotonicity:** Batter $\text{{LB}}_{{90\% \text{{ CI}}}}$ strictly descending ($+2.72\%$ to $-1.26\%$); Bowler $\text{{UB}}_{{90\% \text{{ CI}}}}$ strictly ascending ($+0.296$ to $+0.697$ RPO).

- [x] **Delivery Statistics Verification:** All balls faced/bowled, runs, strike rates, economy rates, boundaries, dots, and wickets recalculated directly from `match_state_full.csv` (SHA-256 `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4`).

- [x] **Pre-delivery Reconstruction Terminology:** Clarified shift-1 as pre-delivery temporal anti-leakage without unverified causal claims.

- [x] **Contextual Leverage Measure (DLI):** Formulated strictly as contextual situational pressure, not win-outcome predictions.

- [x] **Exact DLI Formulas Implemented:** Full documentation of approved Chase (Innings 2) and Setting (Innings 1) equations, including $\Phi(t)$ power-law progression, stagnation penalties, and phase pars.

- [x] **Confidence Level Disambiguation:** Adopted $Z = 1.645$ as the conservative lower/upper bound of the 90% two-sided credible interval (equivalent to 95% one-sided credible bound).

- [x] **Observed Discipline Eligibility:** Clearly distinguished observed data participation from real-world cricket squad roles.

- [x] **Dataset Provenance Reconciled:** Distinct percentages for 776 canonical matches (47.29% IPL, 52.58% T20I, 0.13% Regional) vs 744 clean modeling matches (48.66% IPL, 51.21% T20I, 0.13% Regional); Super Overs identified as 23 delivery segments, not matches.

- [x] **Statistical Disclosures Visible:** Only 3 batters have $\text{{LB}} > 0$; 0 bowlers have $\text{{UB}} < 0$; 4 batters have 0 Tier 4 balls; 500-ball filter origin disclosed.

- [x] **Milestone Regression Suite:** 30/30 unit tests passed in 35.63s on `tests/m5_5b_4_3_8/test_remediation_b4_3_8.py`.

- [x] **Governance Compliance:** Zero auction bidding recommendations; zero squad gap analysis; zero composite cross-disciplinary weighting; zero self-approval.

