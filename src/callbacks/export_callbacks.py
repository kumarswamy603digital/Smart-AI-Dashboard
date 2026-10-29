"""Download callbacks: filtered CSV, aggregated CSV, Markdown report."""
from __future__ import annotations

from dash import Input, Output, State, html, ctx

from src.ai.schemas import InsightResponse
from src.analytics.aggregations import group_aggregate
from src.services.dashboard_service import get_filtered_view
from src.services.export_service import csv_download, report_download


def register(app) -> None:
    @app.callback(
        [Output("download-data", "data"),
         Output("export-status", "children")],
        [Input("dl-filtered-btn", "n_clicks"),
         Input("dl-agg-btn", "n_clicks"),
         Input("dl-report-btn", "n_clicks")],
        [State("session-token", "data"),
         State("dataset-ver", "data"),
         State("filters-store", "data"),
         State("an-dimension", "value"),
         State("an-measure", "value"),
         State("an-agg", "value"),
         State("ai-last-result", "data")],
        prevent_initial_call=True,
    )
    def download(f_n, a_n, r_n, token, ver, filters, dimension, measure, agg, last_result):
        triggered = ctx.triggered_id
        df, desc, name = get_filtered_view(token, filters)
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:40]
        if df.empty:
            return None, html.Div("Nothing to export — current filters return zero rows.",
                                  className="notice-err")
        if triggered == "dl-filtered-btn":
            payload = csv_download(df, f"filtered_{safe}.csv")
            return payload, html.Div(
                f"Downloaded {len(df):,} filtered rows as CSV.", className="notice-ok")
        if triggered == "dl-agg-btn":
            if not dimension or not measure or dimension not in df.columns or measure not in df.columns:
                return None, html.Div(
                    "Pick a dimension and measure in Interactive Analytics first.",
                    className="notice-err")
            try:
                agg_df = group_aggregate(df, dimension, measure, agg or "sum")
            except (KeyError, ValueError) as exc:
                return None, html.Div(str(exc), className="notice-err")
            payload = csv_download(agg_df, f"agg_{measure}_by_{dimension}.csv".replace(" ", "_"))
            return payload, html.Div(
                f"Downloaded {len(agg_df)} aggregated rows ({agg or 'sum'} of {measure} "
                f"by {dimension}).", className="notice-ok")
        if triggered == "dl-report-btn":
            insight = None
            ai_used = False
            if isinstance(last_result, dict) and last_result.get("insight"):
                try:
                    insight = InsightResponse.model_validate(last_result["insight"])
                    ai_used = bool(last_result.get("ai_used"))
                except Exception:  # noqa: BLE001
                    insight = None
            payload = report_download(df, name, desc, insight, ai_used)
            return payload, html.Div(
                "Report generated: computed KPIs and quality profile first, AI narrative "
                "(if any) clearly separated with caveats.", className="notice-ok")
        return None, html.Div()
