"""Behavior tests for the additive Update1 backend foundation."""

import asyncio
from datetime import datetime, timedelta, timezone

from backend.app.config import Settings
from backend.app.schemas import TelemetryReading
from backend.app.solver_verifier import SolverVerifier
from backend.app.telemetry_manager import TelemetryManager, calculate_forecast_drift
from backend.app.surrogate import generate_solver_dataset


def test_drift_threshold_requires_replan_only_above_threshold():
    settings = Settings(replan_drift_threshold=0.15)
    manager = TelemetryManager(settings)
    timestamp = datetime.now(timezone.utc)
    forecast = 100.0
    exact_actual = forecast + 0.15 * (forecast + 1e-5)
    reading = TelemetryReading(timestamp=timestamp, solar_mw=exact_actual, load_mw=1)

    exact_threshold = manager._status(reading, forecast_solar_mw=forecast, now=timestamp)
    above_threshold = manager._status(
        reading.model_copy(update={"solar_mw": exact_actual + 0.01}),
        forecast_solar_mw=forecast,
        now=timestamp,
    )

    assert abs(calculate_forecast_drift(exact_actual, forecast) - 0.15) < 1e-12
    assert exact_threshold.requires_replan is False
    assert above_threshold.requires_replan is True


def test_stale_telemetry_requires_replan():
    manager = TelemetryManager(Settings(telemetry_stale_after_seconds=30))
    now = datetime.now(timezone.utc)
    old_reading = TelemetryReading(
        timestamp=now - timedelta(minutes=5), solar_mw=2, load_mw=4
    )

    status = manager._status(old_reading, forecast_solar_mw=2, now=now)

    assert status.is_stale is True
    assert status.requires_replan is True


def test_telemetry_without_endpoint_uses_deterministic_mock():
    manager = TelemetryManager(Settings(telemetry_mock_seed=7))
    first = asyncio.run(manager.get_status())
    second = asyncio.run(manager.get_status())

    assert first.used_fallback is True
    assert first.reading.source == "mock"
    assert first.reading.solar_mw == second.reading.solar_mw
    assert first.reading.load_mw == second.reading.load_mw


def test_solver_runs_cigre_and_reports_measured_constraints():
    result = SolverVerifier().run_power_flow(solar_mw=0.21, load_mw=44.74215)

    assert result.converged is True
    assert result.min_voltage_pu is not None
    assert result.max_voltage_pu is not None
    assert result.is_safe is (not result.violations)
    assert all(0.95 <= value <= 1.05 for value in result.bus_voltages_pu.values())


def test_solver_rejects_invalid_dispatch_inputs():
    try:
        SolverVerifier().run_power_flow(solar_mw=2.0, load_mw=5.0, curtailment_fraction=1.2)
    except ValueError as exc:
        assert "curtailment_fraction" in str(exc)
    else:
        raise AssertionError("Invalid curtailment fraction should be rejected")


def test_solver_dataset_uses_cigre_operating_ranges():
    class RecordingVerifier:
        def __init__(self):
            self.inputs = []

        def run_power_flow(self, **inputs):
            from backend.app.schemas import SolverResult

            self.inputs.append(inputs)
            return SolverResult(
                converged=True,
                is_safe=True,
                bus_voltages_pu={0: 1.0},
                line_loadings_percent={0: 50.0},
            )

    verifier = RecordingVerifier()
    features, voltages, loadings = generate_solver_dataset(8, verifier=verifier)

    assert len(features) == 8
    assert voltages.shape == (8, 1)
    assert loadings.shape == (8, 1)
    assert min(item["load_mw"] for item in verifier.inputs) > 15
    assert max(item["load_mw"] for item in verifier.inputs) > 44


def test_update1_health_telemetry_and_forecast_routes():
    from fastapi.testclient import TestClient
    from api import app

    with TestClient(app) as client:
        health = client.get("/health")
        telemetry = client.get("/api/update1/telemetry")
        forecast = client.get("/api/update1/forecast/horizon?steps=8")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert "timestamp" in health.json()
    assert telemetry.status_code == 200
    assert telemetry.json()["reading"]["source"] == "mock"
    assert forecast.status_code == 200
    assert len(forecast.json()["points"]) == 8
    assert forecast.json()["provenance"]["model_source_resolution_minutes"] == 60


def test_update1_assistant_honors_audience_header_without_provider(monkeypatch):
    import api
    from fastapi.testclient import TestClient

    monkeypatch.setattr(api, "settings", Settings(openrouter_api_key=None))
    with TestClient(api.app) as client:
        response = client.post(
            "/api/update1/assistant/chat",
            json={"message": "What is curtailment?"},
            headers={"X-Audience-Mode": "executive"},
        )

    assert response.status_code == 200
    assert response.json()["audience_mode"] == "executive"
    assert "search_project_knowledge" in response.json()["used_tools"]
    assert response.json()["evidence"]["search_project_knowledge"]["matches"]