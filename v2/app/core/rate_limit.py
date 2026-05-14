from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic


class InMemoryRateLimiter:
    def __init__(self, *, capacity: int, window_seconds: int) -> None:
        self.capacity = capacity
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.capacity:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()
