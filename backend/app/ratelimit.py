"""In-memory abuse protection for the authentication endpoints.

No external dependencies and no database writes: the state lives for the
lifetime of the process, which is exactly what brute-force throttling needs.
Failed attempts are tracked per account (stops credential stuffing against a
single user) and requests per client IP (slows bulk registration/spam).
"""
import threading
import time
from collections import defaultdict, deque

# Account lockout: 5 failed logins within 15 minutes locks the account.
FAILED_LOGIN_LIMIT = 5
FAILED_LOGIN_WINDOW = 15 * 60
# Per-IP request ceilings.
LOGIN_LIMIT = 15
LOGIN_WINDOW = 5 * 60
REGISTER_LIMIT = 8
REGISTER_WINDOW = 60 * 60


class SlidingWindowLimiter:
    """Allows at most `limit` hits per key within `window_seconds`."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class LoginThrottle:
    """Locks an account after too many failed logins, then forgets failures on success."""

    def __init__(self, limit: int = FAILED_LOGIN_LIMIT, window_seconds: int = FAILED_LOGIN_WINDOW) -> None:
        self.limit = limit
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_locked(self, email: str) -> bool:
        now = time.monotonic()
        with self._lock:
            failures = self._failures[email]
            cutoff = now - self.window
            while failures and failures[0] <= cutoff:
                failures.popleft()
            return len(failures) >= self.limit

    def record_failure(self, email: str) -> None:
        now = time.monotonic()
        with self._lock:
            failures = self._failures[email]
            failures.append(now)
            cutoff = now - self.window
            while failures and failures[0] <= cutoff:
                failures.popleft()

    def clear(self, email: str) -> None:
        with self._lock:
            self._failures.pop(email, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_ip_limiter = SlidingWindowLimiter(LOGIN_LIMIT, LOGIN_WINDOW)
register_ip_limiter = SlidingWindowLimiter(REGISTER_LIMIT, REGISTER_WINDOW)
login_throttle = LoginThrottle()


def reset_all() -> None:
    """Clear every limiter (used by tests)."""
    login_ip_limiter.reset()
    register_ip_limiter.reset()
    login_throttle.reset()
