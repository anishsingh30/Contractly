import logging
import secrets
import hashlib
from datetime import timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from app.config import settings
from app.core.database import get_db
from app.models.organization import Organization, Department
from app.models.user import User, OrganizationMember
from app.models.auth import OrganizationInvitation, InvitationStatus
from app.models.audit import AuditLog
from app.schemas.auth import (
    InviteMemberRequest,
    MemberResponse,
    DepartmentCreateRequest,
    DepartmentResponse,
    CreateInvitationRequest,
    InvitationResponse,
    AcceptInvitationRequest,
    DeclineInvitationRequest,
    MessageResponse
)
from app.dependencies import get_current_tenant, require_permission, get_current_active_user
from app.core.permissions import (
    PERMISSION_ORG_READ,
    PERMISSION_ORG_MANAGE,
    PERMISSION_AUDIT_READ,
    ROLE_PERMISSIONS
)
from app.core.entitlements import (
    get_account_entitlements,
    enforce_entitlement,
    is_personal_workspace
)
from app.core.security import get_password_hash
from app.models.base import utc_now, generate_uuid
from app.services.email.provider import email_service, get_email_service_health
from app.services.email.templates import render_invitation_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.get("/current")
async def get_current_org(
    tenant: Organization = Depends(get_current_tenant),
    member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_READ))
):
    sub_tier = tenant.subscription_tier or "COMMUNITY"
    entitlements = get_account_entitlements(tenant.account_type, sub_tier, member.role)
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "account_type": tenant.account_type,
        "subscription_tier": sub_tier,
        "storage_quota_bytes": tenant.storage_quota_bytes,
        "is_personal": is_personal_workspace(tenant.account_type),
        "entitlements": entitlements
    }

@router.get("/entitlements")
async def get_org_entitlements(
    tenant: Organization = Depends(get_current_tenant),
    member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_READ))
):
    """
    Returns the comprehensive, enforceable feature entitlements for the active workspace.
    """
    sub_tier = tenant.subscription_tier or "COMMUNITY"
    return get_account_entitlements(tenant.account_type, sub_tier, member.role)

@router.get("/members", response_model=List[MemberResponse])
async def list_members(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists active organization members strictly isolated to the caller's organization.
    """
    stmt = (
        select(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
        .where(
            OrganizationMember.organization_id == tenant.id,
            OrganizationMember.status == "ACTIVE"
        )
        .order_by(OrganizationMember.created_at.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    return [
        MemberResponse(
            id=mem.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=mem.role,
            status=mem.status,
            created_at=mem.created_at.isoformat() if mem.created_at else None
        )
        for mem, user in rows
    ]

@router.post("/members", response_model=MemberResponse)
async def invite_member(
    req: InviteMemberRequest,
    tenant: Organization = Depends(get_current_tenant),
    current_member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_MANAGE)),
    caller_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invites/adds a member to the organization workspace.
    Enforces feature entitlement: Personal workspaces cannot add members.
    Enforces that invited role must be a legitimate customer organization role.
    """
    sub_tier = tenant.subscription_tier or "COMMUNITY"
    enforce_entitlement(
        tenant.account_type,
        sub_tier,
        current_member.role,
        "can_invite_members",
        "Team member invitations"
    )

    # Validate target role: client cannot forge platform roles or unmapped roles
    requested_role = req.role.strip().upper()
    if requested_role not in ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid organization role '{req.role}'. Permitted roles: {list(ROLE_PERMISSIONS.keys())}"
        )

    # Check if target user exists in system
    stmt_user = select(User).where(User.email == req.email)
    res_user = await db.execute(stmt_user)
    target_user = res_user.scalar_one_or_none()

    if not target_user:
        # Create user account placeholder for invited member
        from app.core.security import get_password_hash
        # Generate random secure hash for invite until user sets password
        target_user = User(
            email=req.email,
            password_hash=get_password_hash(generate_uuid() + "!TempSecret99"),
            full_name=req.full_name or req.email.split("@")[0].capitalize(),
            is_active=True
        )
        db.add(target_user)
        await db.flush()

    # Check if already a member of this tenant
    stmt_existing = select(OrganizationMember).where(
        OrganizationMember.organization_id == tenant.id,
        OrganizationMember.user_id == target_user.id
    )
    res_existing = await db.execute(stmt_existing)
    existing_member = res_existing.scalar_one_or_none()
    if existing_member:
        if existing_member.status == "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{req.email}' is already an active member of this organization."
            )
        else:
            existing_member.status = "ACTIVE"
            existing_member.role = requested_role
            await db.commit()
            return MemberResponse(
                id=existing_member.id,
                user_id=target_user.id,
                email=target_user.email,
                full_name=target_user.full_name,
                role=existing_member.role,
                status=existing_member.status,
                created_at=existing_member.created_at.isoformat() if existing_member.created_at else None
            )

    new_member = OrganizationMember(
        organization_id=tenant.id,
        user_id=target_user.id,
        role=requested_role,
        status="ACTIVE"
    )
    db.add(new_member)
    await db.flush()

    # Record tenant audit log
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=caller_user.email,
        action="MEMBER_INVITED",
        object_type="OrganizationMember",
        object_id=new_member.id,
        detail=f"Added member {target_user.email} with role {requested_role} to {tenant.name}"
    )
    db.add(audit)
    await db.commit()

    return MemberResponse(
        id=new_member.id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=new_member.role,
        status=new_member.status,
        created_at=new_member.created_at.isoformat() if new_member.created_at else None
    )

@router.post("/invitations", response_model=InvitationResponse)
async def create_invitation(
    req: CreateInvitationRequest,
    tenant: Organization = Depends(get_current_tenant),
    current_member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_MANAGE)),
    caller_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates and dispatches an invitation to join the organization workspace.
    Enforces feature entitlement: Personal workspaces cannot invite members.
    Enforces role validation and prevents duplicate active memberships.
    """
    sub_tier = tenant.subscription_tier or "COMMUNITY"
    enforce_entitlement(
        tenant.account_type,
        sub_tier,
        current_member.role,
        "can_invite_members",
        "Team member invitations"
    )

    requested_role = req.role.strip().upper()
    if requested_role not in ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid organization role '{req.role}'. Permitted roles: {list(ROLE_PERMISSIONS.keys())}"
        )

    # Check if target user is already an active member of this organization
    u_stmt = select(User).where(User.email == req.email)
    u_res = await db.execute(u_stmt)
    existing_user = u_res.scalar_one_or_none()
    if existing_user:
        m_stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == tenant.id,
            OrganizationMember.user_id == existing_user.id,
            OrganizationMember.status == "ACTIVE"
        )
        m_res = await db.execute(m_stmt)
        if m_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{req.email}' is already an active member of this organization."
            )

    now = utc_now()
    # Revoke any previous pending invitations for this email in this org
    stmt_prev = (
        update(OrganizationInvitation)
        .where(
            OrganizationInvitation.organization_id == tenant.id,
            OrganizationInvitation.invitee_email == req.email,
            OrganizationInvitation.status == InvitationStatus.PENDING.value
        )
        .values(status=InvitationStatus.REVOKED.value)
    )
    await db.execute(stmt_prev)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = now + timedelta(days=7)
    inv_id = generate_uuid()

    invitation = OrganizationInvitation(
        id=inv_id,
        organization_id=tenant.id,
        inviter_user_id=caller_user.id,
        invitee_email=req.email,
        role=requested_role,
        token_hash=token_hash,
        expires_at=expires_at,
        status=InvitationStatus.PENDING.value
    )
    db.add(invitation)

    # Audit log
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=caller_user.email,
        action="INVITATION_CREATED",
        object_type="OrganizationInvitation",
        object_id=inv_id,
        detail=f"Created invitation for {req.email} with role {requested_role}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(invitation)

    email_health = get_email_service_health()
    email_sent = False
    delivery_status = "UNCONFIGURED"

    if email_health["configured"]:
        invite_url = f"{settings.APP_BASE_URL.rstrip('/')}/invitations/accept?token={raw_token}"
        subject, html, text = render_invitation_email(
            tenant.name,
            caller_user.full_name,
            requested_role,
            invite_url
        )
        try:
            await email_service.send_email(req.email, subject, html, text)
            email_sent = True
            delivery_status = "DELIVERED"
        except Exception as e:
            logger.warning(f"Invitation email dispatch failed: {type(e).__name__}")
            delivery_status = "FAILED"

    return InvitationResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        organization_name=tenant.name,
        invitee_email=invitation.invitee_email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at.isoformat(),
        created_at=invitation.created_at.isoformat(),
        email_sent=email_sent,
        delivery_status=delivery_status
    )

@router.get("/invitations", response_model=List[InvitationResponse])
async def list_invitations(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists pending invitations for the caller's organization tenant.
    """
    stmt = (
        select(OrganizationInvitation)
        .where(
            OrganizationInvitation.organization_id == tenant.id,
            OrganizationInvitation.status == InvitationStatus.PENDING.value
        )
        .order_by(OrganizationInvitation.created_at.desc())
    )
    res = await db.execute(stmt)
    invites = res.scalars().all()
    return [
        InvitationResponse(
            id=inv.id,
            organization_id=inv.organization_id,
            organization_name=tenant.name,
            invitee_email=inv.invitee_email,
            role=inv.role,
            status=inv.status,
            expires_at=inv.expires_at.isoformat(),
            created_at=inv.created_at.isoformat(),
            email_sent=False,
            delivery_status=None
        )
        for inv in invites
    ]

@router.post("/invitations/{invitation_id}/revoke", response_model=MessageResponse)
async def revoke_invitation(
    invitation_id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_MANAGE)),
    caller_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revokes an existing pending invitation.
    """
    stmt = select(OrganizationInvitation).where(
        OrganizationInvitation.id == invitation_id,
        OrganizationInvitation.organization_id == tenant.id
    )
    res = await db.execute(stmt)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot revoke invitation with status '{invitation.status}'."
        )

    invitation.status = InvitationStatus.REVOKED.value

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=caller_user.email,
        action="INVITATION_REVOKED",
        object_type="OrganizationInvitation",
        object_id=invitation.id,
        detail=f"Revoked invitation for {invitation.invitee_email}"
    )
    db.add(audit)
    await db.commit()

    return MessageResponse(message="Invitation successfully revoked.")

@router.get("/invitations/verify")
async def verify_invitation(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public diagnostic verification of an invitation token.
    Safe metadata only.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash)
    res = await db.execute(stmt)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    org_stmt = select(Organization).where(Organization.id == invitation.organization_id)
    org_res = await db.execute(org_stmt)
    org = org_res.scalar_one_or_none()

    is_valid = (invitation.status == InvitationStatus.PENDING.value and not invitation.is_expired)

    return {
        "valid": is_valid,
        "status": invitation.status if not invitation.is_expired else "EXPIRED",
        "organization_id": invitation.organization_id,
        "organization_name": org.name if org else "Unknown Organization",
        "invitee_email": invitation.invitee_email,
        "role": invitation.role,
        "expires_at": invitation.expires_at.isoformat()
    }

@router.post("/invitations/accept", response_model=MessageResponse)
async def accept_invitation(
    req: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts an organization invitation.
    Creates or associates user account and establishes active membership.
    """
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    now = utc_now()

    stmt = select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash)
    res = await db.execute(stmt)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=400, detail="Invalid invitation token.")

    if invitation.status == InvitationStatus.ACCEPTED.value:
        raise HTTPException(status_code=400, detail="Invitation has already been accepted.")

    if invitation.status == InvitationStatus.REVOKED.value:
        raise HTTPException(status_code=400, detail="Invitation has been revoked.")

    if invitation.status == InvitationStatus.DECLINED.value:
        raise HTTPException(status_code=400, detail="Invitation was declined.")

    if invitation.is_expired:
        invitation.status = InvitationStatus.EXPIRED.value
        await db.commit()
        raise HTTPException(status_code=400, detail="Invitation has expired.")

    # Find or create user
    u_stmt = select(User).where(User.email == invitation.invitee_email)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user:
        if not req.password:
            raise HTTPException(
                status_code=400,
                detail="Account creation requires a password to accept the invitation."
            )
        user = User(
            email=invitation.invitee_email,
            password_hash=get_password_hash(req.password),
            full_name=req.full_name or invitation.invitee_email.split("@")[0].capitalize(),
            is_active=True
        )
        db.add(user)
        await db.flush()

    # Link membership
    m_stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == invitation.organization_id,
        OrganizationMember.user_id == user.id
    )
    m_res = await db.execute(m_stmt)
    membership = m_res.scalar_one_or_none()

    if membership:
        membership.role = invitation.role
        membership.status = "ACTIVE"
    else:
        membership = OrganizationMember(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role,
            status="ACTIVE"
        )
        db.add(membership)

    invitation.status = InvitationStatus.ACCEPTED.value
    invitation.accepted_at = now

    audit = AuditLog(
        organization_id=invitation.organization_id,
        user_email=user.email,
        action="INVITATION_ACCEPTED",
        object_type="OrganizationInvitation",
        object_id=invitation.id,
        detail=f"Accepted invitation as {invitation.role}"
    )
    db.add(audit)
    await db.commit()

    return MessageResponse(message="Invitation successfully accepted. You may now access the workspace.")

@router.post("/invitations/decline", response_model=MessageResponse)
async def decline_invitation(
    req: DeclineInvitationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Declines an organization invitation.
    """
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    stmt = select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash)
    res = await db.execute(stmt)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=400, detail="Invalid invitation token.")

    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot decline invitation with status '{invitation.status}'."
        )

    invitation.status = InvitationStatus.DECLINED.value
    await db.commit()

    return MessageResponse(message="Invitation declined.")

@router.get("/departments", response_model=List[DepartmentResponse])
async def list_departments(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Department).where(Department.organization_id == tenant.id).order_by(Department.name.asc())
    res = await db.execute(stmt)
    depts = res.scalars().all()
    return [
        DepartmentResponse(
            id=d.id,
            organization_id=d.organization_id,
            name=d.name,
            budget_currency=d.budget_currency
        )
        for d in depts
    ]

@router.post("/departments", response_model=DepartmentResponse)
async def create_department(
    req: DepartmentCreateRequest,
    tenant: Organization = Depends(get_current_tenant),
    current_member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    sub_tier = tenant.subscription_tier or "COMMUNITY"
    enforce_entitlement(
        tenant.account_type,
        sub_tier,
        current_member.role,
        "can_manage_departments",
        "Department management"
    )

    new_dept = Department(
        organization_id=tenant.id,
        name=req.name,
        budget_currency=req.budget_currency
    )
    db.add(new_dept)
    await db.commit()
    await db.refresh(new_dept)
    return DepartmentResponse(
        id=new_dept.id,
        organization_id=new_dept.organization_id,
        name=new_dept.name,
        budget_currency=new_dept.budget_currency
    )

@router.get("/audit-logs")
async def list_audit_logs(
    tenant: Organization = Depends(get_current_tenant),
    member: OrganizationMember = Depends(require_permission(PERMISSION_AUDIT_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    List audit logs strictly isolated to the authenticated organization tenant.
    Enforces entitlement so personal workspaces cannot access organization audit logs.
    """
    from app.api.v1.activity import sanitize_audit_detail
    sub_tier = tenant.subscription_tier or "COMMUNITY"
    enforce_entitlement(
        tenant.account_type,
        sub_tier,
        member.role,
        "can_view_audit_logs",
        "Audit trail access"
    )

    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == tenant.id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        {
            "id": log.id,
            "organization_id": log.organization_id,
            "user_email": log.user_email,
            "action": log.action,
            "object_type": log.object_type,
            "object_id": log.object_id,
            "detail": sanitize_audit_detail(log.detail, log.action, member.user_id, log.user_email, True),
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]
