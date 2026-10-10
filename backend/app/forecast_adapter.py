"""Adapt the existing hourly forecasting models to the quarter-hour MPC API."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from backend.app.config import PROJECT_ROOT
from src.forecast import create_feature_matrix, load_saved_models_and_metrics
from src.grid import load_cigre_network


ALIGNED_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "aligned_solar_load.csv"


def generate_mpc_forecasts(steps: int = 8, step_minutes: int = 15) -> dict[str, Any]:
    """Generate recursive hourly predictions and interpolate to MPC timestamps.

    The forecaster was trained on hourly data; quarter-hour entries are explicit
    linear interpolations and are not represented as a quarter-hour-trained model.
    Per-unit values are mapped to the CIGRE network's current aggregate MW values.
    """
    if not 1 <= steps <= 8:
        raise ValueError("steps must be between 1 and 8")
    if step_minutes != 15:
        raise ValueError("The current MPC contract supports 15-minute steps only")
    if not ALIGNED_DATA_PATH.exists():
        raise FileNotFoundError(f"Aligned training data not found: {ALIGNED_DATA_PATH}")
    saved = load_saved_models_and_metrics()
    if saved is None:
        raise FileNotFoundError("Saved forecast models are required; train models first")

    history = pd.read_csv(ALIGNED_DATA_PATH, index_col=0, parse_dates=True)
    if history.index.tz is not None:
        history.index = history.index.tz_localize(None)
    history = history[["solar_pu", "load_pu"]].dropna().sort_index()
    if len(history) < 25:
        raise ValueError("At least 25 hourly observations are required for lag features")

    history_solar = history["solar_pu"].copy()
    history_load = history["load_pu"].copy()
    last_timestamp = history.index[-1]
    future_hours = math.ceil(steps * step_minutes / 60)
    hourly_predictions: list[dict[str, Any]] = []

    for hour_offset in range(1, future_hours + 1):
        future_timestamp = last_timestamp + pd.Timedelta(hours=hour_offset)
        solar_value = _predict_next(
            history_solar,
            future_timestamp,
            "solar_pu",
            saved["solar_model"],
            saved["solar_features"],
        )
        load_value = _predict_next(
            history_load,
            future_timestamp,
            "load_pu",
            saved["load_model"],
            saved["load_features"],
        )
        history_solar.loc[future_timestamp] = solar_value
        history_load.loc[future_timestamp] = load_value
        hourly_predictions.append(
            {
                "timestamp": future_timestamp,
                "solar_pu": solar_value,
                "load_pu": load_value,
            }
        )

    network = load_cigre_network()
    pv_mask = network.sgen["type"].astype(str).str.upper().str.contains("PV|SOLAR")
    solar_capacity_mw = float(network.sgen.loc[pv_mask, "p_mw"].clip(lower=0).sum())
    load_reference_mw = float(network.load.p_mw.clip(lower=0).sum())
    points: list[dict[str, Any]] = []
    for step in range(1, steps + 1):
        hour_position = step * step_minutes / 60
        left_hour = math.floor(hour_position)
        fraction = hour_position - left_hour
        left_solar = float(history["solar_pu"].iloc[-1]) if left_hour == 0 else hourly_predictions[left_hour - 1]["solar_pu"]
        left_load = float(history["load_pu"].iloc[-1]) if left_hour == 0 else hourly_predictions[left_hour - 1]["load_pu"]
        right_solar = hourly_predictions[min(left_hour, future_hours - 1)]["solar_pu"]
        right_load = hourly_predictions[min(left_hour, future_hours - 1)]["load_pu"]
        solar_pu = max(0.0, left_solar + (right_solar - left_solar) * fraction)
        load_pu = max(0.0, left_load + (right_load - left_load) * fraction)
        points.append(
            {
                "step": step,
                "timestamp": (last_timestamp + pd.Timedelta(minutes=step * step_minutes)).isoformat(),
                "solar_pu": solar_pu,
                "load_pu": load_pu,
                "solar_mw": solar_pu * solar_capacity_mw,
                "load_mw": load_pu * load_reference_mw,
            }
        )

    return {
        "points": points,
        "provenance": {
            "model_source_resolution_minutes": 60,
            "requested_resolution_minutes": step_minutes,
            "quarter_hour_method": "linear interpolation between recursive hourly model predictions",
            "training_data_last_timestamp": last_timestamp.isoformat(),
            "solar_mw_scale": "CIGRE aggregate static-generator base dispatch",
            "load_mw_scale": "CIGRE aggregate base load",
            "network": "CIGRE MV with DER",
        },
    }


def _predict_next(
    history: pd.Series,
    timestamp: pd.Timestamp,
    target: str,
    model: Any,
    feature_names: list[str],
) -> float:
    series = history.rename(target).to_frame()
    series.loc[timestamp, target] = np.nan
    features, _, _ = create_feature_matrix(series, target_col=target, drop_na=False)
    row = features.loc[[timestamp], feature_names]
    return float(max(0.0, model.predict(row)[0]))