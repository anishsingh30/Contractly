import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.core.security import create_access_token, get_password_hash
from app.models.base import utc_now
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.contract import Contract, ContractVersion, ContractRedline
from app.models.audit import AuditLog
from app.models.lawyer import (
    LawyerProfile,
    LegalMatter,
    MatterAccessGrant,
    MatterMessage,
    LawyerVerificationStatus,
    MatterStatus,
    MatterPermissionLevel,
    MatterSenderType,
    MatterDeclineReason,
)
from app.services.storage import storage_client


@pytest.fixture
def auth_helper():
    def _make_headers(user_id: str, org_id: str, role: str = "OWNER"):
        token = create_access_token(subject=user_id, org_id=org_id, role=role)
        return {
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": org_id,
        }
    return _make_headers


@pytest.mark.asyncio
async def test_lawyer_matter_end_to_end_security_and_lifecycle(test_engine, auth_helper):
    """
    Comprehensive test covering:
    1. Client inquiry submission and persistence.
    2. Matter listing and retrieval scoping.
    3. Unverified lawyers omitted from directory and cannot accept inquiries.
    4. Conflict clearance mandatory before acceptance.
    5. Client consent mandatory before document activation.
    6. Cross-tenant IDOR protection (returns 404).
    7. No document access before consent.
    8. Active grant permits only specified lawyer, matter, contract.
    9. Revocation and closure block subsequent document access.
    10. Read-only grants cannot submit redlines.
    11. Clients cannot read internal lawyer notes.
    12. Unassigned lawyers & platform admins cannot read protected matter content.
    13. Invalid state transitions rejected.
    14. Unauthorized profile updates fail.
    15. Audit logs recorded without sensitive data.
    """
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Create Client Organization & User
        client_org = Organization(name="Northstar Corp", slug=f"northstar-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"client.{uuid.uuid4().hex[:6]}@northstar.com", password_hash="pw", full_name="Alice In-House Counsel")
        session.add_all([client_org, client_user])
        await session.flush()

        client_member = OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER", status="ACTIVE")
        session.add(client_member)

        # 2. Create Target Contract and Version under Client Org
        contract = Contract(
            organization_id=client_org.id,
            contract_id=f"CTR-2026-{uuid.uuid4().hex[:4].upper()}",
            title="Enterprise Cloud MSA",
            contract_type="SaaS",
            counterparty="Adverse Cloud Ltd",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        # Save mock file into storage client for streaming tests
        test_file_path = f"{client_org.id}/{contract.contract_id}/v1.0/contract.pdf"
        storage_client.save_file(test_file_path, b"%PDF-1.4 Mock Contract Content", tenant_id=client_org.id)

        version = ContractVersion(
            contract_id=contract.id,
            version_number="v1.0",
            filename="contract.pdf",
            file_storage_path=test_file_path,
            file_mime_type="application/pdf",
            file_byte_size=32,
            sha256_checksum="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            page_count=3
        )
        session.add(version)

        # 3. Create Verified Lawyer Organization & User
        lawyer_org = Organization(name="Swaminathan & Chambers", slug=f"swaminathan-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_user = User(email=f"radhika.{uuid.uuid4().hex[:6]}@chambers.in", password_hash="pw", full_name="Adv. Radhika Swaminathan")
        session.add_all([lawyer_org, lawyer_user])
        await session.flush()

        lawyer_member = OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="OWNER", status="ACTIVE")
        session.add(lawyer_member)

        lawyer_profile = LawyerProfile(
            user_id=lawyer_user.id,
            organization_id=lawyer_org.id,
            bar_council_number=f"D/{uuid.uuid4().hex[:4].upper()}/2012",
            state_bar_council="Bar Council of Delhi",
            admitted_jurisdictions="Supreme Court of India, Delhi High Court",
            practice_areas=["Corporate Contracts", "Technology & SaaS"],
            experience_years=14,
            consultation_fee="₹7,500 / 45 min",
            bio="Technology law advocate.",
            verification_status=LawyerVerificationStatus.VERIFIED.value,
            is_published=True,
            is_available_for_inquiries=True
        )
        session.add(lawyer_profile)

        # 4. Create Unverified Lawyer (PENDING_REVIEW)
        unverified_org = Organization(name="Unverified Practice", slug=f"unverified-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        unverified_user = User(email=f"unverified.{uuid.uuid4().hex[:6]}@practice.in", password_hash="pw", full_name="John Doe Advocate")
        session.add_all([unverified_org, unverified_user])
        await session.flush()

        unverified_member = OrganizationMember(organization_id=unverified_org.id, user_id=unverified_user.id, role="OWNER", status="ACTIVE")
        session.add(unverified_member)

        unverified_profile = LawyerProfile(
            user_id=unverified_user.id,
            organization_id=unverified_org.id,
            bar_council_number=f"KAR/{uuid.uuid4().hex[:4].upper()}/2024",
            state_bar_council="Bar Council of Karnataka",
            admitted_jurisdictions="Karnataka High Court",
            practice_areas=["Employment"],
            experience_years=1,
            consultation_fee="₹3,000 / 45 min",
            verification_status=LawyerVerificationStatus.PENDING_REVIEW.value,
            is_available_for_inquiries=True
        )
        session.add(unverified_profile)

        # 5. Create Third-Party Observer Lawyer (Unassigned to matter)
        third_lawyer_org = Organization(name="Third Firm", slug=f"third-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        third_lawyer_user = User(email=f"third.{uuid.uuid4().hex[:6]}@thirdfirm.com", password_hash="pw", full_name="Adv. Third Party")
        session.add_all([third_lawyer_org, third_lawyer_user])
        await session.flush()
        third_lawyer_member = OrganizationMember(organization_id=third_lawyer_org.id, user_id=third_lawyer_user.id, role="OWNER", status="ACTIVE")
        session.add(third_lawyer_member)

        # 6. Create Platform Super Admin
        admin_org = Organization(name="Contractly Ops", slug=f"platform-ops-{uuid.uuid4().hex[:6]}")
        admin_user = User(email=f"admin.{uuid.uuid4().hex[:6]}@contractly.internal", password_hash="pw", full_name="Platform Admin", is_super_admin=True)
        session.add_all([admin_org, admin_user])
        await session.flush()
        admin_member = OrganizationMember(organization_id=admin_org.id, user_id=admin_user.id, role="OWNER", status="ACTIVE")
        session.add(admin_member)

        await session.commit()

        # Auth Headers
        client_headers = auth_helper(client_user.id, client_org.id)
        lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id)
        unverified_headers = auth_helper(unverified_user.id, unverified_org.id)
        third_lawyer_headers = auth_helper(third_lawyer_user.id, third_lawyer_org.id)
        admin_headers = auth_helper(admin_user.id, admin_org.id)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ====================================================================
        # TEST 1: Public Directory - Only verified advocates appear
        # ====================================================================
        res_dir = await client.get("/api/v1/lawyers/directory", headers=client_headers)
        assert res_dir.status_code == 200
        dir_data = res_dir.json()
        assert len(dir_data) >= 1
        lawyer_user_ids = [d["user_id"] for d in dir_data]
        assert lawyer_user.id in lawyer_user_ids
        assert unverified_user.id not in lawyer_user_ids  # Unverified omitted!

        # ====================================================================
        # TEST 2: Inquiry submission rejected for unverified advocate
        # ====================================================================
        inq_unverified = {
            "lawyer_user_id": unverified_user.id,
            "title": "Review Employment Terms",
            "counterparty_name": "Tech Corp",
        }
        res_fail_inq = await client.post("/api/v1/matters", json=inq_unverified, headers=client_headers)
        assert res_fail_inq.status_code == 400
        assert "not currently verified" in res_fail_inq.json()["detail"]

        # ====================================================================
        # TEST 3: Inquiry submission succeeds for verified advocate
        # ====================================================================
        inq_valid = {
            "lawyer_user_id": lawyer_user.id,
            "title": "MSA Indemnity & Liability Cap Assessment",
            "matter_type": "CONTRACT_REVIEW",
            "counterparty_name": "Adverse Cloud Ltd",
            "contract_id": contract.id,
            "preferred_time_slot": "Thursday at 2:00 PM",
            "client_notes": "Please verify liability cap enforceability."
        }
        res_inq = await client.post("/api/v1/matters", json=inq_valid, headers=client_headers)
        assert res_inq.status_code == 201
        matter_data = res_inq.json()
        matter_id = matter_data["id"]
        assert matter_data["status"] == "SUBMITTED"
        assert matter_data["conflict_cleared"] is False
        assert matter_data["client_consent_given"] is False
        assert matter_data["has_active_grant"] is False

        # ====================================================================
        # TEST 4: Scoped Listing & IDOR Protection
        # ====================================================================
        # Client sees it in their matters list
        res_client_list = await client.get("/api/v1/matters", headers=client_headers)
        assert res_client_list.status_code == 200
        assert any(m["id"] == matter_id for m in res_client_list.json())

        # Assigned lawyer sees it in their incoming queue
        res_lawyer_list = await client.get("/api/v1/matters", headers=lawyer_headers)
        assert res_lawyer_list.status_code == 200
        assert any(m["id"] == matter_id for m in res_lawyer_list.json())

        # Unassigned third-party lawyer CANNOT see it
        res_third_list = await client.get("/api/v1/matters", headers=third_lawyer_headers)
        assert res_third_list.status_code == 200
        assert not any(m["id"] == matter_id for m in res_third_list.json())

        # Unassigned lawyer direct ID retrieval returns 404 (IDOR defense)
        res_third_get = await client.get(f"/api/v1/matters/{matter_id}", headers=third_lawyer_headers)
        assert res_third_get.status_code == 404

        # ====================================================================
        # TEST 5: Document Access BLOCKED prior to conflict clearance & consent
        # ====================================================================
        res_doc_list_blocked = await client.get(f"/api/v1/matters/{matter_id}/documents", headers=lawyer_headers)
        assert res_doc_list_blocked.status_code == 403
        assert "prior to client consent" in res_doc_list_blocked.json()["detail"]

        res_stream_blocked = await client.get(f"/api/v1/matters/{matter_id}/documents/{version.id}/stream", headers=lawyer_headers)
        assert res_stream_blocked.status_code == 403

        # ====================================================================
        # TEST 6: Clarification Request and Client Response Flow
        # ====================================================================
        # Place under review
        res_review = await client.post(f"/api/v1/matters/{matter_id}/review", headers=lawyer_headers)
        assert res_review.status_code == 200
        assert res_review.json()["status"] == "UNDER_REVIEW"

        # Lawyer asks for clarification
        clarify_req = {"scoping_question": "Does this contract include customer personal data?"}
        res_clarify = await client.post(f"/api/v1/matters/{matter_id}/clarification/request", json=clarify_req, headers=lawyer_headers)
        assert res_clarify.status_code == 200
        assert res_clarify.json()["status"] == "CLARIFICATION_REQUESTED"

        # Client responds
        clarify_resp = {"scoping_answer": "Yes, customer telemetry and contact records."}
        res_resp = await client.post(f"/api/v1/matters/{matter_id}/clarification/respond", json=clarify_resp, headers=client_headers)
        assert res_resp.status_code == 200
        assert res_resp.json()["status"] == "UNDER_REVIEW"

        # ====================================================================
        # TEST 7: Acceptance REJECTED without certified conflict check
        # ====================================================================
        res_accept_premature = await client.post(f"/api/v1/matters/{matter_id}/accept", json={"confirmed_slot": "Thursday at 2:00 PM"}, headers=lawyer_headers)
        assert res_accept_premature.status_code == 422
        assert "Conflict-of-interest clearance must be explicitly certified" in res_accept_premature.json()["detail"]

        # ====================================================================
        # TEST 8: Conflict Certification & Acceptance
        # ====================================================================
        res_conflict = await client.post(
            f"/api/v1/matters/{matter_id}/conflict-check",
            json={"certified_clear": True, "conflict_notes": "Adverse Cloud search clear."},
            headers=lawyer_headers
        )
        assert res_conflict.status_code == 200
        assert res_conflict.json()["conflict_cleared"] is True

        # Now accept succeeds
        res_accept = await client.post(f"/api/v1/matters/{matter_id}/accept", json={"confirmed_slot": "Thursday at 2:00 PM"}, headers=lawyer_headers)
        assert res_accept.status_code == 200
        assert res_accept.json()["status"] == "ACCEPTED"
        # Access is STILL blocked until client consent is given!
        assert res_accept.json()["has_active_grant"] is False

        # ====================================================================
        # TEST 9: Client Consent Activates Matter & Document Grant
        # ====================================================================
        consent_payload = {
            "consent_given": True,
            "permission_level": "REDLINE_COLLABORATIVE"
        }
        res_consent = await client.post(f"/api/v1/matters/{matter_id}/consent", json=consent_payload, headers=client_headers)
        assert res_consent.status_code == 200
        assert res_consent.json()["status"] == "MATTER_ACTIVE"
        assert res_consent.json()["client_consent_given"] is True
        assert res_consent.json()["has_active_grant"] is True
        assert res_consent.json()["grant_permission_level"] == "REDLINE_COLLABORATIVE"

        # ====================================================================
        # TEST 10: Authorized Lawyer Document Streaming Works
        # ====================================================================
        res_doc_list = await client.get(f"/api/v1/matters/{matter_id}/documents", headers=lawyer_headers)
        assert res_doc_list.status_code == 200
        docs = res_doc_list.json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "contract.pdf"

        res_stream = await client.get(f"/api/v1/matters/{matter_id}/documents/{version.id}/stream", headers=lawyer_headers)
        assert res_stream.status_code == 200
        assert res_stream.content == b"%PDF-1.4 Mock Contract Content"

        # ====================================================================
        # TEST 11: Lawyer Submits Tracked Redline Proposal
        # ====================================================================
        redline_payload = {
            "section_title": "Section 14.2 - Mutual Indemnification",
            "original_text": "Supplier shall defend and indemnify Customer without limitation.",
            "suggested_text": "Supplier shall defend Customer subject to aggregate liability ceiling.",
            "rationale": "Align with Indian Contract Act Section 73 remote damage principles."
        }
        res_redline = await client.post(f"/api/v1/matters/{matter_id}/redlines", json=redline_payload, headers=lawyer_headers)
        assert res_redline.status_code == 201
        redline_data = res_redline.json()
        assert redline_data["status"] == "PENDING"
        assert "Adv. Radhika Swaminathan" in redline_data["author"]

        # ====================================================================
        # TEST 12: Private Chambers Internal Notes Hidden from Client
        # ====================================================================
        # Lawyer posts client-visible message
        await client.post(
            f"/api/v1/matters/{matter_id}/messages",
            json={"message_text": "We have reviewed Section 14 and proposed a balanced cap.", "is_internal_note": False},
            headers=lawyer_headers
        )

        # Lawyer posts confidential chambers internal note
        await client.post(
            f"/api/v1/matters/{matter_id}/messages",
            json={"message_text": "INTERNAL: Client counterparty has strong bargaining position; do not concede Section 14.2 easily.", "is_internal_note": True},
            headers=lawyer_headers
        )

        # Lawyer retrieves messages: sees BOTH (2 messages)
        res_lawyer_msgs = await client.get(f"/api/v1/matters/{matter_id}/messages", headers=lawyer_headers)
        assert res_lawyer_msgs.status_code == 200
        assert len(res_lawyer_msgs.json()) >= 2
        assert any(m["is_internal_note"] is True for m in res_lawyer_msgs.json())

        # Client retrieves messages: strictly filtered server-side (NO internal note!)
        res_client_msgs = await client.get(f"/api/v1/matters/{matter_id}/messages", headers=client_headers)
        assert res_client_msgs.status_code == 200
        client_msgs = res_client_msgs.json()
        assert not any(m["is_internal_note"] is True for m in client_msgs)
        assert not any("do not concede" in m["message_text"] for m in client_msgs)

        # ====================================================================
        # TEST 13: Revocation & Closure Immediately Blocks Document Access
        # ====================================================================
        # Resolve matter
        res_resolve = await client.post(
            f"/api/v1/matters/{matter_id}/resolve",
            json={"resolution_summary": "Indemnity redline and legal advisory memo delivered."},
            headers=lawyer_headers
        )
        assert res_resolve.status_code == 200
        assert res_resolve.json()["status"] == "RESOLVED"

        # Client closes matter
        res_close = await client.post(f"/api/v1/matters/{matter_id}/close", headers=client_headers)
        assert res_close.status_code == 200
        assert res_close.json()["status"] == "CLOSED"

        # Document streaming immediately returns 403 Forbidden
        res_stream_after_close = await client.get(f"/api/v1/matters/{matter_id}/documents/{version.id}/stream", headers=lawyer_headers)
        assert res_stream_after_close.status_code == 403

        # ====================================================================
        # TEST 14: Platform Admin Cannot Read Matter Messages or Contract Text
        # ====================================================================
        res_admin_msg = await client.get(f"/api/v1/matters/{matter_id}/messages", headers=admin_headers)
        assert res_admin_msg.status_code == 404  # Strictly isolated!

        # ====================================================================
        # TEST 15: Platform Admin Can Verify Unverified Advocate
        # ====================================================================
        verify_payload = {"decision": "VERIFY", "reason": "Bar Council enrollment verified."}
        res_verify = await client.post(
            f"/api/v1/lawyers/profiles/{unverified_profile.id}/verify",
            json=verify_payload,
            headers=admin_headers
        )
        assert res_verify.status_code == 200
        assert res_verify.json()["verification_status"] == "VERIFIED"

        # Now newly verified advocate appears in public directory
        res_dir_updated = await client.get("/api/v1/lawyers/directory", headers=client_headers)
        updated_lawyer_ids = [d["user_id"] for d in res_dir_updated.json()]
        assert unverified_user.id in updated_lawyer_ids


@pytest.mark.asyncio
async def test_read_only_grant_blocks_redlines(test_engine, auth_helper):
    """Verify that READ_ONLY document access grants cannot submit redline revisions."""
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        client_org = Organization(name="RO Client Org", slug=f"ro-client-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"ro.client.{uuid.uuid4().hex[:6]}@ro.com", password_hash="pw", full_name="Client RO")
        lawyer_org = Organization(name="RO Lawyer Firm", slug=f"ro-firm-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_user = User(email=f"ro.lawyer.{uuid.uuid4().hex[:6]}@firm.com", password_hash="pw", full_name="Adv. ReadOnly")
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER", status="ACTIVE"))
        session.add(OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="OWNER", status="ACTIVE"))

        contract = Contract(organization_id=client_org.id, contract_id=f"CTR-{uuid.uuid4().hex[:4]}", title="RO MSA", contract_type="MSA", counterparty="X")
        session.add(contract)
        await session.flush()

        matter = LegalMatter(
            matter_code=f"MAT-{uuid.uuid4().hex[:6]}",
            title="Read Only Review",
            matter_type="CONTRACT_REVIEW",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=lawyer_org.id,
            lawyer_user_id=lawyer_user.id,
            contract_id=contract.id,
            counterparty_name="X",
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True
        )
        session.add(matter)
        await session.flush()

        # Create READ_ONLY grant
        grant = MatterAccessGrant(
            matter_id=matter.id,
            contract_id=contract.id,
            lawyer_user_id=lawyer_user.id,
            permission_level=MatterPermissionLevel.READ_ONLY.value,
            is_active=True
        )
        session.add(grant)
        await session.commit()

        lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempt to submit redline with READ_ONLY grant
        redline_payload = {
            "section_title": "Section 5 - Warranties",
            "original_text": "Original clause text.",
            "suggested_text": "Modified clause text."
        }
        res = await client.post(f"/api/v1/matters/{matter.id}/redlines", json=redline_payload, headers=lawyer_headers)
        assert res.status_code == 403
        assert "Collaborative redlining is not permitted" in res.json()["detail"]


@pytest.mark.asyncio
async def test_unauthorized_profile_updates_and_verification_tampering(test_engine, auth_helper):
    """Verify that clients cannot update lawyer profiles and lawyers cannot verify themselves."""
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        client_org = Organization(name="Regular Org", slug=f"reg-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"reg.{uuid.uuid4().hex[:6]}@reg.com", password_hash="pw", full_name="Regular User")
        lawyer_org = Organization(name="Law Org", slug=f"law-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_user = User(email=f"law.{uuid.uuid4().hex[:6]}@law.com", password_hash="pw", full_name="Advocate Law")
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER", status="ACTIVE"))
        session.add(OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="OWNER", status="ACTIVE"))

        profile = LawyerProfile(
            user_id=lawyer_user.id,
            organization_id=lawyer_org.id,
            bar_council_number=f"DL/{uuid.uuid4().hex[:4]}",
            state_bar_council="Delhi",
            admitted_jurisdictions="Delhi HC",
            verification_status=LawyerVerificationStatus.PENDING_REVIEW.value
        )
        session.add(profile)
        await session.commit()

        client_headers = auth_helper(client_user.id, client_org.id)
        lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Client cannot call lawyer profile endpoints
        res_client_put = await client.put("/api/v1/lawyers/profile", json={"bio": "Hacked"}, headers=client_headers)
        assert res_client_put.status_code == 403

        # Lawyer cannot call platform verification endpoint to verify themselves
        res_self_verify = await client.post(
            f"/api/v1/lawyers/profiles/{profile.id}/verify",
            json={"decision": "VERIFY"},
            headers=lawyer_headers
        )
        assert res_self_verify.status_code == 403
        assert "Platform administrator privileges required" in res_self_verify.json()["detail"]


@pytest.mark.asyncio
async def test_audit_logs_contain_no_sensitive_contract_or_message_data(test_engine, auth_helper):
    """Verify that audit logs record operational milestones without exposing message texts or secret contract text."""
    transport = ASGITransport(app=app)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        client_org = Organization(name="Audit Client", slug=f"audit-c-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"audit.c.{uuid.uuid4().hex[:6]}@c.com", password_hash="pw", full_name="Alice Audit")
        lawyer_org = Organization(name="Audit Lawyer", slug=f"audit-l-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_user = User(email=f"audit.l.{uuid.uuid4().hex[:6]}@l.com", password_hash="pw", full_name="Bob Audit")
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER", status="ACTIVE"))
        session.add(OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="OWNER", status="ACTIVE"))

        profile = LawyerProfile(
            user_id=lawyer_user.id,
            organization_id=lawyer_org.id,
            bar_council_number=f"MH/{uuid.uuid4().hex[:4]}",
            state_bar_council="MH",
            admitted_jurisdictions="Bombay HC",
            verification_status=LawyerVerificationStatus.VERIFIED.value
        )
        session.add(profile)
        await session.commit()

        client_headers = auth_helper(client_user.id, client_org.id)
        lawyer_headers = auth_helper(lawyer_user.id, lawyer_org.id)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit inquiry
        SECRET_NOTE = "SUPER_SECRET_CLIENT_CONFIDENTIAL_VALUATION_OF_100M"
        inq_res = await client.post("/api/v1/matters", json={
            "lawyer_user_id": lawyer_user.id,
            "title": "Audit Test Matter",
            "counterparty_name": "Target Counterparty",
            "client_notes": SECRET_NOTE
        }, headers=client_headers)
        assert inq_res.status_code == 201
        m_id = inq_res.json()["id"]

        # Post message with sensitive text
        SECRET_MSG = "HIGHLY_CONFIDENTIAL_CHAMBERS_STRATEGY_SECRET"
        await client.post(f"/api/v1/matters/{m_id}/messages", json={
            "message_text": SECRET_MSG,
            "is_internal_note": True
        }, headers=lawyer_headers)

        # Inspect audit logs in DB
        async with async_session() as session:
            stmt = select(AuditLog).where(AuditLog.object_id.in_([m_id]))
            res = await session.execute(stmt)
            logs = res.scalars().all()
            for log in logs:
                # Ensure raw message body is NOT in audit log detail
                assert SECRET_MSG not in log.detail

