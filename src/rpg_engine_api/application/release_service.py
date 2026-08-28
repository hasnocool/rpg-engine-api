from collections import Counter
from typing import Any

from rpg_engine_api.application.durable_service import DurableEngineService
from rpg_engine_api.domain.actor import reduce_actor
from rpg_engine_api.domain.campaign import CampaignState, reduce_campaign
from rpg_engine_api.domain.commands import CommandEnvelope, CommandReceipt, CommandStatus, PrincipalContext
from rpg_engine_api.domain.composition import (
    CampaignDraftState, CampaignDraftStatus, FactionState, PartyState, VendorState, WorldEnvironmentState,
    reduce_campaign_draft, reduce_environment, reduce_faction, reduce_party, reduce_vendor,
)
from rpg_engine_api.domain.dice import DeterministicRng
from rpg_engine_api.domain.events import DomainEvent
from rpg_engine_api.domain.ids import new_id
from rpg_engine_api.domain.session import SessionInvitationStatus, reduce_session
from rpg_engine_api.domain.timeline import TimelineRuntime, TimeoutPolicy, TimingMode


CAMPAIGN_TEMPLATES: dict[str, dict[str, object]] = {
    "classic_turn_based": {"timing_mode": "turn_based", "timeout_policy": "forfeit_turn", "decision_duration": None},
    "fast_timed_turns": {"timing_mode": "timed_turn_based", "timeout_policy": "auto_defend", "decision_duration": 30},
    "active_time_party_rpg": {"timing_mode": "active_time", "timeout_policy": "ai_control", "decision_duration": 15},
    "real_time_with_pause": {"timing_mode": "real_time_with_pause", "timeout_policy": "pause_game", "decision_duration": 10},
}


class ReleaseCandidateEngineService(DurableEngineService):
    """Composition/runtime layer closing major v0.7-v1.0 campaign-play gaps."""

    OWNER_COMMANDS = DurableEngineService.OWNER_COMMANDS | {
        "CreateParty", "AddPartyMember", "RemovePartyMember", "SetPartyLeader", "CreateFaction", "ChangeFactionReputation",
        "CreateVendor", "RestockVendor", "ConfigureWorldEnvironment", "RollWeather", "CreateSessionInvitation",
        "RevokeSessionInvitation", "RevokeActorControl",
    }
    ACTOR_COMMANDS = DurableEngineService.ACTOR_COMMANDS | {"BuyFromVendor", "SellToVendor"}

    def __init__(self, store: Any | None = None) -> None:
        super().__init__(store=store)
        self.campaign_drafts: dict[str, CampaignDraftState] = {}
        self.parties: dict[str, PartyState] = {}
        self.factions: dict[str, FactionState] = {}
        self.vendors: dict[str, VendorState] = {}
        self.world_environments: dict[str, WorldEnvironmentState] = {}

    async def _dispatch(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        handlers = {
            "CreateCampaignDraft": self._create_campaign_draft, "ConfigureCampaignDraft": self._configure_campaign_draft,
            "ValidateCampaignDraft": self._validate_campaign_draft, "FinalizeCampaignDraft": self._finalize_campaign_draft,
            "CreateParty": self._create_party, "AddPartyMember": self._add_party_member, "RemovePartyMember": self._remove_party_member,
            "SetPartyLeader": self._set_party_leader, "CreateFaction": self._create_faction, "ChangeFactionReputation": self._change_faction_reputation,
            "CreateVendor": self._create_vendor, "RestockVendor": self._restock_vendor, "BuyFromVendor": self._buy_from_vendor,
            "SellToVendor": self._sell_to_vendor, "ConfigureWorldEnvironment": self._configure_world_environment, "RollWeather": self._roll_weather,
            "CreateSessionInvitation": self._create_session_invitation, "AcceptSessionInvitation": self._accept_session_invitation,
            "RevokeSessionInvitation": self._revoke_session_invitation, "LeaveGameSession": self._leave_game_session,
            "RevokeActorControl": self._revoke_actor_control,
        }
        handler = handlers.get(command.command_type)
        if handler is not None:
            return await handler(command, principal)
        return await super()._dispatch(command, principal)

    @staticmethod
    def _draft_errors(draft: CampaignDraftState) -> list[str]:
        errors: list[str] = []
        if not draft.name.strip(): errors.append("campaign name is required")
        if draft.template_id not in CAMPAIGN_TEMPLATES: errors.append("unknown campaign template")
        try: TimingMode(draft.timing_mode)
        except ValueError: errors.append("unsupported timing mode")
        try: TimeoutPolicy(draft.timeout_policy)
        except ValueError: errors.append("unsupported timeout policy")
        if draft.decision_duration is not None and int(draft.decision_duration) < 0: errors.append("decision duration must be non-negative")
        return errors

    def _owned_draft(self, draft_id: str, principal: PrincipalContext) -> CampaignDraftState:
        draft = self.campaign_drafts.get(draft_id)
        if draft is None: raise KeyError("campaign draft does not exist")
        if draft.owner_id != principal.principal_id and not self._privileged(principal): raise ValueError("campaign draft belongs to another principal")
        if draft.status in {CampaignDraftStatus.FINALIZED, CampaignDraftStatus.CANCELLED}: raise ValueError("campaign draft is no longer editable")
        return draft

    async def _create_campaign_draft(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        draft_id = str(command.payload.get("draft_id") or new_id("campdraft")); campaign_id = str(command.payload.get("campaign_id") or new_id("cmp"))
        if draft_id in self.campaign_drafts or campaign_id in self.campaigns: raise ValueError("draft or campaign ID already exists")
        template_id = str(command.payload.get("template_id", "classic_turn_based")); defaults = CAMPAIGN_TEMPLATES.get(template_id, CAMPAIGN_TEMPLATES["classic_turn_based"])
        stream_id = f"campaign_draft:{draft_id}"
        event = DomainEvent(event_type="CampaignDraftCreated", campaign_id=campaign_id, stream_id=stream_id, command_id=command.command_id, correlation_id=command.command_id, payload={"draft_id": draft_id, "owner_id": principal.principal_id, "name": str(command.payload.get("name", "Untitled Campaign")), "seed": command.payload.get("seed", 1), "template_id": template_id, "timing_mode": command.payload.get("timing_mode", defaults["timing_mode"]), "timeout_policy": command.payload.get("timeout_policy", defaults["timeout_policy"]), "decision_duration": command.payload.get("decision_duration", defaults["decision_duration"]), "world_name": str(command.payload.get("world_name", "World"))})
        stored = await self.store.append(stream_id, 0, (event,)); self.campaign_drafts[draft_id] = reduce_campaign_draft(None, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"draft_id": draft_id, "campaign_id": campaign_id})

    async def _configure_campaign_draft(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        draft = self._owned_draft(str(command.payload.get("draft_id", "")), principal); stream_id = f"campaign_draft:{draft.draft_id}"; expected = await self.store.current_version(stream_id)
        allowed = {key: value for key, value in command.payload.items() if key in {"name","seed","template_id","timing_mode","timeout_policy","decision_duration","world_name"}}
        if "template_id" in allowed and str(allowed["template_id"]) in CAMPAIGN_TEMPLATES:
            defaults = CAMPAIGN_TEMPLATES[str(allowed["template_id"])]
            for key, value in defaults.items(): allowed.setdefault(key, value)
        event = DomainEvent(event_type="CampaignDraftConfigured", campaign_id=draft.campaign_id, stream_id=stream_id, command_id=command.command_id, correlation_id=command.command_id, payload=allowed)
        stored = await self.store.append(stream_id, expected, (event,)); self.campaign_drafts[draft.draft_id] = reduce_campaign_draft(draft, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"draft_id": draft.draft_id})

    async def _validate_campaign_draft(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        draft = self._owned_draft(str(command.payload.get("draft_id", "")), principal); errors = self._draft_errors(draft); stream_id = f"campaign_draft:{draft.draft_id}"; expected = await self.store.current_version(stream_id)
        event = DomainEvent(event_type="CampaignDraftValidated", campaign_id=draft.campaign_id, stream_id=stream_id, command_id=command.command_id, correlation_id=command.command_id, payload={"errors": errors})
        stored = await self.store.append(stream_id, expected, (event,)); self.campaign_drafts[draft.draft_id] = reduce_campaign_draft(draft, stored[0])
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={stream_id: stored[0].stream_version}, result={"draft_id": draft.draft_id, "valid": not errors, "errors": errors})

    async def _finalize_campaign_draft(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        draft = self._owned_draft(str(command.payload.get("draft_id", "")), principal); errors = self._draft_errors(draft)
        if errors: raise ValueError("campaign draft is invalid: " + "; ".join(errors))
        if draft.campaign_id in self.campaigns: raise ValueError("campaign already exists")
        draft_stream = f"campaign_draft:{draft.draft_id}"; campaign_stream = f"campaign:{draft.campaign_id}"
        created = DomainEvent(event_type="CampaignCreated", campaign_id=draft.campaign_id, stream_id=campaign_stream, command_id=command.command_id, correlation_id=command.command_id, payload={"name": draft.name, "seed": draft.seed, "owner_id": draft.owner_id})
        timing = DomainEvent(event_type="CampaignTimingConfigured", campaign_id=draft.campaign_id, stream_id=campaign_stream, command_id=command.command_id, correlation_id=command.command_id, payload={"mode": draft.timing_mode, "decision_duration": draft.decision_duration, "timeout_policy": draft.timeout_policy, "configured_by": principal.principal_id})
        finalized = DomainEvent(event_type="CampaignDraftFinalized", campaign_id=draft.campaign_id, stream_id=draft_stream, command_id=command.command_id, correlation_id=command.command_id, payload={"draft_id": draft.draft_id})
        stored = await self.store.append_many(((campaign_stream, 0, (created, timing)), (draft_stream, await self.store.current_version(draft_stream), (finalized,))))
        campaign: CampaignState | None = None
        for event in stored[campaign_stream]: campaign = reduce_campaign(campaign, event)
        assert campaign is not None
        self.campaigns[draft.campaign_id] = campaign; self.campaign_drafts[draft.draft_id] = reduce_campaign_draft(draft, stored[draft_stream][0]); self._rng[draft.campaign_id] = DeterministicRng(draft.seed)
        self.timelines[draft.campaign_id] = TimelineRuntime(mode=TimingMode(draft.timing_mode), default_decision_duration=draft.decision_duration, timeout_policy=TimeoutPolicy(draft.timeout_policy))
        all_events = stored[campaign_stream] + stored[draft_stream]
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=tuple(event.event_id for event in all_events), stream_versions={campaign_stream: stored[campaign_stream][-1].stream_version, draft_stream: stored[draft_stream][-1].stream_version}, result={"draft_id": draft.draft_id, "campaign_id": draft.campaign_id})

    async def _append_single(self, command: CommandEnvelope, stream_id: str, event: DomainEvent) -> DomainEvent:
        stored = await self.store.append(stream_id, await self.store.current_version(stream_id), (event,)); return stored[0]

    async def _create_party(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; campaign_id = command.campaign_id or str(command.payload.get("campaign_id", "")); party_id = str(command.payload.get("party_id") or new_id("party"))
        if party_id in self.parties: raise ValueError("party already exists")
        members = [str(item) for item in command.payload.get("member_actor_ids", [])]
        if any(actor_id not in self.actors or self.actors[actor_id].campaign_id != campaign_id for actor_id in members): raise ValueError("party member is not in campaign")
        leader = command.payload.get("leader_actor_id") or (members[0] if members else None)
        event = DomainEvent(event_type="PartyCreated", campaign_id=campaign_id, stream_id=f"party:{party_id}", command_id=command.command_id, correlation_id=command.command_id, payload={"party_id": party_id, "name": str(command.payload.get("name", "Party")), "member_actor_ids": members, "leader_actor_id": leader})
        stored = await self.store.append(f"party:{party_id}", 0, (event,)); self.parties[party_id] = reduce_party(None, stored[0]); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={f"party:{party_id}": 1}, result={"campaign_id": campaign_id, "party_id": party_id})

    async def _party_event(self, command: CommandEnvelope, event_type: str, payload: dict[str, object]) -> CommandReceipt:
        party = self.parties.get(str(command.payload.get("party_id", "")))
        if party is None: raise KeyError("party does not exist")
        actor_id = str(payload["actor_id"])
        if actor_id not in self.actors or self.actors[actor_id].campaign_id != party.campaign_id: raise ValueError("actor is not in party campaign")
        event = DomainEvent(event_type=event_type, campaign_id=party.campaign_id, stream_id=f"party:{party.party_id}", command_id=command.command_id, correlation_id=command.command_id, payload=payload); stored = await self._append_single(command, event.stream_id, event); self.parties[party.party_id] = reduce_party(party, stored)
        return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored.event_id,), stream_versions={stored.stream_id: stored.stream_version}, result={"party_id": party.party_id, "actor_id": actor_id})

    async def _add_party_member(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt: del principal; return await self._party_event(command, "PartyMemberAdded", {"actor_id": str(command.payload.get("actor_id", ""))})
    async def _remove_party_member(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt: del principal; return await self._party_event(command, "PartyMemberRemoved", {"actor_id": str(command.payload.get("actor_id", ""))})
    async def _set_party_leader(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; party = self.parties.get(str(command.payload.get("party_id", ""))); actor_id = str(command.payload.get("actor_id", ""))
        if party is None: raise KeyError("party does not exist")
        if actor_id not in party.member_actor_ids: raise ValueError("party leader must be a member")
        return await self._party_event(command, "PartyLeaderChanged", {"actor_id": actor_id})

    async def _create_faction(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; campaign_id = command.campaign_id or str(command.payload.get("campaign_id", "")); faction_id = str(command.payload.get("faction_id") or new_id("faction"))
        if faction_id in self.factions: raise ValueError("faction already exists")
        event = DomainEvent(event_type="FactionCreated", campaign_id=campaign_id, stream_id=f"faction:{faction_id}", command_id=command.command_id, correlation_id=command.command_id, payload={"faction_id": faction_id, "name": str(command.payload.get("name", "Faction"))}); stored = await self.store.append(event.stream_id, 0, (event,)); self.factions[faction_id] = reduce_faction(None, stored[0]); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored[0].event_id,), stream_versions={event.stream_id: 1}, result={"faction_id": faction_id, "campaign_id": campaign_id})

    async def _change_faction_reputation(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; faction = self.factions.get(str(command.payload.get("faction_id", ""))); actor_id = str(command.payload.get("actor_id", ""))
        if faction is None: raise KeyError("faction does not exist")
        if actor_id not in self.actors or self.actors[actor_id].campaign_id != faction.campaign_id: raise ValueError("actor is not in faction campaign")
        current = faction.reputation_by_actor.get(actor_id, 0); reputation = max(-100, min(100, current + int(command.payload.get("delta", 0))))
        event = DomainEvent(event_type="FactionReputationChanged", campaign_id=faction.campaign_id, stream_id=f"faction:{faction.faction_id}", actor_id=actor_id, command_id=command.command_id, correlation_id=command.command_id, payload={"actor_id": actor_id, "reputation": reputation, "delta": reputation-current}); stored = await self._append_single(command, event.stream_id, event); self.factions[faction.faction_id] = reduce_faction(faction, stored); return CommandReceipt(command_id=command.command_id, status=CommandStatus.ACCEPTED, emitted_event_ids=(stored.event_id,), stream_versions={stored.stream_id: stored.stream_version}, result={"faction_id": faction.faction_id, "actor_id": actor_id, "reputation": reputation})

    async def _create_vendor(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; campaign_id = command.campaign_id or str(command.payload.get("campaign_id", "")); vendor_id = str(command.payload.get("vendor_id") or new_id("vendor"))
        stock = {str(k): max(0, int(v)) for k,v in dict(command.payload.get("stock", {})).items()}; prices = {str(k): max(0, int(v)) for k,v in dict(command.payload.get("prices", {})).items()}
        event = DomainEvent(event_type="VendorCreated", campaign_id=campaign_id, stream_id=f"vendor:{vendor_id}", command_id=command.command_id, correlation_id=command.command_id, payload={"vendor_id": vendor_id, "name": str(command.payload.get("name", "Vendor")), "stock": stock, "prices": prices, "currency": int(command.payload.get("currency", 1000)), "buyback_percent": max(0,min(100,int(command.payload.get("buyback_percent",50))))}); stored = await self.store.append(event.stream_id, 0, (event,)); self.vendors[vendor_id]=reduce_vendor(None,stored[0]); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored[0].event_id,),stream_versions={event.stream_id:1},result={"vendor_id":vendor_id,"campaign_id":campaign_id})

    async def _restock_vendor(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; vendor=self.vendors.get(str(command.payload.get("vendor_id","")))
        if vendor is None: raise KeyError("vendor does not exist")
        event=DomainEvent(event_type="VendorRestocked",campaign_id=vendor.campaign_id,stream_id=f"vendor:{vendor.vendor_id}",command_id=command.command_id,correlation_id=command.command_id,payload={"stock_delta":dict(command.payload.get("stock_delta",{})),"prices":dict(command.payload.get("prices",{}))}); stored=await self._append_single(command,event.stream_id,event); self.vendors[vendor.vendor_id]=reduce_vendor(vendor,stored); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored.event_id,),stream_versions={stored.stream_id:stored.stream_version},result={"vendor_id":vendor.vendor_id})

    async def _buy_from_vendor(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; actor_id=command.actor_id or str(command.payload.get("actor_id","")); actor=self.actors.get(actor_id); vendor=self.vendors.get(str(command.payload.get("vendor_id",""))); item_id=str(command.payload.get("item_id",""))
        if actor is None or vendor is None: raise KeyError("actor or vendor does not exist")
        if actor.campaign_id != vendor.campaign_id: raise ValueError("actor and vendor are in different campaigns")
        if vendor.stock.get(item_id,0)<=0: raise ValueError("vendor item is out of stock")
        if item_id not in vendor.prices: raise ValueError("vendor has no price for item")
        price=vendor.prices[item_id]
        if actor.currency<price: raise ValueError("insufficient currency")
        astream=f"actor:{actor_id}"; vstream=f"vendor:{vendor.vendor_id}"
        ae=DomainEvent(event_type="ItemPurchased",campaign_id=actor.campaign_id,stream_id=astream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"item_id":item_id,"price":price,"currency_after":actor.currency-price,"vendor_id":vendor.vendor_id})
        ve=DomainEvent(event_type="VendorItemSold",campaign_id=actor.campaign_id,stream_id=vstream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"item_id":item_id,"price":price,"vendor_currency_after":vendor.currency+price,"actor_id":actor_id})
        stored=await self.store.append_many(((astream,await self.store.current_version(astream),(ae,)),(vstream,await self.store.current_version(vstream),(ve,))))
        self.actors[actor_id]=reduce_actor(actor,stored[astream][0]); self.vendors[vendor.vendor_id]=reduce_vendor(vendor,stored[vstream][0]); events=stored[astream]+stored[vstream]
        return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=tuple(e.event_id for e in events),stream_versions={astream:stored[astream][-1].stream_version,vstream:stored[vstream][-1].stream_version},result={"actor_id":actor_id,"vendor_id":vendor.vendor_id,"item_id":item_id,"price":price})

    async def _sell_to_vendor(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; actor_id=command.actor_id or str(command.payload.get("actor_id","")); actor=self.actors.get(actor_id); vendor=self.vendors.get(str(command.payload.get("vendor_id",""))); item_id=str(command.payload.get("item_id",""))
        if actor is None or vendor is None: raise KeyError("actor or vendor does not exist")
        if actor.campaign_id!=vendor.campaign_id: raise ValueError("actor and vendor are in different campaigns")
        if item_id not in actor.inventory: raise ValueError("actor does not own item")
        price=max(0,vendor.prices.get(item_id,0)*vendor.buyback_percent//100)
        if vendor.currency<price: raise ValueError("vendor cannot afford item")
        astream=f"actor:{actor_id}"; vstream=f"vendor:{vendor.vendor_id}"
        ae=DomainEvent(event_type="ItemSold",campaign_id=actor.campaign_id,stream_id=astream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"item_id":item_id,"price":price,"currency_after":actor.currency+price,"vendor_id":vendor.vendor_id})
        ve=DomainEvent(event_type="VendorItemBought",campaign_id=actor.campaign_id,stream_id=vstream,actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"item_id":item_id,"price":price,"vendor_currency_after":vendor.currency-price,"actor_id":actor_id})
        stored=await self.store.append_many(((astream,await self.store.current_version(astream),(ae,)),(vstream,await self.store.current_version(vstream),(ve,))))
        self.actors[actor_id]=reduce_actor(actor,stored[astream][0]); self.vendors[vendor.vendor_id]=reduce_vendor(vendor,stored[vstream][0]); events=stored[astream]+stored[vstream]
        return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=tuple(e.event_id for e in events),stream_versions={astream:stored[astream][-1].stream_version,vstream:stored[vstream][-1].stream_version},result={"actor_id":actor_id,"vendor_id":vendor.vendor_id,"item_id":item_id,"price":price})

    async def _configure_world_environment(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; campaign_id=command.campaign_id or str(command.payload.get("campaign_id","")); environment_id=str(command.payload.get("environment_id") or f"env_{campaign_id}")
        if environment_id in self.world_environments: raise ValueError("world environment already exists")
        event=DomainEvent(event_type="WorldEnvironmentConfigured",campaign_id=campaign_id,stream_id=f"environment:{environment_id}",command_id=command.command_id,correlation_id=command.command_id,payload={"environment_id":environment_id,"calendar_name":str(command.payload.get("calendar_name","Common Calendar")),"day_length":max(1,int(command.payload.get("day_length",1440))),"epoch_day":int(command.payload.get("epoch_day",1)),"weather":str(command.payload.get("weather","clear"))}); stored=await self.store.append(event.stream_id,0,(event,)); self.world_environments[environment_id]=reduce_environment(None,stored[0]); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored[0].event_id,),stream_versions={event.stream_id:1},result={"campaign_id":campaign_id,"environment_id":environment_id})

    async def _roll_weather(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        del principal; environment=self.world_environments.get(str(command.payload.get("environment_id",f"env_{command.campaign_id or ''}")))
        if environment is None: raise KeyError("world environment does not exist")
        result=self._rng[environment.campaign_id].roll("1d6",stream="world"); weather={1:"storm",2:"rain",3:"fog",4:"clear",5:"clear",6:"wind"}[result.total]
        event=DomainEvent(event_type="WeatherChanged",campaign_id=environment.campaign_id,stream_id=f"environment:{environment.environment_id}",command_id=command.command_id,correlation_id=command.command_id,payload={"weather":weather,"rolls":result.rolls,"rng_stream":"world","rng_sequence":result.rng_sequence}); stored=await self._append_single(command,event.stream_id,event); self.world_environments[environment.environment_id]=reduce_environment(environment,stored); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored.event_id,),stream_versions={stored.stream_id:stored.stream_version},result={"environment_id":environment.environment_id,"weather":weather,"roll":result.total})

    async def _advance_simulation_time(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        receipt=await super()._advance_simulation_time(command,principal); campaign_id=command.campaign_id or str(command.payload.get("campaign_id","")); extra_ids:list[str]=[]; extra_versions:dict[str,int]={}; weather=[]
        for triggered in receipt.result.get("triggered_scheduled_events",[]):
            if isinstance(triggered,dict) and triggered.get("kind")=="weather_roll":
                env_id=str(triggered.get("payload",{}).get("environment_id",f"env_{campaign_id}")); child=await self._roll_weather(CommandEnvelope(command_id=new_id("cmd"),command_type="RollWeather",campaign_id=campaign_id,payload={"environment_id":env_id}),principal); extra_ids.extend(child.emitted_event_ids); extra_versions.update(child.stream_versions); weather.append(child.result)
        return receipt.model_copy(update={"emitted_event_ids":receipt.emitted_event_ids+tuple(extra_ids),"stream_versions":{**receipt.stream_versions,**extra_versions},"result":{**receipt.result,"weather_updates":weather}})

    async def _create_session_invitation(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session=self.sessions.get(str(command.payload.get("session_id","")))
        if session is None: raise KeyError("session does not exist")
        if principal.principal_id!=session.owner_id and not self._privileged(principal): raise ValueError("only session owner can invite")
        invitation_id=str(command.payload.get("invitation_id") or new_id("invite")); target=str(command.payload.get("principal_id",""))
        if not target: raise ValueError("invitation requires principal_id")
        event=DomainEvent(event_type="SessionInvitationCreated",campaign_id=session.campaign_id,stream_id=f"session:{session.session_id}",command_id=command.command_id,correlation_id=command.command_id,payload={"invitation_id":invitation_id,"principal_id":target,"role":str(command.payload.get("role","player")),"status":SessionInvitationStatus.PENDING.value}); stored=await self._append_single(command,event.stream_id,event); self.sessions[session.session_id]=reduce_session(session,stored); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored.event_id,),stream_versions={stored.stream_id:stored.stream_version},result={"session_id":session.session_id,"invitation_id":invitation_id})

    async def _accept_session_invitation(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session=self.sessions.get(str(command.payload.get("session_id",""))); invitation_id=str(command.payload.get("invitation_id",""))
        if session is None: raise KeyError("session does not exist")
        invitation=session.invitations.get(invitation_id)
        if invitation is None or invitation.status!=SessionInvitationStatus.PENDING: raise ValueError("invitation is not pending")
        if invitation.principal_id!=principal.principal_id: raise ValueError("invitation belongs to another principal")
        event=DomainEvent(event_type="SessionInvitationAccepted",campaign_id=session.campaign_id,stream_id=f"session:{session.session_id}",command_id=command.command_id,correlation_id=command.command_id,payload={"invitation_id":invitation_id}); stored=await self._append_single(command,event.stream_id,event); self.sessions[session.session_id]=reduce_session(session,stored); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored.event_id,),stream_versions={stored.stream_id:stored.stream_version},result={"session_id":session.session_id,"principal_id":principal.principal_id})

    async def _revoke_session_invitation(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session=self.sessions.get(str(command.payload.get("session_id",""))); invitation_id=str(command.payload.get("invitation_id",""))
        if session is None: raise KeyError("session does not exist")
        if principal.principal_id!=session.owner_id and not self._privileged(principal): raise ValueError("only session owner can revoke invitation")
        invitation=session.invitations.get(invitation_id)
        if invitation is None or invitation.status!=SessionInvitationStatus.PENDING: raise ValueError("invitation is not pending")
        event=DomainEvent(event_type="SessionInvitationRevoked",campaign_id=session.campaign_id,stream_id=f"session:{session.session_id}",command_id=command.command_id,correlation_id=command.command_id,payload={"invitation_id":invitation_id}); stored=await self._append_single(command,event.stream_id,event); self.sessions[session.session_id]=reduce_session(session,stored); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored.event_id,),stream_versions={stored.stream_id:stored.stream_version},result={"session_id":session.session_id,"invitation_id":invitation_id})

    async def _leave_game_session(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session=self.sessions.get(str(command.payload.get("session_id","")))
        if session is None: raise KeyError("session does not exist")
        if principal.principal_id==session.owner_id: raise ValueError("session owner cannot leave without transferring ownership")
        if principal.principal_id not in session.members: raise ValueError("principal is not a session member")
        event=DomainEvent(event_type="SessionMemberLeft",campaign_id=session.campaign_id,stream_id=f"session:{session.session_id}",command_id=command.command_id,correlation_id=command.command_id,payload={"principal_id":principal.principal_id}); stored=await self._append_single(command,event.stream_id,event); self.sessions[session.session_id]=reduce_session(session,stored); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored.event_id,),stream_versions={stored.stream_id:stored.stream_version},result={"session_id":session.session_id,"principal_id":principal.principal_id})

    async def _revoke_actor_control(self, command: CommandEnvelope, principal: PrincipalContext) -> CommandReceipt:
        session=self.sessions.get(str(command.payload.get("session_id",""))); actor_id=str(command.payload.get("actor_id",""))
        if session is None: raise KeyError("session does not exist")
        if principal.principal_id!=session.owner_id and not self._privileged(principal): raise ValueError("only session owner can revoke actor control")
        event=DomainEvent(event_type="ActorControlRevoked",campaign_id=session.campaign_id,stream_id=f"session:{session.session_id}",actor_id=actor_id,command_id=command.command_id,correlation_id=command.command_id,payload={"actor_id":actor_id}); stored=await self._append_single(command,event.stream_id,event); self.sessions[session.session_id]=reduce_session(session,stored); return CommandReceipt(command_id=command.command_id,status=CommandStatus.ACCEPTED,emitted_event_ids=(stored.event_id,),stream_versions={stored.stream_id:stored.stream_version},result={"session_id":session.session_id,"actor_id":actor_id})

    def environment_projection(self, environment_id: str) -> dict[str,Any]:
        environment=self.world_environments[environment_id]; timeline=self.timelines.get(environment.campaign_id); now=timeline.clock.now if timeline else 0
        return {"data":{**environment.model_dump(mode="json"),"simulation_time":now,"day":environment.epoch_day+now//environment.day_length,"minute_of_day":now%environment.day_length},"meta":{"schema_version":"1.0"}}

    async def campaign_journal(self,campaign_id:str)->dict[str,Any]:
        events=[event for event in await self.store.read_all() if event.campaign_id==campaign_id]; categories:dict[str,int]=Counter()
        mapping={"Quest":"quest","Encounter":"combat","Attack":"combat","Dialogue":"social","Social":"social","Vendor":"economy","Item":"economy","ActorTravel":"exploration","Location":"exploration","WorldObject":"exploration","Weather":"world","Progression":"progression","Experience":"progression","ContentRevision":"content","GameSession":"session","Session":"session"}
        entries=[]
        for event in events:
            category=next((value for prefix,value in mapping.items() if event.event_type.startswith(prefix)),"system"); categories[category]+=1; entries.append({"sequence":event.sequence,"simulation_time":event.simulation_time,"category":category,"event_type":event.event_type,"actor_id":event.actor_id})
        return {"schema_version":"1.0","campaign_id":campaign_id,"entries":entries,"category_counts":dict(sorted(categories.items()))}

    async def character_journal(self,actor_id:str)->dict[str,Any]:
        actor=self.actors[actor_id]; campaign=await self.campaign_journal(actor.campaign_id); entries=[item for item in campaign["entries"] if item["actor_id"]==actor_id]; return {"schema_version":"1.0","actor_id":actor_id,"campaign_id":actor.campaign_id,"entries":entries}

    async def rebuild_from_store(self)->None:
        await super().rebuild_from_store(); self.campaign_drafts.clear(); self.parties.clear(); self.factions.clear(); self.vendors.clear(); self.world_environments.clear(); events=await self.store.read_all()
        for event in events:
            if event.stream_id.startswith("campaign_draft:"):
                key=event.stream_id.split(":",1)[1]; self.campaign_drafts[key]=reduce_campaign_draft(self.campaign_drafts.get(key),event)
            elif event.stream_id.startswith("party:"):
                key=event.stream_id.split(":",1)[1]; self.parties[key]=reduce_party(self.parties.get(key),event)
            elif event.stream_id.startswith("faction:"):
                key=event.stream_id.split(":",1)[1]; self.factions[key]=reduce_faction(self.factions.get(key),event)
            elif event.stream_id.startswith("vendor:"):
                key=event.stream_id.split(":",1)[1]; self.vendors[key]=reduce_vendor(self.vendors.get(key),event)
            elif event.stream_id.startswith("environment:"):
                key=event.stream_id.split(":",1)[1]; self.world_environments[key]=reduce_environment(self.world_environments.get(key),event)
        for event in events:
            if event.event_type=="WeatherChanged" and event.campaign_id in self._rng:
                self._rng[event.campaign_id].replay_roll("1d6",event.payload.get("rolls",()),stream="world",expected_sequence=int(event.payload["rng_sequence"]) if event.payload.get("rng_sequence") is not None else None)

    def live_snapshot(self,campaign_id:str)->dict[str,Any]:
        snapshot=super().live_snapshot(campaign_id); snapshot["parties"]={k:v.model_dump(mode="json") for k,v in sorted(self.parties.items()) if v.campaign_id==campaign_id}; snapshot["factions"]={k:v.model_dump(mode="json") for k,v in sorted(self.factions.items()) if v.campaign_id==campaign_id}; snapshot["vendors"]={k:v.model_dump(mode="json") for k,v in sorted(self.vendors.items()) if v.campaign_id==campaign_id}; snapshot["world_environments"]={k:self.environment_projection(k)["data"] for k,v in sorted(self.world_environments.items()) if v.campaign_id==campaign_id}; return snapshot

    async def replay_snapshot(self,campaign_id:str)->dict[str,Any]:
        snapshot=await super().replay_snapshot(campaign_id); parties:dict[str,PartyState]={}; factions:dict[str,FactionState]={}; vendors:dict[str,VendorState]={}; environments:dict[str,WorldEnvironmentState]={}
        for event in await self.store.read_all():
            if event.campaign_id!=campaign_id: continue
            if event.stream_id.startswith("party:"): key=event.stream_id.split(":",1)[1]; parties[key]=reduce_party(parties.get(key),event)
            elif event.stream_id.startswith("faction:"): key=event.stream_id.split(":",1)[1]; factions[key]=reduce_faction(factions.get(key),event)
            elif event.stream_id.startswith("vendor:"): key=event.stream_id.split(":",1)[1]; vendors[key]=reduce_vendor(vendors.get(key),event)
            elif event.stream_id.startswith("environment:"): key=event.stream_id.split(":",1)[1]; environments[key]=reduce_environment(environments.get(key),event)
        snapshot["parties"]={k:v.model_dump(mode="json") for k,v in sorted(parties.items())}; snapshot["factions"]={k:v.model_dump(mode="json") for k,v in sorted(factions.items())}; snapshot["vendors"]={k:v.model_dump(mode="json") for k,v in sorted(vendors.items())}; snapshot["world_environments"]={k:v.model_dump(mode="json") for k,v in sorted(environments.items())}; return snapshot

    @classmethod
    def capability_projection(cls)->dict[str,Any]:
        base=super().capability_projection(); data=dict(base["data"]); data["features"]=list(data.get("features",[]))+["campaign_drafts","campaign_templates","parties","session_invitations","factions_reputation","stocked_vendors","atomic_trade","world_calendar_weather","journals","atomic_multi_stream"] ; data["campaign_templates"]={key:dict(value) for key,value in CAMPAIGN_TEMPLATES.items()}; return {"data":data,"meta":{"schema_version":"1.1"}}
