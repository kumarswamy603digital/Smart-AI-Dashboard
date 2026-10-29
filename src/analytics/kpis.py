"""KPI calculations. Formulas are explicit and never sum identifier columns.

Default sales schema:
  total_sales       = SUM(sales)
  total_profit      = SUM(profit)
  total_quantity    = SUM(quantity)
  order_count       = COUNT(order_id) (row count fallback)
  avg_order_value   = total_sales / order_count
  profit_margin_pct = total_profit / total_sales * 100   (None when sales == 0)
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SALES_COLUMNS = {
    "sales_measure": "sales",
    "profit_measure": "profit",
    "quantity_measure": "quantity",
    "order_id": "order_id",
}


@dataclass
class KPI:
    key: str
    label: str
    value: float | None
    fmt: str  # "currency" | "number" | "percent" | "count"
    formula: str


def _safe_div(num: float, den: float) -> float | None:
    return None if den in (0, 0.0) or pd.isna(den) else num / den


def compute_kpis(df: pd.DataFrame, columns: dict[str, str] | None = None) -> list[KPI]:
    """Compute KPIs for the sales schema, or a mapped schema for uploaded data."""
    cols = {**SALES_COLUMNS, **(columns or {})}
    kpis: list[KPI] = []

    def num(col: str) -> pd.Series | None:
        if col and col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            return df[col]
        return None

    sales = num(cols["sales_measure"])
    profit = num(cols["profit_measure"])
    qty = num(cols["quantity_measure"])

    order_col = cols["order_id"]
    if order_col and order_col in df.columns:
        orders = int(df[order_col].nunique()) or len(df)
    else:
        orders = len(df)

    total_sales = float(sales.sum()) if sales is not None else None
    total_profit = float(profit.sum()) if profit is not None else None
    total_qty = float(qty.sum()) if qty is not None else None

    if total_sales is not None:
        kpis.append(KPI("total_sales", "Total Sales", total_sales, "currency", "SUM(sales)"))
    if total_profit is not None:
        kpis.append(KPI("total_profit", "Total Profit", total_profit, "currency", "SUM(profit)"))
    if total_qty is not None:
        kpis.append(KPI("total_quantity", "Units Sold", total_qty, "number", "SUM(quantity)"))
    kpis.append(KPI("orders", "Orders", float(orders), "count", "COUNT(order_id)"))
    if total_sales is not None:
        aov = _safe_div(total_sales, orders)
        kpis.append(KPI("aov", "Avg Order Value", aov, "currency", "SUM(sales) / COUNT(orders)"))
    if total_sales is not None and total_profit is not None:
        margin = _safe_div(total_profit, total_sales)
        margin = None if margin is None else margin * 100
        kpis.append(KPI("margin", "Profit Margin", margin, "percent", "SUM(profit) / SUM(sales) × 100"))
    return kpis


def kpis_as_dict(kpis: list[KPI]) -> dict[str, float | None]:
    return {k.key: k.value for k in kpis}


def generic_measure_kpis(df: pd.DataFrame, measures: list[str]) -> list[KPI]:
    """For arbitrary uploads: SUM/MEAN per selected numeric measure."""
    kpis: list[KPI] = []
    kpis.append(KPI("rows", "Rows", float(len(df)), "count", "COUNT(rows)"))
    for m in measures:
        s = num = df.get(m)
        if num is None or not pd.api.types.is_numeric_dtype(s):
            continue
        kpis.append(KPI(f"sum_{m}", f"Total {m}", float(s.sum()), "number", f"SUM({m})"))
        mean = s.mean()
        kpis.append(KPI(f"mean_{m}", f"Average {m}", None if pd.isna(mean) else float(mean), "number", f"MEAN({m})"))
    return kpis
