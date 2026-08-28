from rpg_engine_api.domain.commands import CommandEnvelope


def test_command_fingerprint_ignores_command_id_but_not_payload() -> None:
    first = CommandEnvelope(command_id="a", command_type="RollDice", campaign_id="c", idempotency_key="same", payload={"expression": "1d20"})
    retry = first.model_copy(update={"command_id": "b"})
    changed = first.model_copy(update={"command_id": "c", "payload": {"expression": "2d20"}})
    assert first.idempotency_fingerprint() == retry.idempotency_fingerprint()
    assert first.idempotency_fingerprint() != changed.idempotency_fingerprint()
