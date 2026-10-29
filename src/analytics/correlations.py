"""Correlation analysis (Pearson / Spearman) with safe handling."""
from __future__ import annotations

import pandas as pd

CAVEAT = "Correlation measures association only; it does not establish causation."


def correlation_matrix(df: pd.DataFrame, columns: list[str] | None = None,
                       method: str = "pearson") -> pd.DataFrame:
    """Correlation matrix over numeric columns. Constant columns are dropped
    (their correlation is undefined). NaNs are pairwise-excluded by pandas."""
    if method not in ("pearson", "spearman"):
        raise ValueError("method must be 'pearson' or 'spearman'.")
    numeric = df.select_dtypes(include="number")
    if columns:
        numeric = numeric[[c for c in columns if c in numeric.columns]]
    # Drop constant columns to avoid meaningless NaN correlations.
    numeric = numeric.loc[:, numeric.nunique(dropna=True) > 1]
    if numeric.shape[1] < 2:
        return pd.DataFrame()
    return numeric.corr(method=method)


def pairwise_correlation(df: pd.DataFrame, col_a: str, col_b: str,
                        method: str = "pearson") -> dict:
    for c in (col_a, col_b):
        if c not in df.columns or not pd.api.types.is_numeric_dtype(df[c]):
            raise ValueError(f"Column '{c}' is missing or not numeric.")
    a, b = df[col_a], df[col_b]
    if a.nunique(dropna=True) <= 1 or b.nunique(dropna=True) <= 1:
        return {"value": None, "n": int((a.notna() & b.notna()).sum()),
                "note": "One column is constant — correlation is undefined.", "caveat": CAVEAT}
    value = a.corr(b, method=method)
    return {
        "value": None if pd.isna(value) else float(value),
        "n": int((a.notna() & b.notna()).sum()),
        "method": method,
        "caveat": CAVEAT,
    }
