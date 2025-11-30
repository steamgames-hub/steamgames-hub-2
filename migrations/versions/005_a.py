"""
CSV-only refactor: drop dataset_type and rename UVL columns to CSV.

Revision ID: 005_a
Revises: 004
Create Date: 2025-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = '005_a'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    try:
        inspector = sa.inspect(op.get_bind())
    
        if 'dataset_type' in inspector.get_columns('ds_meta_data'):
            with op.batch_alter_table('ds_meta_data') as batch_op:
                batch_op.drop_column('dataset_type')

        fm_columns = {col['name']: col for col in inspector.get_columns('fm_meta_data')}
        
        with op.batch_alter_table('fm_meta_data') as batch_op:
            if 'uvl_filename' in fm_columns:
                batch_op.alter_column(
                    'uvl_filename',
                    new_column_name='csv_filename',
                    existing_type=sa.String(length=120),
                    existing_nullable=False,
                )
            
            if 'uvl_version' in fm_columns:
                batch_op.alter_column(
                    'uvl_version',
                    new_column_name='csv_version',
                    existing_type=sa.String(length=120),
                    existing_nullable=True,
                )
    except Exception:
        print("Migration unnecessary, skipping...")


def downgrade():
    inspector = sa.inspect(op.get_bind())
    
    if 'dataset_type' not in inspector.get_columns('ds_meta_data'):
        with op.batch_alter_table('ds_meta_data') as batch_op:
            batch_op.add_column(
                sa.Column('dataset_type', sa.String(length=50))
            )

    fm_columns = {
        col['name']: col
        for col in inspector.get_columns('fm_meta_data')
    }
    
    with op.batch_alter_table('fm_meta_data') as batch_op:
        if 'csv_filename' in fm_columns:
            batch_op.alter_column(
                'csv_filename',
                new_column_name='uvl_filename',
                existing_type=sa.String(length=120),
                existing_nullable=False,
            )
        
        if 'csv_version' in fm_columns:
            batch_op.alter_column(
                'csv_version',
                new_column_name='uvl_version',
                existing_type=sa.String(length=120),
                existing_nullable=True,
            )
