"""
API security
============

* **Authentication**: API keys supplied as ``SENTINEL_API_KEYS="name:role:key,..."``.
  Only SHA-256 digests are kept in memory and compared in constant time.
* **Authorisation**: roles ``viewer < analyst < admin`` (RBAC).
* **Fail closed**: in ``production`` with no keys configured and no explicit
  ``SENTINEL_API_PUBLIC_DEMO=true``, every protected endpoint returns 401 -
  the previous "any non-empty key is accepted" behaviour is gone.
* **Public demo mode**: unauthenticated callers get a limited ``demo`` principal
  (analysis only, nothing persisted) under a stricter rate limit.
* **Rate limiting**: keyed on the *validated* principal, otherwise the client IP,
  so rotating a fake ``X-API-Key`` header no longer bypasses it. Counters live in
  the shared cache (Redis when configured), so the limit holds across workers.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import HTTPException, Request

from sentinelai.core.cache import get_cache
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)

ROLE_RANK = {"demo": 0, "viewer": 1, "analyst": 2, "admin": 3}


@dataclass(frozen=True)
class Principal:
    name: str
    role: str

    @property
    def rank(self) -> int:
        return ROLE_RANK.get(self.role, 0)

    @property
    def is_demo(self) -> bool:
        return self.role == "demo"


class KeyStore:
    def __init__(self, spec: str):
        self._keys: Dict[str, Principal] = {}
        for item in [i.strip() for i in (spec or "").split(",") if i.strip()]:
            parts = item.split(":", 2)
            if len(parts) != 3 or parts[1] not in ("viewer", "analyst", "admin") or not parts[2]:
                logger.error("Ignoring malformed SENTINEL_API_KEYS entry (expected name:role:key)")
                continue
            name, role, key = parts
            self._keys[self._digest(key)] = Principal(name, role)

    @staticmethod
    def _digest(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def lookup(self, key: Optional[str]) -> Optional[Principal]:
        if not key:
            return None
        digest = self._digest(key)
        found = None
        for stored, principal in self._keys.items():      # compare against all: no early exit on mismatch
            if hmac.compare_digest(stored, digest):
                found = principal
        return found

    def __len__(self) -> int:
        return len(self._keys)


_store: Optional[KeyStore] = None
_dev_warned = False


def get_keystore(reload: bool = False) -> KeyStore:
    global _store
    if _store is None or reload:
        _store = KeyStore(settings.api.api_keys)
    return _store


def authenticate(request: Request) -> Principal:
    global _dev_warned
    store = get_keystore()
    key = request.headers.get(settings.api.api_key_header)
    if key:
        principal = store.lookup(key)
        if principal:
            return principal
        raise HTTPException(status_code=401, detail="Invalid API key")

    if len(store) == 0 and not settings.is_production:
        if not _dev_warned:
            logger.warning("No API keys configured - running OPEN in %s mode. Set SENTINEL_API_KEYS.", settings.environment)
            _dev_warned = True
        return Principal("dev", "admin")
    if settings.api.public_demo:
        return Principal("anonymous-demo", "demo")
    if len(store) == 0:
        raise HTTPException(status_code=401, detail="Authentication is not configured (set SENTINEL_API_KEYS)")
    raise HTTPException(status_code=401, detail="API key required")


def require(role: str, allow_demo: bool = False):
    """FastAPI dependency factory enforcing a minimum role."""
    needed = ROLE_RANK[role]

    async def dependency(request: Request) -> Principal:
        principal = authenticate(request)
        request.state.principal = principal
        if principal.is_demo:
            if allow_demo:
                return principal
            raise HTTPException(status_code=403, detail="This endpoint is not available in public demo mode")
        if principal.rank < needed:
            raise HTTPException(status_code=403, detail=f"Requires role '{role}' or higher")
        return principal

    return dependency


def client_ip(request: Request) -> str:
    if settings.api.trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(request: Request) -> Optional[Dict[str, str]]:
    """Return None when allowed, else the 429 headers."""
    principal = get_keystore().lookup(request.headers.get(settings.api.api_key_header))
    identity = f"key:{principal.name}" if principal else f"ip:{client_ip(request)}"
    limit = settings.api.rate_limit_requests if principal else (
        settings.api.demo_rate_limit_requests if settings.api.public_demo else settings.api.rate_limit_requests)
    period = settings.api.rate_limit_period
    window = int(time.time() // period)
    count = await get_cache().incr(f"rl:{identity}:{window}", ttl=period * 2)
    remaining = max(0, limit - count)
    request.state.rate_headers = {"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": str(remaining)}
    if count > limit:
        retry = period - int(time.time() % period)
        return {**request.state.rate_headers, "Retry-After": str(retry)}
    return None
