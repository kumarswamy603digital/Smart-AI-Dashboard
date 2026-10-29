"""Root layout: header + sidebar + filter rail + all sections (toggled via CSS)."""
from __future__ import annotations

from dash import dcc, html

from src.components.chart_panels import (
    build_ai_status_panel_static, build_analytics_controls,
    build_overview_charts, chart_card,
)
from src.components.data_table import table_card
from src.components.filter_panel import build_filter_panel
from src.components.header import build_header
from src.components.insight_cards import build_ai_studio
from src.components.kpi_cards import kpi_row
from src.components.sidebar import SECTIONS, build_sidebar


def _empty_section_cls(key: str) -> str:
    return "section" + ("" if key == "overview" else " hidden")


def build_layout() -> html.Div:
    stores = [
        dcc.Store(id="session-token", storage_type="session"),
        dcc.Store(id="dataset-ver", data=0),
        dcc.Store(id="filters-store", data={}),
        dcc.Store(id="ai-history", data=[]),
        dcc.Store(id="ai-last-result", data=None),
        dcc.Download(id="download-data"),
    ]

    overview = html.Section(
        id="section-overview", className=_empty_section_cls("overview"),
        children=[
            html.H2("Overview", className="section-title"),
            html.P("Key business measures recomputed from the active dataset and filters on every change.",
                   className="section-sub"),
            html.Div(id="kpi-row", children=kpi_row([])),
            *build_overview_charts(),
            html.Div(className="chart-duo", children=[
                table_card("Recent records", "recent-table",
                           "Sample of the filtered data — sortable and searchable"),
                html.Section(className="chart-card", children=[
                    html.Div(className="chart-head", children=[
                        html.H3("AI insight preview", className="chart-title")]),
                    html.Div(id="ai-preview", className="table-body",
                             children=html.P("Ask a question in AI Insights Studio.",
                                             className="empty-note")),
                ]),
            ]),
        ],
    )

    explorer = html.Section(
        id="section-explorer", className=_empty_section_cls("explorer"),
        children=[
            html.H2("Data Explorer", className="section-title"),
            html.P("Upload a CSV, inspect its schema and quality, and clean it explicitly. "
                   "Uploaded content is parsed as data only — never executed.", className="section-sub"),
            html.Div(className="upload-band", children=[
                dcc.Upload(
                    id="csv-upload", className="upload-zone",
                    accept=".csv", multiple=False,
                    contents=None, filename=None,
                    children=html.Div([
                        "Drag & drop a .csv here or ",
                        html.A("browse files", className="upload-link"),
                    ]),
                ),
                html.Div(id="upload-status", className="upload-status"),
            ]),
            html.Div(className="clean-band", children=[
                html.Div("Explicit cleaning (applies to a copy — the original upload is preserved)",
                         className="fp-heading"),
                dcc.Checklist(
                    id="clean-options",
                    options=[
                        {"label": " Drop rows with missing values", "value": "na"},
                        {"label": " Drop duplicate rows", "value": "dups"},
                    ],
                    value=[], className="check-row"),
                html.Button("Apply cleaning", id="clean-apply-btn",
                            className="btn btn-primary", n_clicks=0),
                html.Div(id="cleaning-status", className="upload-status"),
            ]),
            table_card("Column schema", "schema-table",
                       "Inferred types, missing counts, distinct values"),
            table_card("Data preview", "preview-table", "First rows of the active dataset"),
            html.Div(className="chart-duo", children=[
                table_card("Numeric summaries", "numeric-table"),
                table_card("Missing-value analysis", "missing-table"),
            ]),
            html.Section(className="chart-card", children=[
                html.Div(className="chart-head", children=[
                    html.H3("Quality warnings", className="chart-title")]),
                html.Div(id="warnings-list", className="table-body"),
            ]),
        ],
    )

    analytics = html.Section(
        id="section-analytics", className=_empty_section_cls("analytics"),
        children=[
            html.H2("Interactive Analytics", className="section-title"),
            html.P("Choose a dimension, measure, aggregation and chart type — results come "
                   "straight from pandas on the filtered data.", className="section-sub"),
            *build_analytics_controls(),
            chart_card("Custom chart", "an-graph"),
            table_card("Computed results", "an-results"),
            html.Div(className="chart-duo", children=[
                chart_card("Correlation heatmap", "corr-graph",
                           "Pearson r over numeric columns; association ≠ causation"),
                html.Section(className="chart-card", children=[
                    html.Div(className="chart-head", children=[
                        html.H3("Outlier investigation", className="chart-title"),
                        html.P("Transparent IQR / z-score baseline on a chosen column.",
                               className="chart-sub")]),
                    html.Div(className="selector-grid", children=[
                        html.Div([html.Label("Column", className="fp-label"),
                                  dcc.Dropdown(id="out-col", options=[], className="fp-input")]),
                        html.Div([html.Label("Method", className="fp-label"),
                                  dcc.Dropdown(id="out-method",
                                               options=[{"label": "IQR (1.5×)", "value": "iqr"},
                                                        {"label": "z-score (3σ)", "value": "zscore"}],
                                               value="iqr", className="fp-input")]),
                    ]),
                    html.Div(id="out-info", className="fp-desc"),
                    html.Div(id="out-table", className="table-body"),
                ]),
            ]),
        ],
    )

    status = html.Section(
        id="section-status", className=_empty_section_cls("status"),
        children=[
            html.H2("Model & AI Status", className="section-title"),
            html.P("Configuration is read from the backend environment. The full API key is never displayed.",
                   className="section-sub"),
            build_ai_status_panel_static(),
        ],
    )

    export = html.Section(
        id="section-export", className=_empty_section_cls("export"),
        children=[
            html.H2("Export Center", className="section-title"),
            html.P("Downloads reflect the active dataset and current filters.", className="section-sub"),
            html.Div(className="export-grid", children=[
                html.Button("Download filtered data (CSV)", id="dl-filtered-btn",
                            className="btn btn-primary btn-lg", n_clicks=0),
                html.Button("Download aggregated results (CSV)", id="dl-agg-btn",
                            className="btn btn-primary btn-lg", n_clicks=0),
                html.Button("Download analysis report (Markdown)", id="dl-report-btn",
                            className="btn btn-primary btn-lg", n_clicks=0),
            ]),
            html.Div(id="export-status", className="upload-status"),
        ],
    )

    return html.Div(id="app-root", className="app-shell", children=[
        *stores,
        build_header(),
        html.Div(className="app-body", children=[
            build_sidebar(),
            html.Main(className="main-col", children=[
                overview, explorer, analytics, build_ai_studio(), status, export,
            ]),
            build_filter_panel(),
        ]),
    ])
