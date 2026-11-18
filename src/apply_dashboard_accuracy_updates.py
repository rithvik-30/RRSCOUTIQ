"""
Applies exact presentation and accuracy updates to:
1. dashboard/index.html
2. dashboard/app.js
"""

# 1. Update dashboard/index.html
with open("dashboard/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Update hero subtext
old_hero = "across 744 clean T20 fixtures."
new_hero = "across 744 clean modeling matches across IPL, T20I and regional T20 cricket, comprising 168,104 clean legal deliveries."
assert old_hero in html, "old_hero not found"
html = html.replace(old_hero, new_hero, 1)

# Update stat-note in stats strip
old_stat_note = '<span class="stat-note">362 IPL (48.7%) • 381 T20I (51.2%)</span>'
new_stat_note = '<span class="stat-note">362 IPL (48.66%) • 381 T20I (51.21%) • 1 Regional (0.13%)</span>'
assert old_stat_note in html, "old_stat_note not found"
html = html.replace(old_stat_note, new_stat_note, 1)

# Update Highlight Box 1
old_hl1 = "Only 3 batters in elite cricket demonstrate confirmed positive boundary value-add with 95% one-sided confidence: <strong>Abhishek Sharma (+2.72% LB)</strong>, <strong>Suryakumar Yadav (+1.05% LB)</strong>, and <strong>Vaibhav Sooryavanshi (+0.78% LB)</strong>."
new_hl1 = "Only 3 batters in elite cricket demonstrate confirmed positive contextual batting value-add with 95% one-sided confidence: <strong>Abhishek Sharma (+2.72% LB)</strong>, <strong>Suryakumar Yadav (+1.05% LB)</strong>, and <strong>Vaibhav Sooryavanshi (+0.78% LB)</strong>. Boundary rate, strike rate and dot-ball rate provide supporting empirical evidence."
assert old_hl1 in html, "old_hl1 not found"
html = html.replace(old_hl1, new_hl1, 1)

# Update Highlight Box 2
old_hl2 = "<strong>Sunil Narine</strong> (-0.605 RPO delta) and <strong>Jasprit Bumrah</strong> (-0.538 RPO delta) lead all bowlers in contextual run suppression, systematically holding economy under 6.70 RPO even in Tier 4 terminal crunch time."
new_hl2 = "<strong>Sunil Narine</strong> (-0.605 RPO delta) and <strong>Jasprit Bumrah</strong> (-0.538 RPO delta) lead all bowlers in contextual run suppression, holding combined pressure economy to 6.63 RPO and 6.96 RPO, and Tier 4 crunch economy to 5.85 RPO and 6.68 RPO respectively."
assert old_hl2 in html, "old_hl2 not found"
html = html.replace(old_hl2, new_hl2, 1)

# Update Method Card 02 (DLI)
old_card2 = (
    '<div class="formula-box">\n'
    '                DLI_chase = Clamp[(RRR/CRR_phase) * (10/(W+1))^0.5 * (1 + 24/(B+12))^0.5, 0.1, 5.0]<br>\n'
    '                DLI_set = Clamp[Phi(t) * (10/(W+1))^0.6 * (1 + stag)^0.5, 0.2, 3.5]\n'
    '              </div>'
)
new_card2 = (
    '<div class="formula-box">\n'
    '                DLI_chase = clamp[(RRR / CRR_phase) × (10 / (wickets_in_hand + 1))^0.50 × (1 + 24 / (balls_remaining + 12))^0.50, 0.10, 5.00]<br>\n'
    '                DLI_setting = clamp[Φ(t) × (10 / (wickets_in_hand + 1))^0.60 × (1 + max(0, (CRR_phase - CRR) / 6))^0.50, 0.20, 3.50]<br>\n'
    '                where Φ(t) = 0.80 + 0.70 × (t / 120)^1.20, stagnation active for t ≥ 6; Super Over DLI = 3.50\n'
    '              </div>'
)

if old_card2 not in html:
    old_card2 = old_card2.replace("\n", "\r\n")
    new_card2 = new_card2.replace("\n", "\r\n")

assert old_card2 in html, "old_card2 not found"
html = html.replace(old_card2, new_card2, 1)

# Update Method Card 06 (Credibility bounds)
old_card6 = (
    '<p class="method-card-text">\n'
    '                Rankings are based on the conservative endpoint of the 90% two-sided credible interval (equivalent to 95% one-sided bound). Batters rank descending by LB; bowlers rank ascending by UB (lower economy relative to par is superior).\n'
    '              </p>'
)
new_card6 = (
    '<p class="method-card-text">\n'
    '                Rankings are based on the conservative endpoint of a 90% two-sided credible interval, mathematically equivalent to a 95% one-sided credible bound under the Gaussian posterior convention (Z = 1.645). Batters rank descending by LB (ensuring value-add is at least LB90 with 95% confidence); bowlers rank ascending by UB (ensuring economy delta is at most UB90 with 95% confidence; lower is superior).\n'
    '              </p>'
)

if old_card6 not in html:
    old_card6 = old_card6.replace("\n", "\r\n")
    new_card6 = new_card6.replace("\n", "\r\n")

assert old_card6 in html, "old_card6 not found"
html = html.replace(old_card6, new_card6, 1)

with open("dashboard/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Saved dashboard/index.html successfully.")

# 2. Update dashboard/app.js
with open("dashboard/app.js", "r", encoding="utf-8") as f:
    app_js = f.read()

old_app_sub = "if (box1Sub) box1Sub.textContent = `Contextual Boundary Val-Add (Δ_EB)`;"
new_app_sub = "if (box1Sub) box1Sub.textContent = `Contextual Batting Val-Add (Δ_EB)`;"
assert old_app_sub in app_js, "old_app_sub not found in app.js"
app_js = app_js.replace(old_app_sub, new_app_sub, 1)

with open("dashboard/app.js", "w", encoding="utf-8") as f:
    f.write(app_js)

print("Saved dashboard/app.js successfully.")
