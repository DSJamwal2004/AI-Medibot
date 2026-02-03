"""add_conversation_phase_and_slots_to_medical_interactions

Revision ID: d8294e62d861
Revises: b03db719df4c
Create Date: 2026-02-01 22:02:37.135707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8294e62d861'
down_revision: Union[str, Sequence[str], None] = 'b03db719df4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "medical_interactions",
        sa.Column("conversation_phase", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "medical_interactions",
        sa.Column("slots_collected", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_medical_interactions_conversation_phase",
        "medical_interactions",
        ["conversation_phase"],
    )


def downgrade():
    op.drop_index(
        "ix_medical_interactions_conversation_phase",
        table_name="medical_interactions",
    )
    op.drop_column("medical_interactions", "slots_collected")
    op.drop_column("medical_interactions", "conversation_phase")

