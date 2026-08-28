from enum import StrEnum

from pydantic import BaseModel, Field

from rpg_engine_api.domain.events import DomainEvent


class CampaignDraftStatus(StrEnum):
    DRAFT = "draft"
    VALID = "valid"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"


class CampaignDraftState(BaseModel):
    schema_version: str = "1.0"
    draft_id: str
    campaign_id: str
    owner_id: str
    name: str = "Untitled Campaign"
    seed: int | str = 1
    template_id: str = "classic_turn_based"
    timing_mode: str = "turn_based"
    timeout_policy: str = "forfeit_turn"
    decision_duration: int | None = None
    world_name: str = "World"
    status: CampaignDraftStatus = CampaignDraftStatus.DRAFT
    errors: list[str] = Field(default_factory=list)
    stream_version: int = 0


class PartyState(BaseModel):
    schema_version: str = "1.0"
    party_id: str
    campaign_id: str
    name: str
    member_actor_ids: list[str] = Field(default_factory=list)
    leader_actor_id: str | None = None
    shared_currency: int = 0
    stream_version: int = 0


class FactionState(BaseModel):
    schema_version: str = "1.0"
    faction_id: str
    campaign_id: str
    name: str
    reputation_by_actor: dict[str, int] = Field(default_factory=dict)
    stream_version: int = 0


class VendorState(BaseModel):
    schema_version: str = "1.0"
    vendor_id: str
    campaign_id: str
    name: str
    stock: dict[str, int] = Field(default_factory=dict)
    prices: dict[str, int] = Field(default_factory=dict)
    currency: int = 1000
    buyback_percent: int = 50
    stream_version: int = 0


class WorldEnvironmentState(BaseModel):
    schema_version: str = "1.0"
    environment_id: str
    campaign_id: str
    calendar_name: str = "Common Calendar"
    day_length: int = 1440
    epoch_day: int = 1
    weather: str = "clear"
    stream_version: int = 0


def reduce_campaign_draft(state: CampaignDraftState | None, event: DomainEvent) -> CampaignDraftState:
    if event.event_type == "CampaignDraftCreated":
        return CampaignDraftState(
            draft_id=str(event.payload["draft_id"]),
            campaign_id=event.campaign_id,
            owner_id=str(event.payload["owner_id"]),
            name=str(event.payload.get("name", "Untitled Campaign")),
            seed=event.payload.get("seed", 1),
            template_id=str(event.payload.get("template_id", "classic_turn_based")),
            timing_mode=str(event.payload.get("timing_mode", "turn_based")),
            timeout_policy=str(event.payload.get("timeout_policy", "forfeit_turn")),
            decision_duration=event.payload.get("decision_duration"),
            world_name=str(event.payload.get("world_name", "World")),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("campaign draft stream must start with CampaignDraftCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "CampaignDraftConfigured":
        for field_name in ("name", "seed", "template_id", "timing_mode", "timeout_policy", "decision_duration", "world_name"):
            if field_name in event.payload:
                setattr(next_state, field_name, event.payload[field_name])
        next_state.status = CampaignDraftStatus.DRAFT
        next_state.errors = []
    elif event.event_type == "CampaignDraftValidated":
        next_state.errors = [str(item) for item in event.payload.get("errors", [])]
        next_state.status = CampaignDraftStatus.VALID if not next_state.errors else CampaignDraftStatus.DRAFT
    elif event.event_type == "CampaignDraftFinalized":
        next_state.status = CampaignDraftStatus.FINALIZED
    elif event.event_type == "CampaignDraftCancelled":
        next_state.status = CampaignDraftStatus.CANCELLED
    return next_state


def reduce_party(state: PartyState | None, event: DomainEvent) -> PartyState:
    if event.event_type == "PartyCreated":
        members = sorted({str(item) for item in event.payload.get("member_actor_ids", [])})
        return PartyState(
            party_id=str(event.payload["party_id"]),
            campaign_id=event.campaign_id,
            name=str(event.payload.get("name", "Party")),
            member_actor_ids=members,
            leader_actor_id=event.payload.get("leader_actor_id"),
            shared_currency=int(event.payload.get("shared_currency", 0)),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("party stream must start with PartyCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "PartyMemberAdded":
        actor_id = str(event.payload["actor_id"])
        if actor_id not in next_state.member_actor_ids:
            next_state.member_actor_ids.append(actor_id)
            next_state.member_actor_ids.sort()
    elif event.event_type == "PartyMemberRemoved":
        actor_id = str(event.payload["actor_id"])
        next_state.member_actor_ids = [item for item in next_state.member_actor_ids if item != actor_id]
        if next_state.leader_actor_id == actor_id:
            next_state.leader_actor_id = next_state.member_actor_ids[0] if next_state.member_actor_ids else None
    elif event.event_type == "PartyLeaderChanged":
        next_state.leader_actor_id = str(event.payload["actor_id"])
    return next_state


def reduce_faction(state: FactionState | None, event: DomainEvent) -> FactionState:
    if event.event_type == "FactionCreated":
        return FactionState(
            faction_id=str(event.payload["faction_id"]),
            campaign_id=event.campaign_id,
            name=str(event.payload["name"]),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("faction stream must start with FactionCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "FactionReputationChanged":
        next_state.reputation_by_actor[str(event.payload["actor_id"])] = int(event.payload["reputation"])
    return next_state


def reduce_vendor(state: VendorState | None, event: DomainEvent) -> VendorState:
    if event.event_type == "VendorCreated":
        return VendorState(
            vendor_id=str(event.payload["vendor_id"]),
            campaign_id=event.campaign_id,
            name=str(event.payload["name"]),
            stock={str(key): int(value) for key, value in dict(event.payload.get("stock", {})).items()},
            prices={str(key): int(value) for key, value in dict(event.payload.get("prices", {})).items()},
            currency=int(event.payload.get("currency", 1000)),
            buyback_percent=int(event.payload.get("buyback_percent", 50)),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("vendor stream must start with VendorCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "VendorRestocked":
        for item_id, quantity in dict(event.payload.get("stock_delta", {})).items():
            next_state.stock[str(item_id)] = max(0, next_state.stock.get(str(item_id), 0) + int(quantity))
        for item_id, price in dict(event.payload.get("prices", {})).items():
            next_state.prices[str(item_id)] = int(price)
    elif event.event_type == "VendorItemSold":
        item_id = str(event.payload["item_id"])
        next_state.stock[item_id] = max(0, next_state.stock.get(item_id, 0) - 1)
        next_state.currency = int(event.payload["vendor_currency_after"])
    elif event.event_type == "VendorItemBought":
        item_id = str(event.payload["item_id"])
        next_state.stock[item_id] = next_state.stock.get(item_id, 0) + 1
        next_state.currency = int(event.payload["vendor_currency_after"])
    return next_state


def reduce_environment(state: WorldEnvironmentState | None, event: DomainEvent) -> WorldEnvironmentState:
    if event.event_type == "WorldEnvironmentConfigured":
        return WorldEnvironmentState(
            environment_id=str(event.payload["environment_id"]),
            campaign_id=event.campaign_id,
            calendar_name=str(event.payload.get("calendar_name", "Common Calendar")),
            day_length=int(event.payload.get("day_length", 1440)),
            epoch_day=int(event.payload.get("epoch_day", 1)),
            weather=str(event.payload.get("weather", "clear")),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("environment stream must start with WorldEnvironmentConfigured")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "WeatherChanged":
        next_state.weather = str(event.payload["weather"])
    return next_state
