"""Generate the synthetic demo sales dataset with a fixed random seed.

The data is clearly synthetic and is regenerated deterministically so every
installation sees identical numbers. It must never be presented as real
company or market data.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_ROWS = 1500
START = datetime(2024, 1, 1)
SPAN_DAYS = 540  # ~18 months of orders

REGIONS = ["North", "South", "East", "West"]
CATEGORIES = {
    "Electronics": (120.0, 1800.0),
    "Furniture": (80.0, 950.0),
    "Office Supplies": (8.0, 240.0),
    "Apparel": (15.0, 320.0),
    "Grocery": (3.0, 60.0),
}
PRODUCTS = {
    "Electronics": ["Laptop", "Smartphone", "Headphones", "Monitor", "Tablet"],
    "Furniture": ["Desk Chair", "Standing Desk", "Bookshelf", "Conference Table"],
    "Office Supplies": ["Paper Reams", "Pens Set", "Desk Organizer", "Whiteboard"],
    "Apparel": ["Running Shoes", "Winter Jacket", "T-Shirt Pack", "Backpack"],
    "Grocery": ["Coffee Beans", "Olive Oil", "Snack Box", "Tea Assortment"],
}
SEGMENTS = ["Consumer", "Corporate", "Home Office"]


def generate_sample_sales(seed: int = SEED, n_rows: int = N_ROWS) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cat_names = list(CATEGORIES)
    cat_weights = [0.30, 0.18, 0.25, 0.15, 0.12]
    categories = rng.choice(cat_names, size=n_rows, p=cat_weights)
    regions = rng.choice(REGIONS, size=n_rows, p=[0.28, 0.22, 0.26, 0.24])
    segments = rng.choice(SEGMENTS, size=n_rows, p=[0.5, 0.3, 0.2])

    dates = [START + timedelta(days=int(d)) for d in rng.integers(0, SPAN_DAYS, n_rows)]
    products = [str(rng.choice(PRODUCTS[c])) for c in categories]

    low = np.array([CATEGORIES[c][0] for c in categories])
    high = np.array([CATEGORIES[c][1] for c in categories])
    unit_price = np.round(rng.uniform(low, high), 2)
    quantity = rng.integers(1, 12, n_rows)

    # Seasonal uplift: Q4 months sell stronger; mild growth over time.
    month = np.array([d.month for d in dates])
    idx = np.array([(d - START).days for d in dates])
    seasonal = 1.0 + 0.35 * np.isin(month, [11, 12]) + 0.15 * np.isin(month, [10, 1, 2])
    growth = 1.0 + 0.25 * idx / SPAN_DAYS
    discount = np.where(rng.random(n_rows) < 0.35, np.round(rng.uniform(0.02, 0.30, n_rows), 3), 0.0)

    sales = np.round(unit_price * quantity * seasonal * growth * (1.0 - discount), 2)
    margin_pct = rng.normal(0.28, 0.12, n_rows)
    profit = np.round(sales * margin_pct - unit_price * quantity * discount, 2)

    df = pd.DataFrame(
        {
            "order_id": [f"ORD-{100000 + i}" for i in range(n_rows)],
            "order_date": [d.strftime("%Y-%m-%d") for d in dates],
            "region": regions,
            "product_category": categories,
            "product": products,
            "sales": sales,
            "quantity": quantity,
            "unit_price": unit_price,
            "discount": discount,
            "profit": profit,
            "customer_segment": segments,
        }
    )
    # A handful of intentional anomalies so outlier detection has real work.
    glitch_rows = rng.choice(n_rows, size=6, replace=False)
    df.loc[glitch_rows, "sales"] = np.round(df.loc[glitch_rows, "sales"] * rng.uniform(9, 14, 6), 2)
    return df.sort_values("order_date").reset_index(drop=True)


def ensure_sample_csv(path: Path, regenerate: bool = False) -> Path:
    """Write the deterministic sample CSV if it is missing."""
    path = Path(path)
    if regenerate or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        generate_sample_sales().to_csv(path, index=False)
    return path


if __name__ == "__main__":  # manual regeneration: python -m src.data.sample_data
    out = ensure_sample_csv(Path(__file__).resolve().parent.parent.parent / "data" / "sample_sales.csv", True)
    print(f"Wrote {out} ({sum(1 for _ in open(out)) - 1} rows)")
