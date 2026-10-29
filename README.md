# AI Insights Dashboard

An end-to-end, production-shaped **data analytics dashboard** built with Python,
[pandas](https://pandas.pydata.org/) and [Plotly Dash](https://dash.plotly.com/),
with optional **OpenAI-powered natural-language insights** that are always grounded
in statistics computed locally. Upload a CSV (or use the bundled synthetic sample),
explore KPIs, charts, anomalies, correlations and export the results — all from a
single `python app.py`.

> **No Node.js, no npm, no frontend build step.** The entire stack is Python.

---

## Features

| Area | What you get |
|---|---|
| Overview | KPI cards (Total Sales, Profit, Units, Orders, AOV, Margin), monthly trend, category & region breakdowns, latest records, data-health tables |
| Data Explorer | CSV upload with validation & guards (size/row/column limits, safe filenames), automatic type inference, profiling summary, cleaning (drop NA / duplicates), full searchable data table |
| Filters | Date range, dimension-value and numeric-range filters applied through **one central code path** so KPIs, charts, tables and the AI context can never diverge |
| Analytics | Configurable dimension × measure × aggregation charts, Top-N, period comparisons, correlation heatmap (Pearson/Spearman), IQR & z-score anomaly detection with plain-English explanations |
| AI Studio | Natural-language Q&A grounded in a **bounded, locally computed context** — the model narrates, Python measures. Works fully **without** an API key (local statistics mode) |
| Exports | Filtered CSV, aggregated CSV and a Markdown report that clearly separates computed statistics from AI narrative |
| Status | Model & AI configuration panel (masked key), dataset & filter state, limits |

## Tech stack

- Python 3.11+, Plotly Dash 4 (UI), pandas 3 + NumPy (analytics), Plotly 7 (charts)
- OpenAI Python SDK (Responses API) + Pydantic (structured, validated AI output)
- python-dotenv (config), pytest (tests), Gunicorn/waitress (prod serving)
- No JavaScript framework — a ~40-line vanilla helper for navigation and the session token

## Quick start

```bash
# 1. (recommended) virtual environment
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/macOS: source venv/bin/activate)

# 2. install dependencies
pip install -r requirements.txt

# 3. (optional) enable AI narratives — the app works without this
copy .env.example .env         # then edit .env and set OPENAI_API_KEY

# 4. run
python app.py
```

Open **http://127.0.0.1:8050**. The synthetic sample dataset loads automatically
(`data/sample_sales.csv`, 1,500 rows, fixed seed — fully reproducible).

## Configuration

All settings come from environment variables (a `.env` file in the project root is
loaded automatically). See [.env.example](.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | *(empty)* | Enables AI narratives; empty = local statistics mode |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model used via the Responses API |
| `OPENAI_TIMEOUT` | `30` | Per-request timeout in seconds |
| `OPENAI_MAX_CONTEXT_CHARS` | `6000` | Hard cap on data sent to the model |
| `MAX_UPLOAD_MB` / `MAX_ROWS` / `MAX_COLUMNS` | `15` / `200000` / `200` | Upload guards |
| `DASH_HOST` / `DASH_PORT` / `DASH_DEBUG` | `127.0.0.1` / `8050` / `false` | Server binding |
| `SESSION_STORE_CAPACITY` | `64` | Max concurrent browser sessions held server-side |

## Running the tests

```bash
python -m pytest            # 92 tests, ~2s, no network access required
```

Unit tests cover data ingestion, the analytics engine and the AI layer (the OpenAI
SDK is stubbed — tests never spend money). Integration tests cover session
isolation, the filter pipeline, exports and app wiring. Details: [docs/testing.md](docs/testing.md).

## Project structure

```
app.py                 Dash app + Flask server + clientside helpers
config/settings.py     Frozen Settings dataclass (single source of env config)
data/                  Synthetic sample dataset (clearly labelled, fixed seed)
src/data/              CSV parsing, validation, profiling, cleaning, type inference
src/analytics/         KPIs, aggregations, time series, anomalies, correlations, comparisons
src/visualization/     Plotly chart builders, tables, theme
src/ai/                OpenAI Responses-API client, prompts, Pydantic schemas,
                       bounded-context insights, Markdown report builder
src/services/          Session store (LRU, thread-safe), filter pipeline, exports
src/components/        Dash layout pieces (header, sidebar, KPI cards, panels…)
src/callbacks/         Dash callbacks (upload, filters, charts, AI, export)
assets/                styles.css + logo (served automatically by Dash)
tests/                 unit/ + integration/ (pytest)
docs/                  architecture, AI design, data dictionary, testing, deployment, demo
```

## How the AI stays honest

1. Python computes every statistic (KPIs, Top-N aggregates, trend, outliers, correlations).
2. The result is **trimmed to a bounded context** (≤ `OPENAI_MAX_CONTEXT_CHARS`) — raw rows
   and record identifiers are never sent.
3. The system prompt forbids fabrication and treats the data block as untrusted content
   (prompt-injection defence).
4. The model must answer with a strict JSON schema; Pydantic validates it, with a
   documented lenient fallback and a clear error if parsing still fails.
5. Without an API key (or on any API failure) the answer degrades gracefully to a
   deterministic local summary — the dashboard never breaks because of the AI.

Full design: [docs/ai_design.md](docs/ai_design.md).

## Deployment

- **Docker**: `docker compose up` (or `docker build -t ai-dashboard .` + `docker run -p 8050:8050 ai-dashboard`)
- **Linux**: `gunicorn -w 2 -b 0.0.0.0:8050 app:server`
- **Windows**: `waitress-serve --host=0.0.0.0 --port=8050 app:server`

Details and reverse-proxy notes: [docs/deployment.md](docs/deployment.md).

## Known limitations

- Uploads are CSV-only (Excel/JSON would be a small extension of `src/data/loader.py`).
- The AI answers from aggregate statistics, not raw records — questions requiring
  row-level lookups are intentionally refused (`can_answer: false`).
- Session state is in-memory by design (bounded LRU); restarting the server resets sessions.
- One uploaded dataset per session at a time.

## License / attribution

Sample data is synthetic, generated with a fixed random seed — see
[data/README.md](data/README.md). No real business data is included anywhere.
