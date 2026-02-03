"""add embedding vector to medical_documents

Revision ID: 83d5be75250c
Revises: fb254c1dcf59
Create Date: 2026-01-13 22:16:49.394078

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '83d5be75250c'
down_revision: Union[str, Sequence[str], None] = 'fb254c1dcf59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "medical_documents",
        sa.Column("embedding", Vector(1536), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("medical_documents", "embedding")

