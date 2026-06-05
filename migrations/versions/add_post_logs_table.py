"""Add post_logs table for note.com and X publishing

Revision ID: add_post_logs_table
Revises: add_watchlist_backtest_tables
Create Date: 2026-03-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_post_logs_table'
down_revision = 'add_watchlist_backtest_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types via raw SQL (idempotent)
    op.execute("DO $$ BEGIN CREATE TYPE postplatform AS ENUM ('note', 'twitter'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE posttype AS ENUM ('breaking', 'analysis', 'daily', 'weekly'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    op.create_table(
        'post_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('platform', sa.String(50), nullable=False, index=True),
        sa.Column('post_type', sa.String(50), nullable=False, index=True),
        sa.Column('external_id', sa.String(500), nullable=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True),
        sa.Column('content_preview', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index('ix_post_logs_document_id', 'post_logs', ['document_id'])
    op.create_index('ix_post_logs_posted_at', 'post_logs', ['posted_at'])


def downgrade() -> None:
    op.drop_table('post_logs')

    postplatform = sa.Enum('note', 'twitter', name='postplatform')
    posttype = sa.Enum('breaking', 'analysis', 'daily', 'weekly', name='posttype')
    postplatform.drop(op.get_bind(), checkfirst=True)
    posttype.drop(op.get_bind(), checkfirst=True)
