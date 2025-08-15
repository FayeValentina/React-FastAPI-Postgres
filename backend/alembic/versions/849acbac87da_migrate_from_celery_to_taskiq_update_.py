"""Migrate from worker to TaskIQ - update task_executions table

Revision ID: 849acbac87da
Revises: 8e09b05f22bc
Create Date: 2025-08-14 02:43:17.894424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '849acbac87da'
down_revision: Union[str, None] = '8e09b05f22bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove old worker-related tables if they exist
    op.drop_table('apscheduler_jobs', if_exists=True)
    op.drop_table('worker_taskmeta', if_exists=True)
    op.drop_table('worker_tasksetmeta', if_exists=True)
    
    # Update task_executions table for TaskIQ
    # Remove old worker columns
    op.drop_column('task_executions', 'job_name', if_exists=True)
    
    # Rename job_id to task_id if it exists, otherwise add task_id
    try:
        # Try to rename column if it exists
        op.alter_column('task_executions', 'job_id', new_column_name='task_id')
    except:
        # If job_id doesn't exist, drop it and add task_id
        try:
            op.drop_column('task_executions', 'job_id')
        except:
            pass
        op.add_column('task_executions', sa.Column('task_id', sa.String(), nullable=False, index=True))


def downgrade() -> None:
    # Note: Downgrade not fully supported for this migration
    # as it represents a major architectural change
    pass
