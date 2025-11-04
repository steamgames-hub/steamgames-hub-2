"""add dataset_type to data_set and create game_data

Revision ID: 002
Revises: 001
Create Date: 2025-10-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add dataset_type enum column to data_set
    dataset_type_enum = sa.Enum('UVL', 'GAME', name='datasettype')
    dataset_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'data_set',
        sa.Column('dataset_type', dataset_type_enum, nullable=False, server_default='UVL')
    )
    # Optionally remove server_default after setting existing rows
    with op.batch_alter_table('data_set') as batch_op:
        batch_op.alter_column('dataset_type', server_default=None)

    # Create game_data table
    op.create_table(
        'game_data',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('data_set_id', sa.Integer(), sa.ForeignKey('data_set.id'), nullable=False, unique=True),
        sa.Column('game_name', sa.String(length=200), nullable=False),
        sa.Column('release_date', sa.String(length=50), nullable=True),
        sa.Column('developer', sa.String(length=200), nullable=True),
        sa.Column('publisher', sa.String(length=200), nullable=True),
        sa.Column('platforms', sa.String(length=200), nullable=True),
        sa.Column('required_age', sa.String(length=10), nullable=True),
        sa.Column('categories', sa.Text(), nullable=True),
        sa.Column('genres', sa.Text(), nullable=True),
    )


def downgrade():
    # Drop game_data table
    op.drop_table('game_data')

    # Drop dataset_type column (keep enum type for compatibility across engines)
    with op.batch_alter_table('data_set') as batch_op:
        batch_op.drop_column('dataset_type')
