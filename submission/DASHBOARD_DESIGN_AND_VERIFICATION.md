# RR ScoutIQ — Official Rajasthan Royals Website-Inspired Design & Verification Report
**Document ID:** REPORT-RR-SCOUTIQ-DASHBOARD-V1  
**Project:** Rajasthan Royals SupeRR Selector Season 2 Hackathon  
**Target Goal:** Top 16 Finish  
**Reference Inspiration:** [Rajasthan Royals Official Website](https://www.rajasthanroyals.com/)  
**Implementation Directory:** [`dashboard/`](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/dashboard/)  
**Creation Date:** 2026-11-17T17:35:00+05:30  
**Status:** COMPLETE & 100% STATISTICALLY VALIDATED  
**Governance:** Zero Modifications to Frozen Analytics; Verified against Physical Source Reports  

---

## 1. Executive Summary & Brand Identity

To provide Rajasthan Royals leadership and hackathon judges with a broadcast-grade analytics experience, the **RR ScoutIQ** interactive dashboard was designed taking visual inspiration from the official Rajasthan Royals digital design system ([rajasthanroyals.com](https://www.rajasthanroyals.com/)).

The dashboard retains its own unique analytical identity while seamlessly integrating with the visual aesthetic of the Rajasthan Royals ecosystem:
- **Primary Royal Cardinal Pink:** `#950460` (Primary accent, highlights, active tabs, and primary CTAs).
- **Electric Hot Pink:** `#D81159` / `#FF70B8` (Glows, hover states, status pills, and positive boundary value-add highlights).
- **Deep Royal Purple:** `#31136C` (Foundation surfaces, brand shields, hero backgrounds).
- **Midnight Purple / Cosmic Navy:** `#0C0519` / `#140A28` / `#180D33` (Dark mode background and card surfaces).
- **Royal Lavender / Crisp Ice White:** `#F7F6FB` / `#FFFFFF` (Light mode backgrounds and cards).
- **Admiral Blue Accent:** `#1E22AA` (Secondary bowling metrics and economy containment accents).
- **Championship Gold:** `#E5A93C` (Rank 1 badge and exposure warning accents).

---

## 2. Page Structure & Navigation System

The dashboard is structured as a responsive single-page application (SPA) with a top sticky navigation bar inspired by the Royals website:

```
+--------------------------------------------------------------------------------------------------------------------+
| [Shield Logo] RR SCOUTIQ  •  Overview  •  Top 10 Batters  •  Top 10 Bowlers  •  Player Explorer  •  Methodology  | [Theme] |
+--------------------------------------------------------------------------------------------------------------------+
```

### 1. Header & Navigation Bar
- **Brand Wordmark:** Styled as **`RR SCOUTIQ`** featuring an SVG shield icon with an animated linear gradient shimmer.
- **Navigation Links:**
  - **Overview:** Hero section, dataset metrics strip, intelligence highlights, governance disclosures.
  - **Top 10 Batters:** Sports ranking cards for the 10 qualified batsmen.
  - **Top 10 Bowlers:** Sports ranking cards for the 10 qualified bowlers.
  - **Player Explorer:** Deep-dive interactive player analysis with 4-tier match-state tables and Chart.js visualizations.
  - **Methodology:** Interactive technical explanation of DLI, LPMO priors, crossed-effects shrinkage, and $Z = 1.645$ bounds.
- **Theme Toggle:** One-click toggle switching between **Dark Mode** (Deep Navy/Purple surfaces) and **Light Mode** (Royal Lavender/White surfaces), with persistent state saved to `localStorage`.

### 2. Overview Section
- **Royals Headline:**
  > `"PRESSURE REVEALS THE ROYALTY."`
- **Supporting Subtext:**
  > `"Discover the batters and bowlers who deliver when the game gets difficult. Powered by Dynamic Delivery Leverage Index (DLI) modeling and leak-free Empirical Bayes crossed-effects shrinkage across 744 clean T20 fixtures."`
- **Tournament Badge:** Explicitly identifies the tool as the official *Rajasthan Royals CRP SupeRR Selector Season 2 • Round 1 Submission*.
- **Authoritative Dataset Metrics Strip:**
  - **776** Canonical Matches (367 IPL • 408 T20I • 1 Regional)
  - **744** Clean Modeling Matches (362 IPL • 381 T20I • 1 Regional)
  - **168,104** Clean Legal Deliveries (excludes 32 rain fixtures & illegal deliveries)
  - **106** Qualified Batters ($\ge 500$ career balls)
  - **109** Qualified Bowlers ($\ge 500$ career balls)
- **Governance Notice:** Prominent banner stating that rankings represent competition-wide pressure evaluations, not official Rajasthan Royals franchise squad selections, purse bidding allocations, or squad-gap strategies.

### 3. Leaderboard Cards (Batters & Bowlers)
Rather than a dense administrative spreadsheet, the leaderboards are presented as sports trading cards:
- **Rank Badge:** Distinct visual styling for podium finishers (#1 Gold gradient, #2 Silver/Blue gradient, #3 Bronze gradient).
- **Player Information:** Name, unique ID, and *Observed Discipline Eligibility* (Single-discipline vs. Dual-discipline eligible).
- **Primary Metric Displays:**
  - Batters: Shrunk Contextual Boundary Value-Add ($\Delta_{\text{EB}}$) and 95% One-Sided Lower Bound ($\text{LB}_{90\% \text{ CI}}$).
  - Bowlers: Shrunk Contextual Economy Delta ($\Delta_{\text{EB}}$ in RPO) and 95% One-Sided Upper Bound ($\text{UB}_{90\% \text{ CI}}$).
- **Status Badges:**
  - `CONFIRMED POSITIVE` (Green/Pink badge) for Ranks 1–3 (Abhishek Sharma, Suryakumar Yadav, Vaibhav Sooryavanshi).
  - `RELATIVE LEADER` for Ranks 4–10.
  - `TOP RELATIVE SUPPRESSOR` for all 10 bowlers.
- **Exposure Pills:** Flags sample exposure (e.g., *Small Tier 4 Sample* for Abhishek and Kishan; *Zero Tier 4 Balls* for Sooryavanshi, Allen, Head, and Jaiswal).
- **"Analyze in Explorer" Button:** Clicking immediately jumps to the Player Explorer section and loads that player's comprehensive dossier.

### 4. Interactive Player Explorer
A split-screen player evaluation laboratory:
- **Left Sidebar:** Instant search filter by player name or ID, plus discipline filter buttons (`All (20)`, `Batters (10)`, `Bowlers (10)`).
- **Right Main Detail Panel:**
  - **Profile Banner:** Huge rank badge, player name, discipline eligibility, total career matches, and total volume.
  - **4 Stat Summary Boxes:** Contextual metric, 95% credible bound, pressure tempo (SR or Economy with delta), and pressure execution (Dot ball % with delta).
  - **Confidence Interval Visualizer Bar:** Interactive scale showing the zero baseline par ($0.0$), the shrunk posterior mean, the latent standard error, and the conservative 95% credible bound.
  - **Interactive Chart.js Visualizations:**
    - *Chart 1 (Trajectory Across Leverage Tiers):* Line chart mapping performance across T1 Low, T2 Medium, T3 High, and T4 Extreme.
    - *Chart 2 (Boundary % vs. Dot Ball % Comparison):* Grouped bar chart comparing Normal play against Combined Pressure and High Pressure.
  - **Comprehensive 4-Tier Match-State Breakdown Table:** Displays exact balls, runs, strike rate/economy, boundary %, dot ball %, wickets/dismissals, and dismissal hazard across all 4 individual tiers, Combined Pressure (T2–4), and High Pressure (T3–4).
  - **Exposure Limitations Alert Card:** Explains the exact sample distribution, highlighting whether terminal crunch execution is verified or zero-exposure.

### 5. Interactive Methodology Section
- 6 visual cards detailing: (1) Pre-delivery Causal Reconstruction, (2) Dynamic DLI Equations, (3) The Four Operational Tiers, (4) LPMO Contextual Priors, (5) Crossed-Effects Shrinkage, and (6) $Z = 1.645$ Credibility Bounds.
- Complete canonical dataset provenance table reconciling 776 canonical matches, 32 excluded fixtures, 744 clean modeling matches, and 23 Super Over deliveries.

---

## 3. Data Integrity & Automated Verification Results

A dedicated validation suite (`src/validate_dashboard_statistics.py`) was executed to cross-examine every number in `dashboard/data.js` against the frozen competition reports:

```
[PASS] Metadata validated:
       - Canonical matches: 776
       - Clean modeling matches: 744
       - Clean legal deliveries: 168,104
       - Multiplier Z: 1.645
[PASS] All 10 Batters validated cell-for-cell against FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md.
[PASS] All 10 Bowlers validated cell-for-cell against FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md.
[PASS] Batter lower bounds strictly descending:
       [+2.72%, +1.05%, +0.78%, -0.07%, -0.18%, -0.75%, -0.78%, -0.90%, -1.00%, -1.26%]
[PASS] Bowler upper bounds strictly ascending:
       [+0.296, +0.393, +0.592, +0.595, +0.651, +0.652, +0.655, +0.656, +0.670, +0.697] RPO
```

Zero statistical discrepancies, zero placeholder statistics, and zero fabricated metrics exist in the dashboard.

---

## 4. How to Launch and Explore the Dashboard

The dashboard is 100% self-contained and requires no build steps (no npm, node, or webpack required).

### Option 1: Direct File Opening (No Server Required)
Because data is loaded via `data.js` into `window.RR_DATA`, the dashboard runs directly off disk without CORS blocks:
- Simply double-click **`dashboard/index.html`** or open it in any modern browser (Chrome, Edge, Firefox, Safari).

### Option 2: Local HTTP Server
To serve it over local HTTP:
```bash
python -m http.server 8080 --directory dashboard
```
Then navigate to: `http://localhost:8080`
