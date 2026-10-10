"""Eight-step receding-horizon controller with physical solver guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.app.schemas import MpcPlan, MpcStepResult, SolverResult, TelemetryStatus
from backend.app.solver_verifier import SolverVerifier
from backend.app.surrogate import PowerFlowSurrogate


@dataclass(frozen=True)
class BatteryLimits:
    capacity_mwh: float = 4.0
    max_charge_mw: float = 2.0
    max_discharge_mw: float = 2.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    step_hours: float = 0.25


class MpcEngine:
    """Screen bounded controls and physically verify every selected step."""

    def __init__(
        self,
        verifier: SolverVerifier | None = None,
        surrogate: PowerFlowSurrogate | None = None,
        battery: BatteryLimits | None = None,
    ) -> None:
        self.verifier = verifier or SolverVerifier()
        self.surrogate = surrogate
        self.battery = battery or BatteryLimits()
        if self.battery.capacity_mwh <= 0 or self.battery.step_hours <= 0:
            raise ValueError("Battery capacity and step duration must be positive")
        if not 0 < self.battery.charge_efficiency <= 1 or not 0 < self.battery.discharge_efficiency <= 1:
            raise ValueError("Battery efficiencies must be in (0, 1]")

    def plan(
        self,
        forecasts: list[dict[str, Any]],
        *,
        initial_state_of_charge_mwh: float = 2.0,
        telemetry: TelemetryStatus | None = None,
    ) -> MpcPlan:
        """Plan the next eight 15-minute steps; SoC is tracked as energy in MWh."""
        if len(forecasts) != 8:
            raise ValueError("MPC requires exactly eight 15-minute forecast steps")
        if not 0 <= initial_state_of_charge_mwh <= self.battery.capacity_mwh:
            raise ValueError("Initial state of charge must be within battery capacity")

        state_of_charge = initial_state_of_charge_mwh
        step_results: list[MpcStepResult] = []
        all_safe = True
        now = datetime.now(timezone.utc)

        for index, forecast in enumerate(forecasts, start=1):
            solar = float(forecast["solar_mw"])
            load = float(forecast["load_mw"])
            if solar < 0 or load < 0:
                raise ValueError("Forecast power values must be non-negative")
            timestamp = forecast.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if timestamp is None:
                timestamp = now + timedelta(minutes=15 * (index - 1))

            candidates = self._candidates(load, state_of_charge)
            selected, surrogate_used, fallback_reason = self._screen(candidates, solar, load)
            solver_result = self.verifier.run_power_flow(
                solar_mw=solar,
                load_mw=load,
                **selected,
            )

            if not solver_result.is_safe:
                selected, solver_result = self._physical_fallback(candidates, solar, load)

            state_of_charge = self._advance_soc(
                state_of_charge,
                selected["battery_charge_mw"],
                selected["battery_discharge_mw"],
            )
            all_safe = all_safe and solver_result.is_safe
            step_results.append(
                MpcStepResult(
                    step=index,
                    timestamp=timestamp,
                    state_of_charge_mwh=state_of_charge,
                    solar_forecast_mw=solar,
                    load_forecast_mw=load,
                    curtailment_fraction=selected["curtailment_fraction"],
                    battery_charge_mw=selected["battery_charge_mw"],
                    battery_discharge_mw=selected["battery_discharge_mw"],
                    load_shed_mw=selected["load_shed_mw"],
                    solver=solver_result,
                    surrogate_used=surrogate_used,
                    surrogate_fallback_reason=fallback_reason,
                )
            )

        return MpcPlan(
            run_id=str(uuid4()),
            horizon_steps=8,
            step_minutes=15,
            initial_state_of_charge_mwh=initial_state_of_charge_mwh,
            final_state_of_charge_mwh=state_of_charge,
            requires_replan=telemetry.requires_replan if telemetry else False,
            fully_resolved=all_safe,
            steps=step_results,
            explanation=(
                "All eight steps passed AC solver verification."
                if all_safe
                else "One or more steps remain outside operating limits after the configured fallback actions."
            ),
        )

    def _candidates(self, load: float, soc: float) -> list[dict[str, float]]:
        dt = self.battery.step_hours
        charge_bound = min(
            self.battery.max_charge_mw,
            (self.battery.capacity_mwh - soc) / (dt * self.battery.charge_efficiency),
        )
        discharge_bound = min(
            self.battery.max_discharge_mw,
            soc * self.battery.discharge_efficiency / dt,
        )
        candidates = [self._control()]
        candidates.extend(
            self._control(curtailment_fraction=value)
            for value in (0.25, 0.5, 0.75, 1.0)
        )
        candidates.extend(
            self._control(battery_charge_mw=min(value, charge_bound))
            for value in (0.5, 1.0, 2.0)
            if charge_bound > 0
        )
        candidates.extend(
            self._control(battery_discharge_mw=min(value, discharge_bound))
            for value in (0.5, 1.0, 2.0)
            if discharge_bound > 0
        )
        candidates.extend(
            self._control(load_shed_mw=min(load * fraction, load * 0.25))
            for fraction in (0.1, 0.25)
            if load > 0
        )
        unique: dict[tuple[float, ...], dict[str, float]] = {}
        for candidate in candidates:
            unique[tuple(candidate.values())] = candidate
        return list(unique.values())

    @staticmethod
    def _control(**changes: float) -> dict[str, float]:
        control = {
            "curtailment_fraction": 0.0,
            "battery_charge_mw": 0.0,
            "battery_discharge_mw": 0.0,
            "load_shed_mw": 0.0,
        }
        control.update(changes)
        return control

    def _screen(
        self,
        candidates: list[dict[str, float]],
        solar: float,
        load: float,
    ) -> tuple[dict[str, float], bool, str | None]:
        if self.surrogate is None or not self.surrogate.is_fitted:
            return candidates[0], False, "No trained surrogate; solver verification required"

        ranked: list[tuple[float, dict[str, float]]] = []
        fallback_reasons: list[str] = []
        for control in candidates:
            prediction = self.surrogate.predict_fast(
                {"solar_mw": solar, "load_mw": load, **control}
            )
            if prediction.get("status") != "PREDICTION":
                fallback_reasons.append(str(prediction.get("reason", "OOD input")))
                continue
            predicted_cost = (
                control["curtailment_fraction"] * 5.0
                + (control["battery_charge_mw"] + control["battery_discharge_mw"]) * 0.2
                + control["load_shed_mw"] * 20.0
            )
            ranked.append((self._prediction_penalty(prediction) + predicted_cost, control))

        if fallback_reasons:
            return candidates[0], False, fallback_reasons[0]
        if not ranked:
            return candidates[0], False, "No usable surrogate prediction"
        ranked.sort(key=lambda entry: entry[0])
        return ranked[0][1], True, None

    def _prediction_penalty(self, prediction: dict[str, Any]) -> float:
        voltages = prediction["bus_voltages_pu"].values()
        loadings = prediction["line_loadings_percent"].values()
        return sum(
            max(0.0, self.verifier.settings.voltage_min_pu - value) * 1000
            + max(0.0, value - self.verifier.settings.voltage_max_pu) * 1000
            for value in voltages
        ) + sum(
            max(0.0, value - self.verifier.settings.max_line_loading_percent) * 5
            for value in loadings
        )

    def _physical_fallback(
        self,
        candidates: list[dict[str, float]],
        solar: float,
        load: float,
    ) -> tuple[dict[str, float], SolverResult]:
        ordered: list[dict[str, float]] = []
        for curtailment in (1.0, 0.75, 0.5, 0.0):
            ordered.extend(
                item for item in candidates
                if item["curtailment_fraction"] == curtailment
                and item["battery_charge_mw"] == 0
                and item["battery_discharge_mw"] == 0
                and item["load_shed_mw"] == 0
            )
        ordered.extend(
            item for item in candidates
            if item not in ordered
            and (item["battery_charge_mw"] > 0 or item["battery_discharge_mw"] > 0)
            and item["load_shed_mw"] == 0
        )
        ordered.extend(item for item in candidates if item not in ordered)

        best_control = ordered[0] if ordered else self._control()
        best_result = self.verifier.run_power_flow(solar_mw=solar, load_mw=load, **best_control)
        for control in ordered:
            result = self.verifier.run_power_flow(solar_mw=solar, load_mw=load, **control)
            if result.is_safe:
                return control, result
            if self._solver_penalty(result) < self._solver_penalty(best_result):
                best_control, best_result = control, result
        return best_control, best_result

    def _solver_penalty(self, result: SolverResult) -> float:
        if not result.converged:
            return float("inf")
        return sum(
            max(0.0, self.verifier.settings.voltage_min_pu - voltage) * 1000
            + max(0.0, voltage - self.verifier.settings.voltage_max_pu) * 1000
            for voltage in result.bus_voltages_pu.values()
        ) + sum(
            max(0.0, loading - self.verifier.settings.max_line_loading_percent) * 5
            for loading in result.line_loadings_percent.values()
        )

    def _advance_soc(self, soc: float, charge_mw: float, discharge_mw: float) -> float:
        next_soc = soc + (
            charge_mw * self.battery.charge_efficiency
            - discharge_mw / self.battery.discharge_efficiency
        ) * self.battery.step_hours
        if next_soc < -1e-9 or next_soc > self.battery.capacity_mwh + 1e-9:
            raise ValueError("Candidate dispatch would violate battery SoC limits")
        return min(self.battery.capacity_mwh, max(0.0, next_soc))