from pydantic import BaseModel, Field

from .events import DomainEvent


class CampaignState(BaseModel):
    schema_version: str = "1.0"
    campaign_id: str
    name: str
    seed: int | str
    owner_id: str
    stream_version: int = 0
    actor_ids: list[str] = Field(default_factory=list)


def reduce_campaign(state: CampaignState | None, event: DomainEvent) -> CampaignState:
    if event.event_type == "CampaignCreated":
        return CampaignState(
            campaign_id=event.campaign_id,
            name=str(event.payload["name"]),
            seed=event.payload["seed"],
            owner_id=str(event.payload["owner_id"]),
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("campaign stream must start with CampaignCreated")
    state = state.model_copy(deep=True)
    state.stream_version = event.stream_version
    if event.event_type == "ActorRegistered":
        actor_id = str(event.payload["actor_id"])
        if actor_id not in state.actor_ids:
            state.actor_ids.append(actor_id)
    return state
