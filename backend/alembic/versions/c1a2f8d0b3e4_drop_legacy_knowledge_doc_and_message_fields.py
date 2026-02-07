"""drop legacy knowledge document fields and messages.updated_at

Revision ID: c1a2f8d0b3e4
Revises: 542516ee7114
Create Date: 2026-02-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c1a2f8d0b3e4"
down_revision: Union[str, None] = "542516ee7114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("knowledge_documents", "language")
    op.drop_column("knowledge_documents", "mime")
    op.drop_column("knowledge_documents", "checksum")
    op.drop_column("knowledge_documents", "meta")
    op.drop_column("messages", "updated_at")


def downgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="自定义元数据"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("checksum", sa.String(length=128), nullable=True, comment="文件校验和"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("mime", sa.String(length=128), nullable=True, comment="MIME 类型"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("language", sa.String(length=16), nullable=True, comment="文档语言"),
    )
