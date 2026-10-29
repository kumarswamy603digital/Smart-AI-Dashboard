"""Reusable Plotly chart builders — every figure comes from real data.

Each builder degrades to a labelled empty-state figure when inputs are
missing or produce no rows, so the UI never shows fabricated values.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.visualization.themes import apply_theme, empty_figure


def _fmt_col(col: str) -> str:
    return str(col).replace("_", " ").title()


def line_trend(series: pd.DataFrame, x: str, y: str, title: str = "Trend",
               color: str | None = None, height: int = 380) -> go.Figure:
    if series is None or series.empty:
        return empty_figure("No time periods available for the current data and filters.")
    fig = px.line(series, x=x, y=y, color=color, markers=True)
    fig.update_xaxes(title=_fmt_col(x))
    fig.update_yaxes(title=_fmt_col(y))
    return apply_theme(fig, title, height=height)


def bar_chart(data: pd.DataFrame, x: str, y: str, title: str = "Breakdown",
              orientation: str = "v", color: str | None = None,
              barmode: str = "relative", height: int = 380) -> go.Figure:
    if data is None or data.empty:
        return empty_figure("No categories matched — try relaxing the filters.")
    fig = px.bar(data, x=x, y=y, orientation=orientation, color=color, barmode=barmode)
    fig.update_xaxes(title=_fmt_col(x))
    fig.update_yaxes(title=_fmt_col(y))
    return apply_theme(fig, title, height=height)


def grouped_bar(data: pd.DataFrame, x: str, y: str, color: str,
                title: str = "Grouped comparison", stack: bool = False,
                height: int = 380) -> go.Figure:
    if data is None or data.empty:
        return empty_figure("No grouped data available for the current selection.")
    fig = px.bar(data, x=x, y=y, color=color, barmode="stack" if stack else "group")
    return apply_theme(fig, title, height=height)


def histogram(df: pd.DataFrame, column: str, title: str | None = None,
              height: int = 340) -> go.Figure:
    if df is None or column not in getattr(df, "columns", []) or df[column].dropna().empty:
        return empty_figure(f"Column '{column}' has no numeric values to distribute.")
    fig = px.histogram(df, x=column, nbins=30, marginal="box")
    fig.update_xaxes(title=_fmt_col(column))
    fig.update_yaxes(title="Count")
    return apply_theme(fig, title or f"{_fmt_col(column)} distribution", height=height)


def scatter(df: pd.DataFrame, x: str, y: str, color: str | None = None,
            title: str = "Relationship", height: int = 380) -> go.Figure:
    if df is None or df.empty or x not in df.columns or y not in df.columns:
        return empty_figure("Scatter needs two numeric columns present in the current data.")
    fig = px.scatter(df, x=x, y=y, color=color, opacity=0.7,
                     hover_data=[c for c in df.columns if c not in (x, y, color)][:2])
    fig.update_xaxes(title=_fmt_col(x))
    fig.update_yaxes(title=_fmt_col(y))
    return apply_theme(fig, title, height=height)


def box_plot(df: pd.DataFrame, column: str, by: str | None = None,
             title: str | None = None, height: int = 340) -> go.Figure:
    if df is None or column not in getattr(df, "columns", []):
        return empty_figure(f"Column '{column}' is not available for distribution analysis.")
    fig = px.box(df, x=by, y=column, points="outliers")
    fig.update_yaxes(title=_fmt_col(column))
    return apply_theme(fig, title or f"{_fmt_col(column)} distribution", height=height)


def correlation_heatmap(corr: pd.DataFrame, title: str = "Correlation",
                        height: int = 420) -> go.Figure:
    if corr is None or corr.empty:
        return empty_figure("Need at least two varying numeric columns for correlation.")
    fig = go.Figure(
        go.Heatmap(
            z=corr.to_numpy(), x=list(corr.columns), y=list(corr.columns),
            zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
            text=corr.round(2).to_numpy(), texttemplate="%{text}",
            colorbar=dict(title="r"),
        )
    )
    fig.update_layout(xaxis=dict(tickangle=-45))
    return apply_theme(fig, title, height=height)


def pie_chart(data: pd.DataFrame, names: str, values: str, title: str = "Share",
              height: int = 360) -> go.Figure:
    if data is None or data.empty:
        return empty_figure("No groups available for a share breakdown.")
    fig = px.pie(data, names=names, values=values, hole=0.45)
    return apply_theme(fig, title, height=height)


CHART_TYPES = ["bar", "line", "grouped_bar", "stacked_bar", "histogram",
               "scatter", "box", "pie"]


def build_figure(df: pd.DataFrame, chart_type: str, dimension: str, measure: str,
                 color: str | None = None, top_n: int | None = None,
                 aggfunc: str = "sum", title: str | None = None) -> go.Figure:
    """Dispatch the analytics tab chart-type selector to the right builder."""
    from src.analytics.aggregations import group_aggregate

    default_title = title or (
        f"{aggfunc.title()} of {_fmt_col(measure)} by {_fmt_col(dimension)}"
    )
    try:
        if chart_type in ("bar", "line", "pie"):
            agg = group_aggregate(df, dimension, measure, aggfunc=aggfunc, top_n=top_n)
            if chart_type == "bar":
                return bar_chart(agg, dimension, measure, default_title,
                                 orientation="h" if len(agg) > 8 else "v")
            if chart_type == "line":
                return line_trend(agg, dimension, measure, default_title)
            return pie_chart(agg.head(min(len(agg), 8)), dimension, measure, default_title)
        if chart_type in ("grouped_bar", "stacked_bar"):
            if not color or color == dimension:
                agg = group_aggregate(df, dimension, measure, aggfunc=aggfunc, top_n=top_n)
                return bar_chart(agg, dimension, measure, default_title)
            data = df.groupby([dimension, color], dropna=True)[measure].agg(aggfunc).reset_index()
            if data.empty:
                return empty_figure("No grouped data for the current selection.")
            return grouped_bar(data.head(200), dimension, measure, color, default_title,
                               stack=chart_type == "stacked_bar")
        if chart_type == "histogram":
            return histogram(df, measure, default_title)
        if chart_type == "box":
            return box_plot(df, measure, by=dimension if dimension in df.columns else None,
                            title=default_title)
        if chart_type == "scatter":
            num_cols = [c for c in df.select_dtypes(include="number").columns if c in (measure, dimension)]
            x = dimension if dimension in num_cols else (num_cols[0] if num_cols else measure)
            return scatter(df.head(3000), x, measure, color=color, title=default_title)
    except (KeyError, ValueError) as exc:
        return empty_figure(str(exc))
    return empty_figure(f"Chart type '{chart_type}' is not supported.")
