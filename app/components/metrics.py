"""
Streamlit Metrics Summary Component.
"""

from typing import Dict, Any
import streamlit as st


def render_metrics(summary: Dict[str, Any]):
    """
    Render key grid power-flow metrics as Streamlit summary cards.
    
    Args:
        summary (Dict[str, Any]): Metrics dictionary from src.grid.get_grid_summary.
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Grid Buses",
            value=summary.get("bus_count", 0),
            delta="15 kV Distribution"
        )

    with col2:
        st.metric(
            label="Total DER Count",
            value=summary.get("der_count", 0),
            delta=f"{summary.get('sgen_count', 0)} Solar / DER"
        )

    with col3:
        vm_min = summary.get("vm_pu_min", 0.0)
        vm_max = summary.get("vm_pu_max", 0.0)
        st.metric(
            label="Voltage Range",
            value=f"{vm_min:.3f} - {vm_max:.3f} p.u.",
            delta="Safe (0.95 - 1.05 p.u.)" if (vm_min >= 0.95 and vm_max <= 1.05) else "Warning",
            delta_color="normal" if (vm_min >= 0.95 and vm_max <= 1.05) else "inverse"
        )

    with col4:
        max_load = summary.get("max_line_loading_percent", 0.0)
        st.metric(
            label="Max Line Loading",
            value=f"{max_load:.1f}%",
            delta="Normal (< 100%)" if max_load <= 100 else "Overload Warning",
            delta_color="normal" if max_load <= 100 else "inverse"
        )
