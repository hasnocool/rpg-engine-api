from pathlib import Path

import pytest


@pytest.mark.migration
def test_initial_event_store_migration_is_present() -> None:
    migration = Path("migrations/versions/0001_event_store.py")
    assert migration.exists()
    text = migration.read_text(encoding="utf-8")
    assert "event_streams" in text
    assert "domain_events" in text
    assert "command_receipts" in text
