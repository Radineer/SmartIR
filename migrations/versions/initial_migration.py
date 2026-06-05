"""Initial migration

Revision ID: initial_migration
Create Date: 2024-01-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'initial_migration'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # companies テーブルの作成
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('ticker_code', sa.String(length=10), nullable=False),
        sa.Column('sector', sa.String(length=100)),
        sa.Column('industry', sa.String(length=100)),
        sa.Column('description', sa.Text()),
        sa.Column('website_url', sa.String(length=255)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=False)
    op.create_index(op.f('ix_companies_ticker_code'), 'companies', ['ticker_code'], unique=True)

    # documents テーブルの作成
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('doc_type', sa.Enum('FINANCIAL_REPORT', 'ANNUAL_REPORT', 'PRESS_RELEASE', 'PRESENTATION', 'OTHER', name='documenttype'), nullable=False),
        sa.Column('publish_date', sa.String(length=10), nullable=False),
        sa.Column('source_url', sa.String(length=512), nullable=False),
        sa.Column('storage_url', sa.String(length=512)),
        sa.Column('is_processed', sa.Boolean(), default=False),
        sa.Column('raw_text', sa.Text()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_publish_date'), 'documents', ['publish_date'], unique=False)

def downgrade():
    op.drop_table('documents')
    op.drop_table('companies') 