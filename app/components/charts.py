"""
Time-series visualization components for Solar irradiance and synthetic demand load profiles.
"""

import plotly.graph_objects as go
import pandas as pd


def render_time_series_charts(aligned_df: pd.DataFrame) -> go.Figure:
    """
    Render time-series comparison chart for Pune solar generation vs synthetic load demand.
    
    Args:
        aligned_df (pd.DataFrame): Time-aligned DataFrame containing solar_pu and load_pu columns.
        
    Returns:
        go.Figure: Plotly figure object.
    """
    fig = go.Figure()

    # Solar trace
    fig.add_trace(
        go.Scatter(
            x=aligned_df.index,
            y=aligned_df["solar_pu"],
            mode="lines",
            name="Solar Generation (Pune PVGIS, p.u.)",
            line=dict(color="#f59e0b", width=2),
            fill="tozeroy",
            fillcolor="rgba(245, 158, 11, 0.1)"
        )
    )

    # Load demand trace
    fig.add_trace(
        go.Scatter(
            x=aligned_df.index,
            y=aligned_df["load_pu"],
            mode="lines",
            name="Synthetic Customer Load (p.u.)",
            line=dict(color="#3b82f6", width=2.5)
        )
    )

    fig.update_layout(
        title=dict(
            text="Hourly Solar Generation vs. Customer Load Demand Profile",
            font=dict(size=18, color="#0f172a")
        ),
        xaxis=dict(title="Timestamp (UTC / Local)", showgrid=True, gridcolor="#e2e8f0"),
        yaxis=dict(title="Normalized Magnitude (p.u.)", showgrid=True, gridcolor="#e2e8f0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=420,
        margin=dict(l=40, r=40, t=60, b=40)
    )

    return fig
