"""Password hashing, tokens and login rate limiting. Standard library only."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

# scrypt: memory-hard, in the standard library. N=2^14, r=8 uses 16 MiB per hash.
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32, "maxmem": 64 * 1024 * 1024}


def hash_password(password: str) -> tuple[bytes, bytes]:
    salt = secrets.token_bytes(16)
    return salt, hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)


def check_password(password: str, salt: bytes, expected: bytes) -> bool:
    return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT), expected)


_DUMMY_SALT, _DUMMY_HASH = hash_password("timing-equaliser")


def burn_time(password: str) -> None:
    """Hash anyway when the login is unknown, so response time doesn't reveal which logins exist."""
    check_password(password, _DUMMY_SALT, _DUMMY_HASH)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


class RateLimiter:
    """At most `limit` events per key per `window_s`. In memory: one worker only, as the app requires."""

    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, *keys: str) -> bool:
        t = time.monotonic()
        with self._lock:
            for k in keys:
                q = self._hits[k]
                while q and t - q[0] > self.window_s:
                    q.popleft()
                if len(q) >= self.limit:
                    return False
            for k in keys:
                self._hits[k].append(t)
            return True
