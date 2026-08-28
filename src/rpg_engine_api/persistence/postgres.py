from collections.abc import Iterable

from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, Text, UniqueConstraint, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rpg_engine_api.domain.commands import CommandReceipt
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.persistence.event_store import StreamVersionConflict

metadata = MetaData()

event_streams = Table("event_streams", metadata, Column("stream_id", String(255), primary_key=True), Column("version", Integer, nullable=False, default=0))

domain_events = Table(
    "domain_events", metadata,
    Column("sequence", BigInteger, primary_key=True, autoincrement=True),
    Column("event_id", String(128), nullable=False, unique=True),
    Column("stream_id", String(255), nullable=False, index=True),
    Column("stream_version", Integer, nullable=False),
    Column("campaign_id", String(128), nullable=False, index=True),
    Column("event_type", String(128), nullable=False, index=True),
    Column("event_json", Text, nullable=False),
    UniqueConstraint("stream_id", "stream_version", name="uq_domain_events_stream_version"),
)

command_receipts = Table(
    "command_receipts", metadata,
    Column("idempotency_key", String(255), primary_key=True),
    Column("command_id", String(128), nullable=False),
    Column("request_fingerprint", String(64), nullable=True),
    Column("receipt_json", Text, nullable=False),
)

snapshots = Table("snapshots", metadata, Column("stream_id", String(255), primary_key=True), Column("stream_version", Integer, nullable=False), Column("schema_version", String(32), nullable=False), Column("snapshot_json", Text, nullable=False))
projection_checkpoints = Table("projection_checkpoints", metadata, Column("projection_name", String(255), primary_key=True), Column("schema_version", String(32), nullable=False), Column("last_sequence", BigInteger, nullable=False))
outbox_events = Table("outbox_events", metadata, Column("id", BigInteger, primary_key=True, autoincrement=True), Column("event_id", String(128), nullable=False, unique=True), Column("payload_json", Text, nullable=False), Column("published_at", String(64), nullable=True))


class PostgresEventStore:
    """Async PostgreSQL event store used by integration/deployment paths."""

    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)

    async def prepare(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def current_version(self, stream_id: str) -> int:
        async with self.engine.connect() as connection:
            value = await connection.scalar(select(event_streams.c.version).where(event_streams.c.stream_id == stream_id))
            return int(value or 0)

    async def append(self, stream_id: str, expected_version: int, events: Iterable[DomainEvent]) -> tuple[DomainEvent, ...]:
        pending = tuple(events)
        async with self.engine.begin() as connection:
            row = (await connection.execute(select(event_streams.c.version).where(event_streams.c.stream_id == stream_id).with_for_update())).first()
            if row is None:
                if expected_version != 0:
                    raise StreamVersionConflict(stream_id, expected_version, 0)
                await connection.execute(insert(event_streams).values(stream_id=stream_id, version=0))
                actual = 0
            else:
                actual = int(row.version)
                if actual != expected_version:
                    raise StreamVersionConflict(stream_id, expected_version, actual)
            stored: list[DomainEvent] = []
            version = actual
            for raw in pending:
                version += 1
                provisional = raw.model_copy(update={"stream_id": stream_id, "stream_version": version})
                result = await connection.execute(insert(domain_events).values(event_id=provisional.event_id, stream_id=stream_id, stream_version=version, campaign_id=provisional.campaign_id, event_type=provisional.event_type, event_json=provisional.model_dump_json()).returning(domain_events.c.sequence))
                sequence = int(result.scalar_one())
                event = provisional.model_copy(update={"sequence": sequence})
                await connection.execute(update(domain_events).where(domain_events.c.event_id == event.event_id).values(event_json=event.model_dump_json()))
                await connection.execute(insert(outbox_events).values(event_id=event.event_id, payload_json=event.model_dump_json()))
                stored.append(event)
            await connection.execute(update(event_streams).where(event_streams.c.stream_id == stream_id).values(version=version))
        return tuple(stored)

    async def read_stream(self, stream_id: str) -> tuple[DomainEvent, ...]:
        async with self.engine.connect() as connection:
            rows = (await connection.execute(select(domain_events.c.event_json).where(domain_events.c.stream_id == stream_id).order_by(domain_events.c.stream_version))).scalars()
            return tuple(DomainEvent.model_validate_json(value) for value in rows)

    async def read_all(self) -> tuple[DomainEvent, ...]:
        async with self.engine.connect() as connection:
            rows = (await connection.execute(select(domain_events.c.event_json).order_by(domain_events.c.sequence))).scalars()
            return tuple(DomainEvent.model_validate_json(value) for value in rows)

    async def read_after(self, sequence: int, *, campaign_id: str | None = None, limit: int = 1000) -> tuple[DomainEvent, ...]:
        statement = select(domain_events.c.event_json).where(domain_events.c.sequence > sequence)
        if campaign_id is not None:
            statement = statement.where(domain_events.c.campaign_id == campaign_id)
        statement = statement.order_by(domain_events.c.sequence).limit(limit)
        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement)).scalars()
            return tuple(DomainEvent.model_validate_json(value) for value in rows)

    async def last_sequence(self, *, campaign_id: str | None = None) -> int:
        statement = select(func.max(domain_events.c.sequence))
        if campaign_id is not None:
            statement = statement.where(domain_events.c.campaign_id == campaign_id)
        async with self.engine.connect() as connection:
            value = await connection.scalar(statement)
            return int(value or 0)

    async def get_receipt(self, key: str) -> CommandReceipt | None:
        async with self.engine.connect() as connection:
            value = await connection.scalar(select(command_receipts.c.receipt_json).where(command_receipts.c.idempotency_key == key))
            return CommandReceipt.model_validate_json(value) if value else None

    async def get_receipt_fingerprint(self, key: str) -> str | None:
        async with self.engine.connect() as connection:
            value = await connection.scalar(select(command_receipts.c.request_fingerprint).where(command_receipts.c.idempotency_key == key))
            return str(value) if value else None

    async def save_receipt(self, key: str, receipt: CommandReceipt, *, fingerprint: str | None = None) -> None:
        async with self.engine.begin() as connection:
            existing = await connection.scalar(select(command_receipts.c.idempotency_key).where(command_receipts.c.idempotency_key == key))
            if existing is None:
                await connection.execute(insert(command_receipts).values(idempotency_key=key, command_id=receipt.command_id, request_fingerprint=fingerprint, receipt_json=receipt.model_dump_json()))

    async def clear_for_test(self) -> None:
        async with self.engine.begin() as connection:
            for table in (outbox_events, command_receipts, domain_events, event_streams):
                await connection.execute(delete(table))
