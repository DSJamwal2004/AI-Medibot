"""add_pdf_chunk_metadata_to_medical_documents

Revision ID: aedb7e2789ba
Revises: ee105d6033db
Create Date: 2026-01-14 17:13:37.080074

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aedb7e2789ba'
down_revision: Union[str, Sequence[str], None] = 'ee105d6033db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "medical_documents",
        sa.Column("source_file", sa.String(), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "medical_documents",
        sa.Column("chunk_index", sa.Integer(), nullable=True),
    )

    op.create_index(
        "ix_medical_documents_source_file",
        "medical_documents",
        ["source_file"],
    )


def downgrade() -> None:
    op.drop_index("ix_medical_documents_source_file", table_name="medical_documents")

    op.drop_column("medical_documents", "chunk_index")
    op.drop_column("medical_documents", "page_number")
    op.drop_column("medical_documents", "source_file")
