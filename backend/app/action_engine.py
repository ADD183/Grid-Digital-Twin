"""
Corrective Action Engine adapter for backend/app/ module (Checkpoint 3 & 4).
Provides dynamic voltage setpoint optimization, DER control, and contingency mitigation.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandapower as pp

from src.engine import (
    DEMO_SCENARIOS,
    trigger_scenario,
    generate_candidate_actions,
    score_action,
    generate_decision_explanation,
    evaluate_actions,
)
from src.actions import (
    apply_curtailment,
    apply_battery_dispatch,
    apply_feeder_reconfiguration,
    apply_voltage_setpoint,
)
from src.violations import check_grid_violations, is_violation_free
from src.grid import load_cigre_network, run_baseline_powerflow, get_grid_summary


def optimize_voltage_setpoint(
    net: pp.pandapowerNet,
    target_v_min: float = 0.95,
    target_v_max: float = 1.05,
) -> Tuple[Optional[float], Optional[pp.pandapowerNet]]:
    """
    Actively search for an ext_grid voltage setpoint that keeps all bus voltages within [target_v_min, target_v_max].
    
    Args:
        net: Target pandapower network.
        target_v_min: Minimum allowed per-unit voltage (default: 0.95).
        target_v_max: Maximum allowed per-unit voltage (default: 1.05).
        
    Returns:
        Tuple[best_setpoint, best_network_copy] or (None, None) if no setpoint alone clears constraints.
    """
    candidate_setpoints = [1.00, 1.01, 1.02, 1.03, 1.036, 1.04, 1.045, 1.05, 0.99, 0.98]
    best_vm = None
    best_net = None
    best_residual_severity = float("inf")

    for vm in candidate_setpoints:
        cand_net, _ = apply_voltage_setpoint(net, vm_pu=vm)
        try:
            pp.runpp(cand_net, numba=False)
            if cand_net.converged:
                vm_min = float(cand_net.res_bus.vm_pu.min())
                vm_max = float(cand_net.res_bus.vm_pu.max())
                if target_v_min <= vm_min and vm_max <= target_v_max:
                    return vm, cand_net
                
                # Track best partial
                dev = max(0.0, target_v_min - vm_min) + max(0.0, vm_max - target_v_max)
                if dev < best_residual_severity:
                    best_residual_severity = dev
                    best_vm = vm
                    best_net = cand_net
        except Exception:
            continue

    return best_vm, best_net


__all__ = [
    "DEMO_SCENARIOS",
    "trigger_scenario",
    "generate_candidate_actions",
    "score_action",
    "generate_decision_explanation",
    "evaluate_actions",
    "apply_curtailment",
    "apply_battery_dispatch",
    "apply_feeder_reconfiguration",
    "apply_voltage_setpoint",
    "optimize_voltage_setpoint",
    "check_grid_violations",
    "is_violation_free",
]
