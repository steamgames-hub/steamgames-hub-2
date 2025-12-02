"""add download_count to Hubfile model

Revision ID: 008_b
Revises: 008_a
Create Date: 2025-11-09 22:24:28.929301

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_b'
down_revision = '008_a'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna download_count a la tabla file (Hubfile)
    op.add_column(
        'file',
        sa.Column(
            'download_count',
            sa.Integer(),
            nullable=False,
            server_default='0'  # Asegura que los registros existentes tengan valor 0
        )
    )
    # Quitar el server_default después de poblar registros existentes (opcional)
    op.alter_column('file', 'download_count', server_default=None)


def downgrade():
    # Eliminar columna download_count
    op.drop_column('file', 'download_count')