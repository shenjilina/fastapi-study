"""Remove indexes not present in the target schema."""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0005"
down_revision = "20260823_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if any(
        item["name"] == "ix_knowledge_bases_name"
        for item in inspector.get_indexes("knowledge_bases")
    ):
        op.drop_index("ix_knowledge_bases_name", table_name="knowledge_bases")

    with op.batch_alter_table("files", recreate="always") as batch:
        batch.alter_column("stored_filename", existing_type=sa.String(length=255), unique=False)


def downgrade() -> None:
    op.create_index("ix_knowledge_bases_name", "knowledge_bases", ["name"])
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.alter_column("stored_filename", existing_type=sa.String(length=255), unique=True)
