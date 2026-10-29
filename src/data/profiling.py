"""Dataset profiling: shape, missing values, duplicates, per-column summaries."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.data.loader import infer_column_types


@dataclass
class Profile:
    n_rows: int
    n_cols: int
    column_kinds: dict[str, str] = field(default_factory=dict)
    missing_counts: dict[str, int] = field(default_factory=dict)
    missing_pct: dict[str, float] = field(default_factory=dict)
    distinct_counts: dict[str, int] = field(default_factory=dict)
    duplicate_rows: int = 0
    numeric_summary: pd.DataFrame | None = None
    date_ranges: dict[str, tuple[str, str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    total_missing_cells: int = 0


def profile_dataset(df: pd.DataFrame) -> Profile:
    kinds = infer_column_types(df)
    missing = df.isna().sum().to_dict()
    n = max(len(df), 1)
    missing_pct = {k: round(100.0 * v / n, 2) for k, v in missing.items()}
    distinct = {c: int(df[c].nunique(dropna=True)) for c in df.columns}

    numeric_cols = [c for c, k in kinds.items() if k == "numeric"]
    numeric_summary = df[numeric_cols].describe().T if numeric_cols else None

    date_ranges: dict[str, tuple[str, str]] = {}
    for c, k in kinds.items():
        if k == "date":
            s = pd.to_datetime(df[c], errors="coerce")
            if s.notna().any():
                date_ranges[c] = (str(s.min().date()), str(s.max().date()))

    warnings: list[str] = []
    for c in df.columns:
        if missing_pct.get(str(c), 0) >= 40:
            warnings.append(f"'{c}' is {missing_pct[str(c)]}% missing.")
    high_card = [c for c, d in distinct.items() if kinds.get(c) == "categorical" and d > 30]
    if high_card:
        warnings.append(f"High-cardinality category columns: {', '.join(high_card[:5])}.")
    dup = int(df.duplicated().sum())
    if dup:
        warnings.append(f"{dup} duplicate row(s) detected (kept, not removed).")

    return Profile(
        n_rows=len(df),
        n_cols=df.shape[1],
        column_kinds=kinds,
        missing_counts={str(k): int(v) for k, v in missing.items()},
        missing_pct=missing_pct,
        distinct_counts=distinct,
        duplicate_rows=dup,
        numeric_summary=numeric_summary,
        date_ranges=date_ranges,
        warnings=warnings,
        total_missing_cells=int(df.isna().sum().sum()),
    )


def schema_table(profile: Profile) -> pd.DataFrame:
    """Compact schema view for the UI: type, missing, distinct per column."""
    return pd.DataFrame(
        {
            "column": list(profile.column_kinds),
            "inferred_type": list(profile.column_kinds.values()),
            "missing": [profile.missing_counts.get(c, 0) for c in profile.column_kinds],
            "missing_%": [profile.missing_pct.get(c, 0.0) for c in profile.column_kinds],
            "distinct": [profile.distinct_counts.get(c, 0) for c in profile.column_kinds],
        }
    )
