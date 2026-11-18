"""
M5.5-B.4.3.3: Final Statistical Consistency Corrections
Targeted Statistical Remediation Module

Focus:
1. Exact Henderson Method III crossed-effects decomposition incorporating contextual fixed effects:
   - Eliminates unweighted centering by directly modeling [X_c, X_b, X_m] in weighted least squares.
   - Exact rank rank([X_c, X_b, X_m]) = K + I + M - 1 - c for arbitrary c connected bipartite components.
   - Exact degrees of freedom df_E = N - rank(X_cbm), df_m = M - c, df_b = I - c.
   - Closed-form analytical trace coefficients for partial reductions R(m | c, b) and R(b | c, m).
2. Match environmental variance in player contextual posterior shrinkage:
   - Derives observation variance V_{i, c} = (6.0 * sigma2_within / n_{i, c}) + H_{i, c} * sigma2_match,
     where H_{i, c} = sum_m (n_{im} / n_{i, c})^2 is the Herfindahl-Hirschman match exposure concentration.
   - Distinguishes delivery volume from independent match exposure without treating multi-spells in
     the same match as independent shocks.
3. Strict validation and rejection of invalid calibration inputs (NaN, Inf, reversed bounds, out-of-range coverage).
"""

__version__ = "5.5.4.3.3"
