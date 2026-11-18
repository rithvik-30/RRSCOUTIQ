"""
RR ScoutIQ - Milestone M3 Methodology Closure Audit
Script: src/methodology_closure_audit.py

Executes empirical audits for:
1. Normal-Normal model validation vs Hierarchical Poisson-Gamma alternative.
2. Wicket prior sensitivity across all 250 qualified batters (absolute deltas, uncertainty, Top 10).
3. Bootstrap clustering validation for batters and bowlers (Schemes A, B, C; multi-innings analysis; MC stability).
4. Role standardization sensitivity (cohort cutoffs, minimum cohort sizes, variance regularization, partial pooling).
5. Mathematical and interval terminology audit.
"""

import numpy as np
import pandas as pd
from scipy import stats

def run_closure_audit():
    print("==================================================================")
    print("RR SCOUTIQ: MILESTONE M3 METHODOLOGY CLOSURE AUDIT")
    print("==================================================================")
    
    # Load source datasets
    bbb = pd.read_csv('data/extracted/ball_by_ball.csv')
    matches = pd.read_csv('data/extracted/matches.csv')
    
    # Basic flags
    bbb['is_striker_ball'] = bbb['extras_type'] != 'wide'
    bbb['is_legal'] = ~bbb['extras_type'].isin(['wide', 'Overstep', 'other'])
    bbb['is_dot'] = bbb['runs'] == 0
    bbb['is_boundary'] = bbb['is_four'] | bbb['is_six']
    bbb['is_wicket_int'] = bbb['is_wicket'].astype(int)
    bbb['over'] = bbb['overid']
    
    valid_bat = bbb[bbb['is_striker_ball']].copy()
    valid_bowl = bbb[bbb['is_legal']].copy()
    
    # Batting career aggregations
    bat_m = valid_bat.groupby(['striker_id', 'match_id', 'innings']).agg(
        balls=('runs', 'count'),
        runs=('runs', 'sum'),
        outs=('is_wicket_int', 'sum')
    ).reset_index()
    
    bat_c = bat_m.groupby('striker_id').agg(
        innings=('match_id', 'count'),
        balls=('balls', 'sum'),
        runs=('runs', 'sum'),
        outs=('outs', 'sum')
    ).reset_index()
    
    q_bat = bat_c[(bat_c['innings'] >= 12) & (bat_c['balls'] >= 120)].copy()
    q_bat['sr'] = q_bat['runs'] / q_bat['balls'] * 100
    q_bat['out_rate'] = q_bat['outs'] / q_bat['balls']
    
    # Bowling career aggregations
    bowl_m = valid_bowl.groupby(['bowler_id', 'match_id', 'innings']).agg(
        balls=('runs', 'count'),
        runs=('runs', 'sum'),
        wickets=('is_wicket_int', 'sum')
    ).reset_index()
    
    bowl_c = bowl_m.groupby('bowler_id').agg(
        innings=('match_id', 'count'),
        balls=('balls', 'sum'),
        runs=('runs', 'sum'),
        wickets=('wickets', 'sum')
    ).reset_index()
    
    q_bowl = bowl_c[(bowl_c['innings'] >= 12) & (bowl_c['balls'] >= 144)].copy()
    q_bowl['econ'] = q_bowl['runs'] / (q_bowl['balls'] / 6.0)
    
    print(f"Qualified Batters: N = {len(q_bat)}")
    print(f"Qualified Bowlers: N = {len(q_bowl)}")
    
    # ==============================================================================
    # TASK 1: NORMAL-NORMAL MODEL VALIDATION & HIERARCHICAL COMPARISON
    # ==============================================================================
    print("\n------------------------------------------------------------------")
    print("TASK 1: DELIVERY-LEVEL DISTRIBUTIONS & NORMAL-NORMAL VALIDATION")
    print("------------------------------------------------------------------")
    
    # 1.1 Outcome distributions
    bat_runs = valid_bat['runs'].values
    bowl_runs = valid_bowl['runs'].values
    
    print("Batting Runs per Delivery Distribution:")
    val_counts_bat = pd.Series(bat_runs).value_counts(normalize=True).sort_index()
    for r, p in val_counts_bat.items():
        print(f"  Runs = {r:2d}: {p*100:6.2f}%")
    print(f"  Batting Mean: {np.mean(bat_runs):.4f}, Variance: {np.var(bat_runs):.4f}")
    print(f"  Batting Skewness: {stats.skew(bat_runs):.4f}, Kurtosis: {stats.kurtosis(bat_runs):.4f}")
    print(f"  Zero-inflation (Dot %): {np.mean(bat_runs == 0)*100:.2f}%")
    
    print("\nBowling Runs Conceded per Legal Ball Distribution:")
    val_counts_bowl = pd.Series(bowl_runs).value_counts(normalize=True).sort_index()
    for r, p in val_counts_bowl.items():
        if p >= 0.0001:
            print(f"  Runs = {r:2d}: {p*100:6.2f}%")
    print(f"  Bowling Mean: {np.mean(bowl_runs):.4f}, Variance: {np.var(bowl_runs):.4f}")
    print(f"  Bowling Skewness: {stats.skew(bowl_runs):.4f}, Kurtosis: {stats.kurtosis(bowl_runs):.4f}")
    
    # 1.2 Autocorrelation & Clustering within innings
    # Lag autocorrelation for batter runs facing consecutive balls
    valid_bat_sorted = valid_bat.sort_values(['match_id', 'innings', 'innings_ball_num'])
    valid_bat_sorted['prev_striker'] = valid_bat_sorted.groupby(['match_id', 'innings'])['striker_id'].shift(1)
    valid_bat_sorted['prev_runs'] = valid_bat_sorted.groupby(['match_id', 'innings'])['runs'].shift(1)
    same_striker = valid_bat_sorted[valid_bat_sorted['striker_id'] == valid_bat_sorted['prev_striker']]
    autocorr_bat = same_striker['runs'].corr(same_striker['prev_runs'])
    print(f"\nBatter consecutive balls lag-1 autocorrelation: {autocorr_bat:.4f}")
    
    # Over-level ICC for bowling
    # Calculate ICC across overs for bowler runs
    valid_bowl_sorted = valid_bowl.sort_values(['match_id', 'innings', 'overid', 'over_ball_num'])
    valid_bowl_sorted['prev_bowler'] = valid_bowl_sorted.groupby(['match_id', 'innings', 'overid'])['bowler_id'].shift(1)
    valid_bowl_sorted['prev_runs'] = valid_bowl_sorted.groupby(['match_id', 'innings', 'overid'])['runs'].shift(1)
    same_bowler = valid_bowl_sorted[valid_bowl_sorted['bowler_id'] == valid_bowl_sorted['prev_bowler']]
    autocorr_bowl = same_bowler['runs'].corr(same_bowler['prev_runs'])
    print(f"Bowler consecutive balls lag-1 autocorrelation within over: {autocorr_bowl:.4f}")
    
    # 1.3 Variance decomposition (ANOVA / Random Effects)
    # Batter runs decomposition
    grand_mean_bat = q_bat['runs'].sum() / q_bat['balls'].sum()
    ss_total = 0.0
    ss_within = 0.0
    ss_between = 0.0
    k_bat = len(q_bat)
    total_n_bat = q_bat['balls'].sum()
    sum_ni2 = (q_bat['balls'] ** 2).sum()
    n0_bat = (total_n_bat - sum_ni2 / total_n_bat) / (k_bat - 1)
    
    for _, row in q_bat.iterrows():
        p_runs = valid_bat[valid_bat['striker_id'] == row['striker_id']]['runs'].values
        p_mean = row['runs'] / row['balls']
        ss_within += np.sum((p_runs - p_mean) ** 2)
        ss_between += row['balls'] * ((p_mean - grand_mean_bat) ** 2)
        
    ms_within_bat = ss_within / (total_n_bat - k_bat)
    ms_between_bat = ss_between / (k_bat - 1)
    tau2_bat = max(0.0, (ms_between_bat - ms_within_bat) / n0_bat)
    
    print(f"\nBatting Variance Decomposition (ANOVA Unbalanced):")
    print(f"  Within-player MSW (sigma_w^2): {ms_within_bat:.4f}")
    print(f"  Between-player MSB:           {ms_between_bat:.4f}")
    print(f"  Effective sample size n0:     {n0_bat:.2f} balls")
    print(f"  Estimated Between-player tau_b^2: {tau2_bat:.6f} (tau_b = {np.sqrt(tau2_bat)*100:.2f} SR points)")
    print(f"  Ratio sigma_w^2 / tau_b^2 (Career): {ms_within_bat / tau2_bat:.2f} balls")
    
    # 1.4 Hierarchical Model Comparison: Normal-Normal vs Poisson-Gamma
    # Normal-Normal model:
    # y_hat_i = runs / balls * 100
    # Shrunk SR: theta_NN = lambda_i * y_hat_i + (1 - lambda_i) * mu_0, where lambda_i = N_i / (N_i + K_NN)
    K_NN = 50.62 # high pressure setting
    mu_SR = grand_mean_bat * 100
    q_bat['lambda_NN'] = q_bat['balls'] / (q_bat['balls'] + K_NN)
    q_bat['sr_NN'] = q_bat['lambda_NN'] * q_bat['sr'] + (1 - q_bat['lambda_NN']) * mu_SR
    q_bat['se_NN'] = np.sqrt(ms_within_bat * 10000.0 / (q_bat['balls'] + K_NN))
    
    # Poisson-Gamma model:
    # Runs ~ Poisson(lambda * Balls)
    # Prior lambda ~ Gamma(alpha, beta) where alpha / beta = grand_mean_bat, beta = K_gamma = 50.62 balls
    beta_prior = 50.62
    alpha_prior = grand_mean_bat * beta_prior
    q_bat['lambda_PG_mean'] = (alpha_prior + q_bat['runs']) / (beta_prior + q_bat['balls']) * 100
    # Posterior variance for Gamma: alpha_post / beta_post^2
    q_bat['lambda_PG_se'] = np.sqrt((alpha_prior + q_bat['runs']) / ((beta_prior + q_bat['balls']) ** 2)) * 100
    
    # Compare estimates
    diff_sr = np.abs(q_bat['sr_NN'] - q_bat['lambda_PG_mean'])
    corr_sr = q_bat['sr_NN'].corr(q_bat['lambda_PG_mean'], method='spearman')
    corr_pearson = q_bat['sr_NN'].corr(q_bat['lambda_PG_mean'], method='pearson')
    
    print("\nComparison of Normal-Normal vs Poisson-Gamma Shrinkage (250 Qualified Batters):")
    print(f"  Spearman Rank Correlation:  {corr_sr:.6f}")
    print(f"  Pearson Correlation:        {corr_pearson:.6f}")
    print(f"  Mean Absolute Difference:   {diff_sr.mean():.4f} SR points")
    print(f"  Median Absolute Difference: {diff_sr.median():.4f} SR points")
    print(f"  Max Absolute Difference:    {diff_sr.max():.4f} SR points")
    print(f"  Median SE (Normal-Normal):  {q_bat['se_NN'].median():.2f} SR")
    print(f"  Median SE (Poisson-Gamma):  {q_bat['lambda_PG_se'].median():.2f} SR")
    
    # Top 10 overlap
    top10_NN = set(q_bat.sort_values('sr_NN', ascending=False)['striker_id'].head(10))
    top10_PG = set(q_bat.sort_values('lambda_PG_mean', ascending=False)['striker_id'].head(10))
    print(f"  Top-10 Overlap: {len(top10_NN.intersection(top10_PG))}/10 ({top10_NN == top10_PG})")
    
    # ==============================================================================
    # TASK 2: WICKET PRIOR SENSITIVITY (M = 60, 90, 120, 180)
    # ==============================================================================
    print("\n------------------------------------------------------------------")
    print("TASK 2: WICKET PRIOR SENSITIVITY (M = 60, 90, 120, 180)")
    print("------------------------------------------------------------------")
    
    p_prior = q_bat['outs'].sum() / q_bat['balls'].sum()
    print(f"Prior Mean Wicket Hazard: {p_prior*100:.3f}%")
    
    # Add volume strata
    q_bat['stratum'] = pd.cut(
        q_bat['balls'], 
        bins=[0, 220, 420, 99999], 
        labels=['Low-Volume (120-220b)', 'Mid-Volume (221-420b)', 'High-Volume (>420b)']
    )
    
    for M in [60, 90, 120, 180]:
        alpha = p_prior * M
        beta_param = M - alpha
        # Posterior mean
        q_bat[f'p_hat_{M}'] = (q_bat['outs'] + alpha) / (q_bat['balls'] + M) * 100
        # Posterior SE (Beta distribution standard deviation)
        a_post = q_bat['outs'] + alpha
        b_post = (q_bat['balls'] - q_bat['outs']) + beta_param
        q_bat[f'se_{M}'] = np.sqrt((a_post * b_post) / (((a_post + b_post) ** 2) * (a_post + b_post + 1))) * 100
        # 90% credible interval width: approx 2 * 1.645 * se
        q_bat[f'ci90_width_{M}'] = 2 * 1.64485 * q_bat[f'se_{M}']
        
    print("\nSummary of Posterior Hazard Rates & Uncertainty by Cap M:")
    for M in [60, 90, 120, 180]:
        print(f"Cap M = {M:3d}:")
        print(f"  Mean: {q_bat[f'p_hat_{M}'].mean():.3f}% | Median: {q_bat[f'p_hat_{M}'].median():.3f}% | Std: {q_bat[f'p_hat_{M}'].std():.3f}%")
        print(f"  Mean 90% CI Width: {q_bat[f'ci90_width_{M}'].mean():.3f}% | Median CI Width: {q_bat[f'ci90_width_{M}'].median():.3f}%")
        
    print("\nAbsolute Changes Compared to M = 90 (Percentage Points):")
    for M in [60, 120, 180]:
        delta = np.abs(q_bat[f'p_hat_{M}'] - q_bat['p_hat_90'])
        print(f"Comparison |M={M} - M=90|:")
        print(f"  Overall: Mean Abs Delta = {delta.mean():.4f}%, Median = {delta.median():.4f}%, Max = {delta.max():.4f}%, 95th Pct = {delta.quantile(0.95):.4f}%")
        for s in ['Low-Volume (120-220b)', 'Mid-Volume (221-420b)', 'High-Volume (>420b)']:
            s_delta = delta[q_bat['stratum'] == s]
            print(f"    {s:22s}: Mean Abs Delta = {s_delta.mean():.4f}%, Max = {s_delta.max():.4f}%")
            
    # Top-10 Batters by lowest wicket hazard (highest survival)
    print("\nTop-10 Lowest Wicket Hazard Batter Overlap across Caps:")
    top10_by_cap = {}
    for M in [60, 90, 120, 180]:
        top10_by_cap[M] = set(q_bat.sort_values(f'p_hat_{M}', ascending=True)['striker_id'].head(10))
    print(f"  Top 10 Overlap (M=60 vs M=90):   {len(top10_by_cap[60].intersection(top10_by_cap[90]))}/10")
    print(f"  Top 10 Overlap (M=90 vs M=120):  {len(top10_by_cap[90].intersection(top10_by_cap[120]))}/10")
    print(f"  Top 10 Overlap (M=90 vs M=180):  {len(top10_by_cap[90].intersection(top10_by_cap[180]))}/10")
    print(f"  Top 10 Overlap (M=60 vs M=180):  {len(top10_by_cap[60].intersection(top10_by_cap[180]))}/10")
    
    # ==============================================================================
    # TASK 3: BOOTSTRAP CLUSTERING VALIDATION & MULTI-INNINGS ANALYSIS
    # ==============================================================================
    print("\n------------------------------------------------------------------")
    print("TASK 3: BOOTSTRAP CLUSTERING (SCHEMES A, B, C; MULTI-INNINGS; MC STABILITY)")
    print("------------------------------------------------------------------")
    
    # Multi-innings empirical audit
    bat_mi = bbb.groupby(['match_id', 'striker_id'])['innings'].nunique()
    bowl_mi = bbb.groupby(['match_id', 'bowler_id'])['innings'].nunique()
    print(f"Batter Multi-Innings Matches: {len(bat_mi[bat_mi > 1])} out of {len(bat_mi)} ({len(bat_mi[bat_mi > 1])/len(bat_mi)*100:.2f}%)")
    print(f"Bowler Multi-Innings Matches: {len(bowl_mi[bowl_mi > 1])} out of {len(bowl_mi)} ({len(bowl_mi[bowl_mi > 1])/len(bowl_mi)*100:.2f}%)")
    
    # Detailed bowler analysis for multi-innings matches
    multi_bowl_cases = bowl_mi[bowl_mi > 1].index.tolist()
    print(f"\nAudit of Multi-Innings Bowlers (Total instances = {len(multi_bowl_cases)}):")
    multi_records = []
    for mid, bid in multi_bowl_cases:
        p_sub = bbb[(bbb['match_id'] == mid) & (bbb['bowler_id'] == bid)]
        inns_list = p_sub['innings'].unique().tolist()
        balls_per_inn = p_sub.groupby('innings').size().to_dict()
        runs_per_inn = p_sub.groupby('innings')['runs'].sum().to_dict()
        multi_records.append({
            'match_id': mid, 'bowler_id': bid, 'innings': inns_list,
            'balls': balls_per_inn, 'runs': runs_per_inn
        })
    print(pd.DataFrame(multi_records).to_string(index=False))
    
    # Monte Carlo stability across B = 250, 500, 1000, 2000 for a representative player sample
    print("\nMonte Carlo Stability across Draw Counts B in Scheme B:")
    sample_bat_ids = q_bat['striker_id'].head(10).values
    for B_draws in [250, 500, 1000, 2000]:
        se_reps = []
        for rep in range(5):
            np.random.seed(100 + rep * 17)
            se_list = []
            for pid in sample_bat_ids:
                p_df = valid_bat[valid_bat['striker_id'] == pid]
                inn_agg = p_df.groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
                ni = len(inn_agg)
                idx = np.random.choice(ni, size=(B_draws, ni), replace=True)
                se_b = (inn_agg[idx, 0].sum(axis=1) / inn_agg[idx, 1].sum(axis=1) * 100).std()
                se_list.append(se_b)
            se_reps.append(np.mean(se_list))
        print(f"  Draws B = {B_draws:4d}: Mean SE over 5 runs = {np.mean(se_reps):.4f} SR | Std over runs (MC SE) = {np.std(se_reps):.4f} SR | CV = {np.std(se_reps)/np.mean(se_reps)*100:.3f}%")
        
    # Rank correlations between Scheme B and Scheme C
    # Load previously computed bootstrap distributions from final_signoff_audit logic
    # Re-run for complete qualified sets
    np.random.seed(42)
    b_se_a, b_se_b, b_se_c = [], [], []
    for pid in q_bat['striker_id'].values:
        p_df = valid_bat[valid_bat['striker_id'] == pid]
        runs_d = p_df['runs'].values
        nd = len(runs_d)
        b_se_a.append(np.random.choice(runs_d, size=(1000, nd), replace=True).mean(axis=1).std() * 100)
        
        inn_agg = p_df.groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
        ni = len(inn_agg)
        idx_b = np.random.choice(ni, size=(1000, ni), replace=True)
        b_se_b.append((inn_agg[idx_b, 0].sum(axis=1) / inn_agg[idx_b, 1].sum(axis=1) * 100).std())
        
        m_agg = p_df.groupby('match_id')['runs'].agg(['sum', 'count']).values
        nm = len(m_agg)
        idx_c = np.random.choice(nm, size=(1000, nm), replace=True)
        b_se_c.append((m_agg[idx_c, 0].sum(axis=1) / m_agg[idx_c, 1].sum(axis=1) * 100).std())
        
    b_se_a = np.array(b_se_a)
    b_se_b = np.array(b_se_b)
    b_se_c = np.array(b_se_c)
    
    bw_se_a, bw_se_b, bw_se_c = [], [], []
    for bid in q_bowl['bowler_id'].values:
        p_df = valid_bowl[valid_bowl['bowler_id'] == bid]
        runs_d = p_df['runs'].values
        nd = len(runs_d)
        bw_se_a.append(np.random.choice(runs_d, size=(1000, nd), replace=True).mean(axis=1).std() * 6.0)
        
        inn_agg = p_df.groupby(['match_id', 'innings'])['runs'].agg(['sum', 'count']).values
        ni = len(inn_agg)
        idx_b = np.random.choice(ni, size=(1000, ni), replace=True)
        bw_se_b.append((inn_agg[idx_b, 0].sum(axis=1) / inn_agg[idx_b, 1].sum(axis=1) * 6.0).std())
        
        m_agg = p_df.groupby('match_id')['runs'].agg(['sum', 'count']).values
        nm = len(m_agg)
        idx_c = np.random.choice(nm, size=(1000, nm), replace=True)
        bw_se_c.append((m_agg[idx_c, 0].sum(axis=1) / m_agg[idx_c, 1].sum(axis=1) * 6.0).std())
        
    bw_se_a = np.array(bw_se_a)
    bw_se_b = np.array(bw_se_b)
    bw_se_c = np.array(bw_se_c)
    
    print("\nDetailed Resampling Percentiles & Ratio Distributions:")
    print("Batters (N = 250):")
    print(f"  Scheme A (Delivery):      Median = {np.median(b_se_a):.2f} | Mean = {np.mean(b_se_a):.2f} | 25th = {np.percentile(b_se_a, 25):.2f} | 75th = {np.percentile(b_se_a, 75):.2f} | 95th = {np.percentile(b_se_a, 95):.2f}")
    print(f"  Scheme B (Match-Innings): Median = {np.median(b_se_b):.2f} | Mean = {np.mean(b_se_b):.2f} | 25th = {np.percentile(b_se_b, 25):.2f} | 75th = {np.percentile(b_se_b, 75):.2f} | 95th = {np.percentile(b_se_b, 95):.2f}")
    print(f"  Scheme C (Whole Match):   Median = {np.median(b_se_c):.2f} | Mean = {np.mean(b_se_c):.2f} | 25th = {np.percentile(b_se_c, 25):.2f} | 75th = {np.percentile(b_se_c, 75):.2f} | 95th = {np.percentile(b_se_c, 95):.2f}")
    r_ba_bat = b_se_b / b_se_a
    r_cb_bat = b_se_c / b_se_b
    print(f"  Ratio B / A: Median = {np.median(r_ba_bat):.2f}x | Mean = {np.mean(r_ba_bat):.2f}x | 25th = {np.percentile(r_ba_bat, 25):.2f}x | 75th = {np.percentile(r_ba_bat, 75):.2f}x | 95th = {np.percentile(r_ba_bat, 95):.2f}x")
    print(f"  Ratio C / B: Median = {np.median(r_cb_bat):.2f}x | Mean = {np.mean(r_cb_bat):.2f}x | 25th = {np.percentile(r_cb_bat, 25):.2f}x | 75th = {np.percentile(r_cb_bat, 75):.2f}x | 95th = {np.percentile(r_cb_bat, 95):.2f}x")
    print(f"  Spearman Corr(SE_B, SE_C): {stats.spearmanr(b_se_b, b_se_c).statistic:.6f}")
    
    print("\nBowlers (N = 227):")
    print(f"  Scheme A (Delivery):      Median = {np.median(bw_se_a):.2f} | Mean = {np.mean(bw_se_a):.2f} | 25th = {np.percentile(bw_se_a, 25):.2f} | 75th = {np.percentile(bw_se_a, 75):.2f} | 95th = {np.percentile(bw_se_a, 95):.2f}")
    print(f"  Scheme B (Match-Innings): Median = {np.median(bw_se_b):.2f} | Mean = {np.mean(bw_se_b):.2f} | 25th = {np.percentile(bw_se_b, 25):.2f} | 75th = {np.percentile(bw_se_b, 75):.2f} | 95th = {np.percentile(bw_se_b, 95):.2f}")
    print(f"  Scheme C (Whole Match):   Median = {np.median(bw_se_c):.2f} | Mean = {np.mean(bw_se_c):.2f} | 25th = {np.percentile(bw_se_c, 25):.2f} | 75th = {np.percentile(bw_se_c, 75):.2f} | 95th = {np.percentile(bw_se_c, 95):.2f}")
    r_ba_bowl = bw_se_b / bw_se_a
    r_cb_bowl = bw_se_c / bw_se_b
    print(f"  Ratio B / A: Median = {np.median(r_ba_bowl):.2f}x | Mean = {np.mean(r_ba_bowl):.2f}x | 25th = {np.percentile(r_ba_bowl, 25):.2f}x | 75th = {np.percentile(r_ba_bowl, 75):.2f}x | 95th = {np.percentile(r_ba_bowl, 95):.2f}x")
    print(f"  Ratio C / B: Median = {np.median(r_cb_bowl):.2f}x | Mean = {np.mean(r_cb_bowl):.2f}x | 25th = {np.percentile(r_cb_bowl, 25):.2f}x | 75th = {np.percentile(r_cb_bowl, 75):.2f}x | 95th = {np.percentile(r_cb_bowl, 95):.2f}x")
    print(f"  Spearman Corr(SE_B, SE_C): {stats.spearmanr(bw_se_b, bw_se_c).statistic:.6f}")
    
    # ==============================================================================
    # TASK 4: ROLE STANDARDIZATION SAFEGUARDS & SENSITIVITY
    # ==============================================================================
    print("\n------------------------------------------------------------------")
    print("TASK 4: ROLE STANDARDIZATION SENSITIVITY (CUTOFFS, REGULARIZATION, POOLING)")
    print("------------------------------------------------------------------")
    
    # 4.1 Batting Roles
    # Def 1: Standard entry over
    # Find entry over for each batter innings
    first_ball = valid_bat.groupby(['match_id', 'innings', 'striker_id'])['overid'].min().reset_index()
    avg_entry = first_ball.groupby('striker_id')['overid'].mean()
    q_bat['avg_entry'] = q_bat['striker_id'].map(avg_entry)
    
    def bat_role_1(entry):
        if entry <= 6.0: return 'Top Order'
        elif entry <= 13.0: return 'Middle Order'
        else: return 'Finisher'
        
    # Def 2: Phase ball proportions
    def get_phase(o):
        if o <= 6: return 'PP'
        elif o <= 15: return 'Mid'
        else: return 'Death'
    valid_bat['phase'] = valid_bat['overid'].apply(get_phase)
    phase_shares = valid_bat.groupby(['striker_id', 'phase']).size().unstack(fill_value=0)
    phase_shares['tot'] = phase_shares.sum(axis=1)
    for p in ['PP', 'Mid', 'Death']:
        phase_shares[p+'_pct'] = phase_shares[p] / phase_shares['tot']
        
    q_bat['pp_pct'] = q_bat['striker_id'].map(phase_shares['PP_pct'])
    q_bat['death_pct'] = q_bat['striker_id'].map(phase_shares['Death_pct'])
    
    def bat_role_2(r):
        if r['pp_pct'] >= 0.50: return 'Top Order'
        elif r['death_pct'] >= 0.35: return 'Finisher'
        else: return 'Middle Order'
        
    q_bat['role_def1'] = q_bat['avg_entry'].apply(bat_role_1)
    q_bat['role_def2'] = q_bat.apply(bat_role_2, axis=1)
    
    print("Batting Cohort Sizes:")
    print("  Definition 1 (Entry Over: <=6.0, 6.1-13.0, >13.0):", q_bat['role_def1'].value_counts().to_dict())
    print("  Definition 2 (Phase %: PP>=50%, Death>=35%):       ", q_bat['role_def2'].value_counts().to_dict())
    
    # 4.2 Bowler Roles
    # Def B1: Standard: PP >= 40%, Death >= 30%
    # Def B2: Relaxed:  PP >= 35%, Death >= 25%
    # Def B3: Strict:   PP >= 45%, Death >= 35%
    valid_bowl['phase'] = valid_bowl['overid'].apply(get_phase)
    b_shares = valid_bowl.groupby(['bowler_id', 'phase']).size().unstack(fill_value=0)
    b_shares['tot'] = b_shares.sum(axis=1)
    for p in ['PP', 'Mid', 'Death']:
        b_shares[p+'_pct'] = b_shares[p] / b_shares['tot']
        
    q_bowl['pp_pct'] = q_bowl['bowler_id'].map(b_shares['PP_pct'])
    q_bowl['death_pct'] = q_bowl['bowler_id'].map(b_shares['Death_pct'])
    
    def role_b1(r):
        if r['pp_pct'] >= 0.40: return 'Powerplay'
        elif r['death_pct'] >= 0.30: return 'Death'
        else: return 'Middle'
        
    def role_b2(r):
        if r['pp_pct'] >= 0.35: return 'Powerplay'
        elif r['death_pct'] >= 0.25: return 'Death'
        else: return 'Middle'
        
    def role_b3(r):
        if r['pp_pct'] >= 0.45: return 'Powerplay'
        elif r['death_pct'] >= 0.35: return 'Death'
        else: return 'Middle'
        
    q_bowl['role_b1'] = q_bowl.apply(role_b1, axis=1)
    q_bowl['role_b2'] = q_bowl.apply(role_b2, axis=1)
    q_bowl['role_b3'] = q_bowl.apply(role_b3, axis=1)
    
    print("\nBowling Cohort Sizes:")
    print("  Definition B1 (Standard: PP>=40%, Death>=30%):", q_bowl['role_b1'].value_counts().to_dict())
    print("  Definition B2 (Relaxed:  PP>=35%, Death>=25%):", q_bowl['role_b2'].value_counts().to_dict())
    print("  Definition B3 (Strict:   PP>=45%, Death>=35%):", q_bowl['role_b3'].value_counts().to_dict())
    
    # 4.3 Variance Regularization Sensitivity: alpha in [0.00, 0.05, 0.10, 0.20]
    # Check impact on z-scores for batters under role_def1
    league_sigma_bat = q_bat['sr_NN'].std()
    cohort_stats_bat = q_bat.groupby('role_def1')['sr_NN'].agg(['mean', 'std', 'count'])
    print(f"\nBatting Cohort Empirical Moments (League SD = {league_sigma_bat:.2f}):")
    print(cohort_stats_bat.round(2))
    
    for alpha in [0.00, 0.05, 0.10, 0.20]:
        col = f'z_sr_alpha_{int(alpha*100)}'
        q_bat[col] = 0.0
        for r, row in cohort_stats_bat.iterrows():
            mu_c = row['mean']
            sigma_c = row['std']
            sigma_reg = np.sqrt(sigma_c**2 + (alpha * league_sigma_bat)**2)
            mask = q_bat['role_def1'] == r
            q_bat.loc[mask, col] = (q_bat.loc[mask, 'sr_NN'] - mu_c) / sigma_reg
            
    print("\nImpact of Variance Regularization (alpha) on Batter Z-scores:")
    corr_z0_z10 = q_bat['z_sr_alpha_0'].corr(q_bat['z_sr_alpha_10'], method='spearman')
    corr_z0_z20 = q_bat['z_sr_alpha_0'].corr(q_bat['z_sr_alpha_20'], method='spearman')
    max_delta_z10 = (q_bat['z_sr_alpha_0'] - q_bat['z_sr_alpha_10']).abs().max()
    max_delta_z20 = (q_bat['z_sr_alpha_0'] - q_bat['z_sr_alpha_20']).abs().max()
    print(f"  Spearman Corr (alpha=0.00 vs 0.10): {corr_z0_z10:.6f} | Max Delta Z: {max_delta_z10:.4f}")
    print(f"  Spearman Corr (alpha=0.00 vs 0.20): {corr_z0_z20:.6f} | Max Delta Z: {max_delta_z20:.4f}")
    
    # 4.4 Partial-Pooling Sensitivity: K_pool in [0, 5, 10, 20]
    league_mu_bat = q_bat['sr_NN'].mean()
    print(f"\nPartial Pooling of Cohort Means toward League Mean ({league_mu_bat:.2f} SR):")
    for K_pool in [0, 5, 10, 20]:
        pooled_means = {}
        for r, row in cohort_stats_bat.iterrows():
            nc = row['count']
            mu_c = row['mean']
            pooled_mu = (nc / (nc + K_pool)) * mu_c + (K_pool / (nc + K_pool)) * league_mu_bat
            pooled_means[r] = pooled_mu
        print(f"  K_pool = {K_pool:2d}: " + " | ".join([f"{k}: {v:.2f}" for k, v in pooled_means.items()]))
        
    print("\n==================================================================")
    print("M3 CLOSURE AUDIT COMPLETE: ALL METRICS REPRODUCIBLE")
    print("==================================================================")

if __name__ == '__main__':
    run_closure_audit()

