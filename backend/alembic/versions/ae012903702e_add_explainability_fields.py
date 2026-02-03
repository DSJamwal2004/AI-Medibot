"""add explainability fields

Revision ID: ae012903702e
Revises: c0eefc9e3e42
Create Date: 2026-01-11 00:35:51.518746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae012903702e'
down_revision: Union[str, Sequence[str], None] = 'c0eefc9e3e42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "medical_interactions",
        sa.Column("confidence_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "medical_interactions",
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
    )

    # Backfill
    op.execute(
        "UPDATE medical_interactions SET confidence_score = 0.5 WHERE confidence_score IS NULL"
    )

    # Enforce NOT NULL where required
    op.alter_column(
        "medical_interactions",
        "confidence_score",
        nullable=False,
    )


def downgrade():
    op.drop_column("medical_interactions", "reasoning_summary")
    op.drop_column("medical_interactions", "confidence_score")

