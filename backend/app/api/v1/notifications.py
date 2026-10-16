import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update, or_, and_

from app.core.database import get_db
from app.dependencies import get_current_active_user, get_current_tenant
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.notification import Notification, UserNotificationPreference
from app.models.audit import AuditLog
from app.models.base import utc_now, generate_uuid
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    UserNotificationPreferenceResponse,
    UserNotificationPreferenceUpdate,
    TestEmailRequest,
    EvaluateWorkerResponse
)
from app.config import settings
from app.services.email.provider import get_email_provider
from app.services.email.templates import render_test_notification_email
from app.services.notifications.worker import NotificationWorker

router = APIRouter(prefix="/notifications", tags=["Intelligent Notifications"])

async def _get_user_notification_filter(user_id: str, active_tenant_id: str, db: AsyncSession):
    user_org_stmt = select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.status == "ACTIVE"
    )
    user_org_res = await db.execute(user_org_stmt)
    authorized_org_ids = set(user_org_res.scalars().all())
    authorized_org_ids.add(active_tenant_id)

    return and_(
        Notification.user_id == user_id,
        or_(
            Notification.organization_id == active_tenant_id,
            and_(
                Notification.event_type == "MATTER_MESSAGE_RECEIVED",
                Notification.organization_id.in_(authorized_org_ids)
            )
        )
    )

@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    priority: Optional[str] = Query(None, description="Filter by priority: CRITICAL, IMPORTANT, INFORMATIONAL"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Lists notifications for the authenticated user in the active tenant or direct matter messages."""
    user_filter = await _get_user_notification_filter(current_user.id, tenant.id, db)
    base_stmt = select(Notification).where(user_filter)
    if is_read is not None:
        base_stmt = base_stmt.where(Notification.is_read == is_read)
    if priority:
        base_stmt = base_stmt.where(Notification.priority == priority)

    # Count total
    count_stmt = select(func.count(Notification.id)).where(user_filter)
    if is_read is not None:
        count_stmt = count_stmt.where(Notification.is_read == is_read)
    if priority:
        count_stmt = count_stmt.where(Notification.priority == priority)
    total_res = await db.execute(count_stmt)
    total_count = total_res.scalar_one_or_none() or 0

    # Count unread total
    unread_stmt = select(func.count(Notification.id)).where(
        user_filter,
        Notification.is_read == False
    )
    unread_res = await db.execute(unread_stmt)
    unread_count = unread_res.scalar_one_or_none() or 0

    # Count unread messages (for sidebar messages badge)
    unread_msg_stmt = select(func.count(Notification.id)).where(
        user_filter,
        Notification.event_type == "MATTER_MESSAGE_RECEIVED",
        Notification.is_read == False
    )
    unread_msg_res = await db.execute(unread_msg_stmt)
    unread_messages_count = unread_msg_res.scalar_one_or_none() or 0

    # Fetch items
    stmt = base_stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    items = res.scalars().all()

    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                organization_id=n.organization_id,
                user_id=n.user_id,
                contract_id=n.contract_id,
                obligation_id=n.obligation_id,
                calendar_event_id=n.calendar_event_id,
                event_type=n.event_type,
                priority=n.priority,
                title=n.title,
                message=n.message,
                scheduled_at=n.scheduled_at,
                sent_at=n.sent_at,
                delivery_channel=n.delivery_channel,
                delivery_status=n.delivery_status,
                is_read=n.is_read,
                read_at=n.read_at,
                retry_count=n.retry_count,
                last_error=n.last_error,
                created_at=n.created_at
            )
            for n in items
        ],
        unread_count=unread_count,
        unread_messages_count=unread_messages_count,
        total_count=total_count
    )

@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Returns unread notifications count and unread messages count for active user badges."""
    user_filter = await _get_user_notification_filter(current_user.id, tenant.id, db)

    unread_stmt = select(func.count(Notification.id)).where(
        user_filter,
        Notification.is_read == False
    )
    unread_res = await db.execute(unread_stmt)
    count = unread_res.scalar_one_or_none() or 0

    unread_msg_stmt = select(func.count(Notification.id)).where(
        user_filter,
        Notification.event_type == "MATTER_MESSAGE_RECEIVED",
        Notification.is_read == False
    )
    unread_msg_res = await db.execute(unread_msg_stmt)
    msg_count = unread_msg_res.scalar_one_or_none() or 0

    return {
        "unread_count": count,
        "unread_messages_count": msg_count
    }

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Marks a single notification as read."""
    user_filter = await _get_user_notification_filter(current_user.id, tenant.id, db)
    stmt = select(Notification).where(
        Notification.id == notification_id,
        user_filter
    )
    res = await db.execute(stmt)
    n = res.scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    n.is_read = True
    n.read_at = utc_now()
    await db.commit()
    await db.refresh(n)

    return NotificationResponse(
        id=n.id,
        organization_id=n.organization_id,
        user_id=n.user_id,
        contract_id=n.contract_id,
        obligation_id=n.obligation_id,
        calendar_event_id=n.calendar_event_id,
        event_type=n.event_type,
        priority=n.priority,
        title=n.title,
        message=n.message,
        scheduled_at=n.scheduled_at,
        sent_at=n.sent_at,
        delivery_channel=n.delivery_channel,
        delivery_status=n.delivery_status,
        is_read=n.is_read,
        read_at=n.read_at,
        retry_count=n.retry_count,
        last_error=n.last_error,
        created_at=n.created_at
    )

@router.post("/mark-all-read")
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Marks all notifications as read for the user in the active tenant or authorized matters."""
    now = utc_now()
    user_filter = await _get_user_notification_filter(current_user.id, tenant.id, db)
    stmt = (
        update(Notification)
        .where(
            user_filter,
            Notification.is_read == False
        )
        .values(is_read=True, read_at=now)
    )
    await db.execute(stmt)
    await db.commit()
    return {"message": "All notifications marked as read."}

@router.get("/preferences", response_model=UserNotificationPreferenceResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Gets the notification preferences for the current user, seeding defaults if needed."""
    stmt = select(UserNotificationPreference).where(
        UserNotificationPreference.organization_id == tenant.id,
        UserNotificationPreference.user_id == current_user.id
    )
    res = await db.execute(stmt)
    pref = res.scalar_one_or_none()

    if not pref:
        pref = UserNotificationPreference(
            id=generate_uuid(),
            organization_id=tenant.id,
            user_id=current_user.id,
            email_notifications_enabled=False,
            renewal_reminders=True,
            notice_deadline_reminders=True,
            obligation_reminders=True,
            approval_reminders=True,
            critical_events_enabled=True,
            reminder_intervals_json="[30, 7, 1]",
            daily_notification_limit=10,
            quiet_hours_enabled=False,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            preferred_notification_email=current_user.email
        )
        db.add(pref)
        await db.commit()
        await db.refresh(pref)

    intervals = [30, 7, 1]
    try:
        intervals = json.loads(pref.reminder_intervals_json)
    except Exception:
        pass

    email_active = bool(settings.EMAIL_ENABLED)
    provider_status = f"Active ({settings.EMAIL_PROVIDER.upper()})" if email_active else "Disabled in environment (EMAIL_ENABLED=false)"

    return UserNotificationPreferenceResponse(
        id=pref.id,
        organization_id=pref.organization_id,
        user_id=pref.user_id,
        email_notifications_enabled=pref.email_notifications_enabled,
        renewal_reminders=pref.renewal_reminders,
        notice_deadline_reminders=pref.notice_deadline_reminders,
        obligation_reminders=pref.obligation_reminders,
        approval_reminders=pref.approval_reminders,
        critical_events_enabled=pref.critical_events_enabled,
        reminder_intervals=intervals,
        daily_notification_limit=pref.daily_notification_limit,
        quiet_hours_enabled=pref.quiet_hours_enabled,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        preferred_notification_email=pref.preferred_notification_email,
        email_service_enabled=email_active,
        email_provider_status=provider_status,
        created_at=pref.created_at,
        updated_at=pref.updated_at
    )

@router.put("/preferences", response_model=UserNotificationPreferenceResponse)
@router.patch("/preferences", response_model=UserNotificationPreferenceResponse)
async def update_notification_preferences(
    req: UserNotificationPreferenceUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Updates the user's notification preferences with validation and audit logging."""
    stmt = select(UserNotificationPreference).where(
        UserNotificationPreference.organization_id == tenant.id,
        UserNotificationPreference.user_id == current_user.id
    )
    res = await db.execute(stmt)
    pref = res.scalar_one_or_none()

    if not pref:
        pref = UserNotificationPreference(
            id=generate_uuid(),
            organization_id=tenant.id,
            user_id=current_user.id
        )
        db.add(pref)

    if req.email_notifications_enabled is not None:
        pref.email_notifications_enabled = req.email_notifications_enabled
    if req.renewal_reminders is not None:
        pref.renewal_reminders = req.renewal_reminders
    if req.notice_deadline_reminders is not None:
        pref.notice_deadline_reminders = req.notice_deadline_reminders
    if req.obligation_reminders is not None:
        pref.obligation_reminders = req.obligation_reminders
    if req.approval_reminders is not None:
        pref.approval_reminders = req.approval_reminders
    if req.critical_events_enabled is not None:
        pref.critical_events_enabled = req.critical_events_enabled
    if req.reminder_intervals is not None:
        pref.reminder_intervals_json = json.dumps(req.reminder_intervals)
    if req.daily_notification_limit is not None:
        pref.daily_notification_limit = max(1, min(100, req.daily_notification_limit))
    if req.quiet_hours_enabled is not None:
        pref.quiet_hours_enabled = req.quiet_hours_enabled
    if req.quiet_hours_start is not None:
        pref.quiet_hours_start = req.quiet_hours_start
    if req.quiet_hours_end is not None:
        pref.quiet_hours_end = req.quiet_hours_end
    if req.preferred_notification_email is not None:
        pref.preferred_notification_email = str(req.preferred_notification_email)

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="UPDATE_NOTIFICATION_PREFERENCES",
        object_type="NOTIFICATION_PREFERENCE",
        object_id=pref.id,
        detail=f"Updated notification preferences (email_enabled={pref.email_notifications_enabled})",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(pref)

    intervals = [30, 7, 1]
    try:
        intervals = json.loads(pref.reminder_intervals_json)
    except Exception:
        pass

    email_active = bool(settings.EMAIL_ENABLED)
    provider_status = f"Active ({settings.EMAIL_PROVIDER.upper()})" if email_active else "Disabled in environment (EMAIL_ENABLED=false)"

    return UserNotificationPreferenceResponse(
        id=pref.id,
        organization_id=pref.organization_id,
        user_id=pref.user_id,
        email_notifications_enabled=pref.email_notifications_enabled,
        renewal_reminders=pref.renewal_reminders,
        notice_deadline_reminders=pref.notice_deadline_reminders,
        obligation_reminders=pref.obligation_reminders,
        approval_reminders=pref.approval_reminders,
        critical_events_enabled=pref.critical_events_enabled,
        reminder_intervals=intervals,
        daily_notification_limit=pref.daily_notification_limit,
        quiet_hours_enabled=pref.quiet_hours_enabled,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        preferred_notification_email=pref.preferred_notification_email,
        email_service_enabled=email_active,
        email_provider_status=provider_status,
        created_at=pref.created_at,
        updated_at=pref.updated_at
    )

@router.post("/test-email")
async def send_test_email(
    req: TestEmailRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Sends an authorized administrative test email to verify transport configuration.
    Fails safely if email is disabled or misconfigured.
    """
    recipient = str(req.recipient_email) if req.recipient_email else current_user.email
    html, text = render_test_notification_email(recipient)

    email_provider = get_email_provider()
    res = email_provider.send_email(
        to_email=recipient,
        subject="[Contractly] Administrative Test Email",
        html_body=html,
        text_body=text
    )

    status_label = "Accepted by provider" if res.success else "Delivery rejected by upstream provider"
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="TEST_EMAIL_DISPATCH",
        object_type="EMAIL",
        object_id=res.provider_message_id or "none",
        detail=f"Test email dispatch to {recipient} (Status: {status_label}; success={res.success})",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()

    if not res.success:
        return {
            "success": False,
            "message": res.error_message or "Email dispatch failed. Please check environment configuration.",
            "recipient": recipient
        }

    return {
        "success": True,
        "message": f"Test email successfully dispatched to {recipient}.",
        "provider_message_id": res.provider_message_id,
        "recipient": recipient
    }

@router.post("/evaluate-and-dispatch", response_model=EvaluateWorkerResponse)
async def trigger_worker_evaluation(
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers an idempotent evaluation cycle for the active tenant's contracts,
    deadlines, and obligations.
    """
    stats = await NotificationWorker.evaluate_and_dispatch(db, organization_id=tenant.id)
    return EvaluateWorkerResponse(
        evaluated_contracts=stats.get("evaluated_contracts", 0),
        evaluated_obligations=stats.get("evaluated_obligations", 0),
        notifications_created=stats.get("notifications_created", 0),
        skipped_dedup=stats.get("skipped_dedup", 0),
        errors=stats.get("errors", 0)
    )
