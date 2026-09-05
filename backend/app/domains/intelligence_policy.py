from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Literal

SCORE_QUANTUM = Decimal("0.01")
COST_QUANTUM = Decimal("0.000001")
TOKENS_PER_MILLION = Decimal(1_000_000)
SCORE_WEIGHTS = (
    Decimal("0.40"),
    Decimal("0.25"),
    Decimal("0.20"),
    Decimal("0.15"),
)
OUTPUT_FIELDS = frozenset(
    {"summary", "category", "relevance", "importance", "novelty", "impact", "reason"}
)


class RecommendationValue(StrEnum):
    MUST_READ = "must_read"
    READ = "read"
    MONITOR = "monitor"
    ARCHIVE = "archive"


class OutputValidationError(ValueError):
    def __init__(self, reason: Literal["invalid_output", "invalid_category"]) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class AnalysisOutput:
    summary: str
    category: str
    relevance: int
    importance: int
    novelty: int
    impact: int
    reason: str


def calculate_score(relevance: int, importance: int, novelty: int, impact: int) -> Decimal:
    values = (relevance, importance, novelty, impact)
    weighted = sum(
        (Decimal(value) * weight for value, weight in zip(values, SCORE_WEIGHTS, strict=True)),
        start=Decimal(0),
    )
    return weighted.quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)


def recommendation_for(score: Decimal) -> RecommendationValue:
    if score >= Decimal("85"):
        return RecommendationValue.MUST_READ
    if score >= Decimal("70"):
        return RecommendationValue.READ
    if score >= Decimal("50"):
        return RecommendationValue.MONITOR
    return RecommendationValue.ARCHIVE


def qualifies_for_notification(score: Decimal, threshold: int) -> bool:
    return score >= Decimal(threshold)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    input_cost_per_million: Decimal,
    output_cost_per_million: Decimal,
) -> Decimal:
    value = (
        Decimal(input_tokens) * input_cost_per_million
        + Decimal(output_tokens) * output_cost_per_million
    ) / TOKENS_PER_MILLION
    return value.quantize(COST_QUANTUM, rounding=ROUND_HALF_UP)


def validate_output(content: str, categories: tuple[str, ...]) -> AnalysisOutput:
    try:
        raw = json.loads(content, parse_constant=_reject_constant)
        if not isinstance(raw, dict) or set(raw) != OUTPUT_FIELDS:
            raise ValueError("output fields are invalid")
        output = AnalysisOutput(
            summary=_validated_text(raw["summary"], minimum=1, maximum=2000),
            category=_validated_text(raw["category"], minimum=1, maximum=120),
            relevance=_validated_score(raw["relevance"]),
            importance=_validated_score(raw["importance"]),
            novelty=_validated_score(raw["novelty"]),
            impact=_validated_score(raw["impact"]),
            reason=_validated_text(raw["reason"], minimum=1, maximum=1000),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise OutputValidationError("invalid_output") from None
    if categories and output.category not in {*categories, "other"}:
        raise OutputValidationError("invalid_category")
    return output


def _validated_text(value: Any, *, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        raise ValueError("text length is invalid")
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
        raise ValueError("text contains control characters")
    normalized = value.strip()
    if not normalized:
        raise ValueError("text must not be blank")
    normalized.encode("utf-8")
    return normalized


def _validated_score(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError("score is invalid")
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
