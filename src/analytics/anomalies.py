"""Transparent baseline anomaly detection (IQR and z-score).

These flag *statistical outliers* only. They never assert that a point is an
error, fraud or a business problem — that interpretation is left to the user.
"""
from __future__ import annotations

import pandas as pd


def iqr_outliers(df: pd.DataFrame, column: str, multiplier: float = 1.5) -> dict:
    """Rows outside [Q1 - k*IQR, Q3 + k*IQR] for a numeric column."""
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' is not numeric; IQR detection needs a numeric column.")
    s = pd.to_numeric(df[column], errors="coerce")
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr == 0:
        return {"method": "IQR", "multiplier": multiplier, "lower": None, "upper": None,
                "indices": [], "count": 0,
                "explanation": "Interquartile range is zero — every value sits inside one narrow band, so IQR flags nothing."}
    lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
    mask = (s < lower) | (s > upper)
    return {
        "method": "IQR",
        "multiplier": multiplier,
        "lower": float(lower),
        "upper": float(upper),
        "indices": [int(i) for i in s.index[mask.fillna(False)]],
        "count": int(mask.fillna(False).sum()),
        "explanation": (
            f"A row is flagged when {column} falls below {lower:,.2f} or above {upper:,.2f} "
            f"(Q1−{multiplier}×IQR, Q3+{multiplier}×IQR)."
        ),
    }


def zscore_outliers(df: pd.DataFrame, column: str, threshold: float = 3.0) -> dict:
    """Rows with |z| > threshold using mean/std of the column."""
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' is not numeric; z-score detection needs a numeric column.")
    s = pd.to_numeric(df[column], errors="coerce")
    mean, std = s.mean(), s.std()
    if pd.isna(std) or std == 0:
        return {"method": "z-score", "threshold": threshold, "indices": [], "count": 0,
                "explanation": "Standard deviation is zero — all values are identical, so no z-score outliers exist."}
    z = (s - mean) / std
    mask = z.abs() > threshold
    return {
        "method": "z-score",
        "threshold": threshold,
        "mean": float(mean),
        "std": float(std),
        "indices": [int(i) for i in s.index[mask.fillna(False)]],
        "count": int(mask.fillna(False).sum()),
        "explanation": (
            f"A row is flagged when its value deviates more than {threshold} standard deviations "
            f"from the mean ({mean:,.2f}, σ={std:,.2f})."
        ),
    }


def detect_outliers(df: pd.DataFrame, column: str, method: str = "iqr",
                    param: float | None = None) -> dict:
    if method == "zscore":
        return zscore_outliers(df, column, threshold=param if param else 3.0)
    return iqr_outliers(df, column, multiplier=param if param else 1.5)
