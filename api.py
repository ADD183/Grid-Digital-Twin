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
from src.forecast import train_all_models, load_saved_models_and_metrics, get_forecast_chart_data
from src.violations import check_grid_violations
from src.actions import apply_curtailment, apply_battery_dispatch, apply_feeder_reconfiguration
from src.engine import trigger_scenario, evaluate_actions, DEMO_SCENARIOS

app = FastAPI(
    title="Renewable Grid Digital Twin API",
    description="REST API serving pandapower grid simulations, PVGIS solar/demand datasets, ML forecasting models, and corrective action engine",
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
            "id": int(idx),
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
            "id": int(idx),
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
                "id": int(idx),
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
                "timestamp": idx.strftime("%Y-%m-%d %H:%M"),
                "solar_ghi": round(float(row.get("solar_ghi", 0.0)), 2),
                "solar_pu": round(float(row.get("solar_pu", 0.0)), 4),
                "load_kw": round(float(row.get("load_kw", 0.0)), 2),
                "load_pu": round(float(row.get("load_pu", 0.0)), 4)
            })
        return records
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/forecast/metrics")
def get_forecast_metrics() -> Dict[str, Any]:
    """Return model performance metrics (MAE, RMSE, R2, baseline improvements) for solar and load forecasters."""
    try:
        saved = load_saved_models_and_metrics()
        if saved is None:
            res = train_all_models(save=True)
            return res["summary"]
        return saved["summary"]
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/forecast/chart")
def get_forecast_chart(
    points: int = Query(
        168,
        ge=24,
        le=336,
        description="Number of test holdout hours to visualize (24-336; default 168 = 7 days)"
    )
) -> Dict[str, Any]:
    """Return actual vs predicted vs naive persistence baseline time series for the holdout test window."""
    try:
        data = get_forecast_chart_data(max_points=points)
        return data
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.post("/api/forecast/train")
def retrain_forecast_models() -> Dict[str, Any]:
    """Trigger retraining of Solar and Load gradient boosting models and persist artifacts."""
    try:
        res = train_all_models(save=True)
        return {
            "status": "success",
            "message": "Forecasting models retrained and serialized successfully.",
            "summary": res["summary"]
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# =========================================================================
# CHECKPOINT 3: VIOLATION DETECTION & CORRECTIVE ACTION ENGINE ENDPOINTS
# =========================================================================

class TriggerScenarioRequest(BaseModel):
    scenario_id: str = Field("solar_spike", description="Scenario identifier ('solar_spike', 'evening_peak', 'line_congestion')")
    magnitude: Optional[float] = Field(None, description="Optional custom magnitude multiplier")


class EvaluateEngineRequest(BaseModel):
    scenario_id: str = Field("solar_spike", description="Scenario to trigger and evaluate")
    magnitude: Optional[float] = Field(None, description="Optional custom magnitude multiplier")


class CustomActionRequest(BaseModel):
    scenario_id: str = Field("solar_spike", description="Scenario basis")
    action_type: str = Field(..., description="'CURTAILMENT' | 'BATTERY_DISPATCH' | 'FEEDER_RECONFIGURATION'")
    curtailment_pct: Optional[float] = Field(50.0, description="Curtailment percentage (0-100)")
    battery_p_mw: Optional[float] = Field(1.0, description="Battery power in MW (+ charge / - discharge)")
    battery_bus: Optional[int] = Field(5, description="Bus for battery storage")
    switch_name: Optional[str] = Field("S1", description="Switch name ('S1', 'S2', 'S3')")


@app.get("/api/violations/scenarios")
def get_scenarios() -> Dict[str, Any]:
    """Return available triggerable constraint scenarios and their metadata."""
    return {"scenarios": list(DEMO_SCENARIOS.values())}


@app.post("/api/violations/trigger")
def api_trigger_scenario(req: TriggerScenarioRequest) -> Dict[str, Any]:
    """
    Artificially trigger a constraint scenario (solar overvoltage spike, evening peak, line congestion)
    and return the resulting network violations, summary, and post-powerflow topology.
    """
    try:
        net, meta = trigger_scenario(scenario_id=req.scenario_id, magnitude=req.magnitude)
        violations = check_grid_violations(net)
        summary = get_grid_summary(net)
        topology = serialize_topology(net)
        return {
            "status": "success",
            "scenario": meta,
            "violations": violations,
            "summary": summary,
            "topology": topology,
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.post("/api/violations/evaluate")
def api_evaluate_engine(req: EvaluateEngineRequest) -> Dict[str, Any]:
    """
    Execute the Propose -> Verify -> Repair engine:
    1. Triggers the requested scenario.
    2. Proposes candidates across curtailment, battery storage, and feeder reconfiguration.
    3. Verifies each candidate via AC power flow.
    4. Ranks candidates on resolution, clean energy retention, and operational cost.
    5. Returns full ranked matrix, winner, explanation, and before/after topologies.
    """
    try:
        net, meta = trigger_scenario(scenario_id=req.scenario_id, magnitude=req.magnitude)
        before_topology = serialize_topology(net)
        eval_result = evaluate_actions(net)
        eval_result["scenario"] = meta
        eval_result["before_topology"] = before_topology
        return eval_result
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.post("/api/violations/apply-custom-action")
def api_apply_custom_action(req: CustomActionRequest) -> Dict[str, Any]:
    """
    Apply a specific user-selected corrective action to the scenario network
    and return the resulting topology and residual violations.
    """
    try:
        net, meta = trigger_scenario(scenario_id=req.scenario_id)
        
        if req.action_type.upper() == "CURTAILMENT":
            mod_net, action_meta = apply_curtailment(net, curtailment_pct=req.curtailment_pct or 50.0)
        elif req.action_type.upper() == "BATTERY_DISPATCH":
            mod_net, action_meta = apply_battery_dispatch(
                net,
                p_mw=req.battery_p_mw or 1.0,
                bus_id=req.battery_bus or 5
            )
        elif req.action_type.upper() == "FEEDER_RECONFIGURATION":
            mod_net, action_meta = apply_feeder_reconfiguration(
                net,
                switch_name=req.switch_name or "S1"
            )
        else:
            raise ValueError(f"Unknown action_type: {req.action_type}")

        run_baseline_powerflow(mod_net)
        violations = check_grid_violations(mod_net)
        summary = get_grid_summary(mod_net)
        topology = serialize_topology(mod_net)

        return {
            "status": "success",
            "action": action_meta,
            "resolved": not violations["has_violations"],
            "violations": violations,
            "summary": summary,
            "topology": topology,
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
