"""
Plotly Network Diagram Component for visualizing CIGRE MV distribution grid topology and bus voltage levels.
"""

import plotly.graph_objects as go
import pandas as pd


def render_network_diagram(bus_df: pd.DataFrame, line_df: pd.DataFrame) -> go.Figure:
    """
    Build an interactive Plotly diagram representing network topology, colored by bus voltage vm_pu.
    
    Args:
        bus_df (pd.DataFrame): Buses dataframe containing x, y coordinates and vm_pu results.
        line_df (pd.DataFrame): Lines dataframe containing endpoint coordinates and loading_percent.
        
    Returns:
        go.Figure: Interactive Plotly graph object figure.
    """
    fig = go.Figure()

    # Draw lines connecting buses
    for _, line in line_df.iterrows():
        f_x, f_y = line["from_x"], line["from_y"]
        t_x, t_y = line["to_x"], line["to_y"]
        loading = line.get("loading_percent", 0.0)
        line_name = line.get("name", f"Line {line.name}")

        # Color line based on loading percentage
        line_color = "#38ef7d" if loading <= 80 else ("#f12711" if loading >= 100 else "#f5af19")

        fig.add_trace(
            go.Scatter(
                x=[f_x, t_x, None],
                y=[f_y, t_y, None],
                mode="lines+text",
                line=dict(width=3, color=line_color),
                hoverinfo="text",
                text=f"{line_name}<br>Loading: {loading:.1f}%",
                showlegend=False
            )
        )

    # Prepare bus color mapping based on voltage limits [0.95, 1.05]
    colors = []
    hover_texts = []
    for idx, bus in bus_df.iterrows():
        vm = bus.get("vm_pu", 1.0)
        name = bus.get("name", f"Bus {idx}")
        p_mw = bus.get("p_mw", 0.0)
        q_mvar = bus.get("q_mvar", 0.0)

        if 0.95 <= vm <= 1.05:
            color = "#10b981"  # Emerald green (healthy)
        elif 0.90 <= vm < 0.95 or 1.05 < vm <= 1.10:
            color = "#f59e0b"  # Amber warning
        else:
            color = "#ef4444"  # Red violation

        colors.append(color)
        hover_texts.append(
            f"<b>{name}</b> (Bus {idx})<br>"
            f"Voltage: <b>{vm:.4f} p.u.</b><br>"
            f"Active Power: {p_mw:.3f} MW<br>"
            f"Reactive Power: {q_mvar:.3f} MVar"
        )

    # Draw bus nodes
    fig.add_trace(
        go.Scatter(
            x=bus_df["x"],
            y=bus_df["y"],
            mode="markers+text",
            marker=dict(
                size=22,
                color=colors,
                line=dict(width=2, color="#1e293b")
            ),
            text=[str(i) for i in bus_df.index],
            textposition="middle center",
            textfont=dict(color="#ffffff", size=11, family="Inter, Arial, sans-serif"),
            hoverinfo="text",
            hovertext=hover_texts,
            name="Grid Buses"
        )
    )

    fig.update_layout(
        title=dict(
            text="CIGRE MV Distribution Grid Topology (Color-Coded by Bus Voltage)",
            font=dict(size=18, color="#0f172a")
        ),
        showlegend=False,
        hovermode="closest",
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="#f8fafc",
        paper_bgcolor="#ffffff",
        height=520
    )

    return fig
