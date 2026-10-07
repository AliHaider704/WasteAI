# File: server/app/ratelimit.py
import math
import threading
import time
from collections import deque


class TokenBucket:
    """Capacity = per_minute tokens, refilled continuously."""

    def __init__(self, per_minute: int) -> None:
        self.capacity = float(per_minute)
        self.tokens = float(per_minute)
        self.rate = per_minute / 60.0
        self.stamp = time.monotonic()
        self._lock = threading.Lock()

    def take(self) -> bool:
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.stamp) * self.rate)
            self.stamp = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


class IPLimiter:
    """Sliding window per IP, in memory only (no IP is persisted)."""

    def __init__(self, limit: int = 10, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self.hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, ip: str) -> int:
        """Return 0 if allowed, else seconds to wait (Retry-After)."""
        now = time.monotonic()
        with self._lock:
            if len(self.hits) > 5000:
                self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < self.window}
            q = self.hits.setdefault(ip, deque())
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return max(1, math.ceil(self.window - (now - q[0])))
            q.append(now)
            return 0


ip_limiter = IPLimiter(10, 60.0)

# Separate bucket for /feedback: 10 per minute per IP.
feedback_limiter = IPLimiter(10, 60.0)
