import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from rpg_engine_api.domain.authoring import PublishedContentPack
from rpg_engine_api.domain.commands import CommandEnvelope, CommandStatus
from rpg_engine_api.sdk import AsyncRpgClient
from rpg_engine_api.simulation.quality import analyze_pack


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _command_from_action(action: dict[str, Any]) -> CommandEnvelope:
    command_type = str(action["command_type"])
    excluded = {"command_type", "campaign_id", "actor_id", "label", "payload_schema"}
    payload = {key: value for key, value in action.items() if key not in excluded}
    for key, value in dict(action.get("payload_schema", {})).items():
        payload.setdefault(key, value)
    return CommandEnvelope(
        command_type=command_type,
        campaign_id=action.get("campaign_id"),
        actor_id=action.get("actor_id"),
        payload=payload,
    )


async def _play(args: argparse.Namespace) -> int:
    async with AsyncRpgClient(args.base_url, principal_id=args.principal, roles=tuple(args.roles.split(","))) as client:
        while True:
            actor = await client.actor(args.actor)
            print(f"\n{actor.get('name', args.actor)}  level={actor.get('level')}  inventory={actor.get('inventory', [])}")
            actions = await client.available_actions(args.actor)
            if not actions:
                print("No advertised actions are currently available.")
                return 0
            for index, action in enumerate(actions, start=1):
                print(f"{index:>2}. {action.get('label', action.get('action_id', action.get('command_type')))}")
            print(" q. quit")
            choice = input("> ").strip().lower()
            if choice in {"q", "quit", "exit"}:
                return 0
            try:
                action = actions[int(choice) - 1]
            except (ValueError, IndexError):
                print("Invalid choice")
                continue
            receipt = await client.command(_command_from_action(action))
            print(f"{receipt.status.value}: {receipt.result or (receipt.error.model_dump(mode='json') if receipt.error else {})}")
            if receipt.status not in {CommandStatus.ACCEPTED, CommandStatus.ALREADY_PROCESSED}:
                continue


async def _events(args: argparse.Namespace) -> int:
    async with AsyncRpgClient(args.base_url, principal_id=args.principal, roles=tuple(args.roles.split(","))) as client:
        page = await client.events_page(args.campaign, cursor=args.cursor, limit=args.limit)
        _json(page.model_dump(mode="json"))
    return 0


async def _capabilities(args: argparse.Namespace) -> int:
    async with AsyncRpgClient(args.base_url, principal_id=args.principal, roles=tuple(args.roles.split(","))) as client:
        _json(await client.capabilities())
    return 0


def _content_test(args: argparse.Namespace) -> int:
    path = Path(args.path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "data" in raw and "pack_id" not in raw:
        raw = raw["data"]
    pack = PublishedContentPack.model_validate(raw)
    report = analyze_pack(pack)
    _json(report.model_dump(mode="json"))
    return 0 if report.valid else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rpg-engine", description="Thin RPG Engine API client/tooling")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--principal", default="local-player")
    parser.add_argument("--roles", default="player")
    sub = parser.add_subparsers(dest="command", required=True)

    play = sub.add_parser("play", help="play one actor using server-advertised actions")
    play.add_argument("actor")
    play.set_defaults(func=_play)

    events = sub.add_parser("events", help="fetch one opaque-cursor event page")
    events.add_argument("campaign")
    events.add_argument("--cursor")
    events.add_argument("--limit", type=int, default=100)
    events.set_defaults(func=_events)

    caps = sub.add_parser("capabilities", help="show server capabilities")
    caps.set_defaults(func=_capabilities)

    content = sub.add_parser("content-test", help="statically validate a published content-pack JSON file")
    content.add_argument("path")
    content.set_defaults(func=_content_test)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.func(args)
    code = asyncio.run(result) if asyncio.iscoroutine(result) else int(result)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
