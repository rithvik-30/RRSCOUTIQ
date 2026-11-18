# RR ScoutIQ — Competition Pitch & Presentation Outline
## Rajasthan Royals CRP SupeRR Selector Season 2 — Round 1 Submission
**Target Goal:** Top 16 Finish  
**Presentation Time:** 5–7 Minutes  
**Focus:** Clarity, Evidence-Backed Rigor, and Technical Differentiation  

---

## Slide 1: Title & The Scouting Problem
- **Headline:** RR ScoutIQ: Delivery-Level Pressure Performance Intelligence
- **Subtitle:** Identifying Who Delivers When the Match is on the Line
- **Presenter Hook:** 
  > *"Every T20 analyst knows a player's career strike rate or economy rate. But when your team needs 18 off 8 balls at the death, aggregate stats don't tell you who will rise to the occasion and who will fold."*
- **The Core Problem:** Traditional scouting metrics are **context-blind**, **phase-conflated**, and **distorted by small-sample cameos**.

---

## Slide 2: Why Conventional Statistics Fail Under Pressure
- **Context Blindness:** A boundary hit in a dead rubber or during an uncontested middle-overs cruise counts the same as a boundary hit against elite death bowling in a narrow chase.
- **Phase Conflation:** A spinner bowling low-leverage overs at 7.50 RPO looks better on paper than a death bowler conceding 8.50 RPO, even though death overs par is 11.20+ RPO.
- **Cameo Volatility:** High-variance cameos artificially inflate strike rates for low-exposure players, obscuring reliable multi-season performers.
- **The Imperative:** We must evaluate performance **delivery-by-delivery**, relative to **match situation**, with **rigorous shrinkage** of small samples.

---

## Slide 3: The RR ScoutIQ Solution
- **The Philosophy:** Measure situational pressure *before* the ball is bowled, benchmark performance against independent match contexts, and isolate genuine player skill from pitch and delivery noise.
- **Key Innovations:**
  1. **Pre-delivery Reconstruction:** Shift-1 temporal sequence guarantees zero outcome leakage.
  2. **Dynamic Delivery Leverage Index (DLI):** Contextual pressure metric mapping balls into 4 distinct operational tiers.
  3. **Leave-Player-and-Matches-Out (LPMO) Priors:** Unbiased, leak-free contextual expectations.
  4. **Empirical Bayes Crossed-Effects Shrinkage:** Separates player skill from pitch/match noise.
  5. **Conservative Credibility Bounds:** Ranks players using conservative interval endpoints ($Z = 1.645$).

---

## Slide 4: Data Provenance & Cleaning
- **Canonical Population:** 776 total fixtures across IPL and T20 Internationals (179,837 deliveries).
- **Quality Filtering:**
  - Excluded 32 rain-curtailed/DLS matches (4,161 deliveries) due to distorted game states.
  - Excluded 7,761 illegal deliveries (wides and no-balls) for clean boundary modeling.
- **Clean Legal Modeling Population:** **744 matches** (168,104 clean legal deliveries).
  - **IPL:** 362 matches (48.66%)
  - **T20I:** 381 matches (51.21%)
  - **Regional:** 1 match (0.13%)
- **Entity Resolution:** 100% of 852 unique entities mapped to authoritative Cricsheet IDs.

---

## Slide 5: Measuring Match Pressure via Dynamic DLI
- **Definition:** DLI is strictly a contextual measure of delivery-level match pressure, **not** a win-probability predictor.
- **Chase Leverage (Innings 2):**
  $$\text{DLI}_{\text{chase}} = \text{Clamp}\left[ \left(\frac{\text{RRR}}{\text{CRR}_{\text{phase}}}\right) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.50} \times \left(1 + \frac{24}{B_{\text{rem}} + 12}\right)^{0.50}, \; 0.10, \; 5.00 \right]$$
- **Setting Leverage (Innings 1):**
  $$\text{DLI}_{\text{setting}} = \text{Clamp}\left[ \Phi(t) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.60} \times (1 + \text{stag})^{0.50}, \; 0.20, \; 3.50 \right]$$
- **The Four Operational Tiers:**
  - **Tier 1: Low Pressure ($\text{DLI} < 0.90$):** Uncontested play (Normal Baseline).
  - **Tier 2: Medium Pressure ($0.90 \le \text{DLI} < 1.35$):** Standard competitive cricket.
  - **Tier 3: High Pressure ($1.35 \le \text{DLI} < 2.25$):** Elevated leverage moments.
  - **Tier 4: Extreme Pressure ($\text{DLI} \ge 2.25$):** Terminal crunch time.

---

## Slide 6: Statistical Methodology & Empirical Bayes Shrinkage
- **Variance Decomposition:**
  $$\text{Var}(\text{Observed}) = \tau_{\text{player}}^2 + \sigma_{\text{match}}^2 + \sigma_{\text{noise}}^2$$
- **Empirical Bayes Shrinkage:** Pulls small-sample outliers toward the contextual baseline:
  $$\hat{\theta}_i = \lambda_i \bar{y}_i + (1 - \lambda_i) \mu_{\text{context}}$$
- **Uncertainty-Bounded Ranking:**
  - Batters ranked by **conservative lower bound** ($\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$).
  - Bowlers ranked by **conservative upper bound** ($\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$).
- **Result:** Players cannot rank high on lucky cameos; they must demonstrate sustained performance under pressure.

---

## Slide 7: Top 10 Pressure-Performing Batsmen
| Rank | Player Name | Contextual Val-Add ($\Delta_{\text{EB}}$) | 95% One-Sided Lower Bound ($\text{LB}_{90\% \text{ CI}}$) | Pressure SR | Key Insight |
|:---:|:---|:---:|:---:|:---:|:---|
| **#1** | **Abhishek Sharma** | **+6.70%** | **+2.72%** | **186.2** | Confirmed Positive; drops dot balls by 9.5% under pressure. |
| **#2** | **Suryakumar Yadav** | **+4.50%** | **+1.05%** | **166.9** | Confirmed Positive; reaches 215.0 SR in Tier 4 crunch time. |
| **#3** | **Vaibhav Sooryavanshi** | **+6.31%** | **+0.78%** | **220.9** | Confirmed Positive; 37.5% boundary rate under pressure. |
| **#4** | **Finn Allen** | **+5.16%** | **-0.07%** | **196.2** | Massive SR surge (+47.6 SR); high dismissal hazard (7.6%). |
| **#5** | **Travis Head** | **+4.32%** | **-0.18%** | **166.6** | Rebounds in Tier 3 High Leverage (182.2 SR). |
| **#6** | **Phil Salt** | **+3.58%** | **-0.75%** | **171.2** | High boundary consistency; 228.9 SR in Tier 4 (45 balls). |
| **#7** | **Yashasvi Jaiswal** | **+3.03%** | **-0.78%** | **155.6** | Reduces dot balls by 9.5%; accelerates to 171.3 SR in Tier 3. |
| **#8** | **Ishan Kishan** | **+2.51%** | **-0.90%** | **153.0** | Huge contrast: 107.8 normal SR vs 153.0 pressure SR (+45.2). |
| **#9** | **Tim David** | **+3.43%** | **-1.00%** | **177.5** | Elite death specialist: 286 balls in Tier 4 at 199.3 SR. |
| **#10** | **Andre Russell** | **+3.70%** | **-1.26%** | **170.9** | High-pressure concentration: 97.2% career balls in pressure. |

---

## Slide 8: Top 10 Pressure-Performing Bowlers
| Rank | Player Name | Contextual Delta ($\Delta_{\text{EB}}$) | 95% One-Sided Upper Bound ($\text{UB}_{90\% \text{ CI}}$) | Pressure Econ | Key Insight |
|:---:|:---|:---:|:---|:---:|:---|
| **#1** | **Sunil Narine** | **-0.605 RPO** | **+0.296 RPO** | **6.63 RPO** | Economy drops to 5.85 RPO in Tier 4; 44.3% dot balls. |
| **#2** | **Jasprit Bumrah** | **-0.538 RPO** | **+0.393 RPO** | **6.96 RPO** | 6.68 RPO & 44.5% dots in Tier 4 (256 balls); 72 pressure wkts. |
| **#3** | **Mustafizur Rahman** | **-0.326 RPO** | **+0.592 RPO** | **7.33 RPO** | Concedes 6.76 RPO and 49.4% dots in Tier 4 (267 balls). |
| **#4** | **Kuldeep Yadav** | **-0.213 RPO** | **+0.595 RPO** | **7.66 RPO** | 114 pressure wickets (15.9 balls/wkt); 7.20 RPO in High Press. |
| **#5** | **Axar Patel** | **-0.150 RPO** | **+0.651 RPO** | **7.92 RPO** | Massive volume (414 overs); lowest standard error in cohort. |
| **#6** | **Wanindu Hasaranga** | **-0.219 RPO** | **+0.652 RPO** | **7.89 RPO** | Strike rate of 14.5 balls/wkt; 108 pressure wickets. |
| **#7** | **Ravindra Jadeja** | **-0.156 RPO** | **+0.655 RPO** | **7.71 RPO** | Restricts boundaries under pressure (13.6% concession rate). |
| **#8** | **Mitchell Santner** | **-0.245 RPO** | **+0.656 RPO** | **7.18 RPO** | Economy drops to 6.68 RPO in Tier 4 with 41.8% dot balls. |
| **#9** | **Sikandar Raza** | **-0.274 RPO** | **+0.670 RPO** | **7.05 RPO** | Concedes boundaries on only 11.1% of pressure balls. |
| **#10** | **Abrar Ahmed** | **-0.304 RPO** | **+0.697 RPO** | **6.57 RPO** | 5.92 RPO in High Pressure; 5.16 RPO in Tier 4 (49.3% dots). |

---

## Slide 9: Validation, Honest Disclosures & Why RR ScoutIQ Wins
- **Technical Rigor & Honest Disclosures:**
  - We do not make false claims: only 3 batters have confirmed $\text{LB} > 0$; 0 bowlers have $\text{UB} < 0$.
  - We explicitly flag players with 0 Tier 4 balls (e.g. Sooryavanshi, Allen, Head, Jaiswal), noting their profile is established in T2 & T3.
- **Reproducibility:**
  - 30/30 automated unit tests pass in 25 seconds.
  - 100% bitwise data locking (SHA-256 verified).
- **The Competitive Advantage:**
  - RR ScoutIQ gives Rajasthan Royals decision-makers an **objective, contextual, and conservative lens** to recruit players who genuinely elevate performance when matches are decided.
