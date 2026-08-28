"""add idempotency request fingerprint

Revision ID: 0002_idempotency_fingerprint
Revises: 0001_event_store
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_idempotency_fingerprint"
down_revision = "0001_event_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("command_receipts", sa.Column("request_fingerprint", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("command_receipts", "request_fingerprint")
