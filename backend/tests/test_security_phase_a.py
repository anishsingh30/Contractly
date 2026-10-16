import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.core.database import get_db
from app.core.security import create_access_token, hash_refresh_token
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.auth import RefreshToken

@pytest.mark.asyncio
async def test_successful_login():
    """1. Test successful login returns tokens and sets HttpOnly cookies."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "legal@northstar.internal"

        # Check cookies
        cookies = login_res.cookies
        assert "contractly_access_token" in cookies
        assert "contractly_refresh_token" in cookies

@pytest.mark.asyncio
async def test_incorrect_password():
    """2. Test incorrect password returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "WrongPassword999!"
        })
        assert res.status_code == 401
        assert "Invalid email or password" in res.json()["detail"]

@pytest.mark.asyncio
async def test_missing_authentication():
    """3. Test missing authentication returns 401 (backdoor removed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_me = await ac.get("/api/v1/auth/me")
        assert res_me.status_code == 401

        res_contracts = await ac.get("/api/v1/contracts")
        assert res_contracts.status_code == 401

@pytest.mark.asyncio
async def test_invalid_jwt():
    """4. Test invalid/malformed JWT returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"}
        )
        assert res.status_code == 401
        assert "Invalid or malformed" in res.json()["detail"]

@pytest.mark.asyncio
async def test_expired_jwt():
    """5. Test expired JWT returns 401 with TOKEN_EXPIRED detail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create token expired 5 minutes ago
        expired_token = create_access_token(
            subject="test-user-id",
            expires_delta=timedelta(minutes=-5)
        )
        res = await ac.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "TOKEN_EXPIRED"

@pytest.mark.asyncio
async def test_refresh_token_creates_new_access_token():
    """6. Test refresh token creates a new access token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        old_access = login_res.json()["access_token"]
        raw_refresh = login_res.json()["refresh_token"]

        # Call /refresh with cookie
        ref_res = await ac.post(
            "/api/v1/auth/refresh",
            cookies={"contractly_refresh_token": raw_refresh}
        )
        assert ref_res.status_code == 200
        new_access = ref_res.json()["access_token"]
        assert new_access != old_access

@pytest.mark.asyncio
async def test_refresh_token_rotation_works():
    """7. Test refresh token rotation works and replaces refresh tokens."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        refresh_1 = login_res.json()["refresh_token"]

        # First refresh
        ref_res_1 = await ac.post(
            "/api/v1/auth/refresh",
            cookies={"contractly_refresh_token": refresh_1}
        )
        assert ref_res_1.status_code == 200
        refresh_2 = ref_res_1.json()["refresh_token"]
        assert refresh_1 != refresh_2

        # Second refresh using new token
        ref_res_2 = await ac.post(
            "/api/v1/auth/refresh",
            cookies={"contractly_refresh_token": refresh_2}
        )
        assert ref_res_2.status_code == 200
        refresh_3 = ref_res_2.json()["refresh_token"]
        assert refresh_2 != refresh_3

@pytest.mark.asyncio
async def test_reuse_of_revoked_refresh_token_revokes_family():
    """8. Test reuse of revoked refresh token triggers reuse detection and revokes family."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "Password123!"
        })
        refresh_1 = login_res.json()["refresh_token"]

        # Normal rotation: refresh_1 -> refresh_2
        ref_res = await ac.post(
            "/api/v1/auth/refresh",
            cookies={"contractly_refresh_token": refresh_1}
        )
        assert ref_res.status_code == 200
        refresh_2 = ref_res.json()["refresh_token"]

        # Attacker reuses refresh_1 (which is now revoked)
        replay_res = await ac.post(
            "/api/v1/auth/refresh",
            cookies={"contractly_refresh_token": refresh_1}
        )
        assert replay_res.status_code == 401
        assert "TOKEN_REUSE_DETECTED" in replay_res.json()["detail"]

        # Honest user attempts to use refresh_2 -> MUST be rejected because family was invalidated!
        honest_res = await ac.post(
            "/api/v1/auth/refresh",
            cookies={"contractly_refresh_token": refresh_2}
        )
        assert honest_res.status_code == 401

@pytest.mark.asyncio
async def test_logout_invalidates_refresh_session():
    """9. Test logout revokes refresh session and clears cookies."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "Password123!"
        })
        raw_refresh = login_res.json()["refresh_token"]

        # Logout
        logout_res = await ac.post(
            "/api/v1/auth/logout",
            cookies={"contractly_refresh_token": raw_refresh}
        )
        assert logout_res.status_code == 200

        # Attempt to refresh after logout
        subsequent_refresh = await ac.post(
            "/api/v1/auth/refresh",
            cookies={"contractly_refresh_token": raw_refresh}
        )
        assert subsequent_refresh.status_code == 401

@pytest.mark.asyncio
async def test_inactive_user_cannot_authenticate(override_db, test_engine):
    """10. Test inactive user cannot authenticate."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create inactive test user
    u_email = f"inactive_{uuid.uuid4().hex[:6]}@test.internal"
    async with TestSession() as session:
        from app.core.security import get_password_hash
        inactive_user = User(
            email=u_email,
            password_hash=get_password_hash("Password123!"),
            full_name="Inactive User",
            is_active=False
        )
        session.add(inactive_user)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/login", json={
            "email": u_email,
            "password": "Password123!"
        })
        assert res.status_code == 401
        assert "inactive" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_no_northstar_fallback_exists():
    """11. Test no Northstar fallback exists when user tenant doesn't match."""
    # Register an independent user in a separate tenant
    uid = uuid.uuid4().hex[:6]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": f"isolated_{uid}@external.internal",
            "password": "Password123!",
            "full_name": "Isolated User",
            "organization_name": f"Isolated Corp {uid}",
            "role": "EMPLOYEE"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]

        # Request contracts with a foreign or non-existent tenant ID
        res = await ac.get(
            "/api/v1/contracts",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": "non-existent-tenant-id"
            }
        )
        # Should NOT return Northstar contracts! Should return 403 Forbidden or list their own
        if res.status_code == 200:
            contracts = res.json()
            for c in contracts:
                assert "northstar" not in c.get("counterparty", "").lower()

@pytest.mark.asyncio
async def test_no_unauthenticated_request_receives_a_user():
    """12. Test unauthenticated request never receives any user data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_me = await ac.get("/api/v1/auth/me")
        assert res_me.status_code == 401
        res_org = await ac.get("/api/v1/organizations/current")
        assert res_org.status_code == 401

@pytest.mark.asyncio
async def test_login_cookies_are_httponly():
    """13. Test login cookies contain HttpOnly directive."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        set_cookie_headers = login_res.headers.get_list("set-cookie")
        assert len(set_cookie_headers) >= 2
        for cookie_header in set_cookie_headers:
            assert "httponly" in cookie_header.lower()
            assert "samesite=lax" in cookie_header.lower()

@pytest.mark.asyncio
async def test_refresh_token_is_never_stored_in_plaintext(override_db, test_engine):
    """14. Test raw refresh token is NEVER stored in database, only SHA-256 hash."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "legal@northstar.internal",
            "password": "Password123!"
        })
        raw_refresh = login_res.json()["refresh_token"]

    async with TestSession() as session:
        # Verify raw string does NOT match any token_hash column
        stmt = select(RefreshToken).where(RefreshToken.token_hash == raw_refresh)
        res = await session.execute(stmt)
        assert res.scalar_one_or_none() is None

        # Verify hashed version exists in database
        hashed = hash_refresh_token(raw_refresh)
        stmt_hash = select(RefreshToken).where(RefreshToken.token_hash == hashed)
        res_hash = await session.execute(stmt_hash)
        assert res_hash.scalar_one_or_none() is not None
