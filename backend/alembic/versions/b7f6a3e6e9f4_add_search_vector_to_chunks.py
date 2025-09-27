"""add search_vector column for BM25 support

Revision ID: b7f6a3e6e9f4
Revises: 7c2e9e5f3b92
Create Date: 2025-02-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7f6a3e6e9f4"
down_revision: Union[str, None] = "4b7f97a4eb0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;")
    op.add_column(
        "knowledge_chunks",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.execute(
        "UPDATE knowledge_chunks SET search_vector = to_tsvector('simple', content)"
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_search_vector", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "search_vector")
