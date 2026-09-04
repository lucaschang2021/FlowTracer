from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

FOUR_PLACES = Decimal("0.0001")


def _strict_number(value: int | Decimal, *, minimum: Decimal, maximum: Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError("quality component must be a finite number")
    number = Decimal(value)
    if not number.is_finite() or not minimum <= number <= maximum:
        raise ValueError("quality component is outside its allowed range")
    return number


def quality_score(
    *,
    meaningful_chars: int,
    visible_chars: int,
    navigation_chars: int,
    executable_script_count: int,
    has_title: bool,
    has_publish_date: bool,
    has_author: bool,
    has_canonical: bool,
) -> Decimal:
    for value in (meaningful_chars, visible_chars, navigation_chars, executable_script_count):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("quality counts must be non-negative integers")
    if navigation_chars > visible_chars:
        raise ValueError("navigation characters cannot exceed visible characters")
    for value in (has_title, has_publish_date, has_author, has_canonical):
        if not isinstance(value, bool):
            raise ValueError("quality flags must be strict booleans")
    if meaningful_chars == 0:
        return Decimal("0.0000")
    meaningful = min(Fraction(meaningful_chars, 400), Fraction(1))
    density = min(Fraction(2 * meaningful_chars, max(visible_chars, 1)), Fraction(1))
    noise = Fraction(1) - Fraction(navigation_chars, max(visible_chars, 1))
    shell = Fraction(0) if meaningful_chars < 80 and executable_script_count > 0 else Fraction(1)
    total = (
        Fraction(30, 100) * meaningful
        + Fraction(15, 100) * density
        + Fraction(10, 100) * int(has_title)
        + Fraction(10, 100) * int(has_publish_date)
        + Fraction(5, 100) * int(has_author)
        + Fraction(10, 100) * int(has_canonical)
        + Fraction(10, 100) * noise
        + Fraction(10, 100) * shell
    )
    exact = Decimal(total.numerator) / Decimal(total.denominator)
    return exact.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def quality_bucket(score: Decimal) -> str:
    value = _strict_number(score, minimum=Decimal(0), maximum=Decimal(1))
    if value < Decimal("0.4500"):
        return "low"
    if value < Decimal("0.6000"):
        return "marginal"
    return "acceptable"


def aggregate_quality(scores: list[Decimal | None]) -> Decimal | None:
    if not scores or any(score is None for score in scores):
        return None
    values = [score for score in scores if score is not None]
    return (sum(values, Decimal(0)) / Decimal(len(values))).quantize(
        FOUR_PLACES, rounding=ROUND_HALF_UP
    )


def update_quality_ewma(old: Decimal | None, new: Decimal | None) -> Decimal | None:
    if new is None:
        return old
    if old is None:
        return new.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
    return (Decimal("0.8") * old + Decimal("0.2") * new).quantize(
        FOUR_PLACES, rounding=ROUND_HALF_UP
    )
