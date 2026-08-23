"""Rebuild knowledge asset states, audit history and active-document constraint."""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0006"
down_revision = "20260823_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE documents SET parse_status = UPPER(parse_status)")
    op.execute(
        "UPDATE files SET status = 'SUCCESS' WHERE status = 'UPLOADED' AND id IN (SELECT file_id FROM documents WHERE parse_status = 'SUCCESS' AND deleted_at IS NULL)"
    )
    op.execute(
        "UPDATE files SET status = 'PARSE_PENDING' WHERE status = 'UPLOADED' AND id IN (SELECT file_id FROM documents WHERE parse_status IN ('PENDING', 'PARSING') AND deleted_at IS NULL)"
    )
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.add_column(sa.Column("storage_status", sa.String(length=32), nullable=True))
        batch.alter_column(
            "status", existing_type=sa.String(length=32), type_=sa.String(length=32), nullable=False
        )
    op.execute(
        "UPDATE files SET storage_status = CASE WHEN status = 'PHYSICAL_DELETED' THEN 'PHYSICAL_DELETED' ELSE 'PRESENT' END"
    )
    op.execute("UPDATE files SET status = 'UPLOAD_CANCELLED' WHERE status = 'PHYSICAL_DELETED'")
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.alter_column("storage_status", nullable=False, server_default="PRESENT")

    op.drop_index("uq_documents_file_id_deleted_at", table_name="documents")
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.add_column(
            sa.Column(
                "active_file_id",
                sa.Integer(),
                sa.Computed("CASE WHEN deleted_at IS NULL THEN file_id ELSE NULL END"),
                nullable=True,
            )
        )
    # The previous nullable composite unique index allowed multiple active rows in SQLite.
    # Preserve their audit history and keep the most recent row as the current document.
    op.execute(
        "UPDATE documents SET deleted_at = CURRENT_TIMESTAMP WHERE id IN ("
        "SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY file_id ORDER BY id DESC) AS rn "
        "FROM documents WHERE deleted_at IS NULL) WHERE rn > 1)"
    )
    op.create_index("uq_documents_active_file_id", "documents", ["active_file_id"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "operator_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    for name, column in (
        ("ix_audit_logs_operator_id", "operator_id"),
        ("ix_audit_logs_action", "action"),
        ("ix_audit_logs_target_type", "target_type"),
        ("ix_audit_logs_target_id", "target_id"),
    ):
        op.create_index(name, "audit_logs", [column])


def downgrade() -> None:
    for name in (
        "ix_audit_logs_target_id",
        "ix_audit_logs_target_type",
        "ix_audit_logs_action",
        "ix_audit_logs_operator_id",
    ):
        op.drop_index(name, table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("uq_documents_active_file_id", table_name="documents")
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.drop_column("active_file_id")
    op.create_index(
        "uq_documents_file_id_deleted_at", "documents", ["file_id", "deleted_at"], unique=True
    )
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.drop_column("storage_status")
