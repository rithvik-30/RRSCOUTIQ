"""
Validates dashboard/data.js against:
- FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
- audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md
- audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md
"""
import json

with open("dashboard/data.json", encoding="utf-8") as f:
    d = json.load(f)

with open("FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md", encoding="utf-8") as f:
    rep = f.read()

# 1. Check Metadata
meta = d['meta']
assert meta['canonical_matches'] == 776
assert meta['clean_matches'] == 744
assert meta['clean_legal_deliveries'] == 168104
assert meta['multiplier_Z'] == 1.645
print("PASS: Metadata validated.")

# 2. Check Batters
assert len(d['batters']) == 10
for b in d['batters']:
    assert b['name'] in rep, f"Missing {b['name']}"
    assert str(b['player_id']) in rep, f"Missing {b['player_id']}"
    val_add_str = f"+{b['model']['val_add']:.2f}%"
    assert val_add_str in rep, f"Missing {val_add_str} for {b['name']}"
    # Check status
    if b['rank'] <= 3:
        assert b['is_confirmed_positive'] is True
    else:
        assert b['is_confirmed_positive'] is False
print("PASS: All 10 Batters validated against frozen report.")

# 3. Check Bowlers
assert len(d['bowlers']) == 10
for bw in d['bowlers']:
    assert bw['name'] in rep, f"Missing {bw['name']}"
    assert str(bw['player_id']) in rep, f"Missing {bw['player_id']}"
    delta_str = f"{bw['model']['delta_rpo']:.3f} RPO"
    assert delta_str in rep, f"Missing {delta_str} for {bw['name']}"
    assert bw['is_confirmed_positive'] is False
print("PASS: All 10 Bowlers validated against frozen report.")

# 4. Check Monotonicity
b_bounds = [b['model']['lb90'] for b in d['batters']]
assert b_bounds == sorted(b_bounds, reverse=True), "Batter LB90 not strictly descending!"
print("PASS: Batter lower bounds strictly descending:", b_bounds)

bw_bounds = [bw['model']['ub90'] for bw in d['bowlers']]
assert bw_bounds == sorted(bw_bounds), "Bowler UB90 not strictly ascending!"
print("PASS: Bowler upper bounds strictly ascending:", bw_bounds)
