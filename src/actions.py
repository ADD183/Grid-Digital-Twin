"""
Corrective Action Module for Renewable Distribution Grid Digital Twin (Checkpoint 3).

Implements three distinct operational corrective actions to mitigate grid violations:
1. Solar Curtailment: Throttles active power generation of static generators (PV DERs).
2. Battery Storage Dispatch: Charges/discharges energy storage elements to absorb excess solar or support demand.
3. Feeder Reconfiguration: Switches network tie-lines (switches S1, S2, S3) to reroute power flow.

Each action takes a pandapower network, creates an isolated deepcopy, applies the modification,
and returns the modified network alongside standardized action metadata.
"""

import copy
from typing import Dict, Any, Tuple, Optional, List
import pandapower as pp
import pandas as pd


def apply_curtailment(
    net: pp.pandapowerNet,
    curtailment_pct: float,
    bus_id: Optional[int] = None,
    sgen_ids: Optional[List[int]] = None,
) -> Tuple[pp.pandapowerNet, Dict[str, Any]]:
    """
    Apply solar curtailment by reducing active power (p_mw) output of static generators.
    
    Args:
        net (pp.pandapowerNet): Pandapower network.
        curtailment_pct (float): Percentage of generation to curtail (0.0 to 100.0).
        bus_id (Optional[int]): If provided, only curtail sgens connected to this bus.
        sgen_ids (Optional[List[int]]): If provided, only curtail these specific sgens.
        
    Returns:
        Tuple[pp.pandapowerNet, Dict[str, Any]]: Modified net copy and action metadata.
    """
    curtailment_pct = max(0.0, min(100.0, float(curtailment_pct)))
    reduction_factor = 1.0 - (curtailment_pct / 100.0)

    net_copy = copy.deepcopy(net)

    if net_copy.sgen.empty:
        return net_copy, {
            "action_id": f"curtail_{int(curtailment_pct)}pct",
            "action_type": "CURTAILMENT",
            "name": f"Solar Curtailment {curtailment_pct:.0f}%",
            "curtailment_pct": curtailment_pct,
            "renewable_retained_pct": 100.0,
            "mw_curtailed": 0.0,
            "cost_proxy": 3,
            "description": "No static generators available to curtail.",
        }

    # Identify target static generators
    if sgen_ids is not None:
        target_indices = [idx for idx in sgen_ids if idx in net_copy.sgen.index]
    elif bus_id is not None:
        target_indices = list(net_copy.sgen[net_copy.sgen["bus"] == bus_id].index)
    else:
        # Default: curtail all PV / renewable static generators
        pv_mask = net_copy.sgen["type"].astype(str).str.upper().str.contains("PV|WP|WIND|SOLAR")
        target_indices = list(net_copy.sgen[pv_mask].index)
        if not target_indices:
            target_indices = list(net_copy.sgen.index)

    initial_p = float(net_copy.sgen.loc[target_indices, "p_mw"].sum())
    net_copy.sgen.loc[target_indices, "p_mw"] *= reduction_factor
    final_p = float(net_copy.sgen.loc[target_indices, "p_mw"].sum())
    mw_curtailed = round(initial_p - final_p, 4)

    renewable_retained_pct = round(100.0 - curtailment_pct, 2)

    metadata = {
        "action_id": f"curtail_{int(curtailment_pct)}pct" + (f"_bus{bus_id}" if bus_id is not None else ""),
        "action_type": "CURTAILMENT",
        "name": f"Solar Curtailment ({curtailment_pct:.0f}%)",
        "curtailment_pct": round(curtailment_pct, 1),
        "target_buses": [int(b) for b in net_copy.sgen.loc[target_indices, "bus"].unique()],
        "affected_sgens": [int(i) for i in target_indices],
        "initial_p_mw": round(initial_p, 4),
        "final_p_mw": round(final_p, 4),
        "mw_curtailed": mw_curtailed,
        "renewable_retained_pct": renewable_retained_pct,
        "cost_proxy": 3,  # Highest cost: wastes clean renewable generation
        "description": f"Curtailed solar generation by {curtailment_pct:.0f}% across {len(target_indices)} units (-{mw_curtailed:.3f} MW wasted).",
    }

    return net_copy, metadata


def apply_battery_dispatch(
    net: pp.pandapowerNet,
    p_mw: float,
    bus_id: Optional[int] = None,
    storage_id: Optional[int] = None,
) -> Tuple[pp.pandapowerNet, Dict[str, Any]]:
    """
    Dispatch energy storage battery to absorb excess solar or inject power.
    
    Pandapower sign convention:
    - Positive p_mw: CHARGING (load behavior, absorbs active power to suppress overvoltage).
    - Negative p_mw: DISCHARGING (generator behavior, injects active power to elevate undervoltage).
    
    Args:
        net (pp.pandapowerNet): Pandapower network.
        p_mw (float): Dispatch active power in MW.
        bus_id (Optional[int]): Bus location of battery (default: Battery 1 at Bus 5).
        storage_id (Optional[int]): Index of storage unit in net.storage.
        
    Returns:
        Tuple[pp.pandapowerNet, Dict[str, Any]]: Modified net copy and action metadata.
    """
    net_copy = copy.deepcopy(net)

    # Ensure net has storage elements; if not, create one
    if not hasattr(net_copy, "storage") or net_copy.storage.empty:
        target_bus = bus_id if bus_id is not None else 5
        pp.create_storage(
            net_copy,
            bus=target_bus,
            p_mw=float(p_mw),
            max_e_mwh=2.0,
            name=f"Battery Bus {target_bus}",
            type="Battery",
            min_p_mw=-1.0,
            max_p_mw=1.0,
            in_service=True
        )
        target_idx = len(net_copy.storage) - 1
    else:
        if storage_id is not None and storage_id in net_copy.storage.index:
            target_idx = storage_id
        elif bus_id is not None:
            matches = net_copy.storage[net_copy.storage["bus"] == bus_id].index
            if len(matches) > 0:
                target_idx = matches[0]
            else:
                # Add battery at the requested bus
                pp.create_storage(
                    net_copy,
                    bus=bus_id,
                    p_mw=float(p_mw),
                    max_e_mwh=2.0,
                    name=f"Battery Bus {bus_id}",
                    type="Battery",
                    min_p_mw=-1.0,
                    max_p_mw=1.0,
                    in_service=True
                )
                target_idx = len(net_copy.storage) - 1
        else:
            # Default to Battery 1 (bus 5)
            target_idx = net_copy.storage.index[0]

        net_copy.storage.loc[target_idx, "p_mw"] = float(p_mw)
        net_copy.storage.loc[target_idx, "in_service"] = True

    b_bus = int(net_copy.storage.loc[target_idx, "bus"])
    b_name = str(net_copy.storage.loc[target_idx, "name"]) if "name" in net_copy.storage.columns else f"Battery {target_idx}"
    mode = "CHARGING (absorb power)" if p_mw > 0 else ("DISCHARGING (inject power)" if p_mw < 0 else "IDLE")

    metadata = {
        "action_id": f"battery_{'+' if p_mw > 0 else ''}{p_mw:.2f}mw_bus{b_bus}",
        "action_type": "BATTERY_DISPATCH",
        "name": f"Battery Dispatch ({'+' if p_mw > 0 else ''}{p_mw:.2f} MW)",
        "storage_id": int(target_idx),
        "bus_id": b_bus,
        "battery_name": b_name,
        "p_mw": round(float(p_mw), 3),
        "mode": mode,
        "renewable_retained_pct": 100.0,  # 100% clean energy preserved (stored, not wasted)
        "cost_proxy": 2,  # Moderate cost: battery cycling/wear, but zero energy waste
        "description": f"Dispatched {b_name} at Bus {b_bus} to {p_mw:+.2f} MW ({mode}). 100% clean energy preserved.",
    }

    return net_copy, metadata


def apply_feeder_reconfiguration(
    net: pp.pandapowerNet,
    switch_id: Optional[int] = None,
    switch_name: Optional[str] = None,
) -> Tuple[pp.pandapowerNet, Dict[str, Any]]:
    """
    Apply feeder reconfiguration by closing a normally-open tie-switch (S1, S2, or S3).
    
    CIGRE MV tie-switches:
    - Switch 4 (S1): Connects Bus 8 <-> Line 14 <-> Bus 14 (Feeder 1 to Feeder 2 tie)
    - Switch 1 (S2): Connects Bus 7 <-> Line 12 <-> Bus 6 (Branch loop tie)
    - Switch 2 (S3): Connects Bus 4 <-> Line 13 <-> Bus 11 (Feeder cross tie)
    
    Args:
        net (pp.pandapowerNet): Pandapower network.
        switch_id (Optional[int]): Switch index in net.switch.
        switch_name (Optional[str]): Switch name ('S1', 'S2', 'S3').
        
    Returns:
        Tuple[pp.pandapowerNet, Dict[str, Any]]: Modified net copy and action metadata.
    """
    net_copy = copy.deepcopy(net)

    if not hasattr(net_copy, "switch") or net_copy.switch.empty:
        raise ValueError("Network contains no switch elements for reconfiguration.")

    target_idx = None
    if switch_name is not None and "name" in net_copy.switch.columns:
        matches = net_copy.switch[net_copy.switch["name"] == switch_name].index
        if len(matches) > 0:
            target_idx = matches[0]

    if target_idx is None and switch_id is not None and switch_id in net_copy.switch.index:
        target_idx = switch_id

    # Default to switch S1 (index 4 in CIGRE MV)
    if target_idx is None:
        target_idx = 4 if 4 in net_copy.switch.index else net_copy.switch.index[0]

    s_name = str(net_copy.switch.loc[target_idx, "name"]) if "name" in net_copy.switch.columns and pd.notna(net_copy.switch.loc[target_idx, "name"]) else f"Switch {target_idx}"
    s_bus = int(net_copy.switch.loc[target_idx, "bus"])
    s_elem = int(net_copy.switch.loc[target_idx, "element"])
    s_type = str(net_copy.switch.loc[target_idx, "et"])

    # Close the switch (tie-line activated)
    prev_closed = bool(net_copy.switch.loc[target_idx, "closed"])
    net_copy.switch.loc[target_idx, "closed"] = True

    metadata = {
        "action_id": f"reconfig_switch_{target_idx}",
        "action_type": "FEEDER_RECONFIGURATION",
        "name": f"Feeder Reconfiguration ({s_name})",
        "switch_id": int(target_idx),
        "switch_name": s_name,
        "bus_id": s_bus,
        "element": s_elem,
        "element_type": s_type,
        "previous_state": "CLOSED" if prev_closed else "OPEN",
        "new_state": "CLOSED",
        "renewable_retained_pct": 100.0,  # Zero generation altered
        "cost_proxy": 1,  # Lowest cost: pure network switching, zero energy loss
        "description": f"Closed tie-switch {s_name} at Bus {s_bus} (Line {s_elem}) to redistribute power flow across feeders.",
    }

    return net_copy, metadata
