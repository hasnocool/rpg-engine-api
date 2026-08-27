import hashlib
import json
from typing import Any

from rpg_engine_api.application.platform_service import PlatformEngineService
from rpg_engine_api.domain.authoring import (
    AuthoringWorkspace,
    AuthoringWorkspaceStatus,
    ContentQualityReport,
    DraftDefinition,
    PublishedContentPack,
    PublishedDefinition,
    ValidationIssue,
)
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.ids import new_id, validate_content_key


class FullEngineService(PlatformEngineService):
    """Creator/content composition layer over the playable platform runtime."""

    def __init__(self) -> None:
        super().__init__()
        self.authoring_workspaces: dict[str, AuthoringWorkspace] = {}
        self.published_packs: dict[tuple[str, str], PublishedContentPack] = {}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {
            "CreateAuthoringWorkspace": self._create_authoring_workspace,
            "UpsertDraftDefinition": self._upsert_draft_definition,
            "ValidateAuthoringWorkspace": self._validate_authoring_workspace,
            "PublishAuthoringWorkspace": self._publish_authoring_workspace,
            "InstantiateEncounterTemplate": self._instantiate_encounter_template,
            "SimulateEncounterTemplate": self._simulate_encounter_template,
        }
        handler = handlers.get(command.command_type)
        if handler is not None:
            return await handler(command, principal)
        return await super()._dispatch(command, principal)

    def _workspace_owned(self, workspace_id: str, principal: PrincipalContext) -> AuthoringWorkspace:
        workspace = self.authoring_workspaces.get(workspace_id)
        if workspace is None:
            raise KeyError("authoring workspace does not exist")
        if workspace.owner_id != principal.principal_id:
            raise ValueError("authoring workspace belongs to another principal")
        if workspace.status == AuthoringWorkspaceStatus.PUBLISHED:
            raise ValueError("published workspace is immutable")
        return workspace

    async def _create_authoring_workspace(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        workspace_id = str(command.payload.get("workspace_id") or new_id("workspace"))
        namespace = str(command.payload.get("namespace", "")).strip().lower()
        if not namespace or not namespace.replace("_", "").isalnum():
            raise ValueError("namespace must be lowercase alphanumeric/underscore")
        if workspace_id in self.authoring_workspaces:
            raise ValueError("workspace already exists")
        workspace = AuthoringWorkspace(workspace_id=workspace_id, namespace=namespace, owner_id=principal.principal_id)
        self.authoring_workspaces[workspace_id] = workspace
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"workspace_id": workspace_id, "namespace": namespace})

    async def _upsert_draft_definition(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        workspace = self._workspace_owned(str(command.payload.get("workspace_id", "")), principal)
        draft_id = str(command.payload.get("draft_id") or new_id("draft"))
        key = validate_content_key(str(command.payload.get("key", "")))
        if not key.startswith(f"{workspace.namespace}:"):
            raise ValueError("definition key must use workspace namespace")
        existing = workspace.drafts.get(draft_id)
        draft = DraftDefinition(
            draft_id=draft_id,
            definition_type=str(command.payload.get("definition_type", "")),
            key=key,
            data=dict(command.payload.get("data", {})),
            source=dict(command.payload.get("source", {})),
            revision=(existing.revision + 1 if existing else 1),
        )
        workspace.drafts[draft_id] = draft
        workspace.status = AuthoringWorkspaceStatus.OPEN
        workspace.last_quality_report = None
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"workspace_id": workspace.workspace_id, "draft_id": draft_id, "revision": draft.revision})

    def _quality_report(self, workspace: AuthoringWorkspace) -> ContentQualityReport:
        issues: list[ValidationIssue] = []
        keys: dict[str, DraftDefinition] = {}
        for draft in workspace.drafts.values():
            if not draft.definition_type:
                issues.append(ValidationIssue(severity="error", code="missing_type", message="definition type is required", draft_id=draft.draft_id))
            if draft.key in keys:
                issues.append(ValidationIssue(severity="error", code="duplicate_key", message=f"duplicate definition key {draft.key}", draft_id=draft.draft_id))
            keys[draft.key] = draft
            if not draft.source.get("license_id"):
                issues.append(ValidationIssue(severity="error", code="missing_license", message="source.license_id is required", draft_id=draft.draft_id))
            if draft.definition_type == "npc_template":
                for required in ("name", "max_hp", "attack_bonus", "defense"):
                    if required not in draft.data:
                        issues.append(ValidationIssue(severity="error", code="missing_field", message=f"npc_template requires {required}", draft_id=draft.draft_id))
            elif draft.definition_type == "encounter_template":
                enemy_ref = draft.data.get("enemy_ref")
                if not enemy_ref:
                    issues.append(ValidationIssue(severity="error", code="missing_enemy_ref", message="encounter_template requires enemy_ref", draft_id=draft.draft_id))
                elif enemy_ref not in keys and not any(item.key == enemy_ref for item in workspace.drafts.values()):
                    issues.append(ValidationIssue(severity="error", code="unknown_reference", message=f"unknown enemy_ref {enemy_ref}", draft_id=draft.draft_id))
            elif draft.definition_type not in {"item", "quest_template", "narration_template"}:
                if draft.definition_type:
                    issues.append(ValidationIssue(severity="warning", code="unrecognized_type", message=f"no semantic validator yet for {draft.definition_type}", draft_id=draft.draft_id))
        return ContentQualityReport(workspace_id=workspace.workspace_id, valid=not any(issue.severity == "error" for issue in issues), issues=issues, definitions_checked=len(workspace.drafts))

    async def _validate_authoring_workspace(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        workspace = self._workspace_owned(str(command.payload.get("workspace_id", "")), principal)
        report = self._quality_report(workspace)
        workspace.last_quality_report = report
        workspace.status = AuthoringWorkspaceStatus.VALID if report.valid else AuthoringWorkspaceStatus.OPEN
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"workspace_id": workspace.workspace_id, "quality_report": report.model_dump(mode="json")})

    async def _publish_authoring_workspace(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        workspace = self._workspace_owned(str(command.payload.get("workspace_id", "")), principal)
        report = self._quality_report(workspace)
        workspace.last_quality_report = report
        if not report.valid:
            raise ValueError("workspace has validation errors")
        version = str(command.payload.get("version", "1.0.0"))
        definitions = tuple(
            PublishedDefinition(definition_type=draft.definition_type, key=draft.key, data=draft.data, source=draft.source)
            for draft in sorted(workspace.drafts.values(), key=lambda item: item.key)
        )
        canonical = json.dumps([definition.model_dump(mode="json") for definition in definitions], sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        pack = PublishedContentPack(pack_id=workspace.namespace, namespace=workspace.namespace, version=version, content_hash=content_hash, definitions=definitions)
        identity = (pack.pack_id, pack.version)
        if identity in self.published_packs:
            raise ValueError("published pack version already exists")
        self.published_packs[identity] = pack
        workspace.status = AuthoringWorkspaceStatus.PUBLISHED
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"workspace_id": workspace.workspace_id, "pack_id": pack.pack_id, "version": pack.version, "content_hash": content_hash})

    def _pack(self, pack_id: str, version: str) -> PublishedContentPack:
        pack = self.published_packs.get((pack_id, version))
        if pack is None:
            raise KeyError("published content pack does not exist")
        return pack

    async def _instantiate_encounter_template(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        campaign_id = command.campaign_id or str(command.payload.get("campaign_id", ""))
        pack = self._pack(str(command.payload.get("pack_id", "")), str(command.payload.get("version", "")))
        encounter_definition = pack.definition(str(command.payload.get("encounter_key", "")))
        if encounter_definition.definition_type != "encounter_template":
            raise ValueError("requested definition is not an encounter template")
        enemy_definition = pack.definition(str(encounter_definition.data["enemy_ref"]))
        if enemy_definition.definition_type != "npc_template":
            raise ValueError("encounter enemy_ref must reference npc_template")
        player_actor_id = str(command.payload.get("player_actor_id", ""))
        if player_actor_id not in self.actors or self.actors[player_actor_id].campaign_id != campaign_id:
            raise ValueError("player actor is not in campaign")
        enemy_actor_id = str(command.payload.get("enemy_actor_id") or new_id("npc"))
        npc = enemy_definition.data
        actor_receipt = await self._create_actor(
            CommandEnvelope(command_id=new_id("cmd"), command_type="CreateActor", campaign_id=campaign_id, payload={"actor_id": enemy_actor_id, "name": str(npc["name"]), "max_hp": int(npc["max_hp"]), "attack_bonus": int(npc["attack_bonus"]), "defense": int(npc["defense"]), "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": str(npc.get("behavior_profile", "aggressive_melee"))}}),
            principal,
        )
        encounter_id = str(command.payload.get("encounter_id") or new_id("enc"))
        encounter_receipt = await self._start_encounter(
            CommandEnvelope(command_id=new_id("cmd"), command_type="StartEncounter", campaign_id=campaign_id, payload={"encounter_id": encounter_id, "participants": [{"actor_id": player_actor_id, "side": str(encounter_definition.data.get("player_side", "heroes")), "position": int(encounter_definition.data.get("player_position", 0))}, {"actor_id": enemy_actor_id, "side": str(encounter_definition.data.get("enemy_side", "enemies")), "position": int(encounter_definition.data.get("enemy_position", 2))}]}),
            principal,
        )
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=actor_receipt.emitted_event_ids + encounter_receipt.emitted_event_ids, stream_versions={**actor_receipt.stream_versions, **encounter_receipt.stream_versions}, result={"campaign_id": campaign_id, "encounter_id": encounter_id, "enemy_actor_id": enemy_actor_id, "pack_id": pack.pack_id, "version": pack.version})

    async def _simulate_encounter_template(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal
        pack = self._pack(str(command.payload.get("pack_id", "")), str(command.payload.get("version", "")))
        encounter_definition = pack.definition(str(command.payload.get("encounter_key", "")))
        enemy_definition = pack.definition(str(encounter_definition.data["enemy_ref"]))
        runs = max(1, min(100, int(command.payload.get("runs", 5))))
        outcomes: dict[str, int] = {"heroes": 0, "enemies": 0}
        for index in range(runs):
            sandbox = PlatformEngineService()
            sim_principal = PrincipalContext(principal_id="simulation")
            campaign_id = f"sim_campaign_{index}"
            await sandbox.execute(CommandEnvelope(command_type="CreateCampaign", payload={"campaign_id": campaign_id, "seed": index + 1}), sim_principal)
            await sandbox.execute(CommandEnvelope(command_type="CreateActor", campaign_id=campaign_id, payload={"actor_id": "sim_hero", "name": "Simulation Hero", "max_hp": 22, "attack_bonus": 5, "defense": 13, "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": "aggressive_melee"}}), sim_principal)
            npc = enemy_definition.data
            await sandbox.execute(CommandEnvelope(command_type="CreateActor", campaign_id=campaign_id, payload={"actor_id": "sim_enemy", "name": str(npc["name"]), "max_hp": int(npc["max_hp"]), "attack_bonus": int(npc["attack_bonus"]), "defense": int(npc["defense"]), "controller": {"controller_type": "simple_npc", "controller_version": "1", "behavior_profile_ref": str(npc.get("behavior_profile", "aggressive_melee"))}}), sim_principal)
            await sandbox.execute(CommandEnvelope(command_type="StartEncounter", campaign_id=campaign_id, payload={"encounter_id": "sim_encounter", "participants": [{"actor_id": "sim_hero", "side": "heroes", "position": int(encounter_definition.data.get("player_position", 0))}, {"actor_id": "sim_enemy", "side": "enemies", "position": int(encounter_definition.data.get("enemy_position", 2))}]}), sim_principal)
            winner = sandbox.encounters["sim_encounter"].winner_side
            if winner in outcomes:
                outcomes[winner] += 1
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, result={"pack_id": pack.pack_id, "version": pack.version, "encounter_key": encounter_definition.key, "runs": runs, "outcomes": outcomes})

    def authoring_workspace_projection(self, workspace_id: str) -> dict[str, Any]:
        return {"data": self.authoring_workspaces[workspace_id].model_dump(mode="json"), "meta": {"schema_version": "1.0"}}

    def published_pack_projection(self, pack_id: str, version: str) -> dict[str, Any]:
        return {"data": self._pack(pack_id, version).model_dump(mode="json"), "meta": {"schema_version": "1.0"}}
