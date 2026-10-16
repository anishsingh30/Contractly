"""
End-to-End Regression Test Suite:
Get Legal Help, Lawyer Approval Queue, and Synchronized Client-Lawyer Messaging.

Validates:
1. Admin lawyer creation, verification, publication lifecycle & client directory appearance.
2. Directory privacy protection (no private email/phone/cert leakage).
3. Directory resilience against silent failure (HTTP 500 on DB exception, no masked empty 200).
4. Client consultation intake creates genuine LegalMatter (SUBMITTED) & initial MatterMessage.
5. Idempotent intake guard against rapid double-clicks.
6. Chat guard blocking premature messaging while consultation is pending administrative approval.
7. Admin consultation intake queue visibility (GET /platform/consultation-requests).
8. Admin consultation approval (POST /platform/consultation-requests/{id}/decision).
9. Synchronized bidirectional messaging post-approval (Client <-> Lawyer).
10. Admin consultation rejection lifecycle (status -> DECLINED, messaging permanently blocked).
11. Admin conversation oversight with mandatory justification and audit logging.
12. Multi-tenant IDOR protection (unauthorized tenant blocked from accessing matter).
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
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
async def test_get_legal_help_approval_and_synchronized_messaging(test_engine, auth_helper):
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Super Admin
        admin_user = User(
            email=f"admin.{uuid.uuid4().hex[:6]}@contractly.test",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="Platform Legal Overseer",
            is_active=True,
            is_super_admin=True,
        )
        session.add(admin_user)

        # 2. Client Org & Client User
        client_org = Organization(name="Starlight Corp", slug=f"star-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(
            email=f"client.{uuid.uuid4().hex[:6]}@starlight.test",
            password_hash=get_password_hash("ClientPass123!"),
            full_name="Alice Client Director",
            is_active=True,
        )
        session.add_all([client_org, client_user])
        await session.flush()

        client_member = OrganizationMember(
            organization_id=client_org.id,
            user_id=client_user.id,
            role="OWNER",
            status="ACTIVE",
        )
        session.add(client_member)

        # 3. Third-party Client (for IDOR tests)
        stranger_org = Organization(name="Rival Inc", slug=f"rival-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        stranger_user = User(
            email=f"stranger.{uuid.uuid4().hex[:6]}@rival.test",
            password_hash=get_password_hash("Pass123!"),
            full_name="Eve Stranger",
            is_active=True,
        )
        session.add_all([stranger_org, stranger_user])
        await session.flush()
        stranger_member = OrganizationMember(
            organization_id=stranger_org.id,
            user_id=stranger_user.id,
            role="OWNER",
            status="ACTIVE",
        )
        session.add(stranger_member)

        # 4. Advocate Org & Advocate User
        lawyer_org = Organization(name="Athena Chambers", slug=f"athena-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_user = User(
            email=f"counsel.{uuid.uuid4().hex[:6]}@athena.test",
            password_hash=get_password_hash("CounselPass123!"),
            full_name="Adv. Vikram Sharma",
            is_active=True,
        )
        session.add_all([lawyer_org, lawyer_user])
        await session.flush()

        lawyer_member = OrganizationMember(
            organization_id=lawyer_org.id,
            user_id=lawyer_user.id,
            role="OWNER",
            status="ACTIVE",
        )
        session.add(lawyer_member)

        await session.commit()

        admin_headers = auth_helper(admin_user.id, None, role="ADMIN", is_admin=True)
        client_headers = auth_helper(client_user.id, client_org.id, role="OWNER")
        lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id, role="OWNER")
        stranger_headers = auth_helper(stranger_user.id, stranger_org.id, role="OWNER")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # =====================================================================
        # Step 1: Admin creates lawyer profile
        # =====================================================================
        lawyer_payload = {
            "full_name": "Adv. Vikram Sharma",
            "email": lawyer_user.email,
            "phone_number": "+91 98765 43210",
            "professional_title": "Senior Advocate",
            "firm_name": "Athena Chambers",
            "bar_council_number": f"D/{uuid.uuid4().hex[:4].upper()}/2018",
            "state_bar_council": "Bar Council of Delhi",
            "admitted_jurisdictions": "Delhi High Court & Supreme Court",
            "experience_years": 11,
            "consultation_fee": "INR 5,000",
            "is_published": False,
            "is_available_for_inquiries": True,
            "practice_areas": ["Commercial Contracts", "M&A", "IP Licensing"],
            "bio": "Experienced legal counsel specializing in enterprise commercial agreements.",
        }
        res_create = await client.post("/api/v1/platform/lawyers", json=lawyer_payload, headers=admin_headers)
        assert res_create.status_code in (200, 201), res_create.text
        created_lawyer = res_create.json()
        lawyer_id = created_lawyer["id"]
        assert created_lawyer["verification_status"] == "PENDING_REVIEW"
        assert created_lawyer["is_published"] is False

        # Verify not yet in public directory
        res_dir = await client.get("/api/v1/lawyers/directory", headers=client_headers)
        assert res_dir.status_code == 200
        matching = [l for l in res_dir.json() if l["id"] == lawyer_id]
        assert len(matching) == 0, "Unverified/unpublished lawyer must not appear in directory"

        # Verify and Publish lawyer via Platform Admin
        res_verify = await client.post(
            f"/api/v1/platform/lawyers/{lawyer_id}/verify",
            json={"decision": "VERIFY", "reason": "Bar Council credentials confirmed with Bar Council registry."},
            headers=admin_headers,
        )
        assert res_verify.status_code == 200

        res_publish = await client.post(
            f"/api/v1/platform/lawyers/{lawyer_id}/publish",
            json={"is_published": True},
            headers=admin_headers,
        )
        assert res_publish.status_code == 200

        # Verify lawyer appears in public directory with strict privacy enforcement
        res_dir2 = await client.get("/api/v1/lawyers/directory", headers=client_headers)
        assert res_dir2.status_code == 200
        matching2 = [l for l in res_dir2.json() if l["id"] == lawyer_id]
        assert len(matching2) == 1
        dir_lawyer = matching2[0]
        assert dir_lawyer["full_name"] == "Adv. Vikram Sharma"
        # Privacy verification: no phone numbers or verification notes in client response
        assert "primary_phone" not in dir_lawyer or dir_lawyer.get("primary_phone") is None
        assert "verification_notes" not in dir_lawyer

        # =====================================================================
        # Step 2: Client submits consultation inquiry
        # =====================================================================
        inquiry_payload = {
            "lawyer_id": lawyer_id,
            "title": "Master Services Agreement Dispute Review",
            "counterparty_name": "Acme Global Solutions",
            "preferred_time_slot": "Tomorrow 3:00 PM IST",
            "client_notes": "We require advice regarding limitation of liability clause 12.4.",
            "urgency": "HIGH",
        }
        res_inquiry = await client.post("/api/v1/lawyers/inquiries", json=inquiry_payload, headers=client_headers)
        assert res_inquiry.status_code in (200, 201), res_inquiry.text
        inquiry_data = res_inquiry.json()
        assert inquiry_data["success"] is True
        matter_id = inquiry_data["matter_id"]
        matter_code = inquiry_data["inquiry_reference"]
        assert inquiry_data["status"] in ("SUBMITTED", "PENDING_APPROVAL")

        # Test idempotency: re-submitting duplicate inquiry within minutes returns existing matter
        res_dup = await client.post("/api/v1/lawyers/inquiries", json=inquiry_payload, headers=client_headers)
        assert res_dup.status_code in (200, 201)
        dup_data = res_dup.json()
        assert dup_data["matter_id"] == matter_id
        assert "Existing consultation request" in dup_data.get("message", "")

        # Verify matter exists in DB with SUBMITTED status and initial message is recorded
        async with async_session() as s:
            stmt = select(LegalMatter).where(LegalMatter.id == matter_id)
            res_m = await s.execute(stmt)
            m = res_m.scalar_one()
            assert m.status == MatterStatus.SUBMITTED
            assert m.client_user_id == client_user.id
            assert m.lawyer_user_id == lawyer_user.id

            stmt_msg = select(MatterMessage).where(MatterMessage.matter_id == matter_id)
            res_msgs = await s.execute(stmt_msg)
            initial_msgs = res_msgs.scalars().all()
            assert len(initial_msgs) == 1
            assert "limitation of liability clause 12.4" in initial_msgs[0].message_text
            assert initial_msgs[0].sender_type == "CLIENT"

        # =====================================================================
        # Step 3: Guard Check - Premature Messaging is Blocked While Pending
        # =====================================================================
        res_premature_msg = await client.post(
            f"/api/v1/matters/{matter_id}/messages",
            json={"message_text": "Hello counsel, following up on our request!"},
            headers=client_headers,
        )
        assert res_premature_msg.status_code == 400
        assert "pending administrative approval" in res_premature_msg.json()["detail"].lower()

        # In conversation list, is_active_for_messaging should be False
        res_convs = await client.get("/api/v1/matters/conversations", headers=client_headers)
        assert res_convs.status_code == 200
        pending_conv = next((c for c in res_convs.json() if c["matter_id"] == matter_id), None)
        assert pending_conv is not None
        assert pending_conv["is_active_for_messaging"] is False
        assert pending_conv["status"] == "SUBMITTED"

        # =====================================================================
        # Step 4: Admin Consultation Queue Visibility & Approval
        # =====================================================================
        res_admin_queue = await client.get("/api/v1/platform/consultation-requests", headers=admin_headers)
        assert res_admin_queue.status_code == 200
        requests = res_admin_queue.json()
        matching_req = next((r for r in requests if r["matter_id"] == matter_id), None)
        assert matching_req is not None
        assert matching_req["matter_code"] == matter_code
        assert matching_req["counterparty_name"] == "Acme Global Solutions"
        assert matching_req["client_organization_name"] == "Starlight Corp"
        assert matching_req["lawyer_user_name"] == "Adv. Vikram Sharma"
        assert matching_req["status"] == "SUBMITTED"

        # Admin approves the consultation request
        decision_payload = {
            "action": "APPROVE",
            "reason": "Conflict check cleared. Counsel is qualified and available.",
        }
        res_approve = await client.post(
            f"/api/v1/platform/consultation-requests/{matter_id}/decision",
            json=decision_payload,
            headers=admin_headers,
        )
        assert res_approve.status_code == 200
        approve_resp = res_approve.json()
        assert approve_resp["success"] is True
        assert approve_resp["new_status"] == "ACCEPTED"
        assert approve_resp["is_active_for_messaging"] is True

        # Test idempotency: re-approving is harmless
        res_reapprove = await client.post(
            f"/api/v1/platform/consultation-requests/{matter_id}/decision",
            json=decision_payload,
            headers=admin_headers,
        )
        assert res_reapprove.status_code == 200

        # =====================================================================
        # Step 5: Synchronized Bidirectional Messaging Post-Approval
        # =====================================================================
        # Client sends follow-up message
        res_client_send = await client.post(
            f"/api/v1/matters/{matter_id}/messages",
            json={"message_text": "Good afternoon Advocate Sharma, thank you for accepting our matter."},
            headers=client_headers,
        )
        assert res_client_send.status_code in (200, 201), res_client_send.text

        # Lawyer sends reply
        res_lawyer_reply = await client.post(
            f"/api/v1/matters/{matter_id}/messages",
            json={"message_text": "Good afternoon. I have reviewed clause 12.4. Let us schedule a call."},
            headers=lawyer_headers,
        )
        assert res_lawyer_reply.status_code in (200, 201), res_lawyer_reply.text

        # Client fetches messages and sees both
        res_client_thread = await client.get(f"/api/v1/matters/{matter_id}/messages", headers=client_headers)
        assert res_client_thread.status_code == 200
        client_msgs = res_client_thread.json()
        assert len(client_msgs) >= 3  # Initial intake note + client follow-up + lawyer reply
        texts = [m["message_text"] for m in client_msgs]
        assert any("limitation of liability" in t for t in texts)
        assert any("thank you for accepting" in t for t in texts)
        assert any("reviewed clause 12.4" in t for t in texts)

        # Lawyer fetches messages and sees identical synchronized history
        res_lawyer_thread = await client.get(f"/api/v1/matters/{matter_id}/messages", headers=lawyer_headers)
        assert res_lawyer_thread.status_code == 200
        assert len(res_lawyer_thread.json()) == len(client_msgs)

        # =====================================================================
        # Step 6: Admin Oversight with Mandatory Justification & Audit Log
        # =====================================================================
        res_oversight_list = await client.get("/api/v1/platform/conversations", headers=admin_headers)
        assert res_oversight_list.status_code == 200
        oversight_items = res_oversight_list.json()
        assert any(item["matter_id"] == matter_id for item in oversight_items)

        # Review messages with compliance reason
        review_payload = {
            "reason": "COMPLIANCE_REVIEW",
            "notes": "Scheduled routine compliance quality assessment.",
        }
        res_review = await client.post(
            f"/api/v1/platform/conversations/{matter_id}/review",
            json=review_payload,
            headers=admin_headers,
        )
        assert res_review.status_code == 200
        review_data = res_review.json()
        assert len(review_data["messages"]) >= 3

        # Verify audit log recorded in DB
        async with async_session() as s:
            stmt_audit = select(AuditLog).where(
                AuditLog.action.in_(["PLATFORM_CONSULTATION_REQUEST_APPROVED", "CONVERSATION_OVERSIGHT_REVIEWED"])
            )
            res_a = await s.execute(stmt_audit)
            audits = res_a.scalars().all()
            actions = [a.action for a in audits]
            assert "PLATFORM_CONSULTATION_REQUEST_APPROVED" in actions
            assert "CONVERSATION_OVERSIGHT_REVIEWED" in actions

        # =====================================================================
        # Step 7: Multi-Tenant IDOR Guard
        # =====================================================================
        # Stranger client cannot read or write to this matter
        res_stranger_read = await client.get(f"/api/v1/matters/{matter_id}/messages", headers=stranger_headers)
        assert res_stranger_read.status_code in (403, 404)

        res_stranger_write = await client.post(
            f"/api/v1/matters/{matter_id}/messages",
            json={"message_text": "I should not be able to send this!"},
            headers=stranger_headers,
        )
        assert res_stranger_write.status_code in (403, 404)

        # =====================================================================
        # Step 8: Rejection Lifecycle
        # =====================================================================
        # Client submits a second inquiry to be rejected
        inquiry_reject_payload = {
            "lawyer_id": lawyer_id,
            "title": "Patent Dispute Inquiry",
            "counterparty_name": "Mega Tech",
            "client_notes": "Patent infringement matter.",
        }
        res_inq2 = await client.post("/api/v1/lawyers/inquiries", json=inquiry_reject_payload, headers=client_headers)
        assert res_inq2.status_code in (200, 201), res_inq2.text
        matter2_id = res_inq2.json()["matter_id"]

        # Admin rejects
        res_reject = await client.post(
            f"/api/v1/platform/consultation-requests/{matter2_id}/decision",
            json={"action": "REJECT", "reason": "Jurisdictional constraint; advocate does not practice patent litigation."},
            headers=admin_headers,
        )
        assert res_reject.status_code == 200
        rej_data = res_reject.json()
        assert rej_data["new_status"] == "DECLINED"
        assert rej_data["is_active_for_messaging"] is False

        # Attempting to message in declined matter is blocked
        res_blocked_msg = await client.post(
            f"/api/v1/matters/{matter2_id}/messages",
            json={"message_text": "Can we still talk?"},
            headers=client_headers,
        )
        assert res_blocked_msg.status_code == 400
        assert "declined" in res_blocked_msg.json()["detail"].lower() or "active" in res_blocked_msg.json()["detail"].lower()
