"""Read-only telemetry ingestion with drift detection and mock fallback."""

from __future__ import annotations

import random
from datetime import datetime, timezone

import httpx

from backend.app.config import Settings, get_settings
from backend.app.schemas import TelemetryReading, TelemetryStatus
from src.grid import load_cigre_network


def calculate_forecast_drift(actual_mw: float, forecast_mw: float) -> float:
    """Return the specified relative forecast error, protected near zero."""
    if actual_mw < 0 or forecast_mw < 0:
        raise ValueError("Power values must be non-negative")
    return abs(actual_mw - forecast_mw) / (forecast_mw + 1e-5)


class TelemetryManager:
    """Fetch the latest read-only telemetry or return a deterministic mock."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        network = load_cigre_network()
        pv_mask = network["sgen"]["type"].astype(str).str.upper().str.contains("PV|SOLAR")
        self.mock_solar_capacity_mw = float(network.sgen.loc[pv_mask, "p_mw"].clip(lower=0).sum())
        self.mock_load_reference_mw = float(network.load.p_mw.clip(lower=0).sum())

    def _status(
        self,
        reading: TelemetryReading,
        forecast_solar_mw: float,
        *,
        used_fallback: bool = False,
        error: str | None = None,
        now: datetime | None = None,
    ) -> TelemetryStatus:
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        age_seconds = max(0.0, (checked_at - reading.timestamp).total_seconds())
        stale = age_seconds > self.settings.telemetry_stale_after_seconds
        drift = calculate_forecast_drift(reading.solar_mw, forecast_solar_mw)
        return TelemetryStatus(
            reading=reading,
            forecast_solar_mw=forecast_solar_mw,
            drift=drift,
            requires_replan=drift > self.settings.replan_drift_threshold or stale,
            is_stale=stale,
            used_fallback=used_fallback,
            error=error,
        )

    def mock_status(self, error: str | None = None) -> TelemetryStatus:
        """Generate reproducible development telemetry and a matching forecast."""
        generator = random.Random(self.settings.telemetry_mock_seed)
        solar_forecast = round(
            self.mock_solar_capacity_mw * (0.55 + generator.random() * 0.35), 4
        )
        solar_actual = round(solar_forecast * (0.97 + generator.random() * 0.06), 3)
        reading = TelemetryReading(
            timestamp=datetime.now(timezone.utc),
            solar_mw=solar_actual,
            load_mw=round(
                self.mock_load_reference_mw * (0.75 + generator.random() * 0.3), 3
            ),
            source="mock",
        )
        return self._status(
            reading,
            solar_forecast,
            used_fallback=True,
            error=error,
        )

    async def get_status(self) -> TelemetryStatus:
        """Fetch configured telemetry; fall back safely for any feed failure."""
        if not self.settings.grid_api_url:
            return self.mock_status()

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.telemetry_timeout_seconds
            ) as client:
                response = await client.get(self.settings.grid_api_url)
                response.raise_for_status()
                payload = response.json()

            reading = TelemetryReading.model_validate(
                {
                    "timestamp": payload.get("timestamp", datetime.now(timezone.utc)),
                    "solar_mw": payload["solar_mw"],
                    "load_mw": payload["load_mw"],
                    "source": payload.get("source", "grid_api"),
                }
            )
            forecast = float(payload["forecast_solar_mw"])
            if forecast < 0:
                raise ValueError("forecast_solar_mw must be non-negative")
            return self._status(reading, forecast)
        except Exception as exc:
            return self.mock_status(error=f"Telemetry feed unavailable: {exc}")