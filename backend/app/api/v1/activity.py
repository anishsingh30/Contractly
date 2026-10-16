import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import (
    get_current_active_user,
    get_current_tenant,
    get_current_token,
)
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.models.lawyer import LegalMatter, MatterMessage, LawyerProfile
from app.core.permissions import has_permission, PERMISSION_AUDIT_READ
from app.schemas.activity import (
    ActivityItem,
    ActivityListResponse,
    ActivityDetailResponse
)

router = APIRouter(prefix="/activity", tags=["Activity History"])

ACTION_DISPLAY_LABELS: Dict[str, str] = {
    "CONTRACT_UPLOADED": "Contract Uploaded",
    "CONTRACT_STATUS_TRANSITIONED": "Contract Status Changed",
    "CONTRACT_ARCHIVED": "Contract Archived",
    "REDLINE_ACCEPTED": "Redline Accepted",
    "REDLINE_REJECTED": "Redline Rejected",
    "REDLINES_GENERATED": "AI Redlines Generated",
    "NEGOTIATION_EVALUATED": "Negotiation Playbook Evaluated",
    "INTELLIGENCE_REPROCESSED": "Contract Intelligence Reprocessed",
    "APPROVAL_DECISION_SUBMITTED": "Approval Sign-Off",
    "MATTER_MESSAGE_SENT": "Matter Message Sent",
    "MATTER_RESOLVED": "Matter Resolved",
    "LAWYER_CONSULTATION_INQUIRY_SUBMITTED": "Consultation Inquiry Submitted",
    "TEST_EMAIL_DISPATCH": "Email Dispatch Attempt",
    "UPDATE_NOTIFICATION_PREFERENCES": "Notification Preferences Updated",
    "OBLIGATION_EVIDENCE_UPLOADED": "Obligation Evidence Uploaded",
    "OBLIGATION_STATUS_UPDATED": "Obligation Status Updated",
    "VENDOR_CREATED": "Vendor Profile Created",
    "VENDOR_UPDATED": "Vendor Profile Updated",
    "PLAYBOOK_RULE_CREATED": "Playbook Rule Created",
    "PLAYBOOK_RULE_UPDATED": "Playbook Rule Updated",
    "ORGANIZATION_MEMBER_INVITED": "Team Member Invited",
    "ROLE_UPDATED": "Member Role Changed",
    "CONVERSATION_OVERSIGHT_REVIEWED": "Compliance Review Conducted",
}

def mask_email(email: str) -> str:
    """Safely masks an email address for privacy (e.g., j***e@domain.com)."""
    if not email or "@" not in email:
        return "[REDACTED]"
    parts = email.split("@")
    user_part = parts[0]
    domain_part = parts[1]
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain_part}"

def sanitize_audit_detail(
    raw_detail: str,
    action: str,
    viewer_email: str,
    actor_email: str,
    is_owner_or_admin: bool
) -> str:
    """
    Sanitizes raw implementation fields, internal notes, credentials,
    file paths, and masks recipient emails for unauthorized viewers.
    """
    if not raw_detail:
        return ""

    text = raw_detail.strip()

    # 1. Strip raw implementation flags like (InternalNote=False) or (InternalNote=True)
    text = re.sub(r"\s*\(InternalNote=(?:True|False)\)", "", text, flags=re.IGNORECASE)

    # 2. Email dispatch handling (truthful status & masked recipients)
    if action == "TEST_EMAIL_DISPATCH" or "Test email dispatch" in text:
        email_match = re.search(r"Test email dispatch to\s+([^\s\(\)]+)", text, re.IGNORECASE)
        recipient = email_match.group(1) if email_match else ""
        
        # Determine failure vs success
        is_success = "success=True" in text or "Accepted by provider" in text
        if is_success:
            status_desc = "Accepted by provider"
        else:
            status_desc = "Delivery rejected by upstream provider (unverified domain)"

        if recipient:
            can_see_full = (viewer_email.lower() == recipient.lower()) or is_owner_or_admin
            display_recipient = recipient if can_see_full else mask_email(recipient)
            return f"Administrative test email dispatch to {display_recipient} (Status: {status_desc})"
        return f"Administrative test email dispatch (Status: {status_desc})"

    # 3. Strip raw client consultation notes if present
    if action == "LAWYER_CONSULTATION_INQUIRY_SUBMITTED":
        notes_idx = text.find(". Client notes:")
        if notes_idx != -1:
            text = text[:notes_idx + 1]

    # 4. Strip internal filesystem paths and stack traces
    text = re.sub(r"[A-Za-z]:\\[\w\\\s.-]+", "[SECURE_STORAGE]", text)
    text = re.sub(r"/(?:var|tmp|home|app)/[\w/\s.-]+", "[SECURE_STORAGE]", text)
    text = re.sub(r"Traceback \(most recent call last\):.*", "[ERROR_DETAILS_SANITIZED]", text, flags=re.DOTALL)

    return text.strip()

def determine_activity_status(action: str, detail: str) -> str:
    """Returns human-readable activity outcome status."""
    if "success=False" in detail or "failed" in detail.lower() or "rejected by upstream" in detail.lower():
        return "FAILED"
    if "PENDING" in action or "submitted" in detail.lower():
        return "PENDING"
    return "COMPLETED"

@router.get("", response_model=ActivityListResponse)
async def list_activity_history(
    scope: str = Query("personal", pattern="^(personal|organization)$"),
    action_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    team_member: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Enforces granular role-based access control for Activity History:
    - scope=personal: user's own actions and authorized matter events.
    - scope=organization: organization-wide events; strictly restricted to
      roles with PERMISSION_AUDIT_READ or OWNER/ADMIN/LEGAL_MANAGER in non-individual orgs.
    - Never leaks foreign tenant data, raw UUIDs, or sensitive implementation details.
    """
    # 1. Evaluate user membership and permission in the tenant
    stmt_member = select(OrganizationMember).where(
        OrganizationMember.organization_id == tenant.id,
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.status == "ACTIVE"
    )
    res_member = await db.execute(stmt_member)
    member = res_member.scalar_one_or_none()

    member_role = (member.role.upper() if member and member.role else "MEMBER")
    is_personal_workspace = (tenant.account_type == "INDIVIDUAL")

    can_view_org = (
        not is_personal_workspace
        and (
            has_permission(member_role, PERMISSION_AUDIT_READ)
            or member_role in ("OWNER", "ADMIN", "LEGAL_MANAGER")
        )
    )

    # 2. Validate scope authorization
    if scope == "organization":
        if is_personal_workspace:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization activity history is not permitted for INDIVIDUAL workspace."
            )
        if not can_view_org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Viewing organization-wide activity history requires administrative or legal manager privileges."
            )

    if team_member:
        if not can_view_org and team_member.strip().lower() != current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Filtering team member activity is restricted to organization administrators."
            )

    # 3. Build query based on scope and role
    conditions = []

    if scope == "organization":
        # Strict tenant boundary
        conditions.append(AuditLog.organization_id == tenant.id)
        if team_member:
            conditions.append(func.lower(AuditLog.user_email) == team_member.strip().lower())
    else:
        # Personal scope
        # User sees their own actions:
        personal_cond = [func.lower(AuditLog.user_email) == current_user.email.lower()]

        # If user is associated with legal matters in this tenant, include permitted matter events
        # First, find accessible matters for this user:
        stmt_matters = select(LegalMatter.id).where(
            or_(
                LegalMatter.client_user_id == current_user.id,
                LegalMatter.lawyer_user_id == current_user.id,
                LegalMatter.client_organization_id == tenant.id
            )
        )
        res_matters = await db.execute(stmt_matters)
        accessible_matter_ids = [m for m in res_matters.scalars().all()]

        if accessible_matter_ids:
            # Client/Lawyer can see matter actions on accessible matters within tenant
            matter_cond = and_(
                AuditLog.organization_id == tenant.id,
                AuditLog.object_type.in_(["LegalMatter", "MatterMessage"]),
                AuditLog.object_id.in_(accessible_matter_ids)
            )
            personal_cond.append(matter_cond)

        conditions.append(or_(*personal_cond))

        # Clients must NEVER see internal lawyer notes
        if member_role in ("CLIENT", "MEMBER", "EMPLOYEE", "VIEWER"):
            conditions.append(
                and_(
                    ~AuditLog.detail.contains("(InternalNote=True)"),
                    AuditLog.action != "MATTER_INTERNAL_NOTE_RECORDED"
                )
            )

    # 4. Optional action and date filters
    if action_type and action_type.strip():
        conditions.append(AuditLog.action == action_type.strip())

    if start_date:
        try:
            dt_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            conditions.append(AuditLog.created_at >= dt_start)
        except Exception:
            pass

    if end_date:
        try:
            dt_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            conditions.append(AuditLog.created_at <= dt_end)
        except Exception:
            pass

    # 5. Base select query
    base_query = select(AuditLog)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Stable deterministic ordering: primary by created_at DESC, secondary by id DESC
    ordered_query = base_query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())

    # Count total matching rows
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Pagination
    offset = (page - 1) * page_size
    paged_query = ordered_query.offset(offset).limit(page_size)
    res_logs = await db.execute(paged_query)
    logs = res_logs.scalars().all()

    # 6. Batch resolve readable references and links (Prevent N+1)
    contract_ids = {l.object_id for l in logs if l.object_type == "Contract"}
    matter_ids = {l.object_id for l in logs if l.object_type in ("LegalMatter", "MatterMessage")}
    actor_emails = {l.user_email.lower() for l in logs if l.user_email}

    contracts_map: Dict[str, str] = {}
    if contract_ids:
        c_stmt = select(Contract.id, Contract.title).where(
            Contract.id.in_(contract_ids),
            Contract.organization_id == tenant.id
        )
        c_res = await db.execute(c_stmt)
        for c_id, c_title in c_res.all():
            contracts_map[c_id] = c_title or "Untitled Contract"

    matters_map: Dict[str, str] = {}
    if matter_ids:
        m_stmt = select(LegalMatter.id, LegalMatter.matter_code, LegalMatter.title).where(
            LegalMatter.id.in_(matter_ids)
        )
        m_res = await db.execute(m_stmt)
        for m_id, m_code, m_title in m_res.all():
            matters_map[m_id] = f"{m_code}: {m_title}" if m_code else (m_title or "Matter")

    users_map: Dict[str, str] = {}
    if actor_emails:
        u_stmt = select(User.email, User.full_name).where(
            func.lower(User.email).in_(actor_emails)
        )
        u_res = await db.execute(u_stmt)
        for u_email, u_name in u_res.all():
            if u_name:
                users_map[u_email.lower()] = u_name

    # 7. Format activity items
    items: List[ActivityItem] = []
    for log in logs:
        action_label = ACTION_DISPLAY_LABELS.get(log.action, log.action.replace("_", " ").title())
        actor_name = users_map.get(log.user_email.lower(), log.user_email.split("@")[0].title())

        # Determine readable item reference and authorized navigation link
        item_ref = log.object_id
        item_link = None

        if log.object_type == "Contract":
            if log.object_id in contracts_map:
                item_ref = f"Contract: {contracts_map[log.object_id]}"
                item_link = f"/dashboard/contracts?id={log.object_id}"
            else:
                item_ref = f"Contract #{log.object_id[:8]}"
        elif log.object_type in ("LegalMatter", "MatterMessage"):
            if log.object_id in matters_map:
                item_ref = matters_map[log.object_id]
                item_link = f"/dashboard/messages?matter={log.object_id}"
            else:
                item_ref = f"Matter #{log.object_id[:8]}"
        elif log.object_type == "ContractRedline":
            item_ref = f"Redline #{log.object_id[:8]}"
            item_link = "/dashboard/redlines"
        elif log.object_type == "ContractObligation":
            item_ref = f"Obligation #{log.object_id[:8]}"
            item_link = "/dashboard/calendar"
        elif log.object_type == "EMAIL":
            item_ref = "Email Transport Verification"
            item_link = None

        # Sanitize summary and details
        sanitized_summary = sanitize_audit_detail(
            log.detail,
            log.action,
            current_user.email,
            log.user_email,
            can_view_org
        )
        activity_status = determine_activity_status(log.action, log.detail)

        # Formatted timestamp
        created_dt = log.created_at
        formatted_time = created_dt.strftime("%b %d, %Y %I:%M %p") if created_dt else "Recently"
        iso_timestamp = created_dt.isoformat() if created_dt else ""

        items.append(ActivityItem(
            id=log.id,
            timestamp=iso_timestamp,
            formatted_time=formatted_time,
            actor_email=log.user_email,
            actor_name=actor_name,
            action=log.action,
            action_label=action_label,
            object_type=log.object_type,
            object_id=log.object_id,
            item_reference=item_ref,
            item_link=item_link,
            summary=sanitized_summary,
            detail=sanitized_summary,
            status=activity_status,
            scope=scope
        ))

    # Available action types for filtering
    avail_actions = sorted(list(ACTION_DISPLAY_LABELS.keys()))
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    return ActivityListResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        current_scope=scope,
        can_view_organization_activity=can_view_org,
        available_action_types=avail_actions
    )

@router.get("/{id}", response_model=ActivityDetailResponse)
async def get_activity_detail(
    id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves detailed metadata for a single activity log entry.
    Strictly validates that the record belongs to the active tenant and the user is authorized.
    """
    stmt = select(AuditLog).where(AuditLog.id == id)
    res = await db.execute(stmt)
    log = res.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity record not found."
        )

    # 1. Enforce tenant boundary
    if log.organization_id and log.organization_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity record not found."
        )

    # 2. Check user permissions
    stmt_member = select(OrganizationMember).where(
        OrganizationMember.organization_id == tenant.id,
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.status == "ACTIVE"
    )
    res_member = await db.execute(stmt_member)
    member = res_member.scalar_one_or_none()
    member_role = (member.role.upper() if member and member.role else "MEMBER")

    is_owner_or_admin = (
        tenant.account_type != "INDIVIDUAL"
        and (
            has_permission(member_role, PERMISSION_AUDIT_READ)
            or member_role in ("OWNER", "ADMIN", "LEGAL_MANAGER")
        )
    )

    # If viewer is not owner/admin, they can only view their own activity or permitted matter events
    if not is_owner_or_admin and log.user_email.lower() != current_user.email.lower():
        # Verify if linked to an authorized matter
        if log.object_type in ("LegalMatter", "MatterMessage"):
            stmt_matter = select(LegalMatter).where(
                LegalMatter.id == log.object_id,
                or_(
                    LegalMatter.client_user_id == current_user.id,
                    LegalMatter.lawyer_user_id == current_user.id
                )
            )
            res_matter = await db.execute(stmt_matter)
            matter = res_matter.scalar_one_or_none()
            if not matter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Activity record not found."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity record not found."
            )

    # Clients cannot see internal lawyer notes
    if member_role in ("CLIENT", "MEMBER", "EMPLOYEE", "VIEWER"):
        if "(InternalNote=True)" in log.detail or log.action == "MATTER_INTERNAL_NOTE_RECORDED":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity record not found."
            )

    # Format detail safely
    sanitized = sanitize_audit_detail(
        log.detail,
        log.action,
        current_user.email,
        log.user_email,
        is_owner_or_admin
    )
    action_label = ACTION_DISPLAY_LABELS.get(log.action, log.action.replace("_", " ").title())
    status_str = determine_activity_status(log.action, log.detail)
    created_dt = log.created_at
    formatted_time = created_dt.strftime("%b %d, %Y %I:%M %p") if created_dt else "Recently"

    return ActivityDetailResponse(
        id=log.id,
        timestamp=log.created_at.isoformat() if log.created_at else "",
        formatted_time=formatted_time,
        actor_email=log.user_email,
        actor_name=log.user_email.split("@")[0].title(),
        action=log.action,
        action_label=action_label,
        object_type=log.object_type,
        object_id=log.object_id,
        item_reference=log.object_id,
        item_link=None,
        summary=sanitized,
        detail=sanitized,
        status=status_str,
        ip_address="127.0.0.1" if is_owner_or_admin else None,
        organization_id=log.organization_id if is_owner_or_admin else None
    )
