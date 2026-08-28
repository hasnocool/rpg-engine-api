from rpg_engine_api.domain.composition import reduce_faction, reduce_party, reduce_vendor
from rpg_engine_api.domain.events import DomainEvent


def event(kind: str, stream: str, payload: dict[str, object], *, version: int = 1):
    return DomainEvent(event_type=kind, campaign_id="cmp", stream_id=stream, stream_version=version, command_id="cmd", payload=payload)


def test_party_faction_and_vendor_reducers() -> None:
    party=reduce_party(None,event("PartyCreated","party:p",{"party_id":"p","name":"Heroes","member_actor_ids":["a"],"leader_actor_id":"a"}))
    party=reduce_party(party,event("PartyMemberAdded","party:p",{"actor_id":"b"},version=2)); assert party.member_actor_ids==["a","b"]
    faction=reduce_faction(None,event("FactionCreated","faction:f",{"faction_id":"f","name":"Town"})); faction=reduce_faction(faction,event("FactionReputationChanged","faction:f",{"actor_id":"a","reputation":15},version=2)); assert faction.reputation_by_actor["a"]==15
    vendor=reduce_vendor(None,event("VendorCreated","vendor:v",{"vendor_id":"v","name":"Smith","stock":{"sword":2},"prices":{"sword":5},"currency":50})); vendor=reduce_vendor(vendor,event("VendorItemSold","vendor:v",{"item_id":"sword","vendor_currency_after":55},version=2)); assert vendor.stock["sword"]==1 and vendor.currency==55
