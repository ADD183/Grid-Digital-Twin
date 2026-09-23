"""
Unit tests for Checkpoint 1: Grid network loading, AC power flow convergence,
and time-series data pipeline alignment.
"""

import os
import pytest
import pandas as pd
import pandapower as pp
from src.grid import (
    load_cigre_network,
    run_baseline_powerflow,
    get_grid_summary,
    get_network_element_dfs,
)
from src.data_pipeline import (
    fetch_pune_solar_data,
    generate_synthetic_load_profile,
    build_aligned_dataset,
)


def test_cigre_network_loads():
    """Verify CIGRE MV network loads with expected elements."""
    net = load_cigre_network()
    assert isinstance(net, pp.pandapowerNet)
    assert len(net.bus) > 0
    assert len(net.line) > 0
    assert len(net.sgen) > 0


def test_run_baseline_powerflow_convergence():
    """Verify baseline power flow calculation converges without errors."""
    net = load_cigre_network()
    converged = run_baseline_powerflow(net)
    assert converged is True
    assert hasattr(net, "res_bus")
    assert not net.res_bus.empty


def test_baseline_voltage_limits():
    """Verify all bus voltages under baseline conditions fall within expected CIGRE bounds [0.94, 1.05] p.u."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    vm_pu = net.res_bus["vm_pu"]
    assert vm_pu.min() >= 0.94, f"Bus voltage drop below limit: {vm_pu.min()} < 0.94"
    assert vm_pu.max() <= 1.05, f"Bus overvoltage above limit: {vm_pu.max()} > 1.05"


def test_grid_summary_structure():
    """Verify get_grid_summary outputs valid dictionary metrics."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    summary = get_grid_summary(net)
    
    assert summary["bus_count"] == len(net.bus)
    assert summary["converged"] is True
    assert 0.94 <= summary["vm_pu_min"] <= 1.05
    assert 0.94 <= summary["vm_pu_max"] <= 1.05
    assert summary["max_line_loading_percent"] >= 0.0


def test_network_element_dfs():
    """Verify network elements and results formatting into DataFrames."""
    net = load_cigre_network()
    run_baseline_powerflow(net)
    bus_df, line_df, sgen_df = get_network_element_dfs(net)

    assert "vm_pu" in bus_df.columns
    assert "x" in bus_df.columns and "y" in bus_df.columns
    assert "loading_percent" in line_df.columns
    assert "from_x" in line_df.columns and "to_x" in line_df.columns


def test_synthetic_load_generation():
    """Verify synthetic load profile generator generates diurnal pattern."""
    time_index = pd.date_range("2023-01-01", "2023-01-02", freq="h")
    df = generate_synthetic_load_profile(time_index)

    assert len(df) == 25
    assert "load_kw" in df.columns
    assert "load_pu" in df.columns
    assert df["load_pu"].min() >= 0.10
    assert df["load_pu"].max() <= 1.20


def test_data_pipeline_aligned_dataset(tmp_path):
    """Verify data pipeline creates aligned time-series dataset file."""
    output_path = os.path.join(tmp_path, "test_aligned.csv")
    aligned_df = build_aligned_dataset(start_date="2023-01-01", end_date="2023-01-02", output_path=output_path)

    assert os.path.exists(output_path)
    assert "solar_pu" in aligned_df.columns
    assert "load_pu" in aligned_df.columns
    assert len(aligned_df) == 25
