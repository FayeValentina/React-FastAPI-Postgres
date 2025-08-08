"""Create task_configs table only

Revision ID: 41786af6649e
Revises: 45d401fd94c3
Create Date: 2025-08-08 12:46:36.739942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41786af6649e'
down_revision: Union[str, None] = 'cf33855d28e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建task_configs表
    from sqlalchemy.dialects import postgresql
    
    op.create_table('task_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('task_type', sa.Enum('BOT_SCRAPING', 'MANUAL_SCRAPING', 'BATCH_SCRAPING', 'CLEANUP_SESSIONS', 'CLEANUP_TOKENS', 'CLEANUP_CONTENT', 'CLEANUP_EVENTS', 'SEND_EMAIL', 'SEND_NOTIFICATION', 'DATA_EXPORT', 'DATA_BACKUP', 'DATA_ANALYSIS', 'HEALTH_CHECK', 'SYSTEM_MONITOR', 'LOG_ROTATION', name='tasktype'), nullable=False),
    sa.Column('scheduler_type', sa.Enum('INTERVAL', 'CRON', 'DATE', 'MANUAL', name='schedulertype'), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', 'PAUSED', 'ERROR', name='taskstatus'), nullable=False),
    sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('schedule_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('max_retries', sa.Integer(), nullable=False),
    sa.Column('timeout_seconds', sa.Integer(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_configs_id'), 'task_configs', ['id'], unique=False)
    op.create_index(op.f('ix_task_configs_name'), 'task_configs', ['name'], unique=False)
    op.create_index(op.f('ix_task_configs_status'), 'task_configs', ['status'], unique=False)
    op.create_index(op.f('ix_task_configs_task_type'), 'task_configs', ['task_type'], unique=False)


def downgrade() -> None:
    # 删除task_configs表及其索引
    op.drop_index(op.f('ix_task_configs_task_type'), table_name='task_configs')
    op.drop_index(op.f('ix_task_configs_status'), table_name='task_configs')
    op.drop_index(op.f('ix_task_configs_name'), table_name='task_configs')
    op.drop_index(op.f('ix_task_configs_id'), table_name='task_configs')
    op.drop_table('task_configs')
