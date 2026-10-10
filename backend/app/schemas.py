"""Shared, validated data contracts for the Update1 service modules."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryReading(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    solar_mw: float = Field(ge=0)
    load_mw: float = Field(ge=0)
    source: str = "mock"


class TelemetryStatus(BaseModel):
    reading: TelemetryReading
    forecast_solar_mw: float = Field(ge=0)
    drift: float = Field(ge=0)
    requires_replan: bool
    is_stale: bool = False
    used_fallback: bool = False
    error: str | None = None


class ElementViolation(BaseModel):
    element_type: Literal["bus", "line", "transformer", "grid"]
    element_id: int
    violation_type: str
    actual_value: float | None = None
    limit_value: float | None = None
    unit: str
    message: str


class SolverResult(BaseModel):
    converged: bool
    is_safe: bool
    min_voltage_pu: float | None = None
    max_voltage_pu: float | None = None
    max_line_loading_percent: float | None = None
    max_transformer_loading_percent: float | None = None
    bus_voltages_pu: dict[int, float] = Field(default_factory=dict)
    line_loadings_percent: dict[int, float] = Field(default_factory=dict)
    violations: list[ElementViolation] = Field(default_factory=list)
    error: str | None = None


class MpcStepResult(BaseModel):
    step: int = Field(ge=1, le=8)
    timestamp: datetime
    state_of_charge_mwh: float = Field(ge=0)
    solar_forecast_mw: float = Field(ge=0)
    load_forecast_mw: float = Field(ge=0)
    curtailment_fraction: float = Field(ge=0, le=1)
    battery_charge_mw: float = Field(ge=0)
    battery_discharge_mw: float = Field(ge=0)
    load_shed_mw: float = Field(ge=0)
    solver: SolverResult
    surrogate_used: bool = False
    surrogate_fallback_reason: str | None = None


class MpcPlan(BaseModel):
    run_id: str
    created_at: datetime = Field(default_factory=utc_now)
    horizon_steps: int = Field(default=8, ge=1, le=8)
    step_minutes: int = Field(default=15, gt=0)
    initial_state_of_charge_mwh: float = Field(ge=0)
    final_state_of_charge_mwh: float = Field(ge=0)
    requires_replan: bool = False
    fully_resolved: bool
    steps: list[MpcStepResult]
    explanation: str


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    audience_mode: Literal["operator", "executive"] = "operator"


class ForecastPoint(BaseModel):
    timestamp: datetime | None = None
    solar_mw: float = Field(ge=0)
    load_mw: float = Field(ge=0)


class SolverRequest(BaseModel):
    solar_mw: float = Field(ge=0)
    load_mw: float = Field(ge=0)
    curtailment_fraction: float = Field(default=0, ge=0, le=1)
    battery_charge_mw: float = Field(default=0, ge=0, le=2)
    battery_discharge_mw: float = Field(default=0, ge=0, le=2)
    load_shed_mw: float = Field(default=0, ge=0)


class MpcPlanRequest(BaseModel):
    forecasts: list[ForecastPoint] = Field(min_length=8, max_length=8)
    initial_state_of_charge_mwh: float = Field(default=2.0, ge=0, le=4)


class SurrogateTrainingRequest(BaseModel):
    sample_count: int = Field(default=32, ge=8, le=250)


class ArtifactExportRequest(BaseModel):
    sample_count: int = Field(default=32, ge=8, le=250)
    initial_state_of_charge_mwh: float = Field(default=2.0, ge=0, le=4)