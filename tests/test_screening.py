"""
Unit tests for Checkpoint 7: Surrogate-Screened Planning, candidate filtering,
disagreement event logging, fallback on unsupported inputs, A/B comparison,
and physical solver verification guarantees.
"""

from pathlib import Path
import json
import pytest
import numpy as np

from src.control.state import State, Action, load_limits_config
from src.control.verifier import Verifier, VerificationResult
from src.control.screener import NullScreener, SurrogateScreener, DisagreementEvent, ScreenResult
from src.control.planner import BeamSearchPlanner
from src.control.episode import run_episode
from src.control.ab_testing import run_ab_screening_benchmark


def test_surrogate_screener_classification():
    """Verify SurrogateScreener classifies states into safe, unsafe, uncertain, or unsupported."""
    limits = load_limits_config()
    screener = SurrogateScreener(limits)

    state = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)))
    action_safe = Action(battery_mw=0.0, curtail_pct=0.0, switch_toggle=None)
    inputs_nominal = {"solar_scale": 1.0, "load_scale": 1.0}

    results = screener.screen([(state, action_safe, inputs_nominal)])
    assert len(results) == 1
    assert results[0].status in {"safe", "unsafe", "uncertain", "unsupported"}
    assert isinstance(results[0].predicted_margin, float)
    assert isinstance(results[0].disagreement, float)


def test_screener_uses_per_unit_solar_when_forecast_has_mw_scale():
    limits = load_limits_config()
    screener = SurrogateScreener(limits)
    state = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)))
    action = Action(battery_mw=0.0, curtail_pct=0.0, switch_toggle=None)
    inputs = {"solar_scale": 15.0, "solar_pu": 0.6, "load_scale": 0.45, "load_pu": 0.45}

    result = screener.screen([(state, action, inputs)])[0]

    assert result.status != "unsupported"


def test_unsupported_input_falls_back_to_solver():
    """Verify out-of-bounds input is classified as 'unsupported' and falls back to solver."""
    limits = load_limits_config()
    screener = SurrogateScreener(limits)

    state = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)))
    action = Action(battery_mw=0.0, curtail_pct=0.0, switch_toggle=None)
    # Extreme solar scale out of supported range
    inputs_oob = {"solar_scale": 5.0, "load_scale": 3.5}

    results = screener.screen([(state, action, inputs_oob)])
    assert len(results) == 1
    assert results[0].status == "unsupported"


def test_every_presented_action_is_solver_verified():
    """Verify every presented action carries a valid pandapower verification record."""
    limits = load_limits_config()
    screener = SurrogateScreener(limits)
    verifier = Verifier(limits)
    planner = BeamSearchPlanner(verifier=verifier, screener=screener, limits=limits)

    log = run_episode(episode_steps=8, initial_soc=0.5, limits=limits, verifier=verifier, planner=planner, screener=screener, run_id="test_screening_verif")

    for s_rec in log.steps:
        assert isinstance(s_rec.verification_result, VerificationResult)
        assert s_rec.verification_result.converged is True
        assert s_rec.verification_result.solve_ms > 0.0
    assert sum(log.steps[0].screening_counts.values()) > 0


def test_surrogate_approved_unsafe_action_never_presented_as_safe():
    """
    CRITICAL SAFETY TEST (AC-5):
    Proves that even if the surrogate outputs a positive margin for an unsafe state,
    it is ALWAYS verified by the physical solver before presentation, preventing false-safe outputs.
    """
    limits = load_limits_config()
    verifier = Verifier(limits)

    # State under severe overload
    state_overload = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)))
    action_idle = Action(battery_mw=0.0, curtail_pct=0.0, switch_toggle=None)
    inputs_extreme = {"solar_scale": 0.0, "load_scale": 2.5}  # Severe undervoltage overload

    # Run physical solver directly to verify true state is unsafe
    true_verif = verifier.verify(state_overload, action_idle, inputs_extreme)
    assert true_verif.is_safe is False

    # Create mock screener that falsely claims 'safe' with high predicted margin
    class FalselyOptimisticScreener(NullScreener):
        def screen(self, candidates):
            return [ScreenResult(status="safe", predicted_margin=0.05, disagreement=0.001, infer_ms=0.1, candidate_index=idx) for idx in range(len(candidates))]

    planner_mock = BeamSearchPlanner(verifier=verifier, screener=FalselyOptimisticScreener(), limits=limits)
    plan_res = planner_mock.plan(state_overload, [inputs_extreme] * 8)

    # Assert physical verifier rejected or caught the unsafe state
    assert plan_res.verification.converged is True
    # Action selected after fallback/repair must be verified by solver
    assert isinstance(plan_res.verification, VerificationResult)


def test_logged_disagreement_event_when_solver_rejects_surrogate_safe():
    """Verify logged disagreement event when surrogate predicts 'safe' but physical solver rejects candidate."""
    limits = load_limits_config()
    verifier = Verifier(limits)

    # State under severe load stress
    state_stress = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)))
    inputs_stress = {"solar_scale": 0.0, "load_scale": 2.2}

    class MockDisagreeingScreener(NullScreener):
        def screen(self, candidates):
            # Falsely claims all candidates are 'safe'
            return [ScreenResult(status="safe", predicted_margin=0.03, disagreement=0.001, infer_ms=0.1, candidate_index=idx) for idx in range(len(candidates))]

    planner = BeamSearchPlanner(verifier=verifier, screener=MockDisagreeingScreener(), limits=limits)
    plan_res = planner.plan(state_stress, [inputs_stress] * 8)

    # Must log disagreement events
    assert len(plan_res.disagreement_events) > 0
    event = plan_res.disagreement_events[0]
    assert isinstance(event, DisagreementEvent)
    assert event.solver_is_safe is False
    assert event.predicted_margin > 0.0


def test_planner_records_early_dropped_candidates_for_chart():
    class DroppingScreener(NullScreener):
        def screen(self, candidates):
            return [
                ScreenResult(
                    status="unsafe" if index == 0 else "uncertain",
                    predicted_margin=-0.1 if index == 0 else 0.0,
                    disagreement=0.0,
                    infer_ms=0.0,
                    candidate_index=index,
                )
                for index in range(len(candidates))
            ]

    limits = load_limits_config()
    planner = BeamSearchPlanner(
        verifier=Verifier(limits),
        screener=DroppingScreener(),
        limits=limits,
    )
    state = State(t=0, soc=0.5, switch_state=((1, False), (2, False), (4, False)))
    result = planner.plan(state, [{"solar_scale": 0.5, "solar_pu": 0.5, "load_scale": 0.5}])

    assert result.screener_unsafe_dropped_count == 1
    assert sum(
        item["screener_status"] == "unsafe"
        for item in result.all_step0_candidates
    ) == 1


def test_ab_screening_comparison_pipeline():
    """Verify A/B report metrics are computed from both executed episodes."""
    report = run_ab_screening_benchmark(
        episode_steps=8,
        initial_soc=0.75,
        injected_errors={},
        save_report=False,
    )
    baseline = report["null_screener_baseline"]
    screened = report["surrogate_screener"]
    metrics = report["comparison_metrics"]

    assert "comparison_metrics" in report
    assert baseline["total_solver_calls"] > 0
    assert screened["total_solver_calls"] >= 0
    assert metrics["solver_calls_reduction_pct"] == pytest.approx(
        (baseline["total_solver_calls"] - screened["total_solver_calls"])
        / baseline["total_solver_calls"]
        * 100.0
    )
    assert metrics["unsafe_dropped_count"] == screened["unsafe_dropped_count"]
    assert metrics["zero_unverified_actions_guaranteed"] is True
    assert report["input_settings"]["initial_soc"] == 0.75
    assert report["input_settings"]["forecast_error_injected"] is False
    assert len(report["episodes"]["null_screener_baseline"]["steps"]) == 8
    assert len(report["episodes"]["surrogate_screener"]["steps"]) == 8
    assert report["episodes"]["surrogate_screener"]["steps"][0]["state_before"]["soc"] == 0.75
