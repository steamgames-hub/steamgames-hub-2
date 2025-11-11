"""create issue table

Revision ID: 007
Revises: 006
Create Date: 2025-11-09 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # create issue table
    try:
        op.create_table(
            'issue',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('dataset_id', sa.Integer(), nullable=False),
            sa.Column('reporter_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('is_open', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['dataset_id'], ['data_set.id'], ),
            sa.ForeignKeyConstraint(['reporter_id'], ['user.id'], ),
        )
    except Exception:
        print("Migration unnecessary, skipping...")


def downgrade():
    op.drop_table('issue')
