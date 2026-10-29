# Architecture

## 1. System overview

The application is a single Python process: a Dash (Flask) web server that owns all
state. There is no separate frontend build and no external database.

```mermaid
flowchart LR
    B[Browser\nDash React components\n+ ~40 lines vanilla JS] -->|HTTP / JSON POST /_dash-update-component| S[Flask + Dash server\napp.py]
    S --> C[src/callbacks\n5 modules]
    C --> SV[src/services\ndashboard_service, export_service]
    SV --> AN[src/analytics\npure pandas functions]
    SV --> DT[src/data\nloader, validation, profiling]
    C --> VZ[src/visualization\nchart & table builders]
    C --> AI[src/ai\nclient, insights, reports]
    AI --> O[(OpenAI Responses API\noptional)]
```

Design consequences:

- **Pure-Python analytics.** Every number shown or exported is produced by
  `src/analytics/*` — plain pandas functions with no UI or network dependencies.
  They are unit-testable in isolation and are the *only* source of numbers.
- **The AI interprets, never measures.** `src/ai` receives a bounded, serialized
  summary of computed statistics (see [ai_design.md](ai_design.md)); it cannot
  invent a number that pandas did not compute.
- **Graceful degradation.** No `OPENAI_API_KEY` → every AI call short-circuits to a
  deterministic local summary. API failures are caught, mapped to friendly messages
  and also fall back locally. The dashboard's analytics never depend on the AI path.

## 2. Layers & responsibilities

| Layer | Modules | Responsibility |
|---|---|---|
| Entry point | `app.py` | Dash app, Flask `server`, clientside JS (session token, navigation), callback registration |
| Config | `config/settings.py` | Frozen `Settings` dataclass reading env vars once; the only module that touches `os.getenv` |
| Components | `src/components/*` | Declarative layout pieces; every interactive element has a stable `id` |
| Callbacks | `src/callbacks/*` | Wire inputs→outputs; contain **orchestration only**, no math |
| Services | `src/services/*` | Session store, the single filter pipeline, export payloads |
| Analytics | `src/analytics/*` | KPIs, aggregations, trends, anomalies, correlations, comparisons — pure functions |
| Data | `src/data/*` | CSV decoding/parsing, validation limits, profiling, cleaning, type inference, sample generator |
| Visualization | `src/visualization/*` | Plotly figure builders, `dash_table` builders, theme |
| AI | `src/ai/*` | OpenAI client wrapper, prompts, Pydantic schemas, context building, report narrative |

## 3. State & data flow

### Session model

Uploaded data lives **server-side** in a bounded, thread-safe LRU store. The browser
holds only an opaque UUID4 token.

```mermaid
sequenceDiagram
    participant Br as Browser
    participant JS as clientside JS
    participant ST as dcc.Store session-token
    participant SV as dashboard_service
    participant SM as BoundedSessionStore (LRU, cap 64)
    Br->>JS: page load
    JS->>JS: sessionStorage 'ai-dashboard-sid' exists? reuse : generate 's-'+uuid
    JS->>ST: set token (storage_type="session")
    ST->>SV: any callback reads Token.data
    SV->>SM: get(token) — miss? seed with synthetic sample
    SM-->>Br: session dict {source_df, active_df, name, is_sample}
```

- Tokens are random UUID4s — one browser can never address another's session.
- LRU eviction bounds memory (`SESSION_STORE_CAPACITY`, default 64 sessions).
- `source_df` (pristine upload) is kept separately from `active_df` (post-cleaning),
  so cleaning can always be re-run from the original.

### Single source of truth for filters

```mermaid
flowchart LR
    U[Filter panel\nApply button] -->|filters-store dict| R[refresh callback C1a]
    T[dataset-ver bump\nupload / reset / clean] --> R
    R --> F["get_filtered_view(token, filters)\n= apply_filters(session.active_df, filters)"]
    F --> K[KPI cards] & CH[charts] & TB[tables] & AIx[AI context] & EX[exports]
```

KPIs, charts, tables, the AI context and exports all consume the *same*
`apply_filters()` output — numbers shown in different sections can never disagree.

### Callback store chain

| Store | Written by | Read by |
|---|---|---|
| `session-token` | clientside JS (once, idempotent) | every server callback |
| `dataset-ver` (int) | upload / reset / clean callbacks | refresh + analytics callbacks (change detection) |
| `filters-store` (dict) | filter Apply/Clear callbacks | refresh, AI, exports |
| `ai-history` (dict keyed by dataset signature) | AI answer callback | AI (follow-up context) |
| `ai-last-result` | AI answer callback | status pill, report export |

Pattern-matching inputs (`{"pattern": ...}`) drive the example-question chips in
AI Studio; Dash 4 delivers the triggering id as a JSON string, which the callback
parses defensively.

## 4. Upload & validation pipeline

```mermaid
flowchart LR
    UP[dcc.Upload] --> G{extension .csv?\nsize <= MAX_UPLOAD_MB?} -->|no| E1[friendly error]
    G -->|yes| P[parse_csv_bytes\nutf-8-sig / utf-8 / latin-1] --> L{rows <= MAX_ROWS\ncols <= MAX_COLUMNS} -->|no| E2[ValidationError message]
    L -->|yes| TI[infer_column_types\nidentifier/date/numeric/categorical/text] --> CO[coerce_types\ndate strings -> datetime] --> SS[(session active_df)]
```

Uploaded content is treated strictly as data: bytes are parsed by `pd.read_csv` from
an in-memory buffer, never written to disk, never used as a path; filenames are
sanitized (`safe_filename`) to block path traversal.

## 5. Key trade-offs

| Decision | Rationale | Rejected alternative |
|---|---|---|
| In-memory session store | Zero external deps; bounded LRU; data is transient analytics state | Redis/SQLite (ops burden, not needed at this scale) |
| Server-side state, token in browser | Full frames never round-trip through the client; `dcc.Store` stays tiny | Storing DataFrames in `dcc.Store` (payload blow-up, tampering) |
| Pure functions in analytics | Testability + reuse by charts, exports and AI context alike | Methods on mutable app globals |
| Dash 4 with `dash_table.DataTable` | Only table component Dash 4 ships; works without a build step | Custom JS table (needs Node) |
| Flask `server` object exposed | Enables gunicorn/waitress/Docker deployment unchanged | `app.run` in production only |
