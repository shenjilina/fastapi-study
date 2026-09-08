"""Move file metadata to files and add document title/description."""

from alembic import op
import sqlalchemy as sa

revision = "20260822_0002"
down_revision = "20260822_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("documents")}
    if "ix_documents_file_md5" in indexes:
        op.drop_index("ix_documents_file_md5", table_name="documents")
    with op.batch_alter_table("files", recreate="always") as batch:
        batch.alter_column("original_filename", new_column_name="filename")

    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))

    op.execute("UPDATE documents SET title = COALESCE(filename, '未命名文档') WHERE title IS NULL")

    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.alter_column("title", existing_type=sa.String(length=255), nullable=False)
        batch.drop_column("filename")
        batch.drop_column("file_type")
        batch.drop_column("file_size")
        batch.drop_column("file_md5")


def downgrade() -> None:
    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.add_column(sa.Column("filename", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("file_type", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("file_size", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("file_md5", sa.String(length=32), nullable=True))

    op.execute(
        "UPDATE documents SET filename = title, file_type = 'unknown', file_size = 0, file_md5 = ''"
    )

    with op.batch_alter_table("documents", recreate="always") as batch:
        batch.drop_column("title")
        batch.drop_column("description")

    with op.batch_alter_table("files", recreate="always") as batch:
        batch.alter_column("filename", new_column_name="original_filename")
