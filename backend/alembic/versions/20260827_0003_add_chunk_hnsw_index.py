"""Add the BE-6 cosine HNSW index.

Revision ID: 20260827_0003
Revises: 20260824_0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260827_0003"
down_revision: str | None = "20260824_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_document_chunks_embedding_hnsw_cosine",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_chunks_embedding_hnsw_cosine",
        table_name="document_chunks",
        postgresql_using="hnsw",
    )
