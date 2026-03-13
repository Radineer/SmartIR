"""Expand analysis_results and add prediction_logs table

Revision ID: expand_analysis_add_predictions
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'expand_analysis_add_predictions'
down_revision = 'add_posttype_enum_values'
branch_labels = None
depends_on = None


def upgrade():
    # analysis_results に新カラム追加
    op.add_column('analysis_results', sa.Column('analysis_depth', sa.String(20), nullable=True))
    op.add_column('analysis_results', sa.Column('llm_model', sa.String(100), nullable=True))
    op.add_column('analysis_results', sa.Column('processing_time_sec', sa.Float(), nullable=True))
    op.add_column('analysis_results', sa.Column('financial_metrics', sa.JSON(), nullable=True))
    op.add_column('analysis_results', sa.Column('guidance_revision', sa.String(20), nullable=True))
    op.add_column('analysis_results', sa.Column('guidance_detail', sa.JSON(), nullable=True))
    op.add_column('analysis_results', sa.Column('segments', sa.JSON(), nullable=True))
    op.add_column('analysis_results', sa.Column('risk_factors', sa.JSON(), nullable=True))
    op.add_column('analysis_results', sa.Column('growth_drivers', sa.JSON(), nullable=True))
    op.add_column('analysis_results', sa.Column('stock_impact_prediction', sa.String(20), nullable=True))
    op.add_column('analysis_results', sa.Column('stock_impact_confidence', sa.Float(), nullable=True))
    op.add_column('analysis_results', sa.Column('stock_impact_reasoning', sa.Text(), nullable=True))
    op.add_column('analysis_results', sa.Column('extracted_tables', sa.JSON(), nullable=True))

    # prediction_logs テーブル作成
    op.create_table(
        'prediction_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('predicted_impact', sa.String(20), nullable=False),
        sa.Column('predicted_confidence', sa.Float(), nullable=True),
        sa.Column('predicted_reasoning', sa.String(500), nullable=True),
        sa.Column('analysis_depth', sa.String(20), nullable=True),
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('predicted_at', sa.DateTime(), nullable=True),
        sa.Column('actual_price_change_pct', sa.Float(), nullable=True),
        sa.Column('actual_direction', sa.String(20), nullable=True),
        sa.Column('was_correct', sa.Boolean(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['analysis_results.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prediction_logs_analysis_id', 'prediction_logs', ['analysis_id'])
    op.create_index('ix_prediction_logs_company_id', 'prediction_logs', ['company_id'])
    op.create_index('ix_prediction_logs_was_correct', 'prediction_logs', ['was_correct'])


def downgrade():
    op.drop_index('ix_prediction_logs_was_correct', table_name='prediction_logs')
    op.drop_index('ix_prediction_logs_company_id', table_name='prediction_logs')
    op.drop_index('ix_prediction_logs_analysis_id', table_name='prediction_logs')
    op.drop_table('prediction_logs')

    op.drop_column('analysis_results', 'extracted_tables')
    op.drop_column('analysis_results', 'stock_impact_reasoning')
    op.drop_column('analysis_results', 'stock_impact_confidence')
    op.drop_column('analysis_results', 'stock_impact_prediction')
    op.drop_column('analysis_results', 'growth_drivers')
    op.drop_column('analysis_results', 'risk_factors')
    op.drop_column('analysis_results', 'segments')
    op.drop_column('analysis_results', 'guidance_detail')
    op.drop_column('analysis_results', 'guidance_revision')
    op.drop_column('analysis_results', 'financial_metrics')
    op.drop_column('analysis_results', 'processing_time_sec')
    op.drop_column('analysis_results', 'llm_model')
    op.drop_column('analysis_results', 'analysis_depth')
