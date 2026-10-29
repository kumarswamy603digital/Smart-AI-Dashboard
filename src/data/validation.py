"""Upload guards: file type, size and shape validation with clear messages."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.settings import settings

ALLOWED_EXTENSIONS = {".csv"}
ALLOWED_MIME = {"text/csv", "application/vnd.ms-excel", "application/octet-stream", ""}


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def validate_upload(filename: str | None, contents: str | None) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if not filename:
        return ValidationResult(False, ["No file was selected."], warnings)

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Unsupported file type '{ext or 'unknown'}'. Please upload a .csv file.")

    # Dash reports size via contents length; approximate decoded byte size.
    if contents:
        b64 = contents.split(",", 1)[-1] if contents.startswith("data:") else contents
        approx_bytes = int(len(b64) * 3 / 4)
        if approx_bytes > settings.max_upload_bytes:
            errors.append(
                f"File is approximately {approx_bytes / 1_048_576:.1f} MB, over the "
                f"{settings.max_upload_mb_display} MB limit."
            )
        elif approx_bytes == 0:
            errors.append("The uploaded file is empty.")
    else:
        errors.append("The uploaded file is empty.")
    return ValidationResult(not errors, errors, warnings)


def validate_frame(df: pd.DataFrame) -> ValidationResult:
    """Structural checks after parsing (row/column budget, all-empty columns)."""
    errors: list[str] = []
    warnings: list[str] = []
    if df is None or len(df) == 0:
        errors.append("The file contains no data rows.")
        return ValidationResult(False, errors, warnings)
    if len(df) > settings.max_rows:
        errors.append(f"Dataset has {len(df):,} rows, over the {settings.max_rows:,} row limit.")
    if len(df.columns) > settings.max_columns:
        errors.append(f"Dataset has {len(df.columns)} columns, over the {settings.max_columns} column limit.")
    empty_cols = [c for c in df.columns if df[c].notna().sum() == 0]
    if empty_cols:
        warnings.append(f"Columns with no values at all: {', '.join(map(str, empty_cols[:8]))}.")
    if df.shape[1] == 1:
        warnings.append("Single-column dataset — most analytics will be unavailable.")
    return ValidationResult(not errors, errors, warnings)
