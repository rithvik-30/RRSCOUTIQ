"""
Unit and Integration Tests for Milestone R1.1.1: Targeted Statistical Verification.
Verifies window length exactness, setting model comparison structure,
clustered standard error inflation properties, and threshold evaluation balance.
"""

from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from src.r1_1_1_targeted_verification.window_length_audit import audit_window_lengths
from src.r1_1_1_targeted_verification.clustered_regression_audit import compute_ols_with_clustered_se


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def match_state_df(project_root) -> pd.DataFrame:
    path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    assert path.exists(), f"Missing match state file: {path}"
    return pd.read_csv(path, low_memory=False)


def test_clustered_se_inflation_ratio():
    """Verify that match clustering inflates standard errors when positive intra-cluster correlation is present."""
    # Synthetic dataset with intra-cluster correlation
    np.random.seed(42)
    G = 50
    cluster_effects = np.random.normal(0, 1.0, size=G)
    cluster_x = np.random.normal(0, 1.0, size=G)
    clusters = np.repeat(np.arange(G), 20)
    N = len(clusters)

    x1_correlated = cluster_x[clusters] + np.random.normal(0, 0.2, N)
    X_mat = np.column_stack([np.ones(N), x1_correlated])
    y = 0.5 * X_mat[:, 1] + cluster_effects[clusters] + np.random.normal(0, 0.5, N)

    df_res = compute_ols_with_clustered_se(X_mat, y, clusters, ["Intercept", "X1"])

    # Clustered SE must be strictly greater than classical OLS SE for cluster-correlated regressors
    for _, row in df_res.iterrows():
        assert row["se_match_clustered"] > row["se_classical_ols"], "Clustered SE should exceed classical OLS SE"
        assert row["se_cluster_inflation_ratio"] > 1.0


def test_exact_6_ball_window_bounds(match_state_df: pd.DataFrame):
    """Verify that exact 6-ball windows contain strictly valid non-negative values."""
    # Test on single match
    sample = match_state_df[match_state_df["match_id"] == 13511].copy()
    _, valid_legal = audit_window_lengths(sample)

    exact_6 = valid_legal[valid_legal["window_length"] == 6]
    assert len(exact_6) > 0
    assert (exact_6["fwd_runs_scaled"] >= 0).all()
    assert (exact_6["fwd_wkts_scaled"] >= 0).all()
    assert (exact_6["fwd_dot_pct"] >= 0).all()
    assert (exact_6["fwd_dot_pct"] <= 100).all()


def test_forensic_csv_deliverables_exist(project_root: Path):
    """Verify that all forensic and sensitivity CSV deliverables exist and are non-empty."""
    out_dir = project_root / "research" / "R1_1_1_TARGETED_VERIFICATION"
    expected_files = [
        "R1_1_1_FINAL_FORENSIC_VERIFICATION_REPORT.md",
        "exact_six_independent_reproduction.csv",
        "setting_model_complete_comparison.csv",
        "clustered_covariance_reproduction.csv",
        "threshold_adjacent_tier_uncertainty.csv",
        "innings_specific_regression.csv",
        "pooled_interaction_regression.csv",
        "early_crr_sensitivity.csv",
        "regression_conditioning_diagnostics.csv",
        "fully_interacted_regression.csv",
        "joint_control_wald_test.csv",
    ]
    for fname in expected_files:
        p = out_dir / fname
        assert p.exists(), f"Missing deliverable: {p}"
        assert p.stat().st_size > 0, f"Empty deliverable: {p}"


def test_sensitivity_interaction_and_conditioning(project_root: Path):
    """Verify that the DLI x Chase interaction is statistically indistinguishable from zero and matrix is well-conditioned."""
    df_int = pd.read_csv(project_root / "research" / "R1_1_1_TARGETED_VERIFICATION" / "pooled_interaction_regression.csv")
    int_row = df_int[df_int["variable_name"] == "DLI_x_Chase"].iloc[0]
    # Interaction p-value must be > 0.05 (statistically insignificant)
    assert float(int_row["p_val_match_clustered"]) > 0.05
    assert abs(float(int_row["t_stat_match_clustered"])) < 1.96

    df_diag = pd.read_csv(project_root / "research" / "R1_1_1_TARGETED_VERIFICATION" / "regression_conditioning_diagnostics.csv")
    dli_vif = df_diag[df_diag["variable_name"] == "DLI"]["vif_factor"].iloc[0]
    assert float(dli_vif) < 10.0, "DLI VIF must be below 10.0"


def test_fully_interacted_slope_contrast(project_root: Path):
    """Verify that in the fully interacted model, the DLI slope difference between Setting and Chasing is statistically insignificant."""
    df_full = pd.read_csv(project_root / "research" / "R1_1_1_TARGETED_VERIFICATION" / "fully_interacted_regression.csv")
    diff_row = df_full[df_full["variable_name"] == "Diff_DLI_Slope (Chase - Setting)"].iloc[0]
    
    # Linear contrast slope difference is -0.02781, clustered SE is 0.0356, t is -0.781, p is ~0.435
    beta_diff = float(diff_row["coefficient_beta"])
    t_stat = float(diff_row["t_stat_match_clustered"])
    p_val = float(diff_row["p_val_match_clustered"])
    
    assert abs(beta_diff - (-0.02781)) < 0.001
    assert abs(t_stat - (-0.781)) < 0.05
    assert p_val > 0.05, "DLI slope difference must fail to reject null of equal slopes (p > 0.05)"


def test_joint_control_wald_test(project_root: Path):
    """Verify that the joint match-clustered Wald test of the five control interactions fails to reject null at 5%."""
    df_wald = pd.read_csv(project_root / "research" / "R1_1_1_TARGETED_VERIFICATION" / "joint_control_wald_test.csv")
    row = df_wald.iloc[0]
    
    assert row["df_numerator_q"] == 5
    assert row["df_denominator_g_minus_1"] == 743
    assert abs(float(row["wald_chi2_statistic"]) - 7.202) < 0.01
    assert abs(float(row["f_statistic"]) - 1.440) < 0.01
    assert float(row["wald_chi2_p_value"]) > 0.05, "Joint Wald p-value must fail to reject null at 5%"
    assert float(row["f_p_value"]) > 0.05, "Joint F p-value must fail to reject null at 5%"
    assert row["rejected_at_alpha_0_05"] == False
    assert row["submatrix_rank"] == 5

    # Check standardized scaling stability
    row_scaled = df_wald.iloc[1]
    assert float(row_scaled["submatrix_condition_number"]) < 10.0, "Scaled covariance condition number must be < 10"
    assert float(row_scaled["wald_diff_from_unscaled"]) < 1e-12, "Wald statistic must be invariant under diagonal scaling"
    assert row_scaled["submatrix_rank"] == 5


