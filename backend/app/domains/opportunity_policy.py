"""ACQ-1G Opportunity deterministic policy (docs/24 §4/§5/§6, ADR-025).

Pure product rules with no I/O: the ``freelance-v1`` hard filter, the
``opportunity-score-v1`` weighted score, recommendation bands, strict evaluation
output parsing and notification qualification. The evaluation service supplies
bounded facts and persists results.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

PROFILE_VERSION = "freelance-v1"
SCORE_VERSION = "opportunity-score-v1"
PAYLOAD_VERSION = "opportunity-action-v1"
EVALUATION_PROMPT_VERSION = "opportunity-eval-v1"

SCORE_QUANTUM = Decimal("0.01")
RISK_NOTIFICATION_CEILING = 30
AMBIGUITY_NOTIFICATION_CEILING = 40
NOTIFICATION_SCORE_FLOOR = Decimal("85")

DISQUALIFIER_CODES = (
    "insufficient_data",
    "currency_unsupported",
    "budget_out_of_profile",
    "effort_over_profile",
    "delivery_unsupported",
    "delivery_window_out_of_profile",
    "meetings_over_profile",
    "maintenance_required",
    "prohibited_content",
)

PROHIBITED_CONTENT_KEYWORDS = (
    "account takeover",
    "bank account",
    "bypass authentication",
    "bypass captcha",
    "bypass paywall",
    "credential",
    "credit card number",
    "ddos",
    "exploit",
    "fake reviews",
    "hack into",
    "identity theft",
    "login credentials",
    "malware",
    "password",
    "payment account",
    "phishing",
    "ransomware",
    "scrape login",
    "spam",
    "steal",
    "stolen",
    "unauthorized access",
    "wire transfer",
)

POSITIVE_DIMENSIONS = (
    "fit",
    "expected_value",
    "completion_probability",
    "effort_efficiency",
    "time_to_delivery",
)
NEGATIVE_DIMENSIONS = ("competition", "ambiguity", "risk")
ALL_DIMENSIONS = (*POSITIVE_DIMENSIONS, *NEGATIVE_DIMENSIONS)
POSITIVE_WEIGHTS = (
    Decimal("0.25"),
    Decimal("0.20"),
    Decimal("0.20"),
    Decimal("0.15"),
    Decimal("0.10"),
)
NEGATIVE_WEIGHTS = (Decimal("0.04"), Decimal("0.03"), Decimal("0.03"))
MIN_OVERALL = Decimal("0")
MAX_OVERALL = Decimal("100")
MAX_REASON_CHARS = 1000


@dataclass(frozen=True, slots=True)
class OpportunityFacts:
    """Bounded facts an opportunity may carry; missing values stay None."""

    title: str | None = None
    description: str | None = None
    source_url: str | None = None
    platform: str | None = None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    currency: str | None = None
    skills: tuple[str, ...] = ()
    deadline: datetime | None = None
    published_at: datetime | None = None
    estimated_effort_hours: Decimal | None = None
    delivery_type: str | None = None
    required_meetings: int | None = None
    maintenance_required: bool | None = None


@dataclass(frozen=True, slots=True)
class FreelanceProfile:
    currency_allowlist: tuple[str, ...] = ("USD",)
    budget_min: Decimal = Decimal("10.00")
    budget_max: Decimal = Decimal("80.00")
    max_estimated_effort_hours: Decimal = Decimal("8")
    max_delivery_days: int = 2
    delivery_type_allowlist: tuple[str, ...] = ("one_off",)
    max_required_meetings: int = 1
    maintenance_required: bool = False


DEFAULT_PROFILE = FreelanceProfile()


@dataclass(frozen=True, slots=True)
class HardFilterOutcome:
    passed: bool
    disqualifiers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Dimensions:
    fit: int
    expected_value: int
    completion_probability: int
    effort_efficiency: int
    time_to_delivery: int
    competition: int
    ambiguity: int
    risk: int


@dataclass(frozen=True, slots=True)
class EvaluationOutput:
    dimensions: Dimensions
    reason: str
    missing: tuple[str, ...]


class EvaluationOutputError(ValueError):
    """Strict evaluation output violation; the whole result must be rejected."""


def hard_filter(
    facts: OpportunityFacts, profile: FreelanceProfile = DEFAULT_PROFILE
) -> HardFilterOutcome:
    """Closed deterministic filter; every observed violation is reported."""
    if _insufficient(facts):
        return HardFilterOutcome(passed=False, disqualifiers=("insufficient_data",))
    disqualifiers: list[str] = []
    if facts.currency not in profile.currency_allowlist:
        disqualifiers.append("currency_unsupported")
    if _budget_out_of_profile(facts, profile):
        disqualifiers.append("budget_out_of_profile")
    if (
        facts.estimated_effort_hours is not None
        and facts.estimated_effort_hours > profile.max_estimated_effort_hours
    ):
        disqualifiers.append("effort_over_profile")
    if (
        facts.delivery_type is not None
        and facts.delivery_type not in profile.delivery_type_allowlist
    ):
        disqualifiers.append("delivery_unsupported")
    if _delivery_window_out_of_profile(facts, profile):
        disqualifiers.append("delivery_window_out_of_profile")
    if (
        facts.required_meetings is not None
        and facts.required_meetings > profile.max_required_meetings
    ):
        disqualifiers.append("meetings_over_profile")
    if facts.maintenance_required and not profile.maintenance_required:
        disqualifiers.append("maintenance_required")
    if _prohibited_content(facts):
        disqualifiers.append("prohibited_content")
    return HardFilterOutcome(passed=not disqualifiers, disqualifiers=tuple(disqualifiers))


def _insufficient(facts: OpportunityFacts) -> bool:
    if not (facts.title and facts.title.strip()):
        return True
    if not (facts.description and facts.description.strip()):
        return True
    if not (facts.source_url and facts.source_url.strip()):
        return True
    if not facts.currency:
        return True
    return facts.budget_min is None and facts.budget_max is None


def _budget_out_of_profile(facts: OpportunityFacts, profile: FreelanceProfile) -> bool:
    if facts.budget_max is not None and facts.budget_max < profile.budget_min:
        return True
    return facts.budget_min is not None and facts.budget_min > profile.budget_max


def _delivery_window_out_of_profile(facts: OpportunityFacts, profile: FreelanceProfile) -> bool:
    if facts.deadline is None or facts.published_at is None:
        return False
    return facts.deadline - facts.published_at > timedelta(days=profile.max_delivery_days)


def _prohibited_content(facts: OpportunityFacts) -> bool:
    haystack = f"{facts.title or ''}\n{facts.description or ''}".casefold()
    return any(keyword in haystack for keyword in PROHIBITED_CONTENT_KEYWORDS)


def overall_score(dimensions: Dimensions) -> Decimal:
    values = [getattr(dimensions, name) for name in ALL_DIMENSIONS]
    total = sum(
        (
            Decimal(value) * weight
            for value, weight in zip(values[: len(POSITIVE_WEIGHTS)], POSITIVE_WEIGHTS, strict=True)
        ),
        start=Decimal(0),
    )
    total += sum(
        (
            (MAX_OVERALL - Decimal(value)) * weight
            for value, weight in zip(values[len(POSITIVE_WEIGHTS) :], NEGATIVE_WEIGHTS, strict=True)
        ),
        start=Decimal(0),
    )
    quantized = total.quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)
    return max(MIN_OVERALL, min(MAX_OVERALL, quantized))


def recommendation_for(score: Decimal) -> str:
    if score >= Decimal("85"):
        return "act_now"
    if score >= Decimal("70"):
        return "review"
    if score >= Decimal("50"):
        return "watch"
    return "dismiss"


def notification_qualified(
    *,
    hard_filter_passed: bool,
    overall: Decimal | None,
    risk: int | None,
    ambiguity: int | None,
    opportunity_status: str,
    deadline: datetime | None,
    radar_threshold: int,
    now: datetime,
    radar_active: bool = True,
) -> bool:
    if not radar_active or not hard_filter_passed:
        return False
    if overall is None or risk is None or ambiguity is None:
        return False
    if opportunity_status != "active":
        return False
    if deadline is not None and deadline <= now:
        return False
    if overall < max(NOTIFICATION_SCORE_FLOOR, Decimal(radar_threshold)):
        return False
    if risk > RISK_NOTIFICATION_CEILING:
        return False
    return ambiguity <= AMBIGUITY_NOTIFICATION_CEILING


def parse_evaluation(raw: Mapping[str, Any]) -> EvaluationOutput:
    """Strictly validate provider dimensions and apply frozen missing-value defaults."""
    if not isinstance(raw, Mapping):
        raise EvaluationOutputError("evaluation output must be an object")
    unknown = set(raw) - {*ALL_DIMENSIONS, "reason"}
    if unknown:
        raise EvaluationOutputError("evaluation output contains unknown fields")
    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > MAX_REASON_CHARS:
        raise EvaluationOutputError("evaluation reason is invalid")
    if any(ord(character) < 32 for character in reason):
        raise EvaluationOutputError("evaluation reason contains control characters")
    values: dict[str, int] = {}
    missing: list[str] = []
    for name in ALL_DIMENSIONS:
        if name not in raw:
            missing.append(name)
            values[name] = 0 if name in POSITIVE_DIMENSIONS else 100
            continue
        value = raw[name]
        if type(value) is not int or not 0 <= value <= 100:
            raise EvaluationOutputError("evaluation dimension is invalid")
        values[name] = value
    reason_text = reason.strip()
    if missing:
        reason_text = (f"{reason_text} (missing dimensions defaulted: {', '.join(missing)})")[
            :MAX_REASON_CHARS
        ]
    return EvaluationOutput(
        dimensions=Dimensions(**values), reason=reason_text, missing=tuple(missing)
    )
