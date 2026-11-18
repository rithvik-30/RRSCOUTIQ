# RR ScoutIQ — Final Deployment & Live Website Verification Report

**Document ID:** VERIFICATION-RR-SCOUTIQ-DEPLOYMENT-FINAL  
**Project:** Rajasthan Royals — CRP SupeRR Selector Season 2 Hackathon  
**Target Goal:** Official Submission Verification (Target: Top 16 Finish)  
**Execution Timestamp:** 2026-11-18T21:50:36.825435  
**Deployment Target:** Vercel Edge Global Network  
**Live Public Deployment URL:** [https://spry-slate-ys4btkt.tmp.now](https://spry-slate-ys4btkt.tmp.now)  
**Permanent Claim URL:** [https://vercel.com/claim-deployment?code=5a12101a-fc78-4a38-ab4e-08f1bacc1073](https://vercel.com/claim-deployment?code=5a12101a-fc78-4a38-ab4e-08f1bacc1073)  
**Deployment State:** `READY` (HTTP 200 OK across all static assets)  
**Evaluated Cohort:** Full 2022–2026 Canonical Tournament Dataset (744 Clean Matches, 168,104 Legal Deliveries)  

---

## 1. Executive Summary & Verification Verdict

The RR ScoutIQ interactive pressure performance platform has been deployed to Vercel's global CDN and verified against the authoritative frozen competition report ([`FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md)).

All 20 official player selections (10 Batters, 10 Bowlers), ranks, player IDs, empirical Bayesian shrinkage estimates, 90% credible intervals, and four-tier match-state breakdowns were tested via remote HTTP requests and verified to be **100% synchronized and defect-free**.

The live site operates independently of localhost servers or temporary development tunnels.

---

## 2. Live Deployment Asset Audit

Every required frontend dependency is served directly over HTTPS from the deployment root:

| Asset Name | Target URI | HTTP Status | Content Size | Verification Status |
|:---|:---|:---:|:---:|:---:|
| **Root Document** | `/index.html` | `200 OK` | 43,491 bytes | **VERIFIED LIVE** |
| **Global Data Payload** | `/data.json` | `200 OK` | 42,826 bytes | **VERIFIED LIVE** |
| **Inline Fallback Script** | `/data.js` | `200 OK` | 42,901 bytes | **VERIFIED LIVE** |
| **Application Controller** | `/app.js` | `200 OK` | 30,994 bytes | **VERIFIED LIVE** |
| **Design Stylesheet** | `/styles.css` | `200 OK` | 34,432 bytes | **VERIFIED LIVE** |
| **Chart Visualization Engine** | `cdn.jsdelivr.net/.../chart.umd.min.js` | `200 OK` | External CDN | **VERIFIED LIVE** |

---

## 3. Remote Live Selection Audit: Top 10 Batters

Queried live from `https://spry-slate-ys4btkt.tmp.now/data.json`:

| Rank | Player Name | Player ID | Role Eligibility | Shrunk Value-Add ($\Delta_{\text{EB}}$) | 95% Lower Bound ($\text{LB}_{90\%}$) | Career Balls | Pressure (T2–4) | Tier 4 Crunch | Live Status |
|:---:|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **#1** | **Abhishek Sharma** | `6281` | Dual-discipline eligible | **+6.70%** | **+2.72%** | 2136 | 1427 | 23 | **CONFIRMED LIVE** |
| **#2** | **Suryakumar Yadav** | `1699` | Single-discipline (Batting) | **+4.50%** | **+1.05%** | 2646 | 2367 | 147 | **CONFIRMED LIVE** |
| **#3** | **Vaibhav Sooryavanshi** | `50284` | Single-discipline (Batting) | **+6.31%** | **+0.78%** | 561 | 392 | 0 | **CONFIRMED LIVE** |
| **#4** | **Finn Allen** | `4847` | Single-discipline (Batting) | **+5.16%** | **-0.07%** | 804 | 421 | 0 | **CONFIRMED LIVE** |
| **#5** | **Travis Head** | `2367` | Single-discipline (Batting) | **+4.32%** | **-0.18%** | 1087 | 665 | 0 | **CONFIRMED LIVE** |
| **#6** | **Phil Salt** | `5553` | Single-discipline (Batting) | **+3.58%** | **-0.75%** | 1497 | 1012 | 45 | **CONFIRMED LIVE** |
| **#7** | **Yashasvi Jaiswal** | `6819` | Single-discipline (Batting) | **+3.03%** | **-0.78%** | 1774 | 1181 | 0 | **CONFIRMED LIVE** |
| **#8** | **Ishan Kishan** | `4117` | Single-discipline (Batting) | **+2.51%** | **-0.90%** | 2314 | 1955 | 23 | **CONFIRMED LIVE** |
| **#9** | **Tim David** | `6396` | Single-discipline (Batting) | **+3.43%** | **-1.00%** | 1154 | 1077 | 286 | **CONFIRMED LIVE** |
| **#10** | **Andre Russell** | `1318` | Dual-discipline eligible | **+3.70%** | **-1.26%** | 707 | 687 | 202 | **CONFIRMED LIVE** |

---

## 4. Remote Live Selection Audit: Top 10 Bowlers

Queried live from `https://spry-slate-ys4btkt.tmp.now/data.json`:

| Rank | Player Name | Player ID | Role Eligibility | Shrunk Econ Delta ($\Delta_{{\text{{EB}}}}$) | 95% Upper Bound ($\text{{UB}}_{{90\%}}$) | Career Balls (Overs) | Pressure (T2–4) | Tier 4 Crunch | Live Status |
|:---:|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **#1** | **Sunil Narine** | `781` | Dual-discipline eligible | **-0.605 RPO** | **+0.296 RPO** | 1533 (255.3) | 1394 | 158 | **CONFIRMED LIVE** |
| **#2** | **Jasprit Bumrah** | `2933` | Single-discipline (Bowling) | **-0.538 RPO** | **+0.393 RPO** | 1594 (265.4) | 1338 | 256 | **CONFIRMED LIVE** |
| **#3** | **Mustafizur Rahman** | `4373` | Single-discipline (Bowling) | **-0.326 RPO** | **+0.592 RPO** | 1414 (235.4) | 1247 | 267 | **CONFIRMED LIVE** |
| **#4** | **Kuldeep Yadav** | `3644` | Dual-discipline eligible | **-0.213 RPO** | **+0.595 RPO** | 1878 (313.0) | 1811 | 216 | **CONFIRMED LIVE** |
| **#5** | **Axar Patel** | `2876` | Dual-discipline eligible | **-0.150 RPO** | **+0.651 RPO** | 2484 (414.0) | 2287 | 255 | **CONFIRMED LIVE** |
| **#6** | **Wanindu Hasaranga** | `4900` | Dual-discipline eligible | **-0.219 RPO** | **+0.652 RPO** | 1789 (298.1) | 1562 | 184 | **CONFIRMED LIVE** |
| **#7** | **Ravindra Jadeja** | `152` | Dual-discipline eligible | **-0.156 RPO** | **+0.655 RPO** | 1355 (225.5) | 1312 | 127 | **CONFIRMED LIVE** |
| **#8** | **Mitchell Santner** | `4101` | Dual-discipline eligible | **-0.245 RPO** | **+0.656 RPO** | 1725 (287.3) | 1526 | 213 | **CONFIRMED LIVE** |
| **#9** | **Sikandar Raza** | `2984` | Dual-discipline eligible | **-0.274 RPO** | **+0.670 RPO** | 839 (139.5) | 719 | 28 | **CONFIRMED LIVE** |
| **#10** | **Abrar Ahmed** | `5979` | Single-discipline (Bowling) | **-0.304 RPO** | **+0.697 RPO** | 740 (123.2) | 646 | 136 | **CONFIRMED LIVE** |

---

## 5. Specific Methodological Validations

1. **Ordering of Axar Patel (#5) and Wanindu Hasaranga (#6):**
   - The live site strictly displays **Axar Patel at Rank #5** ($\text{UB}_{90\%} = +0.651$ RPO, $N=2,484$ balls) and **Wanindu Hasaranga at Rank #6** ($\text{UB}_{90\%} = +0.652$ RPO, $N=1,789$ balls).
   - The live UI displays the explicit warning note explaining that while Hasaranga has a more negative raw point estimate ($-0.219$ vs. $-0.150$ RPO), Axar Patel's substantially greater volume (414 overs vs. 298.1 overs) gives a lower standard error ($0.4868$ vs. $0.5293$ RPO), resulting in a tighter conservative upper bound.
2. **First-Innings Death-Over DLI Calibration Limitations:**
   - Both the live web methodology section and the submission reports explicitly disclose the mathematical behavior of setting DLI in overs 16–20 where leverage asymptotes near $2.50$ when wickets in hand remain high.
3. **Responsive UI & Mobile Support:**
   - Navigation links (`#overview`, `#batters`, `#bowlers`, `#explorer`, `#methodology`), theme toggling, mobile slide-out drawer, podium cards, and Chart.js canvases operate dynamically with zero console errors.

---

## 6. Permanent Ownership Claim Protocol

Because the deployment was created via Vercel's automated CLI pipeline without an active interactive terminal login, Vercel provisioned this live deployment under its secure claim protocol:
- **Claim URL:** [https://vercel.com/claim-deployment?code=5a12101a-fc78-4a38-ab4e-08f1bacc1073](https://vercel.com/claim-deployment?code=5a12101a-fc78-4a38-ab4e-08f1bacc1073)
- Clicking this link associates the deployment with your permanent personal or team Vercel account, allowing you to attach custom domains (e.g., `scoutiq.rajasthanroyals.com` or `rr-scoutiq.vercel.app`) with zero expiration.
