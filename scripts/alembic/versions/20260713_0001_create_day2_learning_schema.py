"""create day2 learning schema"""

from alembic import op
import sqlalchemy as sa

revision = "20260713_0001"
down_revision = None
branch_labels = None
depends_on = None

knowledge_base_status_enum = sa.Enum("ACTIVE", "DISABLED", name="knowledgebasestatus")
document_parse_status_enum = sa.Enum("PENDING", "SUCCESS", "FAILED", name="documentparsestatus")
conversation_record_status_enum = sa.Enum(
    "GENERATED",
    "FAILED",
    name="conversationrecordstatus",
)


def upgrade() -> None:
    """创建 Day2 练习所需的全部核心表。"""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", knowledge_base_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"], unique=False)
    op.create_index("ix_knowledge_bases_name", "knowledge_bases", ["name"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_md5", sa.String(length=32), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parse_status", document_parse_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"], unique=False)
    op.create_index("ix_documents_file_md5", "documents", ["file_md5"], unique=False)

    op.create_table(
        "conversation_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("source_document_ids", sa.String(length=255), nullable=True),
        sa.Column("status", conversation_record_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_conversation_records_knowledge_base_id",
        "conversation_records",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index("ix_conversation_records_user_id", "conversation_records", ["user_id"], unique=False)


def downgrade() -> None:
    """按依赖反向删除 Day2 练习表结构。"""
    op.drop_index("ix_conversation_records_user_id", table_name="conversation_records")
    op.drop_index("ix_conversation_records_knowledge_base_id", table_name="conversation_records")
    op.drop_table("conversation_records")

    op.drop_index("ix_documents_file_md5", table_name="documents")
    op.drop_index("ix_documents_knowledge_base_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_knowledge_bases_name", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_owner_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    conversation_record_status_enum.drop(op.get_bind(), checkfirst=False)
    document_parse_status_enum.drop(op.get_bind(), checkfirst=False)
    knowledge_base_status_enum.drop(op.get_bind(), checkfirst=False)
