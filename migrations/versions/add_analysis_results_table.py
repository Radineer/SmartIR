"""Add analysis_results table

Revision ID: add_analysis_results_table
Create Date: 2025-01-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_analysis_results_table'
down_revision = 'add_users_table'
branch_labels = None
depends_on = None


def upgrade():
    # analysis_results テーブルの作成
    op.create_table(
        'analysis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('sentiment_positive', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sentiment_negative', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sentiment_neutral', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('key_points', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analysis_results_document_id'), 'analysis_results', ['document_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_analysis_results_document_id'), table_name='analysis_results')
    op.drop_table('analysis_results')
