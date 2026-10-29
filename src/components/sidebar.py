"""Compact left navigation rail."""
from __future__ import annotations

from dash import html

SECTIONS = [
    ("overview", "Overview", "KPIs & trends"),
    ("explorer", "Data Explorer", "Upload & profile"),
    ("analytics", "Analytics", "Interactive charts"),
    ("ai", "AI Insights Studio", "Ask questions"),
    ("status", "Model & AI Status", "Configuration"),
    ("export", "Export Center", "CSV & reports"),
]


def build_sidebar(active: str = "overview") -> html.Nav:
    items = [
        html.Button(
            [
                html.Span(label, className="nav-label"),
                html.Span(desc, className="nav-desc"),
            ],
            id=f"nav-{key}",
            className=f"nav-item{' active' if key == active else ''}",
            n_clicks=0,
            title=desc,
        )
        for key, label, desc in SECTIONS
    ]
    return html.Nav(className="sidebar", children=[
        html.Div("Navigate", className="nav-heading"),
        *items,
        html.Div(className="sidebar-foot", children=[
            html.Button("Reset to sample dataset", id="reset-sample-btn",
                        className="nav-reset", title="Discard the uploaded dataset"),
        ]),
    ])
