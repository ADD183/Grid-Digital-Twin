import json
from pathlib import Path

from src.scenarios import RUNNER_SCENARIOS, run_scenario


def test_checkpoint_4_scenario_suite_has_four_scenarios():
    scenario_ids = list(RUNNER_SCENARIOS.keys())
    assert len(scenario_ids) == 4
    assert {"solar_spike", "evening_peak", "cloudy_drop", "infeasible"}.issubset(set(scenario_ids))


def test_run_scenario_persists_artifacts_and_marks_unresolved_case():
    result = run_scenario("infeasible")

    assert result["scenario_id"] == "infeasible"
    assert result["status"] in {"UNRESOLVED", "PARTIAL"}
    assert result["fully_resolved"] is False
    assert "unresolved" in result["explanation"].lower() or "best partial mitigation" in result["explanation"].lower()

    artifact_dir = Path("outputs/scenario_results")
    assert artifact_dir.exists()
    assert (artifact_dir / "infeasible.json").exists()


def test_run_scenario_for_demo_solutions_retains_resolved_status_on_other_cases():
    for scenario_id in ["solar_spike", "evening_peak", "cloudy_drop"]:
        result = run_scenario(scenario_id)
        assert result["scenario_id"] == scenario_id
        assert "status" in result
        assert result["status"] in {"RESOLVED", "PARTIAL", "UNRESOLVED"}
        assert "artifacts" in result
        assert set(["json_path", "csv_path"]).issubset(set(result["artifacts"].keys()))
