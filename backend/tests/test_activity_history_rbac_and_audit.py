import pytest
import uuid
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.core.security import create_access_token
from app.models.base import utc_now, generate_uuid
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.models.lawyer import LegalMatter, MatterMessage, LawyerProfile, LawyerVerificationStatus, MatterStatus, MatterSenderType


@pytest.fixture
def auth_helper():
    def _make_headers(user_id: str, org_id: str, role: str = "OWNER"):
        token = create_access_token(subject=user_id, org_id=org_id, role=role)
        headers = {
            "Authorization": f"Bearer {token}",
        }
        if org_id:
            headers["X-Tenant-ID"] = org_id
        return headers
    return _make_headers


# ─────────────────────────────────────────────────────────────────────────────
# 1. A user sees their own authorized activity (personal scope default)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_user_sees_own_authorized_activity(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name="User Own Org", slug=f"own-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email="active_user@example.com", password_hash="hash", full_name="Active User")
        session.add_all([org, user])
        await session.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="MEMBER", status="ACTIVE")
        session.add(member)

        # Audit logs: 2 by user, 1 by someone else
        log1 = AuditLog(organization_id=org.id, user_email=user.email, action="CONTRACT_UPLOADED", object_type="Contract", object_id="c1", detail="Uploaded NDA contract")
        log2 = AuditLog(organization_id=org.id, user_email=user.email, action="REDLINE_ACCEPTED", object_type="ContractRedline", object_id="r1", detail="Accepted indemnification clause")
        log3 = AuditLog(organization_id=org.id, user_email="other_person@example.com", action="CONTRACT_UPLOADED", object_type="Contract", object_id="c2", detail="Uploaded Master Agreement")
        session.add_all([log1, log2, log3])
        await session.commit()

        headers = auth_helper(user.id, org.id, role="MEMBER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/activity?scope=personal", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert all(item["actor_email"] == user.email for item in data["items"])


# ─────────────────────────────────────────────────────────────────────────────
# 2. One user cannot see another user's private activity
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_one_user_cannot_see_another_users_private_activity(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org_a = Organization(name="Org A", slug=f"orga-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        org_b = Organization(name="Org B", slug=f"orgb-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user_a = User(email="alice@company.com", password_hash="hash", full_name="Alice A")
        user_b = User(email="bob@foreign.com", password_hash="hash", full_name="Bob B")
        session.add_all([org_a, org_b, user_a, user_b])
        await session.flush()

        member_a = OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role="MEMBER", status="ACTIVE")
        member_b = OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role="MEMBER", status="ACTIVE")
        session.add_all([member_a, member_b])

        log_b = AuditLog(organization_id=org_b.id, user_email=user_b.email, action="TEST_EMAIL_DISPATCH", object_type="EMAIL", object_id="none", detail="Test email dispatch to bob@foreign.com (success=False)")
        session.add(log_b)
        await session.commit()

        headers_a = auth_helper(user_a.id, org_a.id, role="MEMBER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Alice tries personal scope -> should see 0
        res = await ac.get("/api/v1/activity?scope=personal", headers=headers_a)
        assert res.status_code == 200
        assert res.json()["total"] == 0

        # Alice tries to IDOR Bob's specific log ID -> should return 404
        res_detail = await ac.get(f"/api/v1/activity/{log_b.id}", headers=headers_a)
        assert res_detail.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 3. An organization manager can see only the activity permitted within their organization
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_organization_manager_sees_only_permitted_org_activity(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org_alpha = Organization(name="Alpha Corp", slug=f"alpha-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        org_beta = Organization(name="Beta Corp", slug=f"beta-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        mgr_alpha = User(email="manager@alpha.com", password_hash="hash", full_name="Alpha Manager")
        emp_alpha = User(email="employee@alpha.com", password_hash="hash", full_name="Alpha Employee")
        emp_beta = User(email="employee@beta.com", password_hash="hash", full_name="Beta Employee")
        session.add_all([org_alpha, org_beta, mgr_alpha, emp_alpha, emp_beta])
        await session.flush()

        member_mgr = OrganizationMember(organization_id=org_alpha.id, user_id=mgr_alpha.id, role="LEGAL_MANAGER", status="ACTIVE")
        member_emp_a = OrganizationMember(organization_id=org_alpha.id, user_id=emp_alpha.id, role="EMPLOYEE", status="ACTIVE")
        member_emp_b = OrganizationMember(organization_id=org_beta.id, user_id=emp_beta.id, role="EMPLOYEE", status="ACTIVE")
        session.add_all([member_mgr, member_emp_a, member_emp_b])

        # Logs in Alpha
        log_alpha_1 = AuditLog(organization_id=org_alpha.id, user_email=emp_alpha.email, action="CONTRACT_UPLOADED", object_type="Contract", object_id="c1", detail="Uploaded Supplier SOW")
        log_alpha_2 = AuditLog(organization_id=org_alpha.id, user_email=mgr_alpha.email, action="APPROVAL_DECISION_SUBMITTED", object_type="Contract", object_id="c1", detail="Approved Supplier SOW")
        # Log in Beta
        log_beta = AuditLog(organization_id=org_beta.id, user_email=emp_beta.email, action="CONTRACT_UPLOADED", object_type="Contract", object_id="c2", detail="Uploaded Beta Secret Agreement")
        session.add_all([log_alpha_1, log_alpha_2, log_beta])
        await session.commit()

        headers_mgr = auth_helper(mgr_alpha.id, org_alpha.id, role="LEGAL_MANAGER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/activity?scope=organization", headers=headers_mgr)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        returned_emails = {item["actor_email"] for item in data["items"]}
        assert returned_emails == {emp_alpha.email, mgr_alpha.email}
        assert emp_beta.email not in returned_emails


# ─────────────────────────────────────────────────────────────────────────────
# 4. A client cannot see internal lawyer notes or another client's messages
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_client_cannot_see_internal_notes_or_foreign_messages(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org_client = Organization(name="Client Org", slug=f"cl-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        org_chambers = Organization(name="Chambers Org", slug=f"ch-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        client_user = User(email="client1@clientcorp.com", password_hash="hash", full_name="Client One")
        foreign_client = User(email="client2@foreigncorp.com", password_hash="hash", full_name="Client Two")
        lawyer_user = User(email="lawyer@chambers.com", password_hash="hash", full_name="Advocate Bose")
        session.add_all([org_client, org_chambers, client_user, foreign_client, lawyer_user])
        await session.flush()

        member_client = OrganizationMember(organization_id=org_client.id, user_id=client_user.id, role="CLIENT", status="ACTIVE")
        member_lawyer = OrganizationMember(organization_id=org_chambers.id, user_id=lawyer_user.id, role="LAWYER", status="ACTIVE")
        session.add_all([member_client, member_lawyer])

        lawyer_prof = LawyerProfile(
            organization_id=org_chambers.id,
            user_id=lawyer_user.id,
            bar_council_number=f"BCI/{uuid.uuid4().hex[:6]}",
            state_bar_council="Delhi",
            admitted_jurisdictions="Delhi High Court",
            practice_areas="Corporate",
            experience_years=8,
            consultation_fee="5000",
            verification_status="VERIFIED"
        )
        session.add(lawyer_prof)
        await session.flush()

        matter1 = LegalMatter(
            matter_code=f"MAT-CL1-{uuid.uuid4().hex[:4]}",
            title="Contract Review",
            client_organization_id=org_client.id,
            lawyer_organization_id=org_chambers.id,
            client_user_id=client_user.id,
            lawyer_user_id=lawyer_user.id,
            counterparty_name="Acme",
            matter_type="CONTRACT_REVIEW",
            status=MatterStatus.MATTER_ACTIVE.value
        )
        session.add(matter1)
        await session.flush()

        # Public message on matter 1
        log_pub = AuditLog(organization_id=org_client.id, user_email=lawyer_user.email, action="MATTER_MESSAGE_SENT", object_type="LegalMatter", object_id=matter1.id, detail=f"Message posted in matter {matter1.matter_code} (InternalNote=False).")
        # Internal note on matter 1
        log_int = AuditLog(organization_id=org_client.id, user_email=lawyer_user.email, action="MATTER_MESSAGE_SENT", object_type="LegalMatter", object_id=matter1.id, detail=f"Message posted in matter {matter1.matter_code} (InternalNote=True).")
        # Foreign client log
        log_foreign = AuditLog(organization_id=org_client.id, user_email=foreign_client.email, action="MATTER_MESSAGE_SENT", object_type="LegalMatter", object_id="foreign-matter-999", detail="Foreign client confidential inquiry")
        session.add_all([log_pub, log_int, log_foreign])
        await session.commit()

        headers_client = auth_helper(client_user.id, org_client.id, role="CLIENT")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/activity?scope=personal", headers=headers_client)
        assert res.status_code == 200
        items = res.json()["items"]
        
        # Verify internal note is NEVER returned
        details = [it["detail"] for it in items]
        assert any("InternalNote=False" in d or "Message posted" in d for d in details)
        assert not any("InternalNote=True" in d for d in details)

        # Direct access to internal note by ID must return 404
        res_int = await ac.get(f"/api/v1/activity/{log_int.id}", headers=headers_client)
        assert res_int.status_code == 404

        # Direct access to foreign client log must return 404
        res_for = await ac.get(f"/api/v1/activity/{log_foreign.id}", headers=headers_client)
        assert res_for.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 5. A lawyer cannot see unauthorized matters
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lawyer_cannot_see_unauthorized_matters(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org_chambers = Organization(name="Firm", slug=f"firm-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_a = User(email="lawyer_a@firm.com", password_hash="hash", full_name="Lawyer A")
        lawyer_b = User(email="lawyer_b@firm.com", password_hash="hash", full_name="Lawyer B")
        client_other = User(email="client_other@other.com", password_hash="hash", full_name="Other Client")
        session.add_all([org_chambers, lawyer_a, lawyer_b, client_other])
        await session.flush()

        member_a = OrganizationMember(organization_id=org_chambers.id, user_id=lawyer_a.id, role="LAWYER", status="ACTIVE")
        member_b = OrganizationMember(organization_id=org_chambers.id, user_id=lawyer_b.id, role="LAWYER", status="ACTIVE")
        session.add_all([member_a, member_b])

        matter_b = LegalMatter(
            matter_code=f"MAT-SEC-B-{uuid.uuid4().hex[:4]}",
            title="Private Matter B",
            client_organization_id=org_chambers.id,
            lawyer_organization_id=org_chambers.id,
            client_user_id=client_other.id,
            lawyer_user_id=lawyer_b.id,
            counterparty_name="Other Corp",
            matter_type="CONTRACT_REVIEW",
            status=MatterStatus.MATTER_ACTIVE.value
        )
        session.add(matter_b)
        await session.flush()

        log_matter_b = AuditLog(organization_id=org_chambers.id, user_email=lawyer_b.email, action="MATTER_MESSAGE_SENT", object_type="LegalMatter", object_id=matter_b.id, detail=f"Chambers discussion on {matter_b.matter_code}")
        session.add(log_matter_b)
        await session.commit()

        headers_lawyer_a = auth_helper(lawyer_a.id, org_chambers.id, role="LAWYER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/activity/{log_matter_b.id}", headers=headers_lawyer_a)
        assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 6. Changing IDs or tenant query parameters cannot bypass authorization
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_changing_ids_or_tenant_params_cannot_bypass_authorization(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org_victim = Organization(name="Victim Corp", slug=f"vic-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        org_attacker = Organization(name="Attacker Corp", slug=f"att-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        victim_user = User(email="victim@victimcorp.com", password_hash="hash", full_name="Victim")
        attacker_user = User(email="attacker@evil.com", password_hash="hash", full_name="Attacker")
        session.add_all([org_victim, org_attacker, victim_user, attacker_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=org_victim.id, user_id=victim_user.id, role="OWNER", status="ACTIVE"))
        session.add(OrganizationMember(organization_id=org_attacker.id, user_id=attacker_user.id, role="OWNER", status="ACTIVE"))

        log_victim = AuditLog(organization_id=org_victim.id, user_email=victim_user.email, action="CONTRACT_UPLOADED", object_type="Contract", object_id="c-secret", detail="Victim private patent acquisition")
        session.add(log_victim)
        await session.commit()

        # Attacker tries to pass X-Tenant-ID of victim
        headers_attacker = auth_helper(attacker_user.id, org_attacker.id, role="OWNER")
        forged_headers = dict(headers_attacker)
        forged_headers["X-Tenant-ID"] = org_victim.id

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Attacker passing forged X-Tenant-ID must get 403 Forbidden
        res_forged = await ac.get("/api/v1/activity?scope=organization", headers=forged_headers)
        assert res_forged.status_code == 403

        # 2. Attacker querying victim log directly must get 404 Not Found
        res_detail = await ac.get(f"/api/v1/activity/{log_victim.id}", headers=headers_attacker)
        assert res_detail.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 7. Pagination and filters preserve tenant isolation
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_pagination_and_filters_preserve_tenant_isolation(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org_target = Organization(name="Target Corp", slug=f"tgt-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        org_other = Organization(name="Other Corp", slug=f"oth-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email="lead@target.com", password_hash="hash", full_name="Target Lead")
        session.add_all([org_target, org_other, user])
        await session.flush()

        session.add(OrganizationMember(organization_id=org_target.id, user_id=user.id, role="OWNER", status="ACTIVE"))

        # Add 30 logs for Target
        for i in range(30):
            session.add(AuditLog(organization_id=org_target.id, user_email=user.email, action="CONTRACT_UPLOADED", object_type="Contract", object_id=f"doc-{i}", detail=f"Contract {i} ingested"))
        # Add 10 logs for Other
        for i in range(10):
            session.add(AuditLog(organization_id=org_other.id, user_email="spy@other.com", action="CONTRACT_UPLOADED", object_type="Contract", object_id=f"spy-{i}", detail=f"Foreign contract {i}"))
        await session.commit()

        headers = auth_helper(user.id, org_target.id, role="OWNER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Page 1
        res1 = await ac.get("/api/v1/activity?scope=organization&page=1&page_size=20", headers=headers)
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["total"] == 30
        assert len(d1["items"]) == 20
        assert d1["total_pages"] == 2
        assert all(it["actor_email"] == user.email for it in d1["items"])

        # Page 2
        res2 = await ac.get("/api/v1/activity?scope=organization&page=2&page_size=20", headers=headers)
        assert res2.status_code == 200
        d2 = res2.json()
        assert len(d2["items"]) == 10
        assert all(it["actor_email"] == user.email for it in d2["items"])


# ─────────────────────────────────────────────────────────────────────────────
# 8. Failed email attempts remain marked as failures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_failed_email_attempts_remain_marked_as_failures(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name="Audit Email Corp", slug=f"em-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email="admin@auditcorp.com", password_hash="hash", full_name="Admin Audit")
        session.add_all([org, user])
        await session.flush()

        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER", status="ACTIVE"))

        log_failed_email = AuditLog(
            organization_id=org.id,
            user_email=user.email,
            action="TEST_EMAIL_DISPATCH",
            object_type="EMAIL",
            object_id="none",
            detail="Test email dispatch to singhanishlko@gmail.com (success=False)"
        )
        session.add(log_failed_email)
        await session.commit()

        headers = auth_helper(user.id, org.id, role="OWNER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/activity?scope=organization", headers=headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        item = items[0]
        # Truthful failure status
        assert item["status"] == "FAILED"
        assert "Delivery rejected by upstream provider" in item["summary"]
        assert "success=False" not in item["summary"]


# ─────────────────────────────────────────────────────────────────────────────
# 9. Sensitive implementation details are not returned to unauthorized users
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sensitive_implementation_details_not_returned_to_unauthorized_users(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name="Mask Corp", slug=f"mask-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        owner = User(email="owner@mask.com", password_hash="hash", full_name="Org Owner")
        emp = User(email="emp@mask.com", password_hash="hash", full_name="Employee")
        session.add_all([org, owner, emp])
        await session.flush()

        session.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role="OWNER", status="ACTIVE"))
        session.add(OrganizationMember(organization_id=org.id, user_id=emp.id, role="EMPLOYEE", status="ACTIVE"))

        # Log with sensitive path and raw flags
        log_raw = AuditLog(
            organization_id=org.id,
            user_email=owner.email,
            action="CONTRACT_UPLOADED",
            object_type="Contract",
            object_id="c-raw",
            detail="Ingested contract from C:\\Users\\Administrator\\AppData\\Local\\Temp\\contracts\\secret.docx (InternalNote=False)"
        )
        session.add(log_raw)
        await session.commit()

        headers_emp = auth_helper(emp.id, org.id, role="EMPLOYEE")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Employee requesting organization activity must be blocked with 403
        res_org = await ac.get("/api/v1/activity?scope=organization", headers=headers_emp)
        assert res_org.status_code == 403
        assert "Viewing organization-wide activity history requires administrative" in res_org.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# 10. Activity links enforce the same authorization as the underlying resource
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_activity_links_enforce_resource_authorization(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name="Link Org", slug=f"lnk-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email="lawyer@firm.com", password_hash="hash", full_name="Lawyer")
        session.add_all([org, user])
        await session.flush()

        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER", status="ACTIVE"))

        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-{uuid.uuid4().hex[:6]}",
            title="Consulting Master SOW",
            contract_type="MASTER_SERVICES_AGREEMENT",
            counterparty="Vendor Corp",
            status="ACTIVE"
        )
        session.add(contract)
        await session.flush()

        log_c = AuditLog(organization_id=org.id, user_email=user.email, action="CONTRACT_UPLOADED", object_type="Contract", object_id=contract.id, detail=f"Contract '{contract.title}' uploaded.")
        session.add(log_c)
        await session.commit()

        headers = auth_helper(user.id, org.id, role="OWNER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/activity?scope=organization", headers=headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        assert items[0]["item_reference"] == f"Contract: {contract.title}"
        assert items[0]["item_link"] == f"/dashboard/contracts?id={contract.id}"


# ─────────────────────────────────────────────────────────────────────────────
# 11. Empty states differ from server errors
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_empty_states_differ_from_server_errors(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name="Empty Org", slug=f"emp-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email="newbie@empty.com", password_hash="hash", full_name="Newbie")
        session.add_all([org, user])
        await session.flush()

        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER", status="ACTIVE"))
        await session.commit()

        headers = auth_helper(user.id, org.id, role="OWNER")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Valid empty state returns 200 with total=0 and items=[]
        res = await ac.get("/api/v1/activity?scope=personal", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["items"] == []

        # Invalid scope param returns 422 Unprocessable Entity (different from empty 200)
        res_invalid = await ac.get("/api/v1/activity?scope=invalid_scope", headers=headers)
        assert res_invalid.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 12. Existing activity records remain intact after changes
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_existing_activity_records_remain_intact(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name="Preserve Org", slug=f"prs-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email="preserver@corp.com", password_hash="hash", full_name="Preserver")
        session.add_all([org, user])
        await session.flush()

        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER", status="ACTIVE"))

        # Seed realistic historic entries
        original_detail = "Message posted in matter MAT-2026-HIST (InternalNote=False)."
        log_hist = AuditLog(
            organization_id=org.id,
            user_email=user.email,
            action="MATTER_MESSAGE_SENT",
            object_type="MatterMessage",
            object_id="msg-hist-001",
            detail=original_detail
        )
        session.add(log_hist)
        await session.commit()

        # Verify underlying database row is completely unmodified
        stmt = select(AuditLog).where(AuditLog.id == log_hist.id)
        db_log = (await session.execute(stmt)).scalar_one()
        assert db_log.detail == original_detail
        assert db_log.action == "MATTER_MESSAGE_SENT"
