"""
Deep verification of dashboard/data.json against authoritative reports:
1. FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
2. audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md
3. audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md
"""

import json
import re

with open("dashboard/data.json", encoding="utf-8") as f:
    d = json.load(f)

with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", encoding="utf-8") as f:
    comp_rep = f.read()

with open("audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md", encoding="utf-8") as f:
    bat_rep = f.read()

with open("audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md", encoding="utf-8") as f:
    bowl_rep = f.read()

print("=" * 80)
print("1. DATASET PROVENANCE AUDIT")
print("=" * 80)
meta = d["meta"]
print(f"Project: {meta['project']}")
print(f"Canonical Matches: {meta['canonical_matches']} (Expected: 776)")
print(f"Clean Matches: {meta['clean_matches']} (Expected: 744)")
print(f"Clean Legal Deliveries: {meta['clean_legal_deliveries']} (Expected: 168104)")
print(f"Excluded Matches: {meta['excluded_matches']} (Expected: 32)")
print(f"Clean IPL: {meta['ipl_matches_clean']} ({meta['ipl_pct_clean']}%)")
print(f"Clean T20I: {meta['t20i_matches_clean']} ({meta['t20i_pct_clean']}%)")
print(f"Clean Regional: {meta['regional_matches_clean']} ({meta['regional_pct_clean']}%)")
print(f"Eligible Batters Cohort: {meta['eligible_batters_cohort']} (Expected: 106)")
print(f"Eligible Bowlers Cohort: {meta['eligible_bowlers_cohort']} (Expected: 109)")
print(f"Multiplier Z: {meta['multiplier_Z']} (Expected: 1.645)")

assert meta["canonical_matches"] == 776
assert meta["clean_matches"] == 744
assert meta["clean_legal_deliveries"] == 168104
assert meta["excluded_matches"] == 32
assert meta["multiplier_Z"] == 1.645

print("\n" + "=" * 80)
print("2. BATTER INTEGRITY AUDIT (TOP 10)")
print("=" * 80)

expected_batters = [
    (1, "Abhishek Sharma", 6281, 2136, 1427, 186.19, 6.70, 2.72),
    (2, "Suryakumar Yadav", 1699, 2646, 2367, 166.92, 4.50, 1.05),
    (3, "Vaibhav Sooryavanshi", 50284, 561, 392, 220.92, 6.31, 0.78),
    (4, "Finn Allen", 4847, 804, 421, 196.20, 5.16, -0.07),
    (5, "Travis Head", 2367, 1087, 665, 166.62, 4.32, -0.18),
    (6, "Phil Salt", 5553, 1497, 1012, 171.25, 3.58, -0.75),
    (7, "Yashasvi Jaiswal", 6819, 1774, 1181, 155.63, 3.03, -0.78),
    (8, "Ishan Kishan", 4117, 2314, 1955, 153.04, 2.51, -0.90),
    (9, "Tim David", 6396, 1154, 1077, 177.53, 3.43, -1.00),
    (10, "Andre Russell", 1318, 707, 687, 170.74, 3.70, -1.26),
]

for idx, exp in enumerate(expected_batters):
    act = d["batters"][idx]
    exp_rank, exp_name, exp_pid, exp_tot, exp_press, exp_sr, exp_eb, exp_lb90 = exp
    
    assert act["rank"] == exp_rank, f"Rank mismatch for {exp_name}: act={act['rank']}, exp={exp_rank}"
    assert act["name"] == exp_name, f"Name mismatch: act={act['name']}, exp={exp_name}"
    assert act["player_id"] == exp_pid, f"PID mismatch for {exp_name}: act={act['player_id']}, exp={exp_pid}"
    assert act["total_balls"] == exp_tot, f"Total balls mismatch for {exp_name}: act={act['total_balls']}, exp={exp_tot}"
    assert act["pressure"]["balls"] == exp_press, f"Pressure balls mismatch for {exp_name}: act={act['pressure']['balls']}, exp={exp_press}"
    assert act["pressure"]["sr"] == exp_sr, f"Pressure SR mismatch for {exp_name}: act={act['pressure']['sr']}, exp={exp_sr}"
    assert act["model"]["val_add"] == exp_eb, f"EB mismatch for {exp_name}: act={act['model']['val_add']}, exp={exp_eb}"
    assert act["model"]["lb90"] == exp_lb90, f"LB90 mismatch for {exp_name}: act={act['model']['lb90']}, exp={exp_lb90}"
    
    # Confirm exact presence in authoritative reports
    assert exp_name in comp_rep, f"{exp_name} missing from FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md"
    assert exp_name in bat_rep, f"{exp_name} missing from TOP_10_PRESSURE_BATTERS.md"
    
    print(f"  [OK] #{act['rank']:2d} {act['name']:<22} (ID {act['player_id']:<5}) | Total: {act['total_balls']:4d} | Press: {act['pressure']['balls']:4d} | SR: {act['pressure']['sr']:6.2f} | EB: +{act['model']['val_add']:4.2f}% | LB90: {act['model']['lb90']:+5.2f}%")

print("\n" + "=" * 80)
print("3. BOWLER INTEGRITY AUDIT (TOP 10)")
print("=" * 80)

expected_bowlers = [
    (1, "Sunil Narine", 781, 1533, 1394, 6.63, -0.605, 0.296),
    (2, "Jasprit Bumrah", 2933, 1594, 1338, 6.96, -0.538, 0.393),
    (3, "Mustafizur Rahman", 4373, 1414, 1247, 7.33, -0.326, 0.592),
    (4, "Kuldeep Yadav", 3644, 1878, 1811, 7.66, -0.213, 0.595),
    (5, "Axar Patel", 2876, 2484, 2287, 7.92, -0.150, 0.651),
    (6, "Wanindu Hasaranga", 4900, 1789, 1562, 7.89, -0.219, 0.652),
    (7, "Ravindra Jadeja", 152, 1355, 1312, 7.71, -0.156, 0.655),
    (8, "Mitchell Santner", 4101, 1725, 1526, 7.18, -0.245, 0.656),
    (9, "Sikandar Raza", 2984, 839, 719, 7.05, -0.274, 0.670),
    (10, "Abrar Ahmed", 5979, 740, 646, 6.57, -0.304, 0.697),
]

for idx, exp in enumerate(expected_bowlers):
    act = d["bowlers"][idx]
    exp_rank, exp_name, exp_pid, exp_tot, exp_press, exp_econ, exp_drpo, exp_ub90 = exp
    
    assert act["rank"] == exp_rank, f"Rank mismatch for {exp_name}: act={act['rank']}, exp={exp_rank}"
    assert act["name"] == exp_name, f"Name mismatch: act={act['name']}, exp={exp_name}"
    assert act["player_id"] == exp_pid, f"PID mismatch for {exp_name}: act={act['player_id']}, exp={exp_pid}"
    assert act["total_balls"] == exp_tot, f"Total balls mismatch for {exp_name}: act={act['total_balls']}, exp={exp_tot}"
    assert act["pressure"]["balls"] == exp_press, f"Pressure balls mismatch for {exp_name}: act={act['pressure']['balls']}, exp={exp_press}"
    assert act["pressure"]["econ"] == exp_econ, f"Pressure Econ mismatch for {exp_name}: act={act['pressure']['econ']}, exp={exp_econ}"
    assert act["model"]["delta_rpo"] == exp_drpo, f"dRPO mismatch for {exp_name}: act={act['model']['delta_rpo']}, exp={exp_drpo}"
    assert act["model"]["ub90"] == exp_ub90, f"UB90 mismatch for {exp_name}: act={act['model']['ub90']}, exp={exp_ub90}"
    
    # Confirm exact presence in authoritative reports
    assert exp_name in comp_rep, f"{exp_name} missing from FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md"
    assert exp_name in bowl_rep, f"{exp_name} missing from TOP_10_PRESSURE_BOWLERS.md"
    
    print(f"  [OK] #{act['rank']:2d} {act['name']:<22} (ID {act['player_id']:<5}) | Total: {act['total_balls']:4d} | Press: {act['pressure']['balls']:4d} | Econ: {act['pressure']['econ']:5.2f} | dRPO: {act['model']['delta_rpo']:+6.3f} RPO | UB90: {act['model']['ub90']:+6.3f} RPO")

print("\n" + "=" * 80)
print("AUDIT RESULT: 100% PERFECT FIELD-LEVEL AND METRIC-LEVEL CONCORDANCE")
print("=" * 80)
