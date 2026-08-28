import asyncio

from rpg_engine_api.sdk import AsyncRpgClient


async def main() -> None:
    campaign_id = input("Campaign ID: ").strip()
    async with AsyncRpgClient(principal_id="local-player") as client:
        async for message in client.live_messages(campaign_id):
            print(message)


if __name__ == "__main__":
    asyncio.run(main())
