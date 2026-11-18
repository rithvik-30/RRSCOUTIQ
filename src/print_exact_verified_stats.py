from src.generate_top20_reports import generate_reports

b_data, bw_data = generate_reports()

print("=== BATTERS ===")
for b in b_data:
    print(f"#{b['rank']} {b['name']} (ID: {b['player_id']})")
    print(f"  T1: {b['normal']['balls']} balls, {b['normal']['runs']} runs, {b['normal']['sr']:.2f} SR, {b['normal']['bnd_pct']:.2f}% Bnd, {b['normal']['dot_pct']:.2f}% Dot, {b['normal']['outs']} outs, {b['normal']['hazard']:.2f}% hazard")
    print(f"  T2: {b['t2']['balls']} balls, {b['t2']['runs']} runs, {b['t2']['sr']:.2f} SR, {b['t2']['bnd_pct']:.2f}% Bnd, {b['t2']['dot_pct']:.2f}% Dot, {b['t2']['outs']} outs, {b['t2']['hazard']:.2f}% hazard")
    print(f"  T3: {b['t3']['balls']} balls, {b['t3']['runs']} runs, {b['t3']['sr']:.2f} SR, {b['t3']['bnd_pct']:.2f}% Bnd, {b['t3']['dot_pct']:.2f}% Dot, {b['t3']['outs']} outs, {b['t3']['hazard']:.2f}% hazard")
    print(f"  T4: {b['t4']['balls']} balls, {b['t4']['runs']} runs, {b['t4']['sr']:.2f} SR, {b['t4']['bnd_pct']:.2f}% Bnd, {b['t4']['dot_pct']:.2f}% Dot, {b['t4']['outs']} outs, {b['t4']['hazard']:.2f}% hazard")
    print(f"  Combined (T2-4): {b['pressure']['balls']} balls, {b['pressure']['runs']} runs, {b['pressure']['sr']:.2f} SR, {b['pressure']['bnd_pct']:.2f}% Bnd, {b['pressure']['dot_pct']:.2f}% Dot, {b['pressure']['outs']} outs, {b['pressure']['hazard']:.2f}% hazard")
    print(f"  High (T3-4): {b['high']['balls']} balls, {b['high']['runs']} runs, {b['high']['sr']:.2f} SR, {b['high']['bnd_pct']:.2f}% Bnd, {b['high']['dot_pct']:.2f}% Dot, {b['high']['outs']} outs, {b['high']['hazard']:.2f}% hazard")
    print(f"  Deltas: SR {b['delta_sr']:+.2f}, Bnd {b['delta_bnd']:+.2f}%, Dot {b['delta_dot']:+.2f}%")
    print(f"  Model: ValAdd {b['val_add']*100:+.2f}%, se {b['se_latent']:.4f}, LB90_CI {b['lb90']*100:+.2f}%")

print("\n=== BOWLERS ===")
for bw in bw_data:
    print(f"#{bw['rank']} {bw['name']} (ID: {bw['player_id']})")
    print(f"  T1: {bw['normal']['balls']} balls, {bw['normal']['runs']} runs, {bw['normal']['econ']:.2f} RPO, {bw['normal']['bnd_pct']:.2f}% Bnd, {bw['normal']['dot_pct']:.2f}% Dot, {bw['normal']['wkts']} wkts, {bw['normal']['sr']:.1f} SR")
    print(f"  T2: {bw['t2']['balls']} balls, {bw['t2']['runs']} runs, {bw['t2']['econ']:.2f} RPO, {bw['t2']['bnd_pct']:.2f}% Bnd, {bw['t2']['dot_pct']:.2f}% Dot, {bw['t2']['wkts']} wkts, {bw['t2']['sr']:.1f} SR")
    print(f"  T3: {bw['t3']['balls']} balls, {bw['t3']['runs']} runs, {bw['t3']['econ']:.2f} RPO, {bw['t3']['bnd_pct']:.2f}% Bnd, {bw['t3']['dot_pct']:.2f}% Dot, {bw['t3']['wkts']} wkts, {bw['t3']['sr']:.1f} SR")
    print(f"  T4: {bw['t4']['balls']} balls, {bw['t4']['runs']} runs, {bw['t4']['econ']:.2f} RPO, {bw['t4']['bnd_pct']:.2f}% Bnd, {bw['t4']['dot_pct']:.2f}% Dot, {bw['t4']['wkts']} wkts, {bw['t4']['sr']:.1f} SR")
    print(f"  Combined (T2-4): {bw['pressure']['balls']} balls, {bw['pressure']['runs']} runs, {bw['pressure']['econ']:.2f} RPO, {bw['pressure']['bnd_pct']:.2f}% Bnd, {bw['pressure']['dot_pct']:.2f}% Dot, {bw['pressure']['wkts']} wkts, {bw['pressure']['sr']:.1f} SR")
    print(f"  High (T3-4): {bw['high']['balls']} balls, {bw['high']['runs']} runs, {bw['high']['econ']:.2f} RPO, {bw['high']['bnd_pct']:.2f}% Bnd, {bw['high']['dot_pct']:.2f}% Dot, {bw['high']['wkts']} wkts, {bw['high']['sr']:.1f} SR")
    print(f"  Deltas: Econ {bw['delta_econ']:+.2f} RPO, Bnd {bw['delta_bnd']:+.2f}%, Dot {bw['delta_dot']:+.2f}%")
    print(f"  Model: Delta_EB {bw['delta_rpo']:+.3f} RPO, se {bw['se_latent']:.4f}, UB90_CI {bw['ub90']:+.3f} RPO")
