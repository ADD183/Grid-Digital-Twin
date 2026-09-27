"""
Chatbot tools and OpenRouter API integration module for Renewable Grid Digital Twin.
Provides tool definitions, tool execution, and OpenRouter completion handling for /api/chat.
"""

import os
import json
import requests
from typing import Dict, Any, List

from src.grid import load_cigre_network, run_baseline_powerflow, get_grid_summary
from src.violations import check_grid_violations
from src.scenarios import RUNNER_SCENARIOS, run_scenario
from src.forecast import load_saved_models_and_metrics, get_forecast_chart_data

DEFAULT_OPENROUTER_KEY = ""
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openai/gpt-4o-mini"

# ---------------------------------------------------------------------------
# Tool implementations wrapping existing src/ functions
# ---------------------------------------------------------------------------

def get_grid_summary_tool() -> Dict[str, Any]:
    """Wraps src.grid.get_grid_summary with baseline powerflow and violation check."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    summary = get_grid_summary(net)
    summary["violations"] = check_grid_violations(net)
    return summary


def list_active_violations_tool() -> Dict[str, Any]:
    """Wraps src.violations.check_grid_violations on baseline network state."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    return check_grid_violations(net)


def get_scenario_result_tool(scenario_id: str) -> Dict[str, Any]:
    """Reads persisted scenario results from outputs/scenario_results/{scenario_id}.json."""
    scenario_key = str(scenario_id).strip().lower()
    valid_scenarios = list(RUNNER_SCENARIOS.keys()) + ["line_congestion"]
    if scenario_key not in valid_scenarios:
        return {"error": f"No scenario data found for '{scenario_id}'"}

    json_path = os.path.join("outputs", "scenario_results", f"{scenario_key}.json")
    if not os.path.exists(json_path):
        try:
            return run_scenario(scenario_key)
        except Exception:
            return {"error": f"No scenario data found for '{scenario_id}'"}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as err:
        return {"error": f"Failed to load scenario file: {err}"}


def list_available_scenarios_tool() -> Dict[str, Any]:
    """Returns available scenario metadata."""
    scenarios = {}
    for key, item in RUNNER_SCENARIOS.items():
        scenarios[key] = {
            "id": item["id"],
            "name": item["name"],
            "description": item["description"]
        }
    return scenarios


def get_forecast_summary_tool() -> Dict[str, Any]:
    """Wraps src.forecast evaluation metrics summary."""
    saved = load_saved_models_and_metrics()
    if saved and "summary" in saved:
        return saved["summary"]
    data = get_forecast_chart_data(max_points=24)
    return data.get("summary", {})


# Map tool names to functions
TOOL_MAP = {
    "get_grid_summary": get_grid_summary_tool,
    "list_active_violations": list_active_violations_tool,
    "get_scenario_result": get_scenario_result_tool,
    "list_available_scenarios": list_available_scenarios_tool,
    "get_forecast_summary": get_forecast_summary_tool,
}

# ---------------------------------------------------------------------------
# OpenRouter tool schemas
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_grid_summary",
            "description": "Get summary metrics for the baseline CIGRE MV grid power flow including bus count, DER count, min/max voltage (vm_pu), max line loading percentage, and convergence.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_active_violations",
            "description": "Check and return active voltage (undervoltage/overvoltage) or line thermal overload violations on the current grid.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_scenario_result",
            "description": "Read scenario execution results for a specific scenario_id (e.g., solar_spike, evening_peak, cloudy_drop, infeasible, line_congestion).",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "string",
                        "description": "The scenario ID to query (e.g. solar_spike, evening_peak, cloudy_drop, infeasible)"
                    }
                },
                "required": ["scenario_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_available_scenarios",
            "description": "List all available demo scenario IDs and their descriptions.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast_summary",
            "description": "Get forecasting model metrics (MAE, RMSE, R2 improvement percentage over naive baseline for solar and demand).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

SYSTEM_PROMPT = (
    "You are a grid operations assistant. Answer briefly in plain language, then state "
    "the exact number(s) you used. If no tool returns the needed information, say so — "
    "never invent a value. If the question isn't about this grid system, say you can only "
    "answer questions about this project."
)

# ---------------------------------------------------------------------------
# Fallback keyword handler (when LLM API key is missing or API call fails)
# ---------------------------------------------------------------------------

def handle_canned_fallback(user_message: str) -> Dict[str, Any]:
    msg_lower = user_message.lower().strip()

    if any(k in msg_lower for k in ["safe", "violation", "limit"]):
        ev = list_active_violations_tool()
        if not ev.get("has_violations", False):
            reply = "The grid is currently safe and operating within normal limits with 0 active violations."
        else:
            v_count = ev.get("total_violations", 0)
            reply = f"The grid is not safe right now. There are {v_count} active violation(s)."
        return {"reply": reply, "evidence": ev}

    if any(k in msg_lower for k in ["loading", "voltage", "grid summary", "bus count", "grid status"]):
        ev = get_grid_summary_tool()
        max_load = ev.get("max_line_loading_percent", "N/A")
        min_v = ev.get("min_vm_pu", "N/A")
        max_v = ev.get("max_vm_pu", "N/A")
        reply = f"Current grid summary: max line loading is {max_load}%, min voltage is {min_v} p.u., and max voltage is {max_v} p.u."
        return {"reply": reply, "evidence": ev}

    if "scenario" in msg_lower and any(k in msg_lower for k in ["list", "available", "what scenarios", "can i run"]):
        ev = list_available_scenarios_tool()
        s_list = ", ".join(ev.keys())
        reply = f"Available scenarios you can run: {s_list}."
        return {"reply": reply, "evidence": ev}

    for sc_id in ["solar_spike", "evening_peak", "cloudy_drop", "infeasible", "line_congestion"]:
        if sc_id in msg_lower or sc_id.replace("_", " ") in msg_lower:
            ev = get_scenario_result_tool(sc_id)
            if "error" in ev:
                return {"reply": f"I checked for scenario '{sc_id}', but no data was found.", "evidence": ev}
            status = ev.get("status", "UNKNOWN")
            resolved = ev.get("fully_resolved", False)
            expl = ev.get("explanation", "")
            reply = f"Scenario '{sc_id}' result status: {status} (Fully resolved: {resolved}). {expl}"
            return {"reply": reply, "evidence": ev}

    if "scenario" in msg_lower:
        return {
            "reply": "I have no data for that scenario. Available scenarios are: solar_spike, evening_peak, cloudy_drop, and infeasible.",
            "evidence": {"error": "Unknown scenario"}
        }

    if any(k in msg_lower for k in ["forecast", "mae", "rmse", "model"]):
        ev = get_forecast_summary_tool()
        solar_imp = ev.get("solar", {}).get("mae_improvement_pct", "N/A")
        reply = f"Forecasting summary: solar forecaster achieves a {solar_imp}% MAE improvement over baseline."
        return {"reply": reply, "evidence": ev}

    return {
        "reply": "I can only answer questions about this grid system project.",
        "evidence": {}
    }


# ---------------------------------------------------------------------------
# Main Chat Request Handler
# ---------------------------------------------------------------------------

def _load_env_file():
    """Load key-value pairs from a local .env file into os.environ if present."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(root_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip().strip("'\""))
        except Exception:
            pass


def process_chat_request(user_message: str) -> Dict[str, Any]:
    """
    Process a chat message using OpenRouter function calling, falling back
    to deterministic tool response if the API call fails or key is missing.
    """
    _load_env_file()
    api_key = os.environ.get("OPEN_ROUTER_API_KEY") or os.environ.get("GROQ_API_KEY") or DEFAULT_OPENROUTER_KEY

    if not api_key or not str(api_key).strip():
        return handle_canned_fallback(user_message)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Renewable Grid Digital Twin"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "tools": TOOLS_SCHEMA,
        "tool_choice": "auto"
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=12)
        if response.status_code != 200:
            print(f"OpenRouter returned HTTP {response.status_code}: {response.text}")
            return handle_canned_fallback(user_message)

        res_data = response.json()
        choice = res_data.get("choices", [{}])[0]
        message_obj = choice.get("message", {})
        tool_calls = message_obj.get("tool_calls", [])

        if not tool_calls:
            reply_text = message_obj.get("content") or "I can only answer questions about this grid system."
            return {"reply": reply_text, "evidence": {}}

        tool_call = tool_calls[0]
        func_name = tool_call.get("function", {}).get("name")
        raw_args = tool_call.get("function", {}).get("arguments", "{}")

        try:
            func_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except Exception:
            func_args = {}

        if func_name not in TOOL_MAP:
            return handle_canned_fallback(user_message)

        # Execute tool function
        tool_func = TOOL_MAP[func_name]
        tool_result = tool_func(**func_args) if func_args else tool_func()

        # Followup completion call to synthesize grounded response
        followup_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
            message_obj,
            {
                "role": "tool",
                "tool_call_id": tool_call.get("id"),
                "name": func_name,
                "content": json.dumps(tool_result, default=str)
            }
        ]

        followup_payload = {
            "model": MODEL_NAME,
            "messages": followup_messages
        }

        followup_resp = requests.post(OPENROUTER_URL, json=followup_payload, headers=headers, timeout=12)
        if followup_resp.status_code == 200:
            followup_data = followup_resp.json()
            final_reply = followup_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "reply": final_reply,
                "evidence": tool_result
            }
        else:
            return {
                "reply": f"Tool '{func_name}' output: {json.dumps(tool_result, default=str)}",
                "evidence": tool_result
            }

    except Exception as err:
        print(f"Chat execution exception: {err}")
        return handle_canned_fallback(user_message)
