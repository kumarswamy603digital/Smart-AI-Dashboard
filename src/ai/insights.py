"""Data-grounded insight orchestration.

Python computes every statistic; the AI only narrates validated evidence.
The context sent to OpenAI is bounded (never a full dataset) and its size is
reported to the user.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import pandas as pd

from config.settings import settings
from src.ai.client import AIError, get_client
from src.ai.schemas import InsightResponse
from src.analytics.aggregations import group_aggregate
from src.analytics.anomalies import detect_outliers
from src.analytics.correlations import correlation_matrix
from src.analytics.kpis import compute_kpis, kpis_as_dict
from src.analytics.time_series import peaks_and_troughs, supports_time_series, trend
from src.data.loader import infer_column_types


def _jsonable(v):
    if isinstance(v, (np.float64, float)):
        return None if (math.isnan(v) or math.isinf(v)) else round(float(v), 4)
    if isinstance(v, (int, __import__("numpy").integer)):
        return int(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    return v if isinstance(v, str) else str(v)


import numpy as np  # noqa: E402  (used by _jsonable)


def build_bounded_context(df: pd.DataFrame, filters_desc: dict | None = None,
                          dims: list[str] | None = None,
                          measures: list[str] | None = None) -> dict:
    """Compute the *minimum* validated statistics for the AI to interpret."""
    filters_desc = filters_desc or {}
    kinds = infer_column_types(df)
    numeric = measures or [c for c, k in kinds.items() if k == "numeric"]
    cats = dims or [c for c, k in kinds.items() if k in ("categorical", "identifier") and c != "order_id"]
    date_col = next((c for c, k in kinds.items() if k == "date"), None)
    primary = next((c for c in ("sales", "revenue", "amount") if c in numeric), numeric[0] if numeric else None)

    ctx: dict = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "row_count": len(df),
        "column_count": df.shape[1],
        "applied_filters": {str(k): [str(x) for x in v] if isinstance(v, (list, tuple)) else str(v)
                            for k, v in filters_desc.items() if v not in (None, [], "")},
        "schema": {str(c): k for c, k in kinds.items()},
    }
    if date_col and date_col in df.columns:
        d = pd.to_datetime(df[date_col], errors="coerce")
        if d.notna().any():
            ctx["date_range"] = {"column": date_col, "min": str(d.min().date()), "max": str(d.max().date())}

    # KPIs (sales schema when recognizable, generic sums otherwise).
    try:
        ctx["kpis"] = {k: _jsonable(v) for k, v in kpis_as_dict(compute_kpis(df)).items()}
    except Exception:  # noqa: BLE001
        pass

    # Small aggregates — bounded rows, never raw records.
    for dim in cats[:3]:
        for meas in (primary, ) if primary else ():
            try:
                agg = group_aggregate(df, dim, meas, "sum", sort="desc", top_n=8)
                ctx[f"top8_{dim}_by_{meas}"] = [
                    {str(dim): _jsonable(r[dim]), meas: _jsonable(r[meas])} for r in agg.to_dict("records")
                ]
            except (KeyError, ValueError):
                continue

    if primary and date_col and supports_time_series(df, date_col, primary):
        try:
            tr = trend(df, date_col, primary, freq="month")
            ctx["monthly_trend"] = [
                {"period": _jsonable(r["period"]), primary: _jsonable(r[primary]),
                 "pct_change": _jsonable(None if pd.isna(r.get("pct_change")) else r.get("pct_change"))}
                for r in tr.tail(18).to_dict("records")
            ]
            pt = peaks_and_troughs(tr, primary)
            if pt:
                ctx["trend_shape"] = {
                    "peak_period": pt["peak"]["period"], "peak_value": _jsonable(pt["peak"]["value"]),
                    "trough_period": pt["trough"]["period"], "trough_value": _jsonable(pt["trough"]["value"]),
                    "first_to_last_pct_change": _jsonable(pt["first_to_last_pct_change"]),
                }
        except (KeyError, ValueError):
            pass

    if primary:
        try:
            out = detect_outliers(df, primary, method="iqr")
            ctx["outliers_iqr"] = {"column": primary, "count": out["count"],
                                   "bounds": [_jsonable(out.get("lower")), _jsonable(out.get("upper"))],
                                   "note": "Statistical outliers only — not proven business errors."}
        except ValueError:
            pass

    if len(numeric) >= 2:
        corr = correlation_matrix(df, numeric[:6])
        if not corr.empty:
            cols = list(corr.columns)
            ctx["correlations_pearson"] = {
                f"{a}~{b}": _jsonable(corr.loc[a, b])
                for a in cols for b in cols[:cols.index(a)]
            }
            ctx["correlations_note"] = correlation_matrix.__doc__.strip().splitlines()[0]
    return ctx


def context_char_count(ctx: dict) -> int:
    return len(json.dumps(ctx, default=str))


def _trim_context(ctx: dict, max_chars: int) -> dict:
    """Hard bound on transmitted size: drop the largest list values first."""
    total = context_char_count(ctx)
    if total <= max_chars:
        return ctx
    big_keys = sorted(
        [k for k, v in ctx.items() if isinstance(v, list) and len(v) > 4],
        key=lambda k: len(json.dumps(ctx[k], default=str)), reverse=True,
    )
    for k in big_keys:
        half = max(4, len(ctx[k]) // 2)
        ctx[k] = ctx[k][:half]
        if context_char_count(ctx) <= max_chars:
            return ctx
    if context_char_count(ctx) > max_chars:
        for k in list(big_keys):
            ctx.pop(k, None)
            if context_char_count(ctx) <= max_chars:
                return ctx
    return ctx


def local_summary(df: pd.DataFrame, filters_desc: dict | None = None) -> InsightResponse:
    """Deterministic, no-API narrative built from computed statistics."""
    ctx = build_bounded_context(df, filters_desc)
    kpis = ctx.get("kpis", {})
    bits = [f"{len(df):,} rows analysed locally."]
    if kpis.get("total_sales") is not None:
        bits.append(f"Total sales {kpis['total_sales']:,.0f}.")
    if kpis.get("margin") is not None:
        bits.append(f"Profit margin {kpis['margin']:.1f}%.")
    ts = ctx.get("trend_shape")
    if ts and ts.get("first_to_last_pct_change") is not None:
        direction = "increased" if ts["first_to_last_pct_change"] >= 0 else "decreased"
        bits.append(f"The primary monthly measure {direction} {abs(ts['first_to_last_pct_change']):.1f}% from first to last period (peak: {ts['peak_period']}).")
    findings = []
    for key, val in ctx.items():
        if key.startswith("top8_") and val:
            top = val[0]
            findings.append(f"Highest group on {key[5:]}: {next(iter(top))}={top[next(iter(top))]:,.0f}"
                            if isinstance(next(iter(top.values())), (int, float)) else
                            f"Top group on {key[5:]}: {list(top.values())[:2]}")
    out = ctx.get("outliers_iqr")
    if out:
        findings.append(f"{out['count']} statistical outlier(s) flagged on '{out['column']}' via IQR bounds.")
    return InsightResponse(
        can_answer=True,
        summary=" ".join(bits) or "Local profiling complete; no AI narrative generated.",
        findings=findings or ["Enable OPENAI_API_KEY for natural-language interpretation."],
        supporting_metrics=[{"name": k, "value": v} for k, v in list(ctx.get("kpis", {}).items())[:8]],
        caveats=["AI narrative is unavailable — these are raw computed statistics, not interpretations."],
        recommended_investigations=[],
    )


def answer_question(df: pd.DataFrame, question: str, filters_desc: dict | None = None,
                    history: list[dict] | None = None,
                    dims: list[str] | None = None, measures: list[str] | None = None) -> dict:
    """Full 8-step workflow: compute → bound context → ask → validate → return.

    Returns a dict with the validated insight, the computed evidence, how many
    characters were sent to the provider, and the AI availability flag.
    """
    ctx = _trim_context(build_bounded_context(df, filters_desc, dims, measures),
                        settings.openai_max_context_chars)
    evidence = {"kpis": ctx.get("kpis", {}), "context_preview": ctx}
    client = get_client()

    if not client.is_available():
        insight = local_summary(df, filters_desc)
        return {
            "ok": True, "ai_used": False,
            "reason": "OPENAI_API_KEY is not configured — showing locally computed statistics instead of an AI narrative.",
            "insight": insight.model_dump(), "evidence": evidence,
            "context_chars": context_char_count(ctx),
        }
    try:
        insight = client.ask(question, json.dumps(ctx, default=str), history)
    except AIError as exc:
        return {
            "ok": False, "ai_used": False, "reason": str(exc),
            "insight": local_summary(df, filters_desc).model_dump(), "evidence": evidence,
            "context_chars": context_char_count(ctx),
        }
    return {
        "ok": True, "ai_used": True, "reason": None,
        "insight": insight.model_dump(), "evidence": evidence,
        "context_chars": context_char_count(ctx),
        "model": settings.openai_model,
    }
