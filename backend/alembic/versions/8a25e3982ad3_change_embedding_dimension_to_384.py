"""change embedding dimension to 384

Revision ID: 8a25e3982ad3
Revises: 83d5be75250c
Create Date: 2026-01-13
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "8a25e3982ad3"
down_revision = "83d5be75250c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old 1536-dim vector column
    op.drop_column("medical_documents", "embedding")

    # Add new 384-dim vector column
    op.add_column(
        "medical_documents",
        sa.Column("embedding", Vector(384), nullable=True),
    )


def downgrade() -> None:
    # Rollback to 1536-dim vector if ever needed
    op.drop_column("medical_documents", "embedding")

    op.add_column(
        "medical_documents",
        sa.Column("embedding", Vector(1536), nullable=True),
    )

