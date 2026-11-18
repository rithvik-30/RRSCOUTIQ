"""
Freezes verification script for RR ScoutIQ Competition Report
"""
import re

with open('FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md', encoding='utf-8') as f:
    text = f.read()

batters = [
    'Abhishek Sharma', 'Suryakumar Yadav', 'Vaibhav Sooryavanshi', 'Finn Allen',
    'Travis Head', 'Phil Salt', 'Yashasvi Jaiswal', 'Ishan Kishan',
    'Tim David', 'Andre Russell'
]

bowlers = [
    'Sunil Narine', 'Jasprit Bumrah', 'Mustafizur Rahman', 'Kuldeep Yadav',
    'Axar Patel', 'Wanindu Hasaranga', 'Ravindra Jadeja', 'Mitchell Santner',
    'Sikandar Raza', 'Abrar Ahmed'
]

sections = [
    'Normal Conditions (T1)',
    'Combined Pressure (T2–T4)',
    'High Pressure (T3–T4)',
    'Extreme Pressure (T4)',
    'Contextual Model Estimate & Uncertainty'
]

print("=== VERIFYING BATTERS (10) ===")
b_pass = True
for b in batters:
    pattern = rf'#### \d+\. {re.escape(b)} \(Local ID: `\d+`\)(.*?)(?=####|\n---|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        print(f"FAIL: {b} not found!")
        b_pass = False
        continue
    content = match.group(1)
    missing = [s for s in sections if s not in content]
    if missing:
        print(f"FAIL: {b} missing: {missing}")
        b_pass = False
    else:
        print(f"PASS: {b} (All 5 sections present)")

print("\n=== VERIFYING BOWLERS (10) ===")
bw_pass = True
for bw in bowlers:
    pattern = rf'#### \d+\. {re.escape(bw)} \(Local ID: `\d+`\)(.*?)(?=####|\n---|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        print(f"FAIL: {bw} not found!")
        bw_pass = False
        continue
    content = match.group(1)
    missing = [s for s in sections if s not in content]
    if missing:
        print(f"FAIL: {bw} missing: {missing}")
        bw_pass = False
    else:
        print(f"PASS: {bw} (All 5 sections present)")

print(f"\nAll Batters Pass: {b_pass}")
print(f"All Bowlers Pass: {bw_pass}")
