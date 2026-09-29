import time
from collections import defaultdict
from collections.abc import Callable
from typing import ClassVar

from fastapi import HTTPException, Request, status

from utils.client_ip import get_client_ip


class InMemoryRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter.
    Stores timestamps of requests per client key (IP or identifier).
    """

    _storage: ClassVar[dict[str, list[float]]] = defaultdict(list)
    MAX_KEYS: ClassVar[int] = 10_000

    @classmethod
    def _prune(cls, window_start: float) -> None:
        """Drop keys with no recent requests so the table cannot grow without bound."""
        for stale in [k for k, ts in cls._storage.items() if not ts or ts[-1] <= window_start]:
            del cls._storage[stale]

    @classmethod
    def is_allowed(cls, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        Check if request is allowed under rate limit.
        Returns (is_allowed, retry_after_seconds).
        """
        now = time.time()
        window_start = now - window_seconds

        # Clean timestamps older than the sliding window
        cls._storage[key] = [t for t in cls._storage[key] if t > window_start]
        if len(cls._storage) > cls.MAX_KEYS:
            cls._prune(window_start)

        if len(cls._storage[key]) >= max_requests:
            oldest = cls._storage[key][0]
            retry_after = max(1, int(oldest + window_seconds - now))
            return False, retry_after

        # Record current request
        cls._storage[key].append(now)
        return True, 0

    @classmethod
    def reset(cls, key: str | None = None) -> None:
        """Reset rate limit tracking (useful for test suites)."""
        if key:
            cls._storage.pop(key, None)
        else:
            cls._storage.clear()


def rate_limit(
    max_requests: int = 5,
    window_seconds: int = 60,
    scope: str = "default",
    key_func: Callable[[Request], str] | None = None,
) -> Callable:
    """
    FastAPI dependency for generic rate limiting per endpoint.
    
    Usage:
        @router.post("/login", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, scope="login"))])
        async def login(...):
            ...
    """

    async def dependency(request: Request) -> None:
        # Never key on the raw (client-controlled) X-Forwarded-For value: rotating it bypassed the limit
        client_id = key_func(request) if key_func else get_client_ip(request)

        rate_key = f"{scope}:{client_id}"
        allowed, retry_after = InMemoryRateLimiter.is_allowed(
            key=rate_key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Terlalu banyak permintaan untuk endpoint ini. Batas: {max_requests} per {window_seconds} detik. Coba lagi dalam {retry_after} detik.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
