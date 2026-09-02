"""Fix indexes to match the target schema."""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0004"
down_revision = "20260823_0003"
branch_labels = None
depends_on = None


def _index_info(table: str, name: str):
    return next(
        (item for item in sa.inspect(op.get_bind()).get_indexes(table) if item["name"] == name),
        None,
    )


def upgrade() -> None:
    if _index_info("knowledge_bases", "ix_knowledge_bases_deleted_at") is None:
        op.create_index("ix_knowledge_bases_deleted_at", "knowledge_bases", ["deleted_at"])

    index = _index_info("documents", "ix_documents_file_id")
    if index is not None:
        op.drop_index("ix_documents_file_id", table_name="documents")
    op.create_index("ix_documents_file_id", "documents", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_file_id", table_name="documents")
    op.create_index("ix_documents_file_id", "documents", ["file_id"], unique=True)
    op.drop_index("ix_knowledge_bases_deleted_at", table_name="knowledge_bases")
