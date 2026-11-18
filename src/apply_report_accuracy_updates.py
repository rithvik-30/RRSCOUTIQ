"""
Applies exact presentation and accuracy corrections to:
1. FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
2. Mirrors to audit_reports/M5_5B_4_3_8/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
3. Mirrors to submission/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
"""

with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Dataset in exec summary
target1 = "The framework evaluates all eligible players across 744 clean legal fixtures and delivers:"
repl1 = "The framework evaluates all eligible players across 744 clean modeling matches across IPL, T20I and regional T20 cricket, comprising 168,104 clean legal deliveries, and delivers:"
assert target1 in text, "target1 not found"
text = text.replace(target1, repl1, 1)

# 2. Top 10 Batters line in exec summary
target2 = "- **Top 10 Pressure-Performing Batsmen** (ranked by conservative contextual boundary value-add lower bound)."
repl2 = "- **Top 10 Pressure-Performing Batsmen** (ranked by conservative lower credible bound of contextual batting value-add)."
assert target2 in text, "target2 not found"
text = text.replace(target2, repl2, 1)

# 3. Chase formula typo
target3 = r"W_{\text{hand}組}"
repl3 = r"W_{\text{hand}}"
assert target3 in text, "target3 not found"
text = text.replace(target3, repl3, 1)

# 4. Setting formula and stag replacement
old_setting = (
    r"$$\text{DLI}_{\text{setting}} = \text{Clamp}\left[ \Phi(t) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.60} \times (1 + \text{stag})^{0.50}, \; 0.20, \; 3.50 \right]$$" + "\n"
    r"Where:" + "\n"
    r"- $\Phi(t)$ is a continuous power-law time progression factor:" + "\n"
    r"  $$\Phi(t) = 0.80 + 0.70 \times \left(\frac{t}{120}\right)^{1.20}$$" + "\n"
    r"- The wicket sensitivity exponent ($0.60$) is higher than in chases ($0.50$) because early wickets in Innings 1 severely compromise the team's ability to attack at the death." + "\n"
    r"- $\text{stag}$ is the run-rate stagnation penalty relative to phase par:" + "\n"
    r"  $$\text{stag} = \max\left(0, \; \frac{\text{CRR}_{\text{phase}} - \text{CRR}}{6.0}\right) \quad (\text{defined for } t \ge 6)$$" + "\n"
    r"- Clamping limits the setting DLI strictly to $[0.20, 3.50]$."
)

new_setting = (
    r"$$\text{DLI}_{\text{setting}} = \text{Clamp}\left[ \Phi(t) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.60} \times \left(1 + \max\left(0, \; \frac{\text{CRR}_{\text{phase}} - \text{CRR}}{6}\right)\right)^{0.50}, \; 0.20, \; 3.50 \right]$$" + "\n"
    r"Where:" + "\n"
    r"- $\Phi(t)$ is the continuous power-law time progression factor:" + "\n"
    r"  $$\Phi(t) = 0.80 + 0.70 \times \left(\frac{t}{120}\right)^{1.20}$$" + "\n"
    r"- The wicket sensitivity exponent ($0.60$) is higher than in chases ($0.50$) because early wickets in Innings 1 severely compromise the batting team's ability to attack at the death." + "\n"
    r"- The stagnation penalty term $\max\left(0, \frac{\text{CRR}_{\text{phase}} - \text{CRR}}{6}\right)$ is active for $t \ge 6$ (defined as $0$ for $t < 6$), measuring cumulative scoring slowdown relative to empirical phase par $\text{CRR}_{\text{phase}}$." + "\n"
    r"- Clamping limits the setting DLI strictly to $[0.20, 3.50]$."
)

if old_setting not in text:
    old_setting = old_setting.replace("\n", "\r\n")
    new_setting = new_setting.replace("\n", "\r\n")

assert old_setting in text, "old_setting block not found"
text = text.replace(old_setting, new_setting, 1)

# 5. Batting ranking line
target5 = r"- **Batting Ranking:** Higher boundary value-add is superior. Batters are ranked in **descending order** of their conservative lower bound ($\text{LB}_{90\% \text{ CI}}$)."
repl5 = r"- **Batting Ranking:** Higher contextual batting value-add is superior. Batters are ranked in **descending order** of their conservative lower bound ($\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$). Boundary rate, strike rate and dot-ball rate are supporting evidence, not substitutes for the primary contextual estimate."
assert target5 in text, "target5 not found"
text = text.replace(target5, repl5, 1)

# 6. Shrunk contextual boundary value-add in batter profiles (all 10 occurrences)
target6 = "Shrunk contextual boundary value-add"
repl6 = "Shrunk contextual batting value-add"
count6 = text.count(target6)
assert count6 == 10, f"Expected 10 occurrences of target6, found {count6}"
text = text.replace(target6, repl6)

# 7. Section F.1 clarification on supporting evidence
target7 = r"- The remaining seven batters (Allen, Head, Salt, Jaiswal, Kishan, David, Russell) exhibit positive posterior point estimates ($\Delta_{\text{EB}} \in [+2.51\%, +5.16\%]$), but their 90% CI lower bounds cross below zero. They are included on relative ranking merit within the eligible population, not as statistically confirmed positive performers."
repl7 = r"- The remaining seven batters (Allen, Head, Salt, Jaiswal, Kishan, David, Russell) exhibit positive posterior point estimates ($\Delta_{\text{EB}} \in [+2.51\%, +5.16\%]$), but their 90% CI lower bounds cross below zero. They are included on relative ranking merit within the eligible population, not as statistically confirmed positive performers. Boundary rate, strike rate and dot-ball rate serve as supporting empirical evidence, not substitutes for the primary contextual estimate."
assert target7 in text, "target7 not found"
text = text.replace(target7, repl7, 1)

# 8. Section G conclusion phrase
target8 = "demonstrate statistically defensible increases in boundary-scoring value-add as match pressure mounts."
repl8 = "demonstrate statistically defensible positive contextual batting value-add as match pressure mounts."
assert target8 in text, "target8 not found"
text = text.replace(target8, repl8, 1)

with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Saved FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md successfully.")

# Mirror copies
import shutil
shutil.copy("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "audit_reports/M5_5B_4_3_8/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md")
shutil.copy("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "submission/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md")
print("Mirrored to audit_reports and submission successfully.")
