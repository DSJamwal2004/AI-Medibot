"""evolve medical_interactions for explainable audit

Revision ID: c98a5e4aee32
Revises: aedb7e2789ba
Create Date: 2026-01-14 23:55:56.597660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c98a5e4aee32'
down_revision: Union[str, Sequence[str], None] = 'aedb7e2789ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # -----------------------------
    # 1. Add new columns
    # -----------------------------

    op.add_column(
        "medical_interactions",
        sa.Column(
            "chat_message_id",
            sa.Integer(),
            nullable=True,  # temporary, will enforce later
        ),
    )

    op.add_column(
        "medical_interactions",
        sa.Column(
            "risk_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "medical_interactions",
        sa.Column(
            "risk_trigger",
            sa.String(),
            nullable=True,
        ),
    )

    op.add_column(
        "medical_interactions",
        sa.Column(
            "primary_domain",
            sa.String(),
            nullable=True,
        ),
    )

    op.add_column(
        "medical_interactions",
        sa.Column(
            "all_domains",
            sa.JSON(),
            nullable=True,
        ),
    )

    # -----------------------------
    # 2. Foreign key to chat_message
    # -----------------------------

    op.create_foreign_key(
        "fk_medical_interactions_chat_message",
        "medical_interactions",
        "chat_messages",  # ✅ CORRECT (plural)
        ["chat_message_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # -----------------------------
    # 3. Remove duplicated text columns
    # -----------------------------

    op.drop_column("medical_interactions", "user_message")
    op.drop_column("medical_interactions", "ai_response")

    # -----------------------------
    # 4. Add unique constraint
    # -----------------------------

    op.create_unique_constraint(
        "uq_medical_interactions_chat_message",
        "medical_interactions",
        ["chat_message_id"],
    )


def downgrade():
    # -----------------------------
    # Reverse operations
    # -----------------------------

    op.drop_constraint(
        "uq_medical_interactions_chat_message",
        "medical_interactions",
        type_="unique",
    )

    op.drop_constraint(
        "fk_medical_interactions_chat_message",
        "medical_interactions",
        type_="foreignkey",
    )

    op.drop_column("medical_interactions", "all_domains")
    op.drop_column("medical_interactions", "primary_domain")
    op.drop_column("medical_interactions", "risk_trigger")
    op.drop_column("medical_interactions", "risk_reason")
    op.drop_column("medical_interactions", "chat_message_id")

    op.add_column(
        "medical_interactions",
        sa.Column("user_message", sa.Text(), nullable=False),
    )

    op.add_column(
        "medical_interactions",
        sa.Column("ai_response", sa.Text(), nullable=False),
    )
