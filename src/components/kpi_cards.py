"""Consistent KPI cards rendered from computed KPI objects."""
from __future__ import annotations

from dash import html

from src.analytics.kpis import KPI


def _fmt(v: float | None, fmt: str) -> str:
    if v is None:
        return "n/a"
    if fmt == "currency":
        return f"${v:,.0f}" if abs(v) >= 1000 else f"${v:,.2f}"
    if fmt == "percent":
        return f"{v:.1f}%"
    if fmt == "count":
        return f"{int(v):,}"
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"


def kpi_card(kpi: KPI) -> html.Div:
    negative = kpi.value is not None and kpi.value < 0
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(kpi.label, className="kpi-label"),
            html.Div(
                _fmt(kpi.value, kpi.fmt),
                className=("kpi-value" + (" kpi-neg" if negative else "")),
                title=kpi.formula,
            ),
            html.Div(kpi.formula, className="kpi-formula"),
        ],
    )


def kpi_row(kpis: list[KPI]) -> html.Div:
    if not kpis:
        return html.Div(className="empty-note",
                        children="No KPI-eligible numeric measures found. Pick measures in Analytics.")
    return html.Div(className="kpi-grid", children=[kpi_card(k) for k in kpis])
