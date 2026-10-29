# Sample data — SYNTHETIC, generated

`sample_sales.csv` is **synthetic demo data**. It does not describe any real
company, customers, products or market. It exists so the dashboard has something
meaningful to analyse on first run and so tests are reproducible.

## How it is produced

- Generator: [`src/data/sample_data.py`](../src/data/sample_data.py)
- RNG: `numpy.random.default_rng(42)` — **fixed seed**, byte-identical output on every machine
- 1,500 orders spanning 2024-01-01 → ~2025-06-25
- Realistic structure: seasonal Q4 uplift, mild growth trend, category price bands,
  discount flags, ~6 deliberately inflated rows so anomaly detection has real work

Regenerate manually (rarely needed):

```bash
python -m src.data.sample_data
```

## Schema

| Column | Type | Notes |
|---|---|---|
| `order_id` | string `ORD-#####` | Synthetic identifier (never sent to the AI) |
| `order_date` | date `YYYY-MM-DD` | 18-month window |
| `region` | categorical | North / South / East / West |
| `product_category` | categorical | Electronics, Furniture, Office Supplies, Apparel, Grocery |
| `product` | categorical | Within-category product name |
| `sales` | float | unit_price × quantity × seasonal × growth × (1 − discount) |
| `quantity` | int 1–11 | |
| `unit_price` | float | Category-specific band |
| `discount` | float 0–0.30 | 35 % of rows carry a discount |
| `profit` | float | sales × margin − discount cost; can be negative |
| `customer_segment` | categorical | Consumer / Corporate / Home Office |

Uploading a CSV with *any* columns works — the dashboard infers roles
(date / numeric / categorical / identifier) automatically. The sales-specific
KPIs simply light up when `sales`, `profit`, `quantity` and `order_id` are present.
