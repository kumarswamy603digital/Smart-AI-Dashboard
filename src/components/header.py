"""Top header: brand, active dataset badge and AI status pill."""
from __future__ import annotations

from dash import dcc, html


def build_header() -> html.Header:
    return html.Header(
        className="app-header",
        children=[
            html.Div(
                className="brand",
                children=[
                    html.Img(src="/assets/logo.svg", className="brand-logo", alt="Logo"),
                    html.Div(
                        [
                            html.H1("AI Insights Dashboard", className="brand-title"),
                            html.P("Interactive analytics with data-grounded natural-language insights",
                                   className="brand-sub"),
                        ]
                    ),
                ],
            ),
            html.Div(
                className="header-meta",
                children=[
                    html.Div(id="dataset-meta", className="meta-chip"),
                    html.Div(id="ai-status-pill", className="meta-chip ai-chip"),
                ],
            ),
        ],
    )


def dataset_meta_children(name: str, rows: int, is_sample: bool, filters_desc: dict) -> list:
    """Content for the dataset chip (called from callbacks)."""
    badge = html.Span("SYNTHETIC DEMO", className="tag tag-amber") if is_sample else \
        html.Span("USER UPLOAD", className="tag tag-blue")
    flt = f" · {len(filters_desc)} filter(s) active" if filters_desc else ""
    return [
        html.Span(badge),
        html.Span(f"  {name} · {rows:,} rows{flt}", className="meta-text"),
    ]
