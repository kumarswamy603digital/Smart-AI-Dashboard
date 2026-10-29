"""Shared pytest fixtures. No test here requires a real OpenAI key."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.sample_data import generate_sample_sales  # noqa: E402


@pytest.fixture(scope="session")
def sample_df() -> pd.DataFrame:
    """Small deterministic slice of the synthetic demo data."""
    return generate_sample_sales(seed=42, n_rows=200)


@pytest.fixture()
def tiny_sales_df() -> pd.DataFrame:
    """Hand-built frame with exact, verifiable KPI values."""
    return pd.DataFrame(
        {
            "order_id": ["A1", "A2", "A3"],
            "order_date": pd.to_datetime(["2024-01-05", "2024-02-10", "2024-03-20"]),
            "region": ["North", "South", "North"],
            "product_category": ["Widgets", "Widgets", "Gadgets"],
            "sales": [100.0, 200.0, 300.0],
            "quantity": [2, 3, 4],
            "unit_price": [50.0, 66.67, 75.0],
            "discount": [0.0, 0.1, 0.0],
            "profit": [10.0, -20.0, 60.0],
        }
    )


@pytest.fixture()
def no_schema_df() -> pd.DataFrame:
    """A generic uploaded-style dataset without sales semantics."""
    return pd.DataFrame(
        {
            "station": ["S1", "S2", "S1", "S2"],
            "temperature": [30.1, 25.4, 31.0, 24.9],
            "humidity": [60, 55, 62, 54],
        }
    )
