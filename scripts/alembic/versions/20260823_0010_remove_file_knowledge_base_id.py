"""Remove the direct knowledge-base association from files."""

from alembic import op


revision = "20260823_0010"
down_revision = "20260823_0009"
branch_labels = None
depends_on = None


_DOCUMENT_TRIGGERS = (
    "trg_documents_knowledge_base_id_update_check",
    "trg_documents_knowledge_base_id_matches_file",
    "trg_documents_knowledge_base_id_required",
)


def _drop_document_triggers() -> None:
    for trigger in _DOCUMENT_TRIGGERS:
        op.execute(f"DROP TRIGGER {trigger}")


def _create_document_triggers() -> None:
    op.execute(
        "CREATE TRIGGER trg_documents_knowledge_base_id_required "
        "BEFORE INSERT ON documents "
        "WHEN NEW.knowledge_base_id IS NULL "
        "BEGIN SELECT RAISE(ABORT, 'knowledge_base_id is required'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_documents_knowledge_base_id_update_check "
        "BEFORE UPDATE OF knowledge_base_id ON documents "
        "WHEN NEW.knowledge_base_id IS NULL "
        "BEGIN SELECT RAISE(ABORT, 'knowledge_base_id is required'); END"
    )


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        with op.batch_alter_table("files") as batch:
            batch.drop_constraint("fk_files_knowledge_base_id", type_="foreignkey")
            batch.drop_index("ix_files_knowledge_base_id")
            batch.drop_column("knowledge_base_id")
        return

    _drop_document_triggers()
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.drop_constraint("fk_files_knowledge_base_id", type_="foreignkey")
        batch.drop_index("ix_files_knowledge_base_id")
        batch.drop_column("knowledge_base_id")
    _create_document_triggers()


def downgrade() -> None:
    raise NotImplementedError(
        "Restoring files.knowledge_base_id requires an explicit reassignment plan."
    )
