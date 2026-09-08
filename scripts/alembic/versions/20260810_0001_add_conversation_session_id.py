"""add conversation session id for multi-turn memory"""

from alembic import op
import sqlalchemy as sa

revision = "20260810_0001"
down_revision = "20260713_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Day12：问答记录新增 session_id 列，标记多轮会话归属。"""
    with op.batch_alter_table("conversation_records") as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_conversation_records_session_id", ["session_id"], unique=False)


def downgrade() -> None:
    """回滚 Day12 会话标识列。"""
    with op.batch_alter_table("conversation_records") as batch_op:
        batch_op.drop_index("ix_conversation_records_session_id")
        batch_op.drop_column("session_id")
