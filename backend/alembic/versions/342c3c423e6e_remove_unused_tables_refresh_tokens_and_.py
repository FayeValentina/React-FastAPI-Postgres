"""remove_unused_tables_refresh_tokens_and_schedule_events

Revision ID: 342c3c423e6e
Revises: c189053a4eaa
Create Date: 2025-08-18 12:00:36.267474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '342c3c423e6e'
down_revision: Union[str, None] = 'c189053a4eaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除 refresh_tokens 表 (已迁移到Redis)
    op.drop_table('refresh_tokens')
    
    # 删除 schedule_events 表 (已迁移到Redis)
    op.drop_table('schedule_events')


def downgrade() -> None:
    # 如果需要回滚，重新创建这些表的基本结构
    # 注意：这只是基本结构，不会恢复数据
    
    # 重新创建 refresh_tokens 表
    op.create_table('refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
    )
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'])
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    
    # 重新创建 schedule_events 表
    op.create_table('schedule_events',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('config_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_schedule_events_config_id', 'schedule_events', ['config_id'])
    op.create_index('ix_schedule_events_event_type', 'schedule_events', ['event_type'])
