# RR ScoutIQ: Milestone M3 Methodology Requirements & Specification

**Milestone:** M3 – Pressure Performance Methodology & Metric Approval  
**Document Purpose:** Define core design questions, mathematical foundations, empirical constraints, and architectural prerequisites before implementing player rankings or pressure calculations.  
**Scope Boundary:** Methodology specification and requirements definition only (Zero player rankings, pressure scores, or full-dataset delivery enrichments generated).

---

## 1. Executive Context & Objective

The primary objective of RR ScoutIQ for Rajasthan Royals (*SupeRR Selector Season 2*) is:
> Identify the **Top 10 Batters** and **Top 10 Bowlers** who perform most reliably under pressure, comparing ordinary performance with pressure performance while considering consistency, resilience, and sample-size credibility.

Milestones M1 through M2.5 have audited the raw data, resolved scoring conventions, verified external Cricsheet archives, pilot-tested the hybrid enrichment layer, and established the reliable analysis population. 

Milestone M3 must formalize the **mathematical definitions, contextual thresholds, normalization baselines, eligibility filters, and ranking algorithms**. This specification establishes the binding requirements that M3 must address.

---

## 2. Core Methodological Design Decisions for M3

M3 must resolve eight foundational design decisions through explicit domain and mathematical evidence:

### Decision 1: Definition of Pressure Situations
Pressure is not a binary flag present in raw data; it is an emergent state of match leverage and resource constraints. M3 must formalize separate definitions for Innings 1 and Innings 2:

```
+---------------------------------------------------------------------------------------------------------+
|                                    M3 DUAL-PHASE PRESSURE TAXONOMY                                      |
+---------------------------------------------------------------------------------------------------------+
| 1. CHASE PRESSURE (Innings 2 - Primary Leverage Context):                                              |
|    - High Required Run Rate (RRR): Required Run Rate >= 10.0 runs per over.                             |
|    - Death Chase: Legal Balls Remaining <= 30 (Overs 15.1-20.0) with match in balance.                 |
|    - Batting Collapse Under Pressure: Wickets in Hand <= 4 (6+ wickets down) with RRR >= 8.5.           |
|    - Close Finish: Final 12 balls with Runs Required <= 24 and Wickets in Hand >= 2.                    |
+---------------------------------------------------------------------------------------------------------+
| 2. FIRST-INNINGS PRESSURE (Innings 1 - Target Setting Context):                                         |
|    - Death Overs Surge: Legal Balls 91-120 (Overs 16-20) where scoring velocity is mandatory.           |
|    - Powerplay Collapse Recovery: Batting team loses >= 3 wickets within the first 36 legal balls.      |
|    - Middle Overs Stagnation: Scoring rate < 7.0 with wickets in hand to rebuild.                      |
+---------------------------------------------------------------------------------------------------------+
| 3. MAXIMUM LEVERAGE TIE-BREAK (Super Overs - Innings 3 & 4):                                            |
|    - Extreme pressure state (1 over, 2 dismissable wickets). Evaluated with specialized weighting.       |
+---------------------------------------------------------------------------------------------------------+
```

### Decision 2: Prevention of Information Leakage & Temporal Boundary
To maintain mathematical integrity, pressure context must be evaluated **strictly before** each delivery:
* **Permitted Pre-Delivery Features:** Current score before ball, wickets lost before ball, balls remaining before ball, required run rate before ball, historical/prior form, match phase.
* **Prohibited Post-Delivery Features (Strictly Excluded from Pressure Definition):** Runs scored on the current ball, wicket on the current ball, final match result (`matches.result`), margin of victory, final team score, Player of the Match awards (`man_of_the_match`).

### Decision 3: Separation of Batter and Bowler Pressure Frameworks
Pressure affects batters and bowlers reciprocally, but their performance objectives differ:
* **Batters:** Maximize scoring rate (Strike Rate) while preserving wickets (Dismissal Rate) under high RRR and dwindling balls.
* **Bowlers:** Minimize runs conceded (Economy Rate) and break partnerships (Strike Rate / Wickets) when defending a total or containing death overs.
* *Requirement:* M3 must maintain two dedicated, non-conflated feature pipelines for batters and bowlers.

### Decision 4: Player Role & Phase Segmentation
Raw universal rankings create severe bias:
* Top-order openers face 36 powerplay balls against hard new balls; death finishers face 15-20 balls against yorkers and slower balls.
* Powerplay swing bowlers operate with 2 fielders outside the ring; death bowlers defend boundaries with 5 fielders out.
* *Requirement:* M3 must establish player role cohorts:
  * **Batters:** Top Order (Positions 1–3), Middle Order (Positions 4–5), Finishers (Positions 6–8).
  * **Bowlers:** Powerplay Specialists (Overs 1–6), Middle-Over Enforcers/Spinners (Overs 7–15), Death Bowlers (Overs 16–20).

### Decision 5: Player Eligibility & Minimum Sample Size Gates
Based on the M2.5 empirical distribution audit:
* 41.9% of batters and 42.0% of bowlers have fewer than 5 innings.
* At $N < 50$ balls, strike rate variance is dominated by sample noise ($\sigma > 30.0$).
* *Requirement:* M3 must mandate dual qualification gates:
  * **Batters:** Minimum 15 innings AND $\ge 150$ balls faced (with $\ge 50$ balls faced under defined pressure).
  * **Bowlers:** Minimum 15 bowling innings AND $\ge 180$ legal balls bowled / 30 overs (with $\ge 60$ legal balls under defined pressure).

### Decision 6: Empirical Bayesian Shrinkage & Small-Sample Stabilization
For players meeting minimum eligibility but having moderate sample sizes ($N \in [50, 150]$ balls in pressure):
* Raw rates ($\text{SR} = \text{Runs}/\text{Balls}$) must be smoothed using Empirical Bayes:
  $$\text{Adjusted Rate} = \frac{N}{N + K} \cdot \text{Observed Rate} + \frac{K}{N + K} \cdot \mu_{\text{cohort}}$$
  where $K$ is the evidence weight constant (e.g., $K = 40$ balls) and $\mu_{\text{cohort}}$ is the role-specific league baseline.
* This prevents small-sample flukes from topping the leaderboard over elite multi-season performers.

### Decision 7: Seasonal Baseline Normalization (2022 to 2026)
Between 2022 and 2025, league-wide scoring rates rose from 8.2 to >9.5 rpo.
* An economy of 9.5 in 2022 was poor; in 2024–2025 IPL death overs, it is above average.
* *Requirement:* M3 must evaluate players relative to **Seasonal Phase Baselines**:
  $$\Delta \text{Metric} = \text{Player Metric}_{\text{phase, season}} - \text{League Mean}_{\text{phase, season}}$$

### Decision 8: Full 784-Match Hybrid Delivery Enrichment Rollout
Milestone M2.4 pilot-tested the enrichment pipeline across 8 matches (1,994 deliveries) with 100.0% QA agreement.
* *Prerequisite for M4 Calculation:* Prior to computing dataset-wide pressure features in M4, Milestone M3 must execute Phase 4 batch enrichment across all 784 Cricsheet-covered fixtures.
* *Safety Rules:* Original 6 CSVs remain untouched; enriched features are generated in `data/enriched/full/enriched_ball_by_ball.csv` carrying explicit `ext_` prefixes and complete source provenance.

---

## 3. Data Availability & Boundary Mapping for M3

| Data Component | Available Scope in Dataset | Missing / Excluded Scope | M3 Operational Boundary |
| :--- | :--- | :--- | :--- |
| **IPL Matches** | 371 matches (100% of played IPL 2022–2026 fixtures). | 0 matches missing. | Primary evaluation benchmark for franchise pressure scouting. |
| **T20I Matches** | 413 bilateral and ICC tournament fixtures. | 61 matches withheld by Cricsheet editorial policy (Afghanistan men). | Secondary evaluation benchmark. Players evaluated on fully covered matches. |
| **Developmental Tournaments** | 25 Emerging Teams & Rising Stars matches. | Not indexed by Cricsheet. | Excluded from hybrid enrichment; retained as raw descriptive context. |
| **Shortened / DLS Matches** | 23 revised target matches; 34 revised over matches. | Delivery-level rain interruption index is unrecorded in raw CSV. | **Exclusion Rule:** Exclude rain-curtailed chases from pre-delivery RRR calculation to prevent information leakage/backcasting. |
| **Telemetry / Sensor Data** | None. | Radar ball speed (`bowl_speed`), release angles, Hawkeye tracking, pitch moisture. | Strictly excluded. Pressure quantified purely through match-state and scorecard events. |
| **Fielding Contributions** | None. | Dropped catches, run-out assists, ground fielding runs saved. | Acknowledged as unobservable uncertainty bounds. |

---

## 4. Formal Acceptance Criteria for Milestone M3

Milestone M3 may be marked COMPLETE only when:
1. **Pressure Context Specification Approved:** Stakeholder sign-off on the formal mathematical boundaries for RRR, Death Overs, Collapse Recovery, and Super Overs.
2. **Eligibility Gates Formally Fixed:** Final selection of minimum innings, balls faced, and overs bowled thresholds with documented exclusion impacts.
3. **Separate Batter & Bowler Formulas Defined:** Mathematical specification for:
   * **Batter Pressure Performance Index (BPPI):** Weighting $\Delta \text{Strike Rate}$, Dot Ball %, Boundary %, and Dismissal Resistance under pressure.
   * **Bowler Pressure Performance Index (PPBI):** Weighting $\Delta \text{Economy}$, Wicket Strike Rate, Dot Ball %, and Boundary Concession % under pressure.
4. **Reliability & Consistency Metric Defined:** A statistical measure of variance/consistency across matches (e.g. interquartile range of match-level pressure contributions) to separate one-match wonders from dependable performers.
5. **Full 784-Match Delivery Enrichment Executed:** Complete batch generation of `data/enriched/full/enriched_ball_by_ball.csv` validated with automated reconciliation assertions.

---

## 5. Explicit Restrictions During M3 Preparation

* **DO NOT calculate player pressure scores yet.**
* **DO NOT rank players or output a top-10 list.**
* **DO NOT modify original source files.**
* **DO NOT backcast revised DLS targets onto pre-interruption deliveries.**

