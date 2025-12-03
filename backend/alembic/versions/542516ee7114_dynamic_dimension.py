"""Adjust knowledge chunk embedding dimension."""

from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "542516ee7114"
down_revision: Union[str, None] = "103421823f33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _target_dim(default: int) -> int:
    """Get the desired vector dimension from env, with a safe default."""
    raw = os.getenv("EMBEDDING_DIM")
    try:
        return int(raw) if raw else default
    except (TypeError, ValueError):
        return default


def upgrade() -> None:
    # NOTE: altering pgvector column dims requires dropping dependent indexes first.
    new_dim = _target_dim(768)
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding")
    op.execute(sa.text(f"ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector({new_dim})"))
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    old_dim = 768
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding")
    op.execute(sa.text(f"ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector({old_dim})"))
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
