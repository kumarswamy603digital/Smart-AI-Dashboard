"""Unit tests for the analytics engine: KPIs, aggregations, time series,
anomalies and correlations. Pure computation — no Dash, no network."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics import aggregations, anomalies, correlations, kpis, time_series


class TestKPIs:
    def test_sales_schema_exact_values(self, tiny_sales_df):
        vals = kpis.kpis_as_dict(kpis.compute_kpis(tiny_sales_df))
        assert vals["total_sales"] == pytest.approx(600.0)
        assert vals["total_profit"] == pytest.approx(50.0)
        assert vals["total_quantity"] == pytest.approx(9.0)
        assert vals["orders"] == 3.0
        assert vals["aov"] == pytest.approx(200.0)          # 600 / 3
        assert vals["margin"] == pytest.approx(50 / 600 * 100)

    def test_orders_uses_distinct_ids(self):
        df = pd.DataFrame({"order_id": ["A", "A", "B"], "sales": [1.0, 2.0, 3.0]})
        vals = kpis.kpis_as_dict(kpis.compute_kpis(df))
        assert vals["orders"] == 2.0  # nunique, not row count

    def test_zero_sales_margin_is_none_not_crash(self, tiny_sales_df):
        df = tiny_sales_df.assign(sales=0.0)
        vals = kpis.kpis_as_dict(kpis.compute_kpis(df))
        assert vals["total_sales"] == 0.0
        assert vals["margin"] is None

    def test_missing_measures_only_orders_kpi(self, no_schema_df):
        vals = kpis.kpis_as_dict(kpis.compute_kpis(no_schema_df))
        assert set(vals) == {"orders"}
        assert vals["orders"] == 4.0

    def test_formulas_documented(self, tiny_sales_df):
        for k in kpis.compute_kpis(tiny_sales_df):
            assert k.formula and k.label

    def test_generic_measure_kpis(self, no_schema_df):
        vals = kpis.kpis_as_dict(kpis.generic_measure_kpis(no_schema_df, ["temperature", "station"]))
        assert vals["rows"] == 4.0
        assert vals["sum_temperature"] == pytest.approx(30.1 + 25.4 + 31.0 + 24.9)
        assert "sum_station" not in vals  # non-numeric ignored


class TestAggregations:
    def test_group_sum_sorted_desc(self, tiny_sales_df):
        out = aggregations.group_aggregate(tiny_sales_df, "region", "sales", "sum")
        assert out.iloc[0]["region"] == "North"
        assert out.iloc[0]["sales"] == pytest.approx(400.0)

    def test_all_agg_funcs_run(self, sample_df):
        for func in aggregations.AGG_FUNCS:
            out = aggregations.group_aggregate(sample_df, "region", "sales", func)
            assert not out.empty

    def test_top_n_truncates(self, tiny_sales_df):
        out = aggregations.group_aggregate(tiny_sales_df, "product_category", "sales", "sum", top_n=1)
        assert len(out) == 1

    def test_unknown_aggregation_rejected(self, tiny_sales_df):
        with pytest.raises(ValueError, match="Unsupported aggregation"):
            aggregations.group_aggregate(tiny_sales_df, "region", "sales", "stddev")

    def test_missing_column_keyerror(self, tiny_sales_df):
        with pytest.raises(KeyError):
            aggregations.group_aggregate(tiny_sales_df, "nope", "sales")
        with pytest.raises(KeyError):
            aggregations.group_aggregate(tiny_sales_df, "region", "nope")

    def test_date_aggregate_monthly(self, tiny_sales_df):
        out = aggregations.date_aggregate(tiny_sales_df, "order_date", "sales", freq="month")
        assert list(out.columns) == ["period", "sales"]
        assert out["sales"].sum() == pytest.approx(600.0)

    def test_date_aggregate_bad_freq(self, tiny_sales_df):
        with pytest.raises(ValueError, match="frequency"):
            aggregations.date_aggregate(tiny_sales_df, "order_date", "sales", freq="fortnight")

    def test_date_aggregate_no_valid_dates(self):
        df = pd.DataFrame({"d": pd.to_datetime(["2024-01-01", "2024-02-01"]), "v": [1.0, 2.0]})
        df["d"] = df["d"].astype(str)
        with pytest.raises((ValueError, KeyError)):
            aggregations.date_aggregate(df.assign(d=["bad", "worse"]), "d", "v")

    def test_top_bottom(self, sample_df):
        top, bottom = aggregations.top_bottom(sample_df, "region", "sales", n=2)
        assert len(top) <= 2 and len(bottom) <= 2
        assert top["sales"].iloc[0] >= bottom["sales"].iloc[-1]


class TestTimeSeries:
    def test_supports(self, tiny_sales_df, no_schema_df):
        assert time_series.supports_time_series(tiny_sales_df, "order_date", "sales")
        assert not time_series.supports_time_series(tiny_sales_df, "region", "sales")
        assert not time_series.supports_time_series(tiny_sales_df, "order_date", "region")
        assert not time_series.supports_time_series(no_schema_df, "station", "temperature")

    def test_pct_change_safe(self):
        assert time_series.pct_change(150, 100) == pytest.approx(50.0)
        assert time_series.pct_change(50, 100) == pytest.approx(-50.0)
        assert time_series.pct_change(100, 0) is None      # zero denominator
        assert time_series.pct_change(None, 100) is None
        assert time_series.pct_change(float("nan"), 100) is None

    def test_trend_columns_and_values(self, tiny_sales_df):
        tr = time_series.trend(tiny_sales_df, "order_date", "sales")
        assert list(tr.columns) == ["period", "sales", "pct_change"]
        assert tr["sales"].tolist() == [100.0, 200.0, 300.0]
        assert tr["pct_change"].iloc[1] == pytest.approx(100.0)
        assert pd.isna(tr["pct_change"].iloc[0])           # first period has no previous

    def test_trend_zero_previous_yields_na_not_inf(self):
        df = pd.DataFrame(
            {
                "d": pd.to_datetime(["2024-01-15", "2024-02-15", "2024-03-15"]),
                "v": [0.0, 10.0, 20.0],
            }
        )
        tr = time_series.trend(df, "d", "v")
        assert pd.isna(tr["pct_change"].iloc[1])  # NA, never a bogus finite %

    def test_peaks_and_troughs(self, tiny_sales_df):
        pt = time_series.peaks_and_troughs(time_series.trend(tiny_sales_df, "order_date", "sales"), "sales")
        assert pt["peak"]["value"] == pytest.approx(300.0)
        assert pt["trough"]["value"] == pytest.approx(100.0)
        assert pt["first_to_last_pct_change"] == pytest.approx(200.0)

    def test_compare_periods(self, tiny_sales_df):
        res = time_series.compare_periods(
            tiny_sales_df, "order_date", "sales", "2024-01-01", "2024-01-31", "2024-02-01", "2024-02-29"
        )
        assert res["period_a"]["value"] == pytest.approx(100.0)
        assert res["period_b"]["value"] == pytest.approx(200.0)
        assert res["pct_change_b_vs_a"] == pytest.approx(100.0)


class TestAnomalies:
    def test_iqr_flags_extreme(self):
        df = pd.DataFrame({"v": [10, 11, 10, 12, 9, 11, 10, 500]})
        res = anomalies.iqr_outliers(df, "v")
        assert res["count"] == 1
        assert 7 in res["indices"]

    def test_iqr_constant_column(self):
        df = pd.DataFrame({"v": [5.0] * 10})
        res = anomalies.iqr_outliers(df, "v")
        assert res["count"] == 0 and res["lower"] is None
        assert "Interquartile range" in res["explanation"]

    def test_zscore_constant_column(self):
        df = pd.DataFrame({"v": [5.0] * 10})
        res = anomalies.zscore_outliers(df, "v")
        assert res["count"] == 0
        assert "Standard deviation is zero" in res["explanation"]

    def test_zscore_threshold(self):
        vals = [0.0] * 50 + [1000.0]
        res = anomalies.zscore_outliers(pd.DataFrame({"v": vals}), "v", threshold=3.0)
        assert res["count"] >= 1 and 50 in res["indices"]

    def test_non_numeric_rejected(self):
        df = pd.DataFrame({"s": ["a", "b", "c"]})
        with pytest.raises(ValueError, match="not numeric"):
            anomalies.iqr_outliers(df, "s")
        with pytest.raises(ValueError, match="not numeric"):
            anomalies.zscore_outliers(df, "s")

    def test_detect_dispatch(self, tiny_sales_df):
        assert anomalies.detect_outliers(tiny_sales_df, "sales", "iqr")["method"] == "IQR"
        assert anomalies.detect_outliers(tiny_sales_df, "sales", "zscore")["method"] == "z-score"

    def test_results_are_explanatory_not_accusatory(self, sample_df):
        res = anomalies.detect_outliers(sample_df, "sales", "iqr")
        assert "flagged" in res["explanation"]


class TestCorrelations:
    def test_perfect_positive(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [2.0, 4.0, 6.0]})
        res = correlations.pairwise_correlation(df, "a", "b")
        assert res["value"] == pytest.approx(1.0)
        assert "causation" in res["caveat"]

    def test_matrix_symmetric_diagonal_one(self, tiny_sales_df):
        m = correlations.correlation_matrix(tiny_sales_df, ["sales", "quantity", "profit"])
        assert list(m.columns) == ["sales", "quantity", "profit"]
        assert m.loc["sales", "sales"] == pytest.approx(1.0)
        assert m.loc["sales", "quantity"] == pytest.approx(m.loc["quantity", "sales"])

    def test_constant_column_dropped(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "c": [7.0, 7.0, 7.0]})
        assert correlations.correlation_matrix(df).empty

    def test_bad_method(self, tiny_sales_df):
        with pytest.raises(ValueError):
            correlations.correlation_matrix(tiny_sales_df, method="kendall-nope")

    def test_pairwise_non_numeric_rejected(self, tiny_sales_df):
        with pytest.raises(ValueError, match="not numeric"):
            correlations.pairwise_correlation(tiny_sales_df, "region", "sales")

    def test_spearman_detects_monotonic(self):
        # Perfectly monotonic with ties -> rank correlation is exactly 1.
        df = pd.DataFrame({"a": [1.0, 2.0, 2.0, 3.0], "b": [10.0, 20.0, 20.0, 30.0]})
        m = correlations.correlation_matrix(df, method="spearman")
        assert m.loc["a", "b"] == pytest.approx(1.0)

    def test_spearman_on_sample(self, sample_df):
        m = correlations.correlation_matrix(sample_df, ["sales", "quantity"], method="spearman")
        assert -1.0 <= m.loc["sales", "quantity"] <= 1.0
