from enum import StrEnum

from pydantic import BaseModel, Field

from rpg_engine_api.domain.events import DomainEvent


class SessionStatus(StrEnum):
    LOBBY = "lobby"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class SessionInvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


class SessionMember(BaseModel):
    principal_id: str
    role: str = "player"
    ready: bool = False


class SessionInvitation(BaseModel):
    invitation_id: str
    principal_id: str
    role: str = "player"
    status: SessionInvitationStatus = SessionInvitationStatus.PENDING


class GameSessionState(BaseModel):
    schema_version: str = "1.2"
    session_id: str
    campaign_id: str
    owner_id: str
    status: SessionStatus = SessionStatus.LOBBY
    members: dict[str, SessionMember] = Field(default_factory=dict)
    invitations: dict[str, SessionInvitation] = Field(default_factory=dict)
    actor_controls: dict[str, str] = Field(default_factory=dict)
    opened_at_sequence: int | None = None
    paused_at_sequence: int | None = None
    closed_at_sequence: int | None = None
    stream_version: int = 0


def reduce_session(state: GameSessionState | None, event: DomainEvent) -> GameSessionState:
    if event.event_type == "GameSessionCreated":
        owner = str(event.payload["owner_id"])
        return GameSessionState(
            session_id=str(event.payload["session_id"]),
            campaign_id=event.campaign_id,
            owner_id=owner,
            members={owner: SessionMember(principal_id=owner, role="owner")},
            stream_version=event.stream_version,
        )
    if state is None:
        raise ValueError("session stream must start with GameSessionCreated")
    next_state = state.model_copy(deep=True)
    next_state.stream_version = event.stream_version
    if event.event_type == "SessionMemberJoined":
        principal_id = str(event.payload["principal_id"])
        next_state.members[principal_id] = SessionMember(principal_id=principal_id, role=str(event.payload.get("role", "player")))
    elif event.event_type == "SessionInvitationCreated":
        invitation = SessionInvitation.model_validate(event.payload)
        next_state.invitations[invitation.invitation_id] = invitation
    elif event.event_type == "SessionInvitationAccepted":
        invitation = next_state.invitations[str(event.payload["invitation_id"])]
        invitation.status = SessionInvitationStatus.ACCEPTED
        next_state.members[invitation.principal_id] = SessionMember(principal_id=invitation.principal_id, role=invitation.role)
    elif event.event_type == "SessionInvitationRevoked":
        next_state.invitations[str(event.payload["invitation_id"])].status = SessionInvitationStatus.REVOKED
    elif event.event_type == "SessionMemberLeft":
        principal_id = str(event.payload["principal_id"])
        next_state.members.pop(principal_id, None)
        next_state.actor_controls = {actor_id: controller for actor_id, controller in next_state.actor_controls.items() if controller != principal_id}
    elif event.event_type == "SessionReadyChanged":
        next_state.members[str(event.payload["principal_id"])].ready = bool(event.payload["ready"])
    elif event.event_type == "ActorControlGranted":
        next_state.actor_controls[str(event.payload["actor_id"])] = str(event.payload["principal_id"])
    elif event.event_type == "ActorControlRevoked":
        next_state.actor_controls.pop(str(event.payload["actor_id"]), None)
    elif event.event_type == "GameSessionOpened":
        next_state.status = SessionStatus.OPEN
        next_state.opened_at_sequence = event.sequence
    elif event.event_type == "GameSessionPaused":
        next_state.status = SessionStatus.PAUSED
        next_state.paused_at_sequence = event.sequence
    elif event.event_type == "GameSessionResumed":
        next_state.status = SessionStatus.OPEN
    elif event.event_type == "GameSessionClosed":
        next_state.status = SessionStatus.CLOSED
        next_state.closed_at_sequence = event.sequence
    return next_state
