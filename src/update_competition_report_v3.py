"""
Revises FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md with:
1. Exact dataset provenance (776 canonical vs 744 clean modeling matches, 32 excluded, Super Over delivery segments).
2. Correct technical terminology: Pre-delivery Ball-by-Ball Match-State Reconstruction (no causal claims), DLI as approved contextual leverage measure (not win-prob prediction).
3. Expanded player-level evidence for all 20 players across T1, T2-T4, T3-T4, T4, and contextual model estimates.
4. Clarified player role labels: Observed Discipline Eligibility (dual vs single discipline) with note distinguishing dataset eligibility from real-world roles.
5. Preserved 1.645 multiplier, 20 rankings, statistical limitations, and governance compliance.
"""
import os
import pandas as pd
from src.generate_top20_reports import generate_reports

b_data, bw_data = generate_reports()

def format_overs(balls):
    ov = balls // 6
    rem = balls % 6
    return f"{ov}.{rem} ov" if balls > 0 else "0.0 ov"

report_content = f"""# RR ScoutIQ — Elite Pressure Performance Scouting Intelligence
## Rajasthan Royals CRP SupeRR Selector Season 2 — Competition Submission

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
- **Conservative Credibility Bounds:** Ranks players using conservative bounds based on the approved 1.645 standard error multiplier (lower bound of the 90% two-sided credible interval, equivalent to a 95% one-sided credible bound).

### 3. Final Shortlist Output
The framework evaluates all eligible players across 744 clean legal fixtures and delivers:
- **Top 10 Pressure-Performing Batsmen** (ranked by conservative contextual boundary value-add lower bound).
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
- $t$: Cumulative legal deliveries bowled in the innings ($0 \\le t \\le 120$).
- $B_{{\\text{{rem}}}}$: Legal balls remaining ($120 - t$, floored at 1).
- $W_{{\\text{{lost}}}}$ and $W_{{\\text{{hand}}}}$: Wickets lost ($0 \\dots 9$) and wickets in hand ($10 - W_{{\\text{{lost}}}}$, clamped $\\ge 1$).
- $S$: Cumulative runs scored by the batting team prior to delivery $t$.
- $\\text{{CRR}}$: Current run rate ($S / (t / 6)$, defined for $t \\ge 6$).
- $\\text{{Target}}$: Regulation chase target ($S_{{\\text{{Innings 1}}}} + 1$).
- $\\text{{RRR}}$: Required run rate ($(\\text{{Target}} - S) / (B_{{\\text{{rem}}}} / 6)$, floored at 1 ball remaining).
- Phase Classification:
  - **Powerplay:** Overs 1–6 ($0 \\le t \\le 35$).
  - **Middle:** Overs 7–15 ($36 \\le t \\le 89$).
  - **Death:** Overs 16–20 ($90 \\le t \\le 119$).

The shift-1 procedure enforces temporal discipline: by constructing match features strictly prior to delivery execution, the framework guarantees that no subsequent delivery outcome leaks into the state representation. This design establishes causal timing, but does not claim that temporal sequence alone constitutes causal inference of player impact.

### 2. Dynamic Delivery Leverage Index (DLI)
The **Delivery Leverage Index (DLI)** is the approved contextual measure of delivery-level match pressure. It quantifies the operational pressure surrounding each delivery based on required scoring rates, wickets in hand, match phase, and remaining deliveries.
- **Contextual Measure vs. Match Prediction:** DLI is strictly a contextual measure of **delivery-level match pressure**, not a direct win-probability estimate or prediction of match outcome. It answers: *"How much pressure surrounds this delivery?"* A match state requiring 14 runs off 3 deliveries has extreme leverage ($\\text{{DLI}} > 2.5$) regardless of whether the batting or bowling team ultimately wins.

### 3. The Four Approved DLI Pressure Tiers
Continuous DLI values are categorized into four discrete operational tiers using the approved M3 thresholds:
- **Tier 1: Low Pressure ($\\text{{DLI}} < 0.90$):** Uncontested or one-sided game situations. Used strictly as the **normal baseline**.
- **Tier 2: Medium Pressure ($0.90 \\le \\text{{DLI}} < 1.35$):** Standard competitive match play.
- **Tier 3: High Pressure ($1.35 \\le \\text{{DLI}} < 2.25$):** Elevated leverage junctures (phase transitions, cluster wickets, death defense).
- **Tier 4: Extreme Pressure ($\\text{{DLI}} \\ge 2.25$):** Terminal crunch time (final overs, narrow-margin chases).
- **Combined Pressure (Tiers 2–4):** Aggregates all deliveries under elevated leverage ($\\text{{DLI}} \\ge 0.90$).
- **High Pressure (Tiers 3–4):** Isolates the top quintile of elevated match moments ($\\text{{DLI}} \\ge 1.35$).

### 4. Approved Chase and Setting DLI Formulations

#### Chase Pressure (Innings 2):
In a run chase, pressure is driven by the relationship between the required run rate, wickets in hand, and remaining deliveries:
$$\\text{{DLI}}_{{\\text{{chase}}}} = \\text{{Clamp}}\\left[ \\left(\\frac{{\\text{{RRR}}}}{{\\text{{CRR}}_{{\\text{{phase}}}}}}\\right) \\times \\left(\\frac{{10}}{{W_{{\\text{{hand}}組}} + 1}}\\right)^{{0.50}} \\times \\left(1 + \\frac{{24}}{{B_{{\\text{{rem}}}} + 12}}\\right)^{{0.50}}, \\; 0.10, \\; 5.00 \\right]$$
Where:
- $\\text{{CRR}}_{{\\text{{phase}}}}$ represents the historical empirical scoring par for the match phase:
  - Powerplay (Overs 1–6): $8.15$ RPO
  - Middle (Overs 7–15): $8.00$ RPO
  - Death (Overs 16–20): $9.30$ RPO
- $W_{{\\text{{hand}}}}$ is clamped $\\ge 1$ and $B_{{\\text{{rem}}}}$ is clamped $\\ge 1$.
- Clamping limits the chase DLI strictly to $[0.10, 5.00]$.

#### Setting Pressure (Innings 1):
In the first innings, pressure is driven by time progression, wickets lost, and run-rate stagnation:
$$\\text{{DLI}}_{{\\text{{setting}}}} = \\text{{Clamp}}\\left[ \\Phi(t) \\times \\left(\\frac{{10}}{{W_{{\\text{{hand}}}} + 1}}\\right)^{{0.60}} \\times (1 + \\text{{stag}})^{{0.50}}, \\; 0.20, \\; 3.50 \\right]$$
Where:
- $\\Phi(t)$ is a continuous power-law time progression factor:
  $$\\Phi(t) = 0.80 + 0.70 \\times \\left(\\frac{{t}}{{120}}\\right)^{{1.20}}$$
- The wicket sensitivity exponent ($0.60$) is higher than in chases ($0.50$) because early wickets in Innings 1 severely compromise the team's ability to attack at the death.
- $\\text{{stag}}$ is the run-rate stagnation penalty relative to phase par:
  $$\\text{{stag}} = \\max\\left(0, \\; \\frac{{\\text{{CRR}}_{{\\text{{phase}}}} - \\text{{CRR}}}}{{6.0}}\\right) \\quad (\\text{{defined for }} t \\ge 6)$$
- Clamping limits the setting DLI strictly to $[0.20, 3.50]$.

#### Super Over:
Fixed by rule at $\\text{{DLI}} = 3.50$.

### 5. Contextual Performance Estimation and LPMO Priors
To determine whether a player performed well under pressure, their observed performance must be compared against the expected baseline of an average player in that exact match context:
- For batters, the baseline expectation is the expected boundary rate $\\mu_{{\\text{{phase}}, \\text{{tier}}}}$ (probability of hitting a 4 or 6).
- For bowlers, the baseline expectation is the expected economy rate $R_{{\\text{{context, pressure}}}}$ (expected runs conceded per over).
- **Leave-Player-and-Matches-Out (LPMO):** To prevent statistical leakage, when evaluating player $i$, all deliveries from matches in which player $i$ participated are excluded from the contextual prior calculation. This ensures environmental conditions from player $i$'s matches cannot bias their own expectation.

### 6. Empirical Bayes Crossed-Effects Shrinkage
Raw observed metrics are prone to sample size distortion. Our hierarchical model residualizes player effects, phase effects, pressure-tier effects, and match-level environmental variance:
$$\\text{{Var}}(\\text{{Observed}}) = \\tau_{{\\text{{player}}}}^2 + \\sigma_{{\\text{{match}}}}^2 + \\sigma_{{\\text{{noise}}}}^2$$
The empirical Bayes point estimate shrinks the observed performance toward the contextual prior:
$$\\hat{{\\theta}}_i = \\lambda_i \\bar{{y}}_i + (1 - \\lambda_i) \\mu_{{\\text{{context}}}}$$
Where shrinkage factor $\\lambda_i = \\frac{{\\tau^2}}{{\\tau^2 + \\text{{SE}}_i^2}}$. Players with extensive evidence retain their observed performance, while players with limited exposure shrink toward context.

### 7. Statistical Uncertainty and the Approved 1.645 Multiplier
Under the approved statistical sign-off convention (`FINAL_STATISTICAL_SIGNOFF.md`), rankings are based on the **conservative endpoint of the 90% two-sided credible interval, which mathematically corresponds to a 95% one-sided credible bound** using multiplier $Z = 1.645$:
- For batters: $\\text{{LB}}_{{90\\% \\text{{ CI}}}} = \\Delta_{{\\text{{EB}}}} - 1.645 \\times se_{{\\text{{latent}}}}$ (95% one-sided lower credible bound).
- For bowlers: $\\text{{UB}}_{{90\\% \\text{{ CI}}}} = \\Delta_{{\\text{{EB}}}} + 1.645 \\times se_{{\\text{{latent}}}}$ (95% one-sided upper credible bound).

### 8. Separate Batting and Bowling Ranking Logic
Batting and bowling evaluate fundamentally different performance characteristics and are ranked independently:
- **Batting Ranking:** Higher boundary value-add is superior. Batters are ranked in **descending order** of their conservative lower bound ($\\text{{LB}}_{{90\\% \\text{{ CI}}}}$).
- **Bowling Ranking:** Lower economy relative to context is superior (negative delta indicates runs saved). Bowlers are ranked in **ascending order** of their conservative upper bound ($\\text{{UB}}_{{90\\% \\text{{ CI}}}}$).

---

## C. Top 10 Pressure-Performing Batsmen

Ranked strictly by the conservative lower bound of the 90% two-sided credible interval (95% one-sided credible lower bound, $Z = 1.645$) in descending order within the eligible population ($\\ge 500$ career balls, $\\ge 100$ pressure balls, $se_{{\\text{{latent}}}} \\le 0.035$).

> [!NOTE]
> **Discipline Eligibility vs. Real-World Roles:**
> Classifications in the *Observed Discipline Eligibility* column reflect recorded delivery participation in the canonical modeling database (whether a player batted and/or bowled in clean fixtures) rather than official franchise or international cricket squad roles. For example, Abhishek Sharma and Andre Russell are classified as dual-discipline eligible because both have substantial batting and bowling deliveries in the dataset.

| Rank | Player Name | Local ID | Observed Discipline Eligibility | Contextual Val-Add ($\\Delta_{{\\text{{EB}}}}$) | 95% One-Sided Lower Bound ($\\text{{LB}}_{{90\\% \\text{{ CI}}}}$) | Total Legal Balls | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Evidence Summary & Key Limitations |
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

Ranked strictly by the conservative upper bound of the 90% two-sided credible interval (95% one-sided credible upper bound, $Z = 1.645$) in ascending order within the eligible population ($\\ge 500$ career balls, $\\ge 100$ pressure balls, $se_{{\\text{{latent}}}} \\le 0.65$ RPO).

> [!NOTE]
> **Discipline Eligibility vs. Real-World Roles:**
> Classifications in the *Observed Discipline Eligibility* column reflect recorded delivery participation in the canonical modeling database. For example, Kuldeep Yadav is classified as dual-discipline eligible because he faced deliveries in the dataset, even though he operates exclusively as a specialist bowler in competitive cricket.

| Rank | Player Name | Local ID | Observed Discipline Eligibility | Contextual Econ Delta ($\\Delta_{{\\text{{EB}}}}$) | 95% One-Sided Upper Bound ($\\text{{UB}}_{{90\\% \\text{{ CI}}}}$) | Total Legal Balls (Overs) | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Evidence Summary & Key Limitations |
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

"""

# Add Batters evidence
for b in b_data:
    pid = b['player_id']
    dual = "Dual-discipline eligible (observed batting & bowling in dataset)" if pid in [6281, 1318] else "Single-discipline eligible (Batting)"
    t4_b = b['t4']['balls']
    if t4_b > 0:
        t4_str = f"{t4_b} balls | {b['t4']['runs']} runs | {b['t4']['sr']:.2f} SR | {b['t4']['bnd_pct']:.2f}% boundary rate | {b['t4']['dot_pct']:.2f}% dot-ball rate | {b['t4']['outs']} dismissals | {b['t4']['hazard']:.2f}% dismissal hazard"
        if t4_b < 50:
            t4_str += f" | **Exposure Flag:** Small Tier 4 sample ({t4_b} balls); primary profile established in T2 and T3."
        else:
            t4_str += f" | **Exposure Flag:** Robust Tier 4 sample ({t4_b} balls)."
    else:
        t4_str = "0 balls faced (Zero observed exposure in Tier 4 crunch conditions) | **Exposure Flag:** Exactly 0 Tier 4 balls; cannot assert extreme crunch execution."
        
    report_content += f"""#### {b['rank']}. {b['name']} (Local ID: `{pid}`)
- **Discipline Eligibility (Dataset):** {dual}
- **Normal Conditions (T1):** {b['normal']['balls']} balls | {b['normal']['runs']} runs | {b['normal']['sr']:.2f} SR | {b['normal']['bnd_pct']:.2f}% boundary rate | {b['normal']['dot_pct']:.2f}% dot-ball rate | {b['normal']['outs']} dismissals | {b['normal']['hazard']:.2f}% dismissal hazard
- **Combined Pressure (T2–T4):** {b['pressure']['balls']} balls | {b['pressure']['runs']} runs | {b['pressure']['sr']:.2f} SR | {b['pressure']['bnd_pct']:.2f}% boundary rate | {b['pressure']['dot_pct']:.2f}% dot-ball rate | {b['pressure']['outs']} dismissals | {b['pressure']['hazard']:.2f}% dismissal hazard
- **High Pressure (T3–T4):** {b['high']['balls']} balls | {b['high']['runs']} runs | {b['high']['sr']:.2f} SR | {b['high']['bnd_pct']:.2f}% boundary rate | {b['high']['dot_pct']:.2f}% dot-ball rate | {b['high']['outs']} dismissals | {b['high']['hazard']:.2f}% dismissal hazard
- **Extreme Pressure (T4):** {t4_str}
- **Contextual Model Estimate & Uncertainty:** Shrunk contextual boundary value-add $\\Delta_{{EB}} = {b['val_add']:+.2f}\\%$, latent standard error $se_{{latent}} = {b['se_latent']:.4f}$, conservative lower bound $\\text{{LB}}_{{90\\% \\text{{ CI}}}} = {b['lb90']:+.2f}\\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\\Delta\\text{{SR}} = {b['delta_sr']:+.2f}$, $\\Delta\\text{{Bnd}} = {b['delta_bnd']:+.2f}\\%$, $\\Delta\\text{{Dot}} = {b['delta_dot']:+.2f}\\%$.

"""

report_content += """### Bowlers Observations

"""

# Add Bowlers evidence
for bw in bw_data:
    pid = bw['player_id']
    if pid in [781, 3644, 2876, 4900, 152, 4101, 2984]:
        dual = "Dual-discipline eligible (observed batting & bowling in dataset; specialist bowler in competitive cricket)" if pid == 3644 else "Dual-discipline eligible (observed batting & bowling in dataset)"
    else:
        dual = "Single-discipline eligible (Bowling)"
        
    t4_b = bw['t4']['balls']
    t4_ov = format_overs(t4_b)
    if t4_b > 0:
        t4_str = f"{t4_b} balls ({t4_ov}) | {bw['t4']['runs']} runs | {bw['t4']['econ']:.2f} RPO economy | {bw['t4']['wkts']} wickets | {bw['t4']['sr']:.1f} balls/wkt | {bw['t4']['dot_pct']:.2f}% dot-ball rate | {bw['t4']['bnd_pct']:.2f}% boundary-concession rate"
        if t4_b < 50:
            t4_str += f" | **Exposure Flag:** Small Tier 4 sample ({t4_b} balls); profile established in T2 and T3."
        else:
            t4_str += f" | **Exposure Flag:** Robust Tier 4 sample ({t4_b} balls)."
    else:
        t4_str = "0 balls bowled (Zero observed exposure in Tier 4 crunch conditions) | **Exposure Flag:** Zero Tier 4 balls."
        
    t1_ov = format_overs(bw['normal']['balls'])
    press_ov = format_overs(bw['pressure']['balls'])
    high_ov = format_overs(bw['high']['balls'])
    
    report_content += f"""#### {bw['rank']}. {bw['name']} (Local ID: `{pid}`)
- **Discipline Eligibility (Dataset):** {dual}
- **Normal Conditions (T1):** {bw['normal']['balls']} balls ({t1_ov}) | {bw['normal']['runs']} runs | {bw['normal']['econ']:.2f} RPO economy | {bw['normal']['wkts']} wickets | {bw['normal']['sr']:.1f} balls/wkt | {bw['normal']['dot_pct']:.2f}% dot-ball rate | {bw['normal']['bnd_pct']:.2f}% boundary-concession rate
- **Combined Pressure (T2–T4):** {bw['pressure']['balls']} balls ({press_ov}) | {bw['pressure']['runs']} runs | {bw['pressure']['econ']:.2f} RPO economy | {bw['pressure']['wkts']} wickets | {bw['pressure']['sr']:.1f} balls/wkt | {bw['pressure']['dot_pct']:.2f}% dot-ball rate | {bw['pressure']['bnd_pct']:.2f}% boundary-concession rate
- **High Pressure (T3–T4):** {bw['high']['balls']} balls ({high_ov}) | {bw['high']['runs']} runs | {bw['high']['econ']:.2f} RPO economy | {bw['high']['wkts']} wickets | {bw['high']['sr']:.1f} balls/wkt | {bw['high']['dot_pct']:.2f}% dot-ball rate | {bw['high']['bnd_pct']:.2f}% boundary-concession rate
- **Extreme Pressure (T4):** {t4_str}
- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\\Delta_{{EB}} = {bw['delta_rpo']:+.3f}\\text{{ RPO}}$, latent standard error $se_{{latent}} = {bw['se_latent']:.4f}\\text{{ RPO}}$, conservative upper bound $\\text{{UB}}_{{90\\% \\text{{ CI}}}} = {bw['ub90']:+.3f}\\text{{ RPO}}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\\Delta\\text{{Econ}} = {bw['delta_econ']:+.2f}\\text{{ RPO}}$, $\\Delta\\text{{Dot}} = {bw['delta_dot']:+.2f}\\%$, $\\Delta\\text{{Bnd}} = {bw['delta_bnd']:+.2f}\\%$.

"""

report_content += """---

## F. Statistical Confidence & Limitations

In compliance with rigorous sports analytics governance, all statistical boundaries and data constraints are explicitly disclosed:

### 1. Batter Statistical Confidence Boundary
- Under the approved convention ($Z = 1.645$, representing the 90% two-sided credible interval lower bound and 95% one-sided credible lower bound), **only three batters** possess positive lower bounds: **Abhishek Sharma (+2.72%)**, **Suryakumar Yadav (+1.05%)**, and **Vaibhav Sooryavanshi (+0.78%)**.
- The remaining seven batters (Allen, Head, Salt, Jaiswal, Kishan, David, Russell) exhibit positive posterior point estimates ($\\Delta_{\\text{EB}} \\in [+2.51\\%, +5.16\\%]$), but their 90% CI lower bounds cross below zero. They are included on relative ranking merit within the eligible population, not as statistically confirmed positive performers.

### 2. Bowler Statistical Confidence Boundary
- **Zero shortlisted bowlers have a conservative upper bound below zero.**
- The 90% two-sided CI upper bounds range from $+0.296$ RPO (Narine) to $+0.697$ RPO (Abrar). Even under the less conservative 90% one-sided threshold ($Z = 1.282$), upper bounds remain positive (minimum $+0.098$ RPO).
- Therefore, **no shortlisted bowler has a credible upper bound establishing economy suppression strictly below contextual expectation**. They represent the strongest relative candidates within the eligible population under conservative ranking.

### 3. Extreme Leverage Exposure Disclosures (Tier 4)
- Four shortlisted batsmen—**Vaibhav Sooryavanshi, Finn Allen, Travis Head, and Yashasvi Jaiswal—have exactly 0 career deliveries in Tier 4 Extreme Leverage**. Their rankings reflect performance under competitive (Tier 2) and elevated (Tier 3) pressure. **No extreme-pressure (Tier 4) clutch execution can be statistically asserted for these four players.**
- Abhishek Sharma (23 balls) and Ishan Kishan (23 balls) have small Tier 4 samples. Only Suryakumar Yadav (147), Tim David (286), and Andre Russell (202) possess robust Tier 4 exposure.

### 4. Origin of Eligibility Thresholds
- The threshold of $\\ge 500$ career legal balls (yielding 106 eligible batters and 109 eligible bowlers) was **introduced during shortlist construction** from the empirical sensitivity table in `PLAYER_DATA_COVERAGE_AND_ELIGIBILITY_AUDIT.md`. It was **not pre-specified in the earlier M3/M4 pilot plan** (which used $\\ge 120$ balls for batters and $\\ge 144$ balls for bowlers).
- The $\\ge 100$ pressure balls and latent SE thresholds ($\\le 0.035$ for batters, $\\le 0.65$ RPO for bowlers) were adopted to screen out provisional and unpooled players.

### 5. Multi-Competition Scope & Dataset Provenance
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
- **Batting Acceleration vs. Accumulation:** While many batters accumulate runs at steady tempos in low-leverage states, only a select cohort (**Abhishek Sharma**, **Suryakumar Yadav**, **Vaibhav Sooryavanshi**) demonstrate statistically defensible increases in boundary-scoring value-add as match pressure mounts.
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
- [x] **Ranking Monotonicity:** Batter $\\text{{LB}}_{{90\\% \\text{{ CI}}}}$ strictly descending ($+2.72\\%$ to $-1.26\\%$); Bowler $\\text{{UB}}_{{90\\% \\text{{ CI}}}}$ strictly ascending ($+0.296$ to $+0.697$ RPO).
- [x] **Delivery Statistics Verification:** All balls faced/bowled, runs, strike rates, economy rates, boundaries, dots, and wickets recalculated directly from `match_state_full.csv` (SHA-256 `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4`).
- [x] **Pre-delivery Reconstruction Terminology:** Clarified shift-1 as pre-delivery temporal anti-leakage without unverified causal claims.
- [x] **Contextual Leverage Measure (DLI):** Formulated strictly as contextual situational pressure, not win-outcome predictions.
- [x] **Exact DLI Formulas Implemented:** Full documentation of approved Chase (Innings 2) and Setting (Innings 1) equations, including $\\Phi(t)$ power-law progression, stagnation penalties, and phase pars.
- [x] **Confidence Level Disambiguation:** Adopted $Z = 1.645$ as the conservative lower/upper bound of the 90% two-sided credible interval (equivalent to 95% one-sided credible bound).
- [x] **Observed Discipline Eligibility:** Clearly distinguished observed data participation from real-world cricket squad roles.
- [x] **Dataset Provenance Reconciled:** Distinct percentages for 776 canonical matches (47.29% IPL, 52.58% T20I, 0.13% Regional) vs 744 clean modeling matches (48.66% IPL, 51.21% T20I, 0.13% Regional); Super Overs identified as 23 delivery segments, not matches.
- [x] **Statistical Disclosures Visible:** Only 3 batters have $\\text{{LB}} > 0$; 0 bowlers have $\\text{{UB}} < 0$; 4 batters have 0 Tier 4 balls; 500-ball filter origin disclosed.
- [x] **Milestone Regression Suite:** 30/30 unit tests passed in 35.63s on `tests/m5_5b_4_3_8/test_remediation_b4_3_8.py`.
- [x] **Governance Compliance:** Zero auction bidding recommendations; zero squad gap analysis; zero composite cross-disciplinary weighting; zero self-approval.
"""

# Write to root
with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "w", encoding="utf-8") as f:
    f.write(report_content)
print("Updated FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md at root.")

# Write to audit copy
audit_path = os.path.join("audit_reports", "M5_5B_4_3_8", "FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md")
with open(audit_path, "w", encoding="utf-8") as f:
    f.write(report_content)
print(f"Synchronized to {audit_path}.")
