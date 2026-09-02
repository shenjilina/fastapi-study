"""Replace the document generated column with a compatible partial index."""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0008"
down_revision = "20260823_0007"
branch_labels = None
depends_on = None


def _create_sqlite_consistency_triggers() -> None:
    op.execute(
        "CREATE TRIGGER trg_documents_knowledge_base_id_required "
        "BEFORE INSERT ON documents "
        "WHEN NEW.knowledge_base_id IS NULL "
        "BEGIN SELECT RAISE(ABORT, 'knowledge_base_id is required'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_documents_knowledge_base_id_matches_file "
        "BEFORE INSERT ON documents "
        "WHEN NEW.knowledge_base_id != "
        "(SELECT knowledge_base_id FROM files WHERE id = NEW.file_id) "
        "BEGIN SELECT RAISE(ABORT, 'knowledge_base_id must match file'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_documents_knowledge_base_id_update_check "
        "BEFORE UPDATE OF file_id, knowledge_base_id ON documents "
        "WHEN NEW.knowledge_base_id IS NULL OR NEW.knowledge_base_id != "
        "(SELECT knowledge_base_id FROM files WHERE id = NEW.file_id) "
        "BEGIN SELECT RAISE(ABORT, 'knowledge_base_id must match file'); END"
    )


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_index("uq_documents_active_file_id", table_name="documents")
        op.create_index(
            "uq_documents_active_file_id",
            "documents",
            ["file_id"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )
        return

    for trigger in (
        "trg_documents_knowledge_base_id_update_check",
        "trg_documents_knowledge_base_id_matches_file",
        "trg_documents_knowledge_base_id_required",
    ):
        op.execute(f"DROP TRIGGER {trigger}")
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.drop_index("uq_documents_active_file_id")
        batch.drop_column("active_file_id")
        batch.create_index(
            "uq_documents_active_file_id",
            ["file_id"],
            unique=True,
            sqlite_where=sa.text("deleted_at IS NULL"),
        )
    _create_sqlite_consistency_triggers()


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        for trigger in (
            "trg_documents_knowledge_base_id_update_check",
            "trg_documents_knowledge_base_id_matches_file",
            "trg_documents_knowledge_base_id_required",
        ):
            op.execute(f"DROP TRIGGER {trigger}")
