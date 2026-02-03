"""add metadata to chat_messages

Revision ID: b03db719df4c
Revises: c98a5e4aee32
Create Date: 2026-01-16 11:48:05.488681

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b03db719df4c'
down_revision: Union[str, Sequence[str], None] = 'c98a5e4aee32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("chat_messages", sa.Column("meta", sa.JSON(), nullable=True))

def downgrade():
    op.drop_column("chat_messages", "meta")

