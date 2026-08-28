import pytest

from rpg_engine_api.testing.benchmarks import budget_failures, run_release_benchmarks


@pytest.mark.performance
@pytest.mark.asyncio
async def test_representative_release_budgets() -> None:
    report = await run_release_benchmarks(event_count=300, command_count=40, scheduler_count=1500, fanout_subscribers=10, fanout_events=50)
    assert budget_failures(report) == []
