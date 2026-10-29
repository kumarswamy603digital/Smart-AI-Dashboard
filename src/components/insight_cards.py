"""Insight cards for the AI Studio: narrative + evidence, clearly separated."""
from __future__ import annotations

from dash import dcc, html

EXAMPLE_QUESTIONS = [
    "Which product category has the highest sales?",
    "Which region has the highest profit margin?",
    "How have monthly sales changed over time?",
    "Which categories show declining performance?",
    "What unusual values should I investigate?",
    "Summarize the main findings in the selected dataset.",
]


def _list_block(title: str, items: list[str], className: str) -> list:
    if not items:
        return []
    return [
        html.Div(title, className="insight-h"),
        html.Ul([html.Li(i, className=className) for i in items], className="insight-ul"),
    ]


def build_ai_studio() -> html.Div:
    return html.Div(className="section hidden", id="section-ai", children=[
        html.H2("AI Insights Studio", className="section-title"),
        html.P("Ask a question about the current dataset and filters. Python computes the statistics "
               "first; the model only interprets the evidence supplied to it.", className="section-sub"),
        html.Div(className="ai-ask", children=[
            html.Div([
                dcc.Textarea(
                    id="ai-question", className="ai-input",
                    placeholder="e.g. Which product category has the highest sales?",
                    rows=3, style={"width": "100%"},
                ),
                html.Div(className="ai-actions", children=[
                    html.Button("Analyze", id="ai-analyze-btn", className="btn btn-primary btn-lg",
                                n_clicks=0),
                    html.Span(id="ai-context-note", className="ai-note"),
                ]),
            ]),
        ]),
        html.Div(className="examples", children=[
            html.Span("Try:", className="examples-lead"),
            *[html.Button(q, id={"type": "example-q", "index": i}, className="chip",
                          n_clicks=0) for i, q in enumerate(EXAMPLE_QUESTIONS)],
            # Clientside-accessible copy of the question list (chip index → text).
            dcc.Store(id="example-questions", data=list(EXAMPLE_QUESTIONS)),
        ]),
        html.Div(id="ai-notice", className="ai-notice"),
        html.Div(id="ai-response", className="insight-wrap"),
    ])


def insight_children(result: dict) -> list:
    """Render a validated InsightResponse dict + provenance banner."""
    insight = result.get("insight", {})
    banner_cls = "prov prov-ai" if result.get("ai_used") else "prov prov-local"
    banner_text = (
        f"AI narrative by model '{result.get('model', 'openai')}' — interprets the computed "
        f"statistics below ({result.get('context_chars', 0):,} chars of bounded context were sent)."
        if result.get("ai_used")
        else f"Local mode — no AI narrative generated. {result.get('reason', '')} "
             f"(shown: deterministic computed statistics)."
    ).strip()
    children = [
        html.Div(banner_text, className=banner_cls),
        html.Div(className="insight-card", children=[
            html.Div("Summary", className="insight-h"),
            html.P(insight.get("summary", ""), className="insight-summary"),
            *_list_block("Findings", insight.get("findings", []), "finding"),
            *_list_block("Caveats & limitations", insight.get("caveats", []), "caveat"),
            *_list_block("Recommended investigations",
                         insight.get("recommended_investigations", []), "invest"),
        ]),
    ]
    metrics = insight.get("supporting_metrics", [])
    if metrics:
        children.append(html.Div(className="insight-card", children=[
            html.Div("Supporting computed statistics", className="insight-h"),
            html.Table(className="metric-table", children=[
                html.Tbody([
                    html.Tr([html.Th(m.get("name")),
                             html.Td(_num_str(m.get("value")))])
                    for m in metrics
                ])
            ]),
        ]))
    return children


def _num_str(v) -> str:
    if isinstance(v, (int, float)):
        return f"{v:,.2f}" if isinstance(v, float) else f"{v:,}"
    return str(v)
