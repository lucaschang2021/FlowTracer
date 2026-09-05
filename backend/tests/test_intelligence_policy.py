from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.domains.intelligence_policy import (
    AnalysisOutput,
    OutputValidationError,
    RecommendationValue,
    calculate_cost,
    calculate_score,
    qualifies_for_notification,
    recommendation_for,
    validate_output,
)


def output_json(**changes: object) -> str:
    payload: dict[str, object] = {
        "summary": " Summary ",
        "category": "technology",
        "relevance": 90,
        "importance": 80,
        "novelty": 70,
        "impact": 60,
        "reason": " Useful ",
    }
    payload.update(changes)
    return json.dumps(payload)


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ((0, 0, 0, 0), Decimal("0.00")),
        ((100, 0, 0, 0), Decimal("40.00")),
        ((0, 100, 0, 0), Decimal("25.00")),
        ((0, 0, 100, 0), Decimal("20.00")),
        ((0, 0, 0, 100), Decimal("15.00")),
        ((90, 80, 70, 60), Decimal("79.00")),
        ((100, 100, 100, 100), Decimal("100.00")),
    ],
)
def test_score_preserves_frozen_weights_and_two_decimal_quantization(
    scores: tuple[int, int, int, int], expected: Decimal
) -> None:
    assert calculate_score(*scores) == expected


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        ("0", RecommendationValue.ARCHIVE),
        ("49.99", RecommendationValue.ARCHIVE),
        ("50", RecommendationValue.MONITOR),
        ("69.99", RecommendationValue.MONITOR),
        ("70", RecommendationValue.READ),
        ("84.99", RecommendationValue.READ),
        ("85", RecommendationValue.MUST_READ),
        ("100", RecommendationValue.MUST_READ),
    ],
)
def test_recommendation_preserves_exact_boundaries(
    score: str, expected: RecommendationValue
) -> None:
    assert recommendation_for(Decimal(score)) is expected


def test_notification_threshold_is_inclusive() -> None:
    assert not qualifies_for_notification(Decimal("84.99"), 85)
    assert qualifies_for_notification(Decimal("85.00"), 85)
    assert qualifies_for_notification(Decimal("85.01"), 85)


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens", "input_rate", "output_rate", "expected"),
    [
        (10, 20, "1.234567", "2.345678", "0.000059"),
        (1, 0, "0.5", "0", "0.000001"),
        (1, 0, "0.4", "0", "0.000000"),
        (0, 0, "999", "999", "0.000000"),
    ],
)
def test_cost_uses_per_million_rates_and_half_up_six_decimals(
    input_tokens: int,
    output_tokens: int,
    input_rate: str,
    output_rate: str,
    expected: str,
) -> None:
    assert calculate_cost(
        input_tokens,
        output_tokens,
        Decimal(input_rate),
        Decimal(output_rate),
    ) == Decimal(expected)


def test_strict_output_returns_frozen_immutable_value_and_other_fallback() -> None:
    output = validate_output(output_json(), ("technology", "policy"))
    other = validate_output(output_json(category="other"), ("technology",))
    uncategorized = validate_output(output_json(category="unlisted"), ())

    assert output == AnalysisOutput("Summary", "technology", 90, 80, 70, 60, "Useful")
    assert other.category == "other"
    assert uncategorized.category == "unlisted"
    with pytest.raises(AttributeError):
        output.summary = "changed"  # type: ignore[misc]


def test_strict_output_accepts_exact_text_boundaries() -> None:
    output = validate_output(
        output_json(summary="s" * 2000, category="c" * 120, reason="r" * 1000),
        (),
    )
    assert len(output.summary) == 2000
    assert len(output.category) == 120
    assert len(output.reason) == 1000


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        "{}",
        "```json\n{}\n```",
        output_json(extra=1),
        output_json(relevance=True),
        output_json(relevance=1.5),
        output_json(relevance=-1),
        output_json(relevance=101),
        output_json(summary=""),
        output_json(summary=" "),
        output_json(summary="s" * 2001),
        output_json(category="c" * 121),
        output_json(reason="r" * 1001),
        output_json(summary="bad\u0001text"),
        output_json(summary="bad\u007ftext"),
        output_json(summary="bad\u009ftext"),
        output_json(summary="bad\ud800text"),
        output_json(summary=1),
        output_json(relevance=None),
        output_json(relevance="90"),
    ],
)
def test_strict_output_rejects_invalid_shape_types_ranges_and_text(content: str) -> None:
    with pytest.raises(OutputValidationError) as raised:
        validate_output(content, ("technology",))
    assert raised.value.reason == "invalid_output"
    assert content not in str(raised.value)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_strict_output_rejects_non_finite_json_constants(constant: str) -> None:
    content = output_json().replace('"relevance": 90', f'"relevance": {constant}')
    with pytest.raises(OutputValidationError) as raised:
        validate_output(content, ("technology",))
    assert raised.value.reason == "invalid_output"


def test_strict_output_rejects_category_outside_allowed_values() -> None:
    with pytest.raises(OutputValidationError) as raised:
        validate_output(output_json(category="finance"), ("technology", "other"))
    assert raised.value.reason == "invalid_category"
