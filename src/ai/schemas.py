"""Pydantic schemas for validated, structured AI responses."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class MetricRef(BaseModel):
    """A computed statistic the model is allowed to cite."""
    name: str = Field(min_length=1, max_length=120)
    value: float | int | str | None = None
    unit: str | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class InsightResponse(BaseModel):
    """Structured natural-language insight grounded in computed statistics."""
    can_answer: bool = True
    summary: str = Field(default="", max_length=2000)
    findings: list[str] = Field(default_factory=list, max_length=12)
    supporting_metrics: list[MetricRef] = Field(default_factory=list, max_length=25)
    caveats: list[str] = Field(default_factory=list, max_length=10)
    recommended_investigations: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("findings", "caveats", "recommended_investigations", mode="before")
    @classmethod
    def _coerce_str_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(item)[:600] for item in v]

    @field_validator("supporting_metrics", mode="before")
    @classmethod
    def _coerce_metrics(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [{"name": k, "value": val} for k, val in v.items()]
        return v


INSIGHT_JSON_SCHEMA = InsightResponse.model_json_schema()
