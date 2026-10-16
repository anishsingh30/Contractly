import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.dependencies import (
    get_current_active_user,
    get_current_tenant,
    get_current_platform_user,
)
from app.models.user import User
from app.models.organization import Organization
from app.models.audit import AuditLog
from app.models.base import generate_uuid, utc_now
from app.models.lawyer import (
    LawyerProfile,
    LegalMatter,
    MatterMessage,
    MatterSenderType,
    LawyerVerificationStatus,
    MatterStatus,
)
from app.schemas.lawyer import (
    LawyerInquiryRequest,
    LawyerInquiryResponse,
    LawyerProfileResponse,
    LawyerProfileUpdateRequest,
    LawyerVerificationDecisionRequest,
)
from app.services.notifications.matter_notifications import create_matter_message_notification


router = APIRouter(prefix="/lawyers", tags=["Lawyers & Consultation Inquiries"])


# ============================================================================
# Public & Client Advocate Directory
# ============================================================================

@router.get("/directory", response_model=List[LawyerProfileResponse])
async def list_verified_lawyers_directory(
    practice_area: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns public verified legal advocates for consultation inquiry booking.
    Safeguards:
    - ONLY advocates with verification_status='VERIFIED', is_published=True,
      and is_available_for_inquiries=True are returned.
    - Private contact details (email, phone, internal notes, credential docs)
      are NEVER included in the response.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(
            LawyerProfile.verification_status == LawyerVerificationStatus.VERIFIED.value,
            LawyerProfile.is_published == True,
            LawyerProfile.is_available_for_inquiries == True
        )
        .order_by(LawyerProfile.experience_years.desc())
    )

    try:
        res = await db.execute(stmt)
        profiles = res.scalars().all()
    except Exception as e:
        logger.error(f"Database error querying lawyer directory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lawyer directory service temporarily unavailable. Please retry shortly."
        )

    results = []
    for p in profiles:
        if practice_area and practice_area.upper() != "ALL":
            clean_pa = practice_area.lower().strip()
            areas = [str(a).lower() for a in (p.practice_areas or [])]
            if not any(clean_pa in a for a in areas):
                continue

        results.append(
            LawyerProfileResponse(
                id=p.id,
                user_id=p.user_id,
                full_name=p.user.full_name if p.user else "Advocate",
                professional_title=p.professional_title or "Advocate",
                firm_name=p.organization.name if p.organization else "Legal Chambers",
                organization_id=p.organization_id,
                bar_council_number=p.bar_council_number,
                state_bar_council=p.state_bar_council,
                admitted_jurisdictions=p.admitted_jurisdictions,
                practice_areas=p.practice_areas or [],
                qualifications=p.qualifications or [],
                languages=p.languages or [],
                experience_years=p.experience_years,
                consultation_fee=p.consultation_fee or "INR 0",
                consultation_duration_minutes=p.consultation_duration_minutes or 30,
                bio=p.bio,
                is_available_for_inquiries=p.is_available_for_inquiries,
                verification_status=p.verification_status,
                verified_at=p.verified_at
            )
        )

    return results


@router.get("/{lawyer_id}/public", response_model=LawyerProfileResponse)
async def get_public_lawyer_profile(
    lawyer_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns public profile of a verified, published advocate.
    Raises generic 404 if unverified, unpublished, or not found.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(
            LawyerProfile.id == lawyer_id,
            LawyerProfile.verification_status == LawyerVerificationStatus.VERIFIED.value,
            LawyerProfile.is_published.is_(True)
        )
    )
    res = await db.execute(stmt)
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verified lawyer profile not found."
        )

    return LawyerProfileResponse(
        id=p.id,
        user_id=p.user_id,
        full_name=p.user.full_name if p.user else "Advocate",
        professional_title=p.professional_title or "Advocate",
        firm_name=p.organization.name if p.organization else "Legal Chambers",
        organization_id=p.organization_id,
        bar_council_number=p.bar_council_number,
        state_bar_council=p.state_bar_council,
        admitted_jurisdictions=p.admitted_jurisdictions,
        practice_areas=p.practice_areas or [],
        qualifications=p.qualifications or [],
        languages=p.languages or [],
        experience_years=p.experience_years,
        consultation_fee=p.consultation_fee or "INR 0",
        consultation_duration_minutes=p.consultation_duration_minutes or 30,
        bio=p.bio,
        is_available_for_inquiries=p.is_available_for_inquiries,
        verification_status=p.verification_status,
        verified_at=p.verified_at
    )


# ============================================================================
# Lawyer Profile Self-Management
# ============================================================================

@router.get("/profile", response_model=LawyerProfileResponse)
async def get_my_lawyer_profile(
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Returns the authenticated lawyer's own advocate profile."""
    if tenant.account_type != "LEGAL_PROFESSIONAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Advocate profile is only accessible to legal professional workspace accounts."
        )

    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lawyer profile not yet initialized. Please complete onboarding."
        )

    return LawyerProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        full_name=current_user.full_name,
        firm_name=tenant.name,
        organization_id=tenant.id,
        bar_council_number=profile.bar_council_number,
        state_bar_council=profile.state_bar_council,
        admitted_jurisdictions=profile.admitted_jurisdictions,
        practice_areas=profile.practice_areas or [],
        experience_years=profile.experience_years,
        consultation_fee=profile.consultation_fee,
        bio=profile.bio,
        is_available_for_inquiries=profile.is_available_for_inquiries,
        verification_status=profile.verification_status,
        verified_at=profile.verified_at
    )


@router.put("/profile", response_model=LawyerProfileResponse)
async def update_my_lawyer_profile(
    req: LawyerProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the authenticated lawyer's own chambers information.
    Safeguard: verification_status cannot be modified through this endpoint.
    """
    if tenant.account_type != "LEGAL_PROFESSIONAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Advocate profile updates are restricted to legal professional accounts."
        )

    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lawyer profile not found."
        )

    if req.state_bar_council is not None:
        profile.state_bar_council = req.state_bar_council.strip()
    if req.admitted_jurisdictions is not None:
        profile.admitted_jurisdictions = req.admitted_jurisdictions.strip()
    if req.practice_areas is not None:
        profile.practice_areas = req.practice_areas
    if req.experience_years is not None:
        profile.experience_years = req.experience_years
    if req.consultation_fee is not None:
        profile.consultation_fee = req.consultation_fee.strip()
    if req.bio is not None:
        profile.bio = req.bio.strip()
    if req.is_available_for_inquiries is not None:
        profile.is_available_for_inquiries = req.is_available_for_inquiries

    if req.firm_name is not None and req.firm_name.strip():
        tenant.name = req.firm_name.strip()

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="LAWYER_PROFILE_UPDATED",
        object_type="LawyerProfile",
        object_id=profile.id,
        detail="Advocate updated chambers profile and practice details."
    )
    db.add(audit)
    await db.commit()

    return LawyerProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        full_name=current_user.full_name,
        firm_name=tenant.name,
        organization_id=tenant.id,
        bar_council_number=profile.bar_council_number,
        state_bar_council=profile.state_bar_council,
        admitted_jurisdictions=profile.admitted_jurisdictions,
        practice_areas=profile.practice_areas or [],
        experience_years=profile.experience_years,
        consultation_fee=profile.consultation_fee,
        bio=profile.bio,
        is_available_for_inquiries=profile.is_available_for_inquiries,
        verification_status=profile.verification_status,
        verified_at=profile.verified_at
    )


# ============================================================================
# Platform Admin Credential Verification
# ============================================================================

@router.post("/profiles/{profile_id}/verify", response_model=LawyerProfileResponse)
async def verify_lawyer_credentials(
    profile_id: str,
    req: LawyerVerificationDecisionRequest,
    admin_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Platform Super Admin verifies or rejects an advocate's Bar Council credentials.
    Safeguards:
    - Requires active platform administrator role.
    - Emits an immutable audit log.
    - Unverified lawyers cannot receive client inquiries.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.id == profile_id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lawyer profile not found."
        )

    decision = req.decision.upper()
    if decision == "VERIFY":
        profile.verification_status = LawyerVerificationStatus.VERIFIED.value
        profile.verified_at = utc_now()
        profile.verified_by_user_id = admin_user.id
        profile.rejection_reason = None
        profile.is_published = True
        action = "LAWYER_CREDENTIALS_VERIFIED"
        audit_detail = f"Platform admin verified Bar Council ID {profile.bar_council_number}."
    else:
        profile.verification_status = LawyerVerificationStatus.REJECTED.value
        profile.rejection_reason = req.reason
        profile.is_published = False
        action = "LAWYER_CREDENTIALS_REJECTED"
        audit_detail = f"Platform admin rejected Bar Council ID {profile.bar_council_number}. Reason: {req.reason or 'Unspecified'}."

    audit = AuditLog(
        organization_id=profile.organization_id,
        user_email=admin_user.email,
        action=action,
        object_type="LawyerProfile",
        object_id=profile.id,
        detail=audit_detail
    )
    db.add(audit)
    await db.commit()

    return LawyerProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.user.full_name if profile.user else "Advocate",
        professional_title=profile.professional_title or "Advocate",
        firm_name=profile.organization.name if profile.organization else "",
        organization_id=profile.organization_id,
        bar_council_number=profile.bar_council_number,
        state_bar_council=profile.state_bar_council,
        admitted_jurisdictions=profile.admitted_jurisdictions,
        practice_areas=profile.practice_areas or [],
        qualifications=profile.qualifications or [],
        languages=profile.languages or [],
        experience_years=profile.experience_years,
        consultation_fee=profile.consultation_fee or "INR 0",
        consultation_duration_minutes=profile.consultation_duration_minutes or 30,
        bio=profile.bio,
        is_available_for_inquiries=profile.is_available_for_inquiries,
        verification_status=profile.verification_status,
        verified_at=profile.verified_at
    )


# ============================================================================
# Legacy Consultation Inquiry Intake (Preserved & Enhanced)
# ============================================================================

@router.post("/inquiries", response_model=LawyerInquiryResponse, status_code=status.HTTP_201_CREATED)
async def submit_lawyer_inquiry(
    req: LawyerInquiryRequest,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a consultation inquiry.
    Persists a genuine LegalMatter and initial MatterMessage into the database,
    places the request into SUBMITTED (Pending Approval) status, and emits dual audit logs.
    Includes idempotency safeguards against duplicate clicks or page refreshes.
    """
    # 1. Resolve and verify target advocate
    stmt_lawyer = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.organization), selectinload(LawyerProfile.user))
        .where(or_(LawyerProfile.id == req.lawyer_id, LawyerProfile.user_id == req.lawyer_id))
    )
    res_lawyer = await db.execute(stmt_lawyer)
    lawyer_prof = res_lawyer.scalar_one_or_none()

    if not lawyer_prof:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Designated legal advocate profile not found."
        )

    if lawyer_prof.verification_status != LawyerVerificationStatus.VERIFIED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Designated legal advocate is not currently verified to accept client inquiries."
        )

    if not lawyer_prof.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Designated legal advocate profile is not currently published."
        )

    if not lawyer_prof.is_available_for_inquiries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Designated legal advocate is currently not accepting new consultation inquiries."
        )

    # 2. Prevent lawyer from submitting inquiries to themselves or their own practice
    if lawyer_prof.organization_id == tenant.id or lawyer_prof.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit an external consultation inquiry to your own practice organization."
        )

    # 3. Extract title, counterparty, and initial message from client_notes
    notes_text = (req.client_notes or "").strip()
    extracted_title = req.title or f"Consultation with {lawyer_prof.user.full_name if lawyer_prof.user else 'Advocate'}"
    extracted_counterparty = req.counterparty_name or "Unspecified Counterparty"
    initial_message = notes_text

    if "Subject: " in notes_text and not req.title:
        try:
            part = notes_text.split("Subject: ", 1)[1]
            extracted_title = part.split("\n", 1)[0].strip() or extracted_title
        except Exception:
            pass

    if "Counterparty for conflict check: " in notes_text and not req.counterparty_name:
        try:
            part = notes_text.split("Counterparty for conflict check: ", 1)[1]
            extracted_counterparty = part.split("\n", 1)[0].strip() or extracted_counterparty
        except Exception:
            pass

    # 4. Idempotency Check: Prevent duplicate requests when user clicks repeatedly
    recent_cutoff = utc_now() - timedelta(minutes=10)
    existing_stmt = select(LegalMatter).where(
        LegalMatter.client_organization_id == tenant.id,
        LegalMatter.client_user_id == current_user.id,
        LegalMatter.lawyer_user_id == lawyer_prof.user_id,
        LegalMatter.title == extracted_title,
        LegalMatter.status.in_([MatterStatus.SUBMITTED.value, MatterStatus.UNDER_REVIEW.value, MatterStatus.ACCEPTED.value]),
        LegalMatter.created_at >= recent_cutoff
    )
    existing_res = await db.execute(existing_stmt)
    existing_matter = existing_res.scalar_one_or_none()
    if existing_matter:
        is_pending = existing_matter.status in (MatterStatus.SUBMITTED.value, MatterStatus.UNDER_REVIEW.value)
        lawyer_disp_name = req.lawyer_name or (lawyer_prof.user.full_name if lawyer_prof.user else "Assigned Counsel")
        slot_disp = existing_matter.preferred_time_slot or req.preferred_time_slot or "Next Available Slot"
        return LawyerInquiryResponse(
            inquiry_id=existing_matter.matter_code,
            status="PENDING_APPROVAL" if is_pending else "APPROVED",
            lawyer_name=lawyer_disp_name,
            preferred_time_slot=slot_disp,
            message=f"Existing consultation request {existing_matter.matter_code} for {lawyer_disp_name} is already registered.",
            limitations_notice=(
                "Notice: Inquiries are submitted for administrative review and conflict clearance. "
                "Active conversation messaging will become available once approved."
            ),
            matter_id=existing_matter.id,
            inquiry_reference=existing_matter.matter_code,
            success=True,
        )

    # 5. Persist genuine LegalMatter
    matter_code = f"MAT-{utc_now().strftime('%Y')}-{generate_uuid()[:6].upper()}"
    new_matter = LegalMatter(
        matter_code=matter_code,
        title=extracted_title,
        matter_type="CONSULTATION",
        client_organization_id=tenant.id,
        client_user_id=current_user.id,
        lawyer_organization_id=lawyer_prof.organization_id,
        lawyer_user_id=lawyer_prof.user_id,
        counterparty_name=extracted_counterparty,
        status=MatterStatus.SUBMITTED.value,
        conflict_cleared=False,
        client_consent_given=False,
        preferred_time_slot=req.preferred_time_slot or "Next Available Slot",
        client_notes=notes_text
    )
    db.add(new_matter)
    await db.flush()

    # 6. Persist initial message in MatterMessage
    msg_body = initial_message or f"Consultation inquiry submitted for {req.preferred_time_slot or 'Next Available Slot'}."
    init_msg = MatterMessage(
        matter_id=new_matter.id,
        sender_user_id=current_user.id,
        sender_type=MatterSenderType.CLIENT.value,
        message_text=msg_body,
        is_internal_note=False,
        attachments_json=[]
    )
    db.add(init_msg)
    await db.flush()
    await create_matter_message_notification(db, new_matter, init_msg, current_user)

    # 7. Audit Logging
    audit_client = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="LAWYER_CONSULTATION_INQUIRY_SUBMITTED",
        object_type="LegalMatter",
        object_id=new_matter.id,
        detail=f"Consultation inquiry {matter_code} submitted for {lawyer_prof.user.full_name if lawyer_prof.user else 'Advocate'} ({req.preferred_time_slot or 'Next Available Slot'})."
    )
    audit_platform = AuditLog(
        organization_id=None,
        user_email=current_user.email,
        action="PLATFORM_CONSULTATION_REQUEST_CREATED",
        object_type="LegalMatter",
        object_id=new_matter.id,
        detail=f"New consultation request {matter_code} submitted by {current_user.email} for advocate {lawyer_prof.bar_council_number}."
    )
    db.add(audit_client)
    db.add(audit_platform)
    await db.commit()

    lawyer_disp_name = req.lawyer_name or (lawyer_prof.user.full_name if lawyer_prof.user else "Assigned Counsel")
    slot_disp = req.preferred_time_slot or "Next Available Slot"
    return LawyerInquiryResponse(
        inquiry_id=matter_code,
        status="PENDING_APPROVAL",
        lawyer_name=lawyer_disp_name,
        preferred_time_slot=slot_disp,
        message=f"Consultation inquiry {matter_code} for {lawyer_disp_name} has been submitted for platform review.",
        limitations_notice=(
            "Notice: Inquiries are submitted to legal operations to verify conflicts and attorney availability. "
            "Messaging will become active once approved by administration."
        ),
        matter_id=new_matter.id,
        inquiry_reference=matter_code,
        success=True,
    )
