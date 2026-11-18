# RR ScoutIQ — System Architecture Documentation
**Document ID:** ARCH-RR-SCOUTIQ-SYSTEM-V1  
**Project:** Rajasthan Royals SupeRR Selector Season 2 — Competition Submission  
**Scope:** End-to-End Pipeline Architecture (Raw Data to Final Shortlist)  
**Verification Date:** November 2026  

---

## 1. End-to-End Pipeline Overview

The RR ScoutIQ system executes a nine-stage, leak-free analytical pipeline. Every stage corresponds to physical, executed code and verified data files in the repository.

```
========================================================================================================================
                                             RR SCOUTIQ DATA PIPELINE ARCHITECTURE
========================================================================================================================

 [ Stage 1: Raw Match Data ]
    │  - 6 Cricsheet CSVs (ball_by_ball, matches, competitions, teams, playing_eleven, player_mapping)
    │  - 776 total matches (367 IPL, 408 T20I, 1 Regional) | 179,837 total rows
    ▼
 [ Stage 2: Validation & Cleaning ]
    │  - Filter: is_dli_valid == 1 & ext_is_legal_delivery == 1
    │  - Exclude 32 rain-curtailed/DLS fixtures (4,161 balls) | Exclude 7,761 wides & no-balls
    │  - Clean modeling subset: 744 fixtures (362 IPL, 381 T20I, 1 Regional) | 168,104 clean legal balls
    ▼
 [ Stage 3: Player Identity Mapping ]
    │  - Canonical entity resolver: data/enriched/player_crosswalk_m5_5.csv
    │  - Reconciles 852 unique player entities (773 strikers, 566 bowlers) to unique Cricsheet IDs
    ▼
 [ Stage 4: Pre-delivery Match-State Reconstruction ]
    │  - Shift-1 anti-leakage temporal sequence
    │  - Pre-ball state variables: balls bowled (t), balls remaining, wickets in hand, score, CRR, RRR, Phase
    ▼
 [ Stage 5: Dynamic Delivery Leverage Index (DLI) Calculation ]
    │  - Innings 2: Chase DLI formula (RRR / phase par, wickets factor, balls remaining factor)
    │  - Innings 1: Setting DLI formula (Phi(t) time progression, wickets exponent 0.60, stagnation penalty)
    │  - Super Over: Fixed rule at DLI = 3.50
    │  - Operational Tiers: Tier 1 (<0.90), Tier 2 (0.90-1.35), Tier 3 (1.35-2.25), Tier 4 (>=2.25)
    ▼
 [ Stage 6: Feature Extraction Across Pressure Tiers ]
    │  - Batting: legal balls, runs, boundaries (4s/6s), dot balls, dismissals across T1, T2, T3, T4
    │  - Bowling: legal balls, runs conceded, boundaries conceded, dot balls, wickets across T1, T2, T3, T4
    ▼
 [ Stage 7: Empirical Bayes Crossed-Effects Estimation ]
    │  - Leave-Player-and-Matches-Out (LPMO) contextual baselines (mu_phase_tier, R_context)
    │  - Crossed-effects variance decomposition: Var(Observed) = tau_player^2 + sigma_match^2 + sigma_noise^2
    │  - Shrunk posterior point estimates: Delta_EB for boundary value-add and economy suppression
    ▼
 [ Stage 8: Confidence-Bound Calculation & Ranking ]
    │  - Statistical uncertainty estimation: se_latent derived from residual covariance
    │  - Conservative bound multiplier: Z = 1.645 (90% two-sided CI endpoint / 95% one-sided bound)
    │  - Batters: LB_90%CI = Delta_EB - 1.645 * se_latent (ranked descending)
    │  - Bowlers: UB_90%CI = Delta_EB + 1.645 * se_latent (ranked ascending)
    ▼
 [ Stage 9: Final Competition Output ]
    │  - Top 10 Pressure-Performing Batsmen (Leaderboard + Detailed Evidence Cards)
    │  - Top 10 Pressure-Performing Bowlers (Leaderboard + Detailed Evidence Cards)
========================================================================================================================
```

---

## 2. Stage-by-Stage Component Specifications

### Stage 1: Raw Match Data Ingestion
- **Repository Location:** `data/extracted/`
- **Source Files:**
  - `ball_by_ball.csv` (179,837 rows, 33 original local columns)
  - `matches.csv` (776 canonical fixtures)
  - `competitions.csv`, `teams.csv`, `playing_eleven.csv`, `competition_team_player_mapping.csv`
- **Data Integrity:** Bitwise locked via SHA-256 hashes recorded in `audit_reports/M4_6_DATASET_INTEGRITY_RECONCILIATION.md`.

### Stage 2: Validation, Cleaning & Filtering
- **Repository Location:** `src/m5_enrichment/clean_canonical_dataset.py`, `src/m4_pilot/input_validation.py`
- **Execution Logic:**
  - Enforces `is_dli_valid == 1` to exclude 32 matches truncated by rain or revised by Duckworth-Lewis-Stern (DLS), where standard chase/setting dynamics are distorted.
  - Enforces `ext_is_legal_delivery == 1` to separate fair deliveries from 6,976 wides and 785 no-balls.
- **Output:** The authoritative modeling dataset `data/processed/m5_3/match_state_full.csv` (168,104 clean legal deliveries across 744 fixtures; SHA-256 `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4`).

### Stage 3: Player Identity & Discipline Mapping
- **Repository Location:** `data/enriched/player_crosswalk_m5_5.csv`, `src/m5_enrichment/crosswalk_builder.py`
- **Execution Logic:**
  - Resolves local integer IDs to standardized Cricsheet player names and global identifiers.
  - Identifies 773 clean strikers (batters), 566 clean bowlers, and 487 dual-discipline participants who both batted and bowled.
  - Zero unresolved entities or dangling references (100.0% entity resolution).

### Stage 4: Pre-delivery Match-State Reconstruction
- **Repository Location:** `src/m5_3/reconstruct_match_state.py`
- **Execution Logic:**
  - Operates strictly under a **shift-1 causal sequence**: the match state for delivery $t$ incorporates only information accumulated through delivery $t-1$.
  - Generates pre-delivery state features: cumulative balls bowled ($t$), balls remaining ($B_{\text{rem}}$), wickets lost ($W_{\text{lost}}$), wickets in hand ($W_{\text{hand}}$), batting team score ($S$), Current Run Rate ($\text{CRR}$), target runs, Required Run Rate ($\text{RRR}$), and match phase (Powerplay: 1–6, Middle: 7–15, Death: 16–20).
  - **Temporal Integrity Guarantee:** Strictly prevents outcome leakage from ball $t$ into its pre-delivery context.

### Stage 5: Dynamic Delivery Leverage Index (DLI) Calculation
- **Repository Location:** `src/m5_3/dli_calculator.py`
- **Execution Logic:**
  - Evaluates situational match pressure on every ball using analytical equations tailored to innings type:
    - **Innings 2 (Chase DLI):** Scaled by Required Run Rate relative to phase par (8.15 PP, 8.00 Mid, 9.30 Death), dampened by wickets in hand ($W_{\text{hand}}^{0.50}$), and amplified by dwindling balls ($B_{\text{rem}}$ factor). Clamped to $[0.10, 5.00]$.
    - **Innings 1 (Setting DLI):** Scaled by continuous time progression $\Phi(t) = 0.80 + 0.70(t/120)^{1.20}$, heightened wicket sensitivity ($W_{\text{hand}}^{0.60}$), and run-rate stagnation penalties. Clamped to $[0.20, 3.50]$.
    - **Super Over:** Fixed at $\text{DLI} = 3.50$.
  - Categorizes continuous DLI into four discrete tiers: Tier 1 Low ($<0.90$), Tier 2 Medium ($0.90–1.35$), Tier 3 High ($1.35–2.25$), Tier 4 Extreme ($\ge 2.25$).

### Stage 6: Delivery-Level Feature Aggregation
- **Repository Location:** `src/m5_5b/baseline_estimation.py`, `src/generate_top20_reports.py`
- **Execution Logic:**
  - Aggregates player exposure across each tier and combination: Normal (T1), Combined Pressure (T2–4), High Pressure (T3–4), and Extreme Crunch (T4).
  - Computes raw strike rates, boundary percentages, dot-ball percentages, dismissals, and dismissal hazard rates for batters.
  - Computes raw economy rates (RPO), wicket counts, balls per wicket (strike rate), dot-ball percentages, and boundary-concession percentages for bowlers.

### Stage 7: Joint Empirical Bayes Crossed-Effects Estimation
- **Repository Location:** `src/m5_5b_4_3_8/variance_decomposition_b4_3_8.py`
- **Execution Logic:**
  - **LPMO Contextual Baselines:** Estimates phase-by-tier baseline expectations ($\mu_{\text{phase}, \text{tier}}$ for boundaries; $R_{\text{context, pressure}}$ for economy) excluding the candidate player's fixtures to avoid self-reinforcing bias.
  - **Crossed-Effects Variance Decomposition:** Residualizes fixed contextual effects and partitions remaining variance into true player talent ($\tau_{\text{player}}^2$), match-level environmental variance ($\sigma_{\text{match}}^2$), and binomial delivery noise ($\sigma_{\text{noise}}^2$).
  - **Bayesian Shrinkage:** Shrinks raw observed differences toward the contextual baseline using shrinkage weight $\lambda_i = \tau^2 / (\tau^2 + \text{SE}_i^2)$, preventing volatile small-sample cameos from outranking sustained performance.

### Stage 8: Conservative Uncertainty Bounding & Ranking
- **Repository Location:** `src/build_top20_scouting_reports.py`, `src/generate_accurate_evidence.py`
- **Execution Logic:**
  - Evaluates candidate eligibility: career legal balls $\ge 500$, pressure balls $\ge 100$, and low epistemic standard error ($se_{\text{latent}} \le 0.035$ for batters, $\le 0.65$ RPO for bowlers).
  - Applies conservative multiplier $Z = 1.645$ (the lower/upper endpoint of the 90% two-sided credible interval, mathematically equivalent to a 95% one-sided bound).
  - **Batting Ranking:** Descending order of $\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$.
  - **Bowling Ranking:** Ascending order of $\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$.

### Stage 9: Submission Deliverable Generation
- **Repository Location:** `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`, `submission/`
- **Execution Logic:**
  - Generates comprehensive competition reports, leaderboard tables, detailed 5-tier player cards, and transparent limitation disclosures.

---

## 3. Implemented vs. Excluded Components

To maintain analytical rigor and adhere strictly to tournament rules, RR ScoutIQ explicitly separates implemented pipeline components from unrequested conceptual ideas:

| Component | Status | Implementation Justification |
|---|:---:|---|
| **Pre-delivery Match-State Engine** | **IMPLEMENTED** | Required to reconstruct contextual leverage without outcome leakage. |
| **Dynamic DLI Calculator** | **IMPLEMENTED** | Core requirement to define and quantify situational pressure. |
| **LPMO Contextual Prior Estimator** | **IMPLEMENTED** | Essential for leak-free, unbiased player benchmarking. |
| **Empirical Bayes Crossed-Effects Engine** | **IMPLEMENTED** | Critical to eliminate match environmental noise and small-sample volatility. |
| **Conservative Credible Bound Ranking** | **IMPLEMENTED** | Required to ensure statistical defensibility over raw point estimates. |
| **Auction Purse Allocation Optimizer** | **DELIBERATELY EXCLUDED** | Out of scope. The official problem statement tasks participants with evaluating player reliability under pressure, not bidding strategy. |
| **Squad Gap / Playing XI Simulator** | **DELIBERATELY EXCLUDED** | Out of scope. Squad building involves subjective team balance not requested in Round 1. |
| **Subjective Cross-Discipline Composite Rating** | **DELIBERATELY EXCLUDED** | Out of scope. The challenge specifically mandates two independent Top-10 lists (batting and bowling). |
