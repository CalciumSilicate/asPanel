# backend/core/rate_limit.py

from collections import defaultdict
from time import time


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)
    
    def _cleanup(self, key: str):
        now = time()
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
    
    def check(self, key: str) -> bool:
        self._cleanup(key)
        return len(self.attempts[key]) < self.max_attempts
    
    def record(self, key: str):
        self._cleanup(key)
        self.attempts[key].append(time())


login_limiter = RateLimiter(max_attempts=5, window_seconds=300)
