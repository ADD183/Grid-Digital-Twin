"""OpenRouter LangChain tool calling with dual-audience grounded fallback."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from backend.app.artifact_exporter import generate_evidence_bundle
from backend.app.config import PROJECT_ROOT, Settings, get_settings
from backend.app.forecast_adapter import generate_mpc_forecasts
from backend.app.mpc_engine import MpcEngine
from backend.app.schemas import AssistantRequest
from backend.app.solver_verifier import SolverVerifier
from backend.app.telemetry_manager import TelemetryManager
from backend.app.surrogate import PowerFlowSurrogate
from src.scenarios import RUNNER_SCENARIOS


APPROVED_KNOWLEDGE_FILES = (
    "PRD_v3_Renewable_Grid_Digital_Twin_DualAudience_Assistant.md",
    "NOTES.md",
    "PROJECT_KNOWLEDGE_BASE.md",
)


class AssistantOrchestrator:
    """Use bounded tools; responses remain evidence-backed in both personas."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.verifier = SolverVerifier(self.settings)
        self.telemetry = TelemetryManager(self.settings)
        self.tools = self._build_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}

    def _build_tools(self) -> list[StructuredTool]:
        def telemetry_status() -> str:
            result = asyncio.run(self.telemetry.get_status())
            return result.model_dump_json()

        def verify_state(solar_mw: float, load_mw: float) -> str:
            result = self.verifier.run_power_flow(solar_mw=solar_mw, load_mw=load_mw)
            return result.model_dump_json()

        def mpc_plan() -> str:
            forecast = generate_mpc_forecasts()
            model_path = self.settings.surrogate_model_path
            model = PowerFlowSurrogate.load(model_path, self.settings) if model_path.exists() else None
            plan = MpcEngine(self.verifier, model).plan(forecast["points"])
            return json.dumps(
                {"plan": plan.model_dump(mode="json"), "forecast_provenance": forecast["provenance"]}
            )

        def export_artifacts() -> str:
            return json.dumps(generate_evidence_bundle(settings=self.settings), default=str)

        def search_knowledge(query: str) -> str:
            return json.dumps(search_project_knowledge(query), default=str)

        def scenario_result(scenario_id: str) -> str:
            key = scenario_id.strip().lower().replace(" ", "_")
            if key not in RUNNER_SCENARIOS:
                return json.dumps({"error": f"No saved result for scenario '{scenario_id}'"})
            path = PROJECT_ROOT / "outputs" / "scenario_results" / f"{key}.json"
            if not path.is_file():
                return json.dumps({"error": f"No saved result for scenario '{key}'"})
            return path.read_text(encoding="utf-8")

        def list_available_scenarios() -> str:
            return json.dumps(
                {
                    key: {
                        "name": value["name"],
                        "description": value["description"],
                    }
                    for key, value in RUNNER_SCENARIOS.items()
                }
            )

        return [
            StructuredTool.from_function(
                telemetry_status,
                name="get_telemetry_status",
                description="Read latest telemetry, forecast drift, freshness, and replan requirement.",
            ),
            StructuredTool.from_function(
                verify_state,
                name="verify_state_with_solver",
                description="Verify a proposed solar_mw and load_mw operating point with pandapower AC power flow.",
            ),
            StructuredTool.from_function(
                mpc_plan,
                name="run_8step_mpc_plan",
                description="Run the eight-step forecast-driven MPC and physically verify its selected steps.",
            ),
            StructuredTool.from_function(
                export_artifacts,
                name="export_hackathon_artifacts",
                description="Generate and export solver benchmarks, an MPC trace, model bundle, and datasets.",
            ),
            StructuredTool.from_function(
                search_knowledge,
                name="search_project_knowledge",
                description="Search only approved project documentation for methodology, definitions, and limitations.",
            ),
            StructuredTool.from_function(
                scenario_result,
                name="get_scenario_result",
                description="Read a saved, verified result for solar_spike, evening_peak, cloudy_drop, or infeasible.",
            ),
            StructuredTool.from_function(
                list_available_scenarios,
                name="list_available_scenarios",
                description="List the four supported scenario IDs and their descriptions.",
            ),
        ]

    def answer(self, request: AssistantRequest) -> dict[str, Any]:
        """Run a bounded tool-call loop or grounded keyword fallback."""
        api_key = self.settings.openrouter_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            return self._fallback(request)

        persona = (
            "Operator mode: preserve exact bus/line IDs, p.u. values, loading percentages, and solver status."
            if request.audience_mode == "operator"
            else "Executive mode: explain impact in plain language, while keeping measured values and uncertainty visible."
        )
        system = (
            "You are VoltPredict's Digital Grid Assistant. You may state project-specific facts only from tool outputs. "
            "Call every tool needed for a combined question; never invent system state, measurements, or financial claims. "
            "When information is missing, say it is unavailable. Put a concise natural-language answer first and cite exact evidence. "
            f"{persona}"
        )
        messages: list[Any] = [SystemMessage(content=system), HumanMessage(content=request.message)]
        evidence: dict[str, Any] = {}
        used_tools: list[str] = []
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=self.settings.openrouter_model,
                api_key=api_key.get_secret_value(),
                base_url=self.settings.openrouter_base_url,
                temperature=0,
                timeout=self.settings.telemetry_timeout_seconds,
                max_retries=0,
            ).bind_tools(self.tools)
            for _ in range(4):
                response = llm.invoke(messages)
                calls = getattr(response, "tool_calls", []) or []
                if not calls:
                    if not used_tools or not str(response.content).strip():
                        return self._fallback(request)
                    return {
                        "reply": str(response.content),
                        "evidence": evidence,
                        "audience_mode": request.audience_mode,
                        "used_tools": used_tools,
                    }
                messages.append(response)
                for call in calls:
                    name = call.get("name")
                    if name not in self.tool_map:
                        continue
                    result = self.tool_map[name].invoke(call.get("args", {}))
                    try:
                        parsed = json.loads(result) if isinstance(result, str) else result
                    except json.JSONDecodeError:
                        parsed = {"result": str(result)}
                    evidence[name] = parsed
                    used_tools.append(name)
                    messages.append(
                        ToolMessage(
                            content=json.dumps(parsed, default=str),
                            tool_call_id=call["id"],
                        )
                    )
            return {
                "reply": "I could not complete a grounded answer within the tool-call limit.",
                "evidence": evidence,
                "audience_mode": request.audience_mode,
                "used_tools": used_tools,
            }
        except Exception as exc:
            fallback = self._fallback(request)
            fallback["provider_error"] = str(exc)
            return fallback

    def _fallback(self, request: AssistantRequest) -> dict[str, Any]:
        message = request.message.lower()
        evidence: dict[str, Any] = {}
        tools: list[str] = []
        known_scenario = next(
            (key for key in RUNNER_SCENARIOS if key in message or key.replace("_", " ") in message),
            None,
        )
        if "scenario" in message and any(word in message for word in ("list", "available", "can i run", "which")):
            evidence["list_available_scenarios"] = json.loads(
                self.tool_map["list_available_scenarios"].invoke({})
            )
            tools.append("list_available_scenarios")
            names = ", ".join(evidence["list_available_scenarios"].keys())
            reply = f"Available saved scenarios are: {names}."
        elif "scenario" in message and (known_scenario or any(key in message for key in ("scenario", "case"))):
            scenario_id = known_scenario or "unknown"
            evidence["get_scenario_result"] = json.loads(
                self.tool_map["get_scenario_result"].invoke({"scenario_id": scenario_id})
            )
            tools.append("get_scenario_result")
            result = evidence["get_scenario_result"]
            if "error" in result:
                reply = f"I do not have a saved result for that scenario: {result['error']}."
            else:
                winner = result.get("recommended_action") or {}
                residual = winner.get("residual_violations_count", "not available")
                reply = (
                    f"The saved {result.get('scenario_id')} run is {result.get('status')}; "
                    f"fully resolved: {result.get('fully_resolved')}. Residual violations: {residual}."
                )
        elif any(word in message for word in ("telemetry", "drift", "actual solar", "replan")):
            evidence["get_telemetry_status"] = json.loads(
                self.tool_map["get_telemetry_status"].invoke({})
            )
            tools.append("get_telemetry_status")
            status = evidence["get_telemetry_status"]
            reply = (
                f"Telemetry is {'stale' if status['is_stale'] else 'fresh'} from {status['reading']['source']}. "
                f"Forecast drift is {status['drift']:.1%}; replan required: {status['requires_replan']}."
            )
        elif "mpc" in message or "plan" in message:
            raw = self.tool_map["run_8step_mpc_plan"].invoke({})
            evidence["run_8step_mpc_plan"] = json.loads(raw)
            tools.append("run_8step_mpc_plan")
            plan = evidence["run_8step_mpc_plan"]["plan"]
            reply = f"The eight-step plan is {'fully verified' if plan['fully_resolved'] else 'not fully resolved'} by the physical solver."
        elif "export" in message or "artifact" in message:
            evidence["export_hackathon_artifacts"] = json.loads(
                self.tool_map["export_hackathon_artifacts"].invoke({})
            )
            tools.append("export_hackathon_artifacts")
            reply = "The evidence bundle was generated. The returned paths identify each exported artifact."
        elif any(word in message for word in ("voltage", "safe", "solver", "verify", "grid state", "loading", "overload")):
            telemetry = json.loads(self.tool_map["get_telemetry_status"].invoke({}))
            reading = telemetry["reading"]
            evidence["verify_state_with_solver"] = json.loads(
                self.tool_map["verify_state_with_solver"].invoke(
                    {"solar_mw": reading["solar_mw"], "load_mw": reading["load_mw"]}
                )
            )
            evidence["get_telemetry_status"] = telemetry
            tools.extend(["get_telemetry_status", "verify_state_with_solver"])
            state = evidence["verify_state_with_solver"]
            if request.audience_mode == "operator":
                reply = (
                    f"The AC solver {'converged' if state['converged'] else 'did not converge'}; "
                    f"the state is {'safe' if state['is_safe'] else 'not safe'}. "
                    f"Voltage range: {state.get('min_voltage_pu')}–{state.get('max_voltage_pu')} p.u.; "
                    f"maximum line loading: {state.get('max_line_loading_percent')}%."
                )
            else:
                reply = (
                    f"At the measured telemetry operating point, the physical solver reports the grid is "
                    f"{'within' if state['is_safe'] else 'outside'} the configured operating limits."
                )
        else:
            evidence["search_project_knowledge"] = json.loads(
                self.tool_map["search_project_knowledge"].invoke({"query": request.message})
            )
            tools.append("search_project_knowledge")
            matches = evidence["search_project_knowledge"].get("matches", [])
            if matches:
                reply = f"Project documentation says: {matches[0]['excerpt']}"
            else:
                reply = (
                    "I can only answer questions about VoltPredict from approved project sources, "
                    "and those sources do not contain that information."
                )

        return {
            "reply": reply,
            "evidence": evidence,
            "audience_mode": request.audience_mode,
            "used_tools": tools,
        }


def search_project_knowledge(query: str, max_results: int = 3) -> dict[str, Any]:
    """Return lexical matches only from the approved repository documents."""
    stop_words = {"what", "which", "where", "when", "does", "this", "that", "with", "from", "about", "explain", "tell", "please"}
    terms = {
        term for term in re.findall(r"[a-z0-9]+", query.lower())
        if len(term) > 2 and term not in stop_words
    }
    minimum_overlap = min(len(terms), max(1, (len(terms) + 1) // 2))
    matches: list[dict[str, Any]] = []
    for filename in APPROVED_KNOWLEDGE_FILES:
        path = PROJECT_ROOT / filename
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            context = " ".join(lines[index:index + 3])
            line_terms = set(re.findall(r"[a-z0-9]+", context.lower()))
            score = len(terms & line_terms)
            if "curtailment" in terms and any(
                word in context.lower() for word in ("deliberately reducing", "reducing solar", "solar export")
            ):
                score += 3
            if score >= minimum_overlap:
                excerpt = " ".join(part.strip() for part in lines[index:index + 3] if part.strip())
                matches.append(
                    {"source": filename, "line": index + 1, "score": score, "excerpt": excerpt[:1000]}
                )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "matches": matches[:max_results]}