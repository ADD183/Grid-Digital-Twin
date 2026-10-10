"""Focused tests for surrogate screening and the eight-step MPC controller."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone

from backend.app.agent_orchestrator import AssistantOrchestrator, search_project_knowledge
from backend.app.artifact_exporter import ArtifactExporter
from backend.app.config import Settings
from backend.app.mpc_engine import BatteryLimits, MpcEngine
from backend.app.schemas import AssistantRequest, MpcPlan, MpcStepResult, SolverResult
from backend.app.surrogate import FEATURE_COLUMNS, PowerFlowSurrogate


def test_surrogate_training_inference_ood_and_reload(tmp_path):
    features = pd.DataFrame(
        np.linspace(0.1, 0.8, 120).reshape(20, len(FEATURE_COLUMNS)),
        columns=FEATURE_COLUMNS,
    )
    voltages = np.column_stack(
        [0.94 + features.solar_mw.to_numpy() * 0.04, 1.02 - features.load_mw.to_numpy() * 0.01]
    )
    loadings = np.column_stack(
        [30 + features.load_mw.to_numpy() * 50, 20 + features.solar_mw.to_numpy() * 40]
    )
    model_path = tmp_path / "surrogate.joblib"
    model = PowerFlowSurrogate()

    metrics = model.train(
        features,
        voltages,
        loadings,
        voltage_bus_ids=[4, 7],
        line_ids=[1, 2],
        save_path=model_path,
    )
    loaded = PowerFlowSurrogate.load(model_path)
    in_range = features.iloc[5].to_dict()

    assert metrics["train_samples"] == 16
    assert metrics["validation_samples"] == 4
    assert metrics["voltage_mae_pu"] >= 0
    assert loaded.predict_fast(in_range)["status"] == "PREDICTION"
    assert loaded.predict_fast({**in_range, "solar_mw": 10_000})["status"] == "OOD_FALLBACK_REQUIRED"


def test_mpc_soc_uses_energy_balance_and_bounds():
    controller = MpcEngine(battery=BatteryLimits(capacity_mwh=4.0, step_hours=0.25))

    next_soc = controller._advance_soc(2.0, charge_mw=1.0, discharge_mw=0.5)

    expected = 2.0 + (1.0 * 0.95 - 0.5 / 0.95) * 0.25
    assert next_soc == pytest.approx(expected)
    with pytest.raises(ValueError, match="SoC limits"):
        controller._advance_soc(4.0, charge_mw=1.0, discharge_mw=0.0)


def test_mpc_rejects_non_eight_step_horizon():
    with pytest.raises(ValueError, match="exactly eight"):
        MpcEngine().plan([{"solar_mw": 2.0, "load_mw": 5.0}])


def test_mpc_sends_entire_step_to_solver_if_any_candidate_is_ood():
    class OodSurrogate:
        is_fitted = True

        @staticmethod
        def predict_fast(_inputs):
            return {"status": "OOD_FALLBACK_REQUIRED", "reason": "outside training range"}

    class SafeVerifier:
        from backend.app.config import get_settings

        settings = get_settings()

        def __init__(self):
            self.calls = 0

        def run_power_flow(self, **_inputs):
            self.calls += 1
            return SolverResult(converged=True, is_safe=True, bus_voltages_pu={0: 1.0})

    verifier = SafeVerifier()
    forecasts = [{"solar_mw": 2.0, "load_mw": 5.0} for _ in range(8)]

    plan = MpcEngine(verifier=verifier, surrogate=OodSurrogate()).plan(forecasts)

    assert verifier.calls == 8
    assert all(not step.surrogate_used for step in plan.steps)
    assert all("outside training range" in step.surrogate_fallback_reason for step in plan.steps)


def test_mpc_runs_and_verifies_eight_steps():
    forecasts = [{"solar_mw": 0.21, "load_mw": 25.0} for _ in range(8)]

    plan = MpcEngine().plan(forecasts, initial_state_of_charge_mwh=2.0)

    assert len(plan.steps) == 8
    assert [step.step for step in plan.steps] == list(range(1, 9))
    assert all(step.solver.converged for step in plan.steps)
    assert 0.0 <= plan.final_state_of_charge_mwh <= 4.0
    assert all(not step.surrogate_used for step in plan.steps)


def test_project_knowledge_search_finds_definition_excerpt():
    result = search_project_knowledge("What is curtailment?")

    assert result["matches"]
    assert "curtailment" in result["matches"][0]["excerpt"].lower()
    assert any(word in result["matches"][0]["excerpt"].lower() for word in ("reducing", "reduce"))


def test_scenario_list_fallback_uses_registered_ids():
    assistant = AssistantOrchestrator(Settings(openrouter_api_key=None))

    answer = assistant.answer(AssistantRequest(message="What scenarios can I run?"))

    assert answer["used_tools"] == ["list_available_scenarios"]
    assert set(answer["evidence"]["list_available_scenarios"]) == {
        "solar_spike",
        "evening_peak",
        "cloudy_drop",
        "infeasible",
    }


def test_assistant_declines_questions_outside_approved_project_sources():
    assistant = AssistantOrchestrator(Settings(openrouter_api_key=None))

    answer = assistant.answer(AssistantRequest(message="What is the capital of France?"))

    assert "only answer questions about VoltPredict" in answer["reply"]
    assert answer["evidence"]["search_project_knowledge"]["matches"] == []


def test_provider_empty_final_answer_uses_grounded_fallback(monkeypatch):
    import langchain_openai

    class FakeResponse:
        def __init__(self, content="", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    class FakeChatModel:
        def __init__(self, **_kwargs):
            self.responses = [
                FakeResponse(
                    tool_calls=[
                        {
                            "name": "list_available_scenarios",
                            "args": {},
                            "id": "call-scenarios",
                        }
                    ]
                ),
                FakeResponse(content=""),
            ]

        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            return self.responses.pop(0)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatModel)
    settings = Settings(openrouter_api_key="test-key")
    answer = AssistantOrchestrator(settings).answer(
        AssistantRequest(message="What scenarios can I run?")
    )

    assert "available saved scenarios" in answer["reply"].lower()
    assert answer["used_tools"] == ["list_available_scenarios"]
    assert "provider_error" not in answer


def test_provider_tool_call_then_synthesis_returns_tool_evidence(monkeypatch):
    import langchain_openai

    class FakeResponse:
        def __init__(self, content="", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    class FakeChatModel:
        def __init__(self, **_kwargs):
            self.responses = [
                FakeResponse(
                    tool_calls=[
                        {
                            "name": "list_available_scenarios",
                            "args": {},
                            "id": "call-scenarios",
                        }
                    ]
                ),
                FakeResponse(content="VoltPredict has four saved scenarios."),
            ]

        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            return self.responses.pop(0)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatModel)
    settings = Settings(openrouter_api_key="test-key")
    answer = AssistantOrchestrator(settings).answer(
        AssistantRequest(message="What scenarios can I run?", audience_mode="executive")
    )

    assert answer["reply"] == "VoltPredict has four saved scenarios."
    assert answer["used_tools"] == ["list_available_scenarios"]
    assert answer["evidence"]["list_available_scenarios"]


def test_no_key_operator_grid_answer_includes_telemetry_and_solver_evidence():
    assistant = AssistantOrchestrator(Settings(openrouter_api_key=None))

    answer = assistant.answer(AssistantRequest(message="Is the grid safe right now?"))

    assert answer["audience_mode"] == "operator"
    assert "get_telemetry_status" in answer["used_tools"]
    assert "verify_state_with_solver" in answer["used_tools"]
    assert answer["evidence"]["verify_state_with_solver"]["converged"] is True


def test_exporter_writes_all_requested_artifacts_atomically(tmp_path):
    features = pd.DataFrame(
        np.linspace(0.1, 0.8, 120).reshape(20, len(FEATURE_COLUMNS)),
        columns=FEATURE_COLUMNS,
    )
    voltages = np.column_stack([0.98 + features.solar_mw.to_numpy() * 0.01])
    loadings = np.column_stack([30 + features.load_mw.to_numpy() * 10])
    settings = Settings(
        artifacts_dir=tmp_path / "artifacts",
        surrogate_model_path=tmp_path / "backend" / "models" / "surrogate.joblib",
    )
    surrogate = PowerFlowSurrogate(settings)
    surrogate.train(features, voltages, loadings, voltage_bus_ids=[2], line_ids=[4])
    solver = SolverResult(
        converged=True,
        is_safe=True,
        min_voltage_pu=0.98,
        max_voltage_pu=1.01,
        max_line_loading_percent=50.0,
        bus_voltages_pu={2: 0.98},
        line_loadings_percent={4: 50.0},
    )
    timestamp = datetime.now(timezone.utc)
    steps = [
        MpcStepResult(
            step=index,
            timestamp=timestamp,
            state_of_charge_mwh=2.0,
            solar_forecast_mw=1.0,
            load_forecast_mw=5.0,
            curtailment_fraction=0,
            battery_charge_mw=0,
            battery_discharge_mw=0,
            load_shed_mw=0,
            solver=solver,
        )
        for index in range(1, 9)
    ]
    plan = MpcPlan(
        run_id="test-run",
        horizon_steps=8,
        step_minutes=15,
        initial_state_of_charge_mwh=2.0,
        final_state_of_charge_mwh=2.0,
        fully_resolved=True,
        steps=steps,
        explanation="Test plan",
    )

    result = ArtifactExporter(settings).export(
        surrogate=surrogate,
        plan=plan,
        features=features,
        voltages=voltages,
        loadings=loadings,
    )

    expected_names = {"benchmark", "mpc_trace", "model", "train_set", "test_set"}
    assert set(result["artifacts"]) == expected_names
    assert (tmp_path / "artifacts" / "surrogate_lgb_v1.pkl").is_file()
    assert (tmp_path / "artifacts" / "surrogate_vs_solver_benchmarks.json").is_file()
    assert (tmp_path / "artifacts" / "mpc_execution_trace_t8.json").is_file()
    assert len(pd.read_csv(tmp_path / "artifacts" / "train_set.csv")) == 16
    assert len(pd.read_csv(tmp_path / "artifacts" / "test_set.csv")) == 4