import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.config import settings
from app.models.base import utc_now, generate_uuid
from app.models.notification import Notification, UserNotificationPreference
from app.models.user import User
from app.services.email.provider import get_email_provider
from app.services.email.templates import (
    render_renewal_notice_email,
    render_overdue_obligation_email,
    render_critical_deadline_email,
    render_approval_request_email
)
from app.services.notifications.policy import (
    NotificationPriority,
    is_notification_eligible
)

logger = logging.getLogger(__name__)

class NotificationDispatcher:
    @staticmethod
    async def dispatch_notification(
        db: AsyncSession,
        organization_id: str,
        user_id: str,
        title: str,
        message: str,
        event_type: str,
        priority: str,
        deduplication_key: Optional[str] = None,
        contract_id: Optional[str] = None,
        contract_title: Optional[str] = None,
        target_date: Optional[str] = None,
        obligation_id: Optional[str] = None,
        calendar_event_id: Optional[str] = None,
        is_user_marked_important: bool = False
    ) -> Tuple[Optional[Notification], str]:
        """
        Idempotently dispatches a notification.
        Returns (notification_record, status_message).
        """
        # 1. Deduplication Check
        if deduplication_key:
            existing_stmt = select(Notification).where(
                Notification.deduplication_key == deduplication_key
            )
            existing_res = await db.execute(existing_stmt)
            if existing_res.scalars().first():
                return None, "SKIPPED_DEDUPLICATION"

        # 2. Fetch User & Preferences
        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalars().first()
        if not user or not user.is_active:
            return None, "USER_INACTIVE_OR_NOT_FOUND"

        pref_stmt = select(UserNotificationPreference).where(
            UserNotificationPreference.organization_id == organization_id,
            UserNotificationPreference.user_id == user_id
        )
        pref_res = await db.execute(pref_stmt)
        pref = pref_res.scalars().first()

        # 3. Determine Eligibility and Channel
        is_eligible, channel, reason = is_notification_eligible(
            priority=priority,
            event_type=event_type,
            email_enabled_globally=settings.EMAIL_ENABLED,
            user_pref=pref,
            is_user_marked_important=is_user_marked_important
        )

        # 4. Check Daily Email Delivery Limit (if channel includes EMAIL)
        final_channel = channel
        delivery_status = "SENT"
        provider_message_id = None
        last_error = None
        sent_at = utc_now()

        if channel in ["EMAIL", "BOTH"]:
            daily_limit = pref.daily_notification_limit if pref else 10
            cutoff = utc_now() - timedelta(days=1)
            count_stmt = select(func.count(Notification.id)).where(
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
                Notification.delivery_channel.in_(["EMAIL", "BOTH"]),
                Notification.delivery_status == "SENT",
                Notification.sent_at >= cutoff
            )
            cnt_res = await db.execute(count_stmt)
            sent_today = cnt_res.scalar_one_or_none() or 0

            if sent_today >= daily_limit and priority != NotificationPriority.CRITICAL:
                logger.warning(f"Daily notification limit reached for user {user.email}. Suppressing email.")
                final_channel = "IN_APP"
                delivery_status = "SUPPRESSED"

        # 5. Execute Email Delivery if required
        if final_channel in ["EMAIL", "BOTH"] and settings.EMAIL_ENABLED:
            target_email = (pref.preferred_notification_email if pref and pref.preferred_notification_email else user.email)
            ctr_title = contract_title or "Commercial Contract"
            dt_str = target_date or "Milestone Date"

            # Render appropriate template
            if "RENEWAL" in event_type or "NOTICE" in event_type:
                days_rem = 7 if priority == NotificationPriority.CRITICAL else 30
                html, text = render_renewal_notice_email(
                    contract_title=ctr_title,
                    days_remaining=days_rem,
                    notice_deadline=dt_str,
                    renewal_date=dt_str,
                    contract_id=contract_id or ""
                )
            elif "OBLIGATION" in event_type:
                html, text = render_overdue_obligation_email(
                    contract_title=ctr_title,
                    obligation_title=title,
                    due_date=dt_str,
                    responsible_party="Responsible Party",
                    contract_id=contract_id or ""
                )
            elif "APPROVAL" in event_type:
                html, text = render_approval_request_email(
                    contract_title=ctr_title,
                    role="Legal / Business Approver",
                    contract_id=contract_id or ""
                )
            else:
                html, text = render_critical_deadline_email(
                    contract_title=ctr_title,
                    event_title=title,
                    event_type=event_type,
                    due_date=dt_str,
                    details=message,
                    contract_id=contract_id or ""
                )

            email_provider = get_email_provider()
            res = email_provider.send_email(
                to_email=target_email,
                subject=f"[Contractly] {title}",
                html_body=html,
                text_body=text
            )

            if res.success:
                provider_message_id = res.provider_message_id
                delivery_status = "SENT"
            else:
                delivery_status = "FAILED"
                last_error = res.error_message

        # 6. Persist Notification Record
        notification = Notification(
            id=generate_uuid(),
            organization_id=organization_id,
            user_id=user_id,
            contract_id=contract_id,
            obligation_id=obligation_id,
            calendar_event_id=calendar_event_id,
            event_type=event_type,
            priority=priority,
            title=title,
            message=message,
            scheduled_at=sent_at,
            sent_at=sent_at,
            delivery_channel=final_channel,
            delivery_status=delivery_status,
            is_read=False,
            provider_message_id=provider_message_id,
            last_error=last_error,
            deduplication_key=deduplication_key
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        return notification, "DELIVERED"
