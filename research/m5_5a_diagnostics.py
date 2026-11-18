import pandas as pd
import numpy as np

def run_diagnostics():
    print("=" * 80)
    print("RR ScoutIQ — M5.5-A Implementation Readiness Diagnostic Script")
    print("=" * 80)

    df = pd.read_csv("data/processed/m5_3/match_state_full.csv", low_memory=False)
    N_total = len(df)
    n_matches = df["match_id"].nunique()
    print(f"Total deliveries: {N_total:,}")
    print(f"Unique matches: {n_matches:,}")

    # Exclusions
    n_super = (df["is_super_over"] == True).sum()
    n_shortened = (df["is_shortened_match"] == True).sum()
    n_dls = (df["is_dls_match"] == True).sum()
    n_dli_valid = (df["is_dli_valid"] == True).sum()
    n_dli_invalid = (df["is_dli_valid"] == False).sum()
    print(f"Super Over balls: {n_super:,}")
    print(f"Shortened match balls: {n_shortened:,}")
    print(f"DLS match balls: {n_dls:,}")
    print(f"DLI Valid balls: {n_dli_valid:,}")
    print(f"DLI Invalid balls: {n_dli_invalid:,}")

    # Pressure delivery definitions
    df["is_pressure_dli"] = (df["is_dli_valid"] == True) & (df["pre_dli"] >= 1.35)
    print(f"Pressure balls (pre_dli >= 1.35): {df['is_pressure_dli'].sum():,}")

    # 1. Empirical Run Baselines by Phase and Pressure Tier
    print("\n--- 1. Empirical Run Expectations by Phase & Pressure Tier ---")
    valid_balls = df[(df["is_dli_valid"] == True) & (df["is_super_over"] == False)].copy()
    
    bat_faced = valid_balls[valid_balls["ext_batter_balls_faced"] == 1]
    cell_bat = bat_faced.groupby(["pre_match_phase", "pre_pressure_tier"]).agg(
        n_balls=("ext_batter_runs", "count"),
        mean_runs=("ext_batter_runs", "mean"),
        std_runs=("ext_batter_runs", "std"),
        boundary_pct=("ext_is_four", lambda s: ((s == 1) | (bat_faced.loc[s.index, "ext_is_six"] == 1)).mean() * 100),
        dot_pct=("ext_batter_runs", lambda s: (s == 0).mean() * 100),
        wkt_pct=("ext_is_wicket", lambda s: (s == 1).mean() * 100)
    ).round(4)
    print("\nBatter Runs Expectation (Cell Breakdown):")
    print(cell_bat)

    bowl_legal = valid_balls[valid_balls["ext_is_legal_delivery"] == True]
    cell_bowl = bowl_legal.groupby(["pre_match_phase", "pre_pressure_tier"]).agg(
        n_balls=("ext_bowler_debit_runs", "count"),
        mean_conceded=("ext_bowler_debit_runs", "mean"),
        std_conceded=("ext_bowler_debit_runs", "std"),
        wkt_pct=("ext_is_bowler_wicket", lambda s: (s == True).mean() * 100),
        dot_pct=("ext_bowler_debit_runs", lambda s: (s == 0).mean() * 100),
        bnd_conceded_pct=("ext_is_four", lambda s: ((s == 1) | (bowl_legal.loc[s.index, "ext_is_six"] == 1)).mean() * 100)
    ).round(4)
    print("\nBowler Concession Expectation (Cell Breakdown):")
    print(cell_bowl)

    # 2. Batter Role Classification
    print("\n--- 2. Batter Role Classification Audit ---")
    bat_inns = df[(df["is_super_over"] == False) & (df["ext_batter_balls_faced"] == 1)].groupby(
        ["striker_id", "match_id", "innings"]
    ).agg(
        first_over=("overid", "min"),
        balls_faced=("ext_batter_balls_faced", "sum"),
        pressure_balls=("is_pressure_dli", "sum")
    ).reset_index()

    def get_bat_role(entry_over):
        if entry_over <= 6:
            return "Top Order"
        elif entry_over <= 13:
            return "Middle Order"
        else:
            return "Finisher"

    bat_inns["innings_role"] = bat_inns["first_over"].apply(get_bat_role)

    bat_summary = bat_inns.groupby("striker_id").agg(
        total_inns=("match_id", "count"),
        total_balls=("balls_faced", "sum"),
        pressure_balls=("pressure_balls", "sum"),
        n_top=("innings_role", lambda s: (s == "Top Order").sum()),
        n_mid=("innings_role", lambda s: (s == "Middle Order").sum()),
        n_fin=("innings_role", lambda s: (s == "Finisher").sum())
    ).reset_index()

    def get_primary_bat_role(row):
        counts = {"Top Order": row["n_top"], "Middle Order": row["n_mid"], "Finisher": row["n_fin"]}
        max_c = max(counts.values())
        top_roles = [r for r, c in counts.items() if c == max_c]
        if len(top_roles) == 1:
            return top_roles[0], False
        else:
            # Tie breaking in M4: Top Order -> Middle Order -> Finisher
            return top_roles[0], True

    roles_and_ties = bat_summary.apply(get_primary_bat_role, axis=1)
    bat_summary["primary_role"] = [r[0] for r in roles_and_ties]
    bat_summary["has_tie"] = [r[1] for r in roles_and_ties]

    bat_summary["is_eligible"] = (
        (bat_summary["total_inns"] >= 12) &
        (bat_summary["total_balls"] >= 120) &
        (bat_summary["pressure_balls"] >= 36)
    )

    print(f"\nTotal unique batters: {len(bat_summary):,}")
    print(f"Total eligible batters: {bat_summary['is_eligible'].sum():,}")
    print(f"Batters with tie in role assignment: {bat_summary['has_tie'].sum():,}")
    print("\nEligible Batter Primary Roles:")
    print(bat_summary[bat_summary["is_eligible"]]["primary_role"].value_counts())

    # 3. Bowler Role Classification
    print("\n--- 3. Bowler Role Classification Audit ---")
    bowl_balls = df[(df["is_super_over"] == False) & (df["ext_is_legal_delivery"] == True)]
    bowl_phases = bowl_balls.groupby(["bowler_id", "pre_match_phase"]).size().unstack(fill_value=0)
    for col in ["Powerplay", "Middle", "Death"]:
        if col not in bowl_phases.columns:
            bowl_phases[col] = 0

    bowl_phases["phase_legal_balls"] = bowl_phases["Powerplay"] + bowl_phases["Middle"] + bowl_phases["Death"]
    bowl_phases["pct_pp"] = bowl_phases["Powerplay"] / bowl_phases["phase_legal_balls"]
    bowl_phases["pct_death"] = bowl_phases["Death"] / bowl_phases["phase_legal_balls"]
    bowl_phases["pct_middle"] = bowl_phases["Middle"] / bowl_phases["phase_legal_balls"]

    bowl_inns = bowl_balls.groupby(["bowler_id", "match_id", "innings"]).agg(
        legal_balls=("ext_is_legal_delivery", "count"),
        pressure_legal_balls=("is_pressure_dli", "sum")
    ).reset_index()

    bowl_summary = bowl_inns.groupby("bowler_id").agg(
        total_inns=("match_id", "count"),
        total_legal_balls=("legal_balls", "sum"),
        pressure_legal_balls=("pressure_legal_balls", "sum")
    ).join(bowl_phases)

    def classify_bowler(row):
        is_pp = row["pct_pp"] >= 0.40
        is_death = row["pct_death"] >= 0.30
        if is_pp and is_death:
            return "Dual PP/Death", True
        elif is_pp:
            return "Powerplay Specialist", False
        elif is_death:
            return "Death Specialist", False
        else:
            return "Middle Enforcer", False

    b_roles_ties = bowl_summary.apply(classify_bowler, axis=1)
    bowl_summary["raw_role"] = [r[0] for r in b_roles_ties]
    bowl_summary["is_dual"] = [r[1] for r in b_roles_ties]

    # In M4 pilot implementation:
    # if pct_pp >= 0.40: Powerplay Specialist
    # elif pct_death >= 0.30: Death Specialist
    # else: Middle Enforcer
    # That means PP took priority over Death!
    def m4_bowler_role(row):
        if row["pct_pp"] >= 0.40:
            return "Powerplay Specialist"
        elif row["pct_death"] >= 0.30:
            return "Death Specialist"
        else:
            return "Middle Enforcer"

    bowl_summary["m4_role"] = bowl_summary.apply(m4_bowler_role, axis=1)

    bowl_summary["is_eligible"] = (
        (bowl_summary["total_inns"] >= 12) &
        (bowl_summary["total_legal_balls"] >= 144) &
        (bowl_summary["pressure_legal_balls"] >= 42)
    )
    print(f"\nTotal unique bowlers: {len(bowl_summary):,}")
    print(f"Bowlers meeting BOTH PP (>=40%) and Death (>=30%): {bowl_summary['is_dual'].sum():,}")
    print(f"Total eligible bowlers: {bowl_summary['is_eligible'].sum():,}")
    print(f"Eligible bowlers with dual qualification: {(bowl_summary['is_eligible'] & bowl_summary['is_dual']).sum():,}")
    print("\nEligible Bowler Role Breakdown (M4 priority rule: PP > Death > Middle):")
    print(bowl_summary[bowl_summary["is_eligible"]]["m4_role"].value_counts())
    print("\nEligible Bowler Role Breakdown (with dual shown separately):")
    print(bowl_summary[bowl_summary["is_eligible"]]["raw_role"].value_counts())

    # 4. Correlation and Collinearity Analysis
    print("\n--- 4. Component Correlation & Multicollinearity Audit ---")
    # For eligible batters: compute components
    # We use empirical expectations computed from the data for each (Phase, Tier) cell
    exp_runs_map = cell_bat["mean_runs"].to_dict()
    valid_balls["exp_bat_runs"] = valid_balls.set_index(["pre_match_phase", "pre_pressure_tier"]).index.map(exp_runs_map)

    # Batter stats per eligible player
    elig_bat_ids = set(bat_summary[bat_summary["is_eligible"]]["striker_id"])
    bat_data = []
    for sid in elig_bat_ids:
        p_balls = valid_balls[(valid_balls["striker_id"] == sid) & (valid_balls["ext_batter_balls_faced"] == 1)]
        p_press = p_balls[p_balls["pre_dli"] >= 1.35]
        p_norm = p_balls[p_balls["pre_dli"] < 1.35]
        if len(p_press) >= 36 and len(p_norm) > 0:
            xra_per_ball = (p_press["ext_batter_runs"] - p_press["exp_bat_runs"]).mean()
            sr_press = (p_press["ext_batter_runs"].sum() / len(p_press)) * 100
            sr_norm = (p_norm["ext_batter_runs"].sum() / len(p_norm)) * 100
            d_sr = sr_press - sr_norm
            
            bnd_press = ((p_press["ext_is_four"] == 1) | (p_press["ext_is_six"] == 1)).mean() * 100
            bnd_norm = ((p_norm["ext_is_four"] == 1) | (p_norm["ext_is_six"] == 1)).mean() * 100
            d_bnd = bnd_press - bnd_norm
            
            dot_press = (p_press["ext_batter_runs"] == 0).mean() * 100
            dot_norm = (p_norm["ext_batter_runs"] == 0).mean() * 100
            d_dot = dot_norm - dot_press # positive is good (dot suppression)
            
            wkt_press = (p_press["ext_is_wicket"] == 1).mean() * 100
            wkt_norm = (p_norm["ext_is_wicket"] == 1).mean() * 100
            d_wkt = wkt_norm - wkt_press # positive is good (dismissal hazard suppression)
            
            bat_data.append({
                "striker_id": sid,
                "xra_per_ball": xra_per_ball,
                "d_sr": d_sr,
                "d_bnd": d_bnd,
                "d_dot": d_dot,
                "d_wkt": d_wkt
            })

    bat_comp_df = pd.DataFrame(bat_data)
    print(f"\nEligible batters evaluated for component correlation (N = {len(bat_comp_df)}):")
    corr_bat = bat_comp_df[["xra_per_ball", "d_sr", "d_bnd", "d_dot", "d_wkt"]].corr().round(4)
    print(corr_bat)

    # For eligible bowlers: compute components
    exp_bowl_map = cell_bowl["mean_conceded"].to_dict()
    valid_balls["exp_bowl_runs"] = valid_balls.set_index(["pre_match_phase", "pre_pressure_tier"]).index.map(exp_bowl_map)

    elig_bowl_ids = set(bowl_summary[bowl_summary["is_eligible"]].index)
    bowl_data = []
    for bid in elig_bowl_ids:
        p_balls = valid_balls[(valid_balls["bowler_id"] == bid) & (valid_balls["ext_is_legal_delivery"] == True)]
        p_press = p_balls[p_balls["pre_dli"] >= 1.35]
        p_norm = p_balls[p_balls["pre_dli"] < 1.35]
        if len(p_press) >= 42 and len(p_norm) > 0:
            xrs_per_ball = (p_press["exp_bowl_runs"] - p_press["ext_bowler_debit_runs"]).mean()
            econ_press = (p_press["ext_bowler_debit_runs"].sum() / (len(p_press) / 6.0))
            econ_norm = (p_norm["ext_bowler_debit_runs"].sum() / (len(p_norm) / 6.0))
            d_econ = econ_norm - econ_press # positive is good (lower economy under fire)
            
            wkt_press = (p_press["ext_is_bowler_wicket"] == True).mean() * 100
            wkt_norm = (p_norm["ext_is_bowler_wicket"] == True).mean() * 100
            d_wkt = wkt_press - wkt_norm # positive is good
            
            dot_press = (p_press["ext_bowler_debit_runs"] == 0).mean() * 100
            dot_norm = (p_norm["ext_bowler_debit_runs"] == 0).mean() * 100
            d_dot = dot_press - dot_norm # positive is good
            
            bnd_press = ((p_press["ext_is_four"] == 1) | (p_press["ext_is_six"] == 1)).mean() * 100
            bnd_norm = ((p_norm["ext_is_four"] == 1) | (p_norm["ext_is_six"] == 1)).mean() * 100
            d_bnd = bnd_norm - bnd_press # positive is good (concession suppression)
            
            bowl_data.append({
                "bowler_id": bid,
                "xrs_per_ball": xrs_per_ball,
                "d_econ": d_econ,
                "d_wkt": d_wkt,
                "d_dot": d_dot,
                "d_bnd": d_bnd
            })

    bowl_comp_df = pd.DataFrame(bowl_data)
    print(f"\nEligible bowlers evaluated for component correlation (N = {len(bowl_comp_df)}):")
    corr_bowl = bowl_comp_df[["xrs_per_ball", "d_econ", "d_wkt", "d_dot", "d_bnd"]].corr().round(4)
    print(corr_bowl)

if __name__ == "__main__":
    run_diagnostics()
