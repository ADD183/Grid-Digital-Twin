"""
Unit tests for Checkpoint 3: Grid Violation Detection, Corrective Actions (Curtailment,
Battery Storage Dispatch, Feeder Reconfiguration), and Propose-Verify-Repair Engine.
"""

import pytest
import pandapower as pp
import numpy as np

from src.grid import load_cigre_network, run_baseline_powerflow
from src.violations import check_grid_violations, is_violation_free
from src.actions import (
    apply_curtailment,
    apply_battery_dispatch,
    apply_feeder_reconfiguration,
)
from src.engine import (
    trigger_scenario,
    generate_candidate_actions,
    score_action,
    evaluate_actions,
    DEMO_SCENARIOS,
)


def test_baseline_grid_violation_free():
    """Verify that under nominal conditions, the CIGRE MV grid has 0 violations."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    report = check_grid_violations(net)
    
    assert report["converged"] is True
    assert report["has_violations"] is False
    assert report["total_violations"] == 0
    assert len(report["voltage_violations"]) == 0
    assert len(report["loading_violations"]) == 0
    assert is_violation_free(net) is True


def test_detect_bus_overvoltage():
    """Verify violation detector flags bus voltages that exceed upper limit (1.05 p.u.)."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    
    # Artificially modify bus 7 voltage in results to simulate an overvoltage
    net.res_bus.loc[7, "vm_pu"] = 1.0825
    report = check_grid_violations(net)
    
    assert report["has_violations"] is True
    assert len(report["voltage_violations"]) >= 1
    
    overvoltage_buses = [v["element_id"] for v in report["voltage_violations"] if v["violation_type"] == "OVERVOLTAGE"]
    assert 7 in overvoltage_buses
    
    v7 = next(v for v in report["voltage_violations"] if v["element_id"] == 7)
    assert v7["actual_value"] == 1.0825
    assert v7["limit_value"] == 1.05
    assert v7["margin"] == round(1.0825 - 1.05, 4)


def test_detect_bus_undervoltage():
    """Verify violation detector flags bus voltages that fall below lower limit (0.94 p.u.)."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    
    # Artificially modify bus 6 voltage to simulate an undervoltage
    net.res_bus.loc[6, "vm_pu"] = 0.9120
    report = check_grid_violations(net)
    
    assert report["has_violations"] is True
    undervoltage_buses = [v["element_id"] for v in report["voltage_violations"] if v["violation_type"] == "UNDERVOLTAGE"]
    assert 6 in undervoltage_buses
    
    v6 = next(v for v in report["voltage_violations"] if v["element_id"] == 6)
    assert v6["actual_value"] == 0.9120
    assert v6["margin"] == round(0.94 - 0.9120, 4)


def test_detect_line_overload():
    """Verify violation detector flags lines whose thermal loading exceeds 100%."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    
    # Artificially set line 2 loading to 135%
    net.res_line.loc[2, "loading_percent"] = 135.4
    report = check_grid_violations(net)
    
    assert report["has_violations"] is True
    overloaded_lines = [v["element_id"] for v in report["loading_violations"]]
    assert 2 in overloaded_lines
    
    l2 = next(v for v in report["loading_violations"] if v["element_id"] == 2)
    assert l2["actual_value"] == 135.4
    assert l2["margin"] == 35.4


def test_curtailment_action_independent():
    """Verify solar curtailment creates an isolated net copy and executes valid AC power flow."""
    net = load_cigre_network()
    initial_pv = float(net.sgen["p_mw"].sum())
    
    mod_net, meta = apply_curtailment(net, curtailment_pct=40.0)
    
    assert mod_net is not net
    assert meta["action_type"] == "CURTAILMENT"
    assert meta["curtailment_pct"] == 40.0
    assert meta["renewable_retained_pct"] == 60.0
    assert meta["cost_proxy"] == 3
    assert float(mod_net.sgen["p_mw"].sum()) < initial_pv
    
    # Ensure power flow executes cleanly
    pp.runpp(mod_net, numba=False)
    assert mod_net.converged is True


def test_battery_dispatch_action_independent():
    """Verify battery storage dispatch can charge and discharge with valid AC power flow."""
    net = load_cigre_network()
    
    # Test charging (p_mw > 0)
    mod_net_charge, meta_charge = apply_battery_dispatch(net, p_mw=0.6, bus_id=5)
    assert meta_charge["action_type"] == "BATTERY_DISPATCH"
    assert meta_charge["p_mw"] == 0.6
    assert meta_charge["cost_proxy"] == 2
    assert meta_charge["renewable_retained_pct"] == 100.0
    pp.runpp(mod_net_charge, numba=False)
    assert mod_net_charge.converged is True
    
    # Test discharging (p_mw < 0)
    mod_net_discharge, meta_discharge = apply_battery_dispatch(net, p_mw=-0.4, bus_id=10)
    assert meta_discharge["p_mw"] == -0.4
    pp.runpp(mod_net_discharge, numba=False)
    assert mod_net_discharge.converged is True


def test_feeder_reconfiguration_action_independent():
    """Verify feeder reconfiguration toggles tie-switch and executes valid AC power flow."""
    net = load_cigre_network()
    
    mod_net, meta = apply_feeder_reconfiguration(net, switch_name="S1")
    assert mod_net is not net
    assert meta["action_type"] == "FEEDER_RECONFIGURATION"
    assert meta["switch_name"] == "S1"
    assert meta["new_state"] == "CLOSED"
    assert meta["cost_proxy"] == 1
    assert meta["renewable_retained_pct"] == 100.0
    
    # Switch S1 is index 4 in CIGRE MV net
    assert bool(mod_net.switch.loc[4, "closed"]) is True
    pp.runpp(mod_net, numba=False)
    assert mod_net.converged is True


def test_solar_spike_trigger_creates_violations():
    """Verify artificial solar spike scenario induces multiple bus overvoltage violations."""
    net, meta = trigger_scenario("solar_spike", magnitude=25.0)
    
    violations = meta["initial_violations"]
    assert violations["has_violations"] is True
    assert violations["total_violations"] > 0
    assert violations["summary"]["max_vm_pu"] > 1.05
    assert len(violations["voltage_violations"]) > 0


def test_evening_peak_trigger_creates_violations():
    """Verify artificial evening peak scenario induces voltage sags and line loading."""
    net, meta = trigger_scenario("evening_peak", magnitude=1.30)
    
    violations = meta["initial_violations"]
    assert violations["has_violations"] is True
    assert violations["total_violations"] > 0
    assert violations["summary"]["min_vm_pu"] < 0.94


def test_score_action_logic():
    """Verify multi-objective scoring formula favors resolution, renewable retention, and low cost."""
    # Fully resolved with 100% clean energy and low cost (Switch)
    score_switch = score_action(
        resolved=True,
        renewable_retained_pct=100.0,
        cost_proxy=1.0,
        residual_violations_count=0,
        max_voltage_deviation=0.0,
        max_loading_margin=0.0,
    )
    
    # Fully resolved with 100% clean energy and moderate cost (Battery)
    score_battery = score_action(
        resolved=True,
        renewable_retained_pct=100.0,
        cost_proxy=2.0,
        residual_violations_count=0,
        max_voltage_deviation=0.0,
        max_loading_margin=0.0,
    )
    
    # Fully resolved with 50% clean energy and high cost (Curtailment)
    score_curtail = score_action(
        resolved=True,
        renewable_retained_pct=50.0,
        cost_proxy=3.0,
        residual_violations_count=0,
        max_voltage_deviation=0.0,
        max_loading_margin=0.0,
    )
    
    # Unresolved with 2 residual violations
    score_unresolved = score_action(
        resolved=False,
        renewable_retained_pct=100.0,
        cost_proxy=1.0,
        residual_violations_count=2,
        max_voltage_deviation=0.02,
        max_loading_margin=10.0,
    )
    
    assert score_switch > score_battery > score_curtail > score_unresolved


def test_engine_evaluates_and_ranks_candidates():
    """Verify propose-verify-repair loop evaluates all 3 action types and ranks them."""
    net, meta = trigger_scenario("solar_spike")
    res = evaluate_actions(net)
    
    assert res["actions_evaluated"] >= 10
    assert len(res["ranked_actions"]) == res["actions_evaluated"]
    assert res["recommended_action"] is not None
    assert "explanation" in res and len(res["explanation"]) > 20
    assert "after_grid_summary" in res
    assert "after_topology" in res
    
    # Verify ranks are ordered 1, 2, 3...
    ranks = [a["rank"] for a in res["ranked_actions"]]
    assert ranks == list(range(1, len(ranks) + 1))
    
    # Verify scores are monotonically non-increasing
    scores = [a["score"] for a in res["ranked_actions"]]
    assert scores == sorted(scores, reverse=True)


def test_engine_resolves_violation_with_explanation():
    """Verify at least one scenario is completely resolved with explainable rationale."""
    net, meta = trigger_scenario("solar_spike")
    res = evaluate_actions(net)
    
    assert res["fully_resolved"] is True
    winner = res["recommended_action"]
    assert winner["resolved"] is True
    assert winner["residual_violations_count"] == 0
    assert winner["rank"] == 1
    
    # Verify plain-English explanation mentions the action and why it was picked
    explanation = res["explanation"]
    assert winner["name"] in explanation or winner["action_type"] in explanation
    assert "resolved" in explanation.lower()


def test_api_violation_endpoints():
    """Verify FastAPI endpoints for scenarios, triggering violations, and evaluation."""
    from fastapi.testclient import TestClient
    from api import app

    client = TestClient(app)

    # 1. Scenarios list
    r_scen = client.get("/api/violations/scenarios")
    assert r_scen.status_code == 200
    scenarios = r_scen.json()["scenarios"]
    assert len(scenarios) >= 3

    # 2. Trigger violation
    r_trig = client.post("/api/violations/trigger", json={"scenario_id": "solar_spike"})
    assert r_trig.status_code == 200
    trig_data = r_trig.json()
    assert trig_data["status"] == "success"
    assert trig_data["violations"]["has_violations"] is True
    assert "topology" in trig_data
    assert len(trig_data["topology"]["buses"]) == 15

    # 3. Evaluate engine
    r_eval = client.post("/api/violations/evaluate", json={"scenario_id": "solar_spike"})
    assert r_eval.status_code == 200
    eval_data = r_eval.json()
    assert eval_data["actions_evaluated"] >= 10
    assert eval_data["recommended_action"] is not None
    assert "explanation" in eval_data
    assert "before_topology" in eval_data
    assert "after_topology" in eval_data

    # 4. Apply custom action
    r_act = client.post(
        "/api/violations/apply-custom-action",
        json={"scenario_id": "solar_spike", "action_type": "FEEDER_RECONFIGURATION", "switch_name": "S1"}
    )
    assert r_act.status_code == 200
    act_data = r_act.json()
    assert act_data["status"] == "success"
    assert "action" in act_data
    assert act_data["action"]["action_type"] == "FEEDER_RECONFIGURATION"
    assert "topology" in act_data

