"""add_metadata_fields_to_medical_documents

Revision ID: ee105d6033db
Revises: 8a25e3982ad3
Create Date: 2026-01-14 15:29:58.398394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee105d6033db'
down_revision: Union[str, Sequence[str], None] = '8a25e3982ad3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "medical_documents",
        sa.Column("medical_domain", sa.String(), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("content_type", sa.String(), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("authority_level", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("is_emergency", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("published_by", sa.String(), nullable=True),
    )

    # Optional but recommended indexes
    op.create_index(
        "ix_medical_documents_domain",
        "medical_documents",
        ["medical_domain"],
    )
    op.create_index(
        "ix_medical_documents_emergency",
        "medical_documents",
        ["is_emergency"],
    )


def downgrade() -> None:
    op.drop_index("ix_medical_documents_emergency", table_name="medical_documents")
    op.drop_index("ix_medical_documents_domain", table_name="medical_documents")

    op.drop_column("medical_documents", "published_by")
    op.drop_column("medical_documents", "is_emergency")
    op.drop_column("medical_documents", "authority_level")
    op.drop_column("medical_documents", "content_type")
    op.drop_column("medical_documents", "medical_domain")
