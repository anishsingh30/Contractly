import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_auth_register_and_login():
    import uuid
    test_email = f"test_counsel_{uuid.uuid4().hex[:8]}@acme.internal"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register new test user
        reg_data = {
            "email": test_email,
            "password": "Password123!",
            "full_name": "Counsel Test",
            "organization_name": f"Acme Legal {uuid.uuid4().hex[:6]}",
            "account_type": "BUSINESS",
            "role": "LEGAL_MANAGER"
        }
        reg_res = await ac.post("/api/v1/auth/register", json=reg_data)
        assert reg_res.status_code == 200
        token_info = reg_res.json()
        assert "access_token" in token_info
        assert token_info["user"]["email"] == test_email

        # Login with registered credentials
        login_data = {
            "email": test_email,
            "password": "Password123!"
        }
        login_res = await ac.post("/api/v1/auth/login", json=login_data)
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()
        token = login_res.json()["access_token"]

        # Update profile full_name
        patch_res = await ac.patch(
            "/api/v1/auth/profile",
            json={"full_name": "Counsel Updated"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["full_name"] == "Counsel Updated"

        # Verify /auth/me reflects the update
        me_res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.json()["full_name"] == "Counsel Updated"
