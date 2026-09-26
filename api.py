"""
FastAPI REST API Server for the Renewable Grid Digital Twin.
Exposes backend grid topology, power flow calculation results, and time-series solar/load data to the React.js frontend.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
import pandas as pd
import os

from pydantic import BaseModel, Field

from src.grid import load_cigre_network, run_baseline_powerflow, get_grid_summary, get_network_element_dfs
from src.data_pipeline import build_aligned_dataset
from src.forecast import get_forecast_chart_data, train_all_models
from src.actions import apply_battery_dispatch, apply_curtailment, apply_feeder_reconfiguration
from src.engine import DEMO_SCENARIOS, evaluate_actions, trigger_scenario
from src.scenarios import run_scenario
from src.violations import check_grid_violations

app = FastAPI(
    title="Renewable Grid Digital Twin API",
    description="REST API serving pandapower grid simulations and PVGIS solar/demand datasets",
    version="1.0.0"
)

# Enable CORS for React frontend (Vite default port 5173 / localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_topology(net) -> Dict[str, Any]:
    """Serialize network elements (buses, lines, static generators) formatted for UI rendering."""
    bus_df, line_df, sgen_df = get_network_element_dfs(net)

    buses = []
    for idx, row in bus_df.iterrows():
            buses.append({
                "id": int(str(idx)),
            "name": str(row.get("name", f"Bus {idx}")),
            "vm_pu": round(float(row.get("vm_pu", 1.0)), 4),
            "va_degree": round(float(row.get("va_degree", 0.0)), 2),
            "p_mw": round(float(row.get("p_mw", 0.0)), 3),
            "q_mvar": round(float(row.get("q_mvar", 0.0)), 3),
            "x": round(float(row.get("x", 0.0)), 2),
            "y": round(float(row.get("y", 0.0)), 2),
            "vn_kv": round(float(row.get("vn_kv", 15.0)), 1)
        })

    lines = []
    for idx, row in line_df.iterrows():
        lines.append({
            "id": int(str(idx)),
            "name": str(row.get("name", f"Line {idx}")),
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
    if not sgen_df.empty:
        for idx, row in sgen_df.iterrows():
            sgens.append({
                "id": int(str(idx)),
                "name": str(row.get("name", f"DER {idx}")),
                "bus": int(row["bus"]),
                "p_mw": round(float(row.get("p_mw", 0.0)), 3),
                "q_mvar": round(float(row.get("q_mvar", 0.0)), 3),
                "type": str(row.get("type", "PV"))
            })

    return {
        "buses": buses,
        "lines": lines,
        "sgens": sgens
    }


@app.get("/api/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0", "system": "Renewable Grid Digital Twin API"}


@app.get("/api/grid/summary")
def get_summary() -> Dict[str, Any]:
    """Return summary metrics for the baseline CIGRE MV grid power flow."""
    try:
        net = load_cigre_network()
        run_baseline_powerflow(net)
        summary = get_grid_summary(net)
        violations = check_grid_violations(net)
        summary["violations"] = violations
        return summary
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/grid/topology")
def get_topology() -> Dict[str, Any]:
    """Return network topology elements (buses, lines, static generators) formatted for UI rendering."""
    try:
        net = load_cigre_network()
        run_baseline_powerflow(net)
        return serialize_topology(net)
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/data/solar-load")
def get_solar_load_data(
    start_date: str = Query("2023-01-01", description="Start date ISO YYYY-MM-DD"),
    end_date: str = Query("2023-01-31", description="End date ISO YYYY-MM-DD")
) -> List[Dict[str, Any]]:
    """
    Return time-aligned hourly Pune solar generation and synthetic demand data
    for the specified date range (supports single or multi-month selection).
    """
    try:
        aligned_df = build_aligned_dataset(start_date=start_date, end_date=end_date)
        records = []
        for idx, row in aligned_df.iterrows():
            records.append({
                "timestamp": pd.Timestamp(str(idx)).strftime("%Y-%m-%d %H:%M"),
                "solar_ghi": round(float(row.get("solar_ghi", 0.0)), 2),
                "solar_pu": round(float(row.get("solar_pu", 0.0)), 4),
                "load_kw": round(float(row.get("load_kw", 0.0)), 2),
                "load_pu": round(float(row.get("load_pu", 0.0)), 4)
            })
        return records
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/forecast/chart")
def get_forecast_chart(
    points: int = Query(168, ge=1, le=8760, description="Maximum number of recent hourly evaluation points")
) -> Dict[str, Any]:
    """Return cached or freshly trained forecast evaluation data for the UI."""
    try:
        return get_forecast_chart_data(max_points=points)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Unable to load forecast data: {err}")


@app.post("/api/forecast/train")
def retrain_forecast_models() -> Dict[str, Any]:
    """Retrain and persist both forecast models, then return their summary metrics."""
    try:
        result = train_all_models(save=True)
        return {"status": "success", "summary": result["summary"]}
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Unable to train forecast models: {err}")


class ScenarioRequest(BaseModel):
    scenario_id: str = "solar_spike"


class CustomActionRequest(ScenarioRequest):
    action_type: str
    curtailment_pct: float = Field(default=50.0, ge=0.0, le=100.0)
    battery_p_mw: float = Field(default=1.5, ge=-2.0, le=2.0)
    battery_bus: int = 5
    switch_name: str = "S1"


@app.get("/api/violations/scenarios")
def get_violation_scenarios() -> Dict[str, Any]:
    """Return the selectable Checkpoint 3 violation scenarios."""
    return {"scenarios": list(DEMO_SCENARIOS.values())}


@app.post("/api/violations/trigger")
def trigger_violation_scenario(request: ScenarioRequest) -> Dict[str, Any]:
    """Trigger a scenario and return its violated topology for the control room."""
    try:
        net, metadata = trigger_scenario(request.scenario_id)
        return {
            "status": "success",
            "scenario": metadata,
            "violations": metadata["initial_violations"],
            "topology": serialize_topology(net),
        }
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.post("/api/violations/evaluate")
def evaluate_violation_scenario(request: ScenarioRequest) -> Dict[str, Any]:
    """Run the corrective-action engine for a selected scenario."""
    try:
        net, _ = trigger_scenario(request.scenario_id)
        result = evaluate_actions(net)
        result["before_topology"] = serialize_topology(net)
        return result
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.post("/api/scenarios/run")
def run_violation_scenario(request: ScenarioRequest) -> Dict[str, Any]:
    """Run the full checkpoint-4 scenario pipeline and persist its artifacts."""
    try:
        return run_scenario(request.scenario_id)
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.post("/api/violations/apply-custom-action")
def apply_custom_violation_action(request: CustomActionRequest) -> Dict[str, Any]:
    """Apply one user-selected action to a triggered scenario and return its result."""
    try:
        net, _ = trigger_scenario(request.scenario_id)
        if request.action_type == "CURTAILMENT":
            modified_net, action = apply_curtailment(net, request.curtailment_pct)
        elif request.action_type == "BATTERY_DISPATCH":
            modified_net, action = apply_battery_dispatch(net, request.battery_p_mw, request.battery_bus)
        elif request.action_type == "FEEDER_RECONFIGURATION":
            modified_net, action = apply_feeder_reconfiguration(net, switch_name=request.switch_name)
        else:
            raise ValueError(f"Unknown action_type: '{request.action_type}'")

        run_baseline_powerflow(modified_net)
        violations = check_grid_violations(modified_net)
        return {
            "status": "success",
            "resolved": not violations["has_violations"],
            "action": action,
            "violations": violations,
            "topology": serialize_topology(modified_net),
        }
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
