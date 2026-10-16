"""
Regression and verification test suite for Contractly Legal Professional workspace registration.

Covers:
1. Legal Professional registration with valid required fields (with & without explicit practice name).
2. Input validation (weak passwords, empty names, invalid account types).
3. Duplicate email handling.
4. Failed registration transaction rollback (ensuring database atomicity).
5. Existing non-lawyer registration flows (Individual, Business, Enterprise).
6. Rate-limit enforcement (HTTP 429 policy validation).
7. Resilience when account_tokens table is missing (simulating unmigrated local SQLite).
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.core.rate_limiter import auth_rate_limiter


@pytest.mark.asyncio
async def test_legal_professional_registration_with_practice_name():
    """Legal Professional registration creates practice workspace with STARTER tier and 25GB quota."""
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "email": "advocate.sharma@apexlegal.internal",
            "password": "StrongLegalPass123!@",
            "full_name": "Advocate Priya Sharma",
            "account_type": "LEGAL_PROFESSIONAL",
            "organization_name": "Apex Legal Chambers"
        }
        res = await ac.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data

        user = data["user"]
        assert user["email"] == "advocate.sharma@apexlegal.internal"
        assert user["full_name"] == "Advocate Priya Sharma"
        assert user["account_type"] == "LEGAL_PROFESSIONAL"
        assert user["role"] == "OWNER"
        assert user["organization_name"] == "Apex Legal Chambers"
        assert user["subscription_tier"] == "STARTER"
        assert user["entitlements"]["storage_quota_bytes"] == 25 * 1024 * 1024 * 1024
        assert user["entitlements"]["is_personal"] is False
        assert user["entitlements"]["can_invite_members"] is True


@pytest.mark.asyncio
async def test_legal_professional_registration_default_practice_name():
    """Omitting organization_name for LEGAL_PROFESSIONAL automatically derives '{full_name} Legal Practice'."""
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "email": "solicitor.roy@practice.internal",
            "password": "SecurePracticePass1#",
            "full_name": "Kunal Roy",
            "account_type": "LEGAL_PROFESSIONAL"
        }
        res = await ac.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        user = data["user"]
        assert user["organization_name"] == "Kunal Roy Legal Practice"
        assert user["account_type"] == "LEGAL_PROFESSIONAL"


@pytest.mark.asyncio
async def test_invalid_registration_inputs():
    """Validates password strength, required full_name, and valid customer account types."""
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Weak password - no number
        res1 = await ac.post("/api/v1/auth/register", json={
            "email": "invalid1@test.internal",
            "password": "NoNumberPass!",
            "full_name": "Test User",
            "account_type": "LEGAL_PROFESSIONAL"
        })
        assert res1.status_code == 422
        assert "at least one number" in res1.text

        # 2. Weak password - no symbol
        res2 = await ac.post("/api/v1/auth/register", json={
            "email": "invalid2@test.internal",
            "password": "NoSymbolPass123",
            "full_name": "Test User",
            "account_type": "LEGAL_PROFESSIONAL"
        })
        assert res2.status_code == 422
        assert "at least one special character" in res2.text

        # 3. Empty full name
        res3 = await ac.post("/api/v1/auth/register", json={
            "email": "invalid3@test.internal",
            "password": "ValidPassword123!",
            "full_name": "   ",
            "account_type": "LEGAL_PROFESSIONAL"
        })
        assert res3.status_code == 422
        assert "Full name cannot be empty" in res3.text

        # 4. Disallowed platform administrative role
        res4 = await ac.post("/api/v1/auth/register", json={
            "email": "invalid4@test.internal",
            "password": "ValidPassword123!",
            "full_name": "Hacker Attempt",
            "account_type": "PLATFORM_ADMIN"
        })
        assert res4.status_code == 422
        assert "Platform administrative roles cannot be requested" in res4.text


@pytest.mark.asyncio
async def test_duplicate_email_handling():
    """Duplicate registration with existing email returns HTTP 400 Bad Request."""
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        reg_payload = {
            "email": "duplicate.test@chambers.internal",
            "password": "UniquePassword123!",
            "full_name": "Original Lawyer",
            "account_type": "LEGAL_PROFESSIONAL",
            "organization_name": "Original Chambers"
        }
        res1 = await ac.post("/api/v1/auth/register", json=reg_payload)
        assert res1.status_code == 200

        # Attempt to register identical email
        res2 = await ac.post("/api/v1/auth/register", json={
            "email": "duplicate.test@chambers.internal",
            "password": "DifferentPassword456!@",
            "full_name": "Second Lawyer",
            "account_type": "LEGAL_PROFESSIONAL",
            "organization_name": "Second Chambers"
        })
        assert res2.status_code == 400
        assert "User with this email already exists." in res2.json()["detail"]


@pytest.mark.asyncio
async def test_registration_transaction_rollback_on_failure():
    """Simulated database failure during registration rolls back all flushed records atomically."""
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)

    target_email = "rollback.test@chambers.internal"
    transport_no_raise = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.auth.create_access_token", side_effect=RuntimeError("Simulated token generation crash")):
        async with AsyncClient(transport=transport_no_raise, base_url="http://test") as ac:
            res = await ac.post("/api/v1/auth/register", json={
                "email": target_email,
                "password": "RollbackPass123!@",
                "full_name": "Rollback User",
                "account_type": "LEGAL_PROFESSIONAL",
                "organization_name": "Rollback Chambers"
            })
            assert res.status_code == 500

    # Verify no orphan user was created in the database
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Attempting fresh registration with same email should succeed if previous failed transaction was rolled back
        res_retry = await ac.post("/api/v1/auth/register", json={
            "email": target_email,
            "password": "RollbackPass123!@",
            "full_name": "Rollback User Clean",
            "account_type": "LEGAL_PROFESSIONAL",
            "organization_name": "Rollback Chambers Clean"
        })
        assert res_retry.status_code == 200


@pytest.mark.asyncio
async def test_existing_non_lawyer_registration_behavior():
    """Verifies INDIVIDUAL, BUSINESS, and ENTERPRISE registration flows continue functioning cleanly."""
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Individual
        res_ind = await ac.post("/api/v1/auth/register", json={
            "email": "individual.reg@test.internal",
            "password": "ValidIndPass123!",
            "full_name": "Individual Client",
            "account_type": "INDIVIDUAL"
        })
        assert res_ind.status_code == 200
        assert res_ind.json()["user"]["account_type"] == "INDIVIDUAL"
        assert res_ind.json()["user"]["entitlements"]["storage_quota_bytes"] == 1 * 1024 * 1024 * 1024

        # 2. Business
        res_biz = await ac.post("/api/v1/auth/register", json={
            "email": "biz.reg@test.internal",
            "password": "ValidBizPass123!",
            "full_name": "Business Exec",
            "account_type": "BUSINESS",
            "organization_name": "Acme Business Inc"
        })
        assert res_biz.status_code == 200
        assert res_biz.json()["user"]["account_type"] == "BUSINESS"
        assert res_biz.json()["user"]["entitlements"]["storage_quota_bytes"] == 10 * 1024 * 1024 * 1024

        # 3. Enterprise
        res_ent = await ac.post("/api/v1/auth/register", json={
            "email": "ent.reg@test.internal",
            "password": "ValidEntPass123!",
            "full_name": "Enterprise Director",
            "account_type": "ENTERPRISE",
            "organization_name": "Global Enterprise Corp"
        })
        assert res_ent.status_code == 200
        assert res_ent.json()["user"]["account_type"] == "ENTERPRISE"
        assert res_ent.json()["user"]["entitlements"]["storage_quota_bytes"] == 100 * 1024 * 1024 * 1024


@pytest.mark.asyncio
async def test_registration_rate_limit_enforcement():
    """Rate limiter allows configured max requests (5) then strictly returns HTTP 429 on subsequent attempts."""
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Make 5 attempts (configured max)
        for i in range(5):
            res = await ac.post("/api/v1/auth/register", json={
                "email": f"ratelimit{i}@test.internal",
                "password": "ValidRateLimitPass123!",
                "full_name": f"Rate Limit User {i}",
                "account_type": "LEGAL_PROFESSIONAL"
            })
            assert res.status_code == 200, f"Attempt {i+1} failed unexpectedly: {res.text}"

        # 6th attempt from the same client IP must be blocked by rate limiter
        res_blocked = await ac.post("/api/v1/auth/register", json={
            "email": "ratelimit.blocked@test.internal",
            "password": "ValidRateLimitPass123!",
            "full_name": "Blocked User",
            "account_type": "LEGAL_PROFESSIONAL"
        })
        assert res_blocked.status_code == 429
        assert "Too many registration attempts from this address" in res_blocked.json()["detail"]
        assert "Retry-After" in res_blocked.headers

    await auth_rate_limiter.reset()


@pytest.mark.asyncio
async def test_registration_resilience_without_account_tokens_table():
    """Simulates an unmigrated database schema (where account_tokens does not exist); registration succeeds with 200."""
    await auth_rate_limiter.reset()

    # Create an isolated temporary in-memory database without the account_tokens table
    isolated_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:?cache=shared",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )
    async with isolated_engine.begin() as conn:
        from app import models as _models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
        # Drop the account_tokens table to simulate unmigrated schema
        from sqlalchemy import text
        await conn.execute(text("DROP TABLE IF EXISTS account_tokens"))

    IsolatedSession = async_sessionmaker(
        bind=isolated_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )

    async def override_isolated_db():
        async with IsolatedSession() as session:
            try:
                yield session
            finally:
                await session.close()

    prev_get_db = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_isolated_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/v1/auth/register", json={
                "email": "unmigrated.lawyer@practice.internal",
                "password": "ValidLawPass123!@",
                "full_name": "Advocate Resilience",
                "account_type": "LEGAL_PROFESSIONAL",
                "organization_name": "Resilient Legal Practice"
            })
            assert res.status_code == 200, f"Expected 200 even without account_tokens table, got: {res.text}"
            data = res.json()
            assert data["token_type"] == "bearer"
            assert "access_token" in data
            assert data["user"]["account_type"] == "LEGAL_PROFESSIONAL"
            assert data["user"]["organization_name"] == "Resilient Legal Practice"
    finally:
        if prev_get_db is not None:
            app.dependency_overrides[get_db] = prev_get_db
        else:
            app.dependency_overrides.pop(get_db, None)
        await isolated_engine.dispose()

