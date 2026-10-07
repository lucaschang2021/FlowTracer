"""ACQ-1G action payload projection (docs/24 §2, ADR-037).

The payload is an immutable, non-executable, versioned projection of a scored
opportunity: every fact traces back to the AcquisitionSnapshot, money and scores
serialize as strings, ``requires_human_approval`` is always true, and the canonical
JSON plus its SHA-256 digest are frozen under the 32 KiB cap.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domains.opportunity_policy import (
    ALL_DIMENSIONS,
    PAYLOAD_VERSION,
    PROFILE_VERSION,
    SCORE_VERSION,
    EvaluationOutput,
    OpportunityFacts,
)

MAX_PAYLOAD_DESCRIPTION = 4000
MAX_PAYLOAD_BYTES = 32768


def build_action_payload(
    *,
    facts: OpportunityFacts,
    evaluation: EvaluationOutput,
    overall: Decimal,
    recommendation: str,
    opportunity_id: UUID,
    radar_id: UUID,
    now: datetime,
) -> dict[str, Any]:
    """Immutable, non-executable projection with every fact traceable to the snapshot."""
    dimensions = evaluation.dimensions
    return {
        "payload_version": PAYLOAD_VERSION,
        "opportunity_id": str(opportunity_id),
        "source": {"platform": facts.platform, "url": facts.source_url},
        "title": facts.title,
        "description": (facts.description or "")[:MAX_PAYLOAD_DESCRIPTION],
        "budget": {
            "min": _money(facts.budget_min),
            "max": _money(facts.budget_max),
            "currency": facts.currency,
        },
        "skills": list(facts.skills),
        "deadline": None if facts.deadline is None else facts.deadline.isoformat(),
        "score": {
            "overall": str(overall),
            "dimensions": {name: getattr(dimensions, name) for name in ALL_DIMENSIONS},
            "recommendation": recommendation,
            "reason": evaluation.reason,
        },
        "risk": dimensions.risk,
        "source_url": facts.source_url,
        "recommended_action": recommendation,
        "requires_human_approval": True,
        "context": {
            "profile_version": PROFILE_VERSION,
            "score_version": SCORE_VERSION,
            "radar_id": str(radar_id),
        },
        "generated_at": now.isoformat(),
    }


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_digest(payload: dict[str, Any]) -> tuple[str, str]:
    """Return the canonical JSON and its SHA-256 hex digest; enforce the 32 KiB cap."""
    canonical = canonical_payload(payload)
    encoded = canonical.encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ValueError("opportunity action payload exceeds the frozen size cap")
    return canonical, hashlib.sha256(encoded).hexdigest()
