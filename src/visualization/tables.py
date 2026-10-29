"""Dash DataTable builders for previews, schema views and results."""
from __future__ import annotations

import math

import pandas as pd
from dash import dash_table

from config.settings import settings


def _clean_records(df: pd.DataFrame) -> list[dict]:
    """JSON-safe records: NaN/Inf → None, timestamps → strings."""
    out = {}
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            vals = [None if (v is None or (isinstance(v, float) and not math.isfinite(v)) or pd.isna(v))
                    else v for v in s]
        elif pd.api.types.is_datetime64_any_dtype(s):
            vals = [None if pd.isna(v) else str(v) for v in s]
        else:
            vals = [None if pd.isna(v) else str(v) for v in s]
        out[str(col)] = vals
    n = len(df)
    return [{k: out[k][i] for k in out} for i in range(n)]


def data_table(df: pd.DataFrame, table_id: str, max_rows: int | None = None,
               page_size: int = 12, floating_filter: bool = True):
    """Interactive table with paging and optional column filter box."""
    shown = df.head(max_rows or settings.table_preview_rows)
    columns = [
        {"name": str(c), "id": str(c), "selectable": True, "hideable": True, "type": "text"}
        for c in shown.columns
    ]
    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=_clean_records(shown),
        page_action="native",
        page_current=0,
        page_size=page_size,
        page_count=min(8, max(1, math.ceil(len(shown) / page_size))),
        filter_action="native" if floating_filter else "none",
        sort_action="native",
        style_data={"whiteSpace": "normal", "height": "auto"},
        style_as_list_view=True,
        style_cell={"padding": "8px 10px", "fontSize": "12.5px", "textAlign": "left",
                    "border": "none", "borderBottom": "1px solid #EEF1F6",
                    "minWidth": "90px", "maxWidth": "180px"},
        style_header={"fontWeight": 600, "backgroundColor": "#F6F8FC",
                      "borderBottom": "2px solid #DDE3EE", "color": "#37415A"},
        style_filter={"backgroundColor": "#FFFFFF", "border": "none",
                      "borderBottom": "1px solid #EEF1F6"},
    )


def numeric_summary_table(summary: pd.DataFrame | None):
    """describe()-style numeric summary rendered as a compact table."""
    if summary is None or summary.empty:
        return dash_table.DataTable(
            id="numeric-summary", columns=[{"name": "info", "id": "info"}],
            data=[{"info": "No numeric columns detected."}], page_action="none")
    summary = summary.round(3).reset_index().rename(columns={"index": "column"})
    return data_table(summary, "numeric-summary", max_rows=30, page_size=10,
                      floating_filter=False)
