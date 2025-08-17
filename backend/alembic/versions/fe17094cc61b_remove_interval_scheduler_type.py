"""remove_interval_scheduler_type

Revision ID: fe17094cc61b
Revises: 4a0ccb782e4e
Create Date: 2025-08-16 14:41:39.062128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe17094cc61b'
down_revision: Union[str, None] = '4a0ccb782e4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Update all INTERVAL records to CRON
    # First, update the task_configs that use INTERVAL to CRON
    op.execute("""
        UPDATE task_configs 
        SET scheduler_type = 'CRON'
        WHERE scheduler_type = 'INTERVAL'
    """)
    
    # Step 2: Update any schedule_config that might need modification for CRON format
    # Convert interval-based schedule_config to CRON format
    op.execute("""
        UPDATE task_configs 
        SET schedule_config = '{"cron_expression": "*/5 * * * *"}'
        WHERE scheduler_type = 'CRON' 
        AND (schedule_config ? 'minutes' OR schedule_config ? 'hours' OR schedule_config ? 'seconds')
        AND NOT (schedule_config ? 'cron_expression' OR schedule_config ? 'minute')
    """)
    
    # Step 3: Recreate the enum without INTERVAL
    # Create new enum type
    op.execute("CREATE TYPE schedulertype_new AS ENUM ('CRON', 'DATE', 'MANUAL')")
    
    # Update the column to use the new enum
    op.execute("""
        ALTER TABLE task_configs 
        ALTER COLUMN scheduler_type TYPE schedulertype_new 
        USING scheduler_type::text::schedulertype_new
    """)
    
    # Drop the old enum and rename the new one
    op.execute("DROP TYPE schedulertype")
    op.execute("ALTER TYPE schedulertype_new RENAME TO schedulertype")


def downgrade() -> None:
    # Recreate the enum with INTERVAL
    op.execute("CREATE TYPE schedulertype_new AS ENUM ('INTERVAL', 'CRON', 'DATE', 'MANUAL')")
    
    # Update the column to use the new enum
    op.execute("""
        ALTER TABLE task_configs 
        ALTER COLUMN scheduler_type TYPE schedulertype_new 
        USING scheduler_type::text::schedulertype_new
    """)
    
    # Drop the old enum and rename the new one
    op.execute("DROP TYPE schedulertype")
    op.execute("ALTER TYPE schedulertype_new RENAME TO schedulertype")
