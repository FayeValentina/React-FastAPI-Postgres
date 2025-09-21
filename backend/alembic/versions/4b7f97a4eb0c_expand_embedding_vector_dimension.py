"""expand embedding vector dimension to 768

Revision ID: 4b7f97a4eb0c
Revises: 7c2e9e5f3b92
Create Date: 2025-01-10 12:00:00.000000
"""

from typing import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4b7f97a4eb0c"
down_revision: str | None = "7c2e9e5f3b92"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(768)")


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(384)")
