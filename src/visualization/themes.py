"""Consistent Plotly styling shared by every chart in the dashboard."""
from __future__ import annotations

import plotly.graph_objects as go

PALETTE = ["#4C8DFF", "#22C1A4", "#F2A65A", "#E45B8A", "#8E7CE8",
           "#59C3DB", "#F26D6D", "#9ACD5C", "#C9A66B", "#7A8CA3"]

FONT_FAMILY = "'Inter', 'Segoe UI', system-ui, sans-serif"


def apply_theme(fig: go.Figure, title: str | None = None, height: int = 380,
                showlegend: bool | None = None) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#1C2333")) if title else None,
        template="plotly_white",
        height=height,
        margin=dict(l=40, r=20, t=60 if title else 20, b=40),
        font=dict(family=FONT_FAMILY, size=12, color="#37415A"),
        colorway=PALETTE,
        hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONT_FAMILY, size=12, color="#1C2333")),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0)
        if showlegend is None or showlegend else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="#EDF0F5", zerolinecolor="#E3E7EF")
    fig.update_yaxes(gridcolor="#EDF0F5", zerolinecolor="#E3E7EF")
    return fig


def empty_figure(message: str, height: int = 320) -> go.Figure:
    """Helpful empty state rendered as a Plotly figure."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"<b>Nothing to chart</b><br><span style='font-size:13px;color:#6B7488'>{message}</span>",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(family=FONT_FAMILY, size=15, color="#9AA3B5"),
        align="center",
    )
    fig.update_layout(
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        height=height, margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
