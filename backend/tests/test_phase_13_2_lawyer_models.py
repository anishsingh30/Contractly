import os
import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.base import utc_now, generate_uuid
from app.models.organization import Organization
from app.models.user import User
from app.models.contract import Contract
from app.models.lawyer import (
    LawyerProfile,
    LegalMatter,
    MatterAccessGrant,
    MatterMessage,
    LawyerAvailability,
    LawyerVerificationStatus,
    MatterStatus,
    MatterPermissionLevel,
    MatterSenderType,
    MatterDeclineReason,
)


@pytest.mark.asyncio
async def test_lawyer_profile_creation_and_defaults(test_engine):
    """
    Test LawyerProfile model creation, ensuring verification_status defaults
    strictly to PENDING_REVIEW and is not implied merely by registration.
    """
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # 1. Create practice organization and advocate user
        org = Organization(
            name="Swaminathan & Chambers",
            slug=f"swaminathan-chambers-{uuid.uuid4().hex[:6]}",
            account_type="LEGAL_PROFESSIONAL"
        )
        user = User(
            email=f"radhika.{uuid.uuid4().hex[:6]}@chambers.in",
            password_hash="hashed_pw_test",
            full_name="Advocate Radhika Swaminathan"
        )
        session.add(org)
        session.add(user)
        await session.flush()

        # 2. Create LawyerProfile without explicit verification status
        profile = LawyerProfile(
            user_id=user.id,
            organization_id=org.id,
            bar_council_number=f"D/{uuid.uuid4().hex[:4].upper()}/2012",
            state_bar_council="Bar Council of Delhi",
            admitted_jurisdictions="Supreme Court of India, High Court of Delhi",
            practice_areas=["Corporate Contracts", "Technology & SaaS", "Data Privacy (DPDPA)"],
            experience_years=14,
            consultation_fee="₹7,500 / 45 min",
            bio="Advises venture-backed startups on SaaS and cross-border commercial deals."
        )
        session.add(profile)
        await session.flush()

        # 3. Assert defaults and persistence
        assert profile.id is not None
        assert profile.verification_status == LawyerVerificationStatus.PENDING_REVIEW.value
        assert profile.is_available_for_inquiries is True
        assert profile.experience_years == 14
        assert profile.verified_at is None
        assert profile.verified_by_user_id is None
        assert isinstance(profile.practice_areas, list)
        assert "Technology & SaaS" in profile.practice_areas

        # 4. Verify unique constraint on user_id
        duplicate_profile = LawyerProfile(
            user_id=user.id,  # Same user
            organization_id=org.id,
            bar_council_number=f"D/{uuid.uuid4().hex[:4].upper()}/2015",
            state_bar_council="Bar Council of Delhi",
            admitted_jurisdictions="High Court of Delhi",
            practice_areas=["Commercial Law"],
        )
        session.add(duplicate_profile)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_lawyer_profile_status_validation():
    """Verify that arbitrary verification status strings are rejected by @validates."""
    profile = LawyerProfile()
    # Valid enum assignments
    profile.verification_status = LawyerVerificationStatus.VERIFIED
    assert profile.verification_status == "VERIFIED"
    profile.verification_status = "REJECTED"
    assert profile.verification_status == "REJECTED"

    # Invalid assignment raises ValueError
    with pytest.raises(ValueError, match="Invalid verification status"):
        profile.verification_status = "INSTANT_ADMIN_ACCESS"


@pytest.mark.asyncio
async def test_legal_matter_lifecycle_and_safeguards(test_engine):
    """
    Test LegalMatter creation, independent conflict clearance,
    independent client consent fields, and lifecycle state enum guards.
    """
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Create client org & user
        client_org = Organization(
            name="Northstar Technologies Ltd",
            slug=f"northstar-{uuid.uuid4().hex[:6]}",
            account_type="BUSINESS"
        )
        client_user = User(
            email=f"client.{uuid.uuid4().hex[:6]}@northstar.com",
            password_hash="pw",
            full_name="Sarah Legal Ops"
        )
        # Create lawyer org & user
        lawyer_org = Organization(
            name="Sen Legal Partners",
            slug=f"sen-legal-{uuid.uuid4().hex[:6]}",
            account_type="LEGAL_PROFESSIONAL"
        )
        lawyer_user = User(
            email=f"vikram.{uuid.uuid4().hex[:6]}@senlegal.com",
            password_hash="pw",
            full_name="Advocate Vikramaditya Sen"
        )
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        # Create target contract under client org
        contract = Contract(
            organization_id=client_org.id,
            contract_id=f"CTR-2026-{uuid.uuid4().hex[:4].upper()}",
            title="Cloud Infrastructure Master Services Agreement",
            contract_type="Vendor Services",
            counterparty="AWS Global Cloud Services Ltd",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        # Create matter
        matter_code = f"MAT-2026-{uuid.uuid4().hex[:4].upper()}"
        matter = LegalMatter(
            matter_code=matter_code,
            title="Review Liability Caps and Indemnity Provisions",
            matter_type="CONTRACT_REVIEW",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=lawyer_org.id,
            lawyer_user_id=lawyer_user.id,
            contract_id=contract.id,
            counterparty_name="AWS Global Cloud Services Ltd",
            preferred_time_slot="Thursday at 11:00 AM",
            client_notes="Please assess mutual indemnities and Section 14 liability ceiling."
        )
        session.add(matter)
        await session.flush()

        # 1. Verify default status
        assert matter.status == MatterStatus.SUBMITTED.value
        # 2. Verify independent conflict clearance (starts False, no certifier)
        assert matter.conflict_cleared is False
        assert matter.conflict_cleared_at is None
        assert matter.conflict_cleared_by_user_id is None
        # 3. Verify independent client consent (starts False, separate from acceptance)
        assert matter.client_consent_given is False
        assert matter.client_consent_at is None
        assert matter.client_consent_by_user_id is None

        # 4. Advance: Lawyer runs conflict check and certifies clearance
        matter.status = MatterStatus.UNDER_REVIEW.value
        matter.conflict_cleared = True
        matter.conflict_cleared_at = utc_now()
        matter.conflict_cleared_by_user_id = lawyer_user.id
        matter.conflict_notes = "Conflict check search on counterparty returned 0 adverse matters."
        await session.flush()

        assert matter.conflict_cleared is True
        assert matter.conflict_cleared_by_user_id == lawyer_user.id
        # Client consent MUST still remain False independently
        assert matter.client_consent_given is False

        # 5. Lawyer accepts inquiry
        matter.status = MatterStatus.ACCEPTED.value
        await session.flush()
        assert matter.status == "ACCEPTED"
        assert matter.client_consent_given is False

        # 6. Client provides explicit consent to share contract document
        matter.client_consent_given = True
        matter.client_consent_at = utc_now()
        matter.client_consent_by_user_id = client_user.id
        matter.status = MatterStatus.MATTER_ACTIVE.value
        await session.flush()

        assert matter.status == "MATTER_ACTIVE"
        assert matter.client_consent_given is True
        assert matter.client_consent_by_user_id == client_user.id


@pytest.mark.asyncio
async def test_legal_matter_status_validation():
    """Verify that arbitrary status strings are blocked on LegalMatter."""
    matter = LegalMatter()
    matter.status = MatterStatus.UNDER_REVIEW
    assert matter.status == "UNDER_REVIEW"

    with pytest.raises(ValueError, match="Invalid matter status"):
        matter.status = "ARBITRARY_CUSTOM_STATUS"


@pytest.mark.asyncio
async def test_matter_access_grant_activation_and_revocation(test_engine):
    """
    Test MatterAccessGrant creation, permission level enforcement,
    activation state, and revocation tracking.
    """
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Create tenant orgs & users
        client_org = Organization(name="FinTech Corp", slug=f"fintech-{uuid.uuid4().hex[:6]}")
        client_user = User(email=f"ops.{uuid.uuid4().hex[:6]}@fintech.com", password_hash="pw", full_name="Ops Lead")
        lawyer_org = Organization(name="Nair Law", slug=f"nair-{uuid.uuid4().hex[:6]}")
        lawyer_user = User(email=f"meera.{uuid.uuid4().hex[:6]}@nairlaw.com", password_hash="pw", full_name="Adv. Meera Nair")
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        contract = Contract(
            organization_id=client_org.id,
            contract_id=f"CTR-2026-{uuid.uuid4().hex[:4].upper()}",
            title="Commercial Real Estate Lease",
            contract_type="Commercial Lease",
            counterparty="Commercial Properties Ltd",
            status="ACTIVE"
        )
        session.add(contract)
        await session.flush()

        matter = LegalMatter(
            matter_code=f"MAT-2026-{uuid.uuid4().hex[:4].upper()}",
            title="Lease Termination Advisory",
            matter_type="CONTRACT_REVIEW",
            client_organization_id=client_org.id,
            client_user_id=client_user.id,
            lawyer_organization_id=lawyer_org.id,
            lawyer_user_id=lawyer_user.id,
            contract_id=contract.id,
            counterparty_name="Commercial Properties Ltd",
            status=MatterStatus.MATTER_ACTIVE.value,
            conflict_cleared=True,
            client_consent_given=True
        )
        session.add(matter)
        await session.flush()

        # 1. Issue Access Grant
        grant = MatterAccessGrant(
            matter_id=matter.id,
            contract_id=contract.id,
            lawyer_user_id=lawyer_user.id,
            permission_level=MatterPermissionLevel.REDLINE_COLLABORATIVE.value,
            is_active=True,
            granted_by_user_id=client_user.id
        )
        session.add(grant)
        await session.flush()

        assert grant.id is not None
        assert grant.is_active is True
        assert grant.permission_level == "REDLINE_COLLABORATIVE"
        assert grant.granted_at is not None
        assert grant.granted_by_user_id == client_user.id
        assert grant.revoked_at is None

        # 2. Revoke Grant upon matter completion or client withdrawal
        grant.is_active = False
        grant.revoked_at = utc_now()
        grant.revoked_by_user_id = client_user.id
        grant.revocation_reason = "Matter resolved and review concluded."
        await session.flush()

        assert grant.is_active is False
        assert grant.revoked_at is not None
        assert grant.revoked_by_user_id == client_user.id
        assert "Matter resolved" in grant.revocation_reason

        # 3. Test permission level validation
        with pytest.raises(ValueError, match="Invalid permission level"):
            grant.permission_level = "SUPERUSER_ADMIN"


@pytest.mark.asyncio
async def test_matter_message_internal_notes_and_attachments(test_engine):
    """
    Test MatterMessage distinguishes internal advocate notes from client-visible messages,
    and records attachments as metadata JSON (never raw binary bytes).
    """
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        client_org = Organization(name="SaaS Org", slug=f"saas-{uuid.uuid4().hex[:6]}")
        client_user = User(email=f"client.{uuid.uuid4().hex[:6]}@saas.com", password_hash="pw", full_name="Client Rep")
        lawyer_org = Organization(name="Advisory Chambers", slug=f"chambers-{uuid.uuid4().hex[:6]}")
        lawyer_user = User(email=f"lawyer.{uuid.uuid4().hex[:6]}@chambers.com", password_hash="pw", full_name="Counsel")
        session.add_all([client_org, client_user, lawyer_org, lawyer_user])
        await session.flush()

        matter = LegalMatter(
            matter_code=f"MAT-2026-{uuid.uuid4().hex[:4].upper()}",
            title="SaaS Redline Advisory",
            matter_type="CONTRACT_REVIEW",
            client_organization_id=client_org.id,
            lawyer_organization_id=lawyer_org.id,
            counterparty_name="Vendor Inc",
            status=MatterStatus.MATTER_ACTIVE.value
        )
        session.add(matter)
        await session.flush()

        # 1. Client-visible message from client
        client_msg = MatterMessage(
            matter_id=matter.id,
            sender_user_id=client_user.id,
            sender_type=MatterSenderType.CLIENT.value,
            message_text="We have uploaded the revised draft. Please inspect Section 8.",
            is_internal_note=False,
            attachments_json=[{
                "filename": "draft_v2.pdf",
                "storage_rel_path": "tenants/client-org/draft_v2.pdf",
                "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "size_bytes": 1048576
            }]
        )
        session.add(client_msg)

        # 2. Private chambers internal note by lawyer (invisible to client)
        internal_note = MatterMessage(
            matter_id=matter.id,
            sender_user_id=lawyer_user.id,
            sender_type=MatterSenderType.LAWYER.value,
            message_text="Internal analysis: Section 8 liability cap is enforceable under Section 73 Indian Contract Act.",
            is_internal_note=True,
            attachments_json=[]
        )
        session.add(internal_note)
        await session.flush()

        # 3. Query and verify separation
        stmt = select(MatterMessage).where(MatterMessage.matter_id == matter.id)
        res = await session.execute(stmt)
        messages = res.scalars().all()
        assert len(messages) == 2

        client_visible = [m for m in messages if not m.is_internal_note]
        internal_only = [m for m in messages if m.is_internal_note]
        assert len(client_visible) == 1
        assert len(internal_only) == 1
        assert client_visible[0].sender_type == "CLIENT"
        assert internal_only[0].sender_type == "LAWYER"
        assert client_visible[0].attachments_json[0]["filename"] == "draft_v2.pdf"


@pytest.mark.asyncio
async def test_lawyer_availability_schedule(test_engine):
    """Test LawyerAvailability working hours slots."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        org = Organization(name="Legal Firm", slug=f"firm-{uuid.uuid4().hex[:6]}")
        user = User(email=f"advocate.{uuid.uuid4().hex[:6]}@firm.com", password_hash="pw", full_name="Advocate")
        session.add_all([org, user])
        await session.flush()

        profile = LawyerProfile(
            user_id=user.id,
            organization_id=org.id,
            bar_council_number=f"MH/{uuid.uuid4().hex[:4].upper()}/2018",
            state_bar_council="Bar Council of Maharashtra & Goa",
            admitted_jurisdictions="Bombay High Court",
            practice_areas=["Commercial Real Estate"],
        )
        session.add(profile)
        await session.flush()

        slot_mon = LawyerAvailability(
            lawyer_profile_id=profile.id,
            day_of_week=0,  # Monday
            start_time="10:00",
            end_time="16:00",
            slot_duration_minutes=45,
            is_active=True
        )
        session.add(slot_mon)
        await session.flush()

        assert slot_mon.id is not None
        assert slot_mon.day_of_week == 0
        assert slot_mon.slot_duration_minutes == 45
