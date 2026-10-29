# Data Dictionary

Two perspectives matter: the **bundled sample dataset** (fixed schema) and the
**contract for uploaded CSVs** (schema-agnostic).

## 1. `data/sample_sales.csv` (synthetic — see [data/README.md](../data/README.md))

| Column | Kind (inferred) | Unit / range | Description |
|---|---|---|---|
| `order_id` | identifier | `ORD-100000…` | One unique id per row; drives the Orders KPI (`nunique`) |
| `order_date` | date | 2024-01-01 → 2025-06 | Order date; enables time-series features |
| `region` | categorical | North/South/East/West | Sales region |
| `product_category` | categorical | 5 categories | Product line |
| `product` | categorical | ~20 products | Concrete item within category |
| `sales` | numeric | currency | Revenue of the line: price × qty × seasonal × growth × (1−discount) |
| `quantity` | numeric (int) | 1–11 | Units in the order line |
| `unit_price` | numeric | currency | Pre-discount price |
| `discount` | numeric | 0–0.30 | Fraction off; 0 on ~65 % of rows |
| `profit` | numeric | currency, can be < 0 | Sales × margin − discount cost |
| `customer_segment` | categorical | Consumer/Corporate/Home Office | Buyer type |

### KPI formulas (documented in the UI too)

| KPI | Formula | Edge behaviour |
|---|---|---|
| Total Sales | `SUM(sales)` | — |
| Total Profit | `SUM(profit)` | — |
| Units Sold | `SUM(quantity)` | — |
| Orders | `COUNT(DISTINCT order_id)` (row-count fallback) | — |
| Avg Order Value | `Total Sales ÷ Orders` | `None` when Orders = 0 |
| Profit Margin | `Total Profit ÷ Total Sales × 100` | `None` when Sales = 0 (never ÷0) |

## 2. Type-inference contract for uploads

`src/data/loader.py::infer_column_types` assigns each column exactly one role:

| Role | Rule (first match wins) | Consequence in the UI |
|---|---|---|
| `identifier` | name matches `*_id`, `id`, `code`, `sku`, `zip`, `postal`, `phone` and values are strings | excluded from aggregates & AI context |
| `numeric` | pandas numeric dtype | measures, correlations, KPIs, numeric filters |
| `date` | datetime dtype, **or** >80 % of string values parse as dates | time-series, date filters, trend charts |
| `categorical` | strings with ≤ 50 unique values **and** (unique ÷ rows < 0.5 **or** ≤ 3 unique) | dimensions, filters, group charts |
| `text` | everything else | shown in preview only; never a dimension/measure |

No-upload-required: a CSV with *any* headers works. Sales-specific KPIs only appear
when columns named `sales` / `profit` / `quantity` / `order_id` exist; otherwise
generic `SUM`/`MEAN` KPIs per numeric measure are computed
(`kpis.generic_measure_kpis`).

## 3. Validation limits (enforced, configurable)

| Limit | Env var | Default | Behaviour on breach |
|---|---|---|---|
| File size | `MAX_UPLOAD_MB` | 15 MB | Rejected before parsing, friendly message |
| Rows | `MAX_ROWS` | 200,000 | Rejected after parsing, before entering the session |
| Columns | `MAX_COLUMNS` | 200 | Rejected |
| Extensions | — | `.csv` only | Rejected |

Duplicate column names are auto-mangled by pandas (`id`, `id.1`, …) and then
deduplicated by `dedupe_columns`, so uploads never crash on header collisions.

## 4. Missing-value semantics

- Missing values are **kept**, not silently dropped: profiling reports per-column
  completeness; charts and KPIs use pandas' NaN-skipping aggregations.
- Numeric range filters always keep NaN rows (they are unknown, not out-of-range).
- Explicit removal happens only via the *Data cleaning* controls (drop-NA /
  drop-duplicates), which operate on the pristine `source_df` and report what changed.
