"""Table containers used across sections (populated by callbacks)."""
from __future__ import annotations

from dash import html


def table_card(title: str, container_id: str, sub: str | None = None) -> html.Section:
    return html.Section(
        className="chart-card",
        children=[
            html.Div(className="chart-head", children=[
                html.Div([
                    html.H3(title, className="chart-title"),
                    html.P(sub, className="chart-sub") if sub else None,
                ]),
            ]),
            html.Div(id=container_id, className="table-body"),
        ],
    )
