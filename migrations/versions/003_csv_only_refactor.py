"""
CSV-only refactor: drop dataset_type and rename UVL columns to CSV.

Revision ID: 003_csv_only_refactor
Revises: 002
Create Date: 2025-11-04
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_csv_only_refactor'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Drop dataset_type column from ds_meta_data if exists
    try:
        with op.batch_alter_table('ds_meta_data') as batch_op:
            # MySQL tolerant drop
            batch_op.drop_column('dataset_type')
    except Exception:
        pass

    # Rename uvl_* columns to csv_* in fm_meta_data
    try:
        with op.batch_alter_table('fm_meta_data') as batch_op:
            # Provide existing types for MySQL rename support
            batch_op.alter_column(
                'uvl_filename',
                new_column_name='csv_filename',
                existing_type=sa.String(length=120),
                existing_nullable=False,
            )
    except Exception:
        pass

    try:
        with op.batch_alter_table('fm_meta_data') as batch_op:
            batch_op.alter_column(
                'uvl_version',
                new_column_name='csv_version',
                existing_type=sa.String(length=120),
                existing_nullable=True,
            )
    except Exception:
        pass


def downgrade():
    # Best-effort rollback
    try:
        with op.batch_alter_table('ds_meta_data') as batch_op:
            batch_op.add_column(sa.Column('dataset_type', sa.String(length=50)))
    except Exception:
        pass

    try:
        with op.batch_alter_table('fm_meta_data') as batch_op:
            batch_op.alter_column(
                'csv_filename',
                new_column_name='uvl_filename',
                existing_type=sa.String(length=120),
                existing_nullable=False,
            )
    except Exception:
        pass

    try:
        with op.batch_alter_table('fm_meta_data') as batch_op:
            batch_op.alter_column(
                'csv_version',
                new_column_name='uvl_version',
                existing_type=sa.String(length=120),
                existing_nullable=True,
            )
    except Exception:
        pass
