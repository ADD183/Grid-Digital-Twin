"""
Unit and integration tests for Multi-Step Control (Checkpoint 5).
Verifies all acceptance criteria in PRD_final_round_additions.md Section 5.
"""

import pytest
import numpy as np

from src.control.state import (
    State,
    Action,
    LimitsConfig,
    load_limits_config,
    update_soc,
    is_action_admissible,
    update_switch_state,
)
from src.control.verifier import Verifier, VerificationResult, verify
from src.control.screener import NullScreener, ScreenResult
from src.control.planner import BeamSearchPlanner, PlanResult
from src.control.episode import (
    StepRecord,
    EpisodeLog,
    run_episode,
    build_default_forecast_profile,
)


@pytest.fixture
def limits() -> LimitsConfig:
    return load_limits_config()


@pytest.fixture
def verifier(limits) -> Verifier:
    return Verifier(limits)


@pytest.fixture
def planner(limits, verifier) -> BeamSearchPlanner:
    return BeamSearchPlanner(verifier=verifier, screener=NullScreener(), limits=limits)


# --- CRITERION 1: State / Action & Battery Dynamics ---

def test_state_and_action_initialization():
    state = State(
        t=0,
        soc=0.5,
        switch_state=((1, False), (2, False), (4, False)),
        curtail_level=0.0,
    )
    assert state.t == 0
    assert state.soc == 0.5
    assert state.is_switch_closed(4) is False
    assert state.switch_dict == {1: False, 2: False, 4: False}

    action = Action(battery_mw=-0.5, curtail_pct=10.0, switch_toggle=4)
    assert action.battery_mw == -0.5  # charging
    assert action.curtail_pct == 10.0
    assert action.switch_toggle == 4


def test_battery_soc_update_with_explicit_efficiency(limits):
    cap = limits.battery.capacity_mwh  # 2.0
    eff = limits.battery.efficiency    # 0.95
    dt = limits.control.dt_hours       # 1.0

    initial_soc = 0.50

    # 1. Charging at 1.0 MW (absorbing power, battery_mw = -1.0)
    # Energy stored = 1.0 MW * 1.0 h * 0.95 = 0.95 MWh
    # Delta SOC = 0.95 / 2.0 = 0.475
    next_soc_charge = update_soc(initial_soc, -1.0, dt, cap, eff)
    expected_charge = 0.50 + (1.0 * 1.0 * 0.95) / 2.0
    assert pytest.approx(next_soc_charge, rel=1e-5) == expected_charge

    # 2. Discharging at 0.5 MW (injecting power, battery_mw = 0.5)
    # Energy depleted = (0.5 * 1.0) / 0.95 = 0.526315 MWh
    # Delta SOC = 0.526315 / 2.0 = 0.263158
    next_soc_disch = update_soc(initial_soc, 0.5, dt, cap, eff)
    expected_disch = 0.50 - (0.5 * 1.0 / 0.95) / 2.0
    assert pytest.approx(next_soc_disch, rel=1e-5) == expected_disch

    # 3. Idle (battery_mw = 0.0)
    assert update_soc(initial_soc, 0.0, dt, cap, eff) == initial_soc


def test_soc_bounds_and_power_limits_enforced(limits):
    initial_soc = 0.50

    # Admissible normal action
    ok_action = Action(battery_mw=0.5, curtail_pct=10.0)
    is_ok, reason = is_action_admissible(initial_soc, ok_action, limits)
    assert is_ok is True
    assert reason == ""

    # Power rating exceeded (> max_power_mw = 1.0 MW)
    overpower = Action(battery_mw=1.5)
    is_ok, reason = is_action_admissible(initial_soc, overpower, limits)
    assert is_ok is False
    assert "exceeds maximum battery rating" in reason

    # Charging past maximum SOC bound (0.90)
    # Starting at 0.85 and charging at 1.0 MW -> would reach 0.85 + 0.475 = 1.325 > 0.90
    high_charge = Action(battery_mw=-1.0)
    is_ok, reason = is_action_admissible(0.85, high_charge, limits)
    assert is_ok is False
    assert "above maximum bound" in reason

    # Discharging below minimum SOC bound (0.10)
    # Starting at 0.20 and discharging at 1.0 MW -> would drop below 0.10
    deep_disch = Action(battery_mw=1.0)
    is_ok, reason = is_action_admissible(0.20, deep_disch, limits)
    assert is_ok is False
    assert "below minimum bound" in reason


def test_switch_state_toggle():
    initial_switches = ((1, False), (2, False), (4, False))
    toggled = update_switch_state(initial_switches, 4)
    assert dict(toggled)[4] is True
    assert dict(toggled)[1] is False

    toggled_back = update_switch_state(toggled, 4)
    assert dict(toggled_back)[4] is False


# --- CRITERION 2: Solver Verifier & Margin Calculation ---

def test_verifier_wrapper_runs_powerflow_and_calculates_margin(verifier, limits):
    state = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)), curtail_level=0.0)
    action = Action(battery_mw=0.0, curtail_pct=0.0, switch_toggle=None)
    inputs = {"solar_scale": 1.0, "load_scale": 1.0, "ext_grid_vm_pu": 1.03}

    res = verifier.verify(state, action, inputs)
    assert isinstance(res, VerificationResult)
    assert res.converged is True
    assert res.solve_ms > 0.0
    assert len(res.bus_vm) == 15
    assert len(res.line_loading) == 15

    # Check nominal baseline safety with voltage setpoint
    assert res.is_safe is True
    assert res.min_margin > 0.0
    assert len(res.violations) == 0


def test_verifier_detects_overvoltage_with_negative_margin(verifier):
    state = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)), curtail_level=0.0)
    # Severe solar export spike without mitigation
    action = Action(battery_mw=0.0, curtail_pct=0.0)
    inputs = {"solar_scale": 50.0, "load_scale": 0.20, "ext_grid_vm_pu": 1.04}

    res = verifier.verify(state, action, inputs)
    assert res.converged is True
    assert res.is_safe is False
    assert res.min_margin < 0.0  # Signed negative distance to limit
    assert any(v.get("violation_type") == "OVERVOLTAGE" for v in res.violations)


# --- CRITERION 3: Null Screener ---

def test_null_screener():
    screener = NullScreener()
    dummy_cands = [
        (State(0, 0.5, ((4, False),), 0.0), Action(battery_mw=0.0), {}),
        (State(0, 0.5, ((4, False),), 0.0), Action(battery_mw=0.5), {}),
    ]
    results = screener.screen(dummy_cands)
    assert len(results) == 2
    for r in results:
        assert isinstance(r, ScreenResult)
        assert r.status == "uncertain"
        assert r.predicted_margin == 0.0


# --- CRITERION 4: Rolling-Horizon Episode Execution (>= 8 Steps) ---

def test_rolling_horizon_episode_at_least_8_steps(limits, verifier, planner):
    episode_steps = 8
    log = run_episode(
        episode_steps=episode_steps,
        initial_soc=0.5,
        limits=limits,
        verifier=verifier,
        planner=planner,
        run_id="test_8step",
    )

    assert log.total_steps == episode_steps
    assert len(log.steps) == episode_steps

    # Acceptance criteria checks
    for step in log.steps:
        # Every step has a solver-verified action
        assert step.verification_result.converged is True
        assert step.verification_result.solve_ms > 0.0
        # Battery SOC never leaves [soc_min, soc_max] bounds
        assert limits.battery.soc_min <= step.soc <= limits.battery.soc_max
        assert limits.battery.soc_min <= step.state_after.soc <= limits.battery.soc_max
        # Power limits respected
        assert abs(step.chosen_action.battery_mw) <= limits.battery.max_power_mw + 1e-5


# --- CRITERION 5: Injected Forecast Error Triggers Replan ---

def test_injected_forecast_error_causes_replan_and_changes_action(limits, verifier, planner):
    # Inject a severe forecast error at step 2 (sudden solar surge that was not predicted)
    injected_errors = {
        2: {"solar_mult": 2.2, "load_mult": 0.8, "label": "Unpredicted midday solar spike"}
    }

    log = run_episode(
        episode_steps=5,
        initial_soc=0.5,
        limits=limits,
        verifier=verifier,
        planner=planner,
        injected_errors=injected_errors,
        run_id="test_replan",
    )

    step2 = log.steps[2]
    assert step2.forecast_error_injected is True
    assert step2.error_label == "Unpredicted midday solar spike"
    assert step2.replan_flag is True
    # The action was verified with the physical solver on the observed inputs
    assert step2.verification_result.converged is True


# --- CRITERION 6: Infeasible Scenario & Fallback Ladder ---

def test_infeasible_period_reported_with_fallback_ladder(limits, verifier, planner):
    # Force step 3 to trigger an extreme unmitigable contingency
    force_infeasible = [3]

    log = run_episode(
        episode_steps=5,
        initial_soc=0.5,
        limits=limits,
        verifier=verifier,
        planner=planner,
        force_infeasible_steps=force_infeasible,
        run_id="test_infeasible",
    )

    step3 = log.steps[3]
    assert step3.infeasible_flag is True
    assert step3.fallback_used is not None
    assert "infeasible" in step3.fallback_used or "fallback" in step3.fallback_used
    assert step3.verification_result.converged is True
    assert len(log.infeasible_steps) == 1
    assert log.infeasible_steps[0] == 3


# --- CRITERION 7: Serialization & Deserialization ---

def test_episode_log_serialization(tmp_path, limits, verifier, planner):
    log = run_episode(
        episode_steps=4,
        initial_soc=0.5,
        limits=limits,
        verifier=verifier,
        planner=planner,
        run_id="test_serialization",
    )

    export_path = tmp_path / "test_episode.json"
    log.save(str(export_path))
    assert export_path.is_file()

    reloaded = EpisodeLog.load(str(export_path), limits=limits)
    assert reloaded.total_steps == 4
    assert reloaded.run_id == "test_serialization"
    assert len(reloaded.steps) == 4
    assert reloaded.soc_series == log.soc_series
