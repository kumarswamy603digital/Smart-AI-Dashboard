"""Group vs group and category comparisons on the active dataset."""
from __future__ import annotations

import pandas as pd

from src.analytics.aggregations import group_aggregate
from src.analytics.time_series import pct_change


def compare_groups(df: pd.DataFrame, dimension: str, measure: str,
                   groups: list[str], aggfunc: str = "sum") -> pd.DataFrame:
    """Aggregate `measure` per chosen group value. Returns [group, value]."""
    agg = group_aggregate(df, dimension, measure, aggfunc=aggfunc, sort="desc")
    sel = agg[agg[dimension].astype(str).isin([str(g) for g in groups])] if groups else agg
    out = sel.rename(columns={dimension: "group", measure: "value"}).reset_index(drop=True)
    return out


def rank_changes(df: pd.DataFrame, date_col: str, dimension: str, measure: str,
                 freq: str = "month", aggfunc: str = "sum") -> pd.DataFrame:
    """Per-category trajectory across periods with first→last % change.

    Returns [dimension, first_value, last_value, pct_change] — categories with
    a negative change are "declining" on the chosen measure.
    """
    tmp = df[[date_col, dimension, measure]].copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
    tmp = tmp.dropna(subset=[date_col, dimension])
    if tmp.empty:
        return pd.DataFrame(columns=[dimension, "first_value", "last_value", "pct_change"])
    tmp["_per"] = tmp[date_col].dt.to_period(freq == "month" and "M" or freq[:1].upper())
    rows = []
    for name, g in tmp.groupby(dimension, dropna=True):
        per = g.groupby("_per", observed=True)[measure].agg(aggfunc).sort_index()
        if len(per) < 2:
            continue
        first, last = float(per.iloc[0]), float(per.iloc[-1])
        rows.append({dimension: name, "first_value": first, "last_value": last,
                     "pct_change": pct_change(last, first),
                     "periods": f"{per.index.min()} → {per.index.max()}"})
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("pct_change", ascending=True, na_position="last").reset_index(drop=True)
    return out
