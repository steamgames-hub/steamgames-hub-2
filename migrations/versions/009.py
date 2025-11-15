"""Add two_factor_code to User

Revision ID: 009
Revises: 008
Create Date: 2025-11-08 22:33:23.075205

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('two_factor_code', sa.String(length=6), nullable=True))
    op.add_column('user', sa.Column('two_factor_expires_at', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('two_factor_verified', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('user', 'two_factor_code')
    op.drop_column('user', 'two_factor_expires_at')
    op.drop_column('user', 'two_factor_verified')

