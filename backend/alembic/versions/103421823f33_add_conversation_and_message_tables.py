"""Add conversation and message tables

Revision ID: 103421823f33
Revises: b7f6a3e6e9f4
Create Date: 2025-10-13 12:50:55.012593

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = '103421823f33'
down_revision: Union[str, None] = 'b7f6a3e6e9f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    chat_model_default = (settings.CHAT_MODEL or "gpt-4-turbo").replace("'", "''")

    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=128), nullable=False, server_default=sa.text(f"'{chat_model_default}'")),
        sa.Column('temperature', sa.Float(), nullable=False, server_default=sa.text('0.2')),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_index', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)
    op.create_index('ix_messages_conv_idx', 'messages', ['conversation_id', 'message_index'], unique=False)
    op.create_index('ix_messages_conv_created', 'messages', ['conversation_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_messages_request_id'), 'messages', ['request_id'], unique=False)
    op.create_unique_constraint(
        'uq_messages_conversation_index',
        'messages',
        ['conversation_id', 'message_index'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_messages_conversation_index', 'messages', type_='unique')
    op.drop_index(op.f('ix_messages_request_id'), table_name='messages')
    op.drop_index('ix_messages_conv_created', table_name='messages')
    op.drop_index('ix_messages_conv_idx', table_name='messages')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_table('conversations')
