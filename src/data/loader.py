"""Safe CSV ingestion: decoding, parsing and light type inference.

Uploaded content is treated strictly as data — never executed, never used as
a filesystem path, never trusted to be well-formed.
"""
from __future__ import annotations

import base64
import io
import re

import pandas as pd

# Columns that identify records rather than measure them.
_ID_RE = re.compile(r"(^|_)(id|code|sku|zip|postal|phone)$|_id$|^id$", re.IGNORECASE)
_DATE_HINT_RE = re.compile(r"date|time|day|month|year|created|updated", re.IGNORECASE)


def decode_upload(contents: str, filename: str = "") -> bytes:
    """Decode a Dash Upload contents payload (data-url base64) to raw bytes."""
    if not contents:
        raise ValueError("The uploaded file is empty.")
    try:
        _, _, b64 = contents.partition(",") if contents.startswith("data:") else ("", "", contents)
        return base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not decode the uploaded file ({type(exc).__name__}).") from exc


def safe_filename(name: str, fallback: str = "uploaded.csv") -> str:
    """Strip paths/odd characters so a user-supplied name can never be a path."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", (name or "").split("/")[-1].split("\\")[-1])
    return cleaned[-80:] if cleaned else fallback


def dedupe_columns(cols) -> list[str]:
    out, seen = [], {}
    for c in cols:
        c = str(c)
        if c in seen:
            seen[c] += 1
            out.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            out.append(c)
    return out


def parse_csv_bytes(raw: bytes) -> pd.DataFrame:
    """Parse raw CSV bytes with common encoding fallbacks."""
    if not raw.strip():
        raise ValueError("The file contains no data.")
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            df = pd.read_csv(io.StringIO(text))
            df.columns = dedupe_columns(df.columns)
            if df.empty:
                raise ValueError("The file parsed successfully but contains zero rows.")
            return df
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            last_err = exc
    raise ValueError(f"Could not parse the file as CSV: {last_err}")


def infer_column_types(df: pd.DataFrame) -> dict[str, str]:
    """Return {column: identifier|numeric|date|categorical|text} without mutating df."""
    kinds: dict[str, str] = {}
    n = max(len(df), 1)
    for col in df.columns:
        s = df[col]
        is_str = pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s)
        if _ID_RE.search(str(col)) and is_str:
            kinds[col] = "identifier"
        elif pd.api.types.is_numeric_dtype(s):
            kinds[col] = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            kinds[col] = "date"
        elif is_str:
            parsed = pd.to_datetime(s, errors="coerce", format="mixed")
            if parsed.notna().mean() > 0.8 and s.notna().mean() > 0:
                kinds[col] = "date"
            elif s.nunique(dropna=True) <= 50 and (
                s.nunique(dropna=True) / n < 0.5 or s.nunique(dropna=True) <= 3
            ):
                kinds[col] = "categorical"
            else:
                kinds[col] = "text"
        else:
            kinds[col] = "text"
    return kinds


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with date-like string columns converted to datetime."""
    out = df.copy()
    kinds = infer_column_types(out)
    for col, kind in kinds.items():
        if kind == "date" and not pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col], errors="coerce", format="mixed")
    return out


def load_csv(path) -> pd.DataFrame:
    df = parse_csv_bytes(io.FileIO(str(path)).read())
    df.attrs["source"] = str(path)
    return coerce_types(df)
