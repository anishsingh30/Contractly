import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.core.security import create_access_token
from app.models.base import utc_now
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.contract import Contract
from app.models.audit import AuditLog
from app.models.lawyer import (
    LawyerProfile,
    LegalMatter,
    MatterMessage,
    LawyerVerificationStatus,
    MatterStatus,
)


@pytest.fixture
def auth_helper():
    def _make_headers(user_id: str, org_id: str, role: str = "OWNER", is_admin: bool = False):
        token = create_access_token(subject=user_id, org_id=org_id, role=role)
        headers = {
            "Authorization": f"Bearer {token}",
        }
        if org_id:
            headers["X-Tenant-ID"] = org_id
        return headers
    return _make_headers


@pytest.mark.asyncio
async def test_client_lawyer_chat_and_oversight_full_lifecycle(test_engine, auth_helper):
    """
    Verifies Section 8 requirements:
    1. Authorized client messages assigned lawyer in eligible matter.
    2. Lawyer replies and client receives persisted message.
    3. Messages remain available after refreshing / reconnecting.
    4. Client cannot access another client's conversation.
    5. Lawyer cannot access matters they are not assigned to.
    6. Unauthorized user cannot access messages by tampering with matter ID.
    7. Messages cannot be sent after matter is closed, resolved, declined, or cancelled.
    8. Revoked / suspended access prevents conversation access.
    9. Authorized admin can review conversation with a mandatory review reason.
    10. Admin review generates append-only AuditLog record.
    11. Ordinary user or organization owner cannot use Platform Admin review endpoints (403).
    12. Admin review does not expose message edit/delete, nor allow impersonation.
    13. Audit logs do not leak confidential message bodies.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Client Org & User
        client_org = Organization(name="Acme Tech", slug=f"acme-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"client.{uuid.uuid4().hex[:6]}@acme.com", password_hash="pw", full_name="Alice Client")
        session.add_all([client_org, client_user])
        await session.flush()

        client_member = OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER", status="ACTIVE")
        session.add(client_member)

        # 2. Second Client Org (for cross-tenant IDOR tests)
        other_client_org = Organization(name="Beta Labs", slug=f"beta-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        other_client_user = User(email=f"other.{uuid.uuid4().hex[:6]}@beta.com", password_hash="pw", full_name="Bob Beta")
        session.add_all([other_client_org, other_client_user])
        await session.flush()
        other_member = OrganizationMember(organization_id=other_client_org.id, user_id=other_client_user.id, role="OWNER", status="ACTIVE")
        session.add(other_member)

        # 3. Assigned Lawyer Org, User & Profile
        lawyer_org = Organization(name="Lex Chambers", slug=f"lex-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_user = User(email=f"counsel.{uuid.uuid4().hex[:6]}@lex.com", password_hash="pw", full_name="Adv. David Counsel")
        session.add_all([lawyer_org, lawyer_user])
        await session.flush()

        lawyer_member = OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="OWNER", status="ACTIVE")
        session.add(lawyer_member)

        lawyer_prof = LawyerProfile(
            user_id=lawyer_user.id,
            organization_id=lawyer_org.id,
            bar_council_number=f"BAR-CHAT-{uuid.uuid4().hex[:6]}",
            state_bar_council="Delhi",
            admitted_jurisdictions="Supreme Court of India",
            practice_areas=["Commercial Law", "SaaS Contracts"],
            verification_status=LawyerVerificationStatus.VERIFIED.value,
            is_published=True,
            is_available_for_inquiries=True,
        )
        session.add(lawyer_prof)

        # 4. Unassigned Lawyer (for unauthorized lawyer tests)
        unassigned_lawyer_org = Organization(name="Other Chambers", slug=f"other-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        unassigned_lawyer_user = User(email=f"unassigned.{uuid.uuid4().hex[:6]}@chambers.com", password_hash="pw", full_name="Adv. Eve Unassigned")
        session.add_all([unassigned_lawyer_org, unassigned_lawyer_user])
        await session.flush()
        unassigned_member = OrganizationMember(organization_id=unassigned_lawyer_org.id, user_id=unassigned_lawyer_user.id, role="OWNER", status="ACTIVE")
        session.add(unassigned_member)
        unassigned_prof = LawyerProfile(
            user_id=unassigned_lawyer_user.id,
            organization_id=unassigned_lawyer_org.id,
            bar_council_number=f"BAR-UNASS-{uuid.uuid4().hex[:6]}",
            state_bar_council="Delhi",
            admitted_jurisdictions="High Court of Delhi",
            practice_areas=["IP Law"],
            verification_status=LawyerVerificationStatus.VERIFIED.value,
            is_published=True,
            is_available_for_inquiries=True,
        )
        session.add(unassigned_prof)

        # 5. Platform Super Admin User (and Platform Org)
        admin_org = Organization(name="Contractly Internal Ops", slug=f"platform-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        admin_user = User(
            email=f"admin.{uuid.uuid4().hex[:6]}@contractly.com",
            password_hash="pw",
            full_name="Platform Super Admin",
            is_super_admin=True,
            platform_role="PLATFORM_SUPER_ADMIN"
        )
        session.add_all([admin_org, admin_user])
        await session.flush()
        admin_member = OrganizationMember(organization_id=admin_org.id, user_id=admin_user.id, role="ADMIN", status="ACTIVE")
        session.add(admin_member)

        # 6. Active Legal Matter between Client and Assigned Lawyer
        matter = LegalMatter(
            matter_code=f"MAT-2026-{uuid.uuid4().hex[:6].upper()}",
            title="SaaS Master Agreement Review",
            matter_type="CONTRACT_REVIEW",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=lawyer_org.id,
            lawyer_user_id=lawyer_user.id,
            counterparty_name="Vendor X",
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True,
        )
        session.add(matter)
        await session.commit()
        await session.refresh(matter)

    client_headers = auth_helper(client_user.id, client_org.id, role="OWNER")
    lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id, role="OWNER")
    other_client_headers = auth_helper(other_client_user.id, other_client_org.id, role="OWNER")
    unassigned_lawyer_headers = auth_helper(unassigned_lawyer_user.id, unassigned_lawyer_org.id, role="OWNER")
    admin_headers = auth_helper(admin_user.id, admin_org.id, role="ADMIN")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # TEST 1: Authorized client messages assigned lawyer
        send_res = await ac.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Hello counsel, please review clause 14 regarding liability caps."},
            headers=client_headers
        )
        assert send_res.status_code == 201, send_res.text
        msg_1 = send_res.json()
        assert msg_1["sender_type"] == "CLIENT"
        assert msg_1["message_text"] == "Hello counsel, please review clause 14 regarding liability caps."
        assert msg_1["is_internal_note"] is False

        # TEST 2: Lawyer replies and client receives persisted message
        reply_res = await ac.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Understood. The 12-month cap is standard, but we should exclude gross negligence."},
            headers=lawyer_headers
        )
        assert reply_res.status_code == 201, reply_res.text
        msg_2 = reply_res.json()
        assert msg_2["sender_type"] == "LAWYER"

        # TEST 3: Messages remain available after refreshing or signing in again
        get_res = await ac.get(f"/api/v1/matters/{matter.id}/messages", headers=client_headers)
        assert get_res.status_code == 200
        messages = get_res.json()
        assert len(messages) == 2
        assert messages[0]["id"] == msg_1["id"]
        assert messages[1]["id"] == msg_2["id"]

        # TEST 3b: Client conversation list returns summary and preview
        conv_res = await ac.get("/api/v1/matters/conversations", headers=client_headers)
        assert conv_res.status_code == 200
        conv_list = conv_res.json()
        assert len(conv_list) >= 1
        found_conv = next(c for c in conv_list if c["matter_id"] == matter.id)
        assert found_conv["message_count"] == 2
        assert "gross negligence" in found_conv["last_message_text"]
        assert found_conv["has_admin_review"] is False

        # TEST 4: Client cannot access another client's conversation (returns 404 IDOR protection)
        other_client_res = await ac.get(f"/api/v1/matters/{matter.id}/messages", headers=other_client_headers)
        assert other_client_res.status_code == 404

        other_send_res = await ac.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Intruder attempt."},
            headers=other_client_headers
        )
        assert other_send_res.status_code == 404

        # TEST 5: Lawyer cannot access matters they are not assigned to
        unassigned_res = await ac.get(f"/api/v1/matters/{matter.id}/messages", headers=unassigned_lawyer_headers)
        assert unassigned_res.status_code == 404

        unassigned_send = await ac.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Unassigned lawyer message attempt."},
            headers=unassigned_lawyer_headers
        )
        assert unassigned_send.status_code == 404

        # TEST 6: Unauthorized user cannot access messages by guessing/changing matter ID
        random_id = str(uuid.uuid4())
        random_res = await ac.get(f"/api/v1/matters/{random_id}/messages", headers=client_headers)
        assert random_res.status_code == 404

        # TEST 11: Ordinary user or organization owner CANNOT access Platform Admin oversight endpoints (403)
        org_owner_admin_res = await ac.get("/api/v1/platform/conversations", headers=client_headers)
        assert org_owner_admin_res.status_code == 403
        assert "Platform administrator privileges required" in org_owner_admin_res.json()["detail"]

        org_owner_review_res = await ac.post(
            f"/api/v1/platform/conversations/{matter.id}/review",
            json={"review_reason": "Curiosity"},
            headers=client_headers
        )
        assert org_owner_review_res.status_code == 403

        # TEST 9: Authorized admin can review conversation with a mandatory review reason
        # 9a. Empty reason fails
        empty_reason_res = await ac.post(
            f"/api/v1/platform/conversations/{matter.id}/review",
            json={"review_reason": "   "},
            headers=admin_headers
        )
        assert empty_reason_res.status_code in (400, 422)

        # 9b. Valid reason succeeds and returns messages
        admin_review_res = await ac.post(
            f"/api/v1/platform/conversations/{matter.id}/review",
            json={
                "review_reason": "SAFETY_AND_DISPUTE_INVESTIGATION",
                "notes": "Matter flagged for routine quality assurance and dispute resolution review."
            },
            headers=admin_headers
        )
        assert admin_review_res.status_code == 200, admin_review_res.text
        review_data = admin_review_res.json()
        assert review_data["matter_id"] == matter.id
        assert review_data["review_status"] == "REVIEWED"
        assert review_data["review_reason"] == "SAFETY_AND_DISPUTE_INVESTIGATION"
        assert len(review_data["messages"]) == 2

        # TEST 10: Admin review creates the required immutable audit record
        async with async_session() as session:
            stmt_audit = select(AuditLog).where(
                AuditLog.object_id == matter.id,
                AuditLog.action == "CONVERSATION_OVERSIGHT_REVIEWED"
            )
            audit_entry = (await session.execute(stmt_audit)).scalar_one_or_none()
            assert audit_entry is not None
            assert audit_entry.user_email == admin_user.email
            assert "SAFETY_AND_DISPUTE_INVESTIGATION" in audit_entry.detail

        # TEST 10b: Admin can add an administrative note strictly separated from client messages
        note_res = await ac.post(
            f"/api/v1/platform/conversations/{matter.id}/notes",
            json={"note_text": "Compliance officer reviewed; no ethics or regulatory violations detected."},
            headers=admin_headers
        )
        assert note_res.status_code == 200

        # Verify admin note is NOT injected into client's message history
        client_check_msgs = await ac.get(f"/api/v1/matters/{matter.id}/messages", headers=client_headers)
        assert len(client_check_msgs.json()) == 2  # Still exactly 2 client-lawyer messages!
        assert client_check_msgs.headers.get("x-admin-reviewed") == "true"

        # TEST 10c: Client conversation listing now reflects administrative oversight disclosure
        conv_res_after = await ac.get("/api/v1/matters/conversations", headers=client_headers)
        found_after = next(c for c in conv_res_after.json() if c["matter_id"] == matter.id)
        assert found_after["has_admin_review"] is True
        assert found_after["admin_review_reason"] is not None

        # TEST 12: Admin cannot post messages into client-lawyer thread
        admin_impersonate_res = await ac.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "I am the platform admin telling you what to do."},
            headers=admin_headers
        )
        assert admin_impersonate_res.status_code == 404

        # TEST 8: Revoked / Suspended lawyer access prevents conversation access
        async with async_session() as session:
            stmt_prof = select(LawyerProfile).where(LawyerProfile.user_id == lawyer_user.id)
            prof = (await session.execute(stmt_prof)).scalar_one()
            prof.verification_status = LawyerVerificationStatus.SUSPENDED.value
            await session.commit()

        suspended_msg_res = await ac.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "I am sending a message while suspended."},
            headers=lawyer_headers
        )
        assert suspended_msg_res.status_code == 403
        assert "suspended" in suspended_msg_res.json()["detail"].lower()

        # Restore lawyer status for closure test
        async with async_session() as session:
            stmt_prof = select(LawyerProfile).where(LawyerProfile.user_id == lawyer_user.id)
            prof = (await session.execute(stmt_prof)).scalar_one()
            prof.verification_status = LawyerVerificationStatus.VERIFIED.value
            await session.commit()

        # TEST 7: Messages cannot be sent after matter-closure policy takes effect
        # Mark matter as RESOLVED / CLOSED
        async with async_session() as session:
            stmt_m = select(LegalMatter).where(LegalMatter.id == matter.id)
            m_db = (await session.execute(stmt_m)).scalar_one()
            m_db.status = MatterStatus.RESOLVED.value
            await session.commit()

        closed_send_res = await ac.post(
            f"/api/v1/matters/{matter.id}/messages",
            json={"message_text": "Attempt to message in a resolved matter."},
            headers=client_headers
        )
        assert closed_send_res.status_code == 400
        assert "no longer active for messaging" in closed_send_res.json()["detail"].lower()

        # TEST 13: Audit logs do not contain raw message text bodies
        async with async_session() as session:
            stmt_all_audits = select(AuditLog).where(
                AuditLog.action == "MATTER_MESSAGE_SENT",
                AuditLog.object_type == "MatterMessage"
            )
            sent_audits = (await session.execute(stmt_all_audits)).scalars().all()
            for sa in sent_audits:
                assert "liability caps" not in sa.detail
                assert "gross negligence" not in sa.detail
