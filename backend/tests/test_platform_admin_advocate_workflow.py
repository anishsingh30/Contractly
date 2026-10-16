"""
Tests for Platform Admin Role, Advocate Directory Real Data, and Verification Workflow.
Enforces:
- Separation of platform super admin vs tenant workspace roles.
- Inclusion of is_super_admin and platform_role in auth responses.
- Exclusion of unverified advocate profiles from the public directory.
- End-to-end credential verification lifecycle with audit logging.
- Strict tenant privacy: aggregate counts without private contract text.
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.main import app
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.lawyer import LawyerProfile, LawyerVerificationStatus
from app.core.security import get_password_hash, create_access_token


@pytest.mark.asyncio
async def test_auth_me_returns_super_admin_flags(test_engine):
    """1. Verify /auth/me returns is_super_admin=True and platform_role=PLATFORM_SUPER_ADMIN."""
    test_email = f"platform_super_admin_{uuid.uuid4().hex[:6]}@contractly.test"
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        admin = User(
            email=test_email,
            password_hash=get_password_hash("PlatformAdmin123!"),
            full_name="Platform Chief Administrator",
            is_active=True,
            is_super_admin=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id

    token = create_access_token(subject=admin_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["is_super_admin"] is True
        assert data["platform_role"] == "PLATFORM_SUPER_ADMIN"
        assert data["email"] == test_email


@pytest.mark.asyncio
async def test_standard_user_me_returns_false_admin_flags(test_engine):
    """2. Verify standard client user has is_super_admin=False and platform_role=None."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        org = Organization(
            name="Acme Legal Client Corp",
            slug="acme-legal-client-corp",
            account_type="BUSINESS",
            subscription_tier="ENTERPRISE",
            storage_quota_bytes=5368709120,
        )
        db.add(org)
        await db.flush()

        user = User(
            email="client_user@acme.test",
            password_hash=get_password_hash("ClientPassword123!"),
            full_name="Client Contract Manager",
            is_active=True,
            is_super_admin=False,
        )
        db.add(user)
        await db.flush()

        membership = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="LEGAL_MANAGER",
            status="ACTIVE",
        )
        db.add(membership)
        await db.commit()
        await db.refresh(user)
        user_id = user.id
        org_id = org.id

    token = create_access_token(subject=user_id, org_id=org_id, role="LEGAL_MANAGER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["is_super_admin"] is False
        assert data["platform_role"] is None
        assert data["role"] == "LEGAL_MANAGER"


@pytest.mark.asyncio
async def test_platform_metrics_privacy_guarantee(test_engine):
    """3. Verify platform aggregate metrics exclude private contract bodies and include counts."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        admin = User(
            email="admin_metrics@contractly.test",
            password_hash=get_password_hash("MetricsAdmin123!"),
            full_name="Metrics Administrator",
            is_active=True,
            is_super_admin=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        admin_id = admin.id

    token = create_access_token(subject=admin_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/platform/metrics", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert "tenants_count" in data
        assert "users_count" in data
        assert "advocates_count" in data
        assert "matters_by_status" in data
        assert "privacy_notice" in data
        # Ensure no private contract contents are returned
        assert "contracts" not in data
        assert "clauses" not in data
        assert "documents" not in data


@pytest.mark.asyncio
async def test_non_admin_forbidden_from_platform_endpoints(test_engine):
    """4. Verify standard users receive 403 Forbidden on platform administration endpoints."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        org = Organization(
            name="Forbidden Test Corp",
            slug="forbidden-test-corp",
            account_type="BUSINESS",
            subscription_tier="COMMUNITY",
        )
        db.add(org)
        await db.flush()

        user = User(
            email="standard_denied@acme.test",
            password_hash=get_password_hash("DeniedPass123!"),
            full_name="Standard Employee",
            is_active=True,
            is_super_admin=False,
        )
        db.add(user)
        await db.flush()

        membership = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="EMPLOYEE",
            status="ACTIVE",
        )
        db.add(membership)
        await db.commit()
        user_id = user.id
        org_id = org.id

    token = create_access_token(subject=user_id, org_id=org_id, role="EMPLOYEE")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Check platform health
        h_res = await ac.get("/api/v1/platform/health", headers={"Authorization": f"Bearer {token}"})
        assert h_res.status_code == 403

        # Check platform metrics
        m_res = await ac.get("/api/v1/platform/metrics", headers={"Authorization": f"Bearer {token}"})
        assert m_res.status_code == 403

        # Check platform advocates
        a_res = await ac.get("/api/v1/platform/advocates", headers={"Authorization": f"Bearer {token}"})
        assert a_res.status_code == 403


@pytest.mark.asyncio
async def test_advocate_directory_excludes_unverified_and_verifies_end_to_end(test_engine):
    """
    5. Test advocate verification lifecycle:
    - Registered advocate with PENDING_REVIEW does NOT appear in /lawyers/directory.
    - Super Admin views pending advocate application via /platform/advocates.
    - Super Admin verifies advocate via /lawyers/profiles/{id}/verify.
    - Advocate now appears in /lawyers/directory for client users.
    """
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        # Create Admin
        admin = User(
            email="super_verifier@contractly.test",
            password_hash=get_password_hash("AdminVerifier123!"),
            full_name="Verification Admin",
            is_active=True,
            is_super_admin=True,
        )
        db.add(admin)

        # Create Client
        client_org = Organization(
            name="Client Search Org",
            slug="client-search-org",
            account_type="BUSINESS",
            subscription_tier="COMMUNITY",
        )
        db.add(client_org)
        await db.flush()

        client_user = User(
            email="client_searcher@client.test",
            password_hash=get_password_hash("ClientPass123!"),
            full_name="Client Searcher",
            is_active=True,
            is_super_admin=False,
        )
        db.add(client_user)
        await db.flush()

        m = OrganizationMember(
            organization_id=client_org.id,
            user_id=client_user.id,
            role="LEGAL_MANAGER",
            status="ACTIVE",
        )
        db.add(m)

        # Create Advocate user and practice organization
        adv_org = Organization(
            name="Swaminathan & Partners Chambers",
            slug="swaminathan-partners-chambers",
            account_type="LEGAL_PROFESSIONAL",
            subscription_tier="COMMUNITY",
        )
        db.add(adv_org)
        await db.flush()

        adv_user = User(
            email="advocate.radhika@chambers.test",
            password_hash=get_password_hash("AdvocatePass123!"),
            full_name="Radhika Swaminathan",
            is_active=True,
            is_super_admin=False,
        )
        db.add(adv_user)
        await db.flush()

        profile = LawyerProfile(
            user_id=adv_user.id,
            organization_id=adv_org.id,
            bar_council_number="D/1429/2012",
            state_bar_council="Bar Council of Delhi",
            admitted_jurisdictions="Supreme Court of India, Delhi High Court",
            practice_areas=["Corporate Contracts", "Technology & SaaS"],
            experience_years=14,
            consultation_fee="INR 12,500 / hr",
            bio="Senior corporate advocate specializing in cross-border tech transactions.",
            is_available_for_inquiries=True,
            verification_status=LawyerVerificationStatus.PENDING_REVIEW.value,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        profile_id = profile.id
        admin_id = admin.id
        client_user_id = client_user.id
        client_org_id = client_org.id

    client_token = create_access_token(subject=client_user_id, org_id=client_org_id, role="LEGAL_MANAGER")
    admin_token = create_access_token(subject=admin_id)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step A: Client browses directory -> Must NOT see unverified advocate
        dir_res_1 = await ac.get(
            "/api/v1/lawyers/directory",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert dir_res_1.status_code == 200
        profiles_1 = dir_res_1.json()
        assert not any(p["id"] == profile_id for p in profiles_1)

        # Step B: Super Admin lists advocate applications -> Sees the pending profile
        adv_list_res = await ac.get(
            "/api/v1/platform/advocates?status=PENDING_REVIEW",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert adv_list_res.status_code == 200
        pending_list = adv_list_res.json()
        target = next((p for p in pending_list if p["id"] == profile_id), None)
        assert target is not None
        assert target["bar_council_number"] == "D/1429/2012"
        assert target["verification_status"] == "PENDING_REVIEW"

        # Step C: Super Admin verifies advocate credentials
        verify_res = await ac.post(
            f"/api/v1/lawyers/profiles/{profile_id}/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "VERIFY"}
        )
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["verification_status"] == "VERIFIED"
        assert verify_data["verified_at"] is not None

        # Step D: Client browses directory -> Advocate now appears with verified status!
        dir_res_2 = await ac.get(
            "/api/v1/lawyers/directory",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert dir_res_2.status_code == 200
        profiles_2 = dir_res_2.json()
        verified_match = next((p for p in profiles_2 if p["id"] == profile_id), None)
        assert verified_match is not None
        assert verified_match["full_name"] == "Radhika Swaminathan"
        assert verified_match["bar_council_number"] == "D/1429/2012"
        assert verified_match["verification_status"] == "VERIFIED"
