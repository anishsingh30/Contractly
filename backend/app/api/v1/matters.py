import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, and_, update

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.dependencies import get_current_active_user, get_current_tenant
from app.models.user import User
from app.models.organization import Organization
from app.models.contract import Contract, ContractVersion, ContractRedline
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.models.base import utc_now, generate_uuid
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
from app.schemas.lawyer import (
    LegalHelpInquiryCreate,
    MatterSummaryResponse,
    MatterDetailResponse,
    ClarificationRequestPayload,
    ClarificationResponsePayload,
    ConflictCheckCertificationPayload,
    MatterAcceptPayload,
    MatterDeclinePayload,
    ClientConsentPayload,
    MatterWithdrawPayload,
    MatterResolvePayload,
    MatterDocumentVersionItem,
    MatterRedlineProposalCreate,
    MatterRedlineResponse,
    MatterMessageCreate,
    MatterMessageResponse,
    ConversationItemResponse,
)
from app.services.storage import storage_client
from app.services.notifications.matter_notifications import create_matter_message_notification


router = APIRouter(prefix="/matters", tags=["Legal Matters & Advocate Collaboration"])


# ============================================================================
# Security & Authorization Helpers
# ============================================================================

async def _get_matter_or_404(matter_id: str, db: AsyncSession) -> LegalMatter:
    stmt = (
        select(LegalMatter)
        .options(
            selectinload(LegalMatter.client_organization),
            selectinload(LegalMatter.lawyer_organization),
            selectinload(LegalMatter.client_user),
            selectinload(LegalMatter.lawyer_user),
            selectinload(LegalMatter.contract),
            selectinload(LegalMatter.access_grants),
        )
        .where(LegalMatter.id == matter_id)
    )
    res = await db.execute(stmt)
    matter = res.scalar_one_or_none()
    if not matter:
        # Generic error message to prevent matter ID enumeration
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Legal matter not found."
        )
    return matter


def _verify_matter_access(matter: LegalMatter, current_user: User, tenant: Organization) -> str:
    """
    Validates cross-tenant boundaries.
    Returns caller perspective: 'CLIENT' or 'LAWYER'.
    Raises HTTP 404 on unauthorized cross-tenant attempts to prevent IDOR enumeration.
    """
    if tenant.id == matter.client_organization_id or current_user.id == matter.client_user_id:
        return "CLIENT"

    if tenant.id == matter.lawyer_organization_id:
        if matter.lawyer_user_id is None or matter.lawyer_user_id == current_user.id:
            return "LAWYER"
    elif current_user.id == matter.lawyer_user_id:
        return "LAWYER"

    # Unauthorized access: Return generic 404 rather than 403 to prevent cross-tenant discovery
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Legal matter not found."
    )


async def _record_audit_log(
    db: AsyncSession,
    org_id: str,
    user_email: str,
    action: str,
    object_type: str,
    object_id: str,
    detail: str
) -> None:
    """Writes an immutable audit log entry without sensitive contract or message contents."""
    audit = AuditLog(
        organization_id=org_id,
        user_email=user_email,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail[:500]
    )
    db.add(audit)


def _format_matter_summary(matter: LegalMatter) -> Dict[str, Any]:
    active_grant = next((g for g in matter.access_grants if g.is_active), None)
    return {
        "id": matter.id,
        "matter_code": matter.matter_code,
        "title": matter.title,
        "matter_type": matter.matter_type,
        "status": matter.status,
        "client_organization_id": matter.client_organization_id,
        "client_organization_name": matter.client_organization.name if matter.client_organization else "",
        "client_user_id": matter.client_user_id,
        "client_user_name": matter.client_user.full_name if matter.client_user else None,
        "lawyer_organization_id": matter.lawyer_organization_id,
        "lawyer_organization_name": matter.lawyer_organization.name if matter.lawyer_organization else "",
        "lawyer_user_id": matter.lawyer_user_id,
        "lawyer_user_name": matter.lawyer_user.full_name if matter.lawyer_user else None,
        "counterparty_name": matter.counterparty_name,
        "contract_id": matter.contract_id,
        "contract_title": matter.contract.title if matter.contract else None,
        "conflict_cleared": matter.conflict_cleared,
        "client_consent_given": matter.client_consent_given,
        "has_active_grant": active_grant is not None,
        "grant_permission_level": active_grant.permission_level if active_grant else None,
        "preferred_time_slot": matter.preferred_time_slot,
        "created_at": matter.created_at,
        "updated_at": matter.updated_at,
    }


def _format_matter_detail(matter: LegalMatter) -> Dict[str, Any]:
    summary = _format_matter_summary(matter)
    summary.update({
        "conflict_cleared_at": matter.conflict_cleared_at,
        "client_consent_at": matter.client_consent_at,
        "client_notes": matter.client_notes,
        "scoping_notes": matter.scoping_notes,
        "decline_reason": matter.decline_reason,
        "resolved_at": matter.resolved_at,
        "closed_at": matter.closed_at,
        "has_admin_review": False,
        "last_admin_review_at": None,
        "admin_review_reason": None,
    })
    return summary


async def _get_matter_admin_review_info(matter_id: str, db: AsyncSession) -> Dict[str, Any]:
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.object_id == matter_id,
            AuditLog.action == "CONVERSATION_OVERSIGHT_REVIEWED"
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    audit = res.scalar_one_or_none()
    if audit:
        reason = None
        if "Reason: " in audit.detail:
            try:
                reason = audit.detail.split("Reason: ", 1)[1].split(". Admin:", 1)[0]
            except Exception:
                reason = audit.detail
        return {
            "has_admin_review": True,
            "last_admin_review_at": audit.created_at,
            "admin_review_reason": reason or "Administrative Compliance Review",
        }
    return {
        "has_admin_review": False,
        "last_admin_review_at": None,
        "admin_review_reason": None,
    }


# ============================================================================
# Matter Management Endpoints
# ============================================================================

@router.post("", response_model=MatterDetailResponse, status_code=status.HTTP_201_CREATED)
async def submit_legal_matter_inquiry(
    req: LegalHelpInquiryCreate,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a new legal help inquiry from a client organization to a verified advocate.
    Safeguards:
    - Target lawyer must exist and hold VERIFIED status.
    - If a contract_id is specified, it MUST belong to the caller's tenant.
    - Matter initial status is SUBMITTED; full document text remains blocked.
    """
    # 1. Resolve and verify target advocate
    stmt_lawyer = (
        select(LawyerProfile)
        .options(selectinload(LawyerProfile.organization), selectinload(LawyerProfile.user))
        .where(LawyerProfile.user_id == req.lawyer_user_id)
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

    if not lawyer_prof.is_available_for_inquiries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Designated legal advocate is currently not accepting new consultation inquiries."
        )

    # 2. Prevent lawyer from submitting inquiries to themselves
    if lawyer_prof.organization_id == tenant.id or lawyer_prof.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit an external consultation inquiry to your own practice organization."
        )

    # 3. If contract_id is supplied, verify it belongs strictly to caller's tenant
    if req.contract_id:
        stmt_ctr = select(Contract).where(
            Contract.id == req.contract_id,
            Contract.organization_id == tenant.id
        )
        res_ctr = await db.execute(stmt_ctr)
        if not res_ctr.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated contract not found in client organization."
            )

    # 4. Create LegalMatter
    matter_code = f"MAT-{utc_now().strftime('%Y')}-{generate_uuid()[:6].upper()}"
    new_matter = LegalMatter(
        matter_code=matter_code,
        title=req.title.strip(),
        matter_type=req.matter_type.strip(),
        client_organization_id=tenant.id,
        client_user_id=current_user.id,
        lawyer_organization_id=lawyer_prof.organization_id,
        lawyer_user_id=lawyer_prof.user_id,
        contract_id=req.contract_id,
        counterparty_name=req.counterparty_name.strip(),
        status=MatterStatus.SUBMITTED.value,
        conflict_cleared=False,
        client_consent_given=False,
        preferred_time_slot=req.preferred_time_slot,
        client_notes=req.client_notes
    )
    db.add(new_matter)
    await db.flush()

    # 5. Persist initial consultation message and notify lawyer
    init_msg_body = req.client_notes or f"New consultation inquiry submitted for {req.preferred_time_slot or 'Next Available Slot'}."
    init_msg = MatterMessage(
        matter_id=new_matter.id,
        sender_user_id=current_user.id,
        sender_type=MatterSenderType.CLIENT.value,
        message_text=init_msg_body,
        is_internal_note=False,
        attachments_json=[]
    )
    db.add(init_msg)
    await db.flush()
    await create_matter_message_notification(db, new_matter, init_msg, current_user)

    # 6. Dual Audit Logging
    await _record_audit_log(
        db, tenant.id, current_user.email,
        "LEGAL_MATTER_INQUIRY_SUBMITTED", "LegalMatter", new_matter.id,
        f"Inquiry {matter_code} submitted for advocate {lawyer_prof.user.full_name}. Counterparty: {req.counterparty_name}."
    )
    await _record_audit_log(
        db, lawyer_prof.organization_id, current_user.email,
        "LEGAL_MATTER_INQUIRY_RECEIVED", "LegalMatter", new_matter.id,
        f"Incoming inquiry {matter_code} received from {tenant.name}. Counterparty: {req.counterparty_name}."
    )
    await db.commit()

    reloaded = await _get_matter_or_404(new_matter.id, db)
    return _format_matter_detail(reloaded)


@router.get("", response_model=List[MatterSummaryResponse])
async def list_matters(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists legal matters strictly scoped to the caller:
    - Client users see only matters belonging to their client organization.
    - Lawyers see only matters specifically assigned to their lawyer user ID and practice organization.
    """
    stmt = (
        select(LegalMatter)
        .options(
            selectinload(LegalMatter.client_organization),
            selectinload(LegalMatter.lawyer_organization),
            selectinload(LegalMatter.client_user),
            selectinload(LegalMatter.lawyer_user),
            selectinload(LegalMatter.contract),
            selectinload(LegalMatter.access_grants),
        )
        .order_by(LegalMatter.created_at.desc())
    )

    if tenant.account_type in ("LEGAL_PROFESSIONAL", "PROFESSIONAL"):
        # Lawyer perspective: strictly assigned to caller or unassigned in this lawyer organization
        stmt = stmt.where(
            LegalMatter.lawyer_organization_id == tenant.id,
            or_(
                LegalMatter.lawyer_user_id == current_user.id,
                LegalMatter.lawyer_user_id == None
            )
        )
    else:
        # Client perspective: organization scoped
        stmt = stmt.where(LegalMatter.client_organization_id == tenant.id)

    if status_filter:
        clean_status = status_filter.strip().upper()
        stmt = stmt.where(LegalMatter.status == clean_status)

    res = await db.execute(stmt)
    matters = res.scalars().all()
    return [_format_matter_summary(m) for m in matters]


@router.get("/conversations", response_model=List[ConversationItemResponse])
async def list_user_conversations(
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns an organized list of conversations for client or lawyer.
    Includes last message snippet, timestamp, message count, matter status,
    and administrative review disclosure indicator.
    """
    stmt = (
        select(LegalMatter)
        .options(
            selectinload(LegalMatter.client_organization),
            selectinload(LegalMatter.lawyer_organization),
            selectinload(LegalMatter.client_user),
            selectinload(LegalMatter.lawyer_user),
            selectinload(LegalMatter.contract),
            selectinload(LegalMatter.messages).selectinload(MatterMessage.sender),
        )
        .order_by(LegalMatter.created_at.desc())
    )

    if tenant.account_type in ("LEGAL_PROFESSIONAL", "PROFESSIONAL"):
        stmt = stmt.where(
            or_(
                and_(
                    LegalMatter.lawyer_organization_id == tenant.id,
                    or_(
                        LegalMatter.lawyer_user_id == current_user.id,
                        LegalMatter.lawyer_user_id == None
                    )
                ),
                LegalMatter.lawyer_user_id == current_user.id,
                LegalMatter.client_organization_id == tenant.id,
                LegalMatter.client_user_id == current_user.id,
            )
        )
    else:
        stmt = stmt.where(
            or_(
                LegalMatter.client_organization_id == tenant.id,
                LegalMatter.client_user_id == current_user.id,
                LegalMatter.lawyer_user_id == current_user.id,
            )
        )

    try:
        res = await db.execute(stmt)
        matters = res.scalars().all()
    except Exception as e:
        logger.error(f"Error executing legal matters query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation list from database."
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
            logger.warning(f"Error querying conversation oversight audit records: {e}")

    conversations = []
    for m in matters:
        all_msgs = m.messages or []
        if tenant.account_type != "LEGAL_PROFESSIONAL":
            visible_msgs = [msg for msg in all_msgs if not msg.is_internal_note]
        else:
            visible_msgs = all_msgs

        last_msg = visible_msgs[-1] if visible_msgs else None
        audit = audit_map.get(m.id)
        reason = None
        if audit and "Reason: " in audit.detail:
            try:
                reason = audit.detail.split("Reason: ", 1)[1].split(". Admin:", 1)[0]
            except Exception:
                reason = audit.detail

        is_active = m.status in (
            MatterStatus.ACCEPTED.value,
            MatterStatus.MATTER_ACTIVE.value,
        )

        conversations.append(
            ConversationItemResponse(
                matter_id=m.id,
                matter_code=m.matter_code,
                title=m.title,
                status=m.status,
                client_organization_name=m.client_organization.name if m.client_organization else "",
                client_user_name=m.client_user.full_name if m.client_user else None,
                lawyer_organization_name=m.lawyer_organization.name if m.lawyer_organization else "",
                lawyer_user_name=m.lawyer_user.full_name if m.lawyer_user else None,
                contract_title=m.contract.title if m.contract else None,
                last_message_text=last_msg.message_text if last_msg else None,
                last_message_at=last_msg.created_at if last_msg else m.created_at,
                last_message_sender_type=last_msg.sender_type if last_msg else None,
                message_count=len(visible_msgs),
                has_admin_review=audit is not None,
                last_admin_review_at=audit.created_at if audit else None,
                admin_review_reason=reason or ("Administrative Review" if audit else None),
                is_active_for_messaging=is_active,
                created_at=m.created_at
            )
        )

    return conversations


@router.get("/{id}", response_model=MatterDetailResponse)
async def get_matter_details(
    id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves full details of an authorized matter."""
    matter = await _get_matter_or_404(id, db)
    _verify_matter_access(matter, current_user, tenant)
    detail = _format_matter_detail(matter)
    review_info = await _get_matter_admin_review_info(matter.id, db)
    detail.update(review_info)
    return detail


# ============================================================================
# Matter Lifecycle State Machine Endpoints
# ============================================================================

@router.post("/{id}/review", response_model=MatterDetailResponse)
async def mark_matter_under_review(
    id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Lawyer opens and marks submitted inquiry as UNDER_REVIEW."""
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "LAWYER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned counsel can place matter under review.")

    if matter.status not in (MatterStatus.SUBMITTED.value, MatterStatus.CLARIFICATION_REQUESTED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition to UNDER_REVIEW from current state '{matter.status}'."
        )

    matter.status = MatterStatus.UNDER_REVIEW.value
    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_UNDER_REVIEW", "LegalMatter", matter.id,
        f"Advocate opened inquiry {matter.matter_code} for intake assessment."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/clarification/request", response_model=MatterDetailResponse)
async def request_matter_clarification(
    id: str,
    payload: ClarificationRequestPayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Lawyer requests scoping clarification from client."""
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "LAWYER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned counsel can request clarification.")

    if matter.status not in (MatterStatus.SUBMITTED.value, MatterStatus.UNDER_REVIEW.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot request clarification from current state '{matter.status}'."
        )

    matter.status = MatterStatus.CLARIFICATION_REQUESTED.value
    matter.scoping_notes = (
        f"Clarification requested on {utc_now().strftime('%Y-%m-%d %H:%M UTC')}:\n{payload.scoping_question.strip()}"
    )

    # Post as client-visible message in matter thread
    msg = MatterMessage(
        matter_id=matter.id,
        sender_user_id=current_user.id,
        sender_type=MatterSenderType.LAWYER.value,
        message_text=f"[Scoping Clarification Requested]: {payload.scoping_question.strip()}",
        is_internal_note=False,
        attachments_json=[]
    )
    db.add(msg)
    await db.flush()
    await create_matter_message_notification(db, matter, msg, current_user)

    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_CLARIFICATION_REQUESTED", "LegalMatter", matter.id,
        f"Counsel requested scoping clarification for matter {matter.matter_code}."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/clarification/respond", response_model=MatterDetailResponse)
async def respond_matter_clarification(
    id: str,
    payload: ClarificationResponsePayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Client provides scoping clarification response."""
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "CLIENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only client organization can respond to clarification.")

    if matter.status != MatterStatus.CLARIFICATION_REQUESTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Matter {matter.matter_code} is not currently awaiting clarification."
        )

    matter.status = MatterStatus.UNDER_REVIEW.value
    existing_notes = matter.scoping_notes or ""
    matter.scoping_notes = (
        f"{existing_notes}\n\nClient response on {utc_now().strftime('%Y-%m-%d %H:%M UTC')}:\n{payload.scoping_answer.strip()}"
    )

    # Post in matter thread
    msg = MatterMessage(
        matter_id=matter.id,
        sender_user_id=current_user.id,
        sender_type=MatterSenderType.CLIENT.value,
        message_text=f"[Clarification Response]: {payload.scoping_answer.strip()}",
        is_internal_note=False,
        attachments_json=[]
    )
    db.add(msg)
    await db.flush()
    await create_matter_message_notification(db, matter, msg, current_user)

    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_CLARIFICATION_RESPONDED", "LegalMatter", matter.id,
        f"Client provided scoping clarification response for matter {matter.matter_code}."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/conflict-check", response_model=MatterDetailResponse)
async def certify_conflict_check(
    id: str,
    payload: ConflictCheckCertificationPayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lawyer explicitly certifies internal conflict-of-interest clearance.
    Records certifier user ID and timestamp.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "LAWYER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned counsel can certify conflict clearance.")

    if matter.status not in (MatterStatus.SUBMITTED.value, MatterStatus.UNDER_REVIEW.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot record conflict check in current state '{matter.status}'."
        )

    matter.conflict_cleared = True
    matter.conflict_cleared_at = utc_now()
    matter.conflict_cleared_by_user_id = current_user.id
    if payload.conflict_notes:
        matter.conflict_notes = payload.conflict_notes.strip()

    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_CONFLICT_CLEARED", "LegalMatter", matter.id,
        f"Counsel certified conflict-of-interest clearance for counterparty '{matter.counterparty_name}'."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/accept", response_model=MatterDetailResponse)
async def accept_matter_inquiry(
    id: str,
    payload: MatterAcceptPayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lawyer accepts inquiry.
    Mandatory invariant: conflict_cleared MUST be certified prior to acceptance.
    Does not activate document access until client provides consent.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "LAWYER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned counsel can accept an inquiry.")

    # Invariant: Conflict check must be certified
    if not matter.conflict_cleared:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conflict-of-interest clearance must be explicitly certified before accepting this matter."
        )

    if matter.status not in (MatterStatus.SUBMITTED.value, MatterStatus.UNDER_REVIEW.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot accept matter from current state '{matter.status}'."
        )

    matter.status = MatterStatus.ACCEPTED.value
    if payload.confirmed_slot:
        matter.preferred_time_slot = payload.confirmed_slot.strip()

    await _record_audit_log(
        db, matter.client_organization_id, current_user.email,
        "MATTER_INQUIRY_ACCEPTED", "LegalMatter", matter.id,
        f"Advocate accepted inquiry {matter.matter_code}. Pending client document sharing consent."
    )
    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_INQUIRY_ACCEPTED", "LegalMatter", matter.id,
        f"Chambers accepted inquiry {matter.matter_code}."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/decline", response_model=MatterDetailResponse)
async def decline_matter_inquiry(
    id: str,
    payload: MatterDeclinePayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lawyer declines inquiry with a controlled reason.
    Privacy invariant: Details about an adverse conflict are not leaked to the client.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "LAWYER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned counsel can decline an inquiry.")

    if matter.status in (MatterStatus.MATTER_ACTIVE.value, MatterStatus.RESOLVED.value, MatterStatus.CLOSED.value, MatterStatus.DECLINED.value, MatterStatus.CANCELLED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decline matter in state '{matter.status}'."
        )

    matter.status = MatterStatus.DECLINED.value
    matter.decline_reason = payload.decline_reason.value

    # Safe sanitized client message
    if payload.decline_reason == MatterDeclineReason.CONFLICT_OF_INTEREST:
        client_reason_msg = "Professional rules and ethical conflict-of-interest guidelines."
    elif payload.decline_reason == MatterDeclineReason.CAPACITY_FULL:
        client_reason_msg = "Chambers capacity constraints for the requested timeframe."
    elif payload.decline_reason == MatterDeclineReason.OUT_OF_SCOPE:
        client_reason_msg = "Matter requirements outside chambers core practice jurisdictions."
    else:
        client_reason_msg = "Counsel availability constraints."

    await _record_audit_log(
        db, matter.client_organization_id, current_user.email,
        "MATTER_INQUIRY_DECLINED", "LegalMatter", matter.id,
        f"Inquiry declined due to: {client_reason_msg}"
    )
    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_INQUIRY_DECLINED", "LegalMatter", matter.id,
        f"Chambers declined inquiry {matter.matter_code} ({payload.decline_reason.value})."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/consent", response_model=MatterDetailResponse)
async def grant_client_consent_and_activate(
    id: str,
    payload: ClientConsentPayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Client explicitly authorizes contract document sharing.
    Creates active MatterAccessGrant and transitions matter to MATTER_ACTIVE.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "CLIENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only client organization can grant document access consent.")

    if matter.status != MatterStatus.ACCEPTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Matter must be in ACCEPTED state before granting consent (current state: '{matter.status}')."
        )

    if not matter.contract_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot grant document sharing consent for a matter without an associated contract."
        )

    # 1. Update client consent records
    matter.client_consent_given = True
    matter.client_consent_at = utc_now()
    matter.client_consent_by_user_id = current_user.id
    matter.status = MatterStatus.MATTER_ACTIVE.value

    # 2. Upsert / Activate MatterAccessGrant
    stmt_grant = select(MatterAccessGrant).where(
        MatterAccessGrant.matter_id == matter.id,
        MatterAccessGrant.contract_id == matter.contract_id,
        MatterAccessGrant.lawyer_user_id == matter.lawyer_user_id
    )
    res_grant = await db.execute(stmt_grant)
    grant = res_grant.scalar_one_or_none()

    if grant:
        grant.is_active = True
        grant.permission_level = payload.permission_level.value
        grant.granted_at = utc_now()
        grant.granted_by_user_id = current_user.id
        grant.revoked_at = None
        grant.revoked_by_user_id = None
        grant.revocation_reason = None
    else:
        grant = MatterAccessGrant(
            matter_id=matter.id,
            contract_id=matter.contract_id,
            lawyer_user_id=matter.lawyer_user_id,
            permission_level=payload.permission_level.value,
            is_active=True,
            granted_at=utc_now(),
            granted_by_user_id=current_user.id
        )
        db.add(grant)
        if hasattr(matter, "access_grants") and matter.access_grants is not None:
            matter.access_grants.append(grant)

    # 3. Dual Audit Logging
    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_DOCUMENT_GRANT_ISSUED", "MatterAccessGrant", matter.id,
        f"Client authorized {payload.permission_level.value} contract sharing for matter {matter.matter_code}."
    )
    await _record_audit_log(
        db, matter.lawyer_organization_id, current_user.email,
        "MATTER_DOCUMENT_GRANT_RECEIVED", "MatterAccessGrant", matter.id,
        f"Active {payload.permission_level.value} document grant received for matter {matter.matter_code}."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/grant/revoke", response_model=MatterDetailResponse)
async def revoke_matter_document_grant(
    id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Client revokes active document access grant immediately."""
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "CLIENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only client organization can revoke document grants.")

    active_grants = [g for g in matter.access_grants if g.is_active]
    now = utc_now()
    for g in active_grants:
        g.is_active = False
        g.revoked_at = now
        g.revoked_by_user_id = current_user.id
        g.revocation_reason = "Client explicitly revoked document access."

    matter.client_consent_given = False

    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_DOCUMENT_GRANT_REVOKED", "MatterAccessGrant", matter.id,
        f"Client revoked document access for matter {matter.matter_code}."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/withdraw", response_model=MatterDetailResponse)
async def withdraw_matter_inquiry(
    id: str,
    payload: MatterWithdrawPayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Client cancels inquiry prior to resolution."""
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "CLIENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only client organization can withdraw an inquiry.")

    if matter.status in (MatterStatus.RESOLVED.value, MatterStatus.CLOSED.value, MatterStatus.DECLINED.value, MatterStatus.CANCELLED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot withdraw matter in state '{matter.status}'."
        )

    matter.status = MatterStatus.CANCELLED.value
    # Automatically deactivate any access grants
    now = utc_now()
    for g in matter.access_grants:
        if g.is_active:
            g.is_active = False
            g.revoked_at = now
            g.revoked_by_user_id = current_user.id
            g.revocation_reason = "Client cancelled matter."

    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_INQUIRY_CANCELLED", "LegalMatter", matter.id,
        f"Inquiry {matter.matter_code} cancelled by client."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/resolve", response_model=MatterDetailResponse)
async def resolve_matter(
    id: str,
    payload: MatterResolvePayload,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Lawyer concludes review and delivers advisory findings."""
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "LAWYER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned counsel can resolve a matter.")

    if matter.status != MatterStatus.MATTER_ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve matter from current state '{matter.status}'."
        )

    matter.status = MatterStatus.RESOLVED.value
    matter.resolved_at = utc_now()

    # Post resolution delivery in matter thread
    msg = MatterMessage(
        matter_id=matter.id,
        sender_user_id=current_user.id,
        sender_type=MatterSenderType.LAWYER.value,
        message_text=f"[Matter Resolution Memorandum]:\n{payload.resolution_summary.strip()}",
        is_internal_note=False,
        attachments_json=[]
    )
    db.add(msg)
    await db.flush()
    await create_matter_message_notification(db, matter, msg, current_user)

    await _record_audit_log(
        db, matter.client_organization_id, current_user.email,
        "MATTER_RESOLVED", "LegalMatter", matter.id,
        f"Counsel delivered findings for matter {matter.matter_code}."
    )
    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_RESOLVED", "LegalMatter", matter.id,
        f"Chambers marked matter {matter.matter_code} as RESOLVED."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


@router.post("/{id}/close", response_model=MatterDetailResponse)
async def close_matter(
    id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Client signs off on deliverables and closes the matter.
    Immediately revokes all active document access grants.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "CLIENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only client organization can close a matter.")

    if matter.status not in (MatterStatus.RESOLVED.value, MatterStatus.MATTER_ACTIVE.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot close matter from current state '{matter.status}'."
        )

    matter.status = MatterStatus.CLOSED.value
    matter.closed_at = utc_now()

    # Immediate access grant revocation
    now = utc_now()
    for g in matter.access_grants:
        if g.is_active:
            g.is_active = False
            g.revoked_at = now
            g.revoked_by_user_id = current_user.id
            g.revocation_reason = "Matter concluded and closed."

    await _record_audit_log(
        db, tenant.id, current_user.email,
        "MATTER_CLOSED", "LegalMatter", matter.id,
        f"Matter {matter.matter_code} formally closed. Document access revoked."
    )
    await db.commit()
    reloaded = await _get_matter_or_404(id, db)
    return _format_matter_detail(reloaded)


# ============================================================================
# Document Streaming & Cross-Tenant Access
# ============================================================================

@router.get("/{id}/documents", response_model=List[MatterDocumentVersionItem])
async def list_authorized_matter_documents(
    id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists authorized contract document versions for a matter.
    Safeguards:
    - If caller is lawyer: returns documents ONLY if matter is MATTER_ACTIVE, client consent is given,
      and an active MatterAccessGrant exists. Otherwise returns HTTP 403 Forbidden.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)

    if not matter.contract_id:
        return []

    if perspective == "LAWYER":
        if matter.status != MatterStatus.MATTER_ACTIVE.value or not matter.client_consent_given:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Contract documents cannot be accessed prior to client consent and matter activation."
            )
        active_grant = next((g for g in matter.access_grants if g.is_active and g.lawyer_user_id == current_user.id), None)
        if not active_grant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active document access grant found for this matter."
            )

    stmt = (
        select(ContractVersion)
        .where(ContractVersion.contract_id == matter.contract_id)
        .order_by(ContractVersion.created_at.desc())
    )
    res = await db.execute(stmt)
    versions = res.scalars().all()

    return [
        MatterDocumentVersionItem(
            version_id=v.id,
            version_number=v.version_number,
            filename=v.filename,
            file_byte_size=v.file_byte_size,
            sha256_checksum=v.sha256_checksum,
            page_count=v.page_count,
            created_at=v.created_at
        )
        for v in versions
    ]


@router.get("/{id}/documents/{version_id}/stream")
async def stream_authorized_matter_document(
    id: str,
    version_id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Streams raw contract document file through the storage abstraction.
    Enforces active grant verification on EVERY request.
    Satisfies immediate revocation upon closing or grant cancellation.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)

    if not matter.contract_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter has no linked contract document.")

    if perspective == "LAWYER":
        if matter.status != MatterStatus.MATTER_ACTIVE.value or not matter.client_consent_given:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Document access is locked until client provides explicit sharing consent."
            )
        active_grant = next((g for g in matter.access_grants if g.is_active and g.lawyer_user_id == current_user.id), None)
        if not active_grant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Document grant is inactive or has been revoked."
            )

    # Query target version
    stmt = select(ContractVersion).where(
        ContractVersion.id == version_id,
        ContractVersion.contract_id == matter.contract_id
    )
    res = await db.execute(stmt)
    v = res.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract document version not found.")

    try:
        content = storage_client.get_file(v.file_storage_path, tenant_id=matter.client_organization_id)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file missing from vault storage.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to retrieve document file.")

    safe_filename = "".join(c for c in (v.filename or f"contract_{v.version_number}.pdf") if c.isalnum() or c in "._- ")

    # Audit stream event
    await _record_audit_log(
        db, matter.client_organization_id, current_user.email,
        "MATTER_DOCUMENT_STREAMED", "ContractVersion", v.id,
        f"Document {safe_filename} streamed by {current_user.email} ({perspective})."
    )
    await db.commit()

    return Response(
        content=content,
        media_type=v.file_mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff"
        }
    )


# ============================================================================
# Redline Collaboration Endpoints
# ============================================================================

@router.post("/{id}/redlines", response_model=MatterRedlineResponse, status_code=status.HTTP_201_CREATED)
async def submit_lawyer_redline_proposal(
    id: str,
    payload: MatterRedlineProposalCreate,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lawyer submits a tracked redline revision on an active matter.
    Safeguards:
    - Grant permission_level MUST be REDLINE_COLLABORATIVE.
    - If grant is READ_ONLY, raises HTTP 403 Forbidden.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)
    if perspective != "LAWYER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned counsel can submit redlines via matter workspace.")

    if matter.status != MatterStatus.MATTER_ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redlines can only be submitted for active matters."
        )

    if not matter.contract_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Matter has no linked contract.")

    active_grant = next((g for g in matter.access_grants if g.is_active and g.lawyer_user_id == current_user.id), None)
    if not active_grant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active document grant found for this matter.")

    if active_grant.permission_level != MatterPermissionLevel.REDLINE_COLLABORATIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Document access grant is {active_grant.permission_level}. Collaborative redlining is not permitted."
        )

    # Insert using existing ContractRedline model
    redline = ContractRedline(
        contract_id=matter.contract_id,
        clause_id=payload.clause_id,
        section_title=payload.section_title.strip(),
        original_text=payload.original_text.strip(),
        suggested_text=payload.suggested_text.strip(),
        rationale=payload.rationale.strip() if payload.rationale else None,
        status="PENDING",
        author=f"Adv. {current_user.full_name}"
    )
    db.add(redline)
    await db.flush()

    await _record_audit_log(
        db, matter.client_organization_id, current_user.email,
        "MATTER_REDLINE_PROPOSED", "ContractRedline", redline.id,
        f"Counsel submitted proposed redline for '{payload.section_title}'."
    )
    await db.commit()

    return MatterRedlineResponse(
        id=redline.id,
        contract_id=redline.contract_id,
        section_title=redline.section_title,
        original_text=redline.original_text,
        suggested_text=redline.suggested_text,
        rationale=redline.rationale,
        status=redline.status,
        author=redline.author,
        created_at=redline.created_at
    )


# ============================================================================
# Matter Messaging & Private Notes Endpoints
# ============================================================================

@router.get("/{id}/messages", response_model=List[MatterMessageResponse])
async def list_matter_messages(
    id: str,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves threaded messages for a matter.
    Critical privacy safeguard:
    - If caller is CLIENT: SQL query filters out is_internal_note=True.
      Clients NEVER receive chambers private internal notes.
    - If caller is LAWYER: returns both client messages and chambers internal notes.
    - Populates X-Admin-Reviewed header if Platform Administration has conducted an oversight review.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)

    # Check lawyer status
    if perspective == "LAWYER":
        stmt_lawyer = select(LawyerProfile).where(LawyerProfile.user_id == current_user.id)
        res_lawyer = await db.execute(stmt_lawyer)
        l_prof = res_lawyer.scalar_one_or_none()
        if l_prof and l_prof.verification_status in (
            LawyerVerificationStatus.SUSPENDED.value,
            LawyerVerificationStatus.REJECTED.value
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lawyer credentials have been suspended or revoked."
            )

    review_info = await _get_matter_admin_review_info(matter.id, db)
    if review_info["has_admin_review"]:
        response.headers["X-Admin-Reviewed"] = "true"
        response.headers["X-Admin-Review-Date"] = review_info["last_admin_review_at"].isoformat() if review_info["last_admin_review_at"] else ""
        response.headers["X-Admin-Review-Reason"] = review_info["admin_review_reason"] or ""

    stmt = (
        select(MatterMessage)
        .options(selectinload(MatterMessage.sender))
        .where(MatterMessage.matter_id == matter.id)
        .order_by(MatterMessage.created_at.asc())
    )

    if perspective == "CLIENT":
        # Strictly exclude internal lawyer notes server-side
        stmt = stmt.where(MatterMessage.is_internal_note.is_(False))

    res = await db.execute(stmt)
    messages = res.scalars().all()

    return [
        MatterMessageResponse(
            id=m.id,
            matter_id=m.matter_id,
            sender_user_id=m.sender_user_id,
            sender_name=m.sender.full_name if m.sender else "Unknown",
            sender_type=m.sender_type,
            message_text=m.message_text,
            is_internal_note=m.is_internal_note,
            attachments=m.attachments_json or [],
            created_at=m.created_at
        )
        for m in messages
    ]


@router.post("/{id}/messages", response_model=MatterMessageResponse, status_code=status.HTTP_201_CREATED)
async def post_matter_message(
    id: str,
    payload: MatterMessageCreate,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Posts a message or internal chambers note in the matter thread.
    Safeguards:
    - Rejects messaging on closed, declined, resolved, or cancelled matters.
    - Client users cannot set is_internal_note=True.
    - Sender identity is derived strictly from server-side authenticated identity.
    - Validates message character length and blocks suspended advocate credentials.
    """
    matter = await _get_matter_or_404(id, db)
    perspective = _verify_matter_access(matter, current_user, tenant)

    # Pending review check: active messaging disabled until approved
    if matter.status in (MatterStatus.SUBMITTED.value, MatterStatus.UNDER_REVIEW.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot post message. Consultation request is pending administrative approval."
        )

    # Matter closure policy: communication strictly prevented once inactive
    if matter.status in (
        MatterStatus.DECLINED.value,
        MatterStatus.CANCELLED.value,
        MatterStatus.RESOLVED.value,
        MatterStatus.CLOSED.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post message. Matter is {matter.status.lower()} and no longer active for messaging."
        )

    # Lawyer suspension check
    if perspective == "LAWYER":
        stmt_lawyer = select(LawyerProfile).where(LawyerProfile.user_id == current_user.id)
        res_lawyer = await db.execute(stmt_lawyer)
        l_prof = res_lawyer.scalar_one_or_none()
        if l_prof and l_prof.verification_status in (
            LawyerVerificationStatus.SUSPENDED.value,
            LawyerVerificationStatus.REJECTED.value
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lawyer credentials have been suspended or revoked."
            )

    is_internal = payload.is_internal_note if perspective == "LAWYER" else False
    sender_type = MatterSenderType.LAWYER.value if perspective == "LAWYER" else MatterSenderType.CLIENT.value

    clean_text = payload.message_text.strip()
    if not clean_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message text cannot be empty.")
    if len(clean_text) > 5000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message text exceeds 5000 character maximum limit.")

    msg = MatterMessage(
        matter_id=matter.id,
        sender_user_id=current_user.id,
        sender_type=sender_type,
        message_text=clean_text,
        is_internal_note=is_internal,
        attachments_json=payload.attachments or []
    )
    db.add(msg)
    await db.flush()

    # Synchronize notification to the recipient
    await create_matter_message_notification(db, matter, msg, current_user)

    # Audit logging without logging message body
    audit_target_org = tenant.id
    await _record_audit_log(
        db, audit_target_org, current_user.email,
        "MATTER_MESSAGE_SENT", "MatterMessage", msg.id,
        f"Message posted in matter {matter.matter_code} (InternalNote={is_internal})."
    )
    await db.commit()

    return MatterMessageResponse(
        id=msg.id,
        matter_id=msg.matter_id,
        sender_user_id=msg.sender_user_id,
        sender_name=current_user.full_name,
        sender_type=msg.sender_type,
        message_text=msg.message_text,
        is_internal_note=msg.is_internal_note,
        attachments=msg.attachments_json or [],
        created_at=msg.created_at
    )


@router.patch("/{id}/read")
@router.post("/{id}/read")
async def mark_matter_messages_read(
    id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Marks unread message notifications associated with this matter as read for the current user in active tenant.
    Preserves all unrelated notifications (deadlines, approvals, other matters).
    """
    matter = await _get_matter_or_404(id, db)
    _verify_matter_access(matter, current_user, tenant)

    msg_stmt = select(MatterMessage.id).where(MatterMessage.matter_id == matter.id)
    msg_res = await db.execute(msg_stmt)
    msg_ids = [str(m) for m in msg_res.scalars().all()]
    dedup_keys = [f"matter_msg_{mid}" for mid in msg_ids]

    criteria = [
        Notification.user_id == current_user.id,
        Notification.is_read == False,
        or_(
            Notification.organization_id == tenant.id,
            Notification.organization_id == matter.lawyer_organization_id,
            Notification.organization_id == matter.client_organization_id
        )
    ]

    matter_conditions = []
    if dedup_keys:
        matter_conditions.append(Notification.deduplication_key.in_(dedup_keys))
    matter_conditions.append(
        and_(
            Notification.event_type == "MATTER_MESSAGE_RECEIVED",
            Notification.title.like(f"%{matter.matter_code}%")
        )
    )
    if matter.contract_id:
        matter_conditions.append(
            and_(
                Notification.contract_id == matter.contract_id,
                Notification.event_type == "MATTER_MESSAGE_RECEIVED"
            )
        )

    stmt = (
        update(Notification)
        .where(
            and_(
                *criteria,
                or_(*matter_conditions)
            )
        )
        .values(is_read=True, read_at=utc_now())
    )
    res = await db.execute(stmt)
    await db.commit()
    return {
        "status": "success",
        "success": True,
        "marked_read": res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0,
        "matter_id": id
    }

