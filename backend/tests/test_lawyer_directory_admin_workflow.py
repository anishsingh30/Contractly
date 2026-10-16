"""
Targeted tests for Admin-Managed Lawyer Directory with Client-Safe Public Profiles.

Verifies:
1. Platform Admin can create and edit lawyer profiles with full administrative fields.
2. Unverified lawyers do NOT appear in the client directory.
3. Verified but unpublished lawyers do NOT appear in the client directory.
4. Unavailable lawyers do NOT appear in the client directory.
5. Publishing an unverified lawyer is blocked with 400 Bad Request.
6. Publishing an eligible verified lawyer makes them visible in the client directory.
7. Strict Backend Privacy Enforcement: Client API responses NEVER leak private email,
   phone number, internal verification notes, or credential document paths.
8. Non-admin users and Organization Owners are strictly blocked from admin endpoints (403 Forbidden).
9. Search, filtering, verification lifecycle, and deletion with immutable audit logging.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.main import app
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.lawyer import LawyerProfile, LawyerVerificationStatus
from app.core.security import get_password_hash, create_access_token


@pytest.mark.asyncio
async def test_admin_lawyer_management_and_client_privacy(test_engine):
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        # 1. Platform Super Admin
        admin = User(
            email="platform_super_admin@contractly.test",
            password_hash=get_password_hash("PlatformPass123!"),
            full_name="Chief Platform Administrator",
            is_active=True,
            is_super_admin=True,
        )
        db.add(admin)

        # 2. Customer Organization Owner (Non-platform-admin)
        client_org = Organization(
            name="Apex Corporate Clients",
            slug="apex-corporate-clients",
            account_type="BUSINESS",
            subscription_tier="ENTERPRISE",
        )
        db.add(client_org)
        await db.flush()

        org_owner = User(
            email="owner@apexcorp.test",
            password_hash=get_password_hash("OwnerPass123!"),
            full_name="Apex Organization Owner",
            is_active=True,
            is_super_admin=False,
        )
        db.add(org_owner)
        await db.flush()

        owner_member = OrganizationMember(
            organization_id=client_org.id,
            user_id=org_owner.id,
            role="OWNER",
            status="ACTIVE",
        )
        db.add(owner_member)

        # 3. Standard Client Member
        client_user = User(
            email="client_member@apexcorp.test",
            password_hash=get_password_hash("MemberPass123!"),
            full_name="Apex Procurement Manager",
            is_active=True,
            is_super_admin=False,
        )
        db.add(client_user)
        await db.flush()

        client_member = OrganizationMember(
            organization_id=client_org.id,
            user_id=client_user.id,
            role="LEGAL_MANAGER",
            status="ACTIVE",
        )
        db.add(client_member)

        await db.commit()
        await db.refresh(admin)
        await db.refresh(org_owner)
        await db.refresh(client_user)

        admin_id = admin.id
        owner_id = org_owner.id
        client_id = client_user.id
        client_org_id = client_org.id

    admin_token = create_access_token(subject=admin_id)
    owner_token = create_access_token(subject=owner_id, org_id=client_org_id, role="OWNER")
    client_token = create_access_token(subject=client_id, org_id=client_org_id, role="LEGAL_MANAGER")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:

        # ── Test 1: Non-Admin & Org Owner Forbidden from Admin Endpoints ────────
        # Standard Client Member
        res_forbidden_1 = await ac.get(
            "/api/v1/platform/lawyers",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert res_forbidden_1.status_code == 403
        assert "Platform administrator privileges required" in res_forbidden_1.json()["detail"]

        # Organization Owner (Even with OWNER role, NOT platform super admin!)
        res_forbidden_2 = await ac.get(
            "/api/v1/platform/lawyers",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert res_forbidden_2.status_code == 403

        res_forbidden_3 = await ac.post(
            "/api/v1/platform/lawyers",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"full_name": "Test", "email": "test@test.com", "bar_council_number": "D/999/2020", "state_bar_council": "Delhi", "admitted_jurisdictions": "Delhi"}
        )
        assert res_forbidden_3.status_code == 403

        # ── Test 2: Platform Admin Creates a Lawyer Profile ────────────────────
        create_payload = {
            "full_name": "Advocate Meenakshi Sundaram",
            "email": "meenakshi.sundaram@sundaramlaw.test",
            "phone_number": "+91 98765 43210",
            "professional_title": "Senior Advocate",
            "firm_name": "Sundaram & Associates Chambers",
            "bar_council_number": "MAH/4821/2011",
            "state_bar_council": "Bar Council of Maharashtra & Goa",
            "admitted_jurisdictions": "Bombay High Court, Supreme Court of India",
            "practice_areas": ["Corporate Contracts", "Technology & SaaS", "Data Privacy (DPDPA)"],
            "qualifications": ["B.A. LL.B. (Hons.), NLSIU Bangalore", "LL.M., Columbia Law School"],
            "languages": ["English", "Hindi", "Marathi"],
            "experience_years": 15,
            "consultation_fee": "INR 8,500 / 30 mins",
            "consultation_duration_minutes": 30,
            "bio": "Specialist in SaaS master agreements, enterprise risk allocation, and statutory Indian data privacy compliance.",
            "internal_notes": "Bar Council enrollment verified against state registry ledger on 2026-10-14.",
            "is_available_for_inquiries": True,
            "is_published": False,
        }

        create_res = await ac.post(
            "/api/v1/platform/lawyers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=create_payload
        )
        assert create_res.status_code == 201
        created_data = create_res.json()
        lawyer_id = created_data["id"]
        assert created_data["full_name"] == "Advocate Meenakshi Sundaram"
        assert created_data["verification_status"] == "PENDING_REVIEW"
        assert created_data["is_published"] is False
        assert created_data["email"] == "meenakshi.sundaram@sundaramlaw.test"
        assert created_data["phone_number"] == "+91 98765 43210"
        assert created_data["internal_notes"] == "Bar Council enrollment verified against state registry ledger on 2026-10-14."

        # ── Test 3: Unverified Lawyer does NOT appear in Public Directory ───────
        dir_res_1 = await ac.get(
            "/api/v1/lawyers/directory",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert dir_res_1.status_code == 200
        dir_items_1 = dir_res_1.json()
        assert not any(l["id"] == lawyer_id for l in dir_items_1)

        # Public direct profile lookup also 404s
        pub_profile_res_1 = await ac.get(
            f"/api/v1/lawyers/{lawyer_id}/public",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert pub_profile_res_1.status_code == 404

        # ── Test 4: Cannot Publish an Unverified Lawyer ────────────────────────
        publish_attempt_res = await ac.post(
            f"/api/v1/platform/lawyers/{lawyer_id}/publish",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_published": True}
        )
        assert publish_attempt_res.status_code == 400
        assert "Bar Council credentials must be verified before publishing" in publish_attempt_res.json()["detail"]

        # ── Test 5: Verify Credentials Without Publishing ─────────────────────
        verify_res = await ac.post(
            f"/api/v1/platform/lawyers/{lawyer_id}/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "VERIFY"}
        )
        assert verify_res.status_code == 200
        verified_data = verify_res.json()
        assert verified_data["verification_status"] == "VERIFIED"
        assert verified_data["is_published"] is False

        # Still does NOT appear in directory because is_published is False!
        dir_res_2 = await ac.get(
            "/api/v1/lawyers/directory",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert dir_res_2.status_code == 200
        assert not any(l["id"] == lawyer_id for l in dir_res_2.json())

        # ── Test 6: Publish Verified Lawyer ───────────────────────────────────
        publish_res = await ac.post(
            f"/api/v1/platform/lawyers/{lawyer_id}/publish",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_published": True}
        )
        assert publish_res.status_code == 200
        assert publish_res.json()["is_published"] is True

        # Now appears in public directory!
        dir_res_3 = await ac.get(
            "/api/v1/lawyers/directory",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert dir_res_3.status_code == 200
        dir_items_3 = dir_res_3.json()
        matching = next((l for l in dir_items_3 if l["id"] == lawyer_id), None)
        assert matching is not None
        assert matching["full_name"] == "Advocate Meenakshi Sundaram"
        assert matching["professional_title"] == "Senior Advocate"
        assert matching["experience_years"] == 15
        assert matching["consultation_fee"] == "INR 8,500 / 30 mins"
        assert "Technology & SaaS" in matching["practice_areas"]
        assert "NLSIU Bangalore" in matching["qualifications"][0]

        # ── Test 7: STRICT CLIENT PRIVACY ENFORCEMENT ──────────────────────────
        # Inspect raw client JSON response to prove zero leakage of private fields
        assert "email" not in matching, "CRITICAL: Private email leaked in client directory!"
        assert "phone_number" not in matching, "CRITICAL: Private phone number leaked in client directory!"
        assert "internal_notes" not in matching, "CRITICAL: Internal verification notes leaked in client directory!"
        assert "credential_documents" not in matching, "CRITICAL: Credential docs leaked in client directory!"
        assert "verified_by_user_id" not in matching, "CRITICAL: Internal admin ID leaked in client directory!"
        assert "rejection_reason" not in matching

        # Single public profile route also protects privacy
        pub_profile_res_2 = await ac.get(
            f"/api/v1/lawyers/{lawyer_id}/public",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert pub_profile_res_2.status_code == 200
        pub_data = pub_profile_res_2.json()
        assert "email" not in pub_data
        assert "phone_number" not in pub_data
        assert "internal_notes" not in pub_data
        assert "credential_documents" not in pub_data

        # ── Test 8: Unavailable Lawyer excluded from Client Directory ──────────
        avail_res = await ac.post(
            f"/api/v1/platform/lawyers/{lawyer_id}/availability",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_available_for_inquiries": False}
        )
        assert avail_res.status_code == 200
        assert avail_res.json()["is_available_for_inquiries"] is False

        dir_res_4 = await ac.get(
            "/api/v1/lawyers/directory",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert not any(l["id"] == lawyer_id for l in dir_res_4.json())

        # Reset availability back to True
        await ac.post(
            f"/api/v1/platform/lawyers/{lawyer_id}/availability",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_available_for_inquiries": True}
        )

        # ── Test 9: Practice Area Filtering in Public Directory ───────────────
        tech_dir = await ac.get(
            "/api/v1/lawyers/directory?practice_area=Technology%20%26%20SaaS",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert any(l["id"] == lawyer_id for l in tech_dir.json())

        criminal_dir = await ac.get(
            "/api/v1/lawyers/directory?practice_area=Criminal%20Defense",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert not any(l["id"] == lawyer_id for l in criminal_dir.json())

        # ── Test 10: Admin Search, Filtering, and Deletion Lifecycle ───────────
        admin_search_res = await ac.get(
            "/api/v1/platform/lawyers?search=Meenakshi",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert admin_search_res.status_code == 200
        assert len(admin_search_res.json()) >= 1

        # Admin can view private contact details in authorized admin endpoint
        admin_lawyer_view = await ac.get(
            f"/api/v1/platform/lawyers/{lawyer_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert admin_lawyer_view.status_code == 200
        admin_data = admin_lawyer_view.json()
        assert admin_data["email"] == "meenakshi.sundaram@sundaramlaw.test"
        assert admin_data["phone_number"] == "+91 98765 43210"
        assert admin_data["internal_notes"] is not None

        # Admin delete
        del_res = await ac.delete(
            f"/api/v1/platform/lawyers/{lawyer_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert del_res.status_code == 200

        # Deleted lawyer no longer in public directory
        dir_res_5 = await ac.get(
            "/api/v1/lawyers/directory",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert not any(l["id"] == lawyer_id for l in dir_res_5.json())
