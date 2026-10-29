"""Unit tests for CSV ingestion, decoding and validation."""
from __future__ import annotations

import base64

import pandas as pd
import pytest

from config.settings import settings
from src.data import loader, validation


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode()


class TestParseCsv:
    def test_valid_csv(self):
        raw = b"name,qty\nwidget,3\ngadget,7\n"
        df = loader.parse_csv_bytes(raw)
        assert len(df) == 2
        assert list(df.columns) == ["name", "qty"]

    def test_empty_file_rejected(self):
        with pytest.raises(ValueError, match="no data"):
            loader.parse_csv_bytes(b"   ")

    def test_header_only_rejected(self):
        with pytest.raises(ValueError):
            loader.parse_csv_bytes(b"a,b,c\n")

    def test_malformed_csv_rejected(self):
        with pytest.raises(ValueError, match="parse"):
            loader.parse_csv_bytes(b'a,b\n"unclosed,x\nextra,columns,here,now\n')

    def test_missing_values_kept_not_crashing(self):
        df = loader.parse_csv_bytes(b"a,b\n1,\n,4\n")
        assert df["b"].isna().sum() == 1
        assert df["a"].isna().sum() == 1

    def test_duplicate_columns_renamed_by_pandas(self):
        # pandas mangles duplicates to id.1/id.2; our dedupe covers any leftovers.
        df = loader.parse_csv_bytes(b"id,id,v\n1,2,3\n")
        assert len(set(df.columns)) == 3
        assert list(df.columns)[0] == "id"

    def test_dedupe_columns_helper(self):
        assert loader.dedupe_columns(["id", "id", "id", "v"]) == ["id", "id_1", "id_2", "v"]

    def test_latin1_fallback(self):
        raw = "city,pop\nZürich,100\n".encode("latin-1")
        df = loader.parse_csv_bytes(raw)
        assert len(df) == 1

    def test_utf8_bom(self):
        df = loader.parse_csv_bytes("a,b\n1,2\n".encode("utf-8-sig"))
        assert list(df.columns) == ["a", "b"]


class TestTypeInference:
    def test_kinds_detected(self):
        df = pd.DataFrame(
            {
                "customer_id": ["C1", "C2", "C3", "C4"],
                "order_date": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
                "amount": [1.0, 2.0, 3.0, 4.5],
                "region": ["N", "S", "N", "S"],
                "free_text": ["alpha text here", "beta", "gamma", "delta"],
            }
        )
        kinds = loader.infer_column_types(df)
        assert kinds["customer_id"] == "identifier"
        assert kinds["order_date"] == "date"
        assert kinds["amount"] == "numeric"
        assert kinds["region"] == "categorical"

    def test_coerce_types_converts_dates_only(self):
        df = pd.DataFrame({"d": ["2024-01-01", "2024-06-15"], "s": ["x", "y"]})
        out = loader.coerce_types(df)
        assert pd.api.types.is_datetime64_any_dtype(out["d"])
        assert not pd.api.types.is_numeric_dtype(out["s"])

    def test_source_not_mutated(self):
        df = pd.DataFrame({"d": ["2024-01-01", "2024-06-15"]})
        loader.coerce_types(df)
        assert not pd.api.types.is_datetime64_any_dtype(df["d"])


class TestUploadGuards:
    def test_decode_upload_data_url(self):
        contents = "data:text/csv;base64," + b64("a,b\n1,2\n")
        assert b"a,b" in loader.decode_upload(contents)

    def test_decode_empty_raises(self):
        with pytest.raises(ValueError):
            loader.decode_upload("")

    def test_safe_filename_blocks_paths(self):
        assert "/" not in loader.safe_filename("../../etc/passwd")
        assert ".." not in loader.safe_filename("../../etc/passwd")
        assert loader.safe_filename("") == "uploaded.csv"

    def test_wrong_extension_rejected(self):
        res = validation.validate_upload("malware.exe", "data:," + b64("x"))
        assert not res.ok
        assert any(".csv" in e for e in res.errors)

    def test_oversize_rejected(self):
        big = "x" * (settings.max_upload_bytes + 10)
        res = validation.validate_upload("ok.csv", b64(big))
        assert not res.ok
        assert any("MB" in e for e in res.errors)

    def test_row_limit_rejected(self, monkeypatch):
        # settings is a frozen dataclass — patch the module-level reference instead.
        class _Cfg:
            max_rows = 5
            max_columns = 10_000

        monkeypatch.setattr(validation, "settings", _Cfg())
        df = pd.DataFrame({"a": range(6)})
        res = validation.validate_frame(df)
        assert not res.ok

    def test_row_limit_not_hit_when_ok(self, sample_df):
        assert validation.validate_frame(sample_df).ok
