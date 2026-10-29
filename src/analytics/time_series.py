"""Time-series trends: period aggregation, % change, peaks/troughs.

Only runs when a real date column and numeric measure exist; callers must
check `supports_time_series` first.
"""
from __future__ import annotations

import pandas as pd

from src.analytics.aggregations import date_aggregate


def supports_time_series(df: pd.DataFrame, date_col: str | None, measure: str | None) -> bool:
    if not date_col or not measure or date_col not in df.columns or measure not in df.columns:
        return False
    if not pd.api.types.is_numeric_dtype(df[measure]):
        return False
    return pd.to_datetime(df[date_col], errors="coerce").notna().any()


def pct_change(current: float, previous: float) -> float | None:
    """Safe percentage change: None when the previous value is zero/NaN."""
    if previous is None or current is None or pd.isna(previous) or pd.isna(current):
        return None
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * 100.0


def trend(df: pd.DataFrame, date_col: str, measure: str, freq: str = "month",
          aggfunc: str = "sum") -> pd.DataFrame:
    """Series with [period, measure, pct_change]."""
    series = date_aggregate(df, date_col, measure, freq=freq, aggfunc=aggfunc)
    series["pct_change"] = series[measure].pct_change() * 100.0
    # pct_change on a zero previous value yields inf — normalize it.
    series["pct_change"] = series["pct_change"].replace([float("inf"), float("-inf")], pd.NA)
    return series


def peaks_and_troughs(series: pd.DataFrame, measure: str) -> dict:
    """Simple global peak/trough plus first vs last movement."""
    s = pd.to_numeric(series[measure], errors="coerce").dropna()
    if s.empty:
        return {}
    peak_i, trough_i = int(s.idxmax()), int(s.idxmin())
    first, last = float(s.iloc[0]), float(s.iloc[-1])
    out = {
        "peak": {"period": str(series.loc[peak_i, "period"]), "value": float(s.max())},
        "trough": {"period": str(series.loc[trough_i, "period"]), "value": float(s.min())},
        "first_to_last_pct_change": pct_change(last, first),
    }
    return out


def compare_periods(df: pd.DataFrame, date_col: str, measure: str,
                    start_a: str, end_a: str, start_b: str, end_b: str,
                    aggfunc: str = "sum") -> dict:
    """Compare aggregated measure between two date ranges (A vs B)."""
    d = pd.to_datetime(df[date_col], errors="coerce")
    m = pd.to_numeric(df[measure], errors="coerce")

    def window(s1: str, e1: str) -> float:
        mask = (d >= pd.Timestamp(s1)) & (d <= pd.Timestamp(e1))
        vals = m[mask].dropna()
        return float(getattr(vals, aggfunc)()) if len(vals) else float("nan")

    a, b = window(start_a, end_a), window(start_b, end_b)
    return {
        "period_a": {"range": f"{start_a} → {end_a}", "value": a},
        "period_b": {"range": f"{start_b} → {end_b}", "value": b},
        "difference": a - b,
        "pct_change_b_vs_a": pct_change(b, a),
    }
