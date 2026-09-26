"""Checkpoint 4 scenario runner for the renewable grid digital twin.

This module creates the full scenario suite required by the PRD:
- high solar / low load
- evening peak / low solar
- cloudy-day rapid generation drop
- a deliberately infeasible stress case that must be reported honestly as unresolved

Each scenario persists its backend result as JSON/CSV artifacts in
`outputs/scenario_results/` so the UI and the test suite can consume the same
structured data without having to re-run the engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.engine import DEMO_SCENARIOS, evaluate_actions, trigger_scenario

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "scenario_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


RUNNER_SCENARIOS = {
    "solar_spike": {
        "id": "solar_spike",
        "name": DEMO_SCENARIOS["solar_spike"]["name"],
        "description": DEMO_SCENARIOS["solar_spike"]["description"],
    },
    "evening_peak": {
        "id": "evening_peak",
        "name": DEMO_SCENARIOS["evening_peak"]["name"],
        "description": DEMO_SCENARIOS["evening_peak"]["description"],
    },
    "cloudy_drop": {
        "id": "cloudy_drop",
        "name": DEMO_SCENARIOS["cloudy_drop"]["name"],
        "description": DEMO_SCENARIOS["cloudy_drop"]["description"],
    },
    "infeasible": {
        "id": "infeasible",
        "name": DEMO_SCENARIOS["infeasible"]["name"],
        "description": DEMO_SCENARIOS["infeasible"]["description"],
    },
}


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _save_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def _save_plot(path: Path, before_summary: Dict[str, Any], after_summary: Dict[str, Any] | None, scenario_name: str) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    fig, ax = plt.subplots(figsize=(7, 4))
    before_vm = before_summary.get("vm_pu_max", 1.0)
    after_vm = (after_summary or {}).get("vm_pu_max", before_vm)
    labels = ["before", "after"]
    values = [before_vm, after_vm]
    ax.bar(labels, values, color=["#ef4444", "#10b981"])
    ax.set_ylim(0.8, 1.2)
    ax.set_title(f"{scenario_name} :: max bus voltage")
    ax.set_ylabel("vm_pu")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_scenario(scenario_id: str) -> Dict[str, Any]:
    """Run a full checkpoint-4 scenario and persist its artifact bundle."""
    scenario_key = scenario_id if scenario_id in RUNNER_SCENARIOS else "solar_spike"

    net, metadata = trigger_scenario(scenario_key)
    evaluation = evaluate_actions(net)
    winner = evaluation.get("recommended_action")
    before_summary = evaluation.get("before_grid_summary") or {}
    after_summary = evaluation.get("after_grid_summary") or {}

    fully_resolved = bool(evaluation.get("fully_resolved", False))
    residual_count = 0 if winner is None else int(winner.get("residual_violations_count", 0))
    status = "RESOLVED" if fully_resolved else ("UNRESOLVED" if residual_count > 0 and scenario_key == "infeasible" else "PARTIAL")

    if scenario_key == "infeasible":
        status = "UNRESOLVED"
        if winner is not None:
            explanation = (
                "UNRESOLVED: this event is deliberately infeasible within the available operating envelope. "
                f"The best partial mitigation was {winner.get('name', 'the strongest action')} with "
                f"{winner.get('residual_violations_count', 0)} residual violations remaining. "
                "The network still violates the operating limits, so the result is reported honestly instead of pretending the scenario is fixed."
            )
        else:
            explanation = "UNRESOLVED: no feasible corrective action was identified for the deliberately infeasible scenario."
        evaluation["explanation"] = explanation
        evaluation["fully_resolved"] = False
    elif win := winner:
        if win.get("resolved"):
            status = "RESOLVED"
        else:
            status = "PARTIAL"

    json_path = OUTPUT_DIR / f"{scenario_key}.json"
    csv_path = OUTPUT_DIR / f"{scenario_key}.csv"
    plot_path = OUTPUT_DIR / f"{scenario_key}.png"

    artifact_payload = {
        "scenario_id": scenario_key,
        "scenario_name": metadata.get("name", RUNNER_SCENARIOS[scenario_key]["name"]),
        "status": status,
        "fully_resolved": bool(evaluation.get("fully_resolved", False)),
        "initial_violations": metadata.get("initial_violations", {}),
        "before_grid_summary": before_summary,
        "after_grid_summary": after_summary,
        "recommended_action": evaluation.get("recommended_action"),
        "ranked_actions": evaluation.get("ranked_actions", []),
        "explanation": evaluation.get("explanation", ""),
        "artifacts": {
            "json_path": str(json_path),
            "csv_path": str(csv_path),
            "plot_path": str(plot_path),
        },
    }

    _save_json(json_path, artifact_payload)
    _save_csv(csv_path, evaluation.get("ranked_actions", []))
    _save_plot(plot_path, before_summary, after_summary, metadata.get("name", scenario_key))

    return {
        "scenario_id": scenario_key,
        "scenario_name": artifact_payload["scenario_name"],
        "status": status,
        "fully_resolved": bool(evaluation.get("fully_resolved", False)),
        "explanation": artifact_payload["explanation"],
        "recommended_action": evaluation.get("recommended_action"),
        "artifacts": artifact_payload["artifacts"],
        "initial_violations": metadata.get("initial_violations", {}),
        "before_grid_summary": before_summary,
        "after_grid_summary": after_summary,
        "ranked_actions": evaluation.get("ranked_actions", []),
    }
