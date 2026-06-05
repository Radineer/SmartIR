"""Add new PostType enum values for industry, weekly_trend, earnings_calendar

Revision ID: add_posttype_enum_values
Revises: add_post_logs_table
Create Date: 2026-03-09 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_posttype_enum_values'
down_revision = 'add_post_logs_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values to existing posttype enum
    # PostgreSQL requires ALTER TYPE ... ADD VALUE
    op.execute("ALTER TYPE posttype ADD VALUE IF NOT EXISTS 'industry'")
    op.execute("ALTER TYPE posttype ADD VALUE IF NOT EXISTS 'weekly_trend'")
    op.execute("ALTER TYPE posttype ADD VALUE IF NOT EXISTS 'earnings_calendar'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    # The values will remain but won't be used if code is rolled back.
    pass
