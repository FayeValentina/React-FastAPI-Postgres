"""add language column to knowledge_chunks

Revision ID: 7c2e9e5f3b92
Revises: 3f9a9b1a7a00
Create Date: 2025-01-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c2e9e5f3b92"
down_revision: Union[str, None] = "3f9a9b1a7a00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_chunks",
        sa.Column("language", sa.String(length=16), nullable=True, comment="块语言/类型"),
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "language")
