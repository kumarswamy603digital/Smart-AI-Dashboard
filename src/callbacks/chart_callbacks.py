"""Core render callbacks: overview refresh, custom analytics chart, outliers."""
from __future__ import annotations

import pandas as pd
from dash import Input, Output, State, html, no_update

from src.ai.client import get_client
from src.analytics.aggregations import group_aggregate
from src.analytics.anomalies import detect_outliers
from src.analytics.correlations import correlation_matrix
from src.analytics.kpis import compute_kpis, generic_measure_kpis
from src.analytics.time_series import supports_time_series, trend
from src.components.header import dataset_meta_children
from src.components.kpi_cards import kpi_row
from src.data.profiling import profile_dataset, schema_table
from src.services.dashboard_service import (
    detect_columns, get_filtered_view, get_session,
)
from src.visualization import charts
from src.visualization.tables import data_table


def _primary_measure(nums: list[str]) -> str | None:
    for pref in ("sales", "revenue", "amount", "profit"):
        if pref in nums:
            return pref
    return nums[0] if nums else None


def register(app) -> None:
    # ------------------------------------------------------------------ #
    # C1a — full dashboard refresh: every derived view from ONE filtered frame
    # ------------------------------------------------------------------ #
    @app.callback(
        [Output("dataset-meta", "children"),
         Output("kpi-row", "children"),
         Output("ov-trend", "figure"),
         Output("ov-category", "figure"),
         Output("ov-region", "figure"),
         Output("recent-table", "children"),
         Output("schema-table", "children"),
         Output("preview-table", "children"),
         Output("numeric-table", "children"),
         Output("missing-table", "children"),
         Output("warnings-list", "children"),
         Output("corr-graph", "figure"),
         Output("ai-status-pill", "children"),
         Output("status-panel", "children"),
         Output("flt-desc", "children")],
        [Input("session-token", "data"),
         Input("dataset-ver", "data"),
         Input("filters-store", "data"),
         Input("ai-last-result", "data")],
    )
    def refresh(token, _ver, filters, last_result):
        session = get_session(token)
        df, desc, name = get_filtered_view(token, filters)
        roles = detect_columns(df)
        nums, dates = roles["numeric"], roles["date"]
        dims = roles["categorical"]

        # KPIs — sales schema when present, generic measures otherwise.
        if "sales" in nums or "profit" in nums:
            kpis = compute_kpis(df)
        else:
            kpis = generic_measure_kpis(df, nums[:3])

        # Trend chart.
        date_col = dates[0] if dates else None
        measure = _primary_measure(nums)
        if date_col and measure and supports_time_series(df, date_col, measure):
            tr = trend(df, date_col, measure, freq="month")
            trend_fig = charts.line_trend(tr, "period", measure,
                                          f"Monthly {measure}")
        else:
            trend_fig = charts.empty_figure(
                "A time trend needs a date column and a numeric measure — "
                "neither was detected in the current data.")

        # Category / region bars — always two DIFFERENT dimensions when possible.
        non_region = [d for d in dims if "region" not in str(d).lower()]
        cand_region = next((d for d in dims if "region" in str(d).lower()), None)
        dim1 = (non_region[0] if non_region else dims[0] if dims else None)
        dim2 = cand_region or (dims[1] if len(dims) > 1 else None)
        if dim2 == dim1:
            dim2 = None
        if measure and dim1:
            cat_fig = charts.bar_chart(
                group_aggregate(df, dim1, measure, "sum", top_n=10),
                dim1, measure, f"{measure.title()} by {dim1.replace('_', ' ')}",
                orientation="h")
        else:
            cat_fig = charts.empty_figure("No category dimension detected for a breakdown.")
        if measure and dim2:
            reg_fig = charts.bar_chart(
                group_aggregate(df, dim2, measure, "sum", top_n=10),
                dim2, measure, f"{measure.title()} by {dim2.replace('_', ' ')}")
        else:
            reg_fig = charts.empty_figure("No second dimension available for comparison.")

        # Tables.
        recent = data_table(df.tail(50).sort_index(ascending=False), "recent-table-inner",
                            max_rows=50, page_size=8)
        preview = data_table(df, "preview-table-inner", max_rows=25, page_size=8)
        p = profile_dataset(df if not df.empty else session["active_df"])
        schema = data_table(schema_table(p), "schema-table-inner", max_rows=60, page_size=10,
                            floating_filter=False)
        from src.visualization.tables import numeric_summary_table
        numeric_tbl = numeric_summary_table(p.numeric_summary)
        missing_df = pd.DataFrame(
            {"column": list(p.missing_counts), "missing": list(p.missing_counts.values()),
             "missing_%": list(p.missing_pct.values())})
        missing_df = missing_df[missing_df["missing"] > 0].sort_values("missing", ascending=False)
        missing_tbl = data_table(missing_df if not missing_df.empty
                                 else pd.DataFrame({"info": ["No missing values"]}),
                                 "missing-table-inner", max_rows=30, page_size=8,
                                 floating_filter=False)
        warn = ([html.Div(w, className="warn-row") for w in p.warnings]
                or [html.Div("No significant quality issues detected.", className="notice-ok")])

        # Correlation heatmap.
        corr = correlation_matrix(df, nums[:8]) if len(nums) >= 2 else pd.DataFrame()
        corr_fig = charts.correlation_heatmap(corr, "Correlation (Pearson r)")

        # AI status.
        client = get_client()
        st = client.status()
        pill = html.Span([
            html.Span("●", className=("dot-ok" if st["configured"] else "dot-off")),
            html.Span(" AI ready" if st["configured"] else " AI unavailable (local mode)"),
        ], className="pill")

        latest = ""
        if isinstance(last_result, dict):
            if last_result.get("ai_used"):
                latest = (f"Last AI analysis: successful (model '{last_result.get('model')}', "
                          f"{last_result.get('context_chars', 0):,} chars of context sent).")
            else:
                latest = f"Last AI attempt did not use the API: {last_result.get('reason') or 'local mode'}."
        status_grid = [
            _stat("Service", "OpenAI Responses API" if st["configured"] else "Not configured"),
            _stat("API key", st["key_masked"]),
            _stat("Model identifier", st["model"]),
            _stat("Features available",
                  "Charts + analytics + AI narrative" if st["configured"]
                  else "Charts, analytics, exports (AI narrative disabled)"),
            _stat("Request timeout", f"{st['timeout_s']:g}s"),
            _stat("Latest analysis", latest or "None yet in this session"),
        ]

        flt_desc = ("; ".join(f"{k}: {v}" for k, v in desc.items())
                    or "No filters applied") if desc else "No filters applied"
        return (
            dataset_meta_children(name, len(df), session["is_sample"], desc),
            kpi_row(kpis), trend_fig, cat_fig, reg_fig, recent, schema, preview,
            numeric_tbl, missing_tbl, warn, corr_fig, pill, status_grid,
            html.Span(flt_desc, className="fp-desc-text"),
        )

    # ------------------------------------------------------------------ #
    # C4 — Interactive Analytics custom chart + results table
    # ------------------------------------------------------------------ #
    @app.callback(
        [Output("an-graph", "figure"),
         Output("an-results", "children")],
        [Input("session-token", "data"),
         Input("dataset-ver", "data"),
         Input("filters-store", "data"),
         Input("an-dimension", "value"),
         Input("an-measure", "value"),
         Input("an-agg", "value"),
         Input("an-chart", "value"),
         Input("an-color", "value"),
         Input("an-topn", "value")],
    )
    def analytics_chart(token, _ver, filters, dimension, measure, agg, chart_type,
                        color, top_n):
        df, _desc, _name = get_filtered_view(token, filters)
        agg = agg or "sum"
        chart_type = chart_type or "bar"
        if not dimension or not measure:
            return charts.empty_figure("Pick a dimension and a measure above."), \
                html.P("No selection yet.", className="empty-note")
        top_n = None if not top_n or int(top_n) <= 0 else int(top_n)
        color = None if color in (None, "None") else color
        fig = charts.build_figure(df, chart_type, dimension, measure,
                                  color=color, top_n=top_n, aggfunc=agg)
        try:
            if chart_type in ("histogram", "box", "scatter"):
                results_df = df.head(100)
            else:
                results_df = group_aggregate(df, dimension, measure, agg, top_n=top_n)
        except (KeyError, ValueError):
            results_df = pd.DataFrame({"info": ["Aggregation not possible for this selection"]})
        tbl = data_table(results_df, "an-results-inner", max_rows=60, page_size=10,
                         floating_filter=False)
        return fig, tbl

    # ------------------------------------------------------------------ #
    # C5 — Outlier investigation
    # ------------------------------------------------------------------ #
    @app.callback(
        [Output("out-info", "children"),
         Output("out-table", "children")],
        [Input("out-col", "value"),
         Input("out-method", "value"),
         Input("session-token", "data"),
         Input("dataset-ver", "data"),
         Input("filters-store", "data")],
    )
    def outlier_view(col, method, token, _ver, filters):
        df, _desc, _name = get_filtered_view(token, filters)
        if not col or col not in df.columns:
            return html.Span("Choose a numeric column to scan.", className="fp-desc-text"), no_update
        try:
            res = detect_outliers(df, col, method or "iqr")
        except ValueError as exc:
            return html.Span(str(exc), className="notice-err"), no_update
        info = html.Div([
            html.B(f"{res['count']} outlier(s)"),
            html.Span(f" · {res['explanation']}"),
            html.Div("Statistical outliers are flagged for investigation — they are not proven "
                     "errors or fraud.", className="muted-note"),
        ])
        if res["indices"]:
            rows = df.loc[res["indices"]].head(50)
            tbl = data_table(rows, "out-table-inner", max_rows=50, page_size=8, floating_filter=False)
        else:
            tbl = html.P("No rows flagged by this method on this column.", className="empty-note")
        return info, tbl


def _stat(label: str, value: str) -> html.Div:
    return html.Div(className="stat-card", children=[
        html.Div(label, className="stat-label"),
        html.Div(value or "—", className="stat-value"),
    ])
