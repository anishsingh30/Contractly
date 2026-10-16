import time
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiterBackend:
    """Abstract interface for distributed or local rate limiter backends."""
    async def check_and_record(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        raise NotImplementedError

    async def record_failure(self, key: str, window_seconds: int) -> int:
        raise NotImplementedError

    async def get_count(self, key: str, window_seconds: int) -> int:
        raise NotImplementedError

    async def reset(self, key: Optional[str] = None) -> None:
        raise NotImplementedError


class InMemoryRateLimiterBackend(RateLimiterBackend):
    """
    In-memory sliding window rate limiter backend.
    Thread-safe and process-isolated using asyncio.Lock.
    """
    def __init__(self):
        self._history: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    async def check_and_record(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            timestamps = self._history.get(key, [])
            active = [ts for ts in timestamps if ts > cutoff]
            if len(active) >= max_requests:
                oldest = active[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                self._history[key] = active
                return False, retry_after

            active.append(now)
            self._history[key] = active
            return True, 0

    async def record_failure(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            timestamps = self._history.get(key, [])
            active = [ts for ts in timestamps if ts > cutoff]
            active.append(now)
            self._history[key] = active
            return len(active)

    async def get_count(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            timestamps = self._history.get(key, [])
            active = [ts for ts in timestamps if ts > cutoff]
            self._history[key] = active
            return len(active)

    async def reset(self, key: Optional[str] = None) -> None:
        async with self._lock:
            if key is None:
                self._history.clear()
            else:
                self._history.pop(key, None)


def sanitize_redis_url(url: Optional[str]) -> str:
    """Removes sensitive credentials from Redis connection URLs for safe logging and diagnostics."""
    if not url:
        return ""
    import re
    cleaned = re.sub(r'://([^:]+):([^@]+)@', r'://\1:[REDACTED]@', url)
    cleaned = re.sub(r'://:([^@]+)@', r'://:[REDACTED]@', cleaned)
    return cleaned

# Atomic sliding-window evaluation script for Redis
SLIDING_WINDOW_LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local count = redis.call('ZCARD', key)

if count >= max_requests then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_ts = (oldest and oldest[2]) and tonumber(oldest[2]) or now
    local retry_after = math.max(1, math.ceil(window - (now - oldest_ts)))
    return {0, retry_after}
else
    redis.call('ZADD', key, now, now .. ':' .. ARGV[4])
    redis.call('EXPIRE', key, math.ceil(window))
    return {1, 0}
end
"""


class RedisRateLimiterBackend(RateLimiterBackend):
    """
    Redis-backed distributed rate limiter.
    Connects when REDIS_URL is provided, executing atomic sliding-window operations.
    Provides clear honest diagnostics and bounded key expirations without leaking credentials.
    """
    def __init__(
        self,
        redis_url: str,
        required: bool = False,
        connect_timeout: float = 3.0,
        redis_client: Optional[Any] = None
    ):
        self.redis_url = redis_url
        self.required = required
        self.connect_timeout = connect_timeout
        self._fallback = InMemoryRateLimiterBackend()
        self._redis = redis_client
        self._connected = redis_client is not None
        self._last_error: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._redis is not None

    @property
    def is_distributed(self) -> bool:
        return self.is_connected

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    async def _get_client(self):
        if not self._connected or self._redis is None:
            sanitized_url = sanitize_redis_url(self.redis_url)
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=self.connect_timeout
                )
                await asyncio.wait_for(self._redis.ping(), timeout=self.connect_timeout)
                self._connected = True
                self._last_error = None
                logger.info(f"[RateLimiter] Connected to distributed Redis backend at {sanitized_url}")
            except Exception as e:
                self._connected = False
                self._redis = None
                err_msg = str(e)
                self._last_error = f"Connection failed: {err_msg}"
                if self.required:
                    logger.critical(
                        f"[RateLimiter] REDIS_REQUIRED=True but connection to Redis failed at {sanitized_url}: {err_msg}."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Distributed rate limiter service is currently unavailable."
                    )
                logger.warning(
                    f"[RateLimiter] Could not connect to Redis at {sanitized_url}: {err_msg}. "
                    "Operating in degraded in-memory local fallback mode (not distributed)."
                )
        return self._redis if self._connected else None

    async def check_and_record(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        client = await self._get_client()
        if not client:
            return await self._fallback.check_and_record(key, max_requests, window_seconds)

        now = time.time()
        rand_suffix = str(now)
        try:
            res = await client.eval(
                SLIDING_WINDOW_LUA_SCRIPT,
                1,
                key,
                str(now),
                str(window_seconds),
                str(max_requests),
                rand_suffix
            )
            allowed = bool(res[0] == 1)
            retry_after = int(res[1])
            return allowed, retry_after
        except Exception:
            try:
                cutoff = now - window_seconds
                pipe = client.pipeline()
                pipe.zremrangebyscore(key, 0, cutoff)
                pipe.zcard(key)
                pipe.zrange(key, 0, 0, withscores=True)
                res = await pipe.execute()
                count = res[1]
                oldest = res[2]
                if count >= max_requests:
                    oldest_time = oldest[0][1] if oldest else now
                    retry_after = max(1, int(window_seconds - (now - oldest_time)))
                    return False, retry_after
                pipe = client.pipeline()
                pipe.zadd(key, {f"{now}:{rand_suffix}": now})
                pipe.expire(key, int(window_seconds))
                await pipe.execute()
                return True, 0
            except Exception as pipe_err:
                sanitized_url = sanitize_redis_url(self.redis_url)
                logger.error(f"[RedisRateLimiter] Operation failed at {sanitized_url}: {pipe_err}. Falling back to in-memory.")
                if self.required:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Distributed rate limiter service is currently unavailable."
                    )
                return await self._fallback.check_and_record(key, max_requests, window_seconds)

    async def record_failure(self, key: str, window_seconds: int) -> int:
        client = await self._get_client()
        if not client:
            return await self._fallback.record_failure(key, window_seconds)
        try:
            now = time.time()
            cutoff = now - window_seconds
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {f"{now}:{now}": now})
            pipe.expire(key, int(window_seconds))
            pipe.zcard(key)
            res = await pipe.execute()
            return int(res[3])
        except Exception as e:
            sanitized_url = sanitize_redis_url(self.redis_url)
            logger.error(f"[RedisRateLimiter] Error at {sanitized_url}: {e}. Falling back to in-memory.")
            return await self._fallback.record_failure(key, window_seconds)

    async def get_count(self, key: str, window_seconds: int) -> int:
        client = await self._get_client()
        if not client:
            return await self._fallback.get_count(key, window_seconds)
        try:
            now = time.time()
            cutoff = now - window_seconds
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            res = await pipe.execute()
            return int(res[1])
        except Exception as e:
            return await self._fallback.get_count(key, window_seconds)

    async def reset(self, key: Optional[str] = None) -> None:
        client = await self._get_client()
        if client and key:
            try:
                await client.delete(key)
            except Exception:
                pass
        await self._fallback.reset(key)


def get_default_backend() -> RateLimiterBackend:
    if settings.REDIS_URL:
        return RedisRateLimiterBackend(
            redis_url=settings.REDIS_URL,
            required=settings.REDIS_REQUIRED,
            connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS
        )
    return InMemoryRateLimiterBackend()


def get_rate_limiter_health() -> Dict[str, Any]:
    """
    Returns non-sensitive operational health and readiness diagnostics for the rate limiter.
    Never exposes passwords, tokens, or full connection credentials.
    """
    backend = auth_rate_limiter.backend
    if isinstance(backend, RedisRateLimiterBackend):
        connected = backend.is_connected
        return {
            "backend": "redis",
            "configured": bool(backend.redis_url),
            "connected": connected,
            "is_distributed": connected,
            "mode": "distributed" if connected else "degraded_in_memory_fallback",
            "endpoint": sanitize_redis_url(backend.redis_url),
            "last_error": backend.last_error
        }
    return {
        "backend": "in_memory",
        "configured": False,
        "connected": True,
        "is_distributed": False,
        "mode": "process_local",
        "endpoint": None,
        "last_error": None
    }


class InMemorySlidingWindowRateLimiter:
    """
    Maintained for backward compatibility with AI and existing endpoints.
    """
    def __init__(self, default_limit: int = 30, window_seconds: int = 60, backend: Optional[RateLimiterBackend] = None):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.backend = backend or get_default_backend()

    async def check_rate_limit(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ) -> None:
        max_requests = limit if limit is not None else self.default_limit
        window_size = window if window is not None else self.window_seconds
        allowed, retry_after = await self.backend.check_and_record(identifier, max_requests, window_size)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for AI operations. Maximum {max_requests} requests per {window_size}s allowed. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)}
            )

    async def reset(self) -> None:
        await self.backend.reset()


class AuthAbuseLimiter:
    """
    Protects authentication endpoints (/login and /register) against brute-force and credential stuffing.
    Enforces IP-based rate limits and account lockout based on repeated failed logins.
    """
    def __init__(self, backend: Optional[RateLimiterBackend] = None):
        self.backend = backend or get_default_backend()

    async def check_login_rate_limit(self, client_ip: str, email: str) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return

        norm_email = email.lower().strip()

        # 1. Check IP burst limit
        ip_key = f"auth:login:ip:{client_ip}"
        ip_allowed, retry_after_ip = await self.backend.check_and_record(
            ip_key,
            settings.AUTH_IP_MAX_REQUESTS_PER_MINUTE,
            60
        )
        if not ip_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication requests from this IP address. Please wait before retrying.",
                headers={"Retry-After": str(retry_after_ip)}
            )

        # 2. Check failed attempt lockout for this email
        email_key = f"auth:failed:email:{norm_email}"
        failed_count = await self.backend.get_count(email_key, settings.AUTH_LOGIN_WINDOW_SECONDS)
        if failed_count >= settings.AUTH_LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Account temporarily locked for security. Please try again later.",
                headers={"Retry-After": str(settings.AUTH_LOGIN_WINDOW_SECONDS)}
            )

    async def record_login_failure(self, client_ip: str, email: str) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return
        norm_email = email.lower().strip()
        email_key = f"auth:failed:email:{norm_email}"
        await self.backend.record_failure(email_key, settings.AUTH_LOGIN_WINDOW_SECONDS)

    async def record_login_success(self, client_ip: str, email: str) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return
        norm_email = email.lower().strip()
        email_key = f"auth:failed:email:{norm_email}"
        await self.backend.reset(email_key)

    async def check_register_rate_limit(self, client_ip: str) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return

        ip_key = f"auth:register:ip:{client_ip}"
        allowed, retry_after = await self.backend.check_and_record(
            ip_key,
            settings.AUTH_REGISTER_MAX_ATTEMPTS,
            settings.AUTH_REGISTER_WINDOW_SECONDS
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many registration attempts from this address. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)}
            )

    async def check_password_reset_rate_limit(self, client_ip: str, email: Optional[str] = None) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return

        ip_key = f"auth:reset:ip:{client_ip}"
        allowed_ip, retry_after = await self.backend.check_and_record(ip_key, 10, 300)
        if not allowed_ip:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset requests from this address. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)}
            )

        if email:
            norm_email = email.lower().strip()
            email_key = f"auth:reset:email:{norm_email}"
            allowed_email, retry_after_email = await self.backend.check_and_record(email_key, 5, 300)
            if not allowed_email:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many password reset requests for this account. Please wait before retrying.",
                    headers={"Retry-After": str(retry_after_email)}
                )

    async def check_verification_rate_limit(self, client_ip: str, email: Optional[str] = None) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return

        ip_key = f"auth:verify:ip:{client_ip}"
        allowed_ip, retry_after = await self.backend.check_and_record(ip_key, 10, 300)
        if not allowed_ip:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification requests from this address. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)}
            )

        if email:
            norm_email = email.lower().strip()
            email_key = f"auth:verify:email:{norm_email}"
            allowed_email, retry_after_email = await self.backend.check_and_record(email_key, 5, 300)
            if not allowed_email:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many verification requests for this account. Please wait before retrying.",
                    headers={"Retry-After": str(retry_after_email)}
                )

    async def check_invitation_rate_limit(self, client_ip: str, org_id: Optional[str] = None) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return

        key = f"org:invite:{org_id}" if org_id else f"org:invite:ip:{client_ip}"
        allowed, retry_after = await self.backend.check_and_record(key, 25, 300)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many invitation requests. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)}
            )

    async def reset(self) -> None:
        await self.backend.reset()


# Global singletons
ai_rate_limiter = InMemorySlidingWindowRateLimiter(default_limit=30, window_seconds=60)
auth_rate_limiter = AuthAbuseLimiter()
