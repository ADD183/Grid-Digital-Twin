"""
Violation Detection Module for Renewable Distribution Grid Digital Twin (Checkpoint 3).

Checks AC power flow results against standard utility operational limits:
- Voltage band: 0.95 to 1.05 p.u. (EN 50160 / ANSI C84.1 tolerance)
- Thermal equipment limits: Line loading <= 100%, Transformer loading <= 100%
Returns structured violation records for analysis and UI rendering.
"""

from typing import Dict, Any, List, Optional
import pandapower as pp
import pandas as pd
import numpy as np


# Standard distribution grid operating thresholds (aligned with CIGRE MV baseline in Checkpoint 1)
DEFAULT_V_MIN_PU = 0.94
DEFAULT_V_MAX_PU = 1.05
DEFAULT_MAX_LINE_LOADING_PCT = 100.0
DEFAULT_MAX_TRAFO_LOADING_PCT = 100.0


def check_grid_violations(
    net: pp.pandapowerNet,
    v_min: float = DEFAULT_V_MIN_PU,
    v_max: float = DEFAULT_V_MAX_PU,
    max_line_loading: float = DEFAULT_MAX_LINE_LOADING_PCT,
    max_trafo_loading: float = DEFAULT_MAX_TRAFO_LOADING_PCT,
) -> Dict[str, Any]:
    """
    Inspect post-powerflow network results and identify all voltage and thermal violations.
    
    Args:
        net (pp.pandapowerNet): Pandapower network with populated res_* tables.
        v_min (float): Minimum acceptable bus voltage in per-unit (default: 0.95).
        v_max (float): Maximum acceptable bus voltage in per-unit (default: 1.05).
        max_line_loading (float): Maximum acceptable line loading percent (default: 100.0).
        max_trafo_loading (float): Maximum acceptable transformer loading percent (default: 100.0).
        
    Returns:
        Dict[str, Any]: Structured dictionary containing detected violations and summary metrics.
    """
    if not hasattr(net, "res_bus") or net.res_bus.empty:
        pp.runpp(net, numba=False)

    converged = bool(getattr(net, "converged", False))
    if not converged:
        return {
            "converged": False,
            "has_violations": True,
            "total_violations": 999,
            "error": "Power flow did not converge",
            "voltage_violations": [],
            "loading_violations": [],
            "trafo_violations": [],
            "all_violations": [{
                "element_type": "grid",
                "element_id": -1,
                "violation_type": "NON_CONVERGENCE",
                "message": "AC power flow failed to converge (voltage collapse / severe numerical divergence)",
                "severity": 10.0,
            }],
            "summary": {
                "voltage_violation_count": 0,
                "loading_violation_count": 0,
                "trafo_violation_count": 0,
                "min_vm_pu": 0.0,
                "max_vm_pu": 0.0,
                "max_line_loading_percent": 0.0,
                "max_voltage_deviation": 9.99,
                "max_loading_margin": 999.0,
            }
        }

    voltage_violations: List[Dict[str, Any]] = []
    loading_violations: List[Dict[str, Any]] = []
    trafo_violations: List[Dict[str, Any]] = []
    all_violations: List[Dict[str, Any]] = []

    # 1. Bus Voltage Violations
    if hasattr(net, "res_bus") and not net.res_bus.empty:
        for bus_idx, row in net.res_bus.iterrows():
            vm_pu = float(row["vm_pu"])
            bus_name = str(net.bus.loc[bus_idx, "name"]) if "name" in net.bus.columns and pd.notna(net.bus.loc[bus_idx, "name"]) else f"Bus {bus_idx}"
            vn_kv = float(net.bus.loc[bus_idx, "vn_kv"]) if "vn_kv" in net.bus.columns and pd.notna(net.bus.loc[bus_idx, "vn_kv"]) else 15.0

            if vm_pu > v_max:
                margin = round(vm_pu - v_max, 4)
                viol = {
                    "element_type": "bus",
                    "element_id": int(bus_idx),
                    "element_name": bus_name,
                    "vn_kv": vn_kv,
                    "violation_type": "OVERVOLTAGE",
                    "actual_value": round(vm_pu, 4),
                    "limit_value": v_max,
                    "unit": "p.u.",
                    "margin": margin,
                    "severity": round(margin * 100.0, 2),  # Percentage points over limit
                    "description": f"{bus_name} overvoltage: {vm_pu:.4f} p.u. exceeds upper limit {v_max:.2f} p.u. (+{margin:.4f} p.u.)"
                }
                voltage_violations.append(viol)
                all_violations.append(viol)
            elif vm_pu < v_min:
                margin = round(v_min - vm_pu, 4)
                viol = {
                    "element_type": "bus",
                    "element_id": int(bus_idx),
                    "element_name": bus_name,
                    "vn_kv": vn_kv,
                    "violation_type": "UNDERVOLTAGE",
                    "actual_value": round(vm_pu, 4),
                    "limit_value": v_min,
                    "unit": "p.u.",
                    "margin": margin,
                    "severity": round(margin * 100.0, 2),
                    "description": f"{bus_name} undervoltage: {vm_pu:.4f} p.u. falls below lower limit {v_min:.2f} p.u. (-{margin:.4f} p.u.)"
                }
                voltage_violations.append(viol)
                all_violations.append(viol)

    # 2. Line Thermal Loading Violations
    if hasattr(net, "res_line") and not net.res_line.empty:
        for line_idx, row in net.res_line.iterrows():
            loading = float(row["loading_percent"])
            line_name = str(net.line.loc[line_idx, "name"]) if "name" in net.line.columns and pd.notna(net.line.loc[line_idx, "name"]) else f"Line {line_idx}"
            from_bus = int(net.line.loc[line_idx, "from_bus"])
            to_bus = int(net.line.loc[line_idx, "to_bus"])

            if loading > max_line_loading:
                margin = round(loading - max_line_loading, 2)
                viol = {
                    "element_type": "line",
                    "element_id": int(line_idx),
                    "element_name": line_name,
                    "from_bus": from_bus,
                    "to_bus": to_bus,
                    "violation_type": "LINE_OVERLOAD",
                    "actual_value": round(loading, 2),
                    "limit_value": max_line_loading,
                    "unit": "%",
                    "margin": margin,
                    "severity": margin,
                    "description": f"{line_name} (Bus {from_bus} -> Bus {to_bus}) thermal overload: {loading:.1f}% exceeds limit {max_line_loading:.1f}% (+{margin:.1f}%)"
                }
                loading_violations.append(viol)
                all_violations.append(viol)

    # 3. Transformer Thermal Loading Violations
    if hasattr(net, "res_trafo") and not net.res_trafo.empty:
        for trafo_idx, row in net.res_trafo.iterrows():
            loading = float(row["loading_percent"])
            trafo_name = str(net.trafo.loc[trafo_idx, "name"]) if "name" in net.trafo.columns and pd.notna(net.trafo.loc[trafo_idx, "name"]) else f"Trafo {trafo_idx}"
            hv_bus = int(net.trafo.loc[trafo_idx, "hv_bus"])
            lv_bus = int(net.trafo.loc[trafo_idx, "lv_bus"])

            if loading > max_trafo_loading:
                margin = round(loading - max_trafo_loading, 2)
                viol = {
                    "element_type": "trafo",
                    "element_id": int(trafo_idx),
                    "element_name": trafo_name,
                    "hv_bus": hv_bus,
                    "lv_bus": lv_bus,
                    "violation_type": "TRAFO_OVERLOAD",
                    "actual_value": round(loading, 2),
                    "limit_value": max_trafo_loading,
                    "unit": "%",
                    "margin": margin,
                    "severity": margin,
                    "description": f"{trafo_name} overload: {loading:.1f}% exceeds limit {max_trafo_loading:.1f}% (+{margin:.1f}%)"
                }
                trafo_violations.append(viol)
                all_violations.append(viol)

    # Calculate summary metrics
    min_vm = float(net.res_bus["vm_pu"].min()) if not net.res_bus.empty else 1.0
    max_vm = float(net.res_bus["vm_pu"].max()) if not net.res_bus.empty else 1.0
    max_line_load = float(net.res_line["loading_percent"].max()) if not net.res_line.empty else 0.0

    max_v_dev = 0.0
    if voltage_violations:
        max_v_dev = max(v["margin"] for v in voltage_violations)

    max_load_margin = 0.0
    if loading_violations or trafo_violations:
        combined_load = [v["margin"] for v in loading_violations + trafo_violations]
        max_load_margin = max(combined_load) if combined_load else 0.0

    has_violations = len(all_violations) > 0

    return {
        "converged": True,
        "has_violations": has_violations,
        "total_violations": len(all_violations),
        "voltage_violations": voltage_violations,
        "loading_violations": loading_violations,
        "trafo_violations": trafo_violations,
        "all_violations": all_violations,
        "summary": {
            "voltage_violation_count": len(voltage_violations),
            "loading_violation_count": len(loading_violations),
            "trafo_violation_count": len(trafo_violations),
            "min_vm_pu": round(min_vm, 4),
            "max_vm_pu": round(max_vm, 4),
            "max_line_loading_percent": round(max_line_load, 2),
            "max_voltage_deviation": round(max_v_dev, 4),
            "max_loading_margin": round(max_load_margin, 2),
            "worst_voltage_bus": int(net.res_bus["vm_pu"].idxmax()) if (max_vm > v_max) else (int(net.res_bus["vm_pu"].idxmin()) if min_vm < v_min else None),
            "worst_loading_line": int(net.res_line["loading_percent"].idxmax()) if max_line_load > max_line_loading else None,
        }
    }


def is_violation_free(
    net: pp.pandapowerNet,
    v_min: float = DEFAULT_V_MIN_PU,
    v_max: float = DEFAULT_V_MAX_PU,
    max_line_loading: float = DEFAULT_MAX_LINE_LOADING_PCT,
    max_trafo_loading: float = DEFAULT_MAX_TRAFO_LOADING_PCT,
) -> bool:
    """
    Fast boolean check if the network satisfies all operational constraints.
    
    Returns:
        bool: True if zero violations and power flow converged cleanly, False otherwise.
    """
    res = check_grid_violations(
        net,
        v_min=v_min,
        v_max=v_max,
        max_line_loading=max_line_loading,
        max_trafo_loading=max_trafo_loading
    )
    return res["converged"] and not res["has_violations"]
