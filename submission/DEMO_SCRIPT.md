# RR ScoutIQ — Video Walkthrough & Demo Script
**Document ID:** DEMO-RR-SCOUTIQ-SCRIPT-V1  
**Project:** Rajasthan Royals SupeRR Selector Season 2 — Round 1 Submission  
**Estimated Duration:** 3–5 Minutes  
**Target Audience:** Technical Judges & Cricket Analytics Reviewers  
**Tone:** Confident, Methodical, Transparent, and Evidence-Driven  

---

## Visual Setup & Screen Layout
*(For video recording or live presentation)*
- **Window 1 (Left / Main):** `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md` (or rendered Markdown view in IDE/browser).
- **Window 2 (Right / Terminal):** PowerShell terminal showing the repository root `C:\Users\rithv\OneDrive\Documents\Desktop\RR_ScoutIQ`.

---

## Demo Script

### [0:00 – 0:45] Minute 1: The Problem & What RR ScoutIQ Does
**Speaker:**
> *"Hello judges. Welcome to RR ScoutIQ.
>
> In modern T20 cricket, teams spend millions at the auction based on career averages, aggregate strike rates, and raw economy rates. But in a close tournament, matches are won and lost in high-leverage moments. Conventional stats treat a boundary in an uncontested blowout identically to a boundary needing 18 off the final over against elite death bowling.
>
> RR ScoutIQ was built specifically to solve this problem for Rajasthan Royals in SupeRR Selector Season 2. 
>
> Our mission is simple and non-negotiable: to measure how batters and bowlers perform in pressure situations compared to their usual baselines, and to deliver an evidence-backed, statistically defensible Top 10 ranking for both disciplines."*

---

### [0:45 – 1:45] Minute 2: How the Pipeline Works
**Speaker:**
*(Highlighting the Pipeline Diagram in `submission/ARCHITECTURE.md` or `submission/README.md`)*
> *"Let's look at how the system actually works.
>
> First, data integrity: We ingest 776 canonical fixtures from IPL and T20 Internationals from 2022 onwards. We apply a strict cleaning filter to remove 32 rain-curtailed and DLS-affected matches where match leverage is distorted, leaving 744 clean legal modeling fixtures and over 168,000 clean deliveries.
>
> Second, pre-delivery reconstruction: We enforce a shift-1 anti-leakage sequence. For every single ball, all match-state variables—balls remaining, wickets in hand, current run rate, required run rate, and phase—are computed strictly *before* the ball is bowled. Zero future information leaks into the context.
>
> Third, measuring pressure: We compute the Dynamic Delivery Leverage Index (DLI). For chases, it models required run rate against historical phase par, wickets in hand, and balls remaining. For first-innings setting, it accounts for time progression and run-rate stagnation. This divides deliveries into four operational tiers: from Tier 1 Normal baseline up to Tier 4 Extreme crunch time.
>
> Fourth, Empirical Bayes shrinkage: Raw stats can be fooled by small-sample cameos. We decompose variance into true player skill, match environmental variance (pitch and ground factors), and delivery noise, shrinking small samples toward leak-free contextual priors."*

---

### [1:45 – 3:15] Minute 3: Interpreting the Top 10 Batters & Bowlers
**Speaker:**
*(Scrolling to the Top 10 Batters and Bowlers Leaderboard in `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`)*
> *"Here are our final rankings, and how to interpret them.
>
> For batters, we rank in descending order of conservative lower bound ($\text{LB}_{90\% \text{ CI}}$), using the 1.645 standard error multiplier. 
>
> Look at our #1 batter: **Abhishek Sharma** (`ID: 6281`). He has an Empirical Bayes contextual value-add of $+6.70\%$, meaning he hits boundaries at a rate $6.7\%$ higher than expected for an average player in those exact game states. Under pressure, his strike rate jumps to $186.2$, and his dot-ball percentage drops by $9.5\%$. His lower credible bound is $+2.72\%$, confirming positive contextual value-add with $95\%$ one-sided confidence.
>
> At #2, **Suryakumar Yadav** (`ID: 1699`) has an astonishing 2,367 pressure deliveries. As leverage rises, his scoring tempo accelerates, reaching a strike rate of $215.0$ in Tier 4 crunch time with a low $4.18\%$ dismissal hazard.
>
> Now look at the bowlers. We rank by conservative upper bound ($\text{UB}_{90\% \text{ CI}}$) in ascending order.
>
> At #1: **Sunil Narine** (`ID: 781`). His economy systematically drops as leverage increases: from $8.07$ RPO in normal conditions down to $5.85$ RPO in Tier 4 Extreme Leverage, with $44.3\%$ dot balls.
>
> At #2: **Jasprit Bumrah** (`ID: 2933`). Across 256 balls in Tier 4 crunch time, Bumrah concedes just $6.68$ RPO while bowling $44.5\%$ dot balls and capturing $72$ pressure wickets."*

---

### [3:15 – 4:15] Minute 4: How Judges Can Inspect the Evidence
**Speaker:**
*(Switching to the Terminal window)*
> *"Everything you see here is 100% reproducible directly from the repository code. 
>
> Let's run the automated regression suite right now:
> `python -m pytest tests/m5_5b_4_3_8/`
>
> *(Executes command in terminal)*
>
> As you can see, all 30 tests pass in approximately 25 seconds. These tests verify the LSQR convergence, crossed-effects variance decomposition, and LPMO prior calculations.
>
> Next, let's run our evidence verification script:
> `python -m src.generate_accurate_evidence`
>
> *(Executes command in terminal)*
>
> This recalculates and displays the exact delivery counts, runs, strike rates, economy rates, and boundary percentages across T1, T2–T4, T3–T4, and T4 for all 20 players directly from the canonical dataset. Every single number in our competition report matches these outputs cell for cell."*

---

### [4:15 – 5:00] Minute 5: Reliability, Limitations & Conclusion
**Speaker:**
> *"What makes RR ScoutIQ truly reliable is our commitment to scientific honesty.
>
> We don't make exaggerated claims. In our report, we explicitly disclose that only 3 batters have a confirmed positive lower bound above zero, and zero bowlers have an upper bound below zero. That's not a flaw—that is the mathematical reality of high-variance T20 death bowling and small-sample cricket data.
>
> Furthermore, we explicitly flag that four top-order batters—Vaibhav Sooryavanshi, Finn Allen, Travis Head, and Yashasvi Jaiswal—have zero balls in Tier 4 Extreme Leverage. Their elite ratings were earned in top-order competitive pressure, not death-overs finishing. We disclose this so recruitment decision-makers never extrapolate beyond the data.
>
> RR ScoutIQ gives Rajasthan Royals an evidence-based, leak-free, and uncertainty-aware foundation to recruit players who deliver when it matters most.
>
> Thank you, and we welcome your questions."*
