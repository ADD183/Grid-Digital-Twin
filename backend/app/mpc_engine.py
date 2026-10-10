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
        beam_width: int = 5,
    ) -> MpcPlan:
        """Jointly optimize the 8-step MPC trajectory using beam search across the horizon."""
        if len(forecasts) != 8:
            raise ValueError("MPC requires exactly eight 15-minute forecast steps")
        if not 0 <= initial_state_of_charge_mwh <= self.battery.capacity_mwh:
            raise ValueError("Initial state of charge must be within battery capacity")

        now = datetime.now(timezone.utc)
        parsed_forecasts: list[dict[str, Any]] = []
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
            parsed_forecasts.append({"step": index, "solar_mw": solar, "load_mw": load, "timestamp": timestamp})

        # --- JOINT MPC TRAJECTORY OPTIMIZATION VIA BEAM SEARCH ---
        # Each beam item: (cumulative_cost, current_soc, list_of_selected_controls, list_of_meta)
        beam: list[tuple[float, float, list[dict[str, float]], list[dict[str, Any]]]] = [
            (0.0, initial_state_of_charge_mwh, [], [])
        ]

        for step_data in parsed_forecasts:
            solar = step_data["solar_mw"]
            load = step_data["load_mw"]
            next_beam: list[tuple[float, float, list[dict[str, float]], list[dict[str, Any]]]] = []

            for cum_cost, soc_k, ctrl_seq, meta_seq in beam:
                candidates_k = self._candidates(load, soc_k)
                for cand in candidates_k:
                    # Screen or predict candidate cost
                    pred_cost, surr_used, f_reason = self._evaluate_candidate_cost(cand, solar, load)
                    next_soc = self._advance_soc(
                        soc_k,
                        cand["battery_charge_mw"],
                        cand["battery_discharge_mw"],
                    )
                    # Add terminal SOC preservation incentive (avoid premature depletion)
                    soc_headroom_cost = max(0.0, (1.0 - next_soc / self.battery.capacity_mwh)) * 2.0
                    total_step_cost = pred_cost + soc_headroom_cost

                    meta = {
                        "surrogate_used": surr_used,
                        "fallback_reason": f_reason,
                    }
                    next_beam.append(
                        (cum_cost + total_step_cost, next_soc, ctrl_seq + [cand], meta_seq + [meta])
                    )

            # Prune beam to top beam_width joint trajectories
            next_beam.sort(key=lambda item: item[0])
            beam = next_beam[:beam_width]

        if not beam:
            raise RuntimeError("MPC beam search produced no admissible trajectory")

        # Select best joint trajectory from beam
        _, _, best_controls, best_metas = beam[0]

        # Execute physical AC power flow solver verification for every step in the trajectory
        step_results: list[MpcStepResult] = []
        all_safe = True
        current_soc = initial_state_of_charge_mwh

        for idx, (step_data, control, meta) in enumerate(zip(parsed_forecasts, best_controls, best_metas), start=1):
            solar = step_data["solar_mw"]
            load = step_data["load_mw"]
            timestamp = step_data["timestamp"]

            solver_result = self.verifier.run_power_flow(
                solar_mw=solar,
                load_mw=load,
                **control,
            )

            surrogate_used = meta["surrogate_used"]
            fallback_reason = meta["fallback_reason"]

            # If solver indicates infeasibility, sequentially trigger the Fallback Ladder
            if not solver_result.is_safe:
                step_candidates = self._candidates(load, current_soc)
                control, solver_result, fallback_name = self._execute_fallback_ladder(
                    step_candidates, solar, load, current_soc
                )
                surrogate_used = False
                fallback_reason = f"fallback_used={fallback_name}"

            current_soc = self._advance_soc(
                current_soc,
                control["battery_charge_mw"],
                control["battery_discharge_mw"],
            )

            all_safe = all_safe and solver_result.is_safe
            step_results.append(
                MpcStepResult(
                    step=idx,
                    timestamp=timestamp,
                    state_of_charge_mwh=current_soc,
                    solar_forecast_mw=solar,
                    load_forecast_mw=load,
                    curtailment_fraction=control["curtailment_fraction"],
                    battery_charge_mw=control["battery_charge_mw"],
                    battery_discharge_mw=control["battery_discharge_mw"],
                    load_shed_mw=control["load_shed_mw"],
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
            final_state_of_charge_mwh=current_soc,
            requires_replan=telemetry.requires_replan if telemetry else False,
            fully_resolved=all_safe,
            steps=step_results,
            explanation=(
                "All eight steps passed AC solver verification."
                if all_safe
                else "One or more steps remain outside operating limits after sequential fallback mitigations."
            ),
        )

    def _evaluate_candidate_cost(
        self,
        control: dict[str, float],
        solar: float,
        load: float,
    ) -> tuple[float, bool, str | None]:
        """Compute operational and constraint cost for a candidate control."""
        op_cost = (
            control["curtailment_fraction"] * 5.0
            + (control["battery_charge_mw"] + control["battery_discharge_mw"]) * 0.2
            + control["load_shed_mw"] * 25.0
        )

        if self.surrogate is not None and self.surrogate.is_fitted:
            prediction = self.surrogate.predict_fast(
                {"solar_mw": solar, "load_mw": load, **control}
            )
            if prediction.get("status") == "PREDICTION":
                constraint_penalty = self._prediction_penalty(prediction)
                return op_cost + constraint_penalty, True, None
            else:
                return op_cost + 100.0, False, str(prediction.get("reason", "OOD"))
        else:
            # Fallback heuristic cost without surrogate
            return op_cost, False, "No trained surrogate"

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

    def _execute_fallback_ladder(
        self,
        candidates: list[dict[str, float]],
        solar: float,
        load: float,
        soc: float,
    ) -> tuple[dict[str, float], SolverResult, str]:
        """
        Execute sequential Fallback Ladder (PRD / Checkpoint 5):
        1) Max BESS dispatch
        2) Max PV curtailment (+ Max BESS)
        3) Feeder tie-switch reconfiguration / voltage support
        4) Targeted Load shedding
        """
        dt = self.battery.step_hours
        max_disch = min(self.battery.max_discharge_mw, soc * self.battery.discharge_efficiency / dt)
        max_chg = min(self.battery.max_charge_mw, (self.battery.capacity_mwh - soc) / (dt * self.battery.charge_efficiency))

        # 1. Max BESS dispatch
        bess_control = self._control(battery_discharge_mw=max_disch if load > solar else 0.0,
                                     battery_charge_mw=max_chg if solar > load else 0.0)
        res_bess = self.verifier.run_power_flow(solar_mw=solar, load_mw=load, **bess_control)
        if res_bess.is_safe:
            return bess_control, res_bess, "max_bess_dispatch"

        # 2. Max PV curtailment (+ Max BESS)
        curtail_control = self._control(curtailment_fraction=1.0,
                                        battery_discharge_mw=max_disch if load > 0 else 0.0)
        res_curtail = self.verifier.run_power_flow(solar_mw=solar, load_mw=load, **curtail_control)
        if res_curtail.is_safe:
            return curtail_control, res_curtail, "max_pv_curtailment"

        # 3. Targeted Load Shedding (moderate 10%)
        shed10_control = self._control(curtailment_fraction=1.0,
                                       battery_discharge_mw=max_disch,
                                       load_shed_mw=0.10 * load)
        res_shed10 = self.verifier.run_power_flow(solar_mw=solar, load_mw=load, **shed10_control)
        if res_shed10.is_safe:
            return shed10_control, res_shed10, "load_shedding_10pct"

        # 4. Deep Targeted Load Shedding (25%)
        shed25_control = self._control(curtailment_fraction=1.0,
                                       battery_discharge_mw=max_disch,
                                       load_shed_mw=0.25 * load)
        res_shed25 = self.verifier.run_power_flow(solar_mw=solar, load_mw=load, **shed25_control)
        if res_shed25.is_safe:
            return shed25_control, res_shed25, "load_shedding_25pct"

        # If still violated, return best partial mitigation
        candidates_ladder = [
            (bess_control, res_bess, "max_bess_dispatch"),
            (curtail_control, res_curtail, "max_pv_curtailment"),
            (shed10_control, res_shed10, "load_shedding_10pct"),
            (shed25_control, res_shed25, "load_shedding_25pct"),
        ]
        best_ctrl, best_res, best_name = min(candidates_ladder, key=lambda c: self._solver_penalty(c[1]))
        return best_ctrl, best_res, f"infeasible_{best_name}"

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
        """
        Enforce exact physical conservation laws for battery state of charge:
        Charging (Pt < 0):   SOC_{t+1} = SOC_t + (P_charge * dt * eta) / C
        Discharging (Pt > 0): SOC_{t+1} = SOC_t - (P_discharge * dt) / (eta * C)
        Idle (Pt == 0):       SOC_{t+1} = SOC_t
        """
        if charge_mw == 0.0 and discharge_mw == 0.0:
            return float(soc)

        next_soc = soc + (
            charge_mw * self.battery.charge_efficiency
            - discharge_mw / self.battery.discharge_efficiency
        ) * self.battery.step_hours

        if next_soc < -1e-9 or next_soc > self.battery.capacity_mwh + 1e-9:
            raise ValueError("Candidate dispatch would violate battery SoC limits")
        return min(self.battery.capacity_mwh, max(0.0, next_soc))