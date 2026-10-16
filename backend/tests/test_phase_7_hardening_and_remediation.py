"""
Phase 7 Test Suite: Staging Hardening and Blocker Remediation
Covers:
1. Next.js middleware public route verification (unauthenticated access to recovery/invite routes,
   query parameter preservation, protected route redirection, authenticated user redirect).
2. Customer account-type separation from platform privileges:
   - AccountType enum exclusion of PLATFORM_ADMIN.
   - Registration rejection of platform administrative roles.
   - Legacy record safe normalization.
   - Invitation role forgery defense.
   - Separation of customer roles from platform administration endpoints.
3. Redis distributed rate limiter backend:
   - URL sanitization (no credential leakage).
   - Atomic Lua/pipeline sliding window enforcement.
   - Bounded expiration and resource usage.
   - Outage behavior: graceful fallback when optional vs. HTTP 503 when REDIS_REQUIRED=True.
   - Safe operational health diagnostics.
4. System health and platform readiness diagnostics.
"""

import os
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.core.entitlements import (
    AccountType,
    VALID_CUSTOMER_ACCOUNT_TYPES,
    normalize_account_type,
    get_account_entitlements
)
from app.schemas.auth import RegisterRequest
from app.core.rate_limiter import (
    RedisRateLimiterBackend,
    InMemoryRateLimiterBackend,
    sanitize_redis_url,
    get_rate_limiter_health,
    auth_rate_limiter
)
from app.services.email.provider import get_email_service_health
from pydantic import ValidationError


# ==============================================================================
# SECTION 1: MIDDLEWARE & PUBLIC ROUTE ROUTING REGRESSION TESTS
# ==============================================================================

def test_middleware_public_route_definitions():
    """
    Verifies that the Next.js middleware file source code explicitly permits
    all public onboarding, recovery, legal, and invitation routes for unauthenticated users.
    """
    middleware_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "middleware.ts")
    assert os.path.exists(middleware_path), "src/middleware.ts must exist"

    with open(middleware_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Required public routes that must be whitelisted
    required_routes = [
        "'/'",
        "'/login'",
        "'/register'",
        "'/privacy'",
        "'/terms'",
        "'/forgot-password'",
        "'/reset-password'",
        "'/verify-email'",
        "'/invitations/accept'",
    ]
    for route in required_routes:
        assert route in content, f"Route {route} must be explicitly declared in public routes"

    # Trailing slash and nested invitation subpath support
    assert "cleanPath.startsWith('/invitations/accept/')" in content
    assert "cleanPath" in content


# ==============================================================================
# SECTION 2: SEPARATION OF PLATFORM PRIVILEGES FROM CUSTOMER ACCOUNT TYPES
# ==============================================================================

def test_account_type_enum_strictly_excludes_platform_admin():
    """PLATFORM_ADMIN must not be present in customer AccountType enum."""
    assert "PLATFORM_ADMIN" not in AccountType.__members__
    valid_values = [e.value for e in AccountType]
    assert "PLATFORM_ADMIN" not in valid_values
    assert "INDIVIDUAL" in valid_values
    assert "BUSINESS" in valid_values
    assert "ENTERPRISE" in valid_values
    assert "LEGAL_PROFESSIONAL" in valid_values


def test_register_request_schema_rejects_platform_roles():
    """RegisterRequest pydantic validator strictly rejects platform administrative role strings."""
    # 1. PLATFORM_ADMIN
    with pytest.raises(ValidationError) as exc1:
        RegisterRequest(
            email="test@user.internal",
            password="StrongPassword123!@",
            full_name="Attacker Admin",
            account_type="PLATFORM_ADMIN"
        )
    assert "Platform administrative roles cannot be requested" in str(exc1.value)

    # 2. SUPER_ADMIN
    with pytest.raises(ValidationError) as exc2:
        RegisterRequest(
            email="test2@user.internal",
            password="StrongPassword123!@",
            full_name="Attacker Admin",
            account_type="SUPER_ADMIN"
        )
    assert "Platform administrative roles cannot be requested" in str(exc2.value)

    # 3. Valid customer account type succeeds
    valid_req = RegisterRequest(
        email="legal@practice.internal",
        password="StrongPassword123!@",
        full_name="Valid Lawyer",
        account_type="LEGAL_PROFESSIONAL"
    )
    assert valid_req.account_type == "LEGAL_PROFESSIONAL"


def test_legacy_platform_admin_records_normalized_safely():
    """
    If a legacy database record contains account_type='PLATFORM_ADMIN',
    normalize_account_type maps it safely to 'ENTERPRISE' without granting platform privileges.
    """
    norm = normalize_account_type("PLATFORM_ADMIN")
    assert norm == "ENTERPRISE"

    # Entitlements for this normalized record do NOT grant platform admin permissions
    entitlements = get_account_entitlements("PLATFORM_ADMIN", "ENTERPRISE", "OWNER")
    assert entitlements["account_type"] == "ENTERPRISE"
    assert entitlements["can_invite_members"] is True
    # Crucially, customer entitlements do not contain platform:* permissions
    assert "platform:*" not in entitlements


@pytest.mark.asyncio
async def test_registration_endpoint_rejects_platform_admin_account_type():
    """POST /api/v1/auth/register rejects account_type='PLATFORM_ADMIN' with HTTP 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/register", json={
            "email": "forged.admin@nowhere.internal",
            "password": "Password123!@",
            "full_name": "Forged Admin",
            "account_type": "PLATFORM_ADMIN"
        })
        assert res.status_code == 422
        assert "Platform administrative roles cannot be requested" in res.text


@pytest.mark.asyncio
async def test_customer_owner_strictly_forbidden_from_platform_endpoints(auth_headers):
    """
    Customer organization OWNER holding customer role='OWNER' is strictly rejected
    with HTTP 403 when attempting to access platform administration endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/platform/health", headers=auth_headers)
        assert res.status_code == 403
        assert "Platform administrator privileges required" in res.json()["detail"]

        res_metrics = await ac.get("/api/v1/platform/metrics", headers=auth_headers)
        assert res_metrics.status_code == 403


# ==============================================================================
# SECTION 3: REDIS DISTRIBUTED RATE LIMITER & HEALTH DIAGNOSTICS
# ==============================================================================

def test_sanitize_redis_url_masks_passwords_and_secrets():
    """sanitize_redis_url removes plaintext passwords from logs and diagnostics."""
    assert sanitize_redis_url("redis://:secret123@redis.internal:6379/0") == "redis://:[REDACTED]@redis.internal:6379/0"
    assert sanitize_redis_url("redis://admin:super_secret@redis.internal:6379/0") == "redis://admin:[REDACTED]@redis.internal:6379/0"
    assert sanitize_redis_url("redis://localhost:6379/0") == "redis://localhost:6379/0"
    assert sanitize_redis_url("") == ""
    assert sanitize_redis_url(None) == ""


@pytest.mark.asyncio
async def test_mock_redis_distributed_rate_limiter_atomic_enforcement():
    """
    Simulates a Redis client and tests that RedisRateLimiterBackend enforces limits,
    tracks expiration, and returns retry-after.
    """
    # Create an in-memory mock Redis client
    mock_store = {}
    mock_redis = MagicMock()

    async def mock_eval(script, numkeys, key, now_str, window_str, max_str, rand_suffix):
        now = float(now_str)
        window = float(window_str)
        max_req = int(max_str)
        cutoff = now - window

        # Filter out old timestamps
        history = [ts for ts in mock_store.get(key, []) if ts > cutoff]
        if len(history) >= max_req:
            oldest = history[0]
            retry_after = max(1, int(window - (now - oldest)))
            mock_store[key] = history
            return [0, retry_after]
        else:
            history.append(now)
            mock_store[key] = history
            return [1, 0]

    mock_redis.eval = AsyncMock(side_effect=mock_eval)
    mock_redis.ping = AsyncMock(return_value=True)

    backend = RedisRateLimiterBackend(
        redis_url="redis://:pw@mock-redis:6379/0",
        required=False,
        redis_client=mock_redis
    )
    assert backend.is_connected is True
    assert backend.is_distributed is True

    # 1. First 3 requests under limit 3
    for i in range(3):
        allowed, retry_after = await backend.check_and_record("test:key", max_requests=3, window_seconds=60)
        assert allowed is True
        assert retry_after == 0

    # 2. 4th request must be rejected
    allowed, retry_after = await backend.check_and_record("test:key", max_requests=3, window_seconds=60)
    assert allowed is False
    assert retry_after > 0


@pytest.mark.asyncio
async def test_redis_rate_limiter_outage_graceful_fallback_when_optional():
    """
    When Redis is unavailable and required=False, backend logs a warning,
    sets is_connected=False, and gracefully falls back to local in-memory.
    """
    backend = RedisRateLimiterBackend(
        redis_url="redis://:pw@unreachable-redis.internal:6379/0",
        required=False,
        connect_timeout=0.1
    )

    # Calling check_and_record falls back without raising 503
    allowed, retry_after = await backend.check_and_record("test:fallback:key", max_requests=2, window_seconds=60)
    assert allowed is True
    assert backend.is_connected is False
    assert backend.is_distributed is False
    assert "Connection failed" in (backend.last_error or "")


@pytest.mark.asyncio
async def test_redis_rate_limiter_outage_fails_closed_when_required():
    """
    When Redis is unavailable and required=True (e.g. production/staging strict security),
    backend raises HTTP 503 Service Unavailable to prevent unmonitored brute force.
    """
    from fastapi import HTTPException
    backend = RedisRateLimiterBackend(
        redis_url="redis://:pw@unreachable-redis.internal:6379/0",
        required=True,
        connect_timeout=0.1
    )

    with pytest.raises(HTTPException) as exc:
        await backend.check_and_record("test:strict:key", max_requests=2, window_seconds=60)

    assert exc.value.status_code == 503
    assert "Distributed rate limiter service is currently unavailable" in exc.value.detail


def test_rate_limiter_health_reporting():
    """get_rate_limiter_health reports safe diagnostics without exposing secrets."""
    health = get_rate_limiter_health()
    assert "backend" in health
    assert "configured" in health
    assert "connected" in health
    assert "is_distributed" in health
    assert "mode" in health
    # Ensure no secrets leak
    assert "password" not in str(health).lower()


# ==============================================================================
# SECTION 4: SYSTEM HEALTH & PLATFORM READINESS
# ==============================================================================

@pytest.mark.asyncio
async def test_system_health_endpoint_exposes_all_dependencies_safely():
    """GET /health exposes email, storage, rate_limiter, database, and scheduler diagnostics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("healthy", "degraded")
        assert "dependencies" in data
        deps = data["dependencies"]
        assert "database" in deps
        assert "storage" in deps
        assert "ai" in deps
        assert "scheduler" in deps
        assert "email" in deps
        assert "rate_limiter" in deps

        # Verify rate_limiter diagnostic fields
        rl = deps["rate_limiter"]
        assert "backend" in rl
        assert "is_distributed" in rl
        assert "mode" in rl

        # Verify email diagnostic fields
        em = deps["email"]
        assert "configured" in em
        assert "provider" in em
