"""
Tests for chatbot tools and /api/chat processing.
"""

import pytest
from src.chat_tools import (
    get_grid_summary_tool,
    list_active_violations_tool,
    get_scenario_result_tool,
    list_available_scenarios_tool,
    get_forecast_summary_tool,
    handle_canned_fallback,
    process_chat_request,
)


def test_grid_summary_tool():
    summary = get_grid_summary_tool()
    assert "bus_count" in summary
    assert "max_line_loading_percent" in summary
    assert "violations" in summary


def test_list_active_violations_tool():
    violations = list_active_violations_tool()
    assert "has_violations" in violations
    assert isinstance(violations["has_violations"], bool)


def test_get_scenario_result_tool():
    res = get_scenario_result_tool("infeasible")
    assert res.get("status") == "UNRESOLVED" or res.get("scenario_id") == "infeasible"
    err = get_scenario_result_tool("non_existent_scenario")
    assert "error" in err


def test_list_available_scenarios_tool():
    scenarios = list_available_scenarios_tool()
    assert "solar_spike" in scenarios
    assert "infeasible" in scenarios


def test_get_forecast_summary_tool():
    summary = get_forecast_summary_tool()
    assert isinstance(summary, dict)


def test_canned_fallback():
    res_safe = handle_canned_fallback("Is the grid safe right now?")
    assert "reply" in res_safe
    assert "evidence" in res_safe

    res_unknown = handle_canned_fallback("What is the capital of France?")
    assert "only answer questions about this grid system" in res_unknown["reply"]


def test_process_chat_request_grounded():
    res = process_chat_request("Is the grid safe right now?")
    assert "reply" in res
    assert "evidence" in res
    assert isinstance(res["reply"], str)
