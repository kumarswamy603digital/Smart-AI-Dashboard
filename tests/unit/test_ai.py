"""Unit tests for the AI layer. NO real network calls: the OpenAI SDK is
either absent (local mode) or replaced by stubs."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from config.settings import settings
from src.ai import client as client_mod
from src.ai import insights
from src.ai.client import AIError, OpenAIInsightClient
from src.ai.schemas import InsightResponse


class FakeCfg:
    def __init__(self, key: str = "sk-test-1234567890abcdef"):
        self.openai_api_key = key
        self.openai_model = "gpt-4o-mini"
        self.openai_timeout_seconds = 20.0


class FakeResponses:
    """Mimics openai.resources.responses with a canned output_text."""

    def __init__(self, text: str, raises: Exception | None = None):
        self.text, self.raises, self.calls = text, raises, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return type("Resp", (), {"output_text": self.text, "output": []})()


class FakeSDK:
    def __init__(self, text: str, raises: Exception | None = None):
        self.responses = FakeResponses(text, raises)


INSIGHT_JSON = json.dumps(
    {
        "can_answer": True,
        "summary": "Sales concentrate in a few regions.",
        "findings": ["North leads total sales."],
        "supporting_metrics": [{"name": "total_sales", "value": 600.0}],
        "caveats": ["Correlation is not causation."],
        "recommended_investigations": [],
    }
)


def make_client(text=INSIGHT_JSON, raises=None, key="sk-test-1234567890abcdef") -> OpenAIInsightClient:
    c = OpenAIInsightClient(FakeCfg(key))
    c._client = FakeSDK(text, raises)
    return c


class TestAvailabilityAndStatus:
    def test_no_key_unavailable(self):
        c = OpenAIInsightClient(FakeCfg(""))
        assert not c.is_available()
        st = c.status()
        assert st["configured"] is False and st["key_masked"] == "not set"

    def test_ask_without_key_raises(self, tiny_sales_df):
        c = OpenAIInsightClient(FakeCfg(""))
        with pytest.raises(AIError, match="not configured"):
            c.ask("why?", "{}")

    def test_status_never_leaks_key(self):
        c = OpenAIInsightClient(FakeCfg("sk-test-1234567890abcdef"))
        st = c.status()
        assert "1234567890" not in json.dumps(st)
        assert st["key_masked"].startswith("sk-") and st["key_masked"].endswith("cdef")


class TestClientParsing:
    def test_valid_structured_json(self, tiny_sales_df):
        c = make_client()
        out = c.ask("Which region sells most?", "{}")
        assert isinstance(out, InsightResponse)
        assert out.summary.startswith("Sales")

    def test_lenient_parse_fenced_json(self):
        parsed = OpenAIInsightClient._lenient_parse("```json\n" + INSIGHT_JSON + "\n```")
        assert parsed is not None and parsed.can_answer is True

    def test_lenient_parse_garbage_returns_none(self):
        assert OpenAIInsightClient._lenient_parse("not json at all") is None

    def test_malformed_model_output_falls_back_or_errors(self):
        c = make_client(text="I think sales are fine.")  # not JSON
        with pytest.raises(AIError, match="did not match"):
            c.ask("q", "{}")

    def test_schema_coercion(self):
        r = InsightResponse.model_validate(
            {"summary": "s", "findings": "single string", "supporting_metrics": {"a": 1}}
        )
        assert r.findings == ["single string"]
        assert r.supporting_metrics[0].name == "a"


class TestErrorMapping:
    @pytest.mark.parametrize(
        "exc_cls, needle",
        [
            ("AuthenticationError", "rejected the API key"),
            ("RateLimitError", "rate limit"),
            ("APITimeoutError", "timed out"),
            ("APIConnectionError", "network error"),
        ],
    )
    def test_sdk_errors_become_friendly_aierrors(self, exc_cls, needle):
        import httpx
        import openai

        request = httpx.Request("POST", "https://api.openai.test/v1/responses")
        if exc_cls in ("APITimeoutError", "APIConnectionError"):
            exc = getattr(openai, exc_cls)(request=request)
        else:
            response = httpx.Response(
                401 if exc_cls == "AuthenticationError" else 429,
                request=request,
                headers={"x-request-id": "req_test"},
            )
            exc = getattr(openai, exc_cls)(message="boom", response=response, body=None)
        c = make_client(raises=exc)
        with pytest.raises(AIError, match=needle):
            c.ask("q", "{}")

    def test_instructions_are_the_system_prompt(self):
        c = make_client()
        c.ask("hello?", '{"row_count": 3}')
        call = c._client.responses.calls[-1]
        assert call["instructions"] == client_mod.SYSTEM_PROMPT
        assert "hello?" in call["input"] and "row_count" in call["input"]


class TestBoundedContext:
    def test_context_contains_computed_stats(self, tiny_sales_df):
        ctx = insights.build_bounded_context(tiny_sales_df, dims=["region"])
        assert ctx["kpis"]["total_sales"] == pytest.approx(600.0)
        assert "top8_region_by_sales" in ctx
        assert "monthly_trend" in ctx

    def test_raw_row_identifiers_never_in_context(self, sample_df):
        ctx = insights.build_bounded_context(sample_df)
        blob = json.dumps(ctx, default=str)
        sample_ids = sample_df["order_id"].astype(str).tolist()
        leaked = [i for i in sample_ids if f'"{i}"' in blob]
        assert not leaked, f"raw identifiers leaked into AI context: {leaked[:3]}"

    def test_trim_hard_caps_size(self, sample_df):
        # Floor is the irreducible schema/KPI metadata; cap used by the app is 6000.
        ctx = insights._trim_context(
            insights.build_bounded_context(sample_df), max_chars=1500
        )
        assert insights.context_char_count(ctx) <= max(1500, 2000)

    def test_answer_question_local_mode(self, tiny_sales_df, monkeypatch):
        monkeypatch.setattr(insights, "get_client", lambda: OpenAIInsightClient(FakeCfg("")))
        res = insights.answer_question(tiny_sales_df, "why is profit negative?")
        assert res["ok"] and res["ai_used"] is False
        assert "OPENAI_API_KEY" in res["reason"]
        assert res["insight"]["summary"]

    def test_answer_question_ai_mode(self, tiny_sales_df, monkeypatch):
        monkeypatch.setattr(insights, "get_client", lambda: make_client())
        res = insights.answer_question(tiny_sales_df, "which region leads?")
        assert res["ok"] and res["ai_used"] is True
        assert res["model"] == settings.openai_model
        assert res["evidence"]["kpis"]["total_sales"] == pytest.approx(600.0)

    def test_answer_question_ai_failure_degrades_locally(self, tiny_sales_df, monkeypatch):
        boom = make_client(raises=RuntimeError("always fails"))

        def always_fail(question, context_json, history=None):
            raise AIError("OpenAI rate limit reached. Please wait a moment and try again.")

        monkeypatch.setattr(boom, "ask", always_fail)
        monkeypatch.setattr(insights, "get_client", lambda: boom)
        res = insights.answer_question(tiny_sales_df, "which region leads?")
        assert res["ok"] is False and res["ai_used"] is False
        assert "rate limit" in res["reason"]
        # Still returns locally computed evidence for the UI
        assert res["insight"]["summary"]

    def test_empty_context_chars_reported(self, no_schema_df):
        res = insights.build_bounded_context(no_schema_df)
        assert insights.context_char_count(res) > 0
        assert res["row_count"] == 4
