"""
Grid topology and power flow calculations for the Renewable Grid Digital Twin.

Uses pandapower CIGRE MV network with DERs to execute baseline AC power flow (runpp).
"""

from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
import pandapower as pp
import pandapower.networks as ppn


def load_cigre_network() -> pp.pandapowerNet:
    """
    Load the standard CIGRE medium-voltage (MV) distribution network with DERs.
    
    Returns:
        pp.pandapowerNet: The initialized pandapower network instance.
    """
    net = ppn.create_cigre_network_mv(with_der="all")
    return net


def run_baseline_powerflow(net: pp.pandapowerNet) -> bool:
    """
    Run baseline AC power flow calculation on the network.
    
    Args:
        net (pp.pandapowerNet): Target grid network.
        
    Returns:
        bool: True if power flow calculation converged successfully, False otherwise.
    """
    pp.runpp(net)
    return bool(getattr(net, "converged", False))


def get_grid_summary(net: pp.pandapowerNet) -> Dict[str, Any]:
    """
    Extract summary metrics from a post-powerflow pandapower network.
    
    Args:
        net (pp.pandapowerNet): Analyzed grid network.
        
    Returns:
        Dict[str, Any]: Metrics dictionary containing bus count, DER count, voltage extremes, 
                        max line loading, and convergence status.
    """
    if not hasattr(net, "res_bus") or net.res_bus.empty:
        run_baseline_powerflow(net)

    bus_count = len(net.bus)
    sgen_count = len(net.sgen)
    storage_count = len(net.storage) if hasattr(net, "storage") else 0
    total_der = sgen_count + storage_count

    vm_pu_min = float(net.res_bus.vm_pu.min()) if not net.res_bus.empty else 0.0
    vm_pu_max = float(net.res_bus.vm_pu.max()) if not net.res_bus.empty else 0.0
    max_line_loading = float(net.res_line.loading_percent.max()) if not net.res_line.empty else 0.0

    return {
        "bus_count": bus_count,
        "der_count": total_der,
        "sgen_count": sgen_count,
        "storage_count": storage_count,
        "vm_pu_min": round(vm_pu_min, 4),
        "vm_pu_max": round(vm_pu_max, 4),
        "max_line_loading_percent": round(max_line_loading, 2),
        "converged": bool(getattr(net, "converged", False)),
    }


def get_network_element_dfs(net: pp.pandapowerNet) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Format network elements and AC power flow results into clean DataFrames for UI visualization.
    
    Args:
        net (pp.pandapowerNet): Grid network with populated result tables.
        
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: DataFrames for (buses, lines, sgens).
    """
    if not hasattr(net, "res_bus") or net.res_bus.empty:
        run_baseline_powerflow(net)

    # 1. Bus Data
    bus_df = net.bus.copy()
    res_bus = net.res_bus.copy()

    bus_df["vm_pu"] = res_bus["vm_pu"]
    bus_df["va_degree"] = res_bus["va_degree"]
    bus_df["p_mw"] = res_bus["p_mw"]
    bus_df["q_mvar"] = res_bus["q_mvar"]

    # Extract coordinates from bus_geodata if available
    if hasattr(net, "bus_geodata") and not net.bus_geodata.empty:
        bus_df["x"] = net.bus_geodata.reindex(bus_df.index)["x"]
        bus_df["y"] = net.bus_geodata.reindex(bus_df.index)["y"]
    else:
        bus_df["x"] = np.nan
        bus_df["y"] = np.nan

    # Synthetic layout coordinates fallback if geodata is missing
    if bus_df["x"].isna().all():
        # Fallback grid layout positioning for CIGRE MV 15 buses
        n_buses = len(bus_df)
        cols = 5
        bus_df["x"] = [(i % cols) * 2.0 for i in range(n_buses)]
        bus_df["y"] = [-(i // cols) * 2.0 for i in range(n_buses)]

    # 2. Line Data
    line_df = net.line.copy()
    res_line = net.res_line.copy()

    line_df["loading_percent"] = res_line["loading_percent"]
    line_df["i_ka"] = res_line["i_ka"]
    line_df["p_from_mw"] = res_line["p_from_mw"]
    line_df["q_from_mvar"] = res_line["q_from_mvar"]

    # Map line endpoints coordinates
    from_x = []
    from_y = []
    to_x = []
    to_y = []
    for _, row in line_df.iterrows():
        f_idx = row["from_bus"]
        t_idx = row["to_bus"]
        from_x.append(bus_df.loc[f_idx, "x"])
        from_y.append(bus_df.loc[f_idx, "y"])
        to_x.append(bus_df.loc[t_idx, "x"])
        to_y.append(bus_df.loc[t_idx, "y"])

    line_df["from_x"] = from_x
    line_df["from_y"] = from_y
    line_df["to_x"] = to_x
    line_df["to_y"] = to_y

    # 3. DER / Static Generator Data
    sgen_df = net.sgen.copy() if not net.sgen.empty else pd.DataFrame()
    if not sgen_df.empty and hasattr(net, "res_sgen") and not net.res_sgen.empty:
        res_sgen = net.res_sgen.copy()
        sgen_df["res_p_mw"] = res_sgen["p_mw"]
        sgen_df["res_q_mvar"] = res_sgen["q_mvar"]

    return bus_df, line_df, sgen_df
