"""Bind documents directly to their knowledge bases."""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0007"
down_revision = "20260823_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("knowledge_base_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE documents SET knowledge_base_id = "
        "(SELECT knowledge_base_id FROM files WHERE files.id = documents.file_id)"
    )
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])
    if op.get_bind().dialect.name == "sqlite":
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
    else:
        with op.batch_alter_table("documents") as batch:
            batch.alter_column("knowledge_base_id", nullable=False)
            batch.create_foreign_key(
                "fk_documents_knowledge_base_id",
                "knowledge_bases",
                ["knowledge_base_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER trg_documents_knowledge_base_id_update_check")
        op.execute("DROP TRIGGER trg_documents_knowledge_base_id_matches_file")
        op.execute("DROP TRIGGER trg_documents_knowledge_base_id_required")
    else:
        with op.batch_alter_table("documents") as batch:
            batch.drop_constraint("fk_documents_knowledge_base_id", type_="foreignkey")
    op.drop_index("ix_documents_knowledge_base_id", table_name="documents")
    op.drop_column("documents", "knowledge_base_id")
