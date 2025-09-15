"""add knowledge tables (documents + chunks)

Revision ID: 3f9a9b1a7a00
Revises: ff407dfb6bcd
Create Date: 2025-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '3f9a9b1a7a00'
down_revision: Union[str, None] = 'ff407dfb6bcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 启用 pgvector 扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 文档表
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_type', sa.String(length=32), nullable=True, comment='来源类型'),
        sa.Column('source_ref', sa.String(length=1024), nullable=True, comment='来源引用（URL/路径/外部ID/批次ID）'),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('language', sa.String(length=16), nullable=True),
        sa.Column('mime', sa.String(length=128), nullable=True),
        sa.Column('checksum', sa.String(length=128), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_by', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # 知识块表（引用文档表，级联删除）
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=True, comment='文档内块序'),
        sa.Column('content', sa.Text(), nullable=False, comment='文本内容'),
        sa.Column('embedding', Vector(dim=384), nullable=False, comment='向量表示'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    op.create_index('ix_knowledge_chunks_document_id', 'knowledge_chunks', ['document_id'])
    op.create_index('ix_knowledge_chunks_doc_chunk', 'knowledge_chunks', ['document_id', 'chunk_index'])

    # 余弦相似度的 IVFFlat 索引
    op.create_index(
        'ix_knowledge_chunks_embedding',
        'knowledge_chunks',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )

    # 更新统计信息
    op.execute("ANALYZE knowledge_chunks;")


def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_embedding', table_name='knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_doc_chunk', table_name='knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_document_id', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_documents')
    op.execute("DROP EXTENSION IF EXISTS vector;")
