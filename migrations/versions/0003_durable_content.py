"""persist published content packs and authoring workspaces

Revision ID: 0003_durable_content
Revises: 0002_idempotency_fingerprint
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_durable_content"
down_revision = "0002_idempotency_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("published_content_packs", sa.Column("pack_id", sa.String(length=255), primary_key=True), sa.Column("version", sa.String(length=64), primary_key=True), sa.Column("content_hash", sa.String(length=64), nullable=False), sa.Column("pack_json", sa.Text(), nullable=False))
    op.create_table("authoring_workspaces", sa.Column("workspace_id", sa.String(length=255), primary_key=True), sa.Column("owner_id", sa.String(length=255), nullable=False), sa.Column("status", sa.String(length=32), nullable=False), sa.Column("workspace_json", sa.Text(), nullable=False))
    op.create_index("ix_authoring_workspaces_owner_id", "authoring_workspaces", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_authoring_workspaces_owner_id", table_name="authoring_workspaces")
    op.drop_table("authoring_workspaces")
    op.drop_table("published_content_packs")
