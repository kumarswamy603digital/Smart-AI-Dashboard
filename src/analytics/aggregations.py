"""Grouped aggregations, date bucketing, top/bottom ranking, sorting."""
from __future__ import annotations

import pandas as pd

AGG_FUNCS = ["sum", "mean", "median", "count", "min", "max"]
DATE_FREQS = {"day": "D", "week": "W-SUN", "month": "MS", "year": "YS"}


def group_aggregate(
    df: pd.DataFrame,
    dimension: str,
    measure: str,
    aggfunc: str = "sum",
    sort: str = "desc",
    top_n: int | None = None,
) -> pd.DataFrame:
    """Aggregate `measure` by `dimension`. Returns columns [dimension, measure]."""
    if dimension not in df.columns or measure not in df.columns:
        raise KeyError(f"Missing column: {dimension if dimension not in df.columns else measure}")
    if aggfunc not in AGG_FUNCS:
        raise ValueError(f"Unsupported aggregation '{aggfunc}'. Use one of {AGG_FUNCS}")
    g = df.groupby(dimension, dropna=True)[measure]
    out = getattr(g, "count" if aggfunc == "count" else aggfunc)().reset_index()
    out[measure] = pd.to_numeric(out[measure], errors="coerce")
    if aggfunc == "count":
        out[measure] = out[measure].fillna(0).astype(int)
    asc = sort == "asc"
    out = out.sort_values(measure, ascending=asc, na_position="last")
    if top_n and top_n > 0:
        out = out.head(top_n)
    return out.reset_index(drop=True)


def date_aggregate(
    df: pd.DataFrame,
    date_col: str,
    measure: str,
    freq: str = "month",
    aggfunc: str = "sum",
) -> pd.DataFrame:
    """Bucket by day/week/month/year and aggregate. Returns [period, measure]."""
    if date_col not in df.columns or measure not in df.columns:
        raise KeyError(f"Missing column: {date_col} or {measure}")
    if freq not in DATE_FREQS:
        raise ValueError(f"Unsupported frequency '{freq}'. Use one of {list(DATE_FREQS)}")
    tmp = df[[date_col, measure]].copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
    tmp = tmp.dropna(subset=[date_col])
    if tmp.empty:
        raise ValueError(f"No valid dates in column '{date_col}'.")
    idx = pd.DatetimeIndex(tmp[date_col])
    grouped = tmp.set_index(idx).groupby(pd.Grouper(freq=DATE_FREQS[freq]))[measure]
    out = getattr(grouped, aggfunc)().reset_index()
    out.columns = ["period", measure]
    if aggfunc == "count":
        out[measure] = out[measure].fillna(0).astype(int)
    return out


def top_bottom(df: pd.DataFrame, dimension: str, measure: str, n: int = 5,
               aggfunc: str = "sum") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (top_n, bottom_n) groups by aggregated measure."""
    agg = group_aggregate(df, dimension, measure, aggfunc, sort="desc")
    return agg.head(n).reset_index(drop=True), agg.tail(n).reset_index(drop=True)
