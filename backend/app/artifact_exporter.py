"""Atomic export of model, benchmark, training data, and MPC evidence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from backend.app.config import PROJECT_ROOT, Settings, get_settings
from backend.app.forecast_adapter import generate_mpc_forecasts
from backend.app.mpc_engine import MpcEngine
from backend.app.schemas import MpcPlan
from backend.app.solver_verifier import SolverVerifier
from backend.app.surrogate import FEATURE_COLUMNS, PowerFlowSurrogate, generate_solver_dataset


class ArtifactExporter:
    """Write the required evidence bundle without exposing partial files."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def export(
        self,
        *,
        surrogate: PowerFlowSurrogate,
        plan: MpcPlan,
        features: pd.DataFrame,
        voltages: np.ndarray,
        loadings: np.ndarray,
        forecast_provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist benchmark, MPC trace, model bundle, and fixed train/test CSVs."""
        if not surrogate.is_fitted:
            raise ValueError("A trained surrogate is required before exporting")
        if len(features) != len(voltages) or len(features) != len(loadings):
            raise ValueError("Feature and solver-label datasets must have matching lengths")

        root = self.settings.artifacts_dir
        root.mkdir(parents=True, exist_ok=True)
        model_path = root / "surrogate_lgb_v1.pkl"
        benchmark_path = root / "surrogate_vs_solver_benchmarks.json"
        trace_path = root / "mpc_execution_trace_t8.json"
        train_path = root / "train_set.csv"
        test_path = root / "test_set.csv"

        labelled = features.reset_index(drop=True).copy()
        for index in range(voltages.shape[1]):
            labelled[f"bus_{surrogate.bus_ids[index]}_vm_pu"] = voltages[:, index]
        for index in range(loadings.shape[1]):
            labelled[f"line_{surrogate.line_ids[index]}_loading_percent"] = loadings[:, index]
        split = max(1, min(len(labelled) - 1, int(len(labelled) * 0.8)))
        paths = {
            "benchmark": benchmark_path,
            "mpc_trace": trace_path,
            "model": model_path,
            "train_set": train_path,
            "test_set": test_path,
        }

        self._atomic_json(benchmark_path, surrogate.metrics)
        trace = plan.model_dump(mode="json")
        trace["forecast_provenance"] = forecast_provenance or {}
        self._atomic_json(trace_path, trace)
        self._atomic_joblib(model_path, self._surrogate_bundle(surrogate))
        self._atomic_csv(train_path, labelled.iloc[:split])
        self._atomic_csv(test_path, labelled.iloc[split:])
        return {
            "status": "success",
            "run_id": plan.run_id,
            "artifacts": {
                name: self._relative_path(path)
                for name, path in paths.items()
            },
        }

    @staticmethod
    def _surrogate_bundle(model: PowerFlowSurrogate) -> dict[str, Any]:
        return {
            "feature_columns": FEATURE_COLUMNS,
            "voltage_models": model.voltage_models,
            "loading_models": model.loading_models,
            "feature_min": model.feature_min,
            "feature_max": model.feature_max,
            "bus_ids": model.bus_ids,
            "line_ids": model.line_ids,
            "metrics": model.metrics,
        }

    @staticmethod
    def _atomic_write(destination: Path, writer: Any) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            writer(temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def _atomic_json(cls, destination: Path, payload: Any) -> None:
        cls._atomic_write(
            destination,
            lambda temporary: temporary.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            ),
        )

    @classmethod
    def _atomic_csv(cls, destination: Path, frame: pd.DataFrame) -> None:
        cls._atomic_write(destination, lambda temporary: frame.to_csv(temporary, index=False))

    @classmethod
    def _atomic_joblib(cls, destination: Path, payload: Any) -> None:
        cls._atomic_write(destination, lambda temporary: joblib.dump(payload, temporary))

    @staticmethod
    def _relative_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path.resolve())


def generate_evidence_bundle(
    *,
    sample_count: int = 32,
    initial_state_of_charge_mwh: float = 2.0,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Generate a reproducible physical dataset, train, plan, and export it."""
    current_settings = settings or get_settings()
    features, voltages, loadings = generate_solver_dataset(sample_count=sample_count)
    model = PowerFlowSurrogate(current_settings)
    metrics = model.train(
        features,
        voltages,
        loadings,
        voltage_bus_ids=list(range(voltages.shape[1])),
        line_ids=list(range(loadings.shape[1])),
        save_path=current_settings.surrogate_model_path,
    )
    forecast = generate_mpc_forecasts()
    plan = MpcEngine(
        verifier=SolverVerifier(current_settings), surrogate=model
    ).plan(forecast["points"], initial_state_of_charge_mwh=initial_state_of_charge_mwh)
    exported = ArtifactExporter(current_settings).export(
        surrogate=model,
        plan=plan,
        features=features,
        voltages=voltages,
        loadings=loadings,
        forecast_provenance=forecast["provenance"],
    )
    return {**exported, "surrogate_metrics": metrics, "mpc_fully_resolved": plan.fully_resolved}