import pytest

from rpg_engine_api.simulation.controller_lab import run_controller_quality_lab


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_controller_quality_lab_uses_matched_seed_role_swaps() -> None:
    report = await run_controller_quality_lab([3, 7])
    assert report["matched_role_swaps"] is True
    assert len(report["matches"]) == 4
    assert report["all_replayable"] is True
