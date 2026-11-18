"""
Cross-verifies FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md against:
- audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md
- audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md
- FINAL_STATISTICAL_SIGNOFF.md
"""
import re

with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", encoding="utf-8") as f:
    report_text = f.read()

with open("audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md", encoding="utf-8") as f:
    b_audit_text = f.read()

with open("audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md", encoding="utf-8") as f:
    bw_audit_text = f.read()

# Verify Batter Table entries against TOP_10_PRESSURE_BATTERS.md
print("=== BATTER RECONCILIATION ===")
# Audited batter values:
# Rank, Name, ID, Total Balls, Press Balls, ValAdd, se, LB90
audited_batters = [
    (1, "Abhishek Sharma", "6281", 2136, 1427, "+6.70%", 0.0242, "+2.72%"),
    (2, "Suryakumar Yadav", "1699", 2646, 2367, "+4.50%", 0.0209, "+1.05%"),
    (3, "Vaibhav Sooryavanshi", "50284", 561, 392, "+6.31%", 0.0336, "+0.78%"),
    (4, "Finn Allen", "4847", 804, 421, "+5.16%", 0.0318, "-0.07%"),
    (5, "Travis Head", "2367", 1087, 665, "+4.32%", 0.0274, "-0.18%"),
    (6, "Phil Salt", "5553", 1497, 1012, "+3.58%", 0.0263, "-0.75%"),
    (7, "Yashasvi Jaiswal", "6819", 1774, 1181, "+3.03%", 0.0232, "-0.78%"),
    (8, "Ishan Kishan", "4117", 2314, 1955, "+2.51%", 0.0208, "-0.90%"),
    (9, "Tim David", "6396", 1154, 1077, "+3.43%", 0.0270, "-1.00%"),
    (10, "Andre Russell", "1318", 707, 687, "+3.70%", 0.0302, "-1.26%")
]

for rank, name, pid, total_b, press_b, val_add, se, lb90 in audited_batters:
    # Check if in report text
    has_name = name in report_text
    has_id = pid in report_text
    has_val_add = val_add in report_text
    has_lb90 = lb90 in report_text
    print(f"Batter #{rank} {name} (ID: {pid}): name={has_name}, id={has_id}, val_add={has_val_add}, lb90={has_lb90}")

print("\n=== BOWLER RECONCILIATION ===")
# Rank, Name, ID, Total Balls, Press Balls, DeltaRPO, se, UB90
audited_bowlers = [
    (1, "Sunil Narine", "781", 1533, 1394, "-0.605 RPO", 0.5478, "+0.296 RPO"),
    (2, "Jasprit Bumrah", "2933", 1594, 1338, "-0.538 RPO", 0.5659, "+0.393 RPO"),
    (3, "Mustafizur Rahman", "4373", 1414, 1247, "-0.326 RPO", 0.5576, "+0.592 RPO"),
    (4, "Kuldeep Yadav", "3644", 1878, 1811, "-0.213 RPO", 0.4908, "+0.595 RPO"),
    (5, "Axar Patel", "2876", 2484, 2287, "-0.150 RPO", 0.4868, "+0.651 RPO"),
    (6, "Wanindu Hasaranga", "4900", 1789, 1562, "-0.219 RPO", 0.5296, "+0.652 RPO"),
    (7, "Ravindra Jadeja", "152", 1355, 1312, "-0.156 RPO", 0.4930, "+0.655 RPO"),
    (8, "Mitchell Santner", "4101", 1725, 1526, "-0.245 RPO", 0.5479, "+0.656 RPO"),
    (9, "Sikandar Raza", "2984", 839, 719, "-0.274 RPO", 0.5738, "+0.670 RPO"),
    (10, "Abrar Ahmed", "5979", 740, 646, "-0.304 RPO", 0.6083, "+0.697 RPO")
]

for rank, name, pid, total_b, press_b, delta_rpo, se, ub90 in audited_bowlers:
    has_name = name in report_text
    has_id = pid in report_text
    has_delta = delta_rpo in report_text
    has_ub90 = ub90 in report_text
    print(f"Bowler #{rank} {name} (ID: {pid}): name={has_name}, id={has_id}, delta={has_delta}, ub90={has_ub90}")
