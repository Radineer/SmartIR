"""Add broadcast_jobs table and extend platform/post type enums

Revision ID: add_broadcast_jobs_table
Revises: add_posttype_enum_values
Create Date: 2026-03-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_broadcast_jobs_table'
down_revision = 'expand_analysis_add_predictions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend postplatform enum with new values
    op.execute("ALTER TYPE postplatform ADD VALUE IF NOT EXISTS 'tiktok'")
    op.execute("ALTER TYPE postplatform ADD VALUE IF NOT EXISTS 'instagram'")
    op.execute("ALTER TYPE postplatform ADD VALUE IF NOT EXISTS 'youtube'")

    # Extend posttype enum with video
    op.execute("ALTER TYPE posttype ADD VALUE IF NOT EXISTS 'video'")

    # Create broadcast_status enum via raw SQL (idempotent)
    op.execute("DO $$ BEGIN CREATE TYPE broadcaststatus AS ENUM ('pending', 'scheduled', 'generating', 'uploading', 'completed', 'failed', 'cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    op.create_table(
        'broadcast_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=True, index=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', JSONB(), nullable=True),
        sa.Column('privacy_status', sa.String(20), server_default='unlisted'),
        sa.Column('publish_time', sa.DateTime(), nullable=True),
        sa.Column('video_path', sa.String(512), nullable=True),
        sa.Column('thumbnail_path', sa.String(512), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False, index=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('video_id', sa.String(50), nullable=True),
        sa.Column('video_url', sa.String(512), nullable=True),
        sa.Column('result', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('broadcast_jobs')
    op.execute("DROP TYPE IF EXISTS broadcaststatus")
