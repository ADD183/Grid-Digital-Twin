"""Pandapower AC power-flow verification for MPC candidates."""

from __future__ import annotations

import asyncio
import copy

import pandapower as pp

from backend.app.config import Settings, get_settings
from backend.app.schemas import ElementViolation, SolverResult
from src.grid import load_cigre_network


class SolverVerifier:
    """Apply a candidate operating point to CIGRE MV and verify constraints."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run_power_flow(
        self,
        *,
        solar_mw: float,
        load_mw: float,
        curtailment_fraction: float = 0.0,
        battery_charge_mw: float = 0.0,
        battery_discharge_mw: float = 0.0,
        load_shed_mw: float = 0.0,
        voltage_setpoint_pu: float | None = None,
        network: pp.pandapowerNet | None = None,
    ) -> SolverResult:
        """Run an isolated AC power flow for one dispatch decision."""
        values = {
            "solar_mw": solar_mw,
            "load_mw": load_mw,
            "battery_charge_mw": battery_charge_mw,
            "battery_discharge_mw": battery_discharge_mw,
            "load_shed_mw": load_shed_mw,
        }
        if any(value < 0 for value in values.values()):
            raise ValueError("Power inputs must be non-negative")
        if not 0.0 <= curtailment_fraction <= 1.0:
            raise ValueError("curtailment_fraction must be between 0 and 1")

        net = copy.deepcopy(network) if network is not None else load_cigre_network()
        if voltage_setpoint_pu is not None:
            net.ext_grid.loc[:, "vm_pu"] = float(voltage_setpoint_pu)
        pv_mask = (
            net.sgen["type"].astype(str).str.upper().str.contains("PV|SOLAR")
            if not net.sgen.empty and "type" in net.sgen.columns
            else net.sgen.index.to_series().isin([])
        )
        base_solar = float(net.sgen.loc[pv_mask, "p_mw"].clip(lower=0).sum()) if pv_mask.any() else 0.0
        solar_target = solar_mw * (1.0 - curtailment_fraction)
        if solar_target > 0 and base_solar <= 0:
            raise ValueError("The selected network has no active PV generators for the solar forecast")
        if base_solar > 0:
            net.sgen.loc[pv_mask, "p_mw"] *= solar_target / base_solar

        base_load = float(net.load.p_mw.clip(lower=0).sum()) if not net.load.empty else 0.0
        if base_load > 0 and not net.load.empty:
            # 1. Base scale network load to forecast demand
            base_scale = load_mw / base_load
            net.load.loc[:, "p_mw"] *= base_scale
            net.load.loc[:, "q_mvar"] *= base_scale

            # 2. Apply targeted load shedding to prioritized non-critical feeder branches
            if load_shed_mw > 0:
                remaining_shed_mw = float(load_shed_mw)
                # Prioritize peripheral / non-critical residential feeder end buses
                priority_buses = [6, 10, 11, 14, 8, 9, 7, 5, 4, 3, 2, 1]
                for bus_id in priority_buses:
                    if remaining_shed_mw <= 1e-6:
                        break
                    bus_loads = net.load[net.load["bus"] == bus_id]
                    for idx in bus_loads.index:
                        current_p = float(net.load.loc[idx, "p_mw"])
                        if current_p > 0:
                            shed_amount = min(current_p, remaining_shed_mw)
                            power_factor_ratio = (current_p - shed_amount) / current_p if current_p > 0 else 0.0
                            net.load.loc[idx, "p_mw"] -= shed_amount
                            net.load.loc[idx, "q_mvar"] *= power_factor_ratio
                            remaining_shed_mw -= shed_amount
                            if remaining_shed_mw <= 1e-6:
                                break

                # Fallback: if remaining load shed exceeds priority branches, shed proportionally from remaining
                if remaining_shed_mw > 1e-6:
                    current_total_p = float(net.load.p_mw.clip(lower=0).sum())
                    if current_total_p > 0:
                        rem_scale = max(0.0, (current_total_p - remaining_shed_mw) / current_total_p)
                        net.load.loc[:, "p_mw"] *= rem_scale
                        net.load.loc[:, "q_mvar"] *= rem_scale

        battery_p_mw = battery_charge_mw - battery_discharge_mw
        if abs(battery_p_mw) > 0:
            pp.create_storage(
                net,
                bus=int(net.load.bus.iloc[0]) if not net.load.empty else int(net.bus.index[-1]),
                p_mw=battery_p_mw,
                max_e_mwh=4.0,
                min_p_mw=-2.0,
                max_p_mw=2.0,
                name="MPC Battery",
                type="Battery",
                in_service=True,
            )

        try:
            pp.runpp(
                net,
                algorithm="nr",
                tolerance_mva=self.settings.solver_tolerance,
                numba=False,
            )
        except Exception as exc:
            return SolverResult(
                converged=False,
                is_safe=False,
                violations=[
                    ElementViolation(
                        element_type="grid",
                        element_id=-1,
                        violation_type="NON_CONVERGENCE",
                        unit="status",
                        message=f"AC power flow failed: {exc}",
                    )
                ],
                error=str(exc),
            )

        if not bool(getattr(net, "converged", False)):
            return SolverResult(
                converged=False,
                is_safe=False,
                violations=[
                    ElementViolation(
                        element_type="grid",
                        element_id=-1,
                        violation_type="NON_CONVERGENCE",
                        unit="status",
                        message="AC power flow did not converge",
                    )
                ],
            )

        bus_values = {int(i): float(v) for i, v in net.res_bus.vm_pu.items()}
        line_values = {
            int(i): float(v) for i, v in net.res_line.loading_percent.items()
        }
        trafo_values = (
            {int(i): float(v) for i, v in net.res_trafo.loading_percent.items()}
            if hasattr(net, "res_trafo") and not net.res_trafo.empty
            else {}
        )
        violations: list[ElementViolation] = []

        for bus_id, voltage in bus_values.items():
            if voltage < self.settings.voltage_min_pu:
                violations.append(
                    ElementViolation(
                        element_type="bus",
                        element_id=bus_id,
                        violation_type="UNDERVOLTAGE",
                        actual_value=voltage,
                        limit_value=self.settings.voltage_min_pu,
                        unit="p.u.",
                        message=f"Bus {bus_id} voltage {voltage:.4f} p.u. is below the safe limit",
                    )
                )
            elif voltage > self.settings.voltage_max_pu:
                violations.append(
                    ElementViolation(
                        element_type="bus",
                        element_id=bus_id,
                        violation_type="OVERVOLTAGE",
                        actual_value=voltage,
                        limit_value=self.settings.voltage_max_pu,
                        unit="p.u.",
                        message=f"Bus {bus_id} voltage {voltage:.4f} p.u. is above the safe limit",
                    )
                )

        for line_id, loading in line_values.items():
            if loading > self.settings.max_line_loading_percent:
                violations.append(
                    ElementViolation(
                        element_type="line",
                        element_id=line_id,
                        violation_type="LINE_OVERLOAD",
                        actual_value=loading,
                        limit_value=self.settings.max_line_loading_percent,
                        unit="%",
                        message=f"Line {line_id} loading {loading:.2f}% exceeds its rating",
                    )
                )

        for trafo_id, loading in trafo_values.items():
            if loading > self.settings.max_line_loading_percent:
                violations.append(
                    ElementViolation(
                        element_type="transformer",
                        element_id=trafo_id,
                        violation_type="TRANSFORMER_OVERLOAD",
                        actual_value=loading,
                        limit_value=self.settings.max_line_loading_percent,
                        unit="%",
                        message=f"Transformer {trafo_id} loading {loading:.2f}% exceeds its rating",
                    )
                )

        return SolverResult(
            converged=True,
            is_safe=not violations,
            min_voltage_pu=min(bus_values.values(), default=None),
            max_voltage_pu=max(bus_values.values(), default=None),
            max_line_loading_percent=max(line_values.values(), default=None),
            max_transformer_loading_percent=max(trafo_values.values(), default=None),
            bus_voltages_pu=bus_values,
            line_loadings_percent=line_values,
            violations=violations,
        )

    async def run_power_flow_async(self, **kwargs: object) -> SolverResult:
        """Run synchronous pandapower computation away from the event loop."""
        return await asyncio.to_thread(self.run_power_flow, **kwargs)