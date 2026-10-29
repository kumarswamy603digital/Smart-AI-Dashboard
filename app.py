"""AI Insights Dashboard — application entry point.

Run locally:
    python app.py
Then open http://127.0.0.1:8050

Production (Linux/macOS containers):
    gunicorn app:server --workers 2 --bind 0.0.0.0:8050 --timeout 120
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow `python app.py` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dash
from dash import Dash, Input, Output, dcc, html

from config.settings import settings
from src.callbacks import ai_callbacks, chart_callbacks, export_callbacks, filter_callbacks, upload_callbacks
from src.components.layout import build_layout
from src.data.sample_data import ensure_sample_csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
log = logging.getLogger("app")

app = Dash(
    name="AI Insights Dashboard",
    title="AI Insights Dashboard — Interactive Analytics & Natural-Language Insights",
    assets_folder=str(Path(__file__).resolve().parent / "assets"),
    update_title="Computing…",
    suppress_callback_exceptions=False,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description",
         "content": "Python + Plotly Dash analytics dashboard with OpenAI-grounded insights."},
    ],
)
server = app.server  # for Gunicorn / PaaS deployments

app.layout = build_layout()

# --- Session token: generated client-side, persisted per browser tab ---------
app.clientside_callback(
    """
    function(current) {
        if (current && current.length > 8) {
            return window.dash_clientside.no_update;
        }
        var t = sessionStorage.getItem('ai-dashboard-sid');
        if (!t) {
            t = 's-' + ([1e7]+-1e3+-4e3+-8e3+-1e11)
                .replace(/[018]/g, c =>
                    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
            sessionStorage.setItem('ai-dashboard-sid', t);
        }
        return t;
    }
    """,
    Output("session-token", "data"),
    Input("session-token", "data"),
)

# --- Sidebar navigation: pure CSS class toggle, no server round-trip ---------
_SECTION_IDS = ["section-overview", "section-explorer", "section-analytics",
                "section-ai", "section-status", "section-export"]
_NAV_IDS = [f"nav-{s.replace('section-', '')}" for s in _SECTION_IDS]
app.clientside_callback(
    f"""
    function(...clicks) {{
        const ctx = window.dash_clientside.callback_context;
        const order = {_SECTION_IDS!r};
        let active = 'section-overview';
        if (ctx.triggered.length) {{
            const propId = ctx.triggered[0].prop_id.split('.')[0];
            const idx = {_NAV_IDS!r}.indexOf(propId);
            if (idx >= 0 && ctx.triggered[0].value) active = order[idx];
        }}
        const sectionClasses = order.map(s =>
            s === active ? 'section' : 'section hidden');
        const navClasses = {_NAV_IDS!r}.map((n, i) =>
            order[i] === active ? 'nav-item active' : 'nav-item');
        return sectionClasses.concat(navClasses);
    }}
    """,
    [dash.Output(s, "className") for s in _SECTION_IDS]
    + [dash.Output(n, "className") for n in _NAV_IDS],
    [dash.Input(n, "n_clicks") for n in _NAV_IDS],
    prevent_initial_call=True,
)

# --- Register server callbacks ------------------------------------------------
for module in (upload_callbacks, filter_callbacks, chart_callbacks,
               ai_callbacks, export_callbacks):
    module.register(app)


@server.errorhandler(404)
def _not_found(_err):  # keep stack traces away from the browser
    return html.Div(
        [html.H2("Page not found"),
         html.P("Return to the ", dcc.Link("dashboard home", href="/"), ".")],
        className="error-page")


def main() -> None:
    ensure_sample_csv(settings.sample_csv)
    log.info("Starting AI Insights Dashboard on http://%s:%s (AI configured: %s)",
             settings.host, settings.port, settings.ai_configured)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)


if __name__ == "__main__":
    main()
