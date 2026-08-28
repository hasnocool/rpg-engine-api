from rpg_engine_api.application.durable_service import DurableEngineService
from rpg_engine_api.domain.commands import CommandEnvelope, PrincipalContext
from rpg_engine_api.persistence.event_store import InMemoryEventStore


async def test_published_pack_and_workspace_survive_service_rebuild() -> None:
    store = InMemoryEventStore()
    principal = PrincipalContext(principal_id="creator")
    engine = DurableEngineService(store=store)
    await engine.execute(CommandEnvelope(command_type="CreateAuthoringWorkspace", payload={"workspace_id": "ws", "namespace": "demo"}), principal)
    await engine.execute(CommandEnvelope(command_type="UpsertDraftDefinition", payload={"workspace_id": "ws", "draft_id": "npc", "definition_type": "npc_template", "key": "demo:npc/guard", "data": {"name": "Guard", "max_hp": 10, "attack_bonus": 2, "defense": 10}, "source": {"license_id": "original"}}), principal)
    await engine.execute(CommandEnvelope(command_type="ValidateAuthoringWorkspace", payload={"workspace_id": "ws"}), principal)
    published = await engine.execute(CommandEnvelope(command_type="PublishAuthoringWorkspace", payload={"workspace_id": "ws", "version": "1.0.0"}), principal)
    assert published.status.value == "accepted"

    restored = DurableEngineService(store=store)
    await restored.rebuild_from_store()
    assert restored.authoring_workspaces["ws"].status.value == "published"
    assert ("demo", "1.0.0") in restored.published_packs
