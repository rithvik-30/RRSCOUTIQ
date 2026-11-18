import pandas as pd
import numpy as np

# Chase DLI Formulation A
def dli_chase(rrr, w_hand, b_rem, crr_phase):
    term_rate = rrr / crr_phase
    term_wkt = (10.0 / (w_hand + 1.0)) ** 0.50
    term_time = (1.0 + 24.0 / (b_rem + 12.0)) ** 0.50
    raw = term_rate * term_wkt * term_time
    clamped = np.clip(raw, 0.10, 5.00)
    return raw, clamped

# Setting DLI Formulation A
def dli_setting(phase, w_hand, crr, crr_phase):
    phi_map = {'Powerplay': 0.90, 'Middle': 1.00, 'Death': 1.50}
    phi = phi_map[phase]
    term_wkt = (10.0 / (w_hand + 1.0)) ** 0.60
    stagnation = np.maximum(0.0, (crr_phase - crr) / 6.0)
    term_stag = (1.0 + stagnation) ** 0.50
    raw = phi * term_wkt * term_stag
    clamped = np.clip(raw, 0.20, 3.50)
    return raw, clamped

# Scenarios
scenarios = [
    # (name, type, rrr/crr, w_hand, b_rem, phase, crr_phase)
    ("Dead Chase (Low Target)", "chase", 1.33, 9, 36, "Death", 9.30),
    ("Comfortable Chase", "chase", 6.67, 7, 36, "Death", 9.30),
    ("Par Chase Middle Overs", "chase", 8.00, 7, 60, "Middle", 8.00),
    ("Pressure Middle Overs", "chase", 10.50, 5, 48, "Middle", 8.00),
    ("Tight Death Chase", "chase", 10.00, 6, 18, "Death", 9.30),
    ("High-Pressure Finish (Over 19)", "chase", 12.00, 4, 12, "Death", 9.30),
    ("Extreme Crisis (Over 20)", "chase", 20.00, 2, 6, "Death", 9.30),
    ("Desperate Finish (Impossible)", "chase", 45.00, 1, 6, "Death", 9.30),
    ("Early Chase Powerplay Par", "chase", 8.50, 10, 100, "Powerplay", 8.15),
    ("Powerplay Collapse Chase", "chase", 9.50, 6, 90, "Powerplay", 8.15),
    ("Setting PP Dominant (60/0)", "setting", 10.00, 10, None, "Powerplay", 8.15),
    ("Setting PP Steady (45/1)", "setting", 7.50, 9, None, "Powerplay", 8.15),
    ("Setting PP Collapse (25/4)", "setting", 4.16, 6, None, "Powerplay", 8.15),
    ("Setting Middle Steady (90/2)", "setting", 8.18, 8, None, "Middle", 8.00),
    ("Setting Middle Collapse (70/6)", "setting", 5.83, 4, None, "Middle", 8.00),
    ("Setting Death Launch (150/3)", "setting", 8.82, 7, None, "Death", 9.30),
    ("Setting Death Tail (110/8)", "setting", 6.47, 2, None, "Death", 9.30),
    ("Super Over", "super_over", None, None, None, "Death", None),
]

results = []
for sc in scenarios:
    name, stype, rate, w, b, phase, crr_p = sc
    if stype == "chase":
        raw, clamped = dli_chase(rate, w, b, crr_p)
    elif stype == "setting":
        raw, clamped = dli_setting(phase, w, rate, crr_p)
    else: # super over
        raw, clamped = 3.50, 3.50
    
    # Tier assignment
    if clamped < 0.75:
        tier = "Tier 1: Low"
    elif clamped < 1.35:
        tier = "Tier 2: Medium"
    elif clamped < 2.25:
        tier = "Tier 3: High"
    else:
        tier = "Tier 4: Extreme"
        
    results.append({
        'Scenario': name,
        'Type': stype.upper(),
        'Phase': phase,
        'Rate': rate,
        'W_hand': w,
        'B_rem': b,
        'Raw DLI': round(raw, 3),
        'Clamped DLI': round(clamped, 3),
        'Tier': tier
    })

df_res = pd.DataFrame(results)
print("=== DLI FORMULATION A SCENARIO STRESS TESTS ===")
print(df_res.to_string(index=False))

# Sensitivity & Variable Dominance in Chase
print("\n=== SENSITIVITY ANALYSIS: PARTIAL DERIVATIVES & ELASTICITIES (AT BASELINE CHASE) ===")
# Baseline: RRR = 9.0, W_hand = 7, B_rem = 36, CRR_phase = 9.30
b_rrr, b_w, b_b, b_cp = 9.0, 7, 36, 9.30
base_raw, _ = dli_chase(b_rrr, b_w, b_b, b_cp)

# +10% RRR
raw_rrr, _ = dli_chase(b_rrr * 1.10, b_w, b_b, b_cp)
e_rrr = (raw_rrr - base_raw) / base_raw / 0.10

# -10% W_hand (w_hand = 6.3)
raw_w, _ = dli_chase(b_rrr, b_w * 0.90, b_b, b_cp)
e_w = (raw_w - base_raw) / base_raw / (-0.10) # elasticity w.r.t lost wickets

# -10% B_rem (b_rem = 32.4)
raw_b, _ = dli_chase(b_rrr, b_w, b_b * 0.90, b_cp)
e_b = (raw_b - base_raw) / base_raw / (-0.10) # elasticity w.r.t fewer balls

print(f"Baseline Chase Raw DLI: {base_raw:.3f}")
print(f"Elasticity wrt RRR (+10% RRR -> % DLI change): {e_rrr:.3f} (Linear: exact 1.00)")
print(f"Elasticity wrt Wickets in hand (-10% W -> % DLI change): {e_w:.3f}")
print(f"Elasticity wrt Balls remaining (-10% B -> % DLI change): {e_b:.3f}")

