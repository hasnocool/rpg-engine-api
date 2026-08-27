"""initial event store tables

Revision ID: 0001_event_store
Revises: None
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_event_store"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_streams",
        sa.Column("stream_id", sa.String(length=255), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "domain_events",
        sa.Column("sequence", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("stream_id", sa.String(length=255), nullable=False),
        sa.Column("stream_version", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("event_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("stream_id", "stream_version", name="uq_domain_events_stream_version"),
    )
    op.create_index("ix_domain_events_stream_id", "domain_events", ["stream_id"])
    op.create_index("ix_domain_events_campaign_id", "domain_events", ["campaign_id"])
    op.create_index("ix_domain_events_event_type", "domain_events", ["event_type"])
    op.create_table(
        "command_receipts",
        sa.Column("idempotency_key", sa.String(length=255), primary_key=True),
        sa.Column("command_id", sa.String(length=128), nullable=False),
        sa.Column("receipt_json", sa.Text(), nullable=False),
    )
    op.create_table(
        "snapshots",
        sa.Column("stream_id", sa.String(length=255), primary_key=True),
        sa.Column("stream_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
    )
    op.create_table(
        "projection_checkpoints",
        sa.Column("projection_name", sa.String(length=255), primary_key=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("last_sequence", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("published_at", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("projection_checkpoints")
    op.drop_table("snapshots")
    op.drop_table("command_receipts")
    op.drop_index("ix_domain_events_event_type", table_name="domain_events")
    op.drop_index("ix_domain_events_campaign_id", table_name="domain_events")
    op.drop_index("ix_domain_events_stream_id", table_name="domain_events")
    op.drop_table("domain_events")
    op.drop_table("event_streams")
