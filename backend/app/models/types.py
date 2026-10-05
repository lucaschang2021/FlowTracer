"""Shared SQLAlchemy column-type helpers for ORM models.

Extracted from ``entities.py`` so model modules added after the architecture budget
was frozen (for example ``notification.py`` and ``opportunity.py``) can reuse them
without growing the baseline module.
"""

from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import Enum


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
