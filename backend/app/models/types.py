"""Shared SQLAlchemy column-type helpers for ORM models.

Extracted from ``entities.py`` so model modules added after the architecture budget
was frozen (for example ``notification.py``, ``opportunity.py`` and ``raw_item.py``)
can reuse them without growing the baseline module.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, text
from sqlalchemy.orm import Mapped, mapped_column


def enum_column(enum_type: type[PyEnum], name: str) -> Enum:
    return Enum(
        enum_type, name=name, values_callable=lambda values: [item.value for item in values]
    )


def varchar_enum(enum_type: type[PyEnum], length: int) -> Enum:
    return Enum(
        enum_type,
        native_enum=False,
        create_constraint=False,
        length=length,
        values_callable=lambda values: [item.value for item in values],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
