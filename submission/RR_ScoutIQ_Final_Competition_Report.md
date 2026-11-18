# RR ScoutIQ — Pressure Performance Intelligence System
## Round 1 Methodology & Official Player Rankings Report
### Rajasthan Royals CRP SupeRR Selector Season 2 (IPL 2027 Auction Strategy)

---

**Project Title:** RR ScoutIQ — Contextual Pressure Performance Scouting System  
**Competition:** Rajasthan Royals CRP SupeRR Selector Season 2  
**Challenge Track:** Round 1 Problem Statement — *Identify the Most Reliable Players Under Pressure*  
**Submission Date:** November 2026  
**Authoritative Cohort:** Full Tournament Corpus 2022–2026 (744 Clean Matches, 168,104 Clean Legal Deliveries)  
**Primary Deliverables:** Official Top 10 Batters, Official Top 10 Bowlers, Interactive Analytics Platform, and Methodology Report  
**Interactive Platform:** [https://taupe-dodol-c84063.netlify.app/](https://taupe-dodol-c84063.netlify.app/)  
**Verified Source Code:** [https://github.com/rithvik-30/RRSCOUTIQ](https://github.com/rithvik-30/RRSCOUTIQ)  

---

## 1. Executive Summary

### 1.1 The Operational Problem in Modern T20 Recruitment
In contemporary franchise cricket recruitment, talent identification relies overwhelmingly on gross aggregate statistics: career batting averages, overall strike rates, boundary percentages, and raw bowling economy rates. While these traditional metrics effectively summarize the volume of run accumulation and containment, they fail to answer the most critical operational question facing the Rajasthan Royals management in tournament cricket:

> **How does a player perform when the match is on the line?**

Standard aggregate career metrics suffer from three foundational analytical defects:
1. **Context Blindness:** A boundary hit during a low-stakes dead rubber or during an uncontested middle-overs cruise is weighted identically to a boundary hit requiring 18 runs off the final 8 deliveries against elite death bowling.
2. **Phase & Resource Conflation:** A spin bowler conceding 7.50 runs per over (RPO) in low-leverage middle overs appears superior on paper to a pace bowler conceding 8.50 RPO during the 19th and 20th overs, even though tournament par at the death exceeds 11.20 RPO.
3. **Small-Sample Volatility:** Short, high-variance cameos can artificially inflate raw rates, making volatile, low-exposure players appear comparable to established performers who consistently absorb high-leverage deliveries.

### 1.2 The RR ScoutIQ Solution
**RR ScoutIQ** resolves these failures through an audited, delivery-level Bayesian statistical framework that evaluates every ball under pre-delivery match leverage, residualizes environmental confounders, applies Empirical Bayes shrinkage, and ranks players by conservative credibility bounds.

Rather than treating pressure as a subjective trait or an unobservable psychological state, RR ScoutIQ models pressure as an **ex-ante (pre-delivery) match-state condition** defined by the **Dynamic Delivery Leverage Index (DLI)**. DLI measures the marginal win-probability sensitivity of each ball using only information available before the bowler enters their delivery stride: required run rate ($RRR$), balls remaining ($B_{\text{rem}}$), wickets in hand ($W_{\text{hand}}$), match phase, venue scoring baselines, and innings context.

### 1.3 Core Methodology & Findings
1. **Match-State Reconstruction:** Reconstructed 168,104 clean legal deliveries across 744 matches (362 IPL, 381 T20Is, 1 Regional Emerging fixture) from 2022 to 2026, categorizing deliveries into four discrete operational leverage tiers: Low (T1: $\text{DLI} < 0.90$), Medium (T2: $0.90 \le \text{DLI} < 1.35$), High (T3: $1.35 \le \text{DLI} < 2.25$), and Extreme Crunch (T4: $\text{DLI} \ge 2.25$).
2. **Discipline-Specific Objectives:**
   - **Batters:** Evaluated on **Contextual Boundary-Rate Value-Add ($\Delta_{\text{EB}}$)**—the percentage-point elevation in boundary conversion under pressure relative to situational expectation. Boundary hitting is the primary objective because boundaries are the non-negotiable currency of winning tight T20 chases; strike rate serves as an external empirical validation metric.
   - **Bowlers:** Evaluated on **Contextual Economy Suppression ($\Delta_{\text{EB}}$ in RPO)**—the reduction in runs conceded per over under pressure relative to phase/venue baseline.
3. **Hierarchical Empirical Bayes Regularization:** Applied crossed-effects Bayesian shrinkage calibrated via Leave-Player-and-Matches-Out (LPMO) priors. This penalizes estimation uncertainty ($se_{\text{latent}}$), shrinking volatile small-sample performers toward the league mean while retaining verified signals for durable volume performers.
4. **Conservative Credibility Ranking:** Batters are ranked descending by their 95% one-sided lower posterior credible bound ($\text{LB}_{90\% \text{ CI}}$); bowlers are ranked ascending by their 95% one-sided upper posterior credible bound ($\text{UB}_{90\% \text{ CI}}$).

### 1.4 Official Shortlist Output
- **Top 10 Batters:** **#1 Abhishek Sharma (`6281`)**, **#2 Suryakumar Yadav (`1699`)**, **#3 Vaibhav Sooryavanshi (`50284`)**, #4 Finn Allen (`4847`), #5 Travis Head (`2367`), #6 Phil Salt (`5553`), #7 Yashasvi Jaiswal (`6819`), #8 Ishan Kishan (`4117`), #9 Tim David (`6396`), #10 Andre Russell (`1318`).
- **Top 10 Bowlers:** **#1 Sunil Narine (`781`)**, **#2 Jasprit Bumrah (`2933`)**, **#3 Mustafizur Rahman (`4373`)**, #4 Kuldeep Yadav (`3644`), #5 Axar Patel (`2876`), #6 Wanindu Hasaranga (`4900`), #7 Ravindra Jadeja (`152`), #8 Mitchell Santner (`4101`), #9 Sikandar Raza (`2984`), #10 Abrar Ahmed (`5979`).

---

## 2. Problem Understanding & Objectives

The official competition brief for Round 1 of the Rajasthan Royals CRP SupeRR Selector Season 2 hackathon defines the central task:
> *"Build a data-driven system that measures how batters and bowlers perform in high-pressure match situations compared with their usual performance levels. Use your system to identify and rank the players who deliver most consistently when it matters."*

To satisfy this challenge with broadcast-grade rigor, RR ScoutIQ was built around four foundational analytical pillars:

```
+---------------------------------------------------------------------------------------------------+
|                                  THE FOUR PILLARS OF RR SCOUTIQ                                   |
+---------------------------------------------------------------------------------------------------+
| 1. OBJECTIVE PRESSURE      | Causal, pre-delivery Dynamic Leverage Index (DLI) categorizing       |
|    DEFINITION              | matches into 4 operational tiers without outcome look-ahead bias.     |
+----------------------------+----------------------------------------------------------------------+
| 2. CONTEXTUAL PERFORMANCE  | Compares pressure execution against situational expectation          |
|    MEASUREMENT             | rather than unadjusted raw career averages.                          |
+----------------------------+----------------------------------------------------------------------+
| 3. FAIR SAMPLE-SIZE        | Crossed-effects Empirical Bayes shrinkage to prevent small-sample    |
|    CREDIBILITY             | volatility from dominating established high-volume performers.       |
+----------------------------+----------------------------------------------------------------------+
| 4. RIGOROUS PROSPECTIVE    | Verified out-of-sample predictive power via walk-forward evaluation  |
|    VALIDATION              | across unseen future tournament seasons (2025 and 2026).             |
+---------------------------------------------------------------------------------------------------+
```

### Key Deliverable Mapping
The competition mandates two primary components:
1. **Deliverable 01: Player Rankings:** Two ordered Top 10 lists (batters and bowlers), ranked from 1 to 10, populated with unique player identities ready for direct Unstop dropdown selection.
2. **Deliverable 02: Methodology Report:** A transparent, comprehensive document explaining the pressure formulation, performance metrics, fair sample-size handling, evidence tables, and model limitations.

---

## 3. Data Sources, Cleaning & Match-State Reconstruction

### 3.1 Historical Scope & Dataset Provenance
The canonical database comprises ball-by-ball records from professional T20 cricket from **January 22, 2022 to November 1, 2026**.

To ensure absolute audit transparency, the match population is reconciled as follows:
- **Canonical Dataset Population:** Exactly **776 matches** (179,837 total deliveries).
  - *Indian Premier League (IPL):* 367 matches (47.29%)
  - *T20 International (T20I):* 408 matches (52.58%)
  - *Men's T20 Regional / Emerging (Asia Cup Rising Stars):* 1 match (0.13%)
- **Excluded Fixtures (32 Matches, 4,161 Deliveries):** Exactly 32 rain-curtailed or Duckworth-Lewis-Stern (DLS) interrupted fixtures were excluded. In weather-interrupted fixtures, shifting targets and truncated over allocations distort resource exhaustion curves and prevent faithful pre-delivery match-state reconstruction.
- **Clean Legal Modeling Population:** Exactly **744 matches** (168,104 clean legal deliveries).
  - *Indian Premier League (IPL):* 362 matches (48.66%)
  - *T20 International (T20I):* 381 matches (51.21%)
  - *Men's T20 Regional / Emerging:* 1 match (0.13%)
- **Super Over Delivery Segments:** Exactly **23 clean legal Super Over deliveries** (16 in Innings 3, 7 in Innings 4 across tied fixtures). Super Overs are tie-breaker segments within regulation matches, not standalone matches. All 23 deliveries are classified by definition into Tier 4 ($DLI = 3.0$).

### 3.2 Delivery-Level Cleaning & Accounting
Raw delivery records were subjected to strict cricket-rules reconciliation:
- **Total Deliveries Analyzed:** 179,837 balls.
- **Clean Legal Balls:** 172,076 balls (95.68%).
- **Wides:** 6,976 balls (3.88%) — excluded from bowler legal ball count and batter balls faced, but debited to bowler runs and team total.
- **No-Balls:** 785 balls (0.44%) — debited to bowler runs and team score; free-hit deliveries tracked.
- **Overlapping Irregularities:** Exactly 0 overlapping balls ($172,076 + 6,976 + 785 = 179,837$).

### 3.3 Entity Resolution & Eligibility Screening
Player identities were unified across competitions using a deterministic crosswalk (`data/enriched/player_crosswalk_m5_5.csv`), resolving all spelling variants and Cricsheet player IDs.

To prevent small-sample cameos from distorting tournament rankings, objective eligibility qualification gates were enforced:
- **Batters:** Minimum 500 career legal balls, minimum 100 combined pressure deliveries (Tiers 2–4), and latent standard error $se_{\text{latent}} \le 0.035$ (yielding 106 qualified batters).
- **Bowlers:** Minimum 500 career legal balls (83.2 overs), minimum 100 combined pressure deliveries (minimum 20 spells under pressure), and latent standard error $se_{\text{latent}} \le 0.65$ RPO (yielding 109 qualified bowlers).

---

## 4. Defining Pressure: The Dynamic Delivery Leverage Index (DLI)

### 4.1 Plain-Language Conceptual Overview
Pressure in T20 cricket is not a static property of the death overs, nor is it captured by generic career averages. A team chasing 12 runs off 30 balls with 8 wickets in hand is experiencing minimal pressure, even though it is the 16th over. Conversely, a team chasing 50 runs off 24 balls with 4 wickets in hand is under intense pressure.

The **Dynamic Delivery Leverage Index (DLI)** measures the **operational leverage** of each delivery. It quantifies how much the probability of winning hinges on the outcome of that single ball, calculated strictly using information observable *before* the ball is bowled.

### 4.2 Mathematical Formulation of DLI

#### Chase Pressure (Innings 2):
In run chases, pressure is governed by required run rate ($RRR$), resource exhaustion (wickets in hand), and delivery decay:

$$\text{DLI}_{\text{chase}} = \left( \frac{RRR}{PAR_{\text{chase}}} \right) \times \left( \frac{10}{W_{\text{hand}}} \right)^{0.5} \times \left( 1 + \frac{B_{\text{rem}}}{120} \right)$$

Where:
- $RRR = \frac{\text{Runs Required}}{\text{Balls Remaining}} \times 6$
- $PAR_{\text{chase}} = 8.50$ RPO (empirical baseline for competitive run chases)
- $W_{\text{hand}} = 10 - \text{Wickets Lost}$ (constrained $\ge 1$)
- $B_{\text{rem}} = 120 - \text{Balls Bowled}$
- When $B_{\text{rem}} \le 18$ and $RRR > 12.0$, an exponential crunch multiplier ($1.25 \times$) activates to capture terminal win-probability volatility.

#### Setting Pressure (Innings 1):
In the first innings, absolute targets do not exist. Pressure is governed by pace progression relative to venue par, resource preservation, and scoring stagnation:

$$\text{DLI}_{\text{setting}} = \left( \frac{PAR_{\text{phase}}}{CRR_{\text{prog}}} \right) \times \left( \frac{10}{W_{\text{hand}}} \right)^{0.3} \times \text{Pen}_{\text{stag}}$$

Where:
- $PAR_{\text{phase}}$ reflects phase-specific expectations: Powerplay ($8.15$), Middle ($8.00$), Death ($9.30$ RPO).
- $CRR_{\text{prog}}$ is the rolling current run rate over the preceding 18 legal balls.
- $\text{Pen}_{\text{stag}} = 1 + 0.05 \times \text{Dot Count}_{(\text{last 12 balls})}$.

### 4.3 The Four Operational Leverage Tiers
Every delivery in the canonical database is mapped into one of four discrete operational tiers:

```
+---------------------------------------------------------------------------------------------------+
|                                  THE FOUR OPERATIONAL DLI TIERS                                   |
+---------------------------------------------------------------------------------------------------+
| Tier 1: Low Leverage / Normal Baseline   | DLI < 0.90       | Low-leverage consolidation / chases |
+------------------------------------------+------------------+-------------------------------------+
| Tier 2: Medium / Competitive Leverage    | 0.90 <= DLI < 1.35| Standard competitive match play    |
+------------------------------------------+------------------+-------------------------------------+
| Tier 3: High Leverage                    | 1.35 <= DLI < 2.25| Elevated match-defining phases     |
+------------------------------------------+------------------+-------------------------------------+
| Tier 4: Extreme Crunch Leverage          | DLI >= 2.25      | Critical terminal game-state cliff  |
+---------------------------------------------------------------------------------------------------+
```
Combined Pressure is defined as the union of **Tiers 2, 3, and 4** ($\text{DLI} \ge 0.90$), while High Pressure represents **Tiers 3 and 4** ($\text{DLI} \ge 1.35$).

### 4.4 Causal Role of CSPM & First-Innings Death-Over Limitations
- **Ex-Ante Causal Discipline:** The Contextual State Pressure Model (CSPM) evaluates match state strictly *prior* to delivery execution. Post-delivery events (runs scored, wickets taken) are evaluated *conditionally* against the pre-delivery match state, eliminating look-ahead bias.
- **First-Innings Death-Over Calibration Limitation:** In the first innings (overs 16–20), setting DLI relies on resource consumption par curves rather than direct win-probability cliffs. When the batting team reaches over 17 with 8–9 wickets in hand, setting DLI approaches an asymptotic ceiling ($DLI \approx 2.50$). Consequently, first-innings death bowling leverage may be moderately under-represented relative to intense second-innings chases ($DLI \ge 3.0$). This boundary condition is formally acknowledged as an operational property of setting leverage in T20 cricket.

---

## 5. Measuring Performance Under Pressure

### 5.1 Batting Performance Objective: Contextual Boundary Value-Add
Why boundary rate over raw strike rate? In modern T20 cricket, tight matches are won by clearing the ropes, not by rotating singles. When required run rates escalate beyond 11.0 RPO, a batter who rotates singles at 120 SR actively harms win probability, whereas a batter who hits boundaries on 30% of deliveries drives winning outcomes. Strike rate serves as a secondary empirical validation metric (+7.63 SR under pressure for Abhishek Sharma), not the selection objective.

The contextual boundary rate model computes expected boundary probability per delivery:

$$\mathbb{E}[\text{Boundary}_{i,b}] = \text{logit}^{-1}\left( \beta_0 + \alpha_{\text{phase}(b)} + \gamma_{\text{tier}(b)} + \delta_{\text{venue}(b)} \right)$$

The batter's contextual value-add is the empirical difference:

$$\Delta_{\text{EB}} = \hat{p}_{\text{bnd, pressure}} - \bar{p}_{\text{bnd, baseline}}$$

### 5.2 Bowling Performance Objective: Contextual Economy Suppression
For bowlers, run containment under pressure is the defining metric. Raw economy rates unfairly penalize death bowlers who bowl in phases where par exceeds 11.0 RPO. RR ScoutIQ evaluates bowlers on **Contextual Economy Delta ($\Delta_{\text{EB}}$ in RPO)** relative to phase and venue par:

$$\Delta_{\text{EB}} = \hat{\text{Econ}}_{\text{pressure}} - \bar{\text{Econ}}_{\text{baseline}}$$

A negative delta indicates runs saved below situational expectation (e.g., Sunil Narine's $-0.605$ RPO delta).

---

## 6. Statistical Reliability & Fair Comparison

### 6.1 Hierarchical Empirical Bayes Shrinkage
Evaluating players purely on sample averages creates severe distortions: a player who faced 120 balls and hit 10 boundaries can appear superior to an established star who faced 2,000 balls.

To ensure fair comparisons across disparate sample sizes, RR ScoutIQ applies **crossed-effects Empirical Bayes shrinkage**:

$$\hat{\theta}_i = \lambda_i \bar{x}_i + (1 - \lambda_i) \mu_0$$

Where the shrinkage weight $\lambda_i$ is determined by the ratio of true across-player variance $\tau^2$ to individual measurement error:

$$\lambda_i = \frac{\tau^2}{\tau^2 + \frac{\sigma_i^2}{n_i}} \in [0, 1]$$

- For players with massive exposure ($n_i > 2,000$), $\lambda_i \to 1.0$ (their observed performance is trusted).
- For players with smaller samples ($n_i \approx 500$), $\lambda_i \approx 0.65$ (their estimate is shrunk toward the league prior $\mu_0$).

Priors were estimated using Leave-Player-and-Matches-Out (LPMO) cross-validation to prevent self-contamination.

### 6.2 Conservative Credibility Ranking Bounds
To protect Rajasthan Royals recruitment from small-sample variance, players are ranked not by point estimates, but by **conservative credibility bounds**:

- **Batters Ranked by 95% One-Sided Lower Credible Bound ($\text{LB}_{90\% \text{ CI}}$):**
  $$\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$$
  *(Descending order; higher is superior. Represents a 95% one-sided lower posterior credible bound / endpoint of a central 90% credible interval).*
  
- **Bowlers Ranked by 95% One-Sided Upper Credible Bound ($\text{UB}_{90\% \text{ CI}}$):**
  $$\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$$
  *(Ascending order; lower is superior. Represents a 95% one-sided upper posterior credible bound / ceiling on run leakage).*

> [!NOTE]
> **Statistical Disclosure on Bowler Upper Bound:**
> Ranking bowlers by ascending $\text{UB}_{90\%}$ minimizes the credible ceiling on expected run concession. It does **not** prove that a bowler's economy delta is guaranteed to be strictly negative, as all 10 shortlisted bowlers maintain positive upper bounds ($+0.296$ to $+0.697$ RPO) due to residual estimation variance.

---

## 7. Official Final Player Rankings & Evidence

### 7.1 Official Top 10 Batters (Full 2022–2026 Cohort)
*Ranked by 95% one-sided lower posterior credible bound ($\text{LB}_{90\% \text{ CI}}$) in descending order within the qualified population ($N \ge 500$ career balls, $N_{\text{press}} \ge 100$, $se_{\text{latent}} \le 0.035$).*

| Rank | Player Name | Local ID | Observed Role Eligibility | Contextual Val-Add ($\Delta_{\text{EB}}$) | 95% One-Sided Lower Bound ($\text{LB}_{90\%}$) | Total Legal Balls | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Status Classification |
|:---:|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **#1** | **Abhishek Sharma** | `6281` | Dual-discipline eligible | **+6.70%** | **+2.72%** | 2,136 | 1,427 | 435 | 23 | **Confirmed Positive Value-Add** |
| **#2** | **Suryakumar Yadav** | `1699` | Single-discipline (Batting) | **+4.50%** | **+1.05%** | 2,646 | 2,367 | 1,137 | 147 | **Confirmed Positive Value-Add** |
| **#3** | **Vaibhav Sooryavanshi** | `50284` | Single-discipline (Batting) | **+6.31%** | **+0.78%** | 561 | 392 | 87 | 0 | **Confirmed Positive Value-Add** |
| **#4** | **Finn Allen** | `4847` | Single-discipline (Batting) | **+5.16%** | **-0.07%** | 804 | 421 | 71 | 0 | Relative Ranking Leader |
| **#5** | **Travis Head** | `2367` | Single-discipline (Batting) | **+4.32%** | **-0.18%** | 1,087 | 665 | 146 | 0 | Relative Ranking Leader |
| **#6** | **Phil Salt** | `5553` | Single-discipline (Batting) | **+3.58%** | **-0.75%** | 1,497 | 1,012 | 280 | 45 | Relative Ranking Leader |
| **#7** | **Yashasvi Jaiswal** | `6819` | Single-discipline (Batting) | **+3.03%** | **-0.78%** | 1,774 | 1,181 | 293 | 0 | Relative Ranking Leader |
| **#8** | **Ishan Kishan** | `4117` | Single-discipline (Batting) | **+2.51%** | **-0.90%** | 2,314 | 1,955 | 621 | 23 | Relative Ranking Leader |
| **#9** | **Tim David** | `6396` | Single-discipline (Batting) | **+3.43%** | **-1.00%** | 1,154 | 1,077 | 902 | 286 | Relative Ranking Leader |
| **#10** | **Andre Russell** | `1318` | Dual-discipline eligible | **+3.70%** | **-1.26%** | 707 | 687 | 626 | 202 | Relative Ranking Leader |

#### Key Batter Insights:
- **Abhishek Sharma (#1):** Highest verified contextual value-add ($+6.70\%$) and strongest lower bound ($+2.72\%$). Elevates strike rate by $+7.63$ under pressure (186.19 SR) while reducing dot balls by $9.51\%$. Primary sample established in Tiers 2 and 3; small Tier 4 exposure (23 balls).
- **Suryakumar Yadav (#2):** Elite volume and proven crunch execution. 2,367 pressure balls with 147 balls in Tier 4 Extreme Crunch, accelerating to 214.97 SR with a modest $4.18\%$ dismissal hazard.
- **Vaibhav Sooryavanshi (#3):** Highest raw boundary conversion ($37.50\%$) and pressure strike rate ($220.92$ SR). *Limitation: Close to sample size eligibility cutoff (561 balls); 0 Tier 4 balls.*

---

### 7.2 Official Top 10 Bowlers (Full 2022–2026 Cohort)
*Ranked by 95% one-sided upper posterior credible bound ($\text{UB}_{90\% \text{ CI}}$) in ascending order within the qualified population ($N \ge 500$ career balls, $N_{\text{press}} \ge 100$, $se_{\text{latent}} \le 0.65$ RPO).*

| Rank | Player Name | Local ID | Observed Role Eligibility | Contextual Econ Delta ($\Delta_{\text{EB}}$) | 95% One-Sided Upper Bound ($\text{UB}_{90\%}$) | Total Legal Balls (Overs) | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Status Classification |
|:---:|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **#1** | **Sunil Narine** | `781` | Dual-discipline eligible | **-0.605 RPO** | **+0.296 RPO** | 1,533 (255.3 ov) | 1,394 | 741 | 158 | **Top Relative Suppressor** |
| **#2** | **Jasprit Bumrah** | `2933` | Single-discipline (Bowling) | **-0.538 RPO** | **+0.393 RPO** | 1,594 (265.4 ov) | 1,338 | 836 | 256 | **Top Relative Suppressor** |
| **#3** | **Mustafizur Rahman** | `4373` | Single-discipline (Bowling) | **-0.326 RPO** | **+0.592 RPO** | 1,414 (235.4 ov) | 1,247 | 756 | 267 | **Top Relative Suppressor** |
| **#4** | **Kuldeep Yadav** | `3644` | Dual-discipline eligible | **-0.213 RPO** | **+0.595 RPO** | 1,878 (313.0 ov) | 1,811 | 1,074 | 216 | **Top Relative Suppressor** |
| **#5** | **Axar Patel** | `2876` | Dual-discipline eligible | **-0.150 RPO** | **+0.651 RPO** | 2,484 (414.0 ov) | 2,287 | 1,273 | 255 | **Top Relative Suppressor** |
| **#6** | **Wanindu Hasaranga** | `4900` | Dual-discipline eligible | **-0.219 RPO** | **+0.652 RPO** | 1,789 (298.1 ov) | 1,562 | 903 | 184 | **Top Relative Suppressor** |
| **#7** | **Ravindra Jadeja** | `152` | Dual-discipline eligible | **-0.156 RPO** | **+0.655 RPO** | 1,355 (225.5 ov) | 1,312 | 743 | 127 | **Top Relative Suppressor** |
| **#8** | **Mitchell Santner** | `4101` | Dual-discipline eligible | **-0.245 RPO** | **+0.656 RPO** | 1,725 (287.3 ov) | 1,526 | 839 | 213 | **Top Relative Suppressor** |
| **#9** | **Sikandar Raza** | `2984` | Dual-discipline eligible | **-0.274 RPO** | **+0.670 RPO** | 839 (139.5 ov) | 719 | 343 | 28 | **Top Relative Suppressor** |
| **#10** | **Abrar Ahmed** | `5979` | Single-discipline (Bowling) | **-0.304 RPO** | **+0.697 RPO** | 740 (123.2 ov) | 646 | 424 | 136 | **Top Relative Suppressor** |

#### Methodological Note: Axar Patel (#5) vs. Wanindu Hasaranga (#6)
A critical insight in empirical Bayesian ranking is that **raw point estimates and uncertainty-adjusted bounds can produce different player orders**:
- Wanindu Hasaranga holds a more negative raw point estimate ($\Delta_{\text{EB}} = -0.219$ RPO) than Axar Patel ($-0.150$ RPO).
- However, Axar Patel absorbed **2,484 deliveries (414.0 overs)** compared to Hasaranga's 1,789 balls.
- Axar's massive volume yields a substantially lower latent standard error ($0.4868$ vs. $0.5293$ RPO), resulting in a tighter conservative upper bound ($\text{UB}_{90\%} = +0.651$ vs. $+0.652$ RPO).
- Axar Patel is therefore ranked strictly at **Rank #5** and Wanindu Hasaranga at **Rank #6**, ensuring that sample reliability and defensive certainty are rewarded.

---

## 8. Validation & Prospective Out-of-Sample Evidence

### 8.1 Production-Faithful Walk-Forward Evaluation
To certify that RR ScoutIQ genuinely isolates true skill rather than overfitting to retrospective data, a rigorous walk-forward out-of-sample evaluation was conducted across two temporal splits:
- **Window A:** Trained strictly on historical matches through 2024; prospectively evaluated on out-of-sample season **2025**.
- **Window B:** Trained strictly on historical matches through 2025; prospectively evaluated on out-of-sample season **2026**.

Player cohorts selected by the model were benchmarked against:
1. **League Average Benchmark:** All deliveries bowled in the prospective season.
2. **Eligible Non-Selected Benchmark:** Qualified players who met eligibility thresholds but were not selected in the Top 10.

### 8.2 Statistical Significance & Holm-Bonferroni Correction
In compliance with rigorous statistical standards, two-sided p-values were computed using 10,000 match-clustered block-bootstrap replications, followed by **Holm-Bonferroni step-down family-wise error rate control**:

```
+---------------------------------------------------------------------------------------------------+
|                        PROSPECTIVE OUT-OF-SAMPLE VALIDATION BENCHMARK RESULTS                     |
+---------------------------------------------------------------------------------------------------+
| Comparison Benchmark               | Metric & Observed Effect   | 95% Conf. Interval | Raw p  | Holm p | Status      |
+------------------------------------+----------------------------+--------------------+--------+--------+-------------+
| 2025 Batters vs. League            | +5.89% Boundary Rate Diff  | [+4.26%, +7.57%]   | 0.0001 | 0.0008 | SIGNIFICANT |
| 2025 Batters vs. Non-Selected      | +4.25% Boundary Rate Diff  | [+2.31%, +6.21%]   | 0.0001 | 0.0008 | SIGNIFICANT |
| 2026 Batters vs. League            | +5.62% Boundary Rate Diff  | [+3.24%, +7.99%]   | 0.0001 | 0.0008 | SIGNIFICANT |
| 2026 Batters vs. Non-Selected      | +4.93% Boundary Rate Diff  | [+2.26%, +7.60%]   | 0.0005 | 0.0025 | SIGNIFICANT |
| 2025 Bowlers vs. Non-Selected      | -0.68 RPO Economy Diff     | [-1.16, -0.19]     | 0.0071 | 0.0284 | SIGNIFICANT |
| 2025 Bowlers vs. League            | -0.52 RPO Economy Diff     | [-0.91, -0.10]     | 0.0117 | 0.0351 | SIGNIFICANT |
| 2026 Bowlers vs. League            | -0.53 RPO Economy Diff     | [-1.06, +0.04]     | 0.0572 | 0.1144 | NON-SIG     |
| 2026 Bowlers vs. Non-Selected      | -0.56 RPO Economy Diff     | [-1.19, +0.13]     | 0.1016 | 0.1144 | NON-SIG     |
+---------------------------------------------------------------------------------------------------+
```

### 8.3 Key Inferential Takeaways
- **6 of 8 Comparisons Statistically Significant Post-Holm:** Batter boundary acceleration achieved overwhelming statistical significance in both prospective seasons ($p_{\text{Holm}} \le 0.0025$). Bowler run containment achieved significance in 2025 ($p_{\text{Holm}} \le 0.0351$).
- **Honest Scientific Reporting:** 2026 bowler comparisons were directionally strong ($-0.53$ and $-0.56$ RPO savings), but did not achieve nominal $0.05$ significance post-Holm due to smaller sample sizes in the final season.
- **Prospective Validation vs. Final Submissions:** Walk-forward testing provides prospective proof of model architecture validity, while the official final Top 10 lists represent the complete retrospective 2022–2026 evaluation to give Rajasthan Royals the full power of all historical data for the IPL 2027 Auction.

---

## 9. Limitations & Responsible Scouting Interpretation

1. **Setting Leverage Ceiling:** In first-innings death overs (overs 16–20), DLI asymptotes near $2.50$ when wickets in hand remain high, moderately underestimating extreme pressure relative to run chases.
2. **Uncertainty Bounds & Zero Exposures:** Four shortlisted batters (Vaibhav Sooryavanshi, Finn Allen, Travis Head, Yashasvi Jaiswal) have 0 career deliveries in Tier 4 Extreme Crunch; their rankings reflect excellence in Tiers 2 and 3. Furthermore, all 10 bowlers have positive upper bounds, indicating relative cohort leadership rather than deterministic containment guarantees.
3. **Multi-Competition Blending:** The dataset combines IPL (48.66%) and T20 International cricket (51.21%). While entity crosswalks and venue adjustments normalize these environments, tactical differences (such as the IPL Impact Player rule) slightly alter boundary baseline distributions.
4. **Correlation vs. Causation:** Observed pressure performance reflects historical selection under specific tactical match states. Rankings should serve as an analytical decision-support tool alongside qualitative scouting and biomechanical evaluation, not as a replacement for human judgment.

---

## 10. Conclusion & Strategic Auction Recommendations

RR ScoutIQ delivers a mathematically defensible, contextually grounded, and out-of-sample validated intelligence engine for the Rajasthan Royals recruitment team.

### Strategic Shortlist Takeaways:
1. **Target Confirmed Positive Batters:** **Abhishek Sharma** and **Suryakumar Yadav** represent the elite tier of modern T20 pressure hitters—both demonstrate statistically confirmed positive boundary value-add under high pressure with substantial delivery volume.
2. **Defensive Bowling Anchors:** **Sunil Narine** and **Jasprit Bumrah** are the premier run-suppression assets in global cricket, consistently suffocating scoring in Tier 4 crunch time (conceding under 6.70 RPO in the death phase).
3. **High-Ceiling Emerging Targets:** **Vaibhav Sooryavanshi** and **Finn Allen** offer extraordinary boundary value-add potential, provided their deployment is managed in phases where their aggressive profiles maximize win probability.

---

## Technical Appendix

### Appendix A: Dynamic Leverage Index (DLI) Pseudocode
```python
def compute_dli(row):
    innings = row['innings']
    b_rem = row['balls_remaining']
    w_hand = max(1, 10 - row['wickets_lost'])
    
    if innings == 2:
        rrr = (row['runs_required'] / max(1, b_rem)) * 6.0
        par_chase = 8.50
        leverage = (rrr / par_chase) * ((10.0 / w_hand) ** 0.5) * (1.0 + (b_rem / 120.0))
        if b_rem <= 18 and rrr > 12.0:
            leverage *= 1.25
    else:
        phase = row['phase'] # Powerplay, Middle, Death
        par_phase = 8.15 if phase == 'PP' else (8.00 if phase == 'MID' else 9.30)
        crr_prog = max(4.0, row['rolling_crr_18b'])
        pen_stag = 1.0 + (0.05 * row['dot_balls_last_12'])
        leverage = (par_phase / crr_prog) * ((10.0 / w_hand) ** 0.3) * pen_stag
        
    return min(3.50, max(0.20, leverage))
```

### Appendix B: Canonical Dataset Provenance & Hash Verification
- **Canonical Dataset Location:** `data/processed/m5_3/match_state_full.csv`
- **Canonical Dataset SHA-256 Hash:** `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4`
- **Frozen Competition Reference Report:** `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`
- **Competition Report SHA-256 Hash:** `0e0a11f87622dbeed44c3d918f37c5c9de2f2be8b22ac180099b5add1b882a1d`
- **Full Repository Test Suite:** 116 passed across all governance gates.
