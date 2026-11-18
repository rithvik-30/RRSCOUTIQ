import json

with open("dashboard/data.json", encoding="utf-8") as f:
    d = json.load(f)

print("--- Batters T2-4 vs T4 ---")
for b in d["batters"]:
    print(f"{b['name']:<22} | Combined SR={b['pressure']['sr']:6.2f} ({b['pressure']['balls']}b) | T4 SR={b['t4']['sr']:6.2f} ({b['t4']['balls']}b)")

print("\n--- Bowlers T2-4 vs T4 ---")
for bw in d["bowlers"]:
    print(f"{bw['name']:<22} | Combined Econ={bw['pressure']['econ']:5.2f} ({bw['pressure']['balls']}b) | T4 Econ={bw['t4']['econ']:5.2f} ({bw['t4']['balls']}b)")
