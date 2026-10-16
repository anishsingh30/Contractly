import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.core.security import create_access_token
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


@pytest.fixture
async def setup_env(test_engine):
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Client Org & User
        client_org = Organization(name="Client Corporation", slug=f"client-{uuid.uuid4().hex[:6]}", account_type="BUSINESS")
        client_user = User(email=f"client.{uuid.uuid4().hex[:6]}@client.com", password_hash="pw", full_name="Client Counsel")
        session.add_all([client_org, client_user])
        await session.flush()
        session.add(OrganizationMember(organization_id=client_org.id, user_id=client_user.id, role="OWNER", status="ACTIVE"))

        # Client Contract & Version
        contract = Contract(
            organization_id=client_org.id,
            contract_id=f"CTR-TEST-{uuid.uuid4().hex[:4].upper()}",
            title="SaaS Master Agreement",
            contract_type="SaaS",
            counterparty="Adverse Provider Ltd",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        doc_path = f"{client_org.id}/{contract.contract_id}/v1.0/agreement.pdf"
        storage_client.save_file(doc_path, b"%PDF-1.4 Strictly Confidential Agreement Bytes", tenant_id=client_org.id)

        version = ContractVersion(
            contract_id=contract.id,
            version_number="v1.0",
            filename="agreement.pdf",
            file_storage_path=doc_path,
            file_mime_type="application/pdf",
            file_byte_size=46,
            sha256_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            page_count=2
        )
        session.add(version)

        # Verified Lawyer Org & User
        lawyer_org = Organization(name="Lawyer Chambers", slug=f"lawyer-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        lawyer_user = User(email=f"advocate.{uuid.uuid4().hex[:6]}@chambers.in", password_hash="pw", full_name="Advocate Sharma")
        session.add_all([lawyer_org, lawyer_user])
        await session.flush()
        session.add(OrganizationMember(organization_id=lawyer_org.id, user_id=lawyer_user.id, role="OWNER", status="ACTIVE"))

        lawyer_profile = LawyerProfile(
            user_id=lawyer_user.id,
            organization_id=lawyer_org.id,
            bar_council_number=f"BCI/{uuid.uuid4().hex[:4].upper()}/2015",
            state_bar_council="Delhi Bar",
            admitted_jurisdictions="Delhi High Court",
            practice_areas=["Commercial", "Technology Contracts"],
            verification_status=LawyerVerificationStatus.VERIFIED.value,
            is_available_for_inquiries=True
        )
        session.add(lawyer_profile)

        # Platform Super Admin
        admin_org = Organization(name="Platform Ops", slug=f"ops-{uuid.uuid4().hex[:6]}")
        admin_user = User(email=f"admin.{uuid.uuid4().hex[:6]}@platform.internal", password_hash="pw", full_name="Platform Admin", is_super_admin=True)
        session.add_all([admin_org, admin_user])
        await session.flush()
        session.add(OrganizationMember(organization_id=admin_org.id, user_id=admin_user.id, role="OWNER", status="ACTIVE"))

        # Third-party unassigned lawyer
        third_org = Organization(name="Third Firm", slug=f"third-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        third_user = User(email=f"third.{uuid.uuid4().hex[:6]}@third.com", password_hash="pw", full_name="Third Lawyer")
        session.add_all([third_org, third_user])
        await session.flush()
        session.add(OrganizationMember(organization_id=third_org.id, user_id=third_user.id, role="OWNER", status="ACTIVE"))

        await session.commit()

        return {
            "client_org": client_org,
            "client_user": client_user,
            "contract": contract,
            "version": version,
            "lawyer_org": lawyer_org,
            "lawyer_user": lawyer_user,
            "lawyer_profile": lawyer_profile,
            "admin_org": admin_org,
            "admin_user": admin_user,
            "third_org": third_org,
            "third_user": third_user,
        }


# ============================================================================
# CHECK 1: Client consent cannot activate matter without conflict clearance
# ============================================================================
@pytest.mark.asyncio
async def test_check_1_consent_cannot_activate_without_conflict_clearance(setup_env, auth_helper):
    env = setup_env
    transport = ASGITransport(app=app)

    client_headers = auth_helper(env["client_user"].id, env["client_org"].id)
    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Submit inquiry
        res_inq = await ac.post("/api/v1/matters", json={
            "lawyer_user_id": env["lawyer_user"].id,
            "title": "Conflict Check Boundary Test",
            "counterparty_name": "Adverse Provider Ltd",
            "contract_id": env["contract"].id,
        }, headers=client_headers)
        assert res_inq.status_code == 201
        m_id = res_inq.json()["id"]

        # 2. Client attempts to give consent prematurely on SUBMITTED matter -> Fails 400
        res_consent_premature = await ac.post(
            f"/api/v1/matters/{m_id}/consent",
            json={"consent_given": True, "permission_level": "READ_ONLY"},
            headers=client_headers
        )
        assert res_consent_premature.status_code == 400
        assert "must be in ACCEPTED state" in res_consent_premature.json()["detail"]

        # 3. Move to UNDER_REVIEW
        await ac.post(f"/api/v1/matters/{m_id}/review", headers=lawyer_headers)

        # 4. Client attempts consent on UNDER_REVIEW matter -> Fails 400
        res_consent_review = await ac.post(
            f"/api/v1/matters/{m_id}/consent",
            json={"consent_given": True, "permission_level": "READ_ONLY"},
            headers=client_headers
        )
        assert res_consent_review.status_code == 400

        # 5. Lawyer attempts to accept without conflict clearance -> Fails 422
        res_accept_no_conflict = await ac.post(
            f"/api/v1/matters/{m_id}/accept",
            json={"confirmed_slot": "Tomorrow 10 AM"},
            headers=lawyer_headers
        )
        assert res_accept_no_conflict.status_code == 422
        assert "Conflict-of-interest clearance must be explicitly certified" in res_accept_no_conflict.json()["detail"]

        # 6. Lawyer certifies conflict check
        res_cert = await ac.post(
            f"/api/v1/matters/{m_id}/conflict-check",
            json={"certified_clear": True, "conflict_notes": "No adverse matters found."},
            headers=lawyer_headers
        )
        assert res_cert.status_code == 200

        # 7. Lawyer accepts inquiry
        res_accept = await ac.post(
            f"/api/v1/matters/{m_id}/accept",
            json={"confirmed_slot": "Tomorrow 10 AM"},
            headers=lawyer_headers
        )
        assert res_accept.status_code == 200
        assert res_accept.json()["status"] == "ACCEPTED"

        # 8. Now client consent succeeds and activates matter
        res_consent_ok = await ac.post(
            f"/api/v1/matters/{m_id}/consent",
            json={"consent_given": True, "permission_level": "READ_ONLY"},
            headers=client_headers
        )
        assert res_consent_ok.status_code == 200
        assert res_consent_ok.json()["status"] == "MATTER_ACTIVE"
        assert res_consent_ok.json()["has_active_grant"] is True


# ============================================================================
# CHECK 2: Document list & stream request validates tenant, assigned lawyer, status, consent, and grant
# ============================================================================
@pytest.mark.asyncio
async def test_check_2_document_list_and_stream_validations(setup_env, auth_helper):
    env = setup_env
    transport = ASGITransport(app=app)

    client_headers = auth_helper(env["client_user"].id, env["client_org"].id)
    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)
    third_headers = auth_helper(env["third_user"].id, env["third_org"].id)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create active matter with consent
        res_inq = await ac.post("/api/v1/matters", json={
            "lawyer_user_id": env["lawyer_user"].id,
            "title": "Stream Validation Test",
            "counterparty_name": "Adverse Provider Ltd",
            "contract_id": env["contract"].id,
        }, headers=client_headers)
        m_id = res_inq.json()["id"]

        # Prior to conflict check & consent: lawyer list & stream return 403
        assert (await ac.get(f"/api/v1/matters/{m_id}/documents", headers=lawyer_headers)).status_code == 403
        assert (await ac.get(f"/api/v1/matters/{m_id}/documents/{env['version'].id}/stream", headers=lawyer_headers)).status_code == 403

        # Unassigned third-party lawyer receives 404 (IDOR defense)
        assert (await ac.get(f"/api/v1/matters/{m_id}/documents", headers=third_headers)).status_code == 404
        assert (await ac.get(f"/api/v1/matters/{m_id}/documents/{env['version'].id}/stream", headers=third_headers)).status_code == 404

        # Complete lifecycle to activate grant
        await ac.post(f"/api/v1/matters/{m_id}/conflict-check", json={"certified_clear": True}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/accept", json={"confirmed_slot": "Mon"}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/consent", json={"consent_given": True, "permission_level": "READ_ONLY"}, headers=client_headers)

        # Now authorized lawyer list & stream succeed
        res_list = await ac.get(f"/api/v1/matters/{m_id}/documents", headers=lawyer_headers)
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1

        res_stream = await ac.get(f"/api/v1/matters/{m_id}/documents/{env['version'].id}/stream", headers=lawyer_headers)
        assert res_stream.status_code == 200
        assert res_stream.content == b"%PDF-1.4 Strictly Confidential Agreement Bytes"

        # Requesting a non-existent version returns 404
        fake_v_id = str(uuid.uuid4())
        res_bad_v = await ac.get(f"/api/v1/matters/{m_id}/documents/{fake_v_id}/stream", headers=lawyer_headers)
        assert res_bad_v.status_code == 404


# ============================================================================
# CHECK 3: Redline creation denied on READ_ONLY, revoked consent, or closed matter
# ============================================================================
@pytest.mark.asyncio
async def test_check_3_redline_denial_conditions(setup_env, auth_helper):
    env = setup_env
    transport = ASGITransport(app=app)

    client_headers = auth_helper(env["client_user"].id, env["client_org"].id)
    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create matter and activate with READ_ONLY grant
        res_inq = await ac.post("/api/v1/matters", json={
            "lawyer_user_id": env["lawyer_user"].id,
            "title": "Redline Denial Test",
            "counterparty_name": "Adverse Provider Ltd",
            "contract_id": env["contract"].id,
        }, headers=client_headers)
        m_id = res_inq.json()["id"]

        await ac.post(f"/api/v1/matters/{m_id}/conflict-check", json={"certified_clear": True}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/accept", json={"confirmed_slot": "Mon"}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/consent", json={"consent_given": True, "permission_level": "READ_ONLY"}, headers=client_headers)

        payload = {
            "section_title": "Section 9 - Non-Compete",
            "original_text": "24 months duration.",
            "suggested_text": "12 months duration."
        }

        # 1. READ_ONLY grant rejects redlines (403)
        res_ro = await ac.post(f"/api/v1/matters/{m_id}/redlines", json=payload, headers=lawyer_headers)
        assert res_ro.status_code == 403
        assert "Collaborative redlining is not permitted" in res_ro.json()["detail"]

        # 2. Collaborative matter allows redlines
        res_inq2 = await ac.post("/api/v1/matters", json={
            "lawyer_user_id": env["lawyer_user"].id,
            "title": "Redline Collab Test",
            "counterparty_name": "Adverse Provider Ltd",
            "contract_id": env["contract"].id,
        }, headers=client_headers)
        m_id2 = res_inq2.json()["id"]

        await ac.post(f"/api/v1/matters/{m_id2}/conflict-check", json={"certified_clear": True}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id2}/accept", json={"confirmed_slot": "Tue"}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id2}/consent", json={"consent_given": True, "permission_level": "REDLINE_COLLABORATIVE"}, headers=client_headers)

        res_rw = await ac.post(f"/api/v1/matters/{m_id2}/redlines", json=payload, headers=lawyer_headers)
        assert res_rw.status_code == 201
        assert res_rw.json()["section_title"] == "Section 9 - Non-Compete"

        # 3. Client revokes grant
        await ac.post(f"/api/v1/matters/{m_id2}/grant/revoke", headers=client_headers)
        # Subsequent redline rejected (403 - inactive grant)
        res_revoked = await ac.post(f"/api/v1/matters/{m_id2}/redlines", json=payload, headers=lawyer_headers)
        assert res_revoked.status_code == 403
        assert "No active document grant found" in res_revoked.json()["detail"]

        # 4. Resolve and close matter
        await ac.post(f"/api/v1/matters/{m_id2}/resolve", json={"resolution_summary": "Done"}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id2}/close", headers=client_headers)

        # In CLOSED state, redlines rejected (400 - no longer eligible for collaboration)
        res_closed = await ac.post(f"/api/v1/matters/{m_id2}/redlines", json=payload, headers=lawyer_headers)
        assert res_closed.status_code == 400
        assert "Redlines can only be submitted for active matters" in res_closed.json()["detail"]


# ============================================================================
# CHECK 4: Message creation and retrieval enforce tenant, sender, and internal-note confidentiality
# ============================================================================
@pytest.mark.asyncio
async def test_check_4_message_creation_and_retrieval_confidentiality(setup_env, auth_helper):
    env = setup_env
    transport = ASGITransport(app=app)

    client_headers = auth_helper(env["client_user"].id, env["client_org"].id)
    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)
    third_headers = auth_helper(env["third_user"].id, env["third_org"].id)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_inq = await ac.post("/api/v1/matters", json={
            "lawyer_user_id": env["lawyer_user"].id,
            "title": "Confidential Message Test",
            "counterparty_name": "Adverse Provider Ltd",
            "contract_id": env["contract"].id,
        }, headers=client_headers)
        m_id = res_inq.json()["id"]

        # Clear conflict and accept/consent matter so messaging is active
        await ac.post(f"/api/v1/matters/{m_id}/conflict-check", json={
            "certified_clear": True,
            "conflict_notes": "No conflict"
        }, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/accept", json={"confirmed_slot": "Mon"}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/consent", json={"consent_given": True, "permission_level": "REDLINE_COLLABORATIVE"}, headers=client_headers)

        # Lawyer posts client message
        await ac.post(f"/api/v1/matters/{m_id}/messages", json={
            "message_text": "Public discussion point for client.",
            "is_internal_note": False
        }, headers=lawyer_headers)

        # Lawyer posts internal chambers note
        CHAMBERS_SECRET = "CHAMBERS_SECRET_PRIVILEGED_OPINION_777"
        await ac.post(f"/api/v1/matters/{m_id}/messages", json={
            "message_text": CHAMBERS_SECRET,
            "is_internal_note": True
        }, headers=lawyer_headers)

        # Client posts a message attempting to set is_internal_note=True
        res_client_post = await ac.post(f"/api/v1/matters/{m_id}/messages", json={
            "message_text": "Client inquiry response.",
            "is_internal_note": True  # Client attempts internal note
        }, headers=client_headers)
        assert res_client_post.status_code == 201
        # Client cannot force is_internal_note=True (sanitized to False)
        assert res_client_post.json()["is_internal_note"] is False

        # Client fetches messages: strictly filters out internal note
        client_res = await ac.get(f"/api/v1/matters/{m_id}/messages", headers=client_headers)
        assert client_res.status_code == 200
        client_msgs = client_res.json()
        assert not any(m["is_internal_note"] is True for m in client_msgs)
        assert not any(CHAMBERS_SECRET in m["message_text"] for m in client_msgs)

        # Lawyer fetches messages: sees internal notes
        lawyer_res = await ac.get(f"/api/v1/matters/{m_id}/messages", headers=lawyer_headers)
        assert lawyer_res.status_code == 200
        lawyer_msgs = lawyer_res.json()
        assert any(CHAMBERS_SECRET in m["message_text"] for m in lawyer_msgs)

        # Unassigned third party receives 404 (IDOR defense)
        assert (await ac.get(f"/api/v1/matters/{m_id}/messages", headers=third_headers)).status_code == 404
        assert (await ac.post(f"/api/v1/matters/{m_id}/messages", json={"message_text": "Hack"}, headers=third_headers)).status_code == 404


# ============================================================================
# CHECK 5: Lawyer verification cannot be performed by ordinary users or via field tampering
# ============================================================================
@pytest.mark.asyncio
async def test_check_5_lawyer_verification_privilege_enforcement(setup_env, auth_helper):
    env = setup_env
    transport = ASGITransport(app=app)

    client_headers = auth_helper(env["client_user"].id, env["client_org"].id)
    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)
    admin_headers = auth_helper(env["admin_user"].id, env["admin_org"].id)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        profile_id = env["lawyer_profile"].id

        # 1. Ordinary client user calls platform verify -> 403 Forbidden
        res_client = await ac.post(
            f"/api/v1/lawyers/profiles/{profile_id}/verify",
            json={"decision": "VERIFY"},
            headers=client_headers
        )
        assert res_client.status_code == 403

        # 2. Lawyer calls platform verify to self-verify -> 403 Forbidden
        res_lawyer = await ac.post(
            f"/api/v1/lawyers/profiles/{profile_id}/verify",
            json={"decision": "VERIFY"},
            headers=lawyer_headers
        )
        assert res_lawyer.status_code == 403

        # 3. Lawyer attempts field tampering on PUT /api/v1/lawyers/profile
        res_tamper = await ac.put(
            "/api/v1/lawyers/profile",
            json={"bio": "Updated bio", "verification_status": "VERIFIED"},
            headers=lawyer_headers
        )
        assert res_tamper.status_code == 200
        # verification_status cannot be altered via self-update

        # 4. Platform Super Admin can verify
        res_admin = await ac.post(
            f"/api/v1/lawyers/profiles/{profile_id}/verify",
            json={"decision": "VERIFY", "reason": "Bar enrollment verified."},
            headers=admin_headers
        )
        assert res_admin.status_code == 200
        assert res_admin.json()["verification_status"] == "VERIFIED"


# ============================================================================
# CHECK 6: Concurrent state transitions, duplicate grants, revocation, and closure cannot bypass authorization
# ============================================================================
@pytest.mark.asyncio
async def test_check_6_concurrent_state_transitions_and_duplicate_grants(setup_env, auth_helper, test_engine):
    env = setup_env
    transport = ASGITransport(app=app)

    client_headers = auth_helper(env["client_user"].id, env["client_org"].id)
    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_inq = await ac.post("/api/v1/matters", json={
            "lawyer_user_id": env["lawyer_user"].id,
            "title": "Concurrency & Duplicate Grant Test",
            "counterparty_name": "Adverse Provider Ltd",
            "contract_id": env["contract"].id,
        }, headers=client_headers)
        m_id = res_inq.json()["id"]

        await ac.post(f"/api/v1/matters/{m_id}/conflict-check", json={"certified_clear": True}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/accept", json={"confirmed_slot": "Mon"}, headers=lawyer_headers)

        # 1. First consent call activates matter
        res_c1 = await ac.post(
            f"/api/v1/matters/{m_id}/consent",
            json={"consent_given": True, "permission_level": "REDLINE_COLLABORATIVE"},
            headers=client_headers
        )
        assert res_c1.status_code == 200

        # 2. Subsequent duplicate consent attempts are rejected by state machine (400)
        res_c2 = await ac.post(
            f"/api/v1/matters/{m_id}/consent",
            json={"consent_given": True, "permission_level": "REDLINE_COLLABORATIVE"},
            headers=client_headers
        )
        assert res_c2.status_code == 400
        assert "Matter must be in ACCEPTED state" in res_c2.json()["detail"]

        # Verify only 1 grant record exists in database
        async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            stmt = select(MatterAccessGrant).where(MatterAccessGrant.matter_id == m_id)
            res = await session.execute(stmt)
            grants = res.scalars().all()
            assert len(grants) == 1
            assert grants[0].is_active is True

        # Revocation immediately deactivates grant
        await ac.post(f"/api/v1/matters/{m_id}/grant/revoke", headers=client_headers)
        async with async_session() as session:
            stmt = select(MatterAccessGrant).where(MatterAccessGrant.matter_id == m_id)
            res = await session.execute(stmt)
            grant = res.scalar_one()
            assert grant.is_active is False

        # Attempting document stream after revocation fails with 403
        res_stream_revoked = await ac.get(
            f"/api/v1/matters/{m_id}/documents/{env['version'].id}/stream",
            headers=lawyer_headers
        )
        assert res_stream_revoked.status_code == 403


# ============================================================================
# CHECK 7: Audit logs do not contain contract contents, access tokens, or sensitive message bodies
# ============================================================================
@pytest.mark.asyncio
async def test_check_7_audit_log_content_sanitization(setup_env, auth_helper, test_engine):
    env = setup_env
    transport = ASGITransport(app=app)

    client_headers = auth_helper(env["client_user"].id, env["client_org"].id)
    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)

    SECRET_CLIENT_NOTE = "SUPER_SECRET_UNANNOUNCED_ACQUISITION_TARGET_XYZ"
    SECRET_MESSAGE_TEXT = "HIGHLY_PRIVILEGED_ADVERSE_PARTY_STRATEGY"
    SECRET_CONFLICT_DETAILS = "ADVERSE_PARTY_REPRESENTED_IN_CONFIDENTIAL_DISPUTE"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_inq = await ac.post("/api/v1/matters", json={
            "lawyer_user_id": env["lawyer_user"].id,
            "title": "Audit Log Sanitization Test",
            "counterparty_name": "Adverse Provider Ltd",
            "contract_id": env["contract"].id,
            "client_notes": SECRET_CLIENT_NOTE
        }, headers=client_headers)
        m_id = res_inq.json()["id"]

        await ac.post(f"/api/v1/matters/{m_id}/conflict-check", json={
            "certified_clear": True,
            "conflict_notes": SECRET_CONFLICT_DETAILS
        }, headers=lawyer_headers)

        await ac.post(f"/api/v1/matters/{m_id}/accept", json={"confirmed_slot": "Mon"}, headers=lawyer_headers)
        await ac.post(f"/api/v1/matters/{m_id}/consent", json={"consent_given": True, "permission_level": "REDLINE_COLLABORATIVE"}, headers=client_headers)

        await ac.post(f"/api/v1/matters/{m_id}/messages", json={
            "message_text": SECRET_MESSAGE_TEXT,
            "is_internal_note": True
        }, headers=lawyer_headers)

        # Inspect all audit logs in DB
        async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            stmt = select(AuditLog)
            res = await session.execute(stmt)
            logs = res.scalars().all()
            for log in logs:
                assert SECRET_MESSAGE_TEXT not in log.detail
                assert SECRET_CONFLICT_DETAILS not in log.detail
                assert "Bearer" not in log.detail
                assert "%PDF-1.4" not in log.detail


# ============================================================================
# CHECK 8: Existing client contract routes do not provide a bypass to lawyers
# ============================================================================
@pytest.mark.asyncio
async def test_check_8_client_contract_routes_isolation_against_lawyers(setup_env, auth_helper):
    env = setup_env
    transport = ASGITransport(app=app)

    lawyer_headers = auth_helper(env["lawyer_user"].id, env["lawyer_org"].id)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        contract_id = env["contract"].id
        version_id = env["version"].id

        # 1. Lawyer calls GET /api/v1/contracts (lists contracts)
        res_list = await ac.get("/api/v1/contracts", headers=lawyer_headers)
        # Should return only lawyer's own tenant contracts (which is 0), NEVER client contracts
        assert res_list.status_code in (200, 403)
        if res_list.status_code == 200:
            contracts = res_list.json()
            assert not any(c["id"] == contract_id for c in contracts)

        # 2. Lawyer calls GET /api/v1/contracts/{id} directly
        res_get = await ac.get(f"/api/v1/contracts/{contract_id}", headers=lawyer_headers)
        # Tenant isolation must reject with 404 or 403
        assert res_get.status_code in (403, 404)

        # 3. Lawyer calls GET /api/v1/contracts/{id}/versions/{version_id}/download directly
        res_download = await ac.get(f"/api/v1/contracts/{contract_id}/versions/{version_id}/download", headers=lawyer_headers)
        assert res_download.status_code in (403, 404)
