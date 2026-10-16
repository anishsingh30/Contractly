import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.models.audit import AuditLog
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.lawyer import LawyerProfile, LawyerVerificationStatus
from sqlalchemy.future import select


@pytest.mark.asyncio
async def test_submit_lawyer_inquiry_persists_audit_log_and_truthful_message(auth_headers, test_engine):
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    async with TestSessionLocal() as session:
        # Seed an advocate user and profile
        adv_org = Organization(name="Sen Chambers", slug=f"sen-{uuid.uuid4().hex[:6]}", account_type="LEGAL_PROFESSIONAL")
        adv_user = User(
            email=f"sen.{uuid.uuid4().hex[:6]}@chambers.test",
            password_hash="testpass",
            full_name="Adv. Vikramaditya Sen",
            is_active=True,
        )
        session.add_all([adv_org, adv_user])
        await session.flush()

        adv_profile = LawyerProfile(
            user_id=adv_user.id,
            organization_id=adv_org.id,
            bar_council_number=f"D/{uuid.uuid4().hex[:4].upper()}/2015",
            state_bar_council="Bar Council of Delhi",
            admitted_jurisdictions="Delhi High Court",
            practice_areas=["Commercial Litigation", "Corporate Law"],
            experience_years=10,
            verification_status=LawyerVerificationStatus.VERIFIED.value,
            is_published=True,
            is_available_for_inquiries=True,
            consultation_fee="INR 5,000",
        )
        session.add(adv_profile)
        await session.commit()
        adv_id = adv_profile.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "lawyer_id": adv_id,
            "lawyer_name": "Adv. Vikramaditya Sen",
            "preferred_time_slot": "Thursday at 11:30 AM",
            "client_notes": "Review liability provisions in vendor agreement."
        }

        res = await client.post(
            "/api/v1/lawyers/inquiries",
            json=payload,
            headers=auth_headers
        )

        assert res.status_code in (200, 201)
        data = res.json()
        assert data["status"] in ("PENDING_APPROVAL", "SUBMITTED")
        assert "MAT-" in data["inquiry_id"]
        assert "Adv. Vikramaditya Sen" in data["message"]
        # Truthful limitations notice verification
        assert "Notice" in data["limitations_notice"]

        # Verify persistence in AuditLog on test database
        async with TestSessionLocal() as session:
            stmt = select(AuditLog).where(
                AuditLog.action == "LAWYER_CONSULTATION_INQUIRY_SUBMITTED"
            )
            result = await session.execute(stmt)
            audits = result.scalars().all()
            assert len(audits) >= 1
            matching = [a for a in audits if "Adv. Vikramaditya Sen" in a.detail]
            assert len(matching) >= 1
