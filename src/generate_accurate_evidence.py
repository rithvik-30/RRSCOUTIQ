"""
Generates the verified player-level evidence across:
- Normal conditions (T1)
- Combined pressure (T2-T4)
- High pressure (T3-T4)
- Extreme pressure (T4)
- Contextual model estimate and uncertainty
"""
from src.generate_top20_reports import generate_reports

b_data, bw_data = generate_reports()

def format_overs(balls):
    ov = balls // 6
    rem = balls % 6
    return f"{ov}.{rem} ov" if balls > 0 else "0.0 ov"

# Dual discipline IDs based on canonical dataset:
# Batters: Abhishek Sharma (6281), Andre Russell (1318)
# Bowlers: Sunil Narine (781), Kuldeep Yadav (3644), Axar Patel (2876), 
#          Wanindu Hasaranga (4900), Ravindra Jadeja (152), Mitchell Santner (4101), Sikandar Raza (2984)

print("BATTERS:")
for b in b_data:
    pid = b['player_id']
    dual = "Dual-discipline eligible (observed batting & bowling in dataset)" if pid in [6281, 1318] else "Single-discipline eligible (Batting)"
    t4_b = b['t4']['balls']
    if t4_b > 0:
        t4_str = f"{t4_b} balls | {b['t4']['runs']} runs | {b['t4']['sr']:.2f} SR | {b['t4']['bnd_pct']:.2f}% boundary rate | {b['t4']['dot_pct']:.2f}% dot-ball rate | {b['t4']['outs']} dismissals | {b['t4']['hazard']:.2f}% dismissal hazard"
    else:
        t4_str = "0 balls faced (Zero observed exposure in Tier 4 crunch conditions)"
        
    print(f"#### {b['rank']}. {b['name']} (Local ID: `{pid}`)")
    print(f"- **Discipline Eligibility (Dataset):** {dual}")
    print(f"- **Normal Conditions (T1):** {b['normal']['balls']} balls | {b['normal']['runs']} runs | {b['normal']['sr']:.2f} SR | {b['normal']['bnd_pct']:.2f}% boundary rate | {b['normal']['dot_pct']:.2f}% dot-ball rate | {b['normal']['outs']} dismissals | {b['normal']['hazard']:.2f}% dismissal hazard")
    print(f"- **Combined Pressure (T2–T4):** {b['pressure']['balls']} balls | {b['pressure']['runs']} runs | {b['pressure']['sr']:.2f} SR | {b['pressure']['bnd_pct']:.2f}% boundary rate | {b['pressure']['dot_pct']:.2f}% dot-ball rate | {b['pressure']['outs']} dismissals | {b['pressure']['hazard']:.2f}% dismissal hazard")
    print(f"- **High Pressure (T3–T4):** {b['high']['balls']} balls | {b['high']['runs']} runs | {b['high']['sr']:.2f} SR | {b['high']['bnd_pct']:.2f}% boundary rate | {b['high']['dot_pct']:.2f}% dot-ball rate | {b['high']['outs']} dismissals | {b['high']['hazard']:.2f}% dismissal hazard")
    print(f"- **Extreme Pressure (T4):** {t4_str}")
    print(f"- **Contextual Model Estimate & Uncertainty:** Shrunk contextual boundary value-add $\\Delta_{{EB}} = {b['val_add']:+.2f}\\%$, latent standard error $se_{{latent}} = {b['se_latent']:.4f}$, conservative lower bound $\\text{{LB}}_{{90\\% \\text{{ CI}}}} = {b['lb90']:+.2f}\\%$ (95% one-sided lower bound, $Z = 1.645$). Raw pressure deltas: $\\Delta\\text{{SR}} = {b['delta_sr']:+.2f}$, $\\Delta\\text{{Bnd}} = {b['delta_bnd']:+.2f}\\%$, $\\Delta\\text{{Dot}} = {b['delta_dot']:+.2f}\\%$.\n")

print("\nBOWLERS:")
for bw in bw_data:
    pid = bw['player_id']
    if pid in [781, 3644, 2876, 4900, 152, 4101, 2984]:
        dual = "Dual-discipline eligible (observed batting & bowling in dataset; specialist bowler in competitive cricket)" if pid == 3644 else "Dual-discipline eligible (observed batting & bowling in dataset)"
    else:
        dual = "Single-discipline eligible (Bowling)"
        
    t4_b = bw['t4']['balls']
    t4_ov = format_overs(t4_b)
    if t4_b > 0:
        t4_str = f"{t4_b} balls ({t4_ov}) | {bw['t4']['runs']} runs | {bw['t4']['econ']:.2f} RPO economy | {bw['t4']['wkts']} wickets | {bw['t4']['sr']:.1f} balls/wkt | {bw['t4']['dot_pct']:.2f}% dot-ball rate | {bw['t4']['bnd_pct']:.2f}% boundary-concession rate"
    else:
        t4_str = "0 balls bowled (Zero observed exposure in Tier 4 crunch conditions)"
        
    t1_ov = format_overs(bw['normal']['balls'])
    press_ov = format_overs(bw['pressure']['balls'])
    high_ov = format_overs(bw['high']['balls'])
    
    print(f"#### {bw['rank']}. {bw['name']} (Local ID: `{pid}`)")
    print(f"- **Discipline Eligibility (Dataset):** {dual}")
    print(f"- **Normal Conditions (T1):** {bw['normal']['balls']} balls ({t1_ov}) | {bw['normal']['runs']} runs | {bw['normal']['econ']:.2f} RPO economy | {bw['normal']['wkts']} wickets | {bw['normal']['sr']:.1f} balls/wkt | {bw['normal']['dot_pct']:.2f}% dot-ball rate | {bw['normal']['bnd_pct']:.2f}% boundary-concession rate")
    print(f"- **Combined Pressure (T2–T4):** {bw['pressure']['balls']} balls ({press_ov}) | {bw['pressure']['runs']} runs | {bw['pressure']['econ']:.2f} RPO economy | {bw['pressure']['wkts']} wickets | {bw['pressure']['sr']:.1f} balls/wkt | {bw['pressure']['dot_pct']:.2f}% dot-ball rate | {bw['pressure']['bnd_pct']:.2f}% boundary-concession rate")
    print(f"- **High Pressure (T3–T4):** {bw['high']['balls']} balls ({high_ov}) | {bw['high']['runs']} runs | {bw['high']['econ']:.2f} RPO economy | {bw['high']['wkts']} wickets | {bw['high']['sr']:.1f} balls/wkt | {bw['high']['dot_pct']:.2f}% dot-ball rate | {bw['high']['bnd_pct']:.2f}% boundary-concession rate")
    print(f"- **Extreme Pressure (T4):** {t4_str}")
    print(f"- **Contextual Model Estimate & Uncertainty:** Shrunk contextual economy delta $\\Delta_{{EB}} = {bw['delta_rpo']:+.3f}\\text{{ RPO}}$, latent standard error $se_{{latent}} = {bw['se_latent']:.4f}\\text{{ RPO}}$, conservative upper bound $\\text{{UB}}_{{90\\% \\text{{ CI}}}} = {bw['ub90']:+.3f}\\text{{ RPO}}$ (95% one-sided upper bound, $Z = 1.645$). Raw pressure deltas: $\\Delta\\text{{Econ}} = {bw['delta_econ']:+.2f}\\text{{ RPO}}$, $\\Delta\\text{{Dot}} = {bw['delta_dot']:+.2f}\\%$, $\\Delta\\text{{Bnd}} = {bw['delta_bnd']:+.2f}\\%$.\n")
