"""AI Studio callbacks: question answering, suggested questions, history."""
from __future__ import annotations

import json

from dash import ALL, Input, Output, State, html, no_update

from src.ai.insights import answer_question
from src.components.insight_cards import insight_children
from src.services.dashboard_service import get_filtered_view


def _signature(token, ver, filters) -> str:
    """Identifies the (dataset, filters) context of a conversation."""
    return json.dumps([token or "", ver or 0, filters or {}], sort_keys=True, default=str)


def register(app) -> None:
    # Pattern-matching example chips are handled CLIENT-side: Dash 4's renderer
    # does not dispatch ALL-pattern n_clicks to the server here, and filling the
    # textarea needs no round trip anyway. The click's pattern id (a JSON string
    # in Dash 4) selects the question from the example-questions store.
    app.clientside_callback(
        """
        function(n_clicks, questions) {
            const cc = window.dash_clientside.callback_context;
            if (!cc || !cc.triggered.length || !questions) {
                return window.dash_clientside.no_update;
            }
            let tid = cc.triggered[0].prop_id.split('.n_clicks')[0];
            let idx = null;
            try { idx = JSON.parse(tid).index; } catch (e) {
                const m = tid.match(/"index"\\s*[:=]\\s*(\\d+)/);
                if (m) idx = parseInt(m[1], 10);
            }
            if (idx === null || idx === undefined || !questions[idx]) {
                return window.dash_clientside.no_update;
            }
            return questions[idx];
        }
        """,
        Output("ai-question", "value"),
        Input({"type": "example-q", "index": ALL}, "n_clicks"),
        State("example-questions", "data"),
        prevent_initial_call=True,
    )

    # Main analysis callback.
    @app.callback(
        [Output("ai-response", "children"),
         Output("ai-history", "data"),
         Output("ai-last-result", "data"),
         Output("ai-preview", "children"),
         Output("ai-context-note", "children")],
        Input("ai-analyze-btn", "n_clicks"),
        [State("ai-question", "value"),
         State("session-token", "data"),
         State("dataset-ver", "data"),
         State("filters-store", "data"),
         State("ai-history", "data")],
        prevent_initial_call=True,
    )
    def analyze(n_clicks, question, token, ver, filters, history):
        if not n_clicks:
            return no_update, no_update, no_update, no_update, no_update
        question = (question or "").strip()
        if not question:
            return html.Div("Type a question first.", className="notice-err"), \
                no_update, no_update, no_update, no_update
        if len(question) > 400:
            question = question[:400]

        df, desc, _name = get_filtered_view(token, filters)
        if df.empty:
            return html.Div("The current filters leave no rows to analyse.", className="notice-err"), \
                no_update, no_update, no_update, no_update

        sig = _signature(token, ver, filters)
        prior = history or {}
        if isinstance(prior, dict) and prior.get("signature") == sig:
            turns = prior.get("turns", [])[-5:]
            reset_note = None
        elif not prior or (isinstance(prior, dict) and not prior.get("turns")):
            # First question of the session — nothing to reset.
            turns = []
            reset_note = None
        else:
            turns = []
            reset_note = html.Div(
                "Conversation context was reset — the dataset or filters changed since the "
                "previous question.", className="notice-warn")

        try:
            result = answer_question(df, question, desc, history=turns)
        except Exception as exc:  # noqa: BLE001 — never let AI issues crash the dashboard
            result = {"ok": False, "ai_used": False,
                      "reason": f"Unexpected analysis failure ({type(exc).__name__}). "
                                "Dashboard features are unaffected.",
                      "insight": {}, "evidence": {}, "context_chars": 0}

        children = [reset_note] if reset_note else []
        children += insight_children(result)
        new_history = {"signature": sig,
                       "turns": turns + [{"question": question,
                                          "summary": (result.get("insight") or {}).get("summary", "")}]}
        preview = html.Div([
            html.B("Latest insight: "),
            html.Span(((result.get("insight") or {}).get("summary", "")[:220] + "…")
                      if result.get("insight") else "—"),
        ], className="ai-preview-text")
        note = html.Span(
            f"{result.get('context_chars', 0):,} characters of computed statistics were sent "
            f"to the AI provider ({'yes' if result.get('ai_used') else 'no — local mode'}). "
            "Your raw rows are never transmitted.", className="ai-note-text")
        return children, new_history, result, preview, note
