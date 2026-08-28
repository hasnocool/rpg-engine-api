import pytest

from .harness import Persona, PlaytestClient


@pytest.mark.playtest
@pytest.mark.asyncio
async def test_permission_boundaries_and_isolated_recovery_probe() -> None:
    owner = PlaytestClient(Persona(name="Owner", principal_id="owner", role="owner"))
    try:
        await owner.command("CreateCampaign", payload={"campaign_id": "cmp_secure", "name": "Secure", "seed": 42})
        await owner.command("CreateActor", campaign_id="cmp_secure", payload={"actor_id": "secure_hero", "name": "Secure Hero"})

        outsider = PlaytestClient(Persona(name="Outsider", principal_id="outsider", role="player"), app=owner.app)
        try:
            actor = await outsider.http.get("/api/v1/actors/secure_hero", headers=outsider.headers)
            assert actor.status_code == 403
            audit = await outsider.http.get("/api/v1/admin/audit", headers=outsider.headers)
            assert audit.status_code == 403
            export = await outsider.http.get("/api/v1/campaigns/cmp_secure/export-package", headers=outsider.headers)
            assert export.status_code == 403
        finally:
            await outsider.close()

        recovery = await owner.http.post("/api/v1/admin/recovery-probe/cmp_secure", headers={"x-principal-id": "admin", "x-principal-roles": "admin"})
        recovery.raise_for_status()
        report = recovery.json()["data"]
        assert report["isolated"] is True
        assert report["source_replay_matches_live"] is True
        assert report["restored_replay_matches_live"] is True
        assert report["restored_matches_source"] is True
        assert report["success"] is True
    finally:
        await owner.close()
