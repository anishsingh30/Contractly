import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.config import settings
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractVersion
from app.models.audit import AuditLog
from app.models.lawyer import LegalMatter, MatterMessage, LawyerProfile, MatterStatus, MatterDeclineReason
from app.schemas.lawyer import (
    AdminConversationItem,
    AdminConversationReviewPayload,
    AdminConversationReviewResponse,
    AdminConversationNotePayload,
    MatterMessageResponse,
    AdminConsultationRequestItem,
    AdminConsultationDecisionPayload,
)
from app.dependencies import get_current_platform_user, require_platform_permission
from app.core.permissions import (
    PLATFORM_PERM_SYSTEM_READ,
    PLATFORM_PERM_METRICS_READ,
    PLATFORM_PERM_TENANTS_READ,
    PLATFORM_PERM_AUDIT_READ,
    PLATFORM_PERM_SYSTEM_MANAGE,
    PLATFORM_PERM_CONVERSATIONS_OVERSIGHT,
)

router = APIRouter(prefix="/platform", tags=["Platform Administration"])


@router.get("/health")
async def get_platform_health(
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_SYSTEM_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Operational system health status for platform administrators.
    Never exposes customer contract contents, private documents, or secret credentials.
    """
    db_status = "HEALTHY"
    try:
        await db.execute(select(1))
    except Exception:
        db_status = "DEGRADED"

    from app.services.email.provider import get_email_service_health
    from app.core.rate_limiter import get_rate_limiter_health

    return {
        "status": "OPERATIONAL" if db_status == "HEALTHY" else "DEGRADED",
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": db_status,
            "engine": "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite",
            "readiness": "ready",
        },
        "storage": {
            "provider": settings.STORAGE_PROVIDER,
            "status": "CONFIGURED",
        },
        "scheduler": {
            "enabled": settings.NOTIFICATION_SCHEDULER_ENABLED,
            "interval_hours": settings.NOTIFICATION_SCHEDULER_INTERVAL_HOURS,
        },
        "email": get_email_service_health(),
        "rate_limiter": get_rate_limiter_health(),
        "audited_by_user": current_platform_user.email,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
async def get_platform_aggregate_metrics(
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_METRICS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregate operational statistics across all customer organizations.
    Strict privacy guarantee: Only numerical aggregate metrics are provided.
    Contract titles, body text, uploaded files, and clause data are NEVER returned.
    """
    # 1. Total Tenants
    orgs_count_res = await db.execute(select(func.count(Organization.id)))
    total_tenants = orgs_count_res.scalar() or 0

    # 2. Total Users
    users_count_res = await db.execute(select(func.count(User.id)))
    total_users = users_count_res.scalar() or 0

    # 3. Aggregate Contract and Version Counts (Pure counts, zero content)
    contracts_count_res = await db.execute(select(func.count(Contract.id)))
    total_contracts = contracts_count_res.scalar() or 0

    versions_count_res = await db.execute(select(func.count(ContractVersion.id)))
    total_versions = versions_count_res.scalar() or 0

    # 4. Storage Quotas
    quota_res = await db.execute(select(func.sum(Organization.storage_quota_bytes)))
    total_allocated_quota_bytes = quota_res.scalar() or 0

    # 5. Advocate counts (graceful fallback if schema does not include lawyer_profiles)
    advocates_count = 0
    pending_advocates_count = 0
    verified_advocates_count = 0
    try:
        from app.models.lawyer import LawyerProfile, LawyerVerificationStatus
        tot_adv_res = await db.execute(select(func.count(LawyerProfile.id)))
        advocates_count = tot_adv_res.scalar() or 0
        pend_adv_res = await db.execute(
            select(func.count(LawyerProfile.id)).where(LawyerProfile.verification_status == LawyerVerificationStatus.PENDING_REVIEW.value)
        )
        pending_advocates_count = pend_adv_res.scalar() or 0
        ver_adv_res = await db.execute(
            select(func.count(LawyerProfile.id)).where(LawyerProfile.verification_status == LawyerVerificationStatus.VERIFIED.value)
        )
        verified_advocates_count = ver_adv_res.scalar() or 0
    except Exception as e:
        logger.warning(f"Advocate metrics unavailable in current database schema: {e}")

    # 6. Legal Matter counts by status (graceful fallback if schema does not include legal_matters)
    matters_by_status = {}
    try:
        from app.models.lawyer import LegalMatter
        m_stmt = select(LegalMatter.status, func.count(LegalMatter.id)).group_by(LegalMatter.status)
        m_res = await db.execute(m_stmt)
        for st, count in m_res.all():
            matters_by_status[st] = count
    except Exception as e:
        logger.warning(f"Matter metrics unavailable in current database schema: {e}")

    # Record platform audit activity
    audit = AuditLog(
        organization_id=None,  # Platform level
        user_email=current_platform_user.email,
        action="PLATFORM_METRICS_VIEWED",
        object_type="PlatformMetrics",
        object_id="system",
        detail="Platform administrator inspected aggregate system operational metrics.",
    )
    db.add(audit)
    await db.commit()

    return {
        "tenants_count": total_tenants,
        "users_count": total_users,
        "total_contracts_count": total_contracts,
        "total_contract_versions_count": total_versions,
        "allocated_storage_quota_bytes": total_allocated_quota_bytes,
        "advocates_count": advocates_count,
        "pending_advocates_count": pending_advocates_count,
        "verified_advocates_count": verified_advocates_count,
        "matters_by_status": matters_by_status,
        "privacy_notice": "Customer contracts, clause texts, and document contents are strictly excluded from platform metrics.",
    }


@router.get("/tenants")
async def list_platform_tenants(
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_TENANTS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists tenant organizations with operational account metadata.
    Enforces least privilege:
    - Returns organization account IDs, names, subscription tiers, and member/contract counts.
    - NEVER returns contract titles, text, uploaded files, or customer AI prompts.
    """
    stmt = select(Organization).order_by(Organization.created_at.desc())
    res = await db.execute(stmt)
    orgs = res.scalars().all()

    tenant_items = []
    for org in orgs:
        # Get member count
        m_count_res = await db.execute(
            select(func.count(OrganizationMember.id)).where(OrganizationMember.organization_id == org.id)
        )
        member_count = m_count_res.scalar() or 0

        # Get contract count
        c_count_res = await db.execute(
            select(func.count(Contract.id)).where(Contract.organization_id == org.id)
        )
        contract_count = c_count_res.scalar() or 0

        tenant_items.append({
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "account_type": org.account_type,
            "subscription_tier": org.subscription_tier,
            "storage_quota_bytes": org.storage_quota_bytes,
            "created_at": org.created_at.isoformat() if org.created_at else None,
            "member_count": member_count,
            "contract_count": contract_count,
        })

    # Record platform audit
    audit = AuditLog(
        organization_id=None,
        user_email=current_platform_user.email,
        action="PLATFORM_TENANTS_LIST_VIEWED",
        object_type="PlatformTenants",
        object_id="all",
        detail=f"Platform administrator viewed tenant organization directory ({len(tenant_items)} tenants).",
    )
    db.add(audit)
    await db.commit()

    return tenant_items


@router.get("/audit-logs")
async def list_platform_audit_logs(
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists platform-level operational administrative audit records.
    Records privileged platform actions without leaking customer data.
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id.is_(None))
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    return [
        {
            "id": log.id,
            "user_email": log.user_email,
            "action": log.action,
            "object_type": log.object_type,
            "object_id": log.object_id,
            "detail": log.detail,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/support-access/status")
async def get_support_access_status(
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Discloses the current customer-content support access policy.
    Pursuant to Phase 4A security constraints, routine support impersonation
    and backdoor master access to customer contracts are disabled.
    """
    return {
        "customer_content_support_access_enabled": False,
        "policy": "DISABLED_BY_DEFAULT",
        "description": (
            "Customer contracts and documents are strictly confidential. Universal administrative "
            "backdoors, master tenant impersonation, and unvetted content inspection are permanently "
            "prohibited in application routes."
        ),
        "exceptional_access_requirements": [
            "Explicit Customer Organization Owner approval required",
            "Documented, verifiable justification with ticket ID",
            "Narrowly scoped to a single contract or issue",
            "Maximum 2-hour enforced hard expiration",
            "Full tamper-evident audit logging of all read operations",
            "Instant revocation capability by customer Owner",
        ],
        "audited_by": current_platform_user.email,
    }


@router.get("/advocates")
async def list_platform_advocates(
    status: Optional[str] = None,
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_TENANTS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists advocate profiles and applications with Bar Council credential details.
    Allows platform administrators to inspect and verify advocate applications.
    """
    try:
        from app.models.lawyer import LawyerProfile
        stmt = (
            select(LawyerProfile)
            .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
            .order_by(LawyerProfile.created_at.desc())
        )
        if status:
            stmt = stmt.where(LawyerProfile.verification_status == status.upper())
        res = await db.execute(stmt)
        profiles = res.scalars().all()

        advocate_items = []
        for p in profiles:
            advocate_items.append({
                "id": p.id,
                "user_id": p.user_id,
                "full_name": p.user.full_name if p.user else "Advocate",
                "email": p.user.email if p.user else "",
                "phone_number": p.phone_number,
                "organization_id": p.organization_id,
                "firm_name": p.organization.name if p.organization else "",
                "professional_title": p.professional_title or "Advocate",
                "bar_council_number": p.bar_council_number,
                "state_bar_council": p.state_bar_council,
                "admitted_jurisdictions": p.admitted_jurisdictions,
                "practice_areas": p.practice_areas or [],
                "qualifications": p.qualifications or [],
                "languages": p.languages or [],
                "experience_years": p.experience_years,
                "consultation_fee": p.consultation_fee or "INR 0",
                "consultation_duration_minutes": p.consultation_duration_minutes or 30,
                "bio": p.bio,
                "internal_notes": p.internal_notes,
                "credential_documents": p.credential_documents or [],
                "is_published": p.is_published,
                "is_available_for_inquiries": p.is_available_for_inquiries,
                "verification_status": p.verification_status,
                "verified_at": p.verified_at.isoformat() if p.verified_at else None,
                "verified_by_user_id": p.verified_by_user_id,
                "rejection_reason": p.rejection_reason,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            })
        return advocate_items
    except Exception as e:
        logger.warning(f"Advocates table unavailable in current database schema: {e}")
        return []


# ============================================================================
# Dedicated Platform Admin Lawyer Management CRUD & Verification Lifecycle
# ============================================================================

from app.models.lawyer import LawyerProfile, LawyerVerificationStatus
from app.schemas.lawyer import (
    AdminLawyerProfileResponse,
    AdminLawyerCreateRequest,
    AdminLawyerUpdateRequest,
    AdminLawyerPublishRequest,
    AdminLawyerAvailabilityRequest,
    LawyerVerificationDecisionRequest,
)
from app.core.security import get_password_hash
from app.models.base import utc_now, generate_uuid


def _serialize_admin_lawyer_profile(p: LawyerProfile) -> AdminLawyerProfileResponse:
    return AdminLawyerProfileResponse(
        id=p.id,
        user_id=p.user_id,
        full_name=p.user.full_name if p.user else "Advocate",
        email=p.user.email if p.user else "",
        phone_number=p.phone_number,
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
        internal_notes=p.internal_notes,
        credential_documents=p.credential_documents or [],
        is_published=p.is_published,
        is_available_for_inquiries=p.is_available_for_inquiries,
        verification_status=p.verification_status,
        verified_at=p.verified_at,
        verified_by_user_id=p.verified_by_user_id,
        rejection_reason=p.rejection_reason,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/lawyers", response_model=List[AdminLawyerProfileResponse])
async def list_admin_lawyers(
    search: Optional[str] = None,
    practice_area: Optional[str] = None,
    verification_status: Optional[str] = None,
    is_published: Optional[bool] = None,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists lawyer profiles with administrative verification details and private contact fields.
    Restricted strictly to Platform Super Admins.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .order_by(LawyerProfile.created_at.desc())
    )

    if verification_status and verification_status.upper() != "ALL":
        stmt = stmt.where(LawyerProfile.verification_status == verification_status.upper())
    if is_published is not None:
        stmt = stmt.where(LawyerProfile.is_published == is_published)

    res = await db.execute(stmt)
    profiles = res.scalars().all()

    results = []
    for p in profiles:
        if practice_area and practice_area.upper() != "ALL":
            clean_pa = practice_area.lower().strip()
            areas = [str(a).lower() for a in (p.practice_areas or [])]
            if not any(clean_pa in a for a in areas):
                continue

        if search and search.strip():
            clean_q = search.lower().strip()
            u_name = (p.user.full_name if p.user else "").lower()
            u_email = (p.user.email if p.user else "").lower()
            org_name = (p.organization.name if p.organization else "").lower()
            bc_num = (p.bar_council_number or "").lower()
            if not (clean_q in u_name or clean_q in u_email or clean_q in org_name or clean_q in bc_num):
                continue

        results.append(_serialize_admin_lawyer_profile(p))

    return results


@router.post("/lawyers", response_model=AdminLawyerProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_lawyer(
    req: AdminLawyerCreateRequest,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Platform Admin adds a new legal advocate profile and initializes their workspace account.
    Restricted strictly to Platform Super Admins.
    """
    # 1. Check Bar Council number uniqueness
    bc_stmt = select(LawyerProfile).where(LawyerProfile.bar_council_number == req.bar_council_number.strip())
    bc_res = await db.execute(bc_stmt)
    if bc_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lawyer profile with Bar Council number '{req.bar_council_number}' already exists."
        )

    # 2. Check or create User
    email_clean = req.email.strip().lower()
    u_stmt = select(User).where(User.email == email_clean)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user:
        user = User(
            email=email_clean,
            password_hash=get_password_hash("AdvocateWelcome123!"),
            full_name=req.full_name.strip(),
            is_active=True,
            is_super_admin=False,
        )
        db.add(user)
        await db.flush()
    else:
        # Check if user already has a lawyer profile
        ex_stmt = select(LawyerProfile).where(LawyerProfile.user_id == user.id)
        ex_res = await db.execute(ex_stmt)
        if ex_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{email_clean}' is already linked to an existing lawyer profile."
            )

    # 3. Create or resolve Legal Organization
    firm_name = req.firm_name.strip() if req.firm_name and req.firm_name.strip() else f"{req.full_name.strip()} Chambers"
    slug_base = firm_name.lower().replace(" ", "-").replace("&", "and")
    org_slug = f"chambers-{generate_uuid()[:6]}-{slug_base[:30]}"

    org = Organization(
        name=firm_name,
        slug=org_slug,
        account_type="LEGAL_PROFESSIONAL",
        subscription_tier="COMMUNITY",
    )
    db.add(org)
    await db.flush()

    # 4. Create OrganizationMember
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="LEGAL_MANAGER",
        status="ACTIVE",
    )
    db.add(membership)
    await db.flush()

    # 5. Create LawyerProfile
    profile = LawyerProfile(
        user_id=user.id,
        organization_id=org.id,
        bar_council_number=req.bar_council_number.strip(),
        state_bar_council=req.state_bar_council.strip(),
        admitted_jurisdictions=req.admitted_jurisdictions.strip(),
        practice_areas=req.practice_areas or [],
        qualifications=req.qualifications or [],
        languages=req.languages or [],
        experience_years=req.experience_years,
        consultation_fee=req.consultation_fee.strip() if req.consultation_fee else "INR 0",
        consultation_duration_minutes=req.consultation_duration_minutes or 30,
        bio=req.bio.strip() if req.bio else None,
        professional_title=req.professional_title.strip() if req.professional_title else "Advocate",
        phone_number=req.phone_number.strip() if req.phone_number else None,
        internal_notes=req.internal_notes.strip() if req.internal_notes else None,
        is_available_for_inquiries=req.is_available_for_inquiries,
        is_published=False,  # Unverified profiles must never start published
        verification_status=LawyerVerificationStatus.PENDING_REVIEW.value,
    )
    db.add(profile)
    await db.flush()

    # 6. Audit Logging
    audit = AuditLog(
        organization_id=None,
        user_email=current_platform_user.email,
        action="LAWYER_PROFILE_CREATED",
        object_type="LawyerProfile",
        object_id=profile.id,
        detail=f"Platform admin registered advocate {req.full_name} (Bar ID: {req.bar_council_number}).",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(profile)
    await db.refresh(user)
    await db.refresh(org)

    return _serialize_admin_lawyer_profile(profile)


@router.get("/lawyers/{lawyer_id}", response_model=AdminLawyerProfileResponse)
async def get_admin_lawyer(
    lawyer_id: str,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns single lawyer profile with private details for Platform Admin."""
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.id == lawyer_id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")

    return _serialize_admin_lawyer_profile(profile)


@router.put("/lawyers/{lawyer_id}", response_model=AdminLawyerProfileResponse)
async def update_admin_lawyer(
    lawyer_id: str,
    req: AdminLawyerUpdateRequest,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Platform Admin edits an existing advocate's profile and credentials.
    Safeguard: Cannot set is_published=True if verification_status != 'VERIFIED'.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.id == lawyer_id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")

    # Guard: publication check
    if req.is_published is True and profile.verification_status != LawyerVerificationStatus.VERIFIED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish unverified lawyer profile. Bar Council credentials must be verified first."
        )

    # Update User fields
    if req.full_name is not None and profile.user:
        profile.user.full_name = req.full_name.strip()
    if req.email is not None and profile.user:
        profile.user.email = req.email.strip().lower()

    # Update Organization firm name
    if req.firm_name is not None and profile.organization:
        profile.organization.name = req.firm_name.strip()

    # Update Profile fields
    if req.professional_title is not None:
        profile.professional_title = req.professional_title.strip()
    if req.bar_council_number is not None:
        profile.bar_council_number = req.bar_council_number.strip()
    if req.state_bar_council is not None:
        profile.state_bar_council = req.state_bar_council.strip()
    if req.admitted_jurisdictions is not None:
        profile.admitted_jurisdictions = req.admitted_jurisdictions.strip()
    if req.practice_areas is not None:
        profile.practice_areas = req.practice_areas
    if req.qualifications is not None:
        profile.qualifications = req.qualifications
    if req.languages is not None:
        profile.languages = req.languages
    if req.experience_years is not None:
        profile.experience_years = req.experience_years
    if req.consultation_fee is not None:
        profile.consultation_fee = req.consultation_fee.strip()
    if req.consultation_duration_minutes is not None:
        profile.consultation_duration_minutes = req.consultation_duration_minutes
    if req.bio is not None:
        profile.bio = req.bio.strip()
    if req.phone_number is not None:
        profile.phone_number = req.phone_number.strip()
    if req.internal_notes is not None:
        profile.internal_notes = req.internal_notes.strip()
    if req.is_available_for_inquiries is not None:
        profile.is_available_for_inquiries = req.is_available_for_inquiries
    if req.is_published is not None:
        profile.is_published = req.is_published

    profile.updated_at = utc_now()

    audit = AuditLog(
        organization_id=None,
        user_email=current_platform_user.email,
        action="LAWYER_PROFILE_UPDATED",
        object_type="LawyerProfile",
        object_id=profile.id,
        detail=f"Platform admin updated advocate profile for {profile.user.full_name if profile.user else profile.id}.",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(profile)

    return _serialize_admin_lawyer_profile(profile)


@router.post("/lawyers/{lawyer_id}/verify", response_model=AdminLawyerProfileResponse)
async def verify_admin_lawyer(
    lawyer_id: str,
    req: LawyerVerificationDecisionRequest,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Platform Admin verifies or rejects an advocate's submitted credentials.
    If rejected, automatically unpublishes the profile.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.id == lawyer_id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")

    decision = req.decision.upper()
    if decision == "VERIFY":
        profile.verification_status = LawyerVerificationStatus.VERIFIED.value
        profile.verified_at = utc_now()
        profile.verified_by_user_id = current_platform_user.id
        profile.rejection_reason = None
        action = "LAWYER_CREDENTIALS_VERIFIED"
        audit_detail = f"Platform admin verified Bar Council ID {profile.bar_council_number}."
    else:
        profile.verification_status = LawyerVerificationStatus.REJECTED.value
        profile.rejection_reason = req.reason or "Credentials rejected by platform administrator."
        profile.is_published = False
        action = "LAWYER_CREDENTIALS_REJECTED"
        audit_detail = f"Platform admin rejected Bar Council ID {profile.bar_council_number}. Reason: {profile.rejection_reason}."

    profile.updated_at = utc_now()

    audit = AuditLog(
        organization_id=None,
        user_email=current_platform_user.email,
        action=action,
        object_type="LawyerProfile",
        object_id=profile.id,
        detail=audit_detail,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(profile)

    return _serialize_admin_lawyer_profile(profile)


@router.post("/lawyers/{lawyer_id}/publish", response_model=AdminLawyerProfileResponse)
async def set_admin_lawyer_publish_status(
    lawyer_id: str,
    req: AdminLawyerPublishRequest,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Publishes or unpublishes an advocate's profile in the client directory.
    Safeguard: Cannot publish an unverified or rejected lawyer profile.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.id == lawyer_id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")

    if req.is_published and profile.verification_status != LawyerVerificationStatus.VERIFIED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish lawyer profile. Bar Council credentials must be verified before publishing."
        )

    profile.is_published = req.is_published
    profile.updated_at = utc_now()

    action = "LAWYER_PROFILE_PUBLISHED" if req.is_published else "LAWYER_PROFILE_UNPUBLISHED"
    audit = AuditLog(
        organization_id=None,
        user_email=current_platform_user.email,
        action=action,
        object_type="LawyerProfile",
        object_id=profile.id,
        detail=f"Platform admin set publication status to {req.is_published} for {profile.bar_council_number}.",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(profile)

    return _serialize_admin_lawyer_profile(profile)


@router.post("/lawyers/{lawyer_id}/availability", response_model=AdminLawyerProfileResponse)
async def set_admin_lawyer_availability(
    lawyer_id: str,
    req: AdminLawyerAvailabilityRequest,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggles lawyer availability for consultation inquiries."""
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user), selectinload(LawyerProfile.organization))
        .where(LawyerProfile.id == lawyer_id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")

    profile.is_available_for_inquiries = req.is_available_for_inquiries
    profile.updated_at = utc_now()

    audit = AuditLog(
        organization_id=None,
        user_email=current_platform_user.email,
        action="LAWYER_AVAILABILITY_UPDATED",
        object_type="LawyerProfile",
        object_id=profile.id,
        detail=f"Platform admin set inquiry availability to {req.is_available_for_inquiries} for {profile.bar_council_number}.",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(profile)

    return _serialize_admin_lawyer_profile(profile)


@router.delete("/lawyers/{lawyer_id}")
async def delete_admin_lawyer(
    lawyer_id: str,
    current_platform_user: User = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Removes a lawyer profile from the platform registry.
    Safeguard: Emits an immutable platform audit log.
    """
    stmt = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.user))
        .where(LawyerProfile.id == lawyer_id)
    )
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")

    advocate_name = profile.user.full_name if profile.user else "Advocate"
    bar_id = profile.bar_council_number

    await db.delete(profile)

    audit = AuditLog(
        organization_id=None,
        user_email=current_platform_user.email,
        action="LAWYER_PROFILE_DELETED",
        object_type="LawyerProfile",
        object_id=lawyer_id,
        detail=f"Platform admin removed lawyer profile for {advocate_name} (Bar ID: {bar_id}).",
    )
    db.add(audit)
    await db.commit()

    return {"success": True, "message": f"Lawyer profile {advocate_name} successfully removed."}


# ============================================================================
# Platform Admin: Controlled Conversation Oversight
# ============================================================================

@router.get("/conversations", response_model=List[AdminConversationItem])
async def list_admin_conversations(
    status_filter: Optional[str] = None,
    review_status: Optional[str] = None,
    search: Optional[str] = None,
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_CONVERSATIONS_OVERSIGHT)),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists conversations across legal matters for Platform Admin compliance and safety oversight.
    Guarantees:
    - Dedicated platform permission required.
    - Tenant organization owners and ordinary members are strictly forbidden (403).
    - Summarizes review history and review status without exposing full confidential dialogue.
    """
    stmt = (
        select(LegalMatter)
        .options(
            selectinload(LegalMatter.client_organization),
            selectinload(LegalMatter.lawyer_organization),
            selectinload(LegalMatter.client_user),
            selectinload(LegalMatter.lawyer_user),
            selectinload(LegalMatter.messages).selectinload(MatterMessage.sender),
        )
        .order_by(LegalMatter.created_at.desc())
    )

    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(LegalMatter.status == status_filter.strip().upper())

    try:
        res = await db.execute(stmt)
        matters = res.scalars().all()
    except Exception as e:
        logger.error(f"Error querying legal matters for platform admin oversight: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversations from database."
        )

    matter_ids = [m.id for m in matters]
    audit_map = {}
    if matter_ids:
        try:
            audit_stmt = (
                select(AuditLog)
                .where(
                    AuditLog.object_id.in_(matter_ids),
                    AuditLog.action == "CONVERSATION_OVERSIGHT_REVIEWED"
                )
                .order_by(AuditLog.created_at.desc())
            )
            audit_res = await db.execute(audit_stmt)
            for a in audit_res.scalars().all():
                if a.object_id not in audit_map:
                    audit_map[a.object_id] = a
        except Exception as e:
            logger.warning(f"Error querying admin conversation oversight audit records: {e}")

    items = []
    search_term = search.strip().lower() if search else None

    for m in matters:
        all_msgs = m.messages or []
        last_msg = all_msgs[-1] if all_msgs else None
        audit = audit_map.get(m.id)

        rev_status = "REVIEWED" if audit else "UNREVIEWED"
        if review_status and review_status.upper() != "ALL" and rev_status != review_status.upper():
            continue

        c_name = m.client_organization.name if m.client_organization else ""
        c_user = m.client_user.full_name if m.client_user else ""
        c_email = m.client_user.email if m.client_user else ""
        l_org = m.lawyer_organization.name if m.lawyer_organization else ""
        l_user = m.lawyer_user.full_name if m.lawyer_user else ""
        l_email = m.lawyer_user.email if m.lawyer_user else ""

        if search_term:
            match_str = f"{m.matter_code} {m.title} {c_name} {c_user} {c_email} {l_org} {l_user} {l_email}".lower()
            if search_term not in match_str:
                continue

        reason = None
        if audit and "Reason: " in audit.detail:
            try:
                reason = audit.detail.split("Reason: ", 1)[1].split(". Admin:", 1)[0]
            except Exception:
                reason = audit.detail

        preview = None
        if last_msg:
            preview = (last_msg.message_text[:80] + "...") if len(last_msg.message_text) > 80 else last_msg.message_text

        items.append(
            AdminConversationItem(
                matter_id=m.id,
                matter_code=m.matter_code,
                title=m.title,
                status=m.status,
                client_organization_id=m.client_organization_id,
                client_organization_name=c_name,
                client_user_email=c_email,
                client_user_name=c_user,
                lawyer_organization_name=l_org,
                lawyer_user_email=l_email,
                lawyer_user_name=l_user,
                message_count=len(all_msgs),
                last_message_at=last_msg.created_at if last_msg else m.created_at,
                last_message_preview=preview,
                review_status=rev_status,
                last_reviewed_at=audit.created_at if audit else None,
                last_reviewed_by=audit.user_email if audit else None,
                last_review_reason=reason or ("Compliance Review" if audit else None),
                created_at=m.created_at
            )
        )

    return items


@router.post("/conversations/{matter_id}/review", response_model=AdminConversationReviewResponse)
async def review_admin_conversation(
    matter_id: str,
    payload: AdminConversationReviewPayload,
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_CONVERSATIONS_OVERSIGHT)),
    db: AsyncSession = Depends(get_db),
):
    """
    Accesses and decrypts conversation messages under explicit platform oversight.
    Safeguards:
    - Mandatory review reason required.
    - Generates append-only immutable audit entry.
    - Separates internal administrative notes from client-lawyer chat history.
    - Admins cannot impersonate participants or modify message records.
    """
    clean_reason = (payload.review_reason or payload.reason or "").strip()
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review reason is mandatory for platform conversation oversight."
        )

    stmt = (
        select(LegalMatter)
        .options(
            selectinload(LegalMatter.client_organization),
            selectinload(LegalMatter.lawyer_organization),
            selectinload(LegalMatter.client_user),
            selectinload(LegalMatter.lawyer_user),
        )
        .where(LegalMatter.id == matter_id)
    )
    res = await db.execute(stmt)
    matter = res.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal matter conversation not found.")

    # 1. Write immutable audit log
    audit_notes = payload.notes.strip() if payload.notes else ""
    audit_log = AuditLog(
        organization_id=matter.client_organization_id,
        user_email=current_platform_user.email,
        action="CONVERSATION_OVERSIGHT_REVIEWED",
        object_type="LegalMatter",
        object_id=matter.id,
        detail=f"Reason: {clean_reason}. Admin: {current_platform_user.email}. Notes: {audit_notes or 'None'}",
        ip_address="127.0.0.1"
    )
    db.add(audit_log)
    await db.commit()

    # 2. Fetch messages for this matter
    msg_stmt = (
        select(MatterMessage)
        .options(selectinload(MatterMessage.sender))
        .where(MatterMessage.matter_id == matter.id)
        .order_by(MatterMessage.created_at.asc())
    )
    msg_res = await db.execute(msg_stmt)
    messages = msg_res.scalars().all()

    # 3. Fetch audit history and notes
    history_stmt = (
        select(AuditLog)
        .where(
            AuditLog.object_id == matter.id,
            AuditLog.action.in_(["CONVERSATION_OVERSIGHT_REVIEWED", "CONVERSATION_OVERSIGHT_NOTE"])
        )
        .order_by(AuditLog.created_at.desc())
    )
    history_res = await db.execute(history_stmt)
    history_logs = history_res.scalars().all()

    audit_history = []
    admin_notes = []
    for h in history_logs:
        entry = {
            "id": h.id,
            "action": h.action,
            "admin_email": h.user_email,
            "detail": h.detail,
            "timestamp": h.created_at.isoformat() if h.created_at else None,
        }
        if h.action == "CONVERSATION_OVERSIGHT_NOTE":
            admin_notes.append(entry)
        else:
            audit_history.append(entry)

    formatted_messages = [
        MatterMessageResponse(
            id=m.id,
            matter_id=m.matter_id,
            sender_user_id=m.sender_user_id,
            sender_name=m.sender.full_name if m.sender else "Participant",
            sender_type=m.sender_type,
            message_text=m.message_text,
            is_internal_note=m.is_internal_note,
            attachments=m.attachments_json or [],
            created_at=m.created_at
        )
        for m in messages
    ]

    return AdminConversationReviewResponse(
        matter_id=matter.id,
        matter_code=matter.matter_code,
        title=matter.title,
        status=matter.status,
        review_status="REVIEWED",
        reviewed_at=audit_log.created_at or datetime.now(timezone.utc),
        reviewed_by=current_platform_user.email,
        review_reason=clean_reason,
        messages=formatted_messages,
        audit_history=audit_history,
        admin_notes=admin_notes,
    )


@router.post("/conversations/{matter_id}/notes")
async def add_admin_conversation_note(
    matter_id: str,
    payload: AdminConversationNotePayload,
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_CONVERSATIONS_OVERSIGHT)),
    db: AsyncSession = Depends(get_db),
):
    """
    Appends an internal administrative oversight note to AuditLog.
    Never injects into client-lawyer chat history.
    """
    clean_note = payload.note_text.strip()
    if not clean_note:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note text cannot be empty.")

    stmt = select(LegalMatter).where(LegalMatter.id == matter_id)
    res = await db.execute(stmt)
    matter = res.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal matter conversation not found.")

    note_audit = AuditLog(
        organization_id=matter.client_organization_id,
        user_email=current_platform_user.email,
        action="CONVERSATION_OVERSIGHT_NOTE",
        object_type="LegalMatter",
        object_id=matter.id,
        detail=f"Admin Note: {clean_note}",
        ip_address="127.0.0.1"
    )
    db.add(note_audit)
    await db.commit()

    return {
        "success": True,
        "note_id": note_audit.id,
        "matter_id": matter.id,
        "admin_email": current_platform_user.email,
        "created_at": note_audit.created_at or datetime.now(timezone.utc)
    }


# ============================================================================
# Platform Admin: Consultation Intake Approval & Rejection Queue
# ============================================================================

@router.get("/consultation-requests", response_model=List[AdminConsultationRequestItem])
async def list_admin_consultation_requests(
    status_filter: Optional[str] = None,
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_CONVERSATIONS_OVERSIGHT)),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists consultation and messaging intake requests for platform admin approval queue.
    Restricted to Platform Administrators with conversation oversight permission.
    """
    stmt = (
        select(LegalMatter)
        .options(
            selectinload(LegalMatter.client_organization),
            selectinload(LegalMatter.lawyer_organization),
            selectinload(LegalMatter.client_user),
            selectinload(LegalMatter.lawyer_user),
            selectinload(LegalMatter.messages),
        )
        .order_by(LegalMatter.created_at.desc())
    )

    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(LegalMatter.status == status_filter.strip().upper())

    try:
        res = await db.execute(stmt)
        matters = res.scalars().all()
    except Exception as e:
        logger.error(f"Error querying consultation requests: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query consultation requests."
        )

    items = []
    for m in matters:
        all_msgs = m.messages or []
        init_msg = all_msgs[0].message_text if all_msgs else m.client_notes
        items.append(
            AdminConsultationRequestItem(
                matter_id=m.id,
                matter_code=m.matter_code,
                title=m.title,
                status=m.status,
                client_organization_id=m.client_organization_id,
                client_organization_name=m.client_organization.name if m.client_organization else "",
                client_user_id=m.client_user_id,
                client_user_name=m.client_user.full_name if m.client_user else None,
                client_user_email=m.client_user.email if m.client_user else None,
                lawyer_organization_id=m.lawyer_organization_id,
                lawyer_organization_name=m.lawyer_organization.name if m.lawyer_organization else "",
                lawyer_user_id=m.lawyer_user_id,
                lawyer_user_name=m.lawyer_user.full_name if m.lawyer_user else None,
                lawyer_user_email=m.lawyer_user.email if m.lawyer_user else None,
                counterparty_name=m.counterparty_name,
                preferred_time_slot=m.preferred_time_slot,
                client_notes=m.client_notes,
                initial_message=init_msg,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
        )
    return items


@router.post("/consultation-requests/{matter_id}/decision")
async def decide_admin_consultation_request(
    matter_id: str,
    payload: AdminConsultationDecisionPayload,
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_CONVERSATIONS_OVERSIGHT)),
    db: AsyncSession = Depends(get_db),
):
    """
    Platform Admin approves or rejects a client consultation request.
    Idempotent: Approving an already approved consultation does not duplicate conversations.
    Enforces that:
    - On APPROVE: Matter status transitions to ACCEPTED, conversation is activated.
      Dual audit logs are emitted.
    - On REJECT: Matter status transitions to DECLINED, reason is recorded, messaging remains blocked.
    """
    stmt = (
        select(LegalMatter)
        .options(
            selectinload(LegalMatter.client_organization),
            selectinload(LegalMatter.lawyer_organization),
            selectinload(LegalMatter.client_user),
            selectinload(LegalMatter.lawyer_user),
        )
        .where(LegalMatter.id == matter_id)
    )
    res = await db.execute(stmt)
    matter = res.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation request not found.")

    decision = (payload.decision or payload.action or "").strip().upper()
    if decision not in ("APPROVE", "REJECT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be either 'APPROVE' or 'REJECT'."
        )
    reason = (payload.reason or "").strip()

    if decision == "APPROVE":
        # Idempotent: If already ACCEPTED or MATTER_ACTIVE, return immediately without duplicate side-effects
        if matter.status in (MatterStatus.ACCEPTED.value, MatterStatus.MATTER_ACTIVE.value):
            return {
                "success": True,
                "matter_id": matter.id,
                "matter_code": matter.matter_code,
                "status": matter.status,
                "new_status": matter.status,
                "is_active_for_messaging": True,
                "message": f"Consultation request {matter.matter_code} is already approved and active."
            }

        matter.status = MatterStatus.ACCEPTED.value
        matter.updated_at = utc_now()

        # Audit logging
        audit_platform = AuditLog(
            organization_id=None,
            user_email=current_platform_user.email,
            action="PLATFORM_CONSULTATION_REQUEST_APPROVED",
            object_type="LegalMatter",
            object_id=matter.id,
            detail=f"Platform admin approved consultation request {matter.matter_code} for client {matter.client_user.email if matter.client_user else matter.client_organization_id} and advocate {matter.lawyer_user.email if matter.lawyer_user else matter.lawyer_organization_id}. Reason: {reason or 'Administrative intake approval'}."
        )
        audit_client = AuditLog(
            organization_id=matter.client_organization_id,
            user_email=current_platform_user.email,
            action="PLATFORM_CONSULTATION_REQUEST_APPROVED",
            object_type="LegalMatter",
            object_id=matter.id,
            detail=f"Consultation request {matter.matter_code} approved by platform administration. Active messaging enabled."
        )
        db.add(audit_platform)
        db.add(audit_client)
        await db.commit()

        return {
            "success": True,
            "matter_id": matter.id,
            "matter_code": matter.matter_code,
            "status": matter.status,
            "new_status": matter.status,
            "is_active_for_messaging": True,
            "message": f"Consultation request {matter.matter_code} approved successfully. Conversation activated."
        }

    else:  # REJECT
        matter.status = MatterStatus.DECLINED.value
        clean_dec_reason = MatterDeclineReason.OTHER.value
        for r in MatterDeclineReason:
            if reason and r.value in reason.upper():
                clean_dec_reason = r.value
                break
        matter.decline_reason = clean_dec_reason
        matter.updated_at = utc_now()

        audit_platform = AuditLog(
            organization_id=None,
            user_email=current_platform_user.email,
            action="PLATFORM_CONSULTATION_REQUEST_REJECTED",
            object_type="LegalMatter",
            object_id=matter.id,
            detail=f"Platform admin rejected consultation request {matter.matter_code}. Reason: {reason or 'Administrative review rejection'}."
        )
        audit_client = AuditLog(
            organization_id=matter.client_organization_id,
            user_email=current_platform_user.email,
            action="PLATFORM_CONSULTATION_REQUEST_REJECTED",
            object_type="LegalMatter",
            object_id=matter.id,
            detail=f"Consultation request {matter.matter_code} was not approved. Reason: {reason or 'Administrative decision'}."
        )
        db.add(audit_platform)
        db.add(audit_client)
        await db.commit()

        return {
            "success": True,
            "matter_id": matter.id,
            "matter_code": matter.matter_code,
            "status": matter.status,
            "new_status": matter.status,
            "is_active_for_messaging": False,
            "message": f"Consultation request {matter.matter_code} marked as rejected."
        }

