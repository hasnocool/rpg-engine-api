from rpg_engine_api.infrastructure.rate_limit import SlidingWindowRateLimiter


async def test_sliding_window_limiter_releases_old_entries() -> None:
    limiter = SlidingWindowRateLimiter(2, window_seconds=10)
    assert await limiter.allow("p", now=0)
    assert await limiter.allow("p", now=1)
    assert not await limiter.allow("p", now=2)
    assert await limiter.allow("p", now=11)
