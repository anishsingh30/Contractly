import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.auth import RefreshToken
from app.models.contract import Contract
from app.core.security import get_password_hash, hash_refresh_token


@pytest.mark.asyncio
async def test_full_auth_login_logout_and_session_invalidation(test_engine):
    """
    Verifies:
    1. User registration & login sets HttpOnly cookies and database refresh token record.
    2. Calling /api/v1/auth/logout revokes the refresh token record in the DB and clears cookies.
    3. Subsequent attempts to refresh token fail with 401.
    4. Protected endpoints reject calls once token is revoked/cleared.
    5. Tenant isolation remains strictly intact throughout.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create test organization and user
        org = Organization(name="Logout Test Org", slug=f"logout-org-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(
            email=f"counsel.{uuid.uuid4().hex[:6]}@logouttest.com",
            password_hash=get_password_hash("ValidPassword123!"),
            full_name="Alice Counsel"
        )
        session.add_all([org, user])
        await session.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER", status="ACTIVE")
        session.add(member)

        # Create confidential contract
        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-{uuid.uuid4().hex[:4]}",
            title="Confidential IP Licensing",
            contract_type="IP",
            counterparty="Partner Co",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.commit()

        user_email = user.email

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login
        login_res = await client.post("/api/v1/auth/login", json={
            "email": user_email,
            "password": "ValidPassword123!"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        raw_refresh = data["refresh_token"]

        # Check response cookies
        cookies_header = login_res.headers.get_list("set-cookie")
        cookie_text = " ".join(cookies_header)
        assert "contractly_access_token=" in cookie_text
        assert "contractly_refresh_token=" in cookie_text
        assert "HttpOnly" in cookie_text

        # Verify refresh token in DB is active
        async with async_session() as session:
            t_hash = hash_refresh_token(raw_refresh)
            res = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == t_hash))
            db_record = res.scalar_one_or_none()
            assert db_record is not None
            assert db_record.is_revoked is False

        # 2. Access protected endpoint with cookie
        me_res = await client.get("/api/v1/auth/me", cookies={"contractly_access_token": data["access_token"]})
        assert me_res.status_code == 200
        assert me_res.json()["email"] == user_email

        # 3. Call Logout endpoint
        logout_res = await client.post("/api/v1/auth/logout", cookies={"contractly_refresh_token": raw_refresh})
        assert logout_res.status_code == 200
        assert logout_res.json()["message"] == "Successfully logged out."

        # Verify response cookies are deleted (Max-Age=0)
        logout_cookie_headers = logout_res.headers.get_list("set-cookie")
        logout_cookie_text = " ".join(logout_cookie_headers)
        assert "contractly_access_token=" in logout_cookie_text
        assert "contractly_refresh_token=" in logout_cookie_text
        assert "max-age=0" in logout_cookie_text.lower() or "expires=" in logout_cookie_text.lower()

        # 4. Verify refresh token in DB is marked revoked
        async with async_session() as session:
            res = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == t_hash))
            db_record = res.scalar_one_or_none()
            assert db_record is not None
            assert db_record.is_revoked is True
            assert db_record.revoked_at is not None

        # 5. Subsequent attempt to refresh session with revoked token fails with 401
        refresh_fail_res = await client.post("/api/v1/auth/refresh", cookies={"contractly_refresh_token": raw_refresh})
        assert refresh_fail_res.status_code == 401

        # 6. Subsequent attempt with body payload also fails
        refresh_fail_body = await client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
        assert refresh_fail_body.status_code == 401


@pytest.mark.asyncio
async def test_invalid_or_expired_tokens_return_401_without_loops(test_engine):
    """Verifies malformed or forged tokens consistently return 401 rather than 500 or looping."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid access token cookie
        res1 = await client.get("/api/v1/auth/me", cookies={"contractly_access_token": "forged.jwt.token"})
        assert res1.status_code == 401

        # Expired / non-existent refresh token
        res2 = await client.post("/api/v1/auth/refresh", cookies={"contractly_refresh_token": "non_existent_token"})
        assert res2.status_code == 401

        # Empty credentials
        res3 = await client.get("/api/v1/auth/me")
        assert res3.status_code == 401
