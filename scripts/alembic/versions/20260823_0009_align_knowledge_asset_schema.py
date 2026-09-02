"""Align SQLite knowledge-asset tables with their SQLAlchemy models."""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0009"
down_revision = "20260823_0008"
branch_labels = None
depends_on = None

_NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s"}
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
        return

    _drop_document_triggers()
    with op.batch_alter_table(
        "files", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint("fk_files_owner_id", type_="foreignkey")
        batch.drop_constraint("fk_files_knowledge_base_id", type_="foreignkey")
        batch.drop_index("uq_files_file_md5")
        batch.alter_column("status", type_=sa.String(length=32))
        batch.alter_column("storage_status", type_=sa.String(length=32))
        batch.create_foreign_key(
            "fk_files_owner_id", "users", ["owner_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_files_knowledge_base_id",
            "knowledge_bases",
            ["knowledge_base_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table(
        "documents", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint("fk_documents_file_id", type_="foreignkey")
        batch.alter_column("knowledge_base_id", nullable=False)
        batch.create_foreign_key(
            "fk_documents_file_id", "files", ["file_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_documents_knowledge_base_id",
            "knowledge_bases",
            ["knowledge_base_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_documents_parse_status", ["parse_status"])
        batch.create_index("ix_documents_deleted_at", ["deleted_at"])

    with op.batch_alter_table(
        "chunks", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint("fk_chunks_document_id", type_="foreignkey")
        batch.create_foreign_key(
            "fk_chunks_document_id", "documents", ["document_id"], ["id"], ondelete="RESTRICT"
        )

    with op.batch_alter_table(
        "knowledge_bases", recreate="always", naming_convention=_NAMING_CONVENTION
    ) as batch:
        batch.drop_constraint("fk_knowledge_bases_owner_id", type_="foreignkey")
        batch.create_foreign_key(
            "fk_knowledge_bases_owner_id", "users", ["owner_id"], ["id"], ondelete="RESTRICT"
        )
    _create_document_triggers()


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    _drop_document_triggers()
