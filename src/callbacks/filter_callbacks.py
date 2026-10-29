"""Filter-related callbacks: option population, dimension values, apply/clear."""
from __future__ import annotations

import copy

from dash import Input, Output, State, callback, ctx, dash, html

from src.components.filter_panel import filter_state
from src.services.dashboard_service import detect_columns, get_session


def _opts(values) -> list[dict]:
    return [{"label": str(v), "value": str(v)} for v in values]


def register(app) -> None:
    @app.callback(
        [Output("flt-date-col", "options"),
         Output("flt-dimension", "options"),
         Output("flt-num-col", "options"),
         Output("an-dimension", "options"),
         Output("an-measure", "options"),
         Output("an-color", "options"),
         Output("out-col", "options")],
        [Input("session-token", "data"),
         Input("dataset-ver", "data")],
    )
    def populate_options(token, _ver):
        df = get_session(token)["active_df"]
        roles = detect_columns(df)
        dims = roles["categorical"] or [c for c in roles["text"] if c not in roles["identifier"]]
        nums = roles["numeric"]
        colors = _opts(dims)
        return (
            _opts(roles["date"]), _opts(dims), _opts(nums),
            _opts(dims) or _opts([str(c) for c in df.columns][:12]),
            _opts(nums) or _opts([str(c) for c in df.columns][:12]),
            [{"label": "—", "value": None}] + colors,
            _opts([c for c in nums if str(c).lower() != "quantity"] or nums),
        )

    @app.callback(
        [Output("flt-dimension-values", "options"),
         Output("flt-dimension-values", "value")],
        [Input("flt-dimension", "value"),
         Input("session-token", "data"),
         Input("dataset-ver", "data")],
        prevent_initial_call=False,
    )
    def dimension_values(dim, token, _ver):
        if not dim:
            return [], None
        df = get_session(token)["active_df"]
        if dim not in df.columns:
            return [], None
        vals = sorted(df[dim].dropna().astype(str).unique().tolist())[:200]
        return _opts(vals), None

    @app.callback(
        [Output("filters-store", "data"),
         Output("ai-notice", "children")],
        [Input("flt-apply-btn", "n_clicks"),
         Input("flt-clear-btn", "n_clicks")],
        [State("flt-date-col", "value"), State("flt-date-start", "date"),
         State("flt-date-end", "date"), State("flt-dimension", "value"),
         State("flt-dimension-values", "value"), State("flt-num-col", "value"),
         State("flt-num-min", "value"), State("flt-num-max", "value"),
         State("filters-store", "data")],
    )
    def apply_or_clear(apply_n, clear_n, date_col, d_start, d_end, dim, dim_vals,
                       ncol, nmin, nmax, current):
        if ctx.triggered_id == "flt-clear-btn":
            return {}, html.Span("Filters cleared — showing the full active dataset.",
                                 className="notice-ok")
        try:
            payload = filter_state(date_col, d_start, d_end, dim, dim_vals, ncol, nmin, nmax)
        except (TypeError, ValueError):
            return copy.deepcopy(current or {}), html.Span(
                "Numeric min/max must be valid numbers.", className="notice-err")
        return payload, html.Span("", className="")
