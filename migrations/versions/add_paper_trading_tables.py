"""Add paper trading tables for AI Trading Challenge

Revision ID: add_paper_trading_tables
Revises: add_broadcast_jobs_table
Create Date: 2026-03-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_paper_trading_tables'
down_revision = 'add_broadcast_jobs_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend posttype enum
    op.execute("ALTER TYPE posttype ADD VALUE IF NOT EXISTS 'trading_challenge'")

    # paper_positions
    op.create_table(
        'paper_positions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(20), nullable=False, index=True),
        sa.Column('company_name', sa.String(200), nullable=True),
        sa.Column('shares', sa.Float(), nullable=False),
        sa.Column('avg_cost', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('sector', sa.String(50), nullable=True),
        sa.Column('signal_source', sa.String(50), nullable=True),
        sa.Column('opened_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('peak_price', sa.Float(), nullable=True),
        sa.Column('metadata', JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # paper_trades
    op.create_table(
        'paper_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(20), nullable=False, index=True),
        sa.Column('company_name', sa.String(200), nullable=True),
        sa.Column('side', sa.String(4), nullable=False),
        sa.Column('shares', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('cost', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('signal_source', sa.String(50), nullable=True),
        sa.Column('signal_strength', sa.Float(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('metadata', JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_paper_trades_executed_at', 'paper_trades', ['executed_at'])

    # paper_portfolio_snapshots
    op.create_table(
        'paper_portfolio_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('snapshot_date', sa.String(10), nullable=False, unique=True, index=True),
        sa.Column('cash', sa.Float(), nullable=False),
        sa.Column('positions_value', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_nav', sa.Float(), nullable=False),
        sa.Column('daily_return_pct', sa.Float(), nullable=True),
        sa.Column('cumulative_return_pct', sa.Float(), nullable=True),
        sa.Column('max_drawdown_pct', sa.Float(), nullable=True),
        sa.Column('num_positions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positions_detail', JSONB(), server_default='[]'),
        sa.Column('trades_today', JSONB(), server_default='[]'),
        sa.Column('metadata', JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('paper_portfolio_snapshots')
    op.drop_index('ix_paper_trades_executed_at', table_name='paper_trades')
    op.drop_table('paper_trades')
    op.drop_table('paper_positions')
