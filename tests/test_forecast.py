"""
Unit tests for Checkpoint 2: Machine learning forecasting models, feature engineering,
chronological holdout evaluation, naive baseline benchmarking, and model persistence.
"""

import os
import pytest
import numpy as np
import pandas as pd
from src.data_pipeline import build_aligned_dataset
from src.forecast import (
    create_feature_matrix,
    chronological_split,
    compute_metrics,
    train_and_evaluate_forecaster,
    train_all_models,
    load_saved_models_and_metrics,
    get_forecast_chart_data,
    LightGBMForecaster,
    SOLAR_MODEL_PATH,
    LOAD_MODEL_PATH,
    METRICS_PATH,
)


@pytest.fixture(scope="module")
def sample_dataset():
    """Generate a reproducible time-series dataset with realistic variability for testing."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", "2023-01-31 23:00", freq="h")
    # Base diurnal solar with realistic weather/cloud fluctuation noise
    base_solar = np.maximum(0.0, np.sin(np.pi * (dates.hour - 6) / 12)) * (dates.hour >= 6) * (dates.hour <= 18)
    weather_noise = np.random.normal(0, 0.06, len(dates))
    solar = np.clip(base_solar + weather_noise * (dates.hour >= 6) * (dates.hour <= 18), 0.0, 1.0)
    
    # Synthetic load with morning/evening ramp + random noise
    load = 0.4 + 0.4 * np.sin(2 * np.pi * (dates.hour - 4) / 24) + np.random.normal(0, 0.05, len(dates))
    df = pd.DataFrame({
        "solar_pu": solar,
        "load_pu": np.clip(load, 0.1, 1.0)
    }, index=dates)
    return df


def test_feature_matrix_generation(sample_dataset):
    """Verify feature engineering produces expected lag and temporal columns with no NaNs."""
    X, y, feature_cols = create_feature_matrix(sample_dataset, target_col="solar_pu", lags=[1, 2, 3, 24])
    
    assert len(X) == len(sample_dataset) - 24
    assert "solar_pu_lag_1" in X.columns
    assert "solar_pu_lag_2" in X.columns
    assert "solar_pu_lag_3" in X.columns
    assert "solar_pu_lag_24" in X.columns
    assert "hour" in X.columns
    assert "dayofweek" in X.columns
    assert "hour_sin" in X.columns
    assert "hour_cos" in X.columns
    assert X.isna().sum().sum() == 0
    assert len(y) == len(X)


def test_chronological_split(sample_dataset):
    """Verify time-series split is strictly chronological with zero lookahead leakage."""
    X, y, _ = create_feature_matrix(sample_dataset, target_col="solar_pu")
    X_train, X_test, y_train, y_test = chronological_split(X, y, test_ratio=0.25)
    
    assert len(X_train) + len(X_test) == len(X)
    assert X_train.index[-1] < X_test.index[0]
    assert y_train.index[-1] < y_test.index[0]
    assert len(X_test) == int(len(X) * 0.25)


def test_compute_metrics_accuracy():
    """Verify pure numpy metric calculation logic."""
    y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y_pred = np.array([1.1, 1.9, 3.2, 3.8, 5.1])
    
    metrics = compute_metrics(y_true, y_pred)
    assert 0.0 < metrics["mae"] < 0.2
    assert 0.0 < metrics["rmse"] < 0.2
    assert metrics["r2"] > 0.95


def test_forecaster_training_and_convergence(sample_dataset):
    """Verify model fits cleanly and produces valid predictions."""
    res = train_and_evaluate_forecaster(sample_dataset, target_col="solar_pu", test_ratio=0.20)
    
    assert res["model"] is not None
    assert "mae" in res["model_metrics"]
    assert "rmse" in res["model_metrics"]
    assert "r2" in res["model_metrics"]
    assert res["model_metrics"]["mae"] < 0.15
    assert len(res["test_results_df"]) == res["test_samples"]


def test_model_outperforms_naive_baseline(sample_dataset):
    """Verify model beats naive persistence baseline on chronological holdout."""
    solar_res = train_and_evaluate_forecaster(sample_dataset, target_col="solar_pu", test_ratio=0.20)
    load_res = train_and_evaluate_forecaster(sample_dataset, target_col="load_pu", test_ratio=0.20)
    
    assert solar_res["model_metrics"]["mae"] <= solar_res["baseline_metrics"]["mae"]
    assert load_res["model_metrics"]["mae"] <= load_res["baseline_metrics"]["mae"]
    assert solar_res["mae_improvement_pct"] >= 0.0
    assert load_res["mae_improvement_pct"] >= 0.0


def test_model_persistence_and_reload():
    """Verify end-to-end model training, serialization, and deserialization."""
    res = train_all_models(save=True)
    assert os.path.exists(SOLAR_MODEL_PATH)
    assert os.path.exists(LOAD_MODEL_PATH)
    assert os.path.exists(METRICS_PATH)
    
    loaded = load_saved_models_and_metrics()
    assert loaded is not None
    assert loaded["solar_model"] is not None
    assert loaded["load_model"] is not None
    assert "solar" in loaded["summary"]
    assert "load" in loaded["summary"]


def test_get_forecast_chart_data():
    """Verify payload formatted for frontend visualization."""
    chart_payload = get_forecast_chart_data(max_points=48)
    
    assert "points" in chart_payload
    assert "summary" in chart_payload
    assert len(chart_payload["points"]) == 48
    
    pt = chart_payload["points"][0]
    assert "timestamp" in pt
    assert "solar_actual" in pt
    assert "solar_pred" in pt
    assert "load_actual" in pt
    assert "load_pred" in pt
