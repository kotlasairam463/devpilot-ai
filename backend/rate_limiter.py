import time
import threading


class GeminiRateLimiter:
    """Token bucket limiter shared across all agent calls."""
    def __init__(self, requests_per_minute: int = 50):
        self.rate = requests_per_minute / 60.0
        self.tokens = requests_per_minute
        self.max_tokens = requests_per_minute
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
                self.last_refill = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
            time.sleep(0.1)


gemini_limiter = GeminiRateLimiter(requests_per_minute=50)