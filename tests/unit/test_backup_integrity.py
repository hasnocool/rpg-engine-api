from rpg_engine_api.infrastructure.backup import EventHistoryBackup


def test_backup_digest_detects_tampering() -> None:
    backup = EventHistoryBackup(campaign_id="x", source_last_sequence=0, events=(), content_packs=(), digest="wrong")
    assert not backup.verify()
