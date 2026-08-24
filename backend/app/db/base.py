from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base reserved for models introduced in later phases."""
