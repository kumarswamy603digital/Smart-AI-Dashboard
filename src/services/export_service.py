"""Export helpers: filtered CSV, aggregated CSV and Markdown reports.

Everything is produced in-memory and returned as a dcc-compatible download
payload — no server-side files are required for the user-facing flow.
"""
from __future__ import annotations

import io

import pandas as pd

from src.ai.reports import build_markdown_report
from src.ai.schemas import InsightResponse


def df_to_csv_text(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return "\ufeff" + buf.getvalue()  # BOM keeps Excel UTF-8 happy


def csv_download(df: pd.DataFrame, filename: str) -> dict:
    return dict(content=df_to_csv_text(df), filename=filename)


def report_download(df: pd.DataFrame, dataset_name: str, filters_desc: dict | None,
                    insight: InsightResponse | None, ai_used: bool) -> dict:
    md = build_markdown_report(df, dataset_name, filters_desc, insight, ai_used)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in dataset_name)
    return dict(content=md, filename=f"report_{safe[:40]}.md")


def report_to_disk(df: pd.DataFrame, dataset_name: str, reports_dir) -> str:
    """Also persist a copy under reports/ for the internship portfolio."""
    from pathlib import Path

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    md = build_markdown_report(df, dataset_name)
    out = reports_dir / "latest_report.md"
    out.write_text(md, encoding="utf-8")
    return str(out)
