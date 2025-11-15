"""Add communities and dataset proposals

Revision ID: 011
Revises: 010
Create Date: 2025-11-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'community',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('icon_path', sa.String(length=255), nullable=True),
        sa.Column('responsible_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['responsible_user_id'], ['user.id']),
    )

    op.create_table(
        'community_dataset_proposal',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=False),
        sa.Column('proposed_by_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['dataset_id'], ['data_set.id']),
        sa.ForeignKeyConstraint(['community_id'], ['community.id']),
        sa.ForeignKeyConstraint(['proposed_by_user_id'], ['user.id']),
        sa.UniqueConstraint('dataset_id', 'community_id', name='uq_dataset_community'),
    )


def downgrade():
    op.drop_table('community_dataset_proposal')
    op.drop_table('community')
