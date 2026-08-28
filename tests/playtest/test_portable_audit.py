import pytest

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_character_export_import_and_redacted_admin_audit() -> None:
    owner = Persona(name="Owner", principal_id="owner", role="owner")
    client = PlaytestClient(owner)
    try:
        await client.command("CreateCampaign", payload={"campaign_id": "cmp_portable", "name": "Portable", "seed": 77, "password": "do-not-log"})
        await client.command("CreateActor", campaign_id="cmp_portable", payload={"actor_id": "hero_portable", "name": "Portable Hero"})
        exported = await client.get("/api/v1/actors/hero_portable/export-package")
        package = exported["data"]
        receipt = await client.command("ImportCharacterPackage", campaign_id="cmp_portable", payload={"actor_id": "hero_imported", "package": package})
        assert receipt["status"] == "accepted"
        assert (await client.get("/api/v1/actors/hero_imported"))["data"]["name"] == "Portable Hero"

        response = await client.http.get("/api/v1/admin/audit?campaign_id=cmp_portable", headers={"x-principal-id": "admin", "x-principal-roles": "admin"})
        response.raise_for_status()
        records = response.json()["data"]
        assert records
        create = next(record for record in records if record["command_type"] == "CreateCampaign")
        assert create["request"]["payload"]["password"] == "[REDACTED]"
    finally:
        await client.close()
