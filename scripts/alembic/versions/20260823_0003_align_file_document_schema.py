"""Align knowledge, files, documents and chunks with the target schema."""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0003"
down_revision = "20260822_0002"
branch_labels = None
depends_on = None


def _drop_index_if_exists(name: str, table: str) -> None:
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}
    if name in indexes:
        op.drop_index(name, table_name=table)


def upgrade() -> None:
    # Legacy documents created before files were introduced cannot satisfy the new
    # required file_id relation. Their vectors are cleaned by the deployment
    # preflight command before this migration runs.
    op.execute("DELETE FROM documents WHERE file_id IS NULL")

    with op.batch_alter_table("knowledge_bases", recreate="always") as batch:
        batch.add_column(
            sa.Column(
                "visibility",
                sa.Enum("PRIVATE", "PUBLIC", name="knowledgebasevisibility"),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("name", existing_type=sa.String(length=100), type_=sa.String(255))
    op.execute("UPDATE knowledge_bases SET visibility = 'PRIVATE' WHERE visibility IS NULL")
    with op.batch_alter_table("knowledge_bases", recreate="always") as batch:
        batch.alter_column("visibility", nullable=False)

    op.execute(
        "UPDATE files SET status = 'PHYSICAL_DELETED' WHERE status IN ('deleted', 'DELETED')"
    )
    op.execute("UPDATE files SET status = 'PARSE_FAILED' WHERE status IN ('failed', 'FAILED')")
    op.execute(
        "UPDATE files SET status = 'UPLOADED' WHERE status IN ('bound', 'BOUND', 'uploaded', 'UPLOADED')"
    )
    _drop_index_if_exists("ix_files_file_md5", "files")
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.alter_column("stored_filename", nullable=True)
        batch.alter_column(
            "storage_path", existing_type=sa.Text(), type_=sa.String(512), nullable=True
        )
        batch.alter_column(
            "file_type", existing_type=sa.String(length=20), type_=sa.String(64), nullable=True
        )
        batch.alter_column("mime_type", existing_type=sa.String(length=100), type_=sa.String(128))
        batch.alter_column(
            "file_size", existing_type=sa.Integer(), type_=sa.BigInteger(), nullable=False
        )
        batch.alter_column(
            "status",
            existing_type=sa.Enum("uploaded", "bound", "deleted", "failed", name="filestatus"),
            type_=sa.Enum(
                "UPLOADING",
                "UPLOADED",
                "PARSE_PENDING",
                "PARSE_FAILED",
                "PHYSICAL_DELETED",
                name="filestatus",
            ),
        )
    op.create_index("uq_files_file_md5", "files", ["file_md5"], unique=True)

    _drop_index_if_exists("ix_documents_knowledge_base_id", "documents")
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.add_column(sa.Column("error_msg", sa.Text(), nullable=True))
        batch.add_column(sa.Column("vector_cleaned", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("file_size", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("file_id", nullable=False)
        batch.drop_column("knowledge_base_id")
    op.execute("UPDATE documents SET vector_cleaned = 0 WHERE vector_cleaned IS NULL")
    op.execute(
        "UPDATE documents SET file_size = (SELECT file_size FROM files WHERE files.id = documents.file_id) "
        "WHERE file_size IS NULL"
    )
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.alter_column("vector_cleaned", nullable=False, server_default=sa.false())
        batch.alter_column("file_size", nullable=False, server_default="0")
    op.create_index(
        "uq_documents_file_id_deleted_at", "documents", ["file_id", "deleted_at"], unique=True
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("vector_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_deleted_at", "chunks", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_chunks_deleted_at", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("uq_documents_file_id_deleted_at", table_name="documents")
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.add_column(sa.Column("knowledge_base_id", sa.Integer(), nullable=True))
        batch.drop_column("error_msg")
        batch.drop_column("vector_cleaned")
        batch.drop_column("file_size")
        batch.drop_column("deleted_at")
    op.drop_index("uq_files_file_md5", table_name="files")
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.alter_column(
            "status", type_=sa.Enum("uploaded", "bound", "deleted", "failed", name="filestatus")
        )
    op.drop_index("ix_knowledge_bases_deleted_at", table_name="knowledge_bases")
    with op.batch_alter_table("knowledge_bases", recreate="always") as batch:
        batch.drop_column("visibility")
        batch.drop_column("deleted_at")
