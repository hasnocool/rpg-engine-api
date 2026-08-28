import asyncio
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, Text, UniqueConstraint, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rpg_engine_api.domain.commands import CommandReceipt
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.persistence.event_store import StreamVersionConflict

metadata = MetaData()
event_streams = Table("event_streams", metadata, Column("stream_id", String(255), primary_key=True), Column("version", Integer, nullable=False, default=0))
domain_events = Table("domain_events", metadata, Column("sequence", BigInteger, primary_key=True, autoincrement=True), Column("event_id", String(128), nullable=False, unique=True), Column("stream_id", String(255), nullable=False, index=True), Column("stream_version", Integer, nullable=False), Column("campaign_id", String(128), nullable=False, index=True), Column("event_type", String(128), nullable=False, index=True), Column("event_json", Text, nullable=False), UniqueConstraint("stream_id", "stream_version", name="uq_domain_events_stream_version"))
command_receipts = Table("command_receipts", metadata, Column("idempotency_key", String(255), primary_key=True), Column("command_id", String(128), nullable=False), Column("request_fingerprint", String(64), nullable=True), Column("receipt_json", Text, nullable=False))
snapshots = Table("snapshots", metadata, Column("stream_id", String(255), primary_key=True), Column("stream_version", Integer, nullable=False), Column("schema_version", String(32), nullable=False), Column("snapshot_json", Text, nullable=False))
projection_checkpoints = Table("projection_checkpoints", metadata, Column("projection_name", String(255), primary_key=True), Column("schema_version", String(32), nullable=False), Column("last_sequence", BigInteger, nullable=False))
outbox_events = Table("outbox_events", metadata, Column("id", BigInteger, primary_key=True, autoincrement=True), Column("event_id", String(128), nullable=False, unique=True), Column("payload_json", Text, nullable=False), Column("published_at", String(64), nullable=True))
published_content_packs = Table("published_content_packs", metadata, Column("pack_id", String(255), primary_key=True), Column("version", String(64), primary_key=True), Column("content_hash", String(64), nullable=False), Column("pack_json", Text, nullable=False))
authoring_workspaces = Table("authoring_workspaces", metadata, Column("workspace_id", String(255), primary_key=True), Column("owner_id", String(255), nullable=False, index=True), Column("status", String(32), nullable=False), Column("workspace_json", Text, nullable=False))


class PostgresEventStore:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self._subscribers: set[asyncio.Queue[DomainEvent]] = set()
        self._overflowed_subscribers: set[asyncio.Queue[DomainEvent]] = set()

    async def prepare(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def current_version(self, stream_id: str) -> int:
        async with self.engine.connect() as connection:
            return int((await connection.scalar(select(event_streams.c.version).where(event_streams.c.stream_id == stream_id))) or 0)

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
                sequence = int((await connection.execute(insert(domain_events).values(event_id=provisional.event_id, stream_id=stream_id, stream_version=version, campaign_id=provisional.campaign_id, event_type=provisional.event_type, event_json=provisional.model_dump_json()).returning(domain_events.c.sequence))).scalar_one())
                event = provisional.model_copy(update={"sequence": sequence})
                await connection.execute(update(domain_events).where(domain_events.c.event_id == event.event_id).values(event_json=event.model_dump_json()))
                await connection.execute(insert(outbox_events).values(event_id=event.event_id, payload_json=event.model_dump_json()))
                stored.append(event)
            await connection.execute(update(event_streams).where(event_streams.c.stream_id == stream_id).values(version=version))
        for event in stored:
            for queue in tuple(self._subscribers):
                if queue in self._overflowed_subscribers:
                    continue
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    self._overflowed_subscribers.add(queue)
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
        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement.order_by(domain_events.c.sequence).limit(limit))).scalars()
            return tuple(DomainEvent.model_validate_json(value) for value in rows)

    async def last_sequence(self, *, campaign_id: str | None = None) -> int:
        statement = select(func.max(domain_events.c.sequence))
        if campaign_id is not None:
            statement = statement.where(domain_events.c.campaign_id == campaign_id)
        async with self.engine.connect() as connection:
            return int((await connection.scalar(statement)) or 0)

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

    async def pending_outbox(self, *, limit: int = 1000) -> tuple[DomainEvent, ...]:
        async with self.engine.connect() as connection:
            rows = (await connection.execute(select(outbox_events.c.payload_json).where(outbox_events.c.published_at.is_(None)).order_by(outbox_events.c.id).limit(limit))).scalars()
            return tuple(DomainEvent.model_validate_json(value) for value in rows)

    async def mark_outbox_published(self, event_id: str, *, published_at: str | None = None) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(update(outbox_events).where(outbox_events.c.event_id == event_id).values(published_at=published_at or datetime.now(UTC).isoformat()))

    async def pending_outbox_count(self) -> int:
        async with self.engine.connect() as connection:
            return int((await connection.scalar(select(func.count()).select_from(outbox_events).where(outbox_events.c.published_at.is_(None)))) or 0)

    async def save_projection_checkpoint(self, name: str, *, schema_version: str, last_sequence: int) -> None:
        async with self.engine.begin() as connection:
            existing = await connection.scalar(select(projection_checkpoints.c.projection_name).where(projection_checkpoints.c.projection_name == name))
            if existing is None:
                await connection.execute(insert(projection_checkpoints).values(projection_name=name, schema_version=schema_version, last_sequence=last_sequence))
            else:
                await connection.execute(update(projection_checkpoints).where(projection_checkpoints.c.projection_name == name).values(schema_version=schema_version, last_sequence=last_sequence))

    async def load_projection_checkpoint(self, name: str) -> dict[str, Any] | None:
        async with self.engine.connect() as connection:
            row = (await connection.execute(select(projection_checkpoints).where(projection_checkpoints.c.projection_name == name))).mappings().first()
            return dict(row) if row else None

    async def save_snapshot(self, stream_id: str, *, stream_version: int, schema_version: str, value: dict[str, Any]) -> None:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        async with self.engine.begin() as connection:
            existing = await connection.scalar(select(snapshots.c.stream_id).where(snapshots.c.stream_id == stream_id))
            if existing is None:
                await connection.execute(insert(snapshots).values(stream_id=stream_id, stream_version=stream_version, schema_version=schema_version, snapshot_json=payload))
            else:
                await connection.execute(update(snapshots).where(snapshots.c.stream_id == stream_id).values(stream_version=stream_version, schema_version=schema_version, snapshot_json=payload))

    async def load_snapshot(self, stream_id: str) -> dict[str, Any] | None:
        async with self.engine.connect() as connection:
            row = (await connection.execute(select(snapshots).where(snapshots.c.stream_id == stream_id))).mappings().first()
            if row is None:
                return None
            return {"stream_id": str(row["stream_id"]), "stream_version": int(row["stream_version"]), "schema_version": str(row["schema_version"]), "value": json.loads(str(row["snapshot_json"]))}

    async def save_content_pack(self, value: dict[str, Any]) -> None:
        pack_id, version = str(value["pack_id"]), str(value["version"])
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        async with self.engine.begin() as connection:
            exists = await connection.scalar(select(published_content_packs.c.pack_id).where(published_content_packs.c.pack_id == pack_id, published_content_packs.c.version == version))
            if exists is None:
                await connection.execute(insert(published_content_packs).values(pack_id=pack_id, version=version, content_hash=str(value["content_hash"]), pack_json=payload))
            else:
                await connection.execute(update(published_content_packs).where(published_content_packs.c.pack_id == pack_id, published_content_packs.c.version == version).values(content_hash=str(value["content_hash"]), pack_json=payload))

    async def load_content_packs(self) -> tuple[dict[str, Any], ...]:
        async with self.engine.connect() as connection:
            rows = (await connection.execute(select(published_content_packs.c.pack_json).order_by(published_content_packs.c.pack_id, published_content_packs.c.version))).scalars()
            return tuple(json.loads(value) for value in rows)

    async def save_authoring_workspace(self, value: dict[str, Any]) -> None:
        workspace_id = str(value["workspace_id"])
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        async with self.engine.begin() as connection:
            exists = await connection.scalar(select(authoring_workspaces.c.workspace_id).where(authoring_workspaces.c.workspace_id == workspace_id))
            if exists is None:
                await connection.execute(insert(authoring_workspaces).values(workspace_id=workspace_id, owner_id=str(value["owner_id"]), status=str(value["status"]), workspace_json=payload))
            else:
                await connection.execute(update(authoring_workspaces).where(authoring_workspaces.c.workspace_id == workspace_id).values(owner_id=str(value["owner_id"]), status=str(value["status"]), workspace_json=payload))

    async def load_authoring_workspaces(self) -> tuple[dict[str, Any], ...]:
        async with self.engine.connect() as connection:
            rows = (await connection.execute(select(authoring_workspaces.c.workspace_json).order_by(authoring_workspaces.c.workspace_id))).scalars()
            return tuple(json.loads(value) for value in rows)

    def subscribe(self, *, maxsize: int = 256) -> asyncio.Queue[DomainEvent]:
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def subscription_overflowed(self, queue: asyncio.Queue[DomainEvent]) -> bool:
        return queue in self._overflowed_subscribers

    def unsubscribe(self, queue: asyncio.Queue[DomainEvent]) -> None:
        self._subscribers.discard(queue)
        self._overflowed_subscribers.discard(queue)

    async def clear_for_test(self) -> None:
        async with self.engine.begin() as connection:
            for table in (outbox_events, command_receipts, domain_events, event_streams, snapshots, projection_checkpoints, authoring_workspaces, published_content_packs):
                await connection.execute(delete(table))
