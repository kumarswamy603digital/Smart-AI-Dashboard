# 5-Minute Demo Script

Goal: show a working analytics product, prove the numbers are real (pure Python),
and show the AI layer is honest (grounded + degradable). Run with the sample
dataset loaded (default) — no prep needed beyond `python app.py`.

**Before you start:** app open at http://127.0.0.1:8050, a small CSV ready to upload
(optional step 4), and decide beforehand whether `OPENAI_API_KEY` is set (both paths work).

---

### 0:00 – 0:45 — The headline numbers
1. Land on **Overview**. Point at the header: dataset name, rows, date range.
2. Walk the KPI cards left to right — *this is a synthetic sales dataset*, but the
   KPIs are live pandas computations: Total Sales, Profit, Units, Orders, AOV, Margin.
3. Hover the **monthly trend** — mention the visible Q4 seasonal bump (it really is
   in the generator).

> Line: “Every number on this page came from the same pandas pipeline you could run
> in a notebook — the dashboard just makes it interactive.”

### 0:45 – 1:45 — Filters that keep every section consistent
1. Open the **Filters** rail. Set `region = North`, click **Apply**.
2. Show that KPIs, both overview charts **and** the filter description update
   together — one `apply_filters()` code path feeds everything.
3. Add a date range (e.g. 2024 only) → numbers shrink again. **Clear** filters.

> Line: “There is a single source of truth for filtering, so no chart can silently
> disagree with a KPI card.”

### 1:45 – 3:00 — Analytics & anomaly detection
1. **Analytics** section: dimension `product_category`, measure `sales`, agg `sum`,
   chart `bar`, Top 5 → chart + computed results table appear.
2. Switch measure to `profit`, then flip the line chart to show the trend.
3. Point at the **correlation heatmap** — mention the built-in caveat: association
   ≠ causation.
4. **Outlier investigation**: column `sales`, method IQR → flagged rows listed with
   the bounds written in plain English.

> Line: “Detection is a transparent statistical baseline — Q1−1.5×IQR, z-scores —
> not a black box. The explanation is part of the output.”

### 3:00 – 4:00 — AI Studio, honesty included
1. **AI Studio**: click an example chip (it fills the textarea) and ask, e.g.
   *“Which categories drive sales and is the trend improving?”*
2. **With a key:** answer arrives as structured findings; show the context-size note
   — only a few thousand characters of *aggregates* were sent, never raw rows.
3. **Without a key (or kill the network):** the amber banner appears and the same
   question gets a deterministic local summary. Nothing crashes.
4. Ask a nonsense question (*“what is 2+2?”* or one needing row-level data) → the
   model must decline via `can_answer=false`.

> Line: “The model narrates; Python measures. If the statistic isn't computed
> locally, the AI is forbidden to say it — and if the API is down you still get
> real numbers.”

### 4:00 – 5:00 — Prove it: exports & tests
1. **Export Center**: download *filtered CSV* (apply one filter first) and the
   *Markdown report* — open the report, point at the clearly separated
   *Computed statistics* vs *AI narrative* sections.
2. **Status** section: masked API key, model name, limits — “the raw key never
   reaches the browser.”
3. Close in the terminal: `python -m pytest` → **92 passed in ~2s**, zero network
   calls — and mention Docker: `docker compose up`.

> Final line: “Same stack locally, in tests and in production: pure Python, one
> command to run, graceful without AI, bounded with it.”

---

## If something goes wrong (it shouldn't)
| Symptom | Recovery line |
|---|---|
| Upload rejected | “That's the guard rail working — 15 MB / 200k rows, shown in Status.” |
| AI slow/timed out | “Timeouts degrade to local mode by design — analytics are unaffected.” |
| Chart empty after filter | “The filter matched zero rows — that's the data talking, Clear fixes it.” |
