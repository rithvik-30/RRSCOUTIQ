# RR ScoutIQ — Phase 5.2: Pressure Exposure and Sample Adequacy Audit

**Document Reference**: `research/phase5/PHASE_5_2_PRESSURE_EXPOSURE_AUDIT.md`  
**Audit Team**: Senior Cricket Analytics Research Group  
**Status**: APPROVED & FINALIZED  
**Evaluation Scope**: In-Depth Exposure Profiling, Phase Concentration, Temporal Volatility, and Sample Adequacy for All 20 Selected Players  
**Data Substrate**: Canonical Clean Legal Deliveries (`data/processed/m5_3/match_state_full.csv`, $N = 168,104$ balls, $730$ fixtures)  

---

## 1. Executive Summary & Audit Mandate

A foundational principle of cricket analytics is that **a player must not appear exceptional merely as an artifact of small-sample volatility or favorable sub-slice selection**. If a batter performs well across only 50 balls in one low-stress tournament, or if a bowler delivers two flukey overs in a dead rubber, unadjusted statistics will produce severe false positives.

Phase 5.2 subjects all 20 official selections (Top 10 Batters and Top 10 Bowlers) to a rigorous sample adequacy audit:
1. Quantifies the exact pressure exposure volume across all four DLI tiers (T1, T2, T3, T4).
2. Deconstructs tactical phase concentration (Powerplay vs. Middle vs. Death).
3. Evaluates temporal concentration across calendar years (2022–2026).
4. Investigates structural edge cases (the "Zero Tier 4" phenomenon, single-season spikes, and near-cutoff career totals).
5. Assesses whether the hierarchical Empirical Bayes shrinkage and uncertainty bounds ($\text{LB}_{90\%}$ / $\text{UB}_{90\%}$) adequately protect the rankings against small-sample inflation.

---

## 2. Batters: Detailed Pressure Exposure & Sample Adequacy

### Master Batting Exposure Matrix

| Rank | Player Name | Canonical Balls | Pressure Balls (T2–4) | Pressure Share | Pressure Innings | Low (T1) | Med (T2) | High (T3) | Crunch (T4) | High Press (T3–4) | Pressure Runs | Pressure Outs | Pressure SR | Boundary % | Context Net Runs |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **Abhishek Sharma** | 2,136 | 1,427 | 66.8% | 99 | 709 | 992 | 412 | 23 | 435 | 2,657 | 86 | 186.19 | 29.43% | $+684.4$ |
| **#2** | **Suryakumar Yadav** | 2,646 | 2,367 | 89.5% | 125 | 279 | 1,230 | 990 | 147 | 1,137 | 3,951 | 99 | 166.92 | 24.50% | $+607.3$ |
| **#3** | **Vaibhav Sooryavanshi** | 561 | 392 | 69.9% | 28 | 169 | 305 | 87 | 0 | 87 | 866 | 21 | 220.92 | 37.50% | $+315.0$ |
| **#4** | **Finn Allen** | 804 | 421 | 52.4% | 38 | 383 | 350 | 71 | 0 | 71 | 826 | 32 | 196.20 | 31.59% | $+247.0$ |
| **#5** | **Travis Head** | 1,087 | 665 | 61.2% | 55 | 422 | 519 | 146 | 0 | 146 | 1,108 | 48 | 166.62 | 28.57% | $+180.4$ |
| **#6** | **Phil Salt** | 1,497 | 1,012 | 67.6% | 59 | 485 | 732 | 235 | 45 | 280 | 1,733 | 47 | 171.25 | 25.69% | $+328.8$ |
| **#7** | **Yashasvi Jaiswal** | 1,774 | 1,181 | 66.6% | 70 | 593 | 888 | 293 | 0 | 293 | 1,838 | 58 | 155.63 | 24.64% | $+210.2$ |
| **#8** | **Ishan Kishan** | 2,314 | 1,955 | 84.5% | 106 | 359 | 1,334 | 598 | 23 | 621 | 2,992 | 96 | 153.04 | 22.81% | $+268.6$ |
| **#9** | **Tim David** | 1,154 | 1,077 | 93.3% | 85 | 77 | 175 | 616 | 286 | 902 | 1,971 | 57 | 183.01 | 22.10% | $+400.9$ |
| **#10** | **Andre Russell** | 707 | 687 | 97.2% | 55 | 20 | 61 | 424 | 202 | 626 | 1,289 | 50 | 187.63 | 24.45% | $+259.9$ |

### Batting Phase Distribution & Tactical Archetypes

| Player Name | Pressure Balls | Powerplay Balls (%) | Middle Overs Balls (%) | Death Overs Balls (%) | Primary Tactical Archetype |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Abhishek Sharma** | 1,427 | 792 (**55.5%**) | 576 (**40.4%**) | 59 (**4.1%**) | Powerplay Accelerator / Middle Transition |
| **Suryakumar Yadav** | 2,367 | 510 (**21.5%**) | 1,535 (**64.9%**) | 320 (**13.5%**) | Middle-Overs Pivot & Late Accelerator |
| **Vaibhav Sooryavanshi**| 392 | 213 (**54.3%**) | 169 (**43.1%**) | 10 (**2.6%**) | Powerplay Disruptor |
| **Finn Allen** | 421 | 234 (**55.6%**) | 173 (**41.1%**) | 14 (**3.3%**) | Powerplay Maximizer |
| **Travis Head** | 665 | 441 (**66.3%**) | 224 (**33.7%**) | 0 (**0.0%**) | Pure Powerplay Enforcer |
| **Phil Salt** | 1,012 | 504 (**49.8%**) | 426 (**42.1%**) | 82 (**8.1%**) | Top-Order Power Hitter |
| **Yashasvi Jaiswal** | 1,181 | 628 (**53.2%**) | 526 (**44.5%**) | 27 (**2.3%**) | Top-Order Anchor & High-Leverage Attacker |
| **Ishan Kishan** | 1,955 | 895 (**45.8%**) | 936 (**47.9%**) | 124 (**6.3%**) | High-Volume Top/Middle Wicketkeeper-Batter |
| **Tim David** | 1,077 | 0 (**0.0%**) | 475 (**44.1%**) | 602 (**55.9%**) | Specialized Death-Overs Finisher |
| **Andre Russell** | 687 | 0 (**0.0%**) | 250 (**36.4%**) | 437 (**63.6%**) | Extreme Death-Overs Power Finisher |

---

## 3. Bowlers: Detailed Pressure Exposure & Sample Adequacy

### Master Bowling Exposure Matrix

| Rank | Player Name | Canonical Balls (Overs) | Pressure Balls (T2–4) | Pressure Share | Pressure Spells | Low (T1) | Med (T2) | High (T3) | Crunch (T4) | High Press (T3–4) | Runs Conceded | Wickets Taken | Pressure Econ (RPO) | Net Runs Saved |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **Sunil Narine** | 1,533 (255.3) | 1,394 | 90.9% | 65 | 139 | 653 | 583 | 158 | 741 | 1,540 | 63 | **6.63** | $+378.1$ |
| **#2** | **Jasprit Bumrah** | 1,594 (265.4) | 1,338 | 83.9% | 67 | 256 | 502 | 580 | 256 | 836 | 1,552 | 72 | **6.96** | $+396.2$ |
| **#3** | **Mustafizur Rahman** | 1,414 (235.4) | 1,247 | 88.2% | 61 | 167 | 491 | 489 | 267 | 756 | 1,524 | 66 | **7.33** | $+293.4$ |
| **#4** | **Kuldeep Yadav** | 1,878 (313.0) | 1,811 | 96.4% | 85 | 67 | 737 | 858 | 216 | 1,074 | 2,311 | 114 | **7.66** | $+202.8$ |
| **#5** | **Axar Patel** | 2,484 (414.0) | 2,287 | 92.1% | 125 | 197 | 1,014 | 1,018 | 255 | 1,273 | 3,018 | 103 | **7.92** | $+114.1$ |
| **#6** | **Wanindu Hasaranga** | 1,789 (298.1) | 1,562 | 87.3% | 73 | 227 | 659 | 719 | 184 | 903 | 2,054 | 108 | **7.89** | $+112.5$ |
| **#7** | **Ravindra Jadeja** | 1,355 (225.5) | 1,312 | 96.8% | 71 | 43 | 569 | 616 | 127 | 743 | 1,685 | 56 | **7.71** | $+86.0$ |
| **#8** | **Mitchell Santner** | 1,725 (287.3) | 1,526 | 88.5% | 77 | 199 | 687 | 626 | 213 | 839 | 1,826 | 79 | **7.18** | $+281.5$ |
| **#9** | **Sikandar Raza** | 839 (139.5) | 719 | 85.7% | 38 | 120 | 376 | 315 | 28 | 343 | 845 | 31 | **7.05** | $+147.0$ |
| **#10** | **Abrar Ahmed** | 740 (123.2) | 646 | 87.3% | 31 | 94 | 222 | 288 | 136 | 424 | 707 | 42 | **6.57** | $+179.9$ |

### Bowling Phase Distribution & Tactical Archetypes

| Player Name | Pressure Balls | Powerplay Balls (%) | Middle Overs Balls (%) | Death Overs Balls (%) | Primary Tactical Bowling Role |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Sunil Narine** | 1,394 | 318 (**22.8%**) | 844 (**60.5%**) | 232 (**16.6%**) | All-Phase Mystery Spinner / Choke Bowler |
| **Jasprit Bumrah** | 1,338 | 472 (**35.3%**) | 360 (**26.9%**) | 506 (**37.8%**) | Universal Strike & Death Enforcer |
| **Mustafizur Rahman** | 1,247 | 349 (**28.0%**) | 353 (**28.3%**) | 545 (**43.7%**) | Specialist Death Cutter Bowler |
| **Kuldeep Yadav** | 1,811 | 6 (**0.3%**) | 1,531 (**84.5%**) | 274 (**15.1%**) | Middle-Overs Attacking Wrist-Spinner |
| **Axar Patel** | 2,287 | 411 (**18.0%**) | 1,662 (**72.7%**) | 214 (**9.4%**) | High-Volume Middle Restrictor & Powerplay Dart |
| **Wanindu Hasaranga** | 1,562 | 49 (**3.1%**) | 1,279 (**81.9%**) | 233 (**14.9%**) | Middle-Overs Wicket-Taking Leg-Spinner |
| **Ravindra Jadeja** | 1,312 | 33 (**2.5%**) | 1,250 (**95.3%**) | 29 (**2.2%**) | Pure Middle-Overs Defensive Controller |
| **Mitchell Santner** | 1,526 | 224 (**14.7%**) | 1,125 (**73.7%**) | 177 (**11.6%**) | Multi-Phase Finger Spinner & Restrictor |
| **Sikandar Raza** | 719 | 41 (**5.7%**) | 617 (**85.8%**) | 61 (**8.5%**) | Middle-Overs Defensive Utility Spinner |
| **Abrar Ahmed** | 646 | 99 (**15.3%**) | 444 (**68.7%**) | 103 (**15.9%**) | Attacking Mystery Spinner across Phases |

---

## 4. Critical Investigation of Structural Edge Cases

### 1. The Zero Tier 4 Phenomenon (Batting)
- **Observed Data**: Four selected batters have exactly zero legal deliveries in Tier 4 Extreme Leverage ($\text{DLI} \ge 3.0$):
  - Vaibhav Sooryavanshi (`50284`): $0$ T4 balls ($87$ T3 balls)
  - Finn Allen (`4847`): $0$ T4 balls ($71$ T3 balls)
  - Travis Head (`2367`): $0$ T4 balls ($146$ T3 balls)
  - Yashasvi Jaiswal (`6819`): $0$ T4 balls ($293$ T3 balls)
- **Tactical Reality**: All four players are specialist top-order openers. In T20 cricket, top-order batters face their pressure in the **Powerplay** and **Middle Overs** (Tiers 2 and 3: high required run rates in chases, or demanding par targets against elite opening bowlers). Under the DLI formulation, Tier 4 requires $\text{DLI} \ge 3.0$, which occurs almost exclusively when a chase requires $>12.0$ rpo with few wickets in hand during the final four overs.
- **Statistical Implications**:
  - The model does not penalize these batters because Model $M_4$ conditions expectation on match phase and tier. Their high $\Delta_{\text{EB}}$ reflects superior scoring in Powerplay/Middle pressure.
  - However, stakeholders must not interpret their ranking as evidence of death-overs finishing capability. They are **high-impact top-order accelerators**, not death-overs rescue bats.

### 2. Sample Size Boundaries Near Cutoff
- **Vaibhav Sooryavanshi (`50284`)**:
  - Career legal balls: $561$ (just $61$ balls above the $\ge 500$ eligibility threshold).
  - Pressure balls: $392$ (across $28$ pressure innings).
  - Temporal concentration: Active in only 2 years ($2025$–$2026$), with **$69.9\%$ of his pressure balls ($274$b) concentrated in 2026**.
  - *Statistical Defense*: His raw boundary rate under pressure is a staggering $37.50\%$ ($220.92$ SR). Because his sample size is smaller, the Empirical Bayes shrinkage model penalizes him with the highest standard error in the Top 10 ($se_{\text{latent}} = 0.0336$). His shrunk value-add of $+6.31\%$ is discounted by $1.645 \times 0.0336 = 5.53\%$, placing his conservative lower bound at **$+0.78\%$**. The model's uncertainty penalty worked as intended: preventing him from taking the #1 rank above Abhishek Sharma (+2.72%) despite having a higher raw strike rate.
- **Abrar Ahmed (`5979`)**:
  - Career legal balls: $740$ (above $500$ cutoff).
  - Pressure balls: $646$ (across $31$ pressure spells).
  - Temporal concentration: $60.7\%$ in $2025$ ($392$b).
  - *Statistical Defense*: He maintains an elite pressure economy of $6.57$ RPO. However, his higher standard error ($se = 0.6083$ RPO) penalizes his upper bound, positioning him at Rank #10 (+0.697 RPO) rather than competing with Narine or Bumrah.

### 3. High-Concentration Death Overs Finishers
- **Tim David (`6396`)** and **Andre Russell (`1318`)**:
  - David faced $902$ balls in T3–4 ($78.2\%$ of his career exposure); Russell faced $626$ balls in T3–4 ($88.5\%$).
  - Russell faced only $20$ normal balls (Tier 1) in his entire canonical career; $97.2\%$ of his deliveries were under pressure.
  - *Scouting Interpretation*: These players operate exclusively in high-stakes environments. Their high dismissal hazards ($4.83\%$ and $7.28\%$) are natural consequences of their role, fully balanced by immense boundary generation ($+3.43\%$ and $+3.70\%$ contextual value-add).

---

## 5. Phase 5.2 Audit Conclusion

1. **No Disqualifying Exposure Anomalies**: All 20 players comfortably surpass the pre-specified eligibility gates ($\ge 500$ career balls; $\ge 100$ pressure balls for batters; $\ge 20$ pressure spells for bowlers).
2. **Uncertainty Bounds Function Effectively**: Players with smaller samples (Sooryavanshi, Allen, Raza, Abrar) receive appropriately wide standard errors that compress their conservative bounds toward the population mean.
3. **Role Differentiation**: The audit conclusively demonstrates that the Top 10 Batters list captures two distinct tactical cohorts: **Top-Order Powerplay Accelerators** (Head, Allen, Sooryavanshi, Jaiswal, Salt) and **Death-Overs Finishers** (David, Russell, Suryakumar). This diversity strengthens the real-world scouting validity of the system.
