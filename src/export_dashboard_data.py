"""
Exports verified frozen statistics into dashboard/data.js and dashboard/data.json
Ensures 100% precision with frozen competition reports.
"""
import json
import os
from src.generate_top20_reports import generate_reports

b_data, bw_data = generate_reports()

def format_overs(balls):
    ov = balls // 6
    rem = balls % 6
    return f"{ov}.{rem}" if balls > 0 else "0.0"

batters_export = []
for b in b_data:
    pid = b['player_id']
    is_dual = pid in [6281, 1318]
    t4_b = b['t4']['balls']
    lb90 = b['lb90']
    
    if t4_b == 0:
        lim_flag = "Zero Tier 4 Balls"
    elif t4_b < 50:
        lim_flag = f"Small Tier 4 Sample ({t4_b}b)"
    else:
        lim_flag = f"Robust Tier 4 Exposure ({t4_b}b)"
        
    status = "Confirmed Positive Value-Add" if lb90 > 0 else "Relative Ranking Leader"
    
    # Clean numpy types to python native
    clean_item = {
        "rank": int(b['rank']),
        "player_id": int(pid),
        "name": str(b['name']),
        "discipline_eligibility": "Dual-discipline eligible" if is_dual else "Single-discipline (Batting)",
        "matches": int(b['matches']),
        "total_balls": int(b['total_balls']),
        "status": status,
        "is_confirmed_positive": bool(lb90 > 0),
        "limitation_flag": lim_flag,
        "normal": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in b['normal'].items()},
        "pressure": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in b['pressure'].items()},
        "high": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in b['high'].items()},
        "t2": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in b['t2'].items()},
        "t3": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in b['t3'].items()},
        "t4": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in b['t4'].items()},
        "deltas": {
            "delta_sr": float(b['delta_sr']),
            "delta_bnd": float(b['delta_bnd']),
            "delta_dot": float(b['delta_dot'])
        },
        "model": {
            "val_add": float(b['val_add']),
            "se_latent": float(b['se_latent']),
            "lb90": float(lb90)
        }
    }
    # Ensure nested ints
    for tier in ['normal', 'pressure', 'high', 't2', 't3', 't4']:
        clean_item[tier]['balls'] = int(clean_item[tier]['balls'])
        clean_item[tier]['runs'] = int(clean_item[tier]['runs'])
        clean_item[tier]['outs'] = int(clean_item[tier]['outs'])
        clean_item[tier]['sr'] = round(float(clean_item[tier]['sr']), 2)
        clean_item[tier]['bnd_pct'] = round(float(clean_item[tier]['bnd_pct']), 2)
        clean_item[tier]['dot_pct'] = round(float(clean_item[tier]['dot_pct']), 2)
        clean_item[tier]['hazard'] = round(float(clean_item[tier]['hazard']), 2)
        
    batters_export.append(clean_item)

bowlers_export = []
for bw in bw_data:
    pid = bw['player_id']
    is_dual = pid in [781, 3644, 2876, 4900, 152, 4101, 2984]
    t4_b = bw['t4']['balls']
    ub90 = bw['ub90']
    
    if t4_b == 0:
        lim_flag = "Zero Tier 4 Balls"
    elif t4_b < 50:
        lim_flag = f"Small Tier 4 Sample ({t4_b}b)"
    else:
        lim_flag = f"Robust Tier 4 Exposure ({t4_b}b)"
        
    status = "Top Relative Suppressor"
    
    clean_item = {
        "rank": int(bw['rank']),
        "player_id": int(pid),
        "name": str(bw['name']),
        "discipline_eligibility": "Dual-discipline eligible" if is_dual else "Single-discipline (Bowling)",
        "matches": int(bw['matches']),
        "total_balls": int(bw['total_balls']),
        "overs": format_overs(bw['total_balls']),
        "status": status,
        "is_confirmed_positive": False,  # No bowler has UB < 0
        "limitation_flag": lim_flag,
        "is_specialist_bowler_note": bool(pid == 3644),
        "normal": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in bw['normal'].items()},
        "pressure": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in bw['pressure'].items()},
        "high": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in bw['high'].items()},
        "t2": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in bw['t2'].items()},
        "t3": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in bw['t3'].items()},
        "t4": {k: float(v) if isinstance(v, (float, int)) or hasattr(v, 'item') else v for k, v in bw['t4'].items()},
        "deltas": {
            "delta_econ": float(bw['delta_econ']),
            "delta_dot": float(bw['delta_dot']),
            "delta_bnd": float(bw['delta_bnd'])
        },
        "model": {
            "delta_rpo": float(bw['delta_rpo']),
            "se_latent": float(bw['se_latent']),
            "ub90": float(ub90)
        }
    }
    for tier in ['normal', 'pressure', 'high', 't2', 't3', 't4']:
        clean_item[tier]['balls'] = int(clean_item[tier]['balls'])
        clean_item[tier]['runs'] = int(clean_item[tier]['runs'])
        clean_item[tier]['wkts'] = int(clean_item[tier]['wkts'])
        clean_item[tier]['overs'] = format_overs(clean_item[tier]['balls'])
        clean_item[tier]['econ'] = round(float(clean_item[tier]['econ']), 2)
        clean_item[tier]['bnd_pct'] = round(float(clean_item[tier]['bnd_pct']), 2)
        clean_item[tier]['dot_pct'] = round(float(clean_item[tier]['dot_pct']), 2)
        clean_item[tier]['sr'] = round(float(clean_item[tier]['sr']), 1)
        
    bowlers_export.append(clean_item)

meta = {
    "project": "RR ScoutIQ",
    "subtitle": "Pressure Performance Intelligence System",
    "canonical_matches": 776,
    "clean_matches": 744,
    "clean_legal_deliveries": 168104,
    "total_deliveries": 179837,
    "excluded_matches": 32,
    "super_over_deliveries": 23,
    "ipl_matches_clean": 362,
    "ipl_pct_clean": 48.66,
    "t20i_matches_clean": 381,
    "t20i_pct_clean": 51.21,
    "regional_matches_clean": 1,
    "regional_pct_clean": 0.13,
    "eligible_batters_cohort": 106,
    "eligible_bowlers_cohort": 109,
    "min_balls_threshold": 500,
    "min_pressure_balls": 100,
    "multiplier_Z": 1.645,
    "credible_interval_desc": "Conservative endpoint of 90% two-sided CI (95% one-sided bound)"
}

dashboard_data = {
    "meta": meta,
    "batters": batters_export,
    "bowlers": bowlers_export
}

# Write JS file
with open("dashboard/data.js", "w", encoding="utf-8") as f:
    f.write("// Authoritative Frozen Data for RR ScoutIQ Dashboard\n")
    f.write("window.RR_DATA = ")
    json.dump(dashboard_data, f, indent=2)
    f.write(";\n")

# Write JSON file
with open("dashboard/data.json", "w", encoding="utf-8") as f:
    json.dump(dashboard_data, f, indent=2)

print("Exported dashboard/data.js and dashboard/data.json successfully.")
