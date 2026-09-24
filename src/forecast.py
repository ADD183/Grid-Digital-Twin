"""
Forecasting module for Renewable Distribution Grid Digital Twin (Checkpoint 2).
Provides feature engineering (lagged + calendar features), chronological train/test splitting,
solar & load gradient boosting models (using native LightGBM with pure-Python fallback),
naive baseline benchmarking (persistence t-1 and seasonal t-24), and model persistence via joblib.
"""

import os
import joblib
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

from src.data_pipeline import build_aligned_dataset, DEFAULT_ALIGNED_OUTPUT

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "models")
SOLAR_MODEL_PATH = os.path.join(MODEL_DIR, "solar_forecast_model.joblib")
LOAD_MODEL_PATH = os.path.join(MODEL_DIR, "load_forecast_model.joblib")
METRICS_PATH = os.path.join(MODEL_DIR, "forecast_metrics.joblib")


def ensure_model_dir():
    """Ensure destination directory for serialized models exists."""
    os.makedirs(MODEL_DIR, exist_ok=True)


def create_feature_matrix(
    df: pd.DataFrame,
    target_col: str,
    lags: List[int] = [1, 2, 3, 24],
    drop_na: bool = True
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """
    Construct lagged time-series features and calendar attributes for a given target column.
    
    Args:
        df (pd.DataFrame): Time-indexed DataFrame containing the target series.
        target_col (str): Column name to forecast (e.g., 'solar_pu' or 'load_pu').
        lags (List[int]): Hourly lag offsets to generate.
        drop_na (bool): Whether to drop rows with NaN values resulting from lag shifts.
        
    Returns:
        Tuple[pd.DataFrame, pd.Series, List[str]]: Feature matrix X, target series y, and list of feature names.
    """
    df_feat = df.copy()
    
    # Calendar / temporal features
    df_feat["hour"] = df_feat.index.hour
    df_feat["dayofweek"] = df_feat.index.dayofweek
    df_feat["dayofyear"] = df_feat.index.dayofyear
    df_feat["month"] = df_feat.index.month
    df_feat["is_weekend"] = (df_feat["dayofweek"] >= 5).astype(int)
    
    # Trigonometric cyclical encodings for hour and day of year
    df_feat["hour_sin"] = np.sin(2 * np.pi * df_feat["hour"] / 24.0)
    df_feat["hour_cos"] = np.cos(2 * np.pi * df_feat["hour"] / 24.0)
    df_feat["day_sin"] = np.sin(2 * np.pi * df_feat["dayofyear"] / 365.25)
    df_feat["day_cos"] = np.cos(2 * np.pi * df_feat["dayofyear"] / 365.25)
    
    feature_cols = [
        "hour", "dayofweek", "dayofyear", "month", "is_weekend",
        "hour_sin", "hour_cos", "day_sin", "day_cos"
    ]
    
    # Generate lag features
    for lag in lags:
        col_name = f"{target_col}_lag_{lag}"
        df_feat[col_name] = df_feat[target_col].shift(lag)
        feature_cols.append(col_name)
        
    # Rolling window statistics (e.g. 24h mean)
    df_feat[f"{target_col}_roll_mean_24"] = df_feat[target_col].shift(1).rolling(24, min_periods=1).mean()
    feature_cols.append(f"{target_col}_roll_mean_24")
    
    if drop_na:
        df_feat = df_feat.dropna()
        
    X = df_feat[feature_cols]
    y = df_feat[target_col]
    return X, y, feature_cols


def chronological_split(
    X: pd.DataFrame,
    y: pd.DataFrame,
    test_ratio: float = 0.20,
    test_hours: Optional[int] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Split time-series data chronologically (train on historical period, test on future holdout).
    
    Args:
        X (pd.DataFrame): Features indexed by timestamp.
        y (pd.Series): Target series indexed by timestamp.
        test_ratio (float): Ratio of most recent data reserved for test set.
        test_hours (Optional[int]): Exact number of final hours for test set.
        
    Returns:
        Tuple: X_train, X_test, y_train, y_test
    """
    n_samples = len(X)
    if test_hours is not None:
        split_idx = max(1, n_samples - test_hours)
    else:
        split_idx = int(n_samples * (1.0 - test_ratio))
        
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    return X_train, X_test, y_train, y_test


class LightGBMForecaster:
    """
    Gradient boosting forecaster using LightGBM, with a scikit-learn fallback.
    """
    def __init__(self, num_boost_round: int = 150, learning_rate: float = 0.05, num_leaves: int = 31):
        self.num_boost_round = num_boost_round
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.booster = None
        self.fallback_model = None
        self.feature_names = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.feature_names = list(X.columns)
        if HAS_LIGHTGBM:
            params = {
                "objective": "regression",
                "metric": "l1",
                "boosting_type": "gbdt",
                "learning_rate": self.learning_rate,
                "num_leaves": self.num_leaves,
                "verbosity": -1,
                "min_child_samples": 20,
                "seed": 42
            }
            train_data = lgb.Dataset(X, label=y, feature_name=self.feature_names)
            self.booster = lgb.train(params, train_data, num_boost_round=self.num_boost_round)
        else:
            try:
                from sklearn.ensemble import GradientBoostingRegressor
            except ImportError as exc:
                raise ImportError(
                    "LightGBM is unavailable and scikit-learn could not be loaded for the fallback forecaster."
                ) from exc
            self.fallback_model = GradientBoostingRegressor(
                n_estimators=self.num_boost_round,
                learning_rate=self.learning_rate,
                max_depth=3,
                random_state=42,
                loss="huber",
            )
            self.fallback_model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.booster is not None:
            preds = self.booster.predict(X)
        elif self.fallback_model is not None:
            preds = self.fallback_model.predict(X)
        else:
            raise RuntimeError("Model has not been fitted yet.")
        return np.clip(preds, 0.0, None)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate regression performance metrics (MAE, RMSE, R2) in pure numpy."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    r2 = float(1.0 - (ss_res / max(ss_tot, 1e-9)))
    
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4)
    }


def train_and_evaluate_forecaster(
    df: pd.DataFrame,
    target_col: str,
    test_ratio: float = 0.20,
    model_name: str = "model"
) -> Dict[str, Any]:
    """
    Train a forecasting model and evaluate against naive persistence baselines on chronological test holdout.
    
    Args:
        df (pd.DataFrame): Input time-series dataset.
        target_col (str): Column name to predict.
        test_ratio (float): Ratio for chronological holdout test set.
        model_name (str): Label identifier.
        
    Returns:
        Dict[str, Any]: Results dictionary with trained model, metrics, and test predictions.
    """
    X, y, feature_cols = create_feature_matrix(df, target_col=target_col)
    X_train, X_test, y_train, y_test = chronological_split(X, y, test_ratio=test_ratio)
    
    # Train model
    model = LightGBMForecaster(num_boost_round=150, learning_rate=0.05)
    model.fit(X_train, y_train)
    
    # Model predictions on test set
    y_pred = model.predict(X_test)
    model_metrics = compute_metrics(y_test.values, y_pred)
    
    # Naive baseline 1: Persistence t-1 (last known hour)
    naive_t1 = X_test[f"{target_col}_lag_1"].values
    naive_t1_metrics = compute_metrics(y_test.values, naive_t1)
    
    # Naive baseline 2: Seasonal persistence t-24 (same hour yesterday)
    naive_t24 = X_test[f"{target_col}_lag_24"].values
    naive_t24_metrics = compute_metrics(y_test.values, naive_t24)
    
    # Use best naive baseline for comparison (t-24 or t-1)
    baseline_metrics = naive_t24_metrics if naive_t24_metrics["mae"] < naive_t1_metrics["mae"] else naive_t1_metrics
    
    mae_improvement_pct = round(
        ((baseline_metrics["mae"] - model_metrics["mae"]) / max(baseline_metrics["mae"], 1e-6)) * 100.0, 2
    )
    rmse_improvement_pct = round(
        ((baseline_metrics["rmse"] - model_metrics["rmse"]) / max(baseline_metrics["rmse"], 1e-6)) * 100.0, 2
    )

    # Compile test comparisons for plotting
    test_results_df = pd.DataFrame({
        "actual": y_test.values,
        "predicted": y_pred,
        "naive_persistence": naive_t24,
    }, index=y_test.index)

    return {
        "model_name": model_name,
        "target_col": target_col,
        "model": model,
        "feature_cols": feature_cols,
        "model_metrics": model_metrics,
        "naive_t1_metrics": naive_t1_metrics,
        "naive_t24_metrics": naive_t24_metrics,
        "baseline_metrics": baseline_metrics,
        "mae_improvement_pct": mae_improvement_pct,
        "rmse_improvement_pct": rmse_improvement_pct,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "test_results_df": test_results_df,
        "test_start": str(y_test.index[0]),
        "test_end": str(y_test.index[-1]),
    }


def train_all_models(
    aligned_csv_path: str = DEFAULT_ALIGNED_OUTPUT,
    save: bool = True
) -> Dict[str, Any]:
    """
    Train both Solar and Load forecasting models, evaluate against baselines, and persist models.
    
    Args:
        aligned_csv_path (str): Path to aligned dataset CSV.
        save (bool): If True, serializes models and metrics to disk.
        
    Returns:
        Dict[str, Any]: Comprehensive training and evaluation payload for both models.
    """
    # Ensure aligned dataset covers full range
    if not os.path.isabs(aligned_csv_path):
        aligned_csv_path = os.path.join(PROJECT_ROOT, aligned_csv_path)
    aligned_csv_path = os.path.abspath(aligned_csv_path)
    if not os.path.exists(aligned_csv_path) or os.path.getsize(aligned_csv_path) < 1000:
        build_aligned_dataset(start_date="2023-01-01", end_date="2023-12-31", output_path=aligned_csv_path)

    df = pd.read_csv(aligned_csv_path, index_col=0, parse_dates=True)
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    solar_res = train_and_evaluate_forecaster(df, target_col="solar_pu", model_name="Solar Forecaster (p.u.)")
    load_res = train_and_evaluate_forecaster(df, target_col="load_pu", model_name="Load Forecaster (p.u.)")

    summary_metrics = {
        "solar": {
            "model_metrics": solar_res["model_metrics"],
            "naive_metrics": solar_res["baseline_metrics"],
            "mae_improvement_pct": solar_res["mae_improvement_pct"],
            "rmse_improvement_pct": solar_res["rmse_improvement_pct"],
            "train_samples": solar_res["train_samples"],
            "test_samples": solar_res["test_samples"],
            "test_start": solar_res["test_start"],
            "test_end": solar_res["test_end"],
        },
        "load": {
            "model_metrics": load_res["model_metrics"],
            "naive_metrics": load_res["baseline_metrics"],
            "mae_improvement_pct": load_res["mae_improvement_pct"],
            "rmse_improvement_pct": load_res["rmse_improvement_pct"],
            "train_samples": load_res["train_samples"],
            "test_samples": load_res["test_samples"],
            "test_start": load_res["test_start"],
            "test_end": load_res["test_end"],
        },
        "engine_used": "LightGBM" if HAS_LIGHTGBM else "Pure-Python Gradient Ridge"
    }

    if save:
        ensure_model_dir()
        joblib.dump({
            "model": solar_res["model"],
            "feature_cols": solar_res["feature_cols"]
        }, SOLAR_MODEL_PATH)
        
        joblib.dump({
            "model": load_res["model"],
            "feature_cols": load_res["feature_cols"]
        }, LOAD_MODEL_PATH)
        
        # Save summary metrics and evaluation sample
        joblib.dump({
            "summary_metrics": summary_metrics,
            "solar_test_results": solar_res["test_results_df"],
            "load_test_results": load_res["test_results_df"]
        }, METRICS_PATH)

    return {
        "solar": solar_res,
        "load": load_res,
        "summary": summary_metrics
    }


def load_saved_models_and_metrics() -> Optional[Dict[str, Any]]:
    """
    Load saved models and cached evaluation metrics without retraining.
    
    Returns:
        Optional[Dict[str, Any]]: Cached payload or None if files don't exist.
    """
    if not (os.path.exists(SOLAR_MODEL_PATH) and os.path.exists(LOAD_MODEL_PATH) and os.path.exists(METRICS_PATH)):
        return None

    solar_bundle = joblib.load(SOLAR_MODEL_PATH)
    load_bundle = joblib.load(LOAD_MODEL_PATH)
    metrics_bundle = joblib.load(METRICS_PATH)

    return {
        "solar_model": solar_bundle["model"],
        "solar_features": solar_bundle["feature_cols"],
        "load_model": load_bundle["model"],
        "load_features": load_bundle["feature_cols"],
        "summary": metrics_bundle["summary_metrics"],
        "solar_test_results": metrics_bundle["solar_test_results"],
        "load_test_results": metrics_bundle["load_test_results"],
    }


def get_forecast_chart_data(max_points: int = 168) -> Dict[str, Any]:
    """
    Retrieve formatted forecast vs actual time series payload for frontend plotting (e.g. 7-day 168h window).
    
    Args:
        max_points (int): Maximum number of recent test data points to return.
        
    Returns:
        Dict[str, Any]: Structured time-series and metrics payload.
    """
    saved = load_saved_models_and_metrics()
    if saved is None:
        training_res = train_all_models(save=True)
        solar_df = training_res["solar"]["test_results_df"]
        load_df = training_res["load"]["test_results_df"]
        summary = training_res["summary"]
    else:
        solar_df = saved["solar_test_results"]
        load_df = saved["load_test_results"]
        summary = saved["summary"]

    # Slice to recent window (e.g. last 7 days = 168 hours)
    solar_slice = solar_df.tail(max_points)
    load_slice = load_df.tail(max_points)

    chart_series = []
    for ts in solar_slice.index:
        iso_str = ts.strftime("%Y-%m-%d %H:%M")
        chart_series.append({
            "timestamp": iso_str,
            "solar_actual": round(float(solar_slice.loc[ts, "actual"]), 4),
            "solar_pred": round(float(solar_slice.loc[ts, "predicted"]), 4),
            "solar_naive": round(float(solar_slice.loc[ts, "naive_persistence"]), 4),
            "load_actual": round(float(load_slice.loc[ts, "actual"]), 4) if ts in load_slice.index else 0.0,
            "load_pred": round(float(load_slice.loc[ts, "predicted"]), 4) if ts in load_slice.index else 0.0,
            "load_naive": round(float(load_slice.loc[ts, "naive_persistence"]), 4) if ts in load_slice.index else 0.0,
        })

    return {
        "summary": summary,
        "points": chart_series,
        "count": len(chart_series)
    }
