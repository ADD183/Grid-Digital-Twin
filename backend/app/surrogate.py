"""LightGBM screening model with training-range OOD protection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.app.config import Settings, get_settings
from backend.app.solver_verifier import SolverVerifier
from src.grid import load_cigre_network


FEATURE_COLUMNS = (
    "solar_mw",
    "load_mw",
    "curtailment_fraction",
    "battery_charge_mw",
    "battery_discharge_mw",
    "load_shed_mw",
)


class PowerFlowSurrogate:
    """Predict bus voltage and line loading for candidate screening only."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.voltage_models: list[LGBMRegressor] = []
        self.loading_models: list[LGBMRegressor] = []
        self.feature_min: dict[str, float] = {}
        self.feature_max: dict[str, float] = {}
        self.bus_ids: list[int] = []
        self.line_ids: list[int] = []
        self.metrics: dict[str, Any] = {}
        self.is_fitted = False

    def train(
        self,
        X: pd.DataFrame,
        Y_v: np.ndarray,
        Y_i: np.ndarray,
        *,
        voltage_bus_ids: list[int] | None = None,
        line_ids: list[int] | None = None,
        validation_fraction: float = 0.2,
        save_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Train per-output LightGBM regressors and report held-out safety metrics."""
        features = X.loc[:, FEATURE_COLUMNS].astype(float).reset_index(drop=True)
        voltages = np.asarray(Y_v, dtype=float)
        loadings = np.asarray(Y_i, dtype=float)
        if len(features) < 5 or len(features) != len(voltages) or len(features) != len(loadings):
            raise ValueError("X, Y_v, and Y_i must have matching lengths of at least five")
        if voltages.ndim != 2 or loadings.ndim != 2:
            raise ValueError("Y_v and Y_i must be two-dimensional output matrices")
        if not 0 < validation_fraction < 0.5:
            raise ValueError("validation_fraction must be between 0 and 0.5")

        split = max(2, min(len(features) - 1, int(len(features) * (1 - validation_fraction))))
        self.feature_min = features.iloc[:split].min().to_dict()
        self.feature_max = features.iloc[:split].max().to_dict()
        self.voltage_models = self._fit_outputs(features.iloc[:split], voltages[:split])
        self.loading_models = self._fit_outputs(features.iloc[:split], loadings[:split])
        self.bus_ids = voltage_bus_ids or list(range(voltages.shape[1]))
        self.line_ids = line_ids or list(range(loadings.shape[1]))
        if len(self.bus_ids) != voltages.shape[1] or len(self.line_ids) != loadings.shape[1]:
            raise ValueError("Output element IDs must match their target matrix widths")

        predicted_v = self._predict_matrix(self.voltage_models, features.iloc[split:])
        predicted_i = self._predict_matrix(self.loading_models, features.iloc[split:])
        actual_v = voltages[split:]
        actual_i = loadings[split:]
        actual_unsafe = np.any(
            (actual_v < self.settings.voltage_min_pu)
            | (actual_v > self.settings.voltage_max_pu),
            axis=1,
        ) | np.any(actual_i > self.settings.max_line_loading_percent, axis=1)
        predicted_safe = np.all(
            (predicted_v >= self.settings.voltage_min_pu)
            & (predicted_v <= self.settings.voltage_max_pu),
            axis=1,
        ) & np.all(predicted_i <= self.settings.max_line_loading_percent, axis=1)
        unsafe_count = int(actual_unsafe.sum())
        false_safe_count = int(np.sum(actual_unsafe & predicted_safe))

        self.metrics = {
            "train_samples": int(split),
            "validation_samples": int(len(features) - split),
            "voltage_mae_pu": float(mean_absolute_error(actual_v, predicted_v)),
            "voltage_rmse_pu": float(np.sqrt(mean_squared_error(actual_v, predicted_v))),
            "line_loading_mae_percent": float(mean_absolute_error(actual_i, predicted_i)),
            "line_loading_rmse_percent": float(np.sqrt(mean_squared_error(actual_i, predicted_i))),
            "false_safe_rate": false_safe_count / unsafe_count if unsafe_count else None,
            "unsafe_validation_samples": unsafe_count,
            "false_safe_samples": false_safe_count,
            "voltage_limits_pu": [
                self.settings.voltage_min_pu,
                self.settings.voltage_max_pu,
            ],
            "line_loading_limit_percent": self.settings.max_line_loading_percent,
        }
        self.is_fitted = True
        if save_path is not None:
            self.save(save_path)
        return self.metrics.copy()

    @staticmethod
    def _fit_outputs(X: pd.DataFrame, targets: np.ndarray) -> list[LGBMRegressor]:
        models: list[LGBMRegressor] = []
        for output_index in range(targets.shape[1]):
            model = LGBMRegressor(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=5,
                num_leaves=15,
                random_state=42,
                n_jobs=1,
                verbosity=-1,
            )
            model.fit(X, targets[:, output_index])
            models.append(model)
        return models

    @staticmethod
    def _predict_matrix(models: list[LGBMRegressor], X: pd.DataFrame) -> np.ndarray:
        if not models:
            raise RuntimeError("Surrogate has no trained output models")
        return np.column_stack([model.predict(X) for model in models])

    def predict_fast(self, x_input: dict[str, float]) -> dict[str, Any]:
        """Predict candidate grid state, or demand solver fallback for OOD input."""
        if not self.is_fitted:
            return {"status": "OOD_FALLBACK_REQUIRED", "reason": "Surrogate is not trained"}
        missing = [name for name in FEATURE_COLUMNS if name not in x_input]
        if missing:
            return {
                "status": "OOD_FALLBACK_REQUIRED",
                "reason": f"Missing features: {', '.join(missing)}",
            }
        row = {name: float(x_input[name]) for name in FEATURE_COLUMNS}
        for name, value in row.items():
            if not np.isfinite(value) or value < self.feature_min[name] or value > self.feature_max[name]:
                return {
                    "status": "OOD_FALLBACK_REQUIRED",
                    "reason": f"{name}={value} is outside the fitted training range",
                }

        frame = pd.DataFrame([row], columns=FEATURE_COLUMNS)
        voltage_values = self._predict_matrix(self.voltage_models, frame)[0]
        loading_values = self._predict_matrix(self.loading_models, frame)[0]

        # Vectorized margin calculation (strict signed distance to limits)
        # Undervoltage margin: min(V) - 0.95 (e.g. 0.868 - 0.95 = -0.082)
        # Overvoltage margin: 1.05 - max(V)
        # Loading margin: (100.0 - max(loading)) / 100.0
        v_min_actual = float(np.min(voltage_values))
        v_max_actual = float(np.max(voltage_values))
        max_line_loading = float(np.max(loading_values))

        v_undervoltage_margin = v_min_actual - self.settings.voltage_min_pu
        v_overvoltage_margin = self.settings.voltage_max_pu - v_max_actual
        line_loading_margin = (self.settings.max_line_loading_percent - max_line_loading) / 100.0
        
        raw_margin = float(min(v_undervoltage_margin, v_overvoltage_margin, line_loading_margin))
        
        # Apply strict +0.0100 p.u. safety guard band shift
        guard_band = 0.0100
        guarded_margin = float(raw_margin - guard_band)

        # Estimate prediction disagreement across ensemble trees/models
        try:
            if self.voltage_models:
                stds = []
                for m in self.voltage_models:
                    if hasattr(m, "booster_"):
                        p1 = float(m.predict(frame, num_iteration=max(1, m.n_estimators // 2))[0])
                        p2 = float(m.predict(frame, num_iteration=m.n_estimators)[0])
                        stds.append(abs(p2 - p1))
                disagreement = float(np.max(stds)) if stds else 0.0
            else:
                disagreement = 0.0
        except Exception:
            disagreement = 0.0

        # OOD fallback if ensemble disagreement exceeds 0.0150 p.u.
        if disagreement > 0.0150:
            return {
                "status": "OOD_FALLBACK_REQUIRED",
                "reason": f"Ensemble disagreement {disagreement:.4f} exceeds ceiling 0.0150 p.u.",
                "disagreement": disagreement,
            }

        # Safe only if guarded margin >= 0 (raw margin >= guard_band) and loading within bounds
        safe = bool(
            raw_margin >= guard_band
            and np.all(voltage_values >= (self.settings.voltage_min_pu + guard_band))
            and np.all(voltage_values <= (self.settings.voltage_max_pu - guard_band))
            and np.all(loading_values <= self.settings.max_line_loading_percent)
        )

        return {
            "status": "PREDICTION",
            "is_safe": safe,
            "raw_margin": round(raw_margin, 5),
            "guarded_margin": round(guarded_margin, 5),
            "min_margin": round(guarded_margin, 5),
            "guard_band": guard_band,
            "disagreement": round(disagreement, 5),
            "bus_voltages_pu": dict(zip(self.bus_ids, voltage_values.tolist())),
            "line_loadings_percent": dict(zip(self.line_ids, loading_values.tolist())),
        }

    def save(self, path: str | Path) -> Path:
        """Persist model state and its feature/output metadata."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "feature_columns": FEATURE_COLUMNS,
                "voltage_models": self.voltage_models,
                "loading_models": self.loading_models,
                "feature_min": self.feature_min,
                "feature_max": self.feature_max,
                "bus_ids": self.bus_ids,
                "line_ids": self.line_ids,
                "metrics": self.metrics,
            },
            destination,
        )
        return destination

    @classmethod
    def load(cls, path: str | Path, settings: Settings | None = None) -> "PowerFlowSurrogate":
        """Load a saved surrogate bundle and restore its training metadata."""
        bundle = joblib.load(path)
        if tuple(bundle.get("feature_columns", ())) != FEATURE_COLUMNS:
            raise ValueError("Surrogate feature schema does not match this application")
        model = cls(settings)
        model.voltage_models = bundle["voltage_models"]
        model.loading_models = bundle["loading_models"]
        model.feature_min = bundle["feature_min"]
        model.feature_max = bundle["feature_max"]
        model.bus_ids = bundle["bus_ids"]
        model.line_ids = bundle["line_ids"]
        model.metrics = bundle["metrics"]
        model.is_fitted = True
        return model


def generate_solver_dataset(
    sample_count: int = 80,
    *,
    seed: int = 42,
    verifier: SolverVerifier | None = None,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Create reproducible CIGRE labels by evaluating operating points physically."""
    if sample_count < 8:
        raise ValueError("sample_count must be at least eight")
    rng = np.random.default_rng(seed)
    solver = verifier or SolverVerifier()
    reference_net = load_cigre_network()
    pv_mask = reference_net.sgen["type"].astype(str).str.upper().str.contains("PV|SOLAR")
    solar_reference_mw = float(reference_net.sgen.loc[pv_mask, "p_mw"].clip(lower=0).sum())
    load_reference_mw = float(reference_net.load.p_mw.clip(lower=0).sum())
    baseline = {
        "solar_mw": 0.0,
        "load_mw": 0.8 * load_reference_mw,
        "curtailment_fraction": 0.0,
        "battery_charge_mw": 0.0,
        "battery_discharge_mw": 0.0,
        "load_shed_mw": 0.0,
    }
    boundary_scenarios = [
        baseline,
        {**baseline, "solar_mw": 2.0 * solar_reference_mw},
        {**baseline, "load_mw": 0.35 * load_reference_mw},
        {**baseline, "load_mw": 1.25 * load_reference_mw},
        {**baseline, "solar_mw": solar_reference_mw, "curtailment_fraction": 1.0},
        {**baseline, "battery_charge_mw": 2.0},
        {**baseline, "battery_discharge_mw": 2.0},
        {
            **baseline,
            "load_mw": 1.25 * load_reference_mw,
            "load_shed_mw": 0.25 * 1.25 * load_reference_mw,
        },
    ]
    records: list[dict[str, float]] = []
    voltage_labels: list[list[float]] = []
    loading_labels: list[list[float]] = []
    for sample_index in range(sample_count):
        if sample_index < len(boundary_scenarios):
            inputs = boundary_scenarios[sample_index].copy()
        else:
            inputs = {
                "solar_mw": float(rng.uniform(0.0, max(0.1, 2.0 * solar_reference_mw))),
                "load_mw": float(rng.uniform(0.35 * load_reference_mw, 1.25 * load_reference_mw)),
                "curtailment_fraction": float(rng.choice([0.0, 0.25, 0.5, 0.75, 1.0])),
                "battery_charge_mw": float(rng.choice([0.0, 0.5, 1.0, 1.5, 2.0])),
                "battery_discharge_mw": float(rng.choice([0.0, 0.5, 1.0, 1.5, 2.0])),
                "load_shed_mw": float(rng.choice([0.0, 0.1, 0.25]) * load_reference_mw),
            }
            if inputs["battery_charge_mw"] and inputs["battery_discharge_mw"]:
                inputs["battery_discharge_mw"] = 0.0
        result = solver.run_power_flow(**inputs)
        if not result.converged:
            continue
        records.append(inputs)
        voltage_labels.append([result.bus_voltages_pu[key] for key in sorted(result.bus_voltages_pu)])
        loading_labels.append([result.line_loadings_percent[key] for key in sorted(result.line_loadings_percent)])

    if len(records) < 8:
        raise RuntimeError("Too few solver samples converged to train a surrogate")
    features = pd.DataFrame(records, columns=FEATURE_COLUMNS)
    return features, np.asarray(voltage_labels), np.asarray(loading_labels)