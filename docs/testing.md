# Testing

```bash
python -m pytest          # from the project root — 92 tests, ~2 seconds
python -m pytest -v       # per-test output
python -m pytest tests/unit/test_analytics.py   # one file
```

## Principles

1. **No network, no money.** The OpenAI SDK is never initialised against the real
   API — tests inject stub clients (`FakeSDK`) or monkeypatch `get_client`.
2. **Pure functions first.** The analytics engine is tested with hand-built frames
   whose expected values are written down by hand (`tiny_sales_df`: sales 100/200/300
   ⇒ Total Sales 600, AOV 200, Margin 50/600×100).
3. **Determinism.** The sample data generator is seeded (42); fixtures slice it
   reproducibly.
4. **Edges over happy paths.** Zero denominators, constant columns, empty uploads,
   duplicate headers, non-UTF-8 files, path-traversal filenames.

## Layout

| File | Covers |
|---|---|
| `tests/conftest.py` | Shared fixtures: `sample_df` (seeded 200-row slice), `tiny_sales_df` (exact KPI values), `no_schema_df` (generic upload without sales semantics) |
| `tests/unit/test_loader.py` | CSV parse failures, encodings (UTF-8-BOM, latin-1), duplicate columns, type inference, `safe_filename` path-traversal guard, size/row limits |
| `tests/unit/test_analytics.py` | KPI formulas & None-on-zero division, aggregations (all 6 funcs, bad agg ⇒ error), date bucketing, safe `pct_change`, peaks/troughs, period comparison, IQR & z-score (incl. constant-column degenerate cases), Pearson/Spearman, correlation caveats |
| `tests/unit/test_ai.py` | Local mode without key, masked key status, stubbed Responses API success, lenient JSON fallback (fenced/unparseable), friendly mapping of Authentication/RateLimit/Timeout/Connection errors, bounded context (`_trim_context` cap), **raw row identifiers never appear in AI context**, AI failure degrades to local evidence |
| `tests/integration/test_services.py` | LRU eviction, per-token session isolation, upload→reset lifecycle, source frame immutability, the central `apply_filters` (date/dimension/numeric + unknown-column guards), export payload shapes (str + BOM for Dash 4 `dcc.Download`), Markdown report separates AI vs computed, app import + layout sections + registered callbacks |

## What is deliberately *not* tested

- Dash callback *execution* (requires a browser or `dash.testing` + WebDriver —
  heavy for this scope). Callback plumbing is covered indirectly: layout ids,
  store chain and pure services are tested; the UI was verified interactively
  (screenshots under `reports/`).
- Plotly figure pixel output — builders are exercised through the refresh
  integration path rather than snapshot-tested.

## Adding tests

- Analytics/AI functions take plain DataFrames → add cases to the relevant unit file
  using `tiny_sales_df` when you need checkable numbers.
- `settings` is a **frozen dataclass**: to vary limits in tests, monkeypatch the
  *module reference* (`monkeypatch.setattr(validation, "settings", _Cfg())`), not its fields.
- Never call the real OpenAI API from a test; stub via `make_client(...)` in
  `test_ai.py`.
