# Dungeon Master and Session Operations Specification

## Status

**Project:** `rpg-engine-api`  
**Role:** Normative specification for lobby/session lifecycle, live Dungeon Master operations, checkpoints/branches, recaps, journals, and control handoff.

`PLAN.md` remains the canonical roadmap. This document defines how a campaign is practically hosted and operated from “players are joining” through “session is closed and resumable.”

---

# 1. Goals

The engine must support the operational flow of an actual tabletop-style session without requiring direct database changes or a specific UI.

Core lifecycle:

```text
campaign exists
    -> invitations/membership
    -> lobby opens
    -> players connect
    -> actor/character control assigned
    -> ready check
    -> game session opens
    -> live play
    -> pause/AFK/reconnect/control handoff
    -> checkpoints/branches as requested
    -> session closes
    -> recap/journal projections update
    -> later session resumes
```

All game-state changes still use commands/events. Presence/lobby metadata remains ephemeral unless explicitly recorded as a campaign/session fact.

---

# 2. Lobby model

A lobby is a pre-session coordination object.

```text
CampaignLobby
    id
    campaign_id
    status
    session_id | null
    member_slots[]
    ready_check | null
    opened_at
    expires_at | null
```

Statuses:

```text
open
starting
closed
cancelled
```

## 2.1 Lobby member slot

```text
LobbyMemberSlot
    membership_id
    connection_state
    selected_actor_ids[]
    ready_state
    device_count
    last_seen_at
```

Connection state is operational/ephemeral. Actor assignment is authoritative campaign configuration/control state.

## 2.2 Ready check

```text
ReadyCheck
    id
    created_by
    created_at
    deadline | null
    required_members[]
    responses
    status
```

Statuses:

```text
open
passed
failed
cancelled
expired
```

A ready check never advances gameplay by itself. Session start is still an explicit authorized command.

Commands:

```text
OpenLobby
CloseLobby
JoinLobby
LeaveLobby
SelectControlledActor
BeginReadyCheck
SetReadyState
CancelReadyCheck
OpenGameSession
```

---

# 3. Game session lifecycle

The existing `GameSession` becomes the durable record of an actual play session.

```text
GameSession
    id
    campaign_id
    status
    opened_at
    closed_at | null
    world_time_at_open
    world_time_at_close | null
    participating_members[]
    active_party_ids[]
    starting_checkpoint_ref | null
    ending_checkpoint_ref | null
    notes
```

Statuses:

```text
scheduled
open
paused
closing
closed
abandoned
```

Commands:

```text
ScheduleGameSession
OpenGameSession
PauseGameSession
ResumeGameSession
CloseGameSession
AbandonGameSession
UpdateSessionNotes
```

Events mirror meaningful lifecycle transitions.

A paused session and a paused simulation timeline are related but distinct. Campaign clock policy determines whether pausing the session pauses the world.

---

# 4. Invitations and membership workflow

Membership creation and permissions are explicit.

Conceptual commands:

```text
InviteCampaignMember
AcceptCampaignInvitation
DeclineCampaignInvitation
RevokeCampaignInvitation
UpdateCampaignMemberRole
RemoveCampaignMember
GrantActorControl
RevokeActorControl
```

Invitation tokens/transport details are authentication infrastructure and must not appear in gameplay events or exports.

A campaign can allow owner/DM-approved joining or other future policies, but v1.0 should support explicit invitations robustly.

---

# 5. Actor control and multi-device behavior

Actor ownership and current control must not be inferred solely from one WebSocket connection.

```text
ActorControlGrant
    campaign_id
    actor_id
    principal_id
    scope
    status
    granted_by
    granted_at
    expires_at | null
```

Possible scopes:

```text
primary
shared
temporary
spectate_only
```

## 5.1 Multiple devices

A principal may connect from multiple devices. Commands still use idempotency/concurrency rules.

Campaign policy determines whether two devices may control the same actor simultaneously.

Recommended default:

```text
multiple connected devices allowed
single active command authority per actor/principal scope
```

The server must reject conflicting/stale commands normally rather than trusting whichever socket was most recent.

---

# 6. Disconnect, AFK, and controller handoff

Connectivity itself is not gameplay authority, but the campaign may configure what happens when a player is absent.

```text
DisconnectPolicy
    grace_period
    current_action_policy
    future_turn_policy
    handoff_controller | null
    return_control_policy
```

Possible future-turn policies:

```text
wait_until_deadline
forfeit
pause_campaign
simple_npc_handoff
dm_control
```

`simple_npc_handoff` uses the normal `SimpleNpcController` with a configured profile and produces normal commands. Control returns only through an explicit policy transition/event.

Events may include:

```text
ActorControlTemporarilyDelegated
ActorControlRestored
```

Do not make connection loss itself directly mutate actor HP, position, inventory, or other state.

---

# 7. Live DM operations

The DM needs a safe operational control plane without bypassing event history.

Useful domains:

```text
session control
actor control
scene/encounter control
world/time control
visibility/reveal control
quest/dialogue control
rewards/items/effects
checkpoint/branch operations
```

Commands remain the privileged command set defined by the main plan, such as:

```text
CreateEncounter
StartEncounter
PauseTimeline
ResumeTimeline
SpawnActor
DespawnActor
RevealLocation
RevealKnowledge
ScheduleWorldEvent
SetWeather
StartDialogue
AdvanceQuest
GrantItem
ApplyEffect
OverrideRuleResolution
```

Every override records principal, reason where required, correlation ID, resulting events, and visibility policy.

## 7.1 DM command preview

Risky DM operations should support dry-run/preview where practical.

```text
DmCommandPreview
    command_type
    validation_result
    affected_entities[]
    predicted_event_types[]
    warnings[]
```

Preview is advisory and cannot guarantee no concurrent state changes; final command still validates against current state.

---

# 8. Named checkpoints

A checkpoint is a durable named reference to campaign history, not a destructive save-file overwrite.

```text
CampaignCheckpoint
    id
    campaign_id
    name
    description | null
    sequence
    simulation_time
    content_lock_hash
    snapshot_ref | null
    created_by
    created_at
    tags[]
```

Commands:

```text
CreateCheckpoint
RenameCheckpoint
DeleteCheckpointReference
ArchiveCheckpoint
```

Deleting a checkpoint reference does not delete authoritative event history.

Useful automatic checkpoints can be created at session open/close, before content migration, and before explicitly destructive-style DM experiments.

---

# 9. Restore and branch semantics

Event-sourced campaigns should avoid pretending history can be erased safely.

Default restore behavior:

```text
checkpoint
    -> CreateCampaignBranch
    -> new campaign/branch identity
    -> history references parent + fork sequence
    -> replay/snapshot initializes branch
```

```text
CampaignBranch
    id
    parent_campaign_id
    parent_sequence
    name
    created_by
    created_at
    reason | null
```

Commands:

```text
CreateBranchFromCheckpoint
CreateBranchFromSequence
CloneCampaignSnapshot
ArchiveCampaign
```

A future explicit destructive rewind mode could exist for special deployments, but the reference engine should prefer branch creation so history remains auditable.

## 9.1 Branch content pins

A branch starts with the parent content/configuration lock as of the fork sequence. Later revisions are independent.

---

# 10. Session recaps

A recap is a deterministic projection first.

```text
SessionRecap
    session_id
    campaign_id
    sequence_range
    world_time_range
    participating_actors[]
    major_events[]
    quest_changes[]
    discoveries[]
    encounters[]
    rewards[]
    progression_changes[]
    relationship_changes[]
    checkpoint_refs[]
    renderer_version
```

The deterministic recap contains structured facts and optionally deterministic localized prose templates.

A later optional LLM summarizer may produce stylistic prose from the visibility-filtered recap facts but cannot become authoritative history.

---

# 11. Journals and chronicles

Useful read projections:

```text
CharacterJournal
QuestJournal
DiscoveryJournal
CampaignChronicle
NpcEncounterHistory
FactionHistory
LocationHistory
```

## 11.1 Character journal

```text
CharacterJournal
    character_id
    sessions[]
    quests[]
    discoveries[]
    major_encounters[]
    acquired_notable_items[]
    progression_changes[]
    relationship_changes[]
```

## 11.2 Campaign chronicle

The chronicle is a role-aware chronological projection of major events, suitable for long-running campaigns.

Visibility rules must prevent private DM facts from leaking into player journals.

---

# 12. Session close workflow

Closing a session should be explicit and deterministic.

Recommended flow:

```text
request close
    -> validate no forbidden unresolved transaction/window
    -> apply campaign close policy
    -> record world time
    -> optional automatic checkpoint
    -> close GameSession
    -> finalize recap projection
    -> publish session-closed event
```

Campaign policy decides what to do with open encounters/action windows. Options may include reject close, pause, or authorized cleanup—not silent state deletion.

---

# 13. Query/API surfaces

Possible APIs:

```text
/api/v1/campaigns/{id}/lobby
/api/v1/campaigns/{id}/members
/api/v1/campaigns/{id}/control-grants
/api/v1/campaigns/{id}/sessions
/api/v1/campaigns/{id}/checkpoints
/api/v1/campaigns/{id}/branches
/api/v1/sessions/{id}/recap
/api/v1/characters/{id}/journal
/api/v1/campaigns/{id}/chronicle
```

State-changing operations should still route through commands where they affect authoritative campaign/session state.

---

# 14. Permissions

Examples:

```text
lobby.manage
session.open
session.pause
session.close
member.invite
member.manage
actor.control.grant
checkpoint.create
branch.create
recap.read
journal.read
```

Role bundles can grant these, but checks remain resource-scoped.

---

# 15. Playtest requirements

Systematic human-play scenarios must cover:

- player invitation/join;
- actor selection/control;
- ready check;
- session open/close;
- DM + multiple players;
- spectator join;
- duplicate/multi-device command conflict;
- disconnect grace period;
- SimpleNpcController handoff and restoration;
- reconnect/resync;
- checkpoint creation;
- branch from checkpoint;
- branch replay equivalence at fork point;
- recap generation;
- role-filtered journals;
- close-session behavior with active encounter/window;
- next-session resume from prior campaign state.

---

# 16. Milestone placement

```text
v0.1
    control-grant identity/version seam

v0.2
    disconnect/timing/control-handoff hooks

v0.7
    lobby, invitations, memberships, sessions, ready checks
    checkpoints/branches
    deterministic recap/journal foundations
    DM operational APIs

v0.8
    advanced controller handoff policies

v0.9
    stable live session/lobby/client contracts
    multi-device/reconnect behavior

v1.0
    complete session-open -> play -> disconnect/reconnect -> close -> recap -> next-session workflow
```

The engine does not need a polished dedicated DM UI for v1.0, but all operations needed to build one must be available through stable APIs.