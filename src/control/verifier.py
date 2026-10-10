"""
Physical Power-Flow Verification Wrapper for VoltPredict (pandapower AC Newton-Raphson).
Contract defined in PRD Section 4:
verify(state, action, observed_inputs) -> VerificationResult:
    converged, violations[], min_margin, bus_vm, line_loading, solve_ms
"""

import copy
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import pandapower as pp
import pandas as pd
import numpy as np

from src.grid import load_cigre_network
from src.violations import check_grid_violations
from src.control.state import State, Action, LimitsConfig, load_limits_config


@dataclass
class VerificationResult:
    """
    Physical verification result returned by the pandapower AC power flow solver.
    """
    converged: bool
    violations: List[Dict[str, Any]]
    min_margin: float
    bus_vm: Dict[int, float]
    line_loading: Dict[int, float]
    solve_ms: float
    is_safe: bool = field(init=False)

    def __post_init__(self):
        self.is_safe = (
            bool(self.converged)
            and len(self.violations) == 0
            and float(self.min_margin) >= 0.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "converged": bool(self.converged),
            "is_safe": bool(self.is_safe),
            "min_margin": round(float(self.min_margin), 5),
            "violations_count": len(self.violations),
            "violations": self.violations,
            "bus_vm": {int(k): round(float(v), 4) for k, v in self.bus_vm.items()},
            "line_loading": {int(k): round(float(v), 2) for k, v in self.line_loading.items()},
            "solve_ms": round(float(self.solve_ms), 3),
        }


class Verifier:
    """
    Deterministic pandapower AC power-flow verification engine.
    Pins solver algorithm, tolerance, and maximum iterations as per solver_config.json.
    """

    def __init__(self, limits: Optional[LimitsConfig] = None, base_net: Optional[pp.pandapowerNet] = None):
        self.limits = limits or load_limits_config()
        self._raw_base_net = base_net or load_cigre_network()
        # Fast reusable worker network for in-place parameter mutations
        self._worker_net = copy.deepcopy(self._raw_base_net)
        self._cache: Dict[Tuple, VerificationResult] = {}
        # Cache baseline load and PV generation vectors for deterministic scaling
        self._base_sgen_p = self._raw_base_net.sgen["p_mw"].copy()
        self._base_load_p = self._raw_base_net.load["p_mw"].copy()
        self._base_load_q = self._raw_base_net.load["q_mvar"].copy()
        self.pv_mask = self._raw_base_net.sgen["type"].astype(str).str.upper().str.contains("PV|SOLAR")
        if not self.pv_mask.any():
            self.pv_mask = slice(None)

    def create_net_for_condition(
        self,
        observed_inputs: Dict[str, Any],
        switch_state: Optional[Dict[int, bool]] = None,
    ) -> pp.pandapowerNet:
        """Create a fresh network copy configured with observed solar and load inputs."""
        net = copy.deepcopy(self._raw_base_net)

        solar_scale = float(observed_inputs.get("solar_scale", observed_inputs.get("solar_pu", 1.0)))
        load_scale = float(observed_inputs.get("load_scale", observed_inputs.get("load_pu", 1.0)))

        # Apply solar generation
        net.sgen.loc[self.pv_mask, "p_mw"] = self._base_sgen_p.loc[self.pv_mask] * solar_scale

        # Apply load demand
        net.load.loc[:, "p_mw"] = self._base_load_p * load_scale
        net.load.loc[:, "q_mvar"] = self._base_load_q * load_scale

        # Apply switch state
        if switch_state:
            for s_id, is_closed in switch_state.items():
                if s_id in net.switch.index:
                    net.switch.loc[s_id, "closed"] = bool(is_closed)

        return net

    def verify(
        self,
        state: State,
        action: Action,
        observed_inputs: Dict[str, Any],
    ) -> VerificationResult:
        """
        Execute deterministic AC power flow and verify grid safety for (state, action, inputs).
        
        Args:
            state: Current state before action
            action: Action to apply
            observed_inputs: Observed or forecasted grid operating conditions (solar, load)
            
        Returns:
            VerificationResult: Exact solver outputs, margin, and violation records
        """
        solar_scale = float(observed_inputs.get("solar_scale", observed_inputs.get("solar_pu", 1.0)))
        load_scale = float(observed_inputs.get("load_scale", observed_inputs.get("load_pu", 1.0)))
        curtail_pct = max(0.0, min(100.0, float(action.curtail_pct)))

        cache_key = (
            round(solar_scale, 2),
            round(load_scale, 2),
            round(float(action.battery_mw), 3),
            round(curtail_pct, 1),
            state.switch_state,
            action.switch_toggle,
        )
        if cache_key in self._cache:
            return self._cache[cache_key]

        t0 = time.perf_counter()

        # Mutate worker network in-place to avoid expensive pandapower deepcopy
        net = self._worker_net

        # 1. Apply baseline solar and load scaling
        curtail_factor = 1.0 - (curtail_pct / 100.0)

        net.sgen.loc[self.pv_mask, "p_mw"] = self._base_sgen_p.loc[self.pv_mask] * (solar_scale * curtail_factor)
        net.load.loc[:, "p_mw"] = self._base_load_p * load_scale
        net.load.loc[:, "q_mvar"] = self._base_load_q * load_scale

        # 2. Apply switch configuration
        current_switches = state.switch_dict
        for s_id, is_closed in current_switches.items():
            if s_id in net.switch.index:
                net.switch.loc[s_id, "closed"] = bool(is_closed)

        if action.switch_toggle is not None and action.switch_toggle in net.switch.index:
            net.switch.loc[action.switch_toggle, "closed"] = not net.switch.loc[action.switch_toggle, "closed"]

        # 3. Apply battery dispatch
        # Action convention: + = discharge (inject), - = charge (absorb)
        # Pandapower convention: + = load (absorb), - = gen (inject)
        storage_bus = self.limits.battery.bus_id
        if hasattr(net, "storage") and not net.storage.empty:
            matches = net.storage[net.storage["bus"] == storage_bus].index
            storage_idx = matches[0] if len(matches) > 0 else net.storage.index[0]
            net.storage.loc[storage_idx, "p_mw"] = -float(action.battery_mw)
            net.storage.loc[storage_idx, "in_service"] = True
            for other_idx in net.storage.index:
                if other_idx != storage_idx:
                    net.storage.loc[other_idx, "p_mw"] = 0.0

        # 4. Deterministic AC Power Flow (pinned settings from solver_config.json)
        try:
            pp.runpp(
                net,
                algorithm="nr",
                tolerance_mva=1e-06,
                max_iteration=50,
                calculate_voltage_angles=True,
                numba=False,
            )
            converged = bool(getattr(net, "converged", False))
        except Exception:
            converged = False

        solve_ms = (time.perf_counter() - t0) * 1000.0

        if not converged:
            return VerificationResult(
                converged=False,
                violations=[{
                    "element_type": "grid",
                    "element_id": -1,
                    "violation_type": "NON_CONVERGENCE",
                    "message": "AC power flow diverged; solver failed to converge.",
                    "severity": 100.0,
                }],
                min_margin=-1.0,
                bus_vm={},
                line_loading={},
                solve_ms=solve_ms,
            )

        # 5. Fast vectorized extraction of bus voltages and line loadings
        vm_series = net.res_bus["vm_pu"]
        load_series = net.res_line["loading_percent"]
        bus_vm = dict(zip(vm_series.index.astype(int), vm_series.astype(float)))
        line_loading = dict(zip(load_series.index.astype(int), load_series.astype(float)))

        # 6. Fast vectorized min_margin calculation (signed distance to limits)
        v_min = self.limits.grid.v_min
        v_max = self.limits.grid.v_max
        max_loading = self.limits.grid.max_loading_pct

        vm_vals = vm_series.to_numpy()
        min_vm_margin = float(min(np.min(vm_vals - v_min), np.min(v_max - vm_vals)))
        min_loading_margin = float((max_loading - np.max(load_series.to_numpy())) / 100.0)
        min_margin = min(min_vm_margin, min_loading_margin)

        # 7. Check detailed violations only when a violation is mathematically present
        if min_margin < 0.0:
            violations_res = check_grid_violations(
                net,
                v_min=v_min,
                v_max=v_max,
                max_line_loading=max_loading,
            )
            violations = violations_res.get("all_violations", [])
        else:
            violations = []

        res = VerificationResult(
            converged=True,
            violations=violations,
            min_margin=min_margin,
            bus_vm=bus_vm,
            line_loading=line_loading,
            solve_ms=solve_ms,
        )
        self._cache[cache_key] = res
        return res


def verify(
    state: State,
    action: Action,
    observed_inputs: Dict[str, Any],
    verifier_instance: Optional[Verifier] = None,
) -> VerificationResult:
    """Functional contract: verify(state, action, observed_inputs) -> VerificationResult"""
    v = verifier_instance or Verifier()
    return v.verify(state, action, observed_inputs)
