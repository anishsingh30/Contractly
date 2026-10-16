import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.core.security import create_access_token
from app.models.base import utc_now, generate_uuid
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.contract import Contract, ContractRedline, ContractClause, ContractRisk
from app.models.obligation import Obligation
from app.models.notification import Notification
from app.models.lawyer import (
    LawyerProfile,
    LegalMatter,
    MatterMessage,
    LawyerVerificationStatus,
    MatterStatus,
    MatterSenderType,
)
from app.services.notifications.matter_notifications import create_matter_message_notification


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
# 1. Three uploaded contracts not reduced to one because only one has obligation
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_three_uploaded_contracts_not_reduced_to_one(test_engine, auth_helper):
    """
    Proves that three uploaded contracts in an organization are preserved and
    never incorrectly reduced to one merely because only one contract has an obligation.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"org-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email=f"user-{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", full_name="Test Owner")
        session.add_all([org, user])
        await session.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER")
        session.add(member)

        # 3 Uploaded Contracts
        c1 = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-001", contract_type="Vendor Agreement", title="SaaS Vendor Agreement", counterparty="SaaS Co", value=120000, status="ACTIVE")
        c2 = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-002", contract_type="Employment Agreement", title="Employment Confidentiality Agreement", counterparty="Employee", value=0, status="ACTIVE")
        c3 = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-003", contract_type="Consulting Agreement", title="Consulting SOW", counterparty="Consultant", value=50000, status="ACTIVE")
        session.add_all([c1, c2, c3])
        await session.flush()

        # Only c3 has an obligation
        ob1 = Obligation(
            id=generate_uuid(),
            contract_id=c3.id,
            title="Deliver Milestone Report",
            description="Deliver milestone report within 30 days",
            due_date="2026-11-15",
            status="UPCOMING",
            obligor_party="Consultant",
            obligee_party="Org",
            responsible_owner="Manager"
        )
        session.add(ob1)
        await session.commit()

    headers = auth_helper(user.id, org.id, role="OWNER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Contract list MUST return all 3 contracts
        res = await client.get("/api/v1/contracts", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert len(data) == 3, f"Expected 3 contracts, got {len(data)}"
        titles = {c["title"] for c in data}
        assert "SaaS Vendor Agreement" in titles
        assert "Employment Confidentiality Agreement" in titles
        assert "Consulting SOW" in titles

        # Things to do endpoint
        res_tasks = await client.get("/api/v1/tasks/things-to-do", headers=headers)
        assert res_tasks.status_code == 200
        task_data = res_tasks.json()
        assert task_data["distinct_contracts_count"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. Badge follows documented definition: zero, one, or multiple obligations
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_badge_definition_zero_one_multiple_obligations(test_engine, auth_helper):
    """
    Proves that the Matters & Deadlines badge counts distinct contracts with
    outstanding obligations, preventing duplicate counting when multiple obligations
    belong to the same contract.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"org-{uuid.uuid4().hex[:6]}", account_type="PROFESSIONAL")
        user = User(email=f"user-{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", full_name="Advocate")
        session.add_all([org, user])
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER"))

        # Contract A: 0 obligations
        ca = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-A", contract_type="Vendor Agreement", title="Contract A (No Obligation)", counterparty="A", status="ACTIVE")
        # Contract B: 1 obligation
        cb = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-B", contract_type="Vendor Agreement", title="Contract B (One Obligation)", counterparty="B", status="ACTIVE")
        # Contract C: 3 obligations
        cc = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-C", contract_type="Vendor Agreement", title="Contract C (Multiple Obligations)", counterparty="C", status="ACTIVE")
        session.add_all([ca, cb, cc])
        await session.flush()

        ob_b1 = Obligation(id=generate_uuid(), contract_id=cb.id, title="Tax Filing", description="File statutory taxes", due_date="2026-12-01", status="UPCOMING", obligor_party="B", obligee_party="Org", responsible_owner="Tax")
        ob_c1 = Obligation(id=generate_uuid(), contract_id=cc.id, title="Payment 1", description="Process installment 1", due_date="2026-11-01", status="UPCOMING", obligor_party="C", obligee_party="Org", responsible_owner="Finance")
        ob_c2 = Obligation(id=generate_uuid(), contract_id=cc.id, title="Payment 2", description="Process installment 2", due_date="2026-12-01", status="UPCOMING", obligor_party="C", obligee_party="Org", responsible_owner="Finance")
        ob_c3 = Obligation(id=generate_uuid(), contract_id=cc.id, title="Audit Compliance", description="Perform annual audit", due_date="2026-12-15", status="UPCOMING", obligor_party="C", obligee_party="Org", responsible_owner="Audit")
        session.add_all([ob_b1, ob_c1, ob_c2, ob_c3])
        await session.commit()

    headers = auth_helper(user.id, org.id, role="OWNER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check /tasks/things-to-do
        res = await client.get("/api/v1/tasks/things-to-do", headers=headers)
        assert res.status_code == 200
        tasks = res.json()
        # Distinct contracts with obligations must be 2 (Contract B and C), not 4!
        assert tasks["distinct_contracts_count"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Accepted & Rejected amendments excluded from pending amendment count
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_accepted_rejected_amendments_excluded_from_pending(test_engine, auth_helper):
    """
    Proves that accepted and rejected amendments, playbook findings, extracted clauses,
    and contract-health warnings are excluded from the pending amendment count.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"org-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email=f"user-{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", full_name="Legal Reviewer")
        session.add_all([org, user])
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="LEGAL_REVIEWER"))

        c = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-VEND", contract_type="Vendor Agreement", title="Vendor Agreement", counterparty="Vendor", status="UNDER_REVIEW")
        session.add(c)
        await session.flush()

        # Add 4 redlines: 2 PENDING, 1 ACCEPTED, 1 REJECTED
        r1 = ContractRedline(id=generate_uuid(), contract_id=c.id, section_title="Indemnity", original_text="A", suggested_text="B", status="PENDING", author="AI")
        r2 = ContractRedline(id=generate_uuid(), contract_id=c.id, section_title="Liability", original_text="C", suggested_text="D", status="PENDING", author="AI")
        r3 = ContractRedline(id=generate_uuid(), contract_id=c.id, section_title="Governing Law", original_text="E", suggested_text="F", status="ACCEPTED", author="AI")
        r4 = ContractRedline(id=generate_uuid(), contract_id=c.id, section_title="Term", original_text="G", suggested_text="H", status="REJECTED", author="AI")
        
        # Add clause and risk (must NOT be counted as amendments)
        clause = ContractClause(
            id=generate_uuid(),
            contract_id=c.id,
            section_number="1.1",
            clause_title="Definitions",
            original_text="Definitions text",
            plain_language="Plain text definitions",
            why_it_matters="Defines contract terms"
        )
        risk = ContractRisk(id=generate_uuid(), contract_id=c.id, risk_title="Uncapped liability", potential_impact="High", remedy_recommendation="Cap it", severity="HIGH")

        session.add_all([r1, r2, r3, r4, clause, risk])
        await session.commit()

    headers = auth_helper(user.id, org.id, role="LEGAL_REVIEWER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/contracts/{c.id}/redlines", headers=headers)
        assert res.status_code == 200
        all_redlines = res.json()
        assert len(all_redlines) == 4

        pending_redlines = [r for r in all_redlines if r["status"] == "PENDING"]
        assert len(pending_redlines) == 2, f"Expected 2 pending redlines, got {len(pending_redlines)}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Pending amendments update badge after generation and accept/reject
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_pending_amendments_update_badge_lifecycle(test_engine, auth_helper):
    """
    Proves that pending amendments update status cleanly on accept and reject endpoints.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"org-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email=f"user-{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", full_name="Reviewer")
        session.add_all([org, user])
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER"))

        c = Contract(id=generate_uuid(), organization_id=org.id, contract_id="CTR-SOW", contract_type="Vendor Agreement", title="Test SOW", counterparty="Vendor", status="UNDER_REVIEW")
        session.add(c)
        await session.flush()

        r1 = ContractRedline(id=generate_uuid(), contract_id=c.id, section_title="Clause 1", original_text="Old 1", suggested_text="New 1", status="PENDING", author="Counsel")
        r2 = ContractRedline(id=generate_uuid(), contract_id=c.id, section_title="Clause 2", original_text="Old 2", suggested_text="New 2", status="PENDING", author="Counsel")
        session.add_all([r1, r2])
        await session.commit()

    headers = auth_helper(user.id, org.id, role="OWNER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initially 2 pending
        res = await client.get(f"/api/v1/contracts/{c.id}/redlines", headers=headers)
        assert res.status_code == 200
        assert sum(1 for r in res.json() if r["status"] == "PENDING") == 2

        # Accept r1
        patch_res1 = await client.patch(
            f"/api/v1/contracts/{c.id}/redlines/{r1.id}/status",
            json={"status": "ACCEPTED"},
            headers=headers
        )
        assert patch_res1.status_code == 200
        assert patch_res1.json()["status"] == "ACCEPTED"

        # Check pending count drops to 1
        res2 = await client.get(f"/api/v1/contracts/{c.id}/redlines", headers=headers)
        assert sum(1 for r in res2.json() if r["status"] == "PENDING") == 1

        # Reject r2
        patch_res2 = await client.patch(
            f"/api/v1/contracts/{c.id}/redlines/{r2.id}/status",
            json={"status": "REJECTED"},
            headers=headers
        )
        assert patch_res2.status_code == 200
        assert patch_res2.json()["status"] == "REJECTED"

        # Check pending count drops to 0
        res3 = await client.get(f"/api/v1/contracts/{c.id}/redlines", headers=headers)
        assert sum(1 for r in res3.json() if r["status"] == "PENDING") == 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. New client message creates correct recipient lawyer notification
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_client_message_creates_lawyer_notification(test_engine, auth_helper):
    """
    Proves that when a client posts a message in an active matter:
    - A persisted notification is created for the assigned lawyer in the lawyer's organization.
    - The client is NOT notified of their own message.
    - The unread count for the lawyer increases by 1.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        client_org = Organization(name=f"ClientOrg-{uuid.uuid4().hex[:6]}", slug=f"cl-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"client-{uuid.uuid4().hex[:6]}@client.com", password_hash="hash", full_name="Client Alice")
        lawyer_org = Organization(name=f"LawyerChambers-{uuid.uuid4().hex[:6]}", slug=f"law-{uuid.uuid4().hex[:6]}", account_type="PROFESSIONAL")
        lawyer_user = User(email=f"lawyer-{uuid.uuid4().hex[:6]}@lawyer.com", password_hash="hash", full_name="Advocate Bob")
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER"))
        session.add(OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="LAWYER"))

        lawyer_prof = LawyerProfile(
            organization_id=lawyer_org.id,
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

        matter = LegalMatter(
            matter_code=f"MAT-2026-{uuid.uuid4().hex[:6].upper()}",
            title="Commercial Review",
            matter_type="CONTRACT_REVIEW",
            counterparty_name="Acme Legal",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=lawyer_org.id,
            lawyer_user_id=lawyer_user.id,
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True
        )
        session.add(matter)
        await session.commit()

    client_headers = auth_helper(client_user.id, client_org.id, role="OWNER")
    lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id, role="LAWYER")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check initial unread counts
        l_unread_initial = await client.get("/api/v1/notifications/unread-count", headers=lawyer_headers)
        assert l_unread_initial.status_code == 200
        initial_count = l_unread_initial.json()["unread_count"]

        # Client posts message
        msg_res = await client.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Hello counsel, please check clause 5."},
            headers=client_headers
        )
        assert msg_res.status_code == 201, msg_res.text

        # Lawyer unread count must increment
        l_unread_after = await client.get("/api/v1/notifications/unread-count", headers=lawyer_headers)
        assert l_unread_after.status_code == 200
        assert l_unread_after.json()["unread_count"] == initial_count + 1

        # Lawyer notifications list must have the message notification
        l_notifs = await client.get("/api/v1/notifications", headers=lawyer_headers)
        assert l_notifs.status_code == 200
        items = l_notifs.json()["items"]
        assert len(items) >= 1
        msg_notif = next((n for n in items if n["event_type"] == "MATTER_MESSAGE_RECEIVED"), None)
        assert msg_notif is not None
        assert matter.matter_code in msg_notif["title"]
        assert "Client Alice" in msg_notif["message"]

        # Client must NOT receive notification for their own message
        c_notifs = await client.get("/api/v1/notifications", headers=client_headers)
        assert c_notifs.status_code == 200
        c_items = c_notifs.json()["items"]
        assert not any(n["event_type"] == "MATTER_MESSAGE_RECEIVED" for n in c_items)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Lawyer reply creates correct recipient client notification
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lawyer_reply_creates_client_notification(test_engine, auth_helper):
    """
    Proves that when a lawyer replies to an active matter:
    - Client receives an in-app notification.
    - Internal chambers note (is_internal_note=True) does NOT notify the client.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        client_org = Organization(name=f"ClientOrg-{uuid.uuid4().hex[:6]}", slug=f"cl-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"client-{uuid.uuid4().hex[:6]}@client.com", password_hash="hash", full_name="Client Clara")
        lawyer_org = Organization(name=f"LawyerChambers-{uuid.uuid4().hex[:6]}", slug=f"law-{uuid.uuid4().hex[:6]}", account_type="PROFESSIONAL")
        lawyer_user = User(email=f"lawyer-{uuid.uuid4().hex[:6]}@lawyer.com", password_hash="hash", full_name="Advocate Dave")
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER"))
        session.add(OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="LAWYER"))

        lawyer_prof = LawyerProfile(
            organization_id=lawyer_org.id,
            user_id=lawyer_user.id,
            bar_council_number=f"BCI/{uuid.uuid4().hex[:6]}",
            state_bar_council="Maharashtra",
            admitted_jurisdictions="Bombay High Court",
            practice_areas="Litigation",
            experience_years=10,
            consultation_fee="8000",
            verification_status="VERIFIED"
        )
        session.add(lawyer_prof)
        await session.flush()

        matter = LegalMatter(
            matter_code=f"MAT-2026-{uuid.uuid4().hex[:6].upper()}",
            title="NDAs Negotiation",
            matter_type="CONTRACT_REVIEW",
            counterparty_name="Acme Legal",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=lawyer_org.id,
            lawyer_user_id=lawyer_user.id,
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True
        )
        session.add(matter)
        await session.commit()

    client_headers = auth_helper(client_user.id, client_org.id, role="OWNER")
    lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id, role="LAWYER")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Lawyer sends internal chambers note (must NOT notify client)
        internal_res = await client.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Confidential research note for junior advocate.", "is_internal_note": True},
            headers=lawyer_headers
        )
        assert internal_res.status_code == 201

        # Client must NOT have any notifications
        c_unread_1 = await client.get("/api/v1/notifications/unread-count", headers=client_headers)
        assert c_unread_1.json()["unread_count"] == 0

        # 2. Lawyer sends client-visible reply
        reply_res = await client.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "I have reviewed clause 5 and suggest modifying the indemnification cap.", "is_internal_note": False},
            headers=lawyer_headers
        )
        assert reply_res.status_code == 201

        # Client unread count must now be 1
        c_unread_2 = await client.get("/api/v1/notifications/unread-count", headers=client_headers)
        assert c_unread_2.json()["unread_count"] == 1

        c_notifs = await client.get("/api/v1/notifications", headers=client_headers)
        items = c_notifs.json()["items"]
        assert len(items) == 1
        assert "Advocate Dave" in items[0]["message"]


# ─────────────────────────────────────────────────────────────────────────────
# 7. Unread counts update when notifications are read
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_unread_counts_update_on_read(test_engine, auth_helper):
    """
    Proves that marking a notification as read immediately decrements unread_count.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"org-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email=f"user-{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", full_name="User")
        session.add_all([org, user])
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER"))

        n = Notification(
            id=generate_uuid(),
            organization_id=org.id,
            user_id=user.id,
            event_type="MATTER_MESSAGE_RECEIVED",
            title="Message Title",
            message="Message Body",
            is_read=False
        )
        session.add(n)
        await session.commit()

    headers = auth_helper(user.id, org.id, role="OWNER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check unread count is 1
        c1 = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert c1.json()["unread_count"] == 1

        # Mark as read using PATCH
        patch_res = await client.patch(f"/api/v1/notifications/{n.id}/read", headers=headers)
        assert patch_res.status_code == 200
        assert patch_res.json()["is_read"] is True

        # Check unread count drops to 0
        c2 = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert c2.json()["unread_count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 8. Duplicate requests do not create duplicate messages or notifications
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_duplicate_requests_prevented_by_deduplication(test_engine):
    """
    Proves that inserting duplicate notifications for the same message is prevented
    by the unique deduplication_key.
    """
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"org-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        sender = User(email=f"sender-{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", full_name="Sender")
        recipient = User(email=f"recipient-{uuid.uuid4().hex[:6]}@example.com", password_hash="hash", full_name="Recipient")
        session.add_all([org, sender, recipient])
        await session.flush()

        matter = LegalMatter(
            matter_code="MAT-DEDUP-001",
            title="Dedup Test",
            matter_type="CONTRACT_REVIEW",
            counterparty_name="Counterparty Corp",
            client_organization_id=org.id,
            client_user_id=sender.id,
            lawyer_organization_id=org.id,
            lawyer_user_id=recipient.id,
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True
        )
        session.add(matter)
        await session.flush()

        msg = MatterMessage(
            id=generate_uuid(),
            matter_id=matter.id,
            sender_user_id=sender.id,
            sender_type="CLIENT",
            message_text="First transmission",
            is_internal_note=False
        )
        session.add(msg)
        await session.flush()

        # First notification creation succeeds
        n1 = await create_matter_message_notification(session, matter, msg, sender)
        assert n1 is not None
        await session.commit()

        # Second notification creation for the exact same message should be safely handled
        n2 = await create_matter_message_notification(session, matter, msg, sender)
        # Because deduplication_key is unique, attempting duplicate returns None or handles safely
        stmt = select(Notification).where(Notification.deduplication_key == f"matter_msg_{msg.id}")
        res = await session.execute(stmt)
        all_notifs = res.scalars().all()
        assert len(all_notifs) == 1, "Duplicate notification was erroneously inserted"


# ─────────────────────────────────────────────────────────────────────────────
# 9. Tenant isolation and authorization boundaries
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_tenant_isolation_and_authorization(test_engine, auth_helper):
    """
    Proves that a user from Tenant B cannot access or mark read Tenant A's notifications.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org_a = Organization(name=f"OrgA-{uuid.uuid4().hex[:6]}", slug=f"orga-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user_a = User(email=f"usera-{uuid.uuid4().hex[:6]}@a.com", password_hash="hash", full_name="User A")
        org_b = Organization(name=f"OrgB-{uuid.uuid4().hex[:6]}", slug=f"orgb-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user_b = User(email=f"userb-{uuid.uuid4().hex[:6]}@b.com", password_hash="hash", full_name="User B")
        session.add_all([org_a, user_a, org_b, user_b])
        await session.flush()

        session.add(OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role="OWNER"))
        session.add(OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role="OWNER"))

        notif_a = Notification(
            id=generate_uuid(),
            organization_id=org_a.id,
            user_id=user_a.id,
            event_type="MATTER_MESSAGE_RECEIVED",
            title="Tenant A Private Alert",
            message="Confidential terms",
            is_read=False
        )
        session.add(notif_a)
        await session.commit()

    headers_b = auth_helper(user_b.id, org_b.id, role="OWNER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User B listing notifications must see 0 items
        res = await client.get("/api/v1/notifications", headers=headers_b)
        assert res.status_code == 200
        assert len(res.json()["items"]) == 0

        # User B attempting to mark User A's notification as read must get 404
        patch_res = await client.patch(f"/api/v1/notifications/{notif_a.id}/read", headers=headers_b)
        assert patch_res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 10. Empty states, API failures, and refresh behavior
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_empty_states_and_api_failure_handling(test_engine, auth_helper):
    """
    Proves that empty states and invalid IDs return appropriate HTTP status codes,
    never crashing the server with unhandled 500 exceptions.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"EmptyOrg-{uuid.uuid4().hex[:6]}", slug=f"empty-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email=f"emptyuser-{uuid.uuid4().hex[:6]}@test.com", password_hash="hash", full_name="Empty User")
        session.add_all([org, user])
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER"))
        await session.commit()

    headers = auth_helper(user.id, org.id, role="OWNER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Clean empty notifications
        notif_res = await client.get("/api/v1/notifications", headers=headers)
        assert notif_res.status_code == 200
        data = notif_res.json()
        assert data["items"] == []
        assert data["unread_count"] == 0
        assert data["total_count"] == 0

        # Non-existent notification returns 404
        fake_id = generate_uuid()
        read_res = await client.patch(f"/api/v1/notifications/{fake_id}/read", headers=headers)
        assert read_res.status_code == 404

        # Non-existent matter messages return 404
        fake_matter_id = generate_uuid()
        msg_res = await client.get(f"/api/v1/matters/{fake_matter_id}/messages", headers=headers)
        assert msg_res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 11. Matter conversation read clears only relevant matter notifications
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_matter_read_clears_only_relevant_matter_notifications(test_engine, auth_helper):
    """
    Proves that opening a matter conversation and calling PATCH /matters/{id}/read
    clears ONLY message notifications for that specific matter, leaving notifications
    for other matters and non-message alerts unread and intact.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Chambers-{uuid.uuid4().hex[:6]}", slug=f"ch-{uuid.uuid4().hex[:6]}", account_type="PROFESSIONAL")
        client_org = Organization(name=f"ClientOrg-{uuid.uuid4().hex[:6]}", slug=f"co-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        lawyer_user = User(email=f"lawyer-{uuid.uuid4().hex[:6]}@law.com", password_hash="hash", full_name="Counsel Lee")
        client_user = User(email=f"client-{uuid.uuid4().hex[:6]}@co.com", password_hash="hash", full_name="Client Pat")
        session.add_all([org, client_org, lawyer_user, client_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=org.id, user_id=lawyer_user.id, role="LAWYER"))
        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER"))

        lawyer_prof = LawyerProfile(
            organization_id=org.id,
            user_id=lawyer_user.id,
            bar_council_number=f"BCI/{uuid.uuid4().hex[:6]}",
            state_bar_council="Delhi",
            admitted_jurisdictions="Delhi High Court",
            practice_areas="Corporate",
            experience_years=7,
            consultation_fee="6000",
            verification_status="VERIFIED"
        )
        session.add(lawyer_prof)

        # Matter 1
        m1 = LegalMatter(
            matter_code=f"MAT-2026-M1-{uuid.uuid4().hex[:4].upper()}",
            title="Matter One",
            matter_type="CONTRACT_REVIEW",
            counterparty_name="Party A",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=org.id,
            lawyer_user_id=lawyer_user.id,
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True
        )
        # Matter 2
        m2 = LegalMatter(
            matter_code=f"MAT-2026-M2-{uuid.uuid4().hex[:4].upper()}",
            title="Matter Two",
            matter_type="CONTRACT_REVIEW",
            counterparty_name="Party B",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=org.id,
            lawyer_user_id=lawyer_user.id,
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True
        )
        session.add_all([m1, m2])
        await session.flush()

        # Notification for Matter 1
        notif_m1 = Notification(
            id=generate_uuid(),
            organization_id=org.id,
            user_id=lawyer_user.id,
            event_type="MATTER_MESSAGE_RECEIVED",
            title=f"New Message: {m1.matter_code}",
            message="Client sent message on Matter 1",
            is_read=False
        )
        # Notification for Matter 2
        notif_m2 = Notification(
            id=generate_uuid(),
            organization_id=org.id,
            user_id=lawyer_user.id,
            event_type="MATTER_MESSAGE_RECEIVED",
            title=f"New Message: {m2.matter_code}",
            message="Client sent message on Matter 2",
            is_read=False
        )
        # General non-message notification (e.g. deadline or risk)
        notif_deadline = Notification(
            id=generate_uuid(),
            organization_id=org.id,
            user_id=lawyer_user.id,
            event_type="OBLIGATION_DEADLINE_APPROACHING",
            title="Deadline Approaching",
            message="Vendor agreement deadline in 3 days",
            is_read=False
        )
        session.add_all([notif_m1, notif_m2, notif_deadline])
        await session.commit()

    lawyer_headers = auth_helper(lawyer_user.id, org.id, role="LAWYER")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check initial counts: total unread = 3, unread messages = 2
        c_init = await client.get("/api/v1/notifications/unread-count", headers=lawyer_headers)
        assert c_init.status_code == 200
        data_init = c_init.json()
        assert data_init["unread_count"] == 3
        assert data_init["unread_messages_count"] == 2

        # Lawyer opens conversation for Matter 1 -> marks Matter 1 notifications read
        read_res = await client.patch(f"/api/v1/matters/{m1.id}/read", headers=lawyer_headers)
        assert read_res.status_code == 200
        read_data = read_res.json()
        assert read_data["status"] == "success"
        assert read_data["marked_read"] == 1

        # Check counts after reading Matter 1: total unread = 2, unread messages = 1
        c_after = await client.get("/api/v1/notifications/unread-count", headers=lawyer_headers)
        assert c_after.status_code == 200
        data_after = c_after.json()
        assert data_after["unread_count"] == 2
        assert data_after["unread_messages_count"] == 1

        # Verify in notification list: Matter 1 is read, Matter 2 and deadline remain unread
        notifs_res = await client.get("/api/v1/notifications", headers=lawyer_headers)
        assert notifs_res.status_code == 200
        items = {n["id"]: n for n in notifs_res.json()["items"]}
        assert items[notif_m1.id]["is_read"] is True
        assert items[notif_m2.id]["is_read"] is False
        assert items[notif_deadline.id]["is_read"] is False

        # Repeating read call is idempotent (marked_read = 0, counts unaffected)
        read_res_2 = await client.patch(f"/api/v1/matters/{m1.id}/read", headers=lawyer_headers)
        assert read_res_2.status_code == 200
        assert read_res_2.json()["marked_read"] == 0

        c_after_repeat = await client.get("/api/v1/notifications/unread-count", headers=lawyer_headers)
        assert c_after_repeat.json()["unread_count"] == 2
        assert c_after_repeat.json()["unread_messages_count"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 12. Unread counts endpoint and notifications list schema verification
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_unread_counts_endpoint_includes_unread_messages_count(test_engine, auth_helper):
    """
    Proves that both /notifications/unread-count and /notifications endpoints accurately
    return unread_messages_count scoped to the authenticated user and organization.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        org = Organization(name=f"Corp-{uuid.uuid4().hex[:6]}", slug=f"corp-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user = User(email=f"corpuser-{uuid.uuid4().hex[:6]}@corp.com", password_hash="hash", full_name="Corp Lead")
        session.add_all([org, user])
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER"))

        # 2 message notifications (1 read, 1 unread)
        # 1 non-message notification (unread)
        n_msg_unread = Notification(
            id=generate_uuid(),
            organization_id=org.id,
            user_id=user.id,
            event_type="MATTER_MESSAGE_RECEIVED",
            title="Unread Msg",
            message="Content",
            is_read=False
        )
        n_msg_read = Notification(
            id=generate_uuid(),
            organization_id=org.id,
            user_id=user.id,
            event_type="MATTER_MESSAGE_RECEIVED",
            title="Read Msg",
            message="Content",
            is_read=True
        )
        n_alert_unread = Notification(
            id=generate_uuid(),
            organization_id=org.id,
            user_id=user.id,
            event_type="CONTRACT_HIGH_RISK_DETECTED",
            title="Risk Alert",
            message="Risk description",
            is_read=False
        )
        session.add_all([n_msg_unread, n_msg_read, n_alert_unread])
        await session.commit()

    headers = auth_helper(user.id, org.id, role="OWNER")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check /notifications/unread-count
        res_count = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert res_count.status_code == 200
        count_json = res_count.json()
        assert count_json["unread_count"] == 2
        assert count_json["unread_messages_count"] == 1

        # Check /notifications list response
        res_list = await client.get("/api/v1/notifications", headers=headers)
        assert res_list.status_code == 200
        list_json = res_list.json()
        assert list_json["unread_count"] == 2
        assert list_json["unread_messages_count"] == 1
        assert len(list_json["items"]) == 3


# ─────────────────────────────────────────────────────────────────────────────
# 13. My Contracts & Contract Health badge counts definition & deduplication
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_contract_health_and_my_contracts_badge_definitions(test_engine, auth_helper):
    """
    Proves that:
    1. 'My Contracts' represents the number of distinct contracts accessible in the active workspace.
    2. 'Contract Health' represents the number of distinct accessible contracts with available health information
       (registered obligations or identified clause risks).
    3. Contracts without obligations and without risks are excluded from the Contract Health count.
    4. Contracts with multiple obligations (e.g. 5) and multiple risks (e.g. 2) are counted ONCE, never duplicated.
    5. Tenant isolation is strictly enforced; contracts from another organization are never combined.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Organization A
        org_a = Organization(name=f"OrgA-{uuid.uuid4().hex[:6]}", slug=f"orga-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user_a = User(email=f"usera-{uuid.uuid4().hex[:6]}@orga.com", password_hash="hash", full_name="User OrgA")
        # Organization B
        org_b = Organization(name=f"OrgB-{uuid.uuid4().hex[:6]}", slug=f"orgb-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        user_b = User(email=f"userb-{uuid.uuid4().hex[:6]}@orgb.com", password_hash="hash", full_name="User OrgB")

        session.add_all([org_a, user_a, org_b, user_b])
        await session.flush()

        session.add(OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role="OWNER"))
        session.add(OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role="OWNER"))

        # In Org A:
        # Contract 1: No obligations, no risks (e.g. freshly uploaded draft)
        c1 = Contract(id=generate_uuid(), organization_id=org_a.id, contract_id="CTR-A1", contract_type="Vendor Agreement", title="Draft SaaS Agreement", counterparty="SaaS Corp", status="UNDER_REVIEW", risk_level="LOW")
        # Contract 2: 5 obligations, 2 risks (complex contract)
        c2 = Contract(id=generate_uuid(), organization_id=org_a.id, contract_id="CTR-A2", contract_type="MSA", title="Master Cloud Agreement", counterparty="Cloud Co", status="UNDER_REVIEW", risk_level="CRITICAL")
        # Contract 3: 2 obligations, 0 risks
        c3 = Contract(id=generate_uuid(), organization_id=org_a.id, contract_id="CTR-A3", contract_type="Employment", title="Executive Employment", counterparty="Exec", status="ACTIVE", risk_level="LOW")
        # Contract 4: 0 obligations, 1 risk
        c4 = Contract(id=generate_uuid(), organization_id=org_a.id, contract_id="CTR-A4", contract_type="NDA", title="Mutual NDA", counterparty="Partner", status="UNDER_REVIEW", risk_level="HIGH")

        # In Org B:
        # Contract B1: 3 obligations
        cb1 = Contract(id=generate_uuid(), organization_id=org_b.id, contract_id="CTR-B1", contract_type="SOW", title="Isolated SOW", counterparty="Vendor B", status="ACTIVE", risk_level="LOW")

        session.add_all([c1, c2, c3, c4, cb1])
        await session.flush()

        # Add 5 obligations to c2
        for i in range(5):
            session.add(Obligation(
                id=generate_uuid(),
                contract_id=c2.id,
                title=f"Obligation {i+1} for C2",
                description="Delivery and compliance check",
                due_date=f"2026-11-0{i+1}",
                status="UPCOMING",
                obligor_party="Cloud Co",
                obligee_party="OrgA",
                responsible_owner="Compliance Lead"
            ))

        # Add 2 risks to c2
        session.add(ContractRisk(id=generate_uuid(), contract_id=c2.id, risk_title="Uncapped Liability", potential_impact="High exposure", remedy_recommendation="Cap at 1x annual fees", severity="CRITICAL", status="OPEN"))
        session.add(ContractRisk(id=generate_uuid(), contract_id=c2.id, risk_title="Unilateral Indemnity", potential_impact="Indemnity without reciprocal defense", remedy_recommendation="Make mutual", severity="HIGH", status="OPEN"))

        # Add 2 obligations to c3
        session.add(Obligation(id=generate_uuid(), contract_id=c3.id, title="Equity Vesting Milestone", description="1-year cliff", due_date="2027-01-01", status="UPCOMING", obligor_party="OrgA", obligee_party="Exec", responsible_owner="HR"))
        session.add(Obligation(id=generate_uuid(), contract_id=c3.id, title="Annual Performance Review", description="Annual review", due_date="2026-12-15", status="UPCOMING", obligor_party="OrgA", obligee_party="Exec", responsible_owner="HR"))

        # Add 1 risk to c4
        session.add(ContractRisk(id=generate_uuid(), contract_id=c4.id, risk_title="Indefinite Confidentiality Term", potential_impact="Perpetual non-disclosure", remedy_recommendation="Limit to 3 years", severity="HIGH", status="OPEN"))

        # Add 3 obligations to cb1 in Org B
        for j in range(3):
            session.add(Obligation(
                id=generate_uuid(),
                contract_id=cb1.id,
                title=f"Org B Obligation {j+1}",
                description="Org B requirement",
                due_date="2026-12-01",
                status="UPCOMING",
                obligor_party="Vendor B",
                obligee_party="OrgB",
                responsible_owner="Manager B"
            ))

        await session.commit()

    headers_a = auth_helper(user_a.id, org_a.id, role="OWNER")
    headers_b = auth_helper(user_b.id, org_b.id, role="OWNER")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch contracts for Org A
        res_contracts_a = await client.get("/api/v1/contracts", headers=headers_a)
        assert res_contracts_a.status_code == 200
        contracts_a = res_contracts_a.json()

        # My Contracts badge: distinct contracts in active workspace = 4
        assert len(contracts_a) == 4
        contract_ids_a = {c["id"] for c in contracts_a}
        assert contract_ids_a == {c1.id, c2.id, c3.id, c4.id}

        # Fetch obligations for Org A
        res_ob_a = await client.get("/api/v1/obligations", headers=headers_a)
        assert res_ob_a.status_code == 200
        obligations_a = res_ob_a.json()
        assert len(obligations_a) == 7  # 5 from c2 + 2 from c3

        # Map obligations to contracts (as contractly-context does)
        ob_by_contract = {}
        for o in obligations_a:
            ob_by_contract.setdefault(o["contract_id"], []).append(o)

        # Evaluate Contract Health badge formula:
        # Distinct accessible contracts with available health info (registered obligations or clause risks)
        health_contracts_a = [
            c for c in contracts_a
            if len(ob_by_contract.get(c["id"], [])) > 0 or len(c.get("risks", [])) > 0
        ]

        # Must equal 3 (c2, c3, c4). c1 has 0 obligations and 0 risks so it has NO health info!
        assert len(health_contracts_a) == 3
        health_ids_a = {c["id"] for c in health_contracts_a}
        assert c1.id not in health_ids_a, "Contract 1 without obligations or risks must not be counted in Contract Health"
        assert c2.id in health_ids_a
        assert c3.id in health_ids_a
        assert c4.id in health_ids_a

        # Verify c2 is counted ONCE despite having 5 obligations and 2 risks
        c2_count = sum(1 for c in health_contracts_a if c["id"] == c2.id)
        assert c2_count == 1, f"Contract 2 must be counted exactly once, got {c2_count}"

        # 2. Verify Tenant Isolation: Org B must see only its own 1 contract
        res_contracts_b = await client.get("/api/v1/contracts", headers=headers_b)
        assert res_contracts_b.status_code == 200
        contracts_b = res_contracts_b.json()
        assert len(contracts_b) == 1
        assert contracts_b[0]["id"] == cb1.id

        res_ob_b = await client.get("/api/v1/obligations", headers=headers_b)
        assert res_ob_b.status_code == 200
        obligations_b = res_ob_b.json()
        assert len(obligations_b) == 3
        assert all(o["contract_id"] == cb1.id for o in obligations_b)


# ─────────────────────────────────────────────────────────────────────────────
# 14. Five obligations on 1 contract produce task count 5 and health count 1;
#     and unassigned lawyer consultation inquiry delivers notification and clears
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_five_obligations_and_unassigned_lawyer_consultation(test_engine, auth_helper):
    """
    Proves:
    1. A contract with 5 obligations displays 5 task items in Things You Need to Do,
       while distinct contracts in Contract Health remains 1.
    2. When a consultation has lawyer_user_id=None initially, recipient resolution
       resolves the verified lawyer in the target organization, delivers the notification,
       and allows the lawyer to open the matter and clear notifications without a 404.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        client_org = Organization(name=f"ClientCorp-{uuid.uuid4().hex[:6]}", slug=f"cc-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"client-{uuid.uuid4().hex[:6]}@clientcorp.com", password_hash="hash", full_name="Client Rachel")
        lawyer_org = Organization(name=f"Chambers-{uuid.uuid4().hex[:6]}", slug=f"ch-{uuid.uuid4().hex[:6]}", account_type="PROFESSIONAL")
        lawyer_user = User(email=f"advocate-{uuid.uuid4().hex[:6]}@chambers.com", password_hash="hash", full_name="Advocate Vikram")

        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER"))
        session.add(OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="LAWYER"))

        lawyer_prof = LawyerProfile(
            organization_id=lawyer_org.id,
            user_id=lawyer_user.id,
            bar_council_number=f"BCI/{uuid.uuid4().hex[:6]}",
            state_bar_council="Delhi",
            admitted_jurisdictions="Delhi High Court",
            practice_areas="Corporate",
            experience_years=9,
            consultation_fee="7500",
            verification_status="VERIFIED"
        )
        session.add(lawyer_prof)

        # Single contract with 5 obligations
        c = Contract(
            id=generate_uuid(),
            organization_id=client_org.id,
            contract_id="CTR-FIVE-001",
            contract_type="Master Services Agreement",
            title="Enterprise Cloud Agreement",
            counterparty="BigCloud Inc",
            status="ACTIVE"
        )
        session.add(c)
        await session.flush()

        for i in range(5):
            session.add(Obligation(
                id=generate_uuid(),
                contract_id=c.id,
                title=f"Cloud SLA Milestone {i+1}",
                description=f"Quarterly review requirement {i+1}",
                due_date=f"2026-11-1{i}",
                status="UPCOMING",
                obligor_party="BigCloud Inc",
                obligee_party="ClientCorp",
                responsible_owner="VP Engineering"
            ))

        # Matter with unassigned lawyer (lawyer_user_id is None)
        matter = LegalMatter(
            matter_code=f"MAT-UNASSIGNED-{uuid.uuid4().hex[:4].upper()}",
            title="Inquiry on Cloud Terms",
            matter_type="CONTRACT_REVIEW",
            counterparty_name="BigCloud Inc",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=lawyer_org.id,
            lawyer_user_id=None,  # initially unassigned
            status=MatterStatus.ACCEPTED.value,
            conflict_cleared=False,
            client_consent_given=True
        )
        session.add(matter)
        await session.commit()

    client_headers = auth_helper(client_user.id, client_org.id, role="OWNER")
    lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id, role="LAWYER")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Verify Things You Need to Do displays 5 obligation tasks
        res_tasks = await client.get("/api/v1/tasks/things-to-do", headers=client_headers)
        assert res_tasks.status_code == 200
        tasks_data = res_tasks.json()
        assert len(tasks_data["items"]) == 5, f"Expected 5 task items, got {len(tasks_data['items'])}"
        assert tasks_data["distinct_contracts_count"] == 1, "Expected distinct_contracts_count to be 1"

        # 2. Client sends a message in the unassigned inquiry matter
        msg_res = await client.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Hello, we need urgent review of the indemnification terms."},
            headers=client_headers
        )
        assert msg_res.status_code == 201, msg_res.text

        # 3. Check lawyer unread counts: recipient resolution must route to Advocate Vikram
        l_counts = await client.get("/api/v1/notifications/unread-count", headers=lawyer_headers)
        assert l_counts.status_code == 200
        assert l_counts.json()["unread_count"] == 1
        assert l_counts.json()["unread_messages_count"] == 1

        # 4. Lawyer can access matter without 404
        m_get = await client.get(f"/api/v1/matters/{matter.id}", headers=lawyer_headers)
        assert m_get.status_code == 200, f"Lawyer access failed: {m_get.text}"
        assert m_get.json()["id"] == matter.id

        # 5. Lawyer opens matter and marks read
        read_res = await client.patch(f"/api/v1/matters/{matter.id}/read", headers=lawyer_headers)
        assert read_res.status_code == 200
        assert read_res.json()["marked_read"] == 1

        # 6. Verify lawyer unread counts drop to 0
        l_counts_cleared = await client.get("/api/v1/notifications/unread-count", headers=lawyer_headers)
        assert l_counts_cleared.json()["unread_count"] == 0
        assert l_counts_cleared.json()["unread_messages_count"] == 0


@pytest.mark.asyncio
async def test_lawyer_receives_matter_notifications_across_member_workspaces(test_engine, auth_helper):
    """
    Verifies that an advocate who is a member of multiple organizations (e.g. Acme corporate
    and Swaminathan Law Firm) receives matter message notifications in their dashboard regardless
    of which workspace is currently active.
    """
    from app.models.organization import Organization
    from app.models.user import User, OrganizationMember
    from app.models.lawyer import LegalMatter, LawyerProfile, LawyerVerificationStatus
    from app.core.security import get_password_hash
    from app.main import app

    SessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        # Create lawyer user
        advocate = User(
            id=generate_uuid(),
            email=f"advocate.{uuid.uuid4().hex[:6]}@chambers.internal",
            password_hash=get_password_hash("Password123!"),
            full_name="Advocate Anish",
            is_active=True
        )
        session.add(advocate)

        # Create two orgs for lawyer: Org A (Firm) and Org B (Client/Corporate)
        firm_org = Organization(
            id=generate_uuid(),
            name="Apex Legal Chambers",
            slug=f"apex-chambers-{uuid.uuid4().hex[:6]}",
            account_type="LEGAL_PROFESSIONAL"
        )
        corp_org = Organization(
            id=generate_uuid(),
            name="Acne Corp",
            slug=f"acne-corp-{uuid.uuid4().hex[:6]}",
            account_type="BUSINESS"
        )
        client_org = Organization(
            id=generate_uuid(),
            name="Client Personal Workspace",
            slug=f"client-ws-{uuid.uuid4().hex[:6]}",
            account_type="INDIVIDUAL"
        )
        session.add_all([firm_org, corp_org, client_org])
        await session.flush()

        # Add lawyer to both firm_org and corp_org
        session.add_all([
            OrganizationMember(id=generate_uuid(), user_id=advocate.id, organization_id=firm_org.id, role="LEGAL_MANAGER", status="ACTIVE"),
            OrganizationMember(id=generate_uuid(), user_id=advocate.id, organization_id=corp_org.id, role="LEGAL_MANAGER", status="ACTIVE"),
        ])

        # Create client user
        client_user = User(
            id=generate_uuid(),
            email=f"client.{uuid.uuid4().hex[:6]}@client.internal",
            password_hash=get_password_hash("Password123!"),
            full_name="Client Requester",
            is_active=True
        )
        session.add(client_user)
        session.add(OrganizationMember(id=generate_uuid(), user_id=client_user.id, organization_id=client_org.id, role="OWNER", status="ACTIVE"))

        # Create verified profile in firm_org
        profile = LawyerProfile(
            id=generate_uuid(),
            user_id=advocate.id,
            organization_id=firm_org.id,
            bar_council_number="D/999/2020",
            state_bar_council="Delhi",
            admitted_jurisdictions="Delhi High Court",
            verification_status=LawyerVerificationStatus.VERIFIED.value,
            is_available_for_inquiries=True,
            is_published=True
        )
        session.add(profile)

        # Create matter assigned to advocate under firm_org
        matter = LegalMatter(
            id=generate_uuid(),
            matter_code=f"MAT-2026-{uuid.uuid4().hex[:6].upper()}",
            title="SaaS Agreement Review",
            matter_type="CONTRACT_REVIEW",
            counterparty_name="Vendor Corp",
            client_organization_id=client_org.id,
            lawyer_organization_id=firm_org.id,
            client_user_id=client_user.id,
            lawyer_user_id=advocate.id,
            status="ACCEPTED"
        )
        session.add(matter)
        await session.commit()

    transport = ASGITransport(app=app)
    client_headers = auth_helper(client_user.id, client_org.id, role="OWNER")
    # Lawyer active in corp_org (NOT firm_org!)
    lawyer_corp_headers = auth_helper(advocate.id, corp_org.id, role="LEGAL_MANAGER")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Client posts a message
        msg_res = await client.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Hello advocate, please review our clause indemnity."},
            headers=client_headers
        )
        assert msg_res.status_code == 201

        # Lawyer is in corp_org ("Acne Corp") - MUST receive unread counts!
        counts_res = await client.get("/api/v1/notifications/unread-count", headers=lawyer_corp_headers)
        assert counts_res.status_code == 200
        data = counts_res.json()
        assert data["unread_count"] == 1, f"Expected unread_count=1, got {data}"
        assert data["unread_messages_count"] == 1, f"Expected unread_messages_count=1, got {data}"

        # Lawyer lists notifications in corp_org - MUST include the matter notification!
        notif_list_res = await client.get("/api/v1/notifications", headers=lawyer_corp_headers)
        assert notif_list_res.status_code == 200
        list_data = notif_list_res.json()
        assert list_data["unread_messages_count"] == 1
        assert len(list_data["items"]) == 1
        assert list_data["items"][0]["event_type"] == "MATTER_MESSAGE_RECEIVED"

        # Lawyer opens matter and marks read from corp_org
        read_res = await client.patch(f"/api/v1/matters/{matter.id}/read", headers=lawyer_corp_headers)
        assert read_res.status_code == 200

        # Unread counts in corp_org must now be 0!
        counts_cleared = await client.get("/api/v1/notifications/unread-count", headers=lawyer_corp_headers)
        assert counts_cleared.json()["unread_count"] == 0
        assert counts_cleared.json()["unread_messages_count"] == 0




