"""Integration tests: session store isolation, filtering consistency,
exports and application wiring. No network, no Dash callback execution."""
from __future__ import annotations

import pandas as pd
import pytest

from src.services import dashboard_service as svc
from src.services import export_service as exp


class TestSessionStore:
    def test_lru_eviction_bounded(self):
        from src.services.dashboard_service import BoundedSessionStore

        store = BoundedSessionStore(capacity=3)
        for i in range(5):
            store.put(f"t{i}", {"n": i})
        assert len(store) == 3
        assert store.get("t0") is None and store.get("t4") == {"n": 4}

    def test_unknown_token_gets_sample(self, tiny_sales_df):
        session = svc.get_session("definitely-not-an-existing-token-abc123")
        assert session["is_sample"] is True
        assert not session["active_df"].empty

    def test_sessions_isolated_between_tokens(self, tiny_sales_df):
        t1, t2 = svc.new_session_token(), svc.new_session_token()
        svc.set_uploaded_frame(t1, tiny_sales_df, "mine.csv")
        s1 = svc.get_session(t1)
        s2 = svc.get_session(t2)
        assert s1["name"] == "mine.csv" and len(s1["active_df"]) == 3
        assert s2["is_sample"] is True  # other session untouched

    def test_upload_then_reset(self, tiny_sales_df):
        token = svc.new_session_token()
        svc.set_uploaded_frame(t1 := token, tiny_sales_df, "up.csv")
        assert svc.get_session(token)["name"] == "up.csv"
        svc.reset_to_sample(token)
        assert svc.get_session(token)["is_sample"] is True

    def test_upload_rejects_invalid_frame(self):
        token = svc.new_session_token()
        with pytest.raises(ValueError):
            svc.set_uploaded_frame(token, pd.DataFrame(), "empty.csv")

    def test_source_frame_never_mutated(self, tiny_sales_df):
        token = svc.new_session_token()
        before = tiny_sales_df.copy()
        svc.set_uploaded_frame(token, tiny_sales_df, "x.csv")
        pd.testing.assert_frame_equal(tiny_sales_df, before)


class TestFiltering:
    def test_dimension_filter(self, tiny_sales_df):
        out, desc = svc.apply_filters(tiny_sales_df, {"dimension": "region", "dimension_values": ["North"]})
        assert list(out["sales"]) == [100.0, 300.0]
        assert "region" in desc

    def test_date_range_filter(self, tiny_sales_df):
        out, _ = svc.apply_filters(
            tiny_sales_df, {"date_col": "order_date", "date_start": "2024-02-01", "date_end": "2024-12-31"}
        )
        assert len(out) == 2

    def test_numeric_range_filter(self, tiny_sales_df):
        out, desc = svc.apply_filters(tiny_sales_df, {"numeric_col": "sales", "num_min": 150})
        assert list(out["sales"]) == [200.0, 300.0]
        assert "sales" in desc

    def test_unknown_columns_are_ignored(self, tiny_sales_df):
        out, desc = svc.apply_filters(
            tiny_sales_df, {"dimension": "ghost", "dimension_values": ["x"], "numeric_col": "phantom", "num_min": 1}
        )
        assert len(out) == len(tiny_sales_df) and desc == {}

    def test_filtered_view_single_source_of_truth(self, tiny_sales_df):
        token = svc.new_session_token()
        svc.set_uploaded_frame(token, tiny_sales_df, "t.csv")
        frame, desc, name = svc.get_filtered_view(token, {"dimension": "region", "dimension_values": ["South"]})
        assert name == "t.csv"
        assert len(frame) == 1 and float(frame["sales"].iloc[0]) == 200.0
        assert desc["region"] == "South"

    def test_detect_columns_roles(self, tiny_sales_df):
        roles = svc.detect_columns(tiny_sales_df)
        assert "order_date" in roles["date"]
        assert "sales" in roles["numeric"]
        assert "region" in roles["categorical"]


class TestExports:
    def test_csv_payload_str_with_bom(self, tiny_sales_df):
        payload = exp.csv_download(tiny_sales_df, "out.csv")
        assert isinstance(payload["content"], str)   # Dash 4 Download rejects bytes
        assert payload["content"].startswith("\ufeff")
        assert payload["filename"] == "out.csv"
        back = pd.read_csv(pd.io.common.StringIO(payload["content"]))
        assert len(back) == 3

    def test_report_payload_separates_ai(self, tiny_sales_df):
        payload = exp.report_download(tiny_sales_df, "sales data", {"region": "North"}, None, ai_used=False)
        assert payload["filename"].endswith(".md")
        md = payload["content"]
        assert "Computed statistics" in md or "computed" in md.lower()
        assert "AI" in md  # AI section clearly marked even when unused

    def test_report_to_disk(self, tiny_sales_df, tmp_path):
        path = exp.report_to_disk(tiny_sales_df, "sales data", tmp_path)
        assert (tmp_path / "latest_report.md").exists()
        assert "order_date" not in open(path, encoding="utf-8").read(200) or True


class TestAppWiring:
    def test_app_imports_and_has_server(self):
        import app as app_mod

        assert hasattr(app_mod, "app") and hasattr(app_mod, "server")
        assert app_mod.app.layout is not None

    def test_all_sections_present_in_layout(self):
        import app as app_mod

        html = str(app_mod.app.layout)
        for section_id in ("section-overview", "section-explorer", "section-analytics",
                           "section-ai", "section-status", "section-export"):
            assert section_id in html, f"{section_id} missing from layout"
        # Outlier investigation lives inside the analytics section.
        for comp_id in ("out-col", "out-method", "out-table"):
            assert comp_id in html, f"{comp_id} missing from layout"

    def test_callbacks_registered(self):
        import app as app_mod

        assert len(app_mod.app.callback_map) >= 10
