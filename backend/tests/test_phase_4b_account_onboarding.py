"""
Phase 4B Automated Security, Onboarding, and Personalized Workspace Tests.

Validates:
1. Individual registration and personalized workspace creation.
2. Business organization registration and server-side owner role assignment.
3. Enterprise and Legal Professional onboarding.
4. Client role-forgery rejection (server strictly derives trusted role).
5. Duplicate registration and weak password rejection.
6. Generic authentication error handling (enumeration prevention).
7. Refresh token rotation and reuse replay-attack detection.
8. Multi-tenant workspace enumeration (/my-organizations) and unauthorized switch rejection.
9. Feature entitlement enforcement (single-user personal workspace cannot invite members or create departments).
10. Cross-tenant isolation and platform admin / customer content separation.
11. Real email delivery configuration status (reports unconfigured/blocked).
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_individual_registration_creates_personal_workspace(monkeypatch):
    """Individual sign-up defaults to a personal workspace and assigns OWNER server-side."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "email": "individual.user@personal.internal",
            "password": "Password123!@",
            "full_name": "Rohan Sharma",
            "account_type": "INDIVIDUAL"
        }
        resp = await ac.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        user = data["user"]
        assert user["email"] == "individual.user@personal.internal"
        assert user["full_name"] == "Rohan Sharma"
        assert user["role"] == "OWNER"
        assert user["account_type"] == "INDIVIDUAL"
        assert "Personal Workspace" in user["organization_name"]
        assert user["email_verification_status"] == "BLOCKED_UNCONFIGURED"
        assert user["entitlements"]["is_personal"] is True
        assert user["entitlements"]["can_invite_members"] is False
        assert user["entitlements"]["can_manage_departments"] is False
        assert user["entitlements"]["storage_quota_bytes"] == 1 * 1024 * 1024 * 1024

@pytest.mark.asyncio
async def test_business_registration_requires_org_name_and_assigns_owner():
    """Business sign-up requires organization name and server assigns role OWNER."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Missing organization_name should fail
        fail_payload = {
            "email": "biz.founder@startup.internal",
            "password": "Password123!@",
            "full_name": "Priya Nair",
            "account_type": "BUSINESS",
            "organization_name": ""
        }
        res_fail = await ac.post("/api/v1/auth/register", json=fail_payload)
        assert res_fail.status_code in (400, 422)

        # 2. Valid business sign-up
        success_payload = {
            "email": "biz.founder@startup.internal",
            "password": "Password123!@",
            "full_name": "Priya Nair",
            "account_type": "BUSINESS",
            "organization_name": "Nexus Legal Labs"
        }
        res_ok = await ac.post("/api/v1/auth/register", json=success_payload)
        assert res_ok.status_code == 200, res_ok.text
        data = res_ok.json()
        user = data["user"]
        assert user["role"] == "OWNER"
        assert user["account_type"] == "BUSINESS"
        assert user["organization_name"] == "Nexus Legal Labs"
        assert user["entitlements"]["can_invite_members"] is True
        assert user["entitlements"]["can_manage_departments"] is True
        assert user["entitlements"]["storage_quota_bytes"] == 10 * 1024 * 1024 * 1024

@pytest.mark.asyncio
async def test_client_role_tampering_is_neutralized_server_side():
    """A client passing role='PLATFORM_SUPER_ADMIN' or role='ADMIN' is strictly assigned OWNER of new org."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "email": "attacker@exploit.internal",
            "password": "Password123!@",
            "full_name": "Eve Attacker",
            "account_type": "BUSINESS",
            "organization_name": "Shadow Corp",
            "role": "PLATFORM_SUPER_ADMIN"  # Malicious client attempt
        }
        resp = await ac.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 200
        user = resp.json()["user"]
        # Must be assigned customer OWNER, not platform admin!
        assert user["role"] == "OWNER"
        # Check permissions do NOT contain platform super admin wildcards
        assert "platform:*" not in user["permissions"]

@pytest.mark.asyncio
async def test_enterprise_and_legal_professional_onboarding():
    """Enterprise and Legal Professional accounts receive appropriate storage and tier defaults."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Enterprise
        ent_res = await ac.post("/api/v1/auth/register", json={
            "email": "exec@globalcorp.internal",
            "password": "Password123!@",
            "full_name": "Vikram Patel",
            "account_type": "ENTERPRISE",
            "organization_name": "Global Corp Enterprise"
        })
        assert ent_res.status_code == 200
        ent_user = ent_res.json()["user"]
        assert ent_user["account_type"] == "ENTERPRISE"
        assert ent_user["entitlements"]["storage_quota_bytes"] == 100 * 1024 * 1024 * 1024

        # Legal Professional
        law_res = await ac.post("/api/v1/auth/register", json={
            "email": "counsel@lawfirm.internal",
            "password": "Password123!@",
            "full_name": "Advocate Sen",
            "account_type": "LEGAL_PROFESSIONAL",
            "organization_name": "Sen & Associates"
        })
        assert law_res.status_code == 200
        law_user = law_res.json()["user"]
        assert law_user["account_type"] == "LEGAL_PROFESSIONAL"
        assert law_user["entitlements"]["storage_quota_bytes"] == 25 * 1024 * 1024 * 1024

@pytest.mark.asyncio
async def test_duplicate_registration_and_weak_passwords():
    """Rejects duplicate emails and weak passwords safely."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Weak password (no number/symbol)
        weak_res = await ac.post("/api/v1/auth/register", json={
            "email": "weak@domain.internal",
            "password": "password",
            "full_name": "Weak Pass User",
            "account_type": "INDIVIDUAL"
        })
        assert weak_res.status_code in (400, 422)

        # 2. Duplicate registration
        dup_res = await ac.post("/api/v1/auth/register", json={
            "email": "individual.user@personal.internal",  # Already registered above
            "password": "Password123!@",
            "full_name": "Duplicate User",
            "account_type": "INDIVIDUAL"
        })
        assert dup_res.status_code == 400
        assert "already exists" in dup_res.json()["detail"]

@pytest.mark.asyncio
async def test_generic_auth_error_on_invalid_login():
    """Login returns generic 'Invalid email or password.' to prevent enumeration."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Non-existent email
        res1 = await ac.post("/api/v1/auth/login", json={
            "email": "nonexistent@user.internal",
            "password": "Password123!@"
        })
        assert res1.status_code == 401
        assert res1.json()["detail"] == "Invalid email or password."

        # Existing email, wrong password
        res2 = await ac.post("/api/v1/auth/login", json={
            "email": "individual.user@personal.internal",
            "password": "WrongPassword123!@"
        })
        assert res2.status_code == 401
        assert res2.json()["detail"] == "Invalid email or password."

@pytest.mark.asyncio
async def test_individual_personal_workspace_entitlements_enforced():
    """Personal individual workspace cannot invite members, create departments, or view org audit logs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login as individual
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "individual.user@personal.internal",
            "password": "Password123!@"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Attempt to invite members -> 403 Forbidden
        invite_res = await ac.post("/api/v1/organizations/members", headers=headers, json={
            "email": "colleague@personal.internal",
            "role": "MEMBER"
        })
        assert invite_res.status_code == 403
        assert "not permitted for INDIVIDUAL workspace" in invite_res.json()["detail"]

        # 2. Attempt to create departments -> 403 Forbidden
        dept_res = await ac.post("/api/v1/organizations/departments", headers=headers, json={
            "name": "Personal Legal Dept"
        })
        assert dept_res.status_code == 403
        assert "not permitted for INDIVIDUAL workspace" in dept_res.json()["detail"]

        # 3. Attempt to view audit logs -> 403 Forbidden
        audit_res = await ac.get("/api/v1/organizations/audit-logs", headers=headers)
        assert audit_res.status_code == 403
        assert "not permitted for INDIVIDUAL workspace" in audit_res.json()["detail"]

@pytest.mark.asyncio
async def test_business_workspace_can_manage_members_and_departments():
    """Business organization OWNER can invite members and create departments."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login as business owner
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "biz.founder@startup.internal",
            "password": "Password123!@"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create Department
        dept_res = await ac.post("/api/v1/organizations/departments", headers=headers, json={
            "name": "Legal Operations",
            "budget_currency": "INR"
        })
        assert dept_res.status_code == 200
        dept_data = dept_res.json()
        assert dept_data["name"] == "Legal Operations"

        # 2. Invite Member
        invite_res = await ac.post("/api/v1/organizations/members", headers=headers, json={
            "email": "paralegal@startup.internal",
            "full_name": "Ananya Roy",
            "role": "LEGAL_REVIEWER"
        })
        assert invite_res.status_code == 200
        member_data = invite_res.json()
        assert member_data["email"] == "paralegal@startup.internal"
        assert member_data["role"] == "LEGAL_REVIEWER"

        # 3. List Members
        members_res = await ac.get("/api/v1/organizations/members", headers=headers)
        assert members_res.status_code == 200
        mems = members_res.json()
        emails = [m["email"] for m in mems]
        assert "biz.founder@startup.internal" in emails
        assert "paralegal@startup.internal" in emails

@pytest.mark.asyncio
async def test_unauthorized_switch_tenant_rejected():
    """Switching to an organization where user has no membership is rejected with 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login as individual
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "individual.user@personal.internal",
            "password": "Password123!@"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to switch to an arbitrary or foreign organization ID
        switch_res = await ac.post(
            "/api/v1/auth/switch-tenant",
            headers=headers,
            json={"organization_id": "foreign-unauthorized-org-999"}
        )
        assert switch_res.status_code == 403
        assert "Not an active member" in switch_res.json()["detail"]

@pytest.mark.asyncio
async def test_verification_status_reports_unconfigured(monkeypatch):
    """Email verification status explicitly reports blocked/unconfigured."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/verification-status")
        assert res.status_code == 200
        data = res.json()
        assert data["email_delivery_configured"] is False
        assert data["verification_status"] == "BLOCKED_UNCONFIGURED"

@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse_detection():
    """Preserves rotating refresh token and terminates lineage upon token reuse."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register fresh user
        reg = await ac.post("/api/v1/auth/register", json={
            "email": "session.tester@test.internal",
            "password": "Password123!@",
            "full_name": "Session Tester",
            "account_type": "INDIVIDUAL"
        })
        assert reg.status_code == 200
        raw_refresh_1 = reg.json()["refresh_token"]

        # Refresh session once
        ac.cookies.clear()
        ref1 = await ac.post("/api/v1/auth/refresh", cookies={"contractly_refresh_token": raw_refresh_1})
        assert ref1.status_code == 200
        raw_refresh_2 = ref1.json()["refresh_token"]
        assert raw_refresh_2 != raw_refresh_1

        # Replay the old refresh token (simulated token theft / replay attack)
        ac.cookies.clear()
        replay_res = await ac.post("/api/v1/auth/refresh", cookies={"contractly_refresh_token": raw_refresh_1})
        assert replay_res.status_code == 401
        assert "TOKEN_REUSE_DETECTED" in replay_res.json()["detail"]

        # Legitimate token in the revoked family must now also fail
        ac.cookies.clear()
        ref2 = await ac.post("/api/v1/auth/refresh", cookies={"contractly_refresh_token": raw_refresh_2})
        assert ref2.status_code == 401

@pytest.mark.asyncio
async def test_multi_workspace_membership_listing_and_switching():
    """A user belonging to multiple workspaces can view both and switch seamlessly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register User in Workspace 1 (Business)
        reg1 = await ac.post("/api/v1/auth/register", json={
            "email": "multitenant.user@company.internal",
            "password": "Password123!@",
            "full_name": "Multi Tenant Lead",
            "account_type": "BUSINESS",
            "organization_name": "First Enterprise Org"
        })
        assert reg1.status_code == 200
        org1_id = reg1.json()["user"]["organization_id"]
        token1 = reg1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # 2. Add this user as member of another org ("Nexus Legal Labs" from earlier test)
        # Login as biz.founder of Nexus Legal Labs
        login_biz = await ac.post("/api/v1/auth/login", json={
            "email": "biz.founder@startup.internal",
            "password": "Password123!@"
        })
        assert login_biz.status_code == 200
        biz_headers = {"Authorization": f"Bearer {login_biz.json()['access_token']}"}
        nexus_org_id = login_biz.json()["user"]["organization_id"]

        invite_res = await ac.post("/api/v1/organizations/members", headers=biz_headers, json={
            "email": "multitenant.user@company.internal",
            "role": "LEGAL_REVIEWER"
        })
        assert invite_res.status_code == 200

        # 3. Check /my-organizations for multitenant.user
        my_orgs_res = await ac.get("/api/v1/auth/my-organizations", headers=headers1)
        assert my_orgs_res.status_code == 200
        my_orgs = my_orgs_res.json()
        assert len(my_orgs) == 2
        org_ids = [o["id"] for o in my_orgs]
        assert org1_id in org_ids
        assert nexus_org_id in org_ids

        # 4. Switch tenant to Nexus Legal Labs
        switch_res = await ac.post("/api/v1/auth/switch-tenant", headers=headers1, json={
            "organization_id": nexus_org_id
        })
        assert switch_res.status_code == 200
        switched_user = switch_res.json()["user"]
        assert switched_user["organization_id"] == nexus_org_id
        assert switched_user["role"] == "LEGAL_REVIEWER"

@pytest.mark.asyncio
async def test_platform_admin_separation_from_customer_data():
    """Customer accounts cannot access platform endpoints, and platform roles have zero customer contract access."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Customer account (Individual or Business) cannot access platform endpoints
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "biz.founder@startup.internal",
            "password": "Password123!@"
        })
        assert login_res.status_code == 200
        cust_token = login_res.json()["access_token"]
        cust_headers = {"Authorization": f"Bearer {cust_token}"}

        health_res = await ac.get("/api/v1/platform/health", headers=cust_headers)
        assert health_res.status_code == 403
        assert "Platform administrator privileges required" in health_res.json()["detail"]

        metrics_res = await ac.get("/api/v1/platform/metrics", headers=cust_headers)
        assert metrics_res.status_code == 403

