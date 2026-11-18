"""
Final Bayesian terminology-only correction:
Replaces statements that say LB90 or UB90 "ensures" a result with "95% confidence"
with precise Bayesian terminology:
- Batter LB90: "95% one-sided lower posterior credible bound for contextual batting value-add."
- Bowler UB90: "95% one-sided upper posterior credible bound for contextual economy delta."
Retains Z = 1.645 and 90% two-sided credible interval explanation.
"""

import os
import shutil

# ----------------------------------------------------------------------------
# 1. Update FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
# ----------------------------------------------------------------------------
with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "r", encoding="utf-8") as f:
    text = f.read()

# Line 35
t_exec = "- **Conservative Credibility Bounds:** Ranks players using conservative bounds based on the approved 1.645 standard error multiplier (lower bound of the 90% two-sided credible interval, equivalent to a 95% one-sided credible bound)."
r_exec = "- **Conservative Credibility Bounds:** Ranks players using conservative bounds based on the approved 1.645 standard error multiplier (endpoint of the 90% two-sided credible interval, mathematically equivalent to a 95% one-sided posterior credible bound under the Gaussian posterior convention: lower posterior credible bound for batters, upper posterior credible bound for bowlers)."
assert t_exec in text, "t_exec not found"
text = text.replace(t_exec, r_exec, 1)

# Lines 142-146
t_meth = (
    "Under the approved statistical sign-off convention (`FINAL_STATISTICAL_SIGNOFF.md`), rankings are based on the **conservative endpoint of the 90% two-sided credible interval, which mathematically corresponds to a 95% one-sided credible bound** using multiplier $Z = 1.645$:\n"
    "- For batters: $\\text{LB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} - 1.645 \\times se_{\\text{latent}}$ (95% one-sided lower credible bound).\n"
    "- For bowlers: $\\text{UB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} + 1.645 \\times se_{\\text{latent}}$ (95% one-sided upper credible bound)."
)
r_meth = (
    "Under the approved statistical sign-off convention (`FINAL_STATISTICAL_SIGNOFF.md`), rankings are based on the **conservative endpoint of the 90% two-sided credible interval, which mathematically corresponds to a 95% one-sided posterior credible bound under the Gaussian posterior convention** using multiplier $Z = 1.645$:\n"
    "- For batters: $\\text{LB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} - 1.645 \\times se_{\\text{latent}}$ (95% one-sided lower posterior credible bound for contextual batting value-add).\n"
    "- For bowlers: $\\text{UB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} + 1.645 \\times se_{\\text{latent}}$ (95% one-sided upper posterior credible bound for contextual economy delta)."
)
if t_meth not in text:
    t_meth = t_meth.replace("\n", "\r\n")
    r_meth = r_meth.replace("\n", "\r\n")
assert t_meth in text, "t_meth not found"
text = text.replace(t_meth, r_meth, 1)

# Line 155
t_rank_b = "Ranked strictly by the conservative lower bound of the 90% two-sided credible interval (95% one-sided credible lower bound, $Z = 1.645$) in descending order within the eligible population"
r_rank_b = "Ranked strictly by the conservative lower bound of the 90% two-sided credible interval (95% one-sided lower posterior credible bound for contextual batting value-add, $Z = 1.645$) in descending order within the eligible population"
assert t_rank_b in text, "t_rank_b not found"
text = text.replace(t_rank_b, r_rank_b, 1)

# Line 178
t_rank_bw = "Ranked strictly by the conservative upper bound of the 90% two-sided credible interval (95% one-sided credible upper bound, $Z = 1.645$) in ascending order within the eligible population"
r_rank_bw = "Ranked strictly by the conservative upper bound of the 90% two-sided credible interval (95% one-sided upper posterior credible bound for contextual economy delta, $Z = 1.645$) in ascending order within the eligible population"
assert t_rank_bw in text, "t_rank_bw not found"
text = text.replace(t_rank_bw, r_rank_bw, 1)

# Line 372
t_conf_b1 = "Under the approved convention ($Z = 1.645$, representing the 90% two-sided credible interval lower bound and 95% one-sided credible lower bound), **only three batters** possess positive lower bounds:"
r_conf_b1 = "Under the approved convention ($Z = 1.645$, representing the 90% two-sided credible interval lower bound and 95% one-sided lower posterior credible bound for contextual batting value-add), **only three batters** possess positive lower bounds:"
assert t_conf_b1 in text, "t_conf_b1 not found"
text = text.replace(t_conf_b1, r_conf_b1, 1)

# Line 374
t_conf_b2 = "They are included on relative ranking merit within the eligible population, not as statistically confirmed positive performers."
r_conf_b2 = "They are included on relative ranking merit within the eligible population, not as confirmed positive performers under a positive 95% one-sided lower posterior credible bound."
assert t_conf_b2 in text, "t_conf_b2 not found"
text = text.replace(t_conf_b2, r_conf_b2, 1)

with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "w", encoding="utf-8") as f:
    f.write(text)

shutil.copy("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "audit_reports/M5_5B_4_3_8/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md")
shutil.copy("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", "submission/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md")
print("1. FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md updated and mirrored.")

# ----------------------------------------------------------------------------
# 2. Update submission/METHODOLOGY.md
# ----------------------------------------------------------------------------
with open("submission/METHODOLOGY.md", "r", encoding="utf-8") as f:
    meth_text = f.read()

t_m1 = "- **Batters:** $\\text{LB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} - 1.645 \\times se_{\\text{latent}}$ (95% one-sided lower credible bound). Ranking descending ensures that we are 95% confident the batter's true contextual value-add is at least $\\text{LB}_{90\\% \\text{ CI}}$."
r_m1 = "- **Batters:** $\\text{LB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} - 1.645 \\times se_{\\text{latent}}$ serves as the 95% one-sided lower posterior credible bound for contextual batting value-add under the Gaussian posterior convention ($Z = 1.645$). Batters rank in descending order."
assert t_m1 in meth_text, "t_m1 not found"
meth_text = meth_text.replace(t_m1, r_m1, 1)

t_m2 = "- **Bowlers:** $\\text{UB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} + 1.645 \\times se_{\\text{latent}}$ (95% one-sided upper credible bound). Ranking ascending ensures that we are 95% confident the bowler's true contextual economy delta is at most $\\text{UB}_{90\\% \\text{ CI}}$ (lower economy indicates superior run prevention)."
r_m2 = "- **Bowlers:** $\\text{UB}_{90\\% \\text{ CI}} = \\Delta_{\\text{EB}} + 1.645 \\times se_{\\text{latent}}$ serves as the 95% one-sided upper posterior credible bound for contextual economy delta under the Gaussian posterior convention ($Z = 1.645$). Bowlers rank in ascending order (lower economy indicates superior run prevention)."
assert t_m2 in meth_text, "t_m2 not found"
meth_text = meth_text.replace(t_m2, r_m2, 1)

t_m3 = "meaning their positive value-add is not confirmed with 95% one-sided confidence."
r_m3 = "meaning their positive value-add does not establish a positive 95% one-sided lower posterior credible bound for contextual batting value-add."
assert t_m3 in meth_text, "t_m3 not found"
meth_text = meth_text.replace(t_m3, r_m3, 1)

t_m4 = "economy suppression below context is not established with 95% one-sided confidence."
r_m4 = "economy suppression below context is not established under a negative 95% one-sided upper posterior credible bound for contextual economy delta."
assert t_m4 in meth_text, "t_m4 not found"
meth_text = meth_text.replace(t_m4, r_m4, 1)

with open("submission/METHODOLOGY.md", "w", encoding="utf-8") as f:
    f.write(meth_text)
print("2. submission/METHODOLOGY.md updated.")

# ----------------------------------------------------------------------------
# 3. Update dashboard/index.html
# ----------------------------------------------------------------------------
with open("dashboard/index.html", "r", encoding="utf-8") as f:
    html_text = f.read()

t_h1 = "Only 3 batters in elite cricket demonstrate confirmed positive contextual batting value-add with 95% one-sided confidence: <strong>Abhishek Sharma (+2.72% LB)</strong>, <strong>Suryakumar Yadav (+1.05% LB)</strong>, and <strong>Vaibhav Sooryavanshi (+0.78% LB)</strong>."
r_h1 = "Only 3 batters in elite cricket possess a positive 95% one-sided lower posterior credible bound for contextual batting value-add: <strong>Abhishek Sharma (+2.72% LB)</strong>, <strong>Suryakumar Yadav (+1.05% LB)</strong>, and <strong>Vaibhav Sooryavanshi (+0.78% LB)</strong>."
assert t_h1 in html_text, "t_h1 not found"
html_text = html_text.replace(t_h1, r_h1, 1)

t_h2 = (
    '<p class="method-card-text">\n'
    '                Rankings are based on the conservative endpoint of a 90% two-sided credible interval, mathematically equivalent to a 95% one-sided credible bound under the Gaussian posterior convention (Z = 1.645). Batters rank descending by LB (ensuring value-add is at least LB90 with 95% confidence); bowlers rank ascending by UB (ensuring economy delta is at most UB90 with 95% confidence; lower is superior).\n'
    '              </p>'
)
r_h2 = (
    '<p class="method-card-text">\n'
    '                Rankings are based on the conservative endpoint of a 90% two-sided credible interval, mathematically equivalent to a 95% one-sided posterior credible bound under the Gaussian posterior convention (Z = 1.645). Batters rank descending by LB90 (95% one-sided lower posterior credible bound for contextual batting value-add); bowlers rank ascending by UB90 (95% one-sided upper posterior credible bound for contextual economy delta; lower is superior).\n'
    '              </p>'
)
if t_h2 not in html_text:
    t_h2 = t_h2.replace("\n", "\r\n")
    r_h2 = r_h2.replace("\n", "\r\n")
assert t_h2 in html_text, "t_h2 not found"
html_text = html_text.replace(t_h2, r_h2, 1)

with open("dashboard/index.html", "w", encoding="utf-8") as f:
    f.write(html_text)
print("3. dashboard/index.html updated.")

# ----------------------------------------------------------------------------
# 4. Update dashboard/app.js
# ----------------------------------------------------------------------------
with open("dashboard/app.js", "r", encoding="utf-8") as f:
    app_text = f.read()

t_a1 = "<span class=\"metric-title\">95% Lower Bound (LB_90%CI)</span>"
r_a1 = "<span class=\"metric-title\">95% Lower Posterior Bound (LB90)</span>"
assert t_a1 in app_text, "t_a1 not found"
app_text = app_text.replace(t_a1, r_a1, 1)

t_a2 = "<span class=\"metric-title\">95% Upper Bound (UB_90%CI)</span>"
r_a2 = "<span class=\"metric-title\">95% Upper Posterior Bound (UB90)</span>"
assert t_a2 in app_text, "t_a2 not found"
app_text = app_text.replace(t_a2, r_a2, 1)

t_a3 = "if (box2Sub) box2Sub.textContent = `95% Lower Bound (Z = 1.645)`;"
r_a3 = "if (box2Sub) box2Sub.textContent = `95% Lower Posterior Bound (Z = 1.645)`;"
assert t_a3 in app_text, "t_a3 not found"
app_text = app_text.replace(t_a3, r_a3, 1)

t_a4 = "if (box2Sub) box2Sub.textContent = `95% Upper Bound (Z = 1.645)`;"
r_a4 = "if (box2Sub) box2Sub.textContent = `95% Upper Posterior Bound (Z = 1.645)`;"
assert t_a4 in app_text, "t_a4 not found"
app_text = app_text.replace(t_a4, r_a4, 1)

t_a5 = "The 95% upper bound (+${player.model.ub90.toFixed(3)} RPO) crosses zero. Like all bowlers in the cohort, economy suppression below context is an empirical relative ranking rather than a statistically confirmed certainty."
r_a5 = "The 95% one-sided upper posterior credible bound (+${player.model.ub90.toFixed(3)} RPO) crosses zero. Like all bowlers in the cohort, economy suppression below context is an empirical relative ranking rather than an assertion of suppression under the credible bound."
assert t_a5 in app_text, "t_a5 not found"
app_text = app_text.replace(t_a5, r_a5, 1)

t_a6 = "<span>95% Lower Bound: <strong>${lb > 0 ? '+' : ''}${lb.toFixed(2)}%</strong></span>"
r_a6 = "<span>95% Lower Posterior Bound: <strong>${lb > 0 ? '+' : ''}${lb.toFixed(2)}%</strong></span>"
assert t_a6 in app_text, "t_a6 not found"
app_text = app_text.replace(t_a6, r_a6, 1)

t_a7 = "<span>95% Upper Bound: <strong>+${ub.toFixed(3)} RPO</strong></span>"
r_a7 = "<span>95% Upper Posterior Bound: <strong>+${ub.toFixed(3)} RPO</strong></span>"
assert t_a7 in app_text, "t_a7 not found"
app_text = app_text.replace(t_a7, r_a7, 1)

with open("dashboard/app.js", "w", encoding="utf-8") as f:
    f.write(app_text)
print("4. dashboard/app.js updated.")

# ----------------------------------------------------------------------------
# 5. Update FINAL_PRESENTATION_ACCURACY_AUDIT.md
# ----------------------------------------------------------------------------
with open("FINAL_PRESENTATION_ACCURACY_AUDIT.md", "r", encoding="utf-8") as f:
    audit_text = f.read()

t_audit = (
    "| **8** | **Credible Bound Convention** | `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`<br>`submission/METHODOLOGY.md`<br>`dashboard/index.html` | Generic 90% credible interval description | \"Endpoint of a 90% two-sided credible interval, mathematically equivalent to a 95% one-sided credible bound under the Gaussian posterior convention ($Z = 1.645$).\" | Clarifies why lower bound is used for batters (value-add $\\ge LB90$ with 95% confidence) and upper bound for bowlers (economy delta $\\le UB90$ with 95% confidence). |"
)
r_audit = (
    "| **8** | **Credible Bound Convention & Bayesian Terminology** | `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`<br>`submission/METHODOLOGY.md`<br>`dashboard/index.html`<br>`dashboard/app.js` | Generic 90% credible interval description / statements that bounds 'ensure' results with '95% confidence' | Replaced with strict Bayesian terminology: Batter LB90 is the '95% one-sided lower posterior credible bound for contextual batting value-add'; Bowler UB90 is the '95% one-sided upper posterior credible bound for contextual economy delta'. Retains $Z = 1.645$ as the endpoint of a 90% two-sided credible interval, mathematically equivalent to a 95% one-sided posterior credible bound under the Gaussian posterior convention. | Eliminates frequentist conflation ('ensures with 95% confidence') in favor of precise posterior probability statements under Bayesian decision theory. |"
)
assert t_audit in audit_text, "t_audit not found"
audit_text = audit_text.replace(t_audit, r_audit, 1)

with open("FINAL_PRESENTATION_ACCURACY_AUDIT.md", "w", encoding="utf-8") as f:
    f.write(audit_text)

shutil.copy("FINAL_PRESENTATION_ACCURACY_AUDIT.md", "audit_reports/M5_5B_4_3_8/FINAL_PRESENTATION_ACCURACY_AUDIT.md")
shutil.copy("FINAL_PRESENTATION_ACCURACY_AUDIT.md", "submission/FINAL_PRESENTATION_ACCURACY_AUDIT.md")
print("5. FINAL_PRESENTATION_ACCURACY_AUDIT.md updated and mirrored.")
