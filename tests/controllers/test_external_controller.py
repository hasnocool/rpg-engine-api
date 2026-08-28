import asyncio

from rpg_engine_api.controllers.external import ControllerIntent, ExternalControllerAdapter, ExternalDecisionStatus, VisibleControllerContext


def context() -> VisibleControllerContext:
    return VisibleControllerContext(actor_id="npc", campaign_id="c", controller_version="provider-v1", available_actions=({"action_id": "attack", "target_id": "hero"}, {"action_id": "guard"}))


async def test_external_controller_accepts_only_advertised_intent() -> None:
    async def provider(_: VisibleControllerContext) -> ControllerIntent:
        return ControllerIntent(action_id="attack", target_id="hero")
    result = await ExternalControllerAdapter("fake", "1", provider).choose_action(context())
    assert result.status == ExternalDecisionStatus.ACCEPTED
    assert result.action["action_id"] == "attack"


async def test_invalid_external_output_falls_back_deterministically() -> None:
    async def provider(_: VisibleControllerContext) -> ControllerIntent:
        return ControllerIntent(action_id="teleport_to_secret_room")
    adapter = ExternalControllerAdapter("fake", "1", provider, failure_threshold=1)
    result = await adapter.choose_action(context())
    assert result.status == ExternalDecisionStatus.FALLBACK
    assert adapter.circuit_open
    assert result.action["action_id"] in {"attack", "guard"}


async def test_timeout_falls_back_without_blocking_authority() -> None:
    async def provider(_: VisibleControllerContext) -> ControllerIntent:
        await asyncio.sleep(0.05)
        return ControllerIntent(action_id="attack", target_id="hero")
    adapter = ExternalControllerAdapter("fake", "1", provider, timeout_seconds=0.001)
    result = await adapter.choose_action(context())
    assert result.status == ExternalDecisionStatus.FALLBACK
    assert result.fallback_reason == "timeout"
