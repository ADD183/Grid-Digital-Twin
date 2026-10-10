"""
FastAPI REST API Server for VoltPredict.
Exposes backend grid topology, power flow calculation results, and time-series solar/load data to the React.js frontend.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query, HTTPException, Header, Request
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
from src.chat_tools import process_chat_request
from backend.app.agent_orchestrator import AssistantOrchestrator
from backend.app.artifact_exporter import generate_evidence_bundle
from backend.app.config import get_settings
from backend.app.forecast_adapter import generate_mpc_forecasts
from backend.app.mpc_engine import MpcEngine
from backend.app.schemas import (
    ArtifactExportRequest,
    AssistantRequest,
    MpcPlanRequest,
    SolverRequest,
    SurrogateTrainingRequest,
)
from backend.app.solver_verifier import SolverVerifier
from backend.app.surrogate import PowerFlowSurrogate, generate_solver_dataset
from backend.app.telemetry_manager import TelemetryManager

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start and cleanly stop the read-only telemetry refresh task."""
    manager = TelemetryManager(settings)
    application.state.telemetry_manager = manager
    application.state.telemetry_status = await manager.get_status()
    stopping = asyncio.Event()

    async def refresh_telemetry() -> None:
        while not stopping.is_set():
            try:
                application.state.telemetry_status = await manager.get_status()
            except Exception:
                application.state.telemetry_status = manager.mock_status(
                    error="Background telemetry refresh failed"
                )
            try:
                await asyncio.wait_for(stopping.wait(), timeout=settings.telemetry_poll_seconds)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(refresh_telemetry())
    try:
        yield
    finally:
        stopping.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="VoltPredict API",
    description="REST API serving pandapower grid simulations and PVGIS solar/demand datasets",
    version="1.1.0",
    lifespan=lifespan,
)

# Enable CORS for React frontend (Vercel / Vite dev server / all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
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
    return {"status": "ok", "version": "1.0.0", "system": "VoltPredict API"}


@app.get("/health")
def standard_health_check() -> Dict[str, str]:
    """Deployment health endpoint with an explicit UTC timestamp."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/update1/telemetry")
async def update1_telemetry(request: Request) -> Dict[str, Any]:
    """Return the latest lifespan-refreshed telemetry and drift status."""
    status = getattr(request.app.state, "telemetry_status", None)
    if status is None:
        status = await TelemetryManager(settings).get_status()
    return status.model_dump(mode="json")


@app.get("/api/update1/forecast/horizon")
async def update1_forecast_horizon(
    steps: int = Query(8, ge=1, le=8),
) -> Dict[str, Any]:
    """Generate recursive forecast values for MPC with resolution provenance."""
    try:
        return await asyncio.to_thread(generate_mpc_forecasts, steps)
    except Exception as err:
        raise HTTPException(status_code=503, detail=f"Unable to generate MPC forecast: {err}")


@app.post("/api/update1/solver/verify")
async def update1_verify_state(request: SolverRequest) -> Dict[str, Any]:
    """Run pandapower verification without blocking the API event loop."""
    try:
        result = await SolverVerifier(settings).run_power_flow_async(**request.model_dump())
        return result.model_dump(mode="json")
    except Exception as err:
        raise HTTPException(status_code=422, detail=str(err))


def _train_update1_surrogate(sample_count: int) -> Dict[str, Any]:
    features, voltages, loadings = generate_solver_dataset(sample_count=sample_count)
    model = PowerFlowSurrogate(settings)
    metrics = model.train(
        features,
        voltages,
        loadings,
        voltage_bus_ids=list(range(voltages.shape[1])),
        line_ids=list(range(loadings.shape[1])),
        save_path=settings.surrogate_model_path,
    )
    return {
        "status": "trained",
        "metrics": metrics,
        "model_path": str(settings.surrogate_model_path),
        "converged_samples": len(features),
    }


@app.post("/api/update1/surrogate/train")
async def update1_train_surrogate(request: SurrogateTrainingRequest) -> Dict[str, Any]:
    """Generate physical labels and train the LightGBM surrogate in a worker."""
    try:
        return await asyncio.to_thread(_train_update1_surrogate, request.sample_count)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Surrogate training failed: {err}")


@app.get("/api/update1/surrogate/status")
def update1_surrogate_status() -> Dict[str, Any]:
    """Return model availability and stored benchmark metrics."""
    path = settings.surrogate_model_path
    if not path.is_file():
        return {"trained": False, "model_path": str(path)}
    try:
        model = PowerFlowSurrogate.load(path, settings)
    except Exception as err:
        return {"trained": False, "model_path": str(path), "error": str(err)}
    return {"trained": True, "metrics": model.metrics, "model_path": str(path)}


@app.post("/api/update1/mpc/plan")
async def update1_mpc_plan(request: MpcPlanRequest, http_request: Request) -> Dict[str, Any]:
    """Execute and physically verify an eight-step candidate plan."""
    try:
        forecasts = [item.model_dump() for item in request.forecasts]
        telemetry = getattr(http_request.app.state, "telemetry_status", None)
        model_path = settings.surrogate_model_path
        model = PowerFlowSurrogate.load(model_path, settings) if model_path.is_file() else None
        engine = MpcEngine(SolverVerifier(settings), model)
        plan = await asyncio.to_thread(
            engine.plan,
            forecasts,
            initial_state_of_charge_mwh=request.initial_state_of_charge_mwh,
            telemetry=telemetry,
        )
        return plan.model_dump(mode="json")
    except Exception as err:
        raise HTTPException(status_code=422, detail=f"MPC plan failed: {err}")


@app.post("/api/export-artifacts")
async def update1_export_artifacts(request: ArtifactExportRequest) -> Dict[str, Any]:
    """Generate benchmark, MPC trace, model, and train/test evidence files."""
    try:
        return await asyncio.to_thread(
            generate_evidence_bundle,
            sample_count=request.sample_count,
            initial_state_of_charge_mwh=request.initial_state_of_charge_mwh,
            settings=settings,
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Artifact export failed: {err}")


@app.post("/api/update1/assistant/chat")
async def update1_assistant_chat(
    request: AssistantRequest,
    audience_mode: str | None = Header(default=None, alias="X-Audience-Mode"),
) -> Dict[str, Any]:
    """Answer with bounded tools and the requested operator/executive voice."""
    mode = audience_mode or request.audience_mode
    if mode not in {"operator", "executive"}:
        raise HTTPException(status_code=422, detail="X-Audience-Mode must be operator or executive")
    request = request.model_copy(update={"audience_mode": mode})
    return await asyncio.to_thread(AssistantOrchestrator(settings).answer, request)


class EpisodeRunRequest(BaseModel):
    episode_steps: int = Field(default=8, ge=1, le=24)
    initial_soc: float = Field(default=0.5, ge=0.1, le=0.9)
    inject_error: bool = True


@app.get("/api/control/limits")
def get_control_limits() -> Dict[str, Any]:
    """Return limits.yaml configuration for multi-step control."""
    from src.control.state import load_limits_config
    import yaml
    with open("config/limits.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.get("/api/control/episode/showcase")
def get_showcase_episode() -> Dict[str, Any]:
    """Return persisted showcase EpisodeLog JSON."""
    from pathlib import Path
    import json
    from src.control.episode import run_episode
    p = Path("outputs/evidence/action_logs/cp5_showcase.json")
    if not p.is_file():
        log = run_episode(episode_steps=8, initial_soc=0.5, run_id="cp5_showcase")
        log.export_evidence()
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/control/episode/run")
def run_control_episode(request: EpisodeRunRequest) -> Dict[str, Any]:
    """Run rolling-horizon episode live and return serialized EpisodeLog."""
    from src.control.episode import run_episode
    errors = {2: {"solar_mult": 2.0, "load_mult": 0.85, "label": "Midday solar surge"}} if request.inject_error else {}
    log = run_episode(
        episode_steps=request.episode_steps,
        initial_soc=request.initial_soc,
        injected_errors=errors,
        run_id="api_run",
    )
    return log.to_dict()


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


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
def chat_endpoint(request: ChatRequest) -> Dict[str, Any]:
    """Process natural language query about grid operations using grounded tools."""
    try:
        return process_chat_request(request.message)
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


# -------------------------------------------------------------------------
# Checkpoint 5: Multi-Step Control & Time Plan Endpoints
# -------------------------------------------------------------------------
class EpisodeRunRequest(BaseModel):
    initial_soc: float = Field(default=0.5, ge=0.1, le=0.9)
    inject_error: bool = True
    inject_error_step: int = 2
    force_infeasible: bool = False
    force_infeasible_step: int = 5
    run_id: str = "live_run"


@app.get("/api/control/limits")
def get_control_limits() -> Dict[str, Any]:
    """Return limits and operational parameters configured for Checkpoint 5 control."""
    from src.control.state import load_limits_config
    cfg = load_limits_config()
    return {
        "grid": {
            "v_min": cfg.grid.v_min,
            "v_max": cfg.grid.v_max,
            "max_loading_pct": cfg.grid.max_loading_pct,
        },
        "battery": {
            "capacity_mwh": cfg.battery.capacity_mwh,
            "max_p_mw": cfg.battery.max_p_mw,
            "soc_min": cfg.battery.soc_min,
            "soc_max": cfg.battery.soc_max,
            "eta": cfg.battery.eta,
            "bus_id": cfg.battery.bus_id,
        },
        "control": {
            "horizon_steps": cfg.control.horizon_steps,
            "delta_t_h": cfg.control.delta_t_h,
            "beam_width": cfg.control.beam_width,
            "max_switches_per_episode": cfg.control.max_switches_per_episode,
        },
        "discrete_actions": {
            "battery_mw": cfg.discrete_actions.battery_mw,
            "curtail_pct": cfg.discrete_actions.curtail_pct,
            "switch_actions": cfg.discrete_actions.switch_actions,
        },
        "fallback_ladder": cfg.fallback_ladder,
    }


@app.get("/api/control/episode/showcase")
def get_showcase_episode() -> Dict[str, Any]:
    """Return the saved Checkpoint 5 showcase episode log or generate if missing."""
    import json
    from pathlib import Path
    from src.control.episode import run_episode

    p = Path("outputs/evidence/action_logs/cp5_showcase.json")
    if p.is_file():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    log = run_episode(episode_steps=8, initial_soc=0.5, run_id="cp5_showcase")
    log.export_evidence()
    return log.to_dict()


@app.post("/api/control/episode/run")
async def run_control_episode(request: EpisodeRunRequest) -> Dict[str, Any]:
    """Execute rolling-horizon episode with pandapower verifier, drift and fallback ladder."""
    import asyncio
    from src.control.episode import run_episode

    errors = {}
    if request.inject_error:
        errors[request.inject_error_step] = {
            "solar_mult": 2.0,
            "load_mult": 0.85,
            "label": "Injected midday solar surge",
        }

    infeasible_steps = [request.force_infeasible_step] if request.force_infeasible else []

    def _execute():
        from src.control.screener import NullScreener
        from src.control.planner import BeamSearchPlanner
        from src.control.state import load_limits_config

        verifier, _ = get_global_verifier_and_screener()
        lims = load_limits_config()
        screener = NullScreener()
        planner = BeamSearchPlanner(verifier=verifier, screener=screener, limits=lims)

        log = run_episode(
            episode_steps=8,
            initial_soc=request.initial_soc,
            limits=lims,
            verifier=verifier,
            planner=planner,
            screener=screener,
            injected_errors=errors,
            force_infeasible_steps=infeasible_steps,
            run_id=request.run_id,
        )
        log.export_evidence()
        return log.to_dict()

    try:
        return await asyncio.to_thread(_execute)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Episode execution failed: {err}")


# -------------------------------------------------------------------------
# Checkpoint 6: Learned Power-Flow Surrogate & Evaluation Endpoints
# -------------------------------------------------------------------------
@app.get("/api/surrogate/status")
def get_surrogate_model_status() -> Dict[str, Any]:
    """Return availability, trained status, guard band, and supported bounds for surrogate."""
    import json
    from pathlib import Path

    meta_path = Path("outputs/evidence/surrogate_model_metadata.json")
    if not meta_path.is_file():
        return {"trained": False, "message": "Surrogate ensemble not yet trained"}

    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/surrogate/train")
async def train_surrogate_model() -> Dict[str, Any]:
    """Generate 5 split manifests and train the 3-seed PyTorch surrogate ensemble."""
    import asyncio
    from src.surrogate.train import train_surrogate_ensemble
    from src.surrogate.evaluate import evaluate_surrogate_full

    def _pipeline():
        meta = train_surrogate_ensemble()
        eval_report = evaluate_surrogate_full()
        return {"status": "success", "metadata": meta, "evaluation_summary": eval_report["split_evaluations"]}

    try:
        return await asyncio.to_thread(_pipeline)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Surrogate training failed: {err}")


@app.get("/api/surrogate/evaluation")
def get_surrogate_evaluation_report() -> Dict[str, Any]:
    """Return complete evaluation report across dev_val, test_unseen, test_extended, test_near_limit."""
    import json
    from pathlib import Path
    from src.surrogate.evaluate import evaluate_surrogate_full

    eval_path = Path("outputs/evidence/surrogate_evaluation.json")
    if not eval_path.is_file():
        return evaluate_surrogate_full()

    with open(eval_path, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------------------------------------------------------
# Checkpoint 7: Surrogate-Screened Planning & A/B Benchmark Endpoints
# -------------------------------------------------------------------------
_GLOBAL_VERIFIER = None
_GLOBAL_SCREENER = None

def get_global_verifier_and_screener():
    global _GLOBAL_VERIFIER, _GLOBAL_SCREENER
    if _GLOBAL_VERIFIER is None:
        from src.control.state import load_limits_config
        from src.control.verifier import Verifier
        from src.control.screener import SurrogateScreener
        lims = load_limits_config()
        _GLOBAL_VERIFIER = Verifier(lims)
        try:
            _GLOBAL_SCREENER = SurrogateScreener(lims)
        except Exception:
            _GLOBAL_SCREENER = None
    return _GLOBAL_VERIFIER, _GLOBAL_SCREENER


@app.get("/api/control/ab-test")
def get_ab_screening_benchmark() -> Dict[str, Any]:
    """Run/return A/B screening benchmark comparing NullScreener vs SurrogateScreener."""
    import json
    from pathlib import Path
    from src.control.ab_testing import run_ab_screening_benchmark

    p = Path("outputs/evidence/ab_screening_comparison.json")
    if p.is_file():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return run_ab_screening_benchmark()


@app.post("/api/control/episode/run-screened")
async def run_surrogate_screened_episode(request: EpisodeRunRequest) -> Dict[str, Any]:
    """Execute rolling-horizon episode with SurrogateScreener filtering and solver verification."""
    import asyncio
    from src.control.episode import run_episode
    from src.control.screener import SurrogateScreener
    from src.control.planner import BeamSearchPlanner
    from src.control.state import load_limits_config

    errors = {}
    if request.inject_error:
        errors[request.inject_error_step] = {
            "solar_mult": 2.0,
            "load_mult": 0.85,
            "label": "Injected midday solar surge",
        }

    infeasible_steps = [request.force_infeasible_step] if request.force_infeasible else []

    def _execute():
        verifier, screener = get_global_verifier_and_screener()
        lims = load_limits_config()
        if screener is None:
            screener = SurrogateScreener(lims)
        planner = BeamSearchPlanner(verifier=verifier, screener=screener, limits=lims)

        log = run_episode(
            episode_steps=8,
            initial_soc=request.initial_soc,
            limits=lims,
            verifier=verifier,
            planner=planner,
            screener=screener,
            injected_errors=errors,
            force_infeasible_steps=infeasible_steps,
            run_id=request.run_id,
        )
        log.export_evidence()
        res = log.to_dict()

        # Attach disagreement events log if present
        disagreements = []
        for s in log.steps:
            if s.error_label and "disagreement" in s.error_label.lower():
                disagreements.append({"step": s.step, "label": s.error_label})

        res["disagreement_events"] = disagreements
        return res

    try:
        return await asyncio.to_thread(_execute)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Screened episode execution failed: {err}")


# -------------------------------------------------------------------------
# Checkpoint 8: Showcase Scenario & Evidence Pack Endpoints
# -------------------------------------------------------------------------
@app.get("/api/control/episode/showcase12")
def get_showcase12_episode() -> Dict[str, Any]:
    """Return 12-step Checkpoint 8 showcase episode log with all 6 required events."""
    import json
    from pathlib import Path
    action_log_path = Path("outputs/evidence/action_logs/cp8_showcase_12step.json")
    if action_log_path.is_file():
        try:
            with open(action_log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    from src.control.showcase import run_showcase_episode
    log = run_showcase_episode(run_id="cp8_showcase_12step")
    log.export_evidence()
    return log.to_dict()


from fastapi.responses import FileResponse, Response

@app.get("/api/evidence/download")
def download_evidence_file(file_path: str = Query(..., description="Relative file path under outputs/evidence/")):
    """Download any file from outputs/evidence/ directory as file attachment."""
    from pathlib import Path
    clean_rel = file_path.replace("\\", "/").lstrip("/")
    full_p = Path(clean_rel)
    if not full_p.is_file():
        full_p = Path("outputs/evidence") / clean_rel
    if not full_p.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    filename = full_p.name
    media_type = "text/csv" if filename.endswith(".csv") else "application/json" if filename.endswith(".json") else "text/plain"
    return FileResponse(path=str(full_p), filename=filename, media_type=media_type)


@app.get("/api/evidence/export-csv")
def export_evidence_csv():
    """Download the 12-step showcase episode execution table as a CSV file for Excel."""
    from pathlib import Path
    csv_p = Path("outputs/evidence/action_logs/cp8_showcase_12step_full_table.csv")
    if not csv_p.is_file():
        csv_p = Path("outputs/evidence/soc_traces/cp8_showcase_12step_soc.csv")
    if not csv_p.is_file():
        from src.control.showcase import run_showcase_episode
        log = run_showcase_episode(run_id="cp8_showcase_12step")
        log.export_evidence()
        csv_p = Path("outputs/evidence/action_logs/cp8_showcase_12step_full_table.csv")

    return FileResponse(
        path=str(csv_p),
        filename="cp8_showcase_12step_evidence_table.csv",
        media_type="text/csv",
    )


@app.get("/api/evidence/index")
def get_evidence_index() -> Dict[str, Any]:
    """Return Checkpoint 8 evidence pack index markdown and artifact map."""
    from pathlib import Path
    p = Path("outputs/evidence/EVIDENCE_INDEX.md")
    content = p.read_text(encoding="utf-8") if p.is_file() else ""
    return {
        "status": "success",
        "index_markdown": content,
        "evidence_files": [
            "outputs/evidence/solver_config.json",
            "outputs/evidence/action_logs/cp8_showcase_12step_full_table.csv",
            "outputs/evidence/action_logs/cp8_showcase_12step.json",
            "outputs/evidence/action_logs/cp8_showcase_12step.jsonl",
            "outputs/evidence/soc_traces/cp8_showcase_12step_soc.csv",
            "outputs/evidence/verification/cp8_showcase_12step_verification.csv",
            "outputs/evidence/verification/cp8_showcase_12step_verification.json",
            "outputs/evidence/metrics/ab_screening_comparison.json",
            "outputs/evidence/metrics/surrogate_evaluation.json",
            "outputs/evidence/surrogate/surrogate_metadata.json",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
