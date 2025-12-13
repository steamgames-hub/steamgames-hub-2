"""Add dataset_type to ds_meta_data

Revision ID: 002
Revises: 001
Create Date: 2025-11-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add as nullable to avoid mislabeling existing datasets; application sets it on create
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('ds_meta_data')]
    if 'dataset_type' not in cols:
        op.add_column(
            'ds_meta_data',
            sa.Column('dataset_type', sa.String(length=50), nullable=True)
        )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('ds_meta_data')]
    if 'dataset_type' in cols:
        op.drop_column('ds_meta_data', 'dataset_type')
