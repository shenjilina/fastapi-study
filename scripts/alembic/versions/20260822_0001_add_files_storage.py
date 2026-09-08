"""Add persistent files table and document file relation."""

from alembic import op
import sqlalchemy as sa

revision = "20260822_0001"
down_revision = "20260810_0001"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return any(item["name"] == column for item in sa.inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    if not _has_table("files"):
        op.create_table(
            "files",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("stored_filename", sa.String(length=255), nullable=False, unique=True),
            sa.Column("storage_path", sa.Text(), nullable=False),
            sa.Column("file_type", sa.String(length=20), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("file_md5", sa.String(length=32), nullable=False),
            sa.Column(
                "status",
                sa.Enum("uploaded", "bound", "deleted", "failed", name="filestatus"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"
            ),
        )
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("files")}
    for name, column in (
        ("ix_files_owner_id", "owner_id"),
        ("ix_files_knowledge_base_id", "knowledge_base_id"),
        ("ix_files_file_md5", "file_md5"),
    ):
        if name not in indexes:
            op.create_index(name, "files", [column])

    if not _has_column("documents", "file_id"):
        op.add_column("documents", sa.Column("file_id", sa.Integer(), nullable=True))
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("documents")}
    if "ix_documents_file_id" not in indexes:
        op.create_index("ix_documents_file_id", "documents", ["file_id"], unique=True)

    # SQLite requires table recreation to add a foreign-key constraint.
    with op.batch_alter_table("documents", recreate="always") as batch:
        constraints = sa.inspect(op.get_bind()).get_foreign_keys("documents")
        if not any(item.get("name") == "fk_documents_file_id" for item in constraints):
            batch.create_foreign_key(
                "fk_documents_file_id", "files", ["file_id"], ["id"], ondelete="CASCADE"
            )


def downgrade() -> None:
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.drop_constraint("fk_documents_file_id", type_="foreignkey")
    op.drop_index("ix_documents_file_id", table_name="documents")
    op.drop_column("documents", "file_id")
    op.drop_index("ix_files_file_md5", table_name="files")
    op.drop_index("ix_files_knowledge_base_id", table_name="files")
    op.drop_index("ix_files_owner_id", table_name="files")
    op.drop_table("files")
