# Deployment

The app is a standard WSGI app: `app.py` exposes `server = app.server` (the Flask
instance Dash runs on), which any WSGI server can serve.

## 1. Local development

```bash
pip install -r requirements.txt
python app.py                     # http://127.0.0.1:8050
# hot reload:  set DASH_DEBUG=true in .env first
```

## 2. Docker

```bash
docker build -t ai-dashboard .
docker run -p 8050:8050 --env-file .env ai-dashboard
# or
docker compose up          # reads OPENAI_API_KEY from your shell env (optional)
```

- Image: `python:3.11-slim`, non-root user, `curl` healthcheck on `/`.
- The AI key is injected at **runtime** via environment — never baked into the image.
- Without `OPENAI_API_KEY` the container still serves the full analytics dashboard
  (local statistics mode).

## 3. Bare metal / VM

**Linux / macOS (gunicorn):**

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
gunicorn -w 2 -b 0.0.0.0:8050 --timeout 120 app:server
```

**Windows (waitress):**

```powershell
py -m venv venv; venv\Scripts\pip install -r requirements.txt
venv\Scripts\waitress-serve --host=0.0.0.0 --port=8050 app:server
```

> Use **1–2 workers maximum** per instance: session state is in-memory by design
> (bounded LRU store). With more workers, pin sessions with sticky routing or
> accept that an upload lives on the worker that received it.

## 4. Reverse proxy (nginx example)

```nginx
location / {
    proxy_pass http://127.0.0.1:8050;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 20m;      # > MAX_UPLOAD_MB (15)
    proxy_read_timeout 120s;       # AI calls can take OPENAI_TIMEOUT seconds
}
```

## 5. Environment reference

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | empty | **Never commit.** Empty ⇒ AI degrades to local statistics mode |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any Responses-API-capable model |
| `OPENAI_TIMEOUT` | `30` | Seconds; raise proxy `read_timeout` to match |
| `OPENAI_MAX_CONTEXT_CHARS` | `6000` | Hard cap on outbound data context |
| `OPENAI_MAX_HISTORY_TURNS` | `6` | Follow-up memory per dataset+filter signature |
| `MAX_UPLOAD_MB` | `15` | Also raise nginx `client_max_body_size` |
| `MAX_ROWS` / `MAX_COLUMNS` | `200000` / `200` | Post-parse rejection limits |
| `DASH_HOST` / `DASH_PORT` | `127.0.0.1` / `8050` | Use `0.0.0.0` inside containers |
| `DASH_DEBUG` | `false` | Never `true` in production (reloader + tracebacks) |
| `SESSION_STORE_CAPACITY` | `64` | Concurrent sessions held per worker |

## 6. Operations notes

- **Health check:** `GET /` returns 200 once the sample dataset has been generated
  (`data/sample_sales.csv` is created on first boot if missing).
- **Logs:** standard WSGI access/error logs; the app logs no dataset contents and
  never logs the API key.
- **State lifetime:** uploads live in memory only — a restart returns every session
  to the sample dataset. This is intentional (transient analytics state) but means
  no horizontal session sharing without sticky workers.
- **Security posture:** CSVs are parsed in-memory and never written to disk;
  filenames are sanitized; AI prompts treat all data as untrusted; uploads and
  AI context are size/row-bounded to keep one tenant from starving the process.
