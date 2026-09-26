"""
Corrective Action Engine for Renewable Distribution Grid Digital Twin (Checkpoint 3).

Implements the Propose -> Verify -> Repair decision-support loop:
1. Detects grid violations (bus overvoltage/undervoltage, line/trafo thermal overload).
2. Proposes a structured candidate pool of corrective actions (curtailment, battery dispatch, feeder reconfiguration, hybrids).
3. Verifies each candidate action by executing AC power flow (pp.runpp) on isolated network copies.
4. Ranks candidates on resolution success, clean renewable energy retention, and operational cost proxy.
5. Returns a structured comparison matrix, recommended winner, and explainable decision rationale.
"""

import copy
from typing import Dict, Any, List, Optional, Tuple
import pandapower as pp
import pandas as pd
import numpy as np

from src.grid import load_cigre_network, run_baseline_powerflow, get_grid_summary, get_network_element_dfs
from src.violations import check_grid_violations, is_violation_free, DEFAULT_V_MIN_PU, DEFAULT_V_MAX_PU
from src.actions import (
    apply_curtailment,
    apply_battery_dispatch,
    apply_feeder_reconfiguration,
)


# Available triggerable simulation scenarios for demo & evaluation
DEMO_SCENARIOS = {
    "solar_spike": {
        "id": "solar_spike",
        "name": "☀️ Midday Solar Surge (Overvoltage Risk)",
        "description": "High rooftop PV export combined with low midday residential load causes bus voltages to rise above 1.05 p.u.",
        "primary_violation": "OVERVOLTAGE",
        "default_magnitude": 25.0,
    },
    "evening_peak": {
        "id": "evening_peak",
        "name": "🌆 Evening Demand Peak (Thermal Sag)",
        "description": "Evening residential load surge with zero solar generation creates severe voltage sags (< 0.94 p.u.) and line loading stress.",
        "primary_violation": "UNDERVOLTAGE",
        "default_magnitude": 1.30,
    },
    "line_congestion": {
        "id": "line_congestion",
        "name": "⚡ Feeder Thermal Overload",
        "description": "High branch load on Feeder 1 pushes Line 1-2 and Line 2-3 current beyond 100% thermal capacity.",
        "primary_violation": "LINE_OVERLOAD",
        "default_magnitude": 1.80,
    },
}


def trigger_scenario(
    scenario_id: str = "solar_spike",
    magnitude: Optional[float] = None,
    base_net: Optional[pp.pandapowerNet] = None,
) -> Tuple[pp.pandapowerNet, Dict[str, Any]]:
    """
    Artificially trigger a realistic distribution grid constraint scenario.
    
    Args:
        scenario_id (str): One of 'solar_spike', 'evening_peak', 'line_congestion'.
        magnitude (Optional[float]): Multiplier or scale factor for the scenario.
        base_net (Optional[pp.pandapowerNet]): Base network to mutate (default: fresh CIGRE MV net).
        
    Returns:
        Tuple[pp.pandapowerNet, Dict[str, Any]]: Mutated network copy and scenario metadata.
    """
    if base_net is None:
        net = load_cigre_network()
    else:
        net = copy.deepcopy(base_net)

    if scenario_id == "solar_spike":
        # Midday sunny conditions: residential demand is low (35% of peak), rooftop solar generation surges
        scale = magnitude if magnitude is not None else 25.0
        net.load["p_mw"] *= 0.35
        net.load["q_mvar"] *= 0.35
        pv_mask = net.sgen["type"].astype(str).str.upper().str.contains("PV|SOLAR")
        if not pv_mask.any():
            pv_mask = slice(None)
        net.sgen.loc[pv_mask, "p_mw"] *= scale

        pp.runpp(net, numba=False)
        violations = check_grid_violations(net)

        metadata = {
            "scenario_id": "solar_spike",
            "name": DEMO_SCENARIOS["solar_spike"]["name"],
            "description": DEMO_SCENARIOS["solar_spike"]["description"],
            "parameters": {"load_scale": 0.35, "solar_multiplier": scale},
            "initial_violations": violations,
        }
        return net, metadata

    elif scenario_id == "evening_peak":
        # Evening peak: residential load surges by 30%, solar PV is completely inactive (sunset)
        scale = magnitude if magnitude is not None else 1.30
        pv_mask = net.sgen["type"].astype(str).str.upper().str.contains("PV|SOLAR")
        net.sgen.loc[pv_mask, "p_mw"] = 0.0
        net.load["p_mw"] *= scale
        net.load["q_mvar"] *= scale

        pp.runpp(net, numba=False)
        violations = check_grid_violations(net)

        metadata = {
            "scenario_id": "evening_peak",
            "name": DEMO_SCENARIOS["evening_peak"]["name"],
            "description": DEMO_SCENARIOS["evening_peak"]["description"],
            "parameters": {"load_scale": scale, "solar_generation_mw": 0.0},
            "initial_violations": violations,
        }
        return net, metadata

    elif scenario_id == "line_congestion":
        # Specific branch congestion on feeder 1
        scale = magnitude if magnitude is not None else 1.80
        branch_buses = [2, 3, 4, 5, 6]
        load_mask = net.load["bus"].isin(branch_buses)
        net.load.loc[load_mask, "p_mw"] *= scale
        net.load.loc[load_mask, "q_mvar"] *= scale

        pp.runpp(net, numba=False)
        violations = check_grid_violations(net)

        metadata = {
            "scenario_id": "line_congestion",
            "name": DEMO_SCENARIOS["line_congestion"]["name"],
            "description": DEMO_SCENARIOS["line_congestion"]["description"],
            "parameters": {"feeder_load_multiplier": scale, "target_buses": branch_buses},
            "initial_violations": violations,
        }
        return net, metadata

    else:
        raise ValueError(f"Unknown scenario_id: '{scenario_id}'. Available: {list(DEMO_SCENARIOS.keys())}")


def generate_candidate_actions(
    net: pp.pandapowerNet,
    violations: Dict[str, Any]
) -> List[Tuple[pp.pandapowerNet, Dict[str, Any]]]:
    """
    Formulate a structured set of candidate corrective actions across multiple types and magnitudes.
    
    Args:
        net (pp.pandapowerNet): Pandapower network currently exhibiting violations.
        violations (Dict[str, Any]): Violation details from check_grid_violations.
        
    Returns:
        List[Tuple[pp.pandapowerNet, Dict[str, Any]]]: List of (modified_net, action_metadata) pairs.
    """
    candidates = []
    is_overvoltage = any(v["violation_type"] == "OVERVOLTAGE" for v in violations.get("all_violations", []))
    is_undervoltage = any(v["violation_type"] == "UNDERVOLTAGE" for v in violations.get("all_violations", []))

    # --- ACTION FAMILY 1: Solar Curtailment ---
    # Curtailment is primarily useful for overvoltage or solar-driven congestion
    curtailment_levels = [15.0, 30.0, 50.0, 75.0, 100.0]
    for pct in curtailment_levels:
        c_net, meta = apply_curtailment(net, curtailment_pct=pct)
        candidates.append((c_net, meta))

    # Targeted curtailment at worst overvoltage bus if identified
    worst_bus = violations.get("summary", {}).get("worst_voltage_bus")
    if worst_bus is not None and is_overvoltage:
        c_net_targeted, meta_targeted = apply_curtailment(net, curtailment_pct=50.0, bus_id=worst_bus)
        meta_targeted["name"] = f"Targeted Solar Curtailment (50% at Bus {worst_bus})"
        candidates.append((c_net_targeted, meta_targeted))

    # --- ACTION FAMILY 2: Battery Storage Dispatch ---
    # Overvoltage -> Charge battery (p_mw > 0) to sink power
    # Undervoltage / Overload -> Discharge battery (p_mw < 0) to inject power
    if is_overvoltage:
        # Battery charging levels
        for p_mw in [0.5, 1.0, 1.5, 2.0]:
            # Dispatch at primary battery (bus 5) or worst bus
            b_bus = worst_bus if (worst_bus is not None and worst_bus in [5, 7, 8, 9, 10]) else 5
            b_net, meta = apply_battery_dispatch(net, p_mw=p_mw, bus_id=b_bus)
            candidates.append((b_net, meta))
    else:
        # Battery discharging levels
        for p_mw in [-0.5, -1.0, -1.5, -2.0]:
            b_bus = worst_bus if worst_bus is not None else 5
            b_net, meta = apply_battery_dispatch(net, p_mw=p_mw, bus_id=b_bus)
            candidates.append((b_net, meta))

    # Multi-battery coordinated dispatch
    coord_net = copy.deepcopy(net)
    b_sign = 1.0 if is_overvoltage else -1.0
    coord_net, _ = apply_battery_dispatch(coord_net, p_mw=b_sign * 1.2, bus_id=5)
    coord_net, _ = apply_battery_dispatch(coord_net, p_mw=b_sign * 0.8, bus_id=10)
    candidates.append((coord_net, {
        "action_id": "battery_coordinated_b5_b10",
        "action_type": "BATTERY_DISPATCH",
        "name": f"Dual-Battery Coordinated Dispatch ({b_sign * 2.0:+.1f} MW)",
        "p_mw": b_sign * 2.0,
        "renewable_retained_pct": 100.0,
        "cost_proxy": 2,
        "description": f"Coordinated dispatch of Battery 1 (Bus 5: {b_sign * 1.2:+.1f} MW) and Battery 2 (Bus 10: {b_sign * 0.8:+.1f} MW). 100% clean energy preserved.",
    }))

    # --- ACTION FAMILY 3: Feeder Reconfiguration ---
    # Tie switches: S1 (switch 4), S2 (switch 1), S3 (switch 2)
    for s_name in ["S1", "S2", "S3"]:
        try:
            s_net, meta = apply_feeder_reconfiguration(net, switch_name=s_name)
            candidates.append((s_net, meta))
        except Exception:
            pass

    # --- ACTION FAMILY 4: Hybrid / Combined Actions ---
    # Hybrid A: Feeder Reconfiguration (S1) + Battery Dispatch (0.5 MW)
    try:
        h1_net, _ = apply_feeder_reconfiguration(net, switch_name="S1")
        h1_net, _ = apply_battery_dispatch(h1_net, p_mw=b_sign * 0.5, bus_id=5)
        candidates.append((h1_net, {
            "action_id": "hybrid_reconfig_s1_battery",
            "action_type": "HYBRID",
            "name": "Hybrid: Reconfiguration (S1) + Battery (0.5 MW)",
            "renewable_retained_pct": 100.0,
            "cost_proxy": 2,
            "description": "Closed tie-switch S1 and dispatched Battery 1 to absorb/support 0.5 MW. 100% clean energy preserved.",
        }))
    except Exception:
        pass

    # Hybrid B: Battery Dispatch (1.0 MW) + Mild Solar Curtailment (20%)
    if is_overvoltage:
        try:
            h2_net, _ = apply_battery_dispatch(net, p_mw=1.0, bus_id=5)
            h2_net, _ = apply_curtailment(h2_net, curtailment_pct=20.0)
            candidates.append((h2_net, {
                "action_id": "hybrid_battery_curtail20",
                "action_type": "HYBRID",
                "name": "Hybrid: Battery (1.0 MW) + Mild Curtailment (20%)",
                "renewable_retained_pct": 80.0,
                "cost_proxy": 2.5,
                "description": "Dispatched Battery 1 to 1.0 MW absorption combined with 20% solar curtailment to clear high peaks.",
            }))
        except Exception:
            pass

    return candidates


def score_action(
    resolved: bool,
    renewable_retained_pct: float,
    cost_proxy: float,
    residual_violations_count: int,
    max_voltage_deviation: float,
    max_loading_margin: float,
) -> float:
    """
    Calculate composite multi-objective score for a candidate corrective action.
    
    Scoring Priorities:
    1. Primary: Does it fully resolve all violations? (+1000 pts if resolved).
    2. Secondary: Renewable energy preserved (+2.0 pts per % retained, max +200).
    3. Tertiary: Operational cost proxy penalty (-15.0 pts per cost unit: 1=switch, 2=battery, 3=curtailment).
    4. Penalty: Residual constraint violation severity (-60.0 pts per residual violation, -100.0 per p.u. deviation).
    
    Returns:
        float: Composite score (higher is superior).
    """
    score = 0.0

    if resolved:
        score += 1000.0
    else:
        # Severe penalty for remaining violations
        score -= residual_violations_count * 60.0
        score -= max_voltage_deviation * 200.0
        score -= max_loading_margin * 2.0

    # Reward clean energy preservation (0 to +200)
    score += (renewable_retained_pct * 2.0)

    # Penalize operational friction / cost (1=lowest, 3=highest)
    score -= (cost_proxy * 15.0)

    return round(score, 2)


def generate_decision_explanation(
    winner: Dict[str, Any],
    all_evaluated: List[Dict[str, Any]],
    initial_violations: Dict[str, Any]
) -> str:
    """
    Produce plain-English natural language rationale explaining why the recommended action was chosen.
    """
    w_name = winner["name"]
    w_type = winner["action_type"]
    w_resolved = winner["resolved"]
    w_clean = winner["renewable_retained_pct"]
    w_cost = winner["cost_proxy"]

    init_count = initial_violations.get("total_violations", 0)

    if w_resolved:
        if w_type == "FEEDER_RECONFIGURATION":
            explanation = (
                f"{w_name} is the optimal recommendation. It fully resolved all {init_count} grid violations "
                f"while retaining 100% of clean renewable generation with minimal operational cost (cost proxy {w_cost}/3). "
                f"It superiorly avoided the energy waste of solar curtailment and equipment wear of battery cycling."
            )
        elif w_type == "BATTERY_DISPATCH":
            explanation = (
                f"{w_name} is the recommended corrective action. It successfully cleared all {init_count} grid violations "
                f"while preserving 100% of solar generation by storing the excess energy rather than wasting it. "
                f"Although battery cycling carries a modest operational cost (cost proxy {w_cost}/3), it scored higher than "
                f"solar curtailment which directly discards clean zero-carbon energy."
            )
        elif w_type == "CURTAILMENT":
            explanation = (
                f"{w_name} is selected. It fully eliminated all {init_count} grid violations. "
                f"While curtailment wastes a portion of renewable generation ({100.0 - w_clean:.0f}% curtailed, cost proxy {w_cost}/3), "
                f"it was mathematically necessary as passive switching and available battery capacity alone could not clear all thermal/voltage constraints."
            )
        else:
            explanation = (
                f"{w_name} is recommended. It achieved 100% resolution of all {init_count} violations "
                f"with {w_clean:.0f}% renewable energy retention and a balanced operational profile (score: {winner['score']})."
            )
    else:
        explanation = (
            f"Constraint Alert: No single action completely resolved all violations. "
            f"{w_name} provided the best partial mitigation (residual violations: {winner['residual_violations_count']}, "
            f"score: {winner['score']}). Additional grid support or combination actions are required."
        )

    return explanation


def evaluate_actions(
    net: pp.pandapowerNet,
    custom_candidates: Optional[List[Tuple[pp.pandapowerNet, Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Execute the Propose -> Verify -> Repair decision engine on a network in violation.
    
    Args:
        net (pp.pandapowerNet): Pandapower network.
        custom_candidates (Optional[List]): Optional pre-defined candidate list.
        
    Returns:
        Dict[str, Any]: Full structured evaluation results, ranked actions, and decision explanation.
    """
    # 1. Detect Initial Violations
    initial_violations = check_grid_violations(net)
    initial_summary = get_grid_summary(net)

    # 2. Propose Candidates
    if custom_candidates is None:
        candidates = generate_candidate_actions(net, initial_violations)
    else:
        candidates = custom_candidates

    evaluated_actions = []

    # 3. Verify Each Candidate via AC Power Flow
    for idx, (cand_net, meta) in enumerate(candidates):
        try:
            pp.runpp(cand_net, numba=False)
            converged = bool(getattr(cand_net, "converged", False))
        except Exception:
            converged = False

        if not converged:
            score = -9999.0
            evaluated_actions.append({
                "rank": 999,
                "action_id": meta.get("action_id", f"action_{idx}"),
                "action_type": meta.get("action_type", "UNKNOWN"),
                "name": meta.get("name", f"Action {idx}"),
                "converged": False,
                "resolved": False,
                "residual_violations_count": 999,
                "min_vm_pu": 0.0,
                "max_vm_pu": 0.0,
                "max_line_loading_percent": 999.0,
                "renewable_retained_pct": meta.get("renewable_retained_pct", 0.0),
                "cost_proxy": meta.get("cost_proxy", 3),
                "score": score,
                "description": meta.get("description", "") + " [POWER FLOW DIVERGED]",
                "net": None,
            })
            continue

        cand_violations = check_grid_violations(cand_net)
        c_summary = cand_violations.get("summary", {})
        total_viol = cand_violations.get("total_violations", 0)
        resolved = (total_viol == 0)

        v_dev = c_summary.get("max_voltage_deviation", 0.0)
        l_margin = c_summary.get("max_loading_margin", 0.0)
        retained = float(meta.get("renewable_retained_pct", 100.0))
        cost = float(meta.get("cost_proxy", 2))

        score = score_action(
            resolved=resolved,
            renewable_retained_pct=retained,
            cost_proxy=cost,
            residual_violations_count=total_viol,
            max_voltage_deviation=v_dev,
            max_loading_margin=l_margin,
        )

        evaluated_actions.append({
            "rank": 0,  # Will be assigned after sort
            "action_id": meta.get("action_id", f"action_{idx}"),
            "action_type": meta.get("action_type", "UNKNOWN"),
            "name": meta.get("name", f"Action {idx}"),
            "converged": True,
            "resolved": resolved,
            "residual_violations_count": total_viol,
            "residual_voltage_violations": len(cand_violations.get("voltage_violations", [])),
            "residual_loading_violations": len(cand_violations.get("loading_violations", [])),
            "min_vm_pu": c_summary.get("min_vm_pu", 1.0),
            "max_vm_pu": c_summary.get("max_vm_pu", 1.0),
            "max_line_loading_percent": c_summary.get("max_line_loading_percent", 0.0),
            "renewable_retained_pct": retained,
            "cost_proxy": cost,
            "score": score,
            "description": meta.get("description", ""),
            "violations_detail": cand_violations.get("all_violations", []),
            "net": cand_net,
        })

    # 4. Rank Candidates Descending by Score
    evaluated_actions.sort(key=lambda x: x["score"], reverse=True)
    for rank_idx, act in enumerate(evaluated_actions, start=1):
        act["rank"] = rank_idx

    winner = evaluated_actions[0] if evaluated_actions else None
    explanation = generate_decision_explanation(winner, evaluated_actions, initial_violations) if winner else "No actions evaluated."

    # Strip raw network instances from serialized JSON output to keep it clean for API/UI
    serialized_actions = []
    winner_net = None
    if winner:
        winner_net = winner.get("net")

    for act in evaluated_actions:
        act_clean = {k: v for k, v in act.items() if k != "net"}
        serialized_actions.append(act_clean)

    # Format winner post-action grid state for before/after comparison
    after_grid_summary = None
    after_topology = None
    if winner_net is not None:
        after_grid_summary = get_grid_summary(winner_net)
        b_df, l_df, s_df = get_network_element_dfs(winner_net)
        
        # Serialize topology
        buses = []
        for b_idx, row in b_df.iterrows():
            buses.append({
                "id": int(b_idx),
                "name": str(row.get("name", f"Bus {b_idx}")),
                "vm_pu": round(float(row.get("vm_pu", 1.0)), 4),
                "va_degree": round(float(row.get("va_degree", 0.0)), 2),
                "x": round(float(row.get("x", 0.0)), 2),
                "y": round(float(row.get("y", 0.0)), 2),
                "vn_kv": round(float(row.get("vn_kv", 15.0)), 1)
            })
        lines = []
        for l_idx, row in l_df.iterrows():
            lines.append({
                "id": int(l_idx),
                "name": str(row.get("name", f"Line {l_idx}")),
                "from_bus": int(row["from_bus"]),
                "to_bus": int(row["to_bus"]),
                "loading_percent": round(float(row.get("loading_percent", 0.0)), 2),
                "length_km": round(float(row.get("length_km", 1.0)), 2),
                "from_x": round(float(row.get("from_x", 0.0)), 2),
                "from_y": round(float(row.get("from_y", 0.0)), 2),
                "to_x": round(float(row.get("to_x", 0.0)), 2),
                "to_y": round(float(row.get("to_y", 0.0)), 2),
            })
        sgens = []
        if not s_df.empty:
            for s_idx, row in s_df.iterrows():
                sgens.append({
                    "id": int(s_idx),
                    "name": str(row.get("name", f"DER {s_idx}")),
                    "bus": int(row["bus"]),
                    "p_mw": round(float(row.get("p_mw", 0.0)), 3),
                    "type": str(row.get("type", "PV"))
                })
        after_topology = {"buses": buses, "lines": lines, "sgens": sgens}

    return {
        "initial_violations": initial_violations,
        "before_grid_summary": initial_summary,
        "actions_evaluated": len(serialized_actions),
        "ranked_actions": serialized_actions,
        "recommended_action": serialized_actions[0] if serialized_actions else None,
        "fully_resolved": bool(winner["resolved"]) if winner else False,
        "explanation": explanation,
        "after_grid_summary": after_grid_summary,
        "after_topology": after_topology,
    }
