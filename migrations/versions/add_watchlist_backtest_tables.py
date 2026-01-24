"""Add watchlist and backtest tables

Revision ID: add_watchlist_backtest_tables
Revises: add_analysis_results_table
Create Date: 2025-01-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_watchlist_backtest_tables'
down_revision = 'add_analysis_results_table'
branch_labels = None
depends_on = None


def upgrade():
    # AlertType Enum型の作成
    alerttype_enum = postgresql.ENUM(
        'price_above', 'price_below', 'volatility', 'ir_release',
        name='alerttype',
        create_type=False
    )

    # BacktestStatus Enum型の作成
    backteststatus_enum = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed',
        name='backteststatus',
        create_type=False
    )

    # Enum型をデータベースに作成（存在しない場合のみ）
    op.execute("DO $$ BEGIN CREATE TYPE alerttype AS ENUM ('price_above', 'price_below', 'volatility', 'ir_release'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE backteststatus AS ENUM ('pending', 'running', 'completed', 'failed'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    # watchlists テーブルの作成
    op.create_table(
        'watchlists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, server_default='メインウォッチリスト'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_watchlists_user_id'), 'watchlists', ['user_id'], unique=False)

    # watchlist_items テーブルの作成
    op.create_table(
        'watchlist_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('watchlist_id', sa.Integer(), nullable=False),
        sa.Column('ticker_code', sa.String(20), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.Column('target_price_high', sa.Float(), nullable=True),
        sa.Column('target_price_low', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_watchlist_items_watchlist_id'), 'watchlist_items', ['watchlist_id'], unique=False)
    op.create_index(op.f('ix_watchlist_items_ticker_code'), 'watchlist_items', ['ticker_code'], unique=False)

    # price_alerts テーブルの作成
    op.create_table(
        'price_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('watchlist_item_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.Enum('price_above', 'price_below', 'volatility', 'ir_release', name='alerttype'), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('is_triggered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('triggered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['watchlist_item_id'], ['watchlist_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_alerts_watchlist_item_id'), 'price_alerts', ['watchlist_item_id'], unique=False)

    # backtest_jobs テーブルの作成
    op.create_table(
        'backtest_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('start_date', sa.String(10), nullable=False),
        sa.Column('end_date', sa.String(10), nullable=False),
        sa.Column('initial_capital', sa.Float(), nullable=False, server_default='1000000'),
        sa.Column('strategy', sa.String(50), nullable=False),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', name='backteststatus'), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_return', sa.Float(), nullable=True),
        sa.Column('annual_return', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('iris_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_jobs_user_id'), 'backtest_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_backtest_jobs_ticker'), 'backtest_jobs', ['ticker'], unique=False)
    op.create_index(op.f('ix_backtest_jobs_strategy'), 'backtest_jobs', ['strategy'], unique=False)
    op.create_index(op.f('ix_backtest_jobs_status'), 'backtest_jobs', ['status'], unique=False)

    # backtest_templates テーブルの作成
    op.create_table(
        'backtest_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategy', sa.String(50), nullable=False),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_templates_user_id'), 'backtest_templates', ['user_id'], unique=False)


def downgrade():
    # backtest_templates
    op.drop_index(op.f('ix_backtest_templates_user_id'), table_name='backtest_templates')
    op.drop_table('backtest_templates')

    # backtest_jobs
    op.drop_index(op.f('ix_backtest_jobs_status'), table_name='backtest_jobs')
    op.drop_index(op.f('ix_backtest_jobs_strategy'), table_name='backtest_jobs')
    op.drop_index(op.f('ix_backtest_jobs_ticker'), table_name='backtest_jobs')
    op.drop_index(op.f('ix_backtest_jobs_user_id'), table_name='backtest_jobs')
    op.drop_table('backtest_jobs')

    # price_alerts
    op.drop_index(op.f('ix_price_alerts_watchlist_item_id'), table_name='price_alerts')
    op.drop_table('price_alerts')

    # watchlist_items
    op.drop_index(op.f('ix_watchlist_items_ticker_code'), table_name='watchlist_items')
    op.drop_index(op.f('ix_watchlist_items_watchlist_id'), table_name='watchlist_items')
    op.drop_table('watchlist_items')

    # watchlists
    op.drop_index(op.f('ix_watchlists_user_id'), table_name='watchlists')
    op.drop_table('watchlists')

    # Enum型の削除
    op.execute("DROP TYPE IF EXISTS backteststatus")
    op.execute("DROP TYPE IF EXISTS alerttype")
