"""Thin, defensive wrapper around the OpenAI Responses API.

All AI requests funnel through this single module. The dashboard never breaks
because of it: when no key is configured `is_available()` is False and callers
degrade to local-only mode. The API key is never returned to the frontend and
never logged.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from config.settings import settings
from src.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from src.ai.schemas import INSIGHT_JSON_SCHEMA, InsightResponse

logger = logging.getLogger("ai.client")


class AIError(Exception):
    """User-presentable AI failure with a friendly message."""


class OpenAIInsightClient:
    def __init__(self, new_settings: Any = None):
        self.cfg = new_settings or settings
        self._client = None
        self._struct_failed = False  # remember if structured output errored once

    # -- availability --------------------------------------------------------
    def is_available(self) -> bool:
        return bool(self.cfg.openai_api_key)

    def status(self) -> dict:
        """Safe status for the UI — never includes the key itself."""
        key = self.cfg.openai_api_key
        masked = f"{key[:3]}…{key[-4:]}" if len(key) > 8 else ("set" if key else "not set")
        return {
            "configured": bool(key),
            "key_masked": masked if key else "not set",
            "model": self.cfg.openai_model,
            "timeout_s": self.cfg.openai_timeout_seconds,
        }

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.cfg.openai_api_key,
                timeout=self.cfg.openai_timeout_seconds,
                max_retries=1,
            )
        return self._client

    # -- requests --------------------------------------------------------------
    def ask(self, question: str, context_json: str,
            history: list[dict] | None = None) -> InsightResponse:
        if not self.is_available():
            raise AIError("AI features are unavailable: OPENAI_API_KEY is not configured.")
        user_prompt = build_user_prompt(question, context_json, history)
        try:
            raw = self._call_responses(user_prompt, structured=not self._struct_failed)
        except AIError:
            raise
        try:
            return InsightResponse.model_validate_json(raw)
        except Exception:
            parsed = self._lenient_parse(raw)
            if parsed is None:
                raise AIError(
                    "The model returned a response that did not match the expected structure. "
                    "Please retry."
                )
            return parsed

    def _call_responses(self, user_prompt: str, structured: bool) -> str:
        from openai import (
            APIConnectionError, APIError, APIStatusError, APITimeoutError,
            AuthenticationError, RateLimitError,
        )

        text_format = None
        if structured:
            text_format = {
                "format": {
                    "type": "json_schema",
                    "name": "insight_response",
                    "strict": False,
                    "schema": INSIGHT_JSON_SCHEMA,
                }
            }
        try:
            resp = self._get_client().responses.create(
                model=self.cfg.openai_model,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                text=(text_format or {"format": {"type": "json_object"}}),
                temperature=0.2,
                max_output_tokens=1200,
            )
            return self._extract_text(resp)
        except AuthenticationError as exc:
            raise AIError("OpenAI rejected the API key. Check OPENAI_API_KEY in your .env file.") from exc
        except RateLimitError as exc:
            raise AIError("OpenAI rate limit reached. Please wait a moment and try again.") from exc
        except APITimeoutError as exc:
            raise AIError(
                f"The OpenAI request timed out after {self.cfg.openai_timeout_seconds:g}s. "
                "Check your connection or raise OPENAI_TIMEOUT."
            ) from exc
        except APIConnectionError as exc:
            raise AIError("Could not reach the OpenAI service (network error).") from exc
        except APIStatusError as exc:
            # Some models reject json_schema — retry once with plain json_object.
            if exc.status_code == 400 and structured and "json_schema" in str(exc.body).lower():
                self._struct_failed = True
                logger.info("Structured output unsupported; falling back to json_object mode.")
                return self._call_responses(user_prompt, structured=False)
            raise AIError(f"OpenAI API error ({exc.status_code}). The request was not completed.") from exc
        except APIError as exc:
            raise AIError("OpenAI API failure. Please try again shortly.") from exc

    @staticmethod
    def _extract_text(resp) -> str:
        # Responses API: prefer output_text; fall back to walking output items.
        text = getattr(resp, "output_text", None)
        if text:
            return text.strip()
        parts = []
        for item in getattr(resp, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                t = getattr(content, "text", None)
                if t:
                    parts.append(t)
        if not parts:
            raise AIError("The model returned an empty response. Please retry.")
        return "\n".join(parts).strip()

    @staticmethod
    def _lenient_parse(raw: str) -> InsightResponse | None:
        """Documented fallback: strip fences / locate the JSON object, then validate."""
        candidates = [raw]
        if "{" in raw and "}" in raw:
            candidates.append(raw[raw.index("{"): raw.rindex("}") + 1])
        for cand in candidates:
            try:
                data = json.loads(cand)
                if isinstance(data, dict):
                    return InsightResponse.model_validate(data)
            except (json.JSONDecodeError, Exception):  # noqa: BLE001
                continue
        return None


_client_singleton: OpenAIInsightClient | None = None


def get_client() -> OpenAIInsightClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = OpenAIInsightClient()
    return _client_singleton
