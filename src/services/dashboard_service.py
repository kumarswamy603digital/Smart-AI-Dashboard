"""Session-scoped dashboard state and the single source of truth for filtering.

Every dashboard component (KPIs, charts, tables, AI context) reads the same
`get_active_frame()` output, so numbers can never diverge between sections.

Uploaded frames live in a bounded server-side store keyed by a random session
token held in the browser (dcc.Store). Keys are opaque UUID4s — one user can
never address another user's data — and the store evicts least-recently-used
sessions when full. Nothing sensitive (no API keys, no raw uploads) is placed
in browser storage; the browser only holds the session token.
"""
from __future__ import annotations

import threading
import uuid
from collections import OrderedDict

import pandas as pd

from config.settings import settings
from src.data.loader import coerce_types, load_csv
from src.data.sample_data import ensure_sample_csv
from src.data.validation import validate_frame

SAMPLE_NAME = "sample_sales.csv (synthetic demo)"


class BoundedSessionStore:
    """LRU-bounded, thread-safe server-side store of per-session frames."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._lock = threading.Lock()
        self._data: OrderedDict[str, dict] = OrderedDict()

    def get(self, token: str) -> dict | None:
        with self._lock:
            if token in self._data:
                self._data.move_to_end(token)
                return self._data[token]
        return None

    def put(self, token: str, session: dict) -> None:
        with self._lock:
            self._data[token] = session
            self._data.move_to_end(token)
            while len(self._data) > self.capacity:
                self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)


_store = BoundedSessionStore(settings.session_store_capacity)


def new_session_token() -> str:
    return uuid.uuid4().hex


def _sample_session() -> dict:
    path = ensure_sample_csv(settings.sample_csv)
    df = load_csv(path)
    return {"source_df": df, "active_df": df, "name": SAMPLE_NAME,
            "is_sample": True, "cleaning_report": None}


def get_session(token: str | None) -> dict:
    """Return the session, creating it with the sample dataset if unknown."""
    if not token:
        token = new_session_token()
    session = _store.get(token)
    if session is None:
        session = _sample_session()
        _store.put(token, session)
    return session


def set_uploaded_frame(token: str, df: pd.DataFrame, name: str) -> dict:
    result = validate_frame(df)
    if not result.ok:
        raise ValueError("; ".join(result.errors))
    active = coerce_types(df.copy())
    session = {
        "source_df": df.copy(),  # pristine original, never mutated
        "active_df": active,
        "name": name,
        "is_sample": False,
        "cleaning_report": None,
    }
    _store.put(token or new_session_token(), session)
    return session


def reset_to_sample(token: str) -> dict:
    session = _sample_session()
    _store.put(token, session)
    return session


def apply_cleaning(token: str, drop_na: bool, drop_dups: bool,
                   na_columns: list[str] | None) -> dict:
    from src.data.preprocessing import apply_cleaning as _clean

    session = get_session(token)
    cleaned, report = _clean(session["source_df"], drop_na, drop_dups, na_columns)
    session = dict(session)
    session["active_df"] = coerce_types(cleaned)
    session["cleaning_report"] = report
    _store.put(token, session)
    return session


def apply_filters(df: pd.DataFrame, filters: dict) -> tuple[pd.DataFrame, dict]:
    """Centralised filter logic — the ONLY place dashboard filters are applied.

    filters: {date_col, date_start, date_end, dimension, dimension_values,
              numeric_col, num_min, num_max}
    Returns (filtered_copy, human_readable_description).
    """
    out = df
    desc: dict = {}
    date_col = filters.get("date_col")
    if date_col and date_col in out.columns:
        start, end = filters.get("date_start"), filters.get("date_end")
        d = pd.to_datetime(out[date_col], errors="coerce")
        mask = d.notna()
        if start:
            mask &= d >= pd.Timestamp(start)
        if end:
            mask &= d <= pd.Timestamp(end)
        if start or end:
            out = out[mask]
            desc[f"date ({date_col})"] = f"{start or '…'} → {end or '…'}"

    dim, vals = filters.get("dimension"), filters.get("dimension_values")
    if dim and dim in out.columns and vals:
        out = out[out[dim].astype(str).isin([str(v) for v in vals])]
        desc[dim] = ", ".join(str(v) for v in vals[:8]) + ("…" if len(vals) > 8 else "")

    ncol, nmin, nmax = filters.get("numeric_col"), filters.get("num_min"), filters.get("num_max")
    if ncol and ncol in out.columns and pd.api.types.is_numeric_dtype(out[ncol]):
        n = pd.to_numeric(out[ncol], errors="coerce")
        keep = n.isna()
        if nmin is not None:
            keep |= n >= float(nmin)
        if nmax is not None:
            keep |= n <= float(nmax)
        if nmin is not None or nmax is not None:
            out = out[keep]
            desc[ncol] = f"[{nmin if nmin is not None else '−∞'}, {nmax if nmax is not None else '∞'}]"
    return out.reset_index(drop=True), desc


def detect_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    """Column-role detection shared by every callback: dates, numbers, cats."""
    from src.data.loader import infer_column_types

    kinds = infer_column_types(df)
    return {
        "date": [c for c, k in kinds.items() if k == "date"],
        "numeric": [c for c, k in kinds.items() if k == "numeric"],
        "categorical": [c for c, k in kinds.items() if k in ("categorical",)],
        "identifier": [c for c, k in kinds.items() if k == "identifier"],
        "text": [c for c, k in kinds.items() if k == "text"],
    }


def get_filtered_view(token: str | None, filters: dict | None) -> tuple[pd.DataFrame, dict, str]:
    """The single entry point UI callbacks use: (frame, filter_desc, name)."""
    session = get_session(token)
    filtered, desc = apply_filters(session["active_df"], filters or {})
    return filtered, desc, session["name"]
