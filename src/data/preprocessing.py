"""Explicit, opt-in cleaning operations. Nothing is silently modified."""
from __future__ import annotations

import pandas as pd


def drop_missing(df: pd.DataFrame, columns: list[str] | None = None) -> tuple[pd.DataFrame, int]:
    """Drop rows with NaN in the given columns (all columns when None)."""
    before = len(df)
    out = df.dropna(subset=columns) if columns else df.dropna()
    return out.reset_index(drop=True), before - len(out)


def drop_duplicate_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    out = df.drop_duplicates()
    return out.reset_index(drop=True), before - len(out)


def apply_cleaning(df: pd.DataFrame, drop_na: bool = False, drop_dups: bool = False,
                   na_columns: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Return (cleaned_copy, report). Source frame is never mutated."""
    report: dict[str, int] = {"rows_before": len(df), "rows_removed_missing": 0, "rows_removed_duplicates": 0}
    out = df.copy()
    if drop_na:
        out, removed = drop_missing(out, na_columns)
        report["rows_removed_missing"] = removed
    if drop_dups:
        out, removed = drop_duplicate_rows(out)
        report["rows_removed_duplicates"] = removed
    report["rows_after"] = len(out)
    return out, report
