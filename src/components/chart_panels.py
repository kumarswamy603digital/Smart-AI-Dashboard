"""Chart section shells — graphs are populated by callbacks with real data."""
from __future__ import annotations

from dash import dcc, html


def chart_card(title: str, graph_id: str, sub: str | None = None,
               controls=None) -> html.Section:
    return html.Section(
        className="chart-card",
        children=[
            html.Div(className="chart-head", children=[
                html.Div([
                    html.H3(title, className="chart-title"),
                    html.P(sub, className="chart-sub") if sub else None,
                ]),
                html.Div(className="chart-controls", children=controls or []),
            ]),
            dcc.Graph(id=graph_id, className="chart-body",
                      config={"displayModeBar": True, "scrollZoom": False}),
        ],
    )


def build_overview_charts() -> list:
    return [
        chart_card("Monthly trend of the primary measure", "ov-trend",
                   "Aggregated in pandas from the filtered dataset"),
        html.Div(className="chart-duo", children=[
            chart_card("By category", "ov-category"),
            chart_card("By region", "ov-region"),
        ]),
    ]


def build_analytics_controls() -> list:
    """Selector row for the Interactive Analytics section."""
    return [
        html.Div(className="selector-grid", children=[
            html.Div([html.Label("Dimension", className="fp-label"),
                      dcc.Dropdown(id="an-dimension", options=[], className="fp-input")]),
            html.Div([html.Label("Measure", className="fp-label"),
                      dcc.Dropdown(id="an-measure", options=[], className="fp-input")]),
            html.Div([html.Label("Aggregation", className="fp-label"),
                      dcc.Dropdown(id="an-agg",
                                   options=[{"label": a, "value": a} for a in
                                            ["sum", "mean", "median", "count", "min", "max"]],
                                   value="sum", className="fp-input")]),
            html.Div([html.Label("Chart type", className="fp-label"),
                      dcc.Dropdown(id="an-chart",
                                   options=[{"label": c.replace("_", " ").title(), "value": c}
                                            for c in ["bar", "line", "grouped_bar", "stacked_bar",
                                                      "histogram", "scatter", "box", "pie"]],
                                   value="bar", className="fp-input")]),
            html.Div([html.Label("Colour by", className="fp-label"),
                      dcc.Dropdown(id="an-color", options=[], className="fp-input")]),
            html.Div([html.Label("Top N", className="fp-label"),
                      dcc.Input(id="an-topn", type="number", min=1, max=100, value=10,
                                className="fp-input")]),
        ]),
    ]


def build_ai_status_panel_static() -> html.Div:
    return html.Div(id="status-panel", className="status-grid")
