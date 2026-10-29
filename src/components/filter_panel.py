"""Global filter panel — writes into the filters store, never queries directly."""
from __future__ import annotations

from dash import dcc, html


def _opt(value: str) -> dict:
    return {"label": str(value), "value": str(value)}


def build_filter_panel() -> html.Aside:
    return html.Aside(
        className="filter-panel",
        children=[
            html.Div("Filters", className="fp-heading"),
            html.Div(className="fp-group", children=[
                html.Div("Time range", className="fp-label"),
                html.Label("Date column", className="fp-label"),
                dcc.Dropdown(id="flt-date-col", options=[], placeholder="none detected",
                             className="fp-input"),
                html.Div(className="fp-row", children=[
                    dcc.DatePickerSingle(id="flt-date-start", placeholder="From",
                                         display_format="YYYY-MM-DD", className="fp-input"),
                    dcc.DatePickerSingle(id="flt-date-end", placeholder="To",
                                         display_format="YYYY-MM-DD", className="fp-input"),
                ]),
            ]),
            html.Div(className="fp-group", children=[
                html.Div("Category dimension", className="fp-label"),
                dcc.Dropdown(id="flt-dimension", options=[], placeholder="dimension",
                             className="fp-input"),
                dcc.Dropdown(id="flt-dimension-values", options=[], multi=True,
                             placeholder="all values", className="fp-input"),
            ]),
            html.Div(className="fp-group", children=[
                html.Div("Numeric range", className="fp-label"),
                dcc.Dropdown(id="flt-num-col", options=[], placeholder="column",
                             className="fp-input"),
                html.Div(className="fp-row", children=[
                    dcc.Input(id="flt-num-min", type="number", placeholder="min",
                              className="fp-input"),
                    dcc.Input(id="flt-num-max", type="number", placeholder="max",
                              className="fp-input"),
                ]),
            ]),
            html.Div(className="fp-actions", children=[
                html.Button("Apply filters", id="flt-apply-btn", className="btn btn-primary"),
                html.Button("Clear", id="flt-clear-btn", className="btn btn-ghost"),
            ]),
            html.Div(id="flt-desc", className="fp-desc"),
        ],
    )


def filter_state(date_col, date_start, date_end, dimension, dimension_values,
                 numeric_col, num_min, num_max) -> dict:
    """Normalize raw component values into the canonical filters payload."""
    return {
        "date_col": date_col,
        "date_start": date_start or None,
        "date_end": date_end or None,
        "dimension": dimension,
        "dimension_values": list(dimension_values or []),
        "numeric_col": numeric_col,
        "num_min": None if num_min in (None, "") else float(num_min),
        "num_max": None if num_max in (None, "") else float(num_max),
    }
