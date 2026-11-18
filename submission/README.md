# RR ScoutIQ — Pressure Performance Intelligence System
## Rajasthan Royals CRP SupeRR Selector Season 2 — Competition Submission

**Project Target:** Top 16 Finish | CRP SupeRR Selector Season 2  
**Challenge:** Round 1 — Identify the Most Reliable Players Under Pressure  
**Dataset:** Official Tournament Canonical Match Data (IPL & T20I 2022–2026)  
**Primary Deliverable:** Top 10 Pressure-Performing Batsmen & Top 10 Pressure-Performing Bowlers  

---

## 1. Executive Summary: The Scouting Dilemma

In modern T20 cricket, conventional recruitment relies heavily on gross aggregate statistics: career batting averages, overall strike rates, and raw bowling economy rates. While these metrics summarize volume of run accumulation, they fail to answer the most critical operational question in high-stakes tournament play:

> **How does a player perform when the match is on the line?**

Standard aggregate career metrics suffer from three foundational analytical defects:
1. **Context Blindness:** A boundary hit in a low-stakes dead rubber or during an uncontested middle-overs cruise is weighted identically to a boundary hit requiring 18 runs off the final 8 deliveries against elite death bowling.
2. **Phase Conflation:** A spin bowler conceding 7.50 runs per over in low-leverage middle overs appears superior on paper to a pace bowler conceding 8.50 runs per over during the 19th and 20th overs, even though tournament par at the death exceeds 11.20 runs per over.
3. **Small-Sample Volatility:** Short, high-variance cameos can artificially inflate strike rates, making volatile, low-exposure players appear comparable to established performers who consistently absorb high-leverage deliveries.

**RR ScoutIQ** resolves these failures through an audited, delivery-level Bayesian statistical framework that evaluates every ball under pre-delivery match leverage, residualizes environmental confounders, applies Empirical Bayes shrinkage, and ranks players by conservative credibility bounds.

---

## 2. What RR ScoutIQ Does

RR ScoutIQ is a delivery-level pressure intelligence engine designed specifically for elite T20 scouting. It processes every legal delivery across 744 clean fixtures and executes a multi-stage analytical pipeline:

```
[ Canonical Match Data ] (744 Fixtures, 168,104 Clean Legal Balls)
          │
          ▼
[ Pre-delivery Match State ] (Score, Balls Rem, Wkts in Hand, CRR, RRR, Phase)
          │
          ▼
[ Dynamic Delivery Leverage Index (DLI) ] (Contextual Pressure: T1 to T4)
          │
          ▼
[ Leave-Player-and-Matches-Out (LPMO) Priors ] (Leak-free Contextual Baselines)
          │
          ▼
[ Empirical Bayes Crossed-Effects Shrinkage ] (Separating Skill from Noise & Match Variance)
          │
          ▼
[ Conservative Uncertainty Bounding ] (Z = 1.645 Credible Interval Endpoints)
          │
          ▼
[ Final Shortlist: Top 10 Batsmen & Top 10 Bowlers ]
```

---

## 3. Measuring Match Pressure: Dynamic Delivery Leverage Index (DLI)

Match pressure is quantified on every ball using the **Dynamic Delivery Leverage Index (DLI)**. DLI is strictly an **approved contextual measure of delivery-level match pressure**, not a direct win-probability estimate or prediction of match outcomes. It quantifies how much situational pressure surrounds each delivery based on pre-delivery match state variables.

### The Four Operational Pressure Tiers
- **Tier 1: Low Pressure ($\text{DLI} < 0.90$):** Uncontested or one-sided match states. Used strictly as the player's **normal performance baseline**.
- **Tier 2: Medium Pressure ($0.90 \le \text{DLI} < 1.35$):** Standard competitive match play.
- **Tier 3: High Pressure ($1.35 \le \text{DLI} < 2.25$):** Elevated leverage junctures (phase transitions, cluster wickets, middle-over pressure).
- **Tier 4: Extreme Pressure ($\text{DLI} \ge 2.25$):** Terminal crunch time (final overs, narrow-margin chases, death bowling defense).
- **Combined Pressure (Tiers 2–4):** Aggregates all deliveries under elevated game leverage ($\text{DLI} \ge 0.90$).
- **High Pressure (Tiers 3–4):** Isolates the top quintile of elevated match moments ($\text{DLI} \ge 1.35$).

### Mathematical Formulations

#### Chase Pressure (Innings 2):
In a run chase, pressure is driven by the relationship between the required run rate, wickets in hand, and remaining deliveries:
$$\text{DLI}_{\text{chase}} = \text{Clamp}\left[ \left(\frac{\text{RRR}}{\text{CRR}_{\text{phase}}}\right) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.50} \times \left(1 + \frac{24}{B_{\text{rem}} + 12}\right)^{0.50}, \; 0.10, \; 5.00 \right]$$
Where phase par $\text{CRR}_{\text{phase}} \in \{8.15 \text{ (PP)}, 8.00 \text{ (Middle)}, 9.30 \text{ (Death)}\}$, with $W_{\text{hand}} \ge 1$ and $B_{\text{rem}} \ge 1$.

#### Setting Pressure (Innings 1):
In the first innings, pressure is driven by time progression, wickets lost, and run-rate stagnation:
$$\text{DLI}_{\text{setting}} = \text{Clamp}\left[ \Phi(t) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.60} \times (1 + \text{stag})^{0.50}, \; 0.20, \; 3.50 \right]$$
Where $\Phi(t) = 0.80 + 0.70 \times (t / 120)^{1.20}$ and $\text{stag} = \max(0, (\text{CRR}_{\text{phase}} - \text{CRR}) / 6.0)$ for $t \ge 6$.

#### Super Over:
Fixed by rule at $\text{DLI} = 3.50$.

---

## 4. Performance Evaluation: Batting & Bowling

Batting and bowling evaluate fundamentally distinct physical skills under pressure and are analyzed independently:

### Batting Evaluation: Contextual Boundary Value-Add
- Under pressure, boundary-hitting (fours and sixes) is the primary driver of win probability, whereas non-boundary strike rotation carries distinct phase value.
- Every batter's observed boundary rate is benchmarked against the expected contextual boundary probability $\mu_{\text{phase}, \text{tier}}$ generated by the Leave-Player-and-Matches-Out (LPMO) model.
- The Empirical Bayes model computes the shrunk posterior value-add:
  $$\Delta_{\text{EB}} = \mathbb{E}[\hat{\theta}_{i, \text{pressure}} - \mu_{\text{context, pressure}}]$$
- **Ranking Metric:** Batters are ranked in descending order of their conservative lower bound ($\text{LB}_{90\% \text{ CI}}$), rewarding players whose boundary scoring reliably exceeds contextual expectations.

### Bowling Evaluation: Contextual Economy Suppression
- Under pressure, run containment and boundary suppression dictate defensive success.
- Every bowler's observed runs conceded per over is benchmarked against the expected contextual economy rate $R_{\text{context, pressure}}$.
- The Empirical Bayes model computes the shrunk contextual economy delta:
  $$\Delta_{\text{EB}} = \mathbb{E}[\hat{\theta}_{i, \text{pressure}} - R_{\text{context, pressure}}] \quad (\text{negative indicates runs saved})$$
- **Ranking Metric:** Bowlers are ranked in ascending order of their conservative upper bound ($\text{UB}_{90\% \text{ CI}}$), rewarding bowlers who reliably suppress runs below contextual expectations.

---

## 5. Statistical Methodology & Uncertainty

To ensure scientific integrity and eliminate small-sample noise, RR ScoutIQ integrates three safeguards:

1. **Pre-delivery Temporal Discipline (Shift-1 Anti-Leakage):** All match-state features are calculated strictly prior to the delivery being bowled. This strictly prevents post-hoc outcome leakage without claiming that temporal sequence alone establishes causal inference.
2. **Leave-Player-and-Matches-Out (LPMO) Benchmarking:** When calculating contextual expectations for player $i$, all deliveries from matches in which player $i$ participated are excluded. This prevents a player's own dominant performances from inflating their baseline.
3. **Crossed-Effects Empirical Bayes Shrinkage:** Separates true player talent from match-level environmental variance (pitch conditions, boundary dimensions, weather) and binomial noise:
   $$\text{Var}(\text{Observed}) = \tau_{\text{player}}^2 + \sigma_{\text{match}}^2 + \sigma_{\text{noise}}^2$$
4. **Conservative Credibility Bounds ($Z = 1.645$):** Under our audited convention, rankings are based on the **conservative endpoint of the 90% two-sided credible interval, which mathematically corresponds to a 95% one-sided credible bound**:
   - Batters: $\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$
   - Bowlers: $\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$

---

## 6. Dataset Coverage & Provenance

The canonical modeling dataset is reconciled across official tournament records:

- **Canonical Dataset Population (776 Matches, 179,837 Total Deliveries):**
  - Indian Premier League (IPL): 367 matches (47.29%)
  - T20 International (T20I): 408 matches (52.58%)
  - Men's T20 Emerging / Regional (*Asia Cup Rising Stars*): 1 match (0.13%)
  - Total: 776 matches (100.00%)
- **Excluded Fixtures (32 Matches, 4,161 Deliveries):**
  - Exactly 32 rain-curtailed or DLS-interrupted fixtures (5 IPL, 27 T20I) were excluded due to distorted DLI match states.
- **Clean Legal Modeling Population (744 Matches, 168,104 Clean Legal Deliveries):**
  - Indian Premier League (IPL): 362 matches (48.66%)
  - T20 International (T20I): 381 matches (51.21%)
  - Men's T20 Emerging / Regional (*Asia Cup Rising Stars*): 1 match (0.13%)
  - Total: 744 matches (100.00%)
- **Super Over Delivery Segments:**
  - Super Overs are **delivery segments within tied matches**, not standalone matches. Across the 744 clean fixtures, exactly 23 clean legal deliveries occurred in Super Overs (0.014% of clean legal deliveries).

---

## 7. Official Competition Output

### Top 10 Pressure-Performing Batsmen
*Ranked strictly by $\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$ (descending)*

| Rank | Player Name | Local ID | Observed Discipline Eligibility | Contextual Val-Add ($\Delta_{\text{EB}}$) | 95% One-Sided Lower Bound ($\text{LB}_{90\% \text{ CI}}$) | Total Legal Balls | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Key Verification Findings & Limitations |
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

### Top 10 Pressure-Performing Bowlers
*Ranked strictly by $\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$ (ascending)*

| Rank | Player Name | Local ID | Observed Discipline Eligibility | Contextual Econ Delta ($\Delta_{\text{EB}}$) | 95% One-Sided Upper Bound ($\text{UB}_{90\% \text{ CI}}$) | Total Legal Balls (Overs) | Combined Pressure (T2–4) | High Pressure (T3–4) | Tier 4 Extreme Crunch | Key Verification Findings & Limitations |
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

*\*Note: Kuldeep Yadav is classified as dual-discipline eligible based on observed batting entries in the canonical dataset, despite operating as a specialist bowler in competitive cricket.*

---

## 8. Reproduction & Execution Guide

### Environment Prerequisites
- Python 3.10+ (tested on Python 3.13)
- `pandas`, `numpy`, `scipy`, `scikit-learn`, `pytest`

### Step 1: Run the Complete Automated Regression Suite
Execute the 30-test statistical regression and remediation suite:
```bash
python -m pytest tests/m5_5b_4_3_8/
```
*Expected Result:* 30 passed in ~25 seconds.

### Step 2: Reproduce the Top 10 Batters and Bowlers Output
Generate and verify all individual delivery statistics and shrunk estimates:
```bash
python -m src.generate_accurate_evidence
```

### Step 3: Verify Canonical Dataset Integrity
Check bitwise SHA-256 integrity of the canonical match dataset:
```powershell
Get-FileHash data\processed\m5_3\match_state_full.csv -Algorithm SHA256
```
*Expected Hash:* `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4`.

---

## 9. Governance & Submission Notice

- **Authoritative Report:** [FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md)
- **Freeze Audit:** [FINAL_FREEZE_VERIFICATION.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/FINAL_FREEZE_VERIFICATION.md)
- **Compliance Audit:** [SUBMISSION_COMPLIANCE_AUDIT.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/SUBMISSION_COMPLIANCE_AUDIT.md)
- Submitted for official hackathon evaluation. Zero subjective self-approval claimed.
