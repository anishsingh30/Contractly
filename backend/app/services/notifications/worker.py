import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.contract import Contract, ContractApprovalStep
from app.models.obligation import Obligation
from app.models.user import OrganizationMember, User
from app.services.calendar.calendar_service import parse_iso_date, calculate_notice_deadline
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.notifications.policy import (
    NotificationPriority,
    generate_deduplication_key
)

logger = logging.getLogger(__name__)

class NotificationWorker:
    @staticmethod
    async def evaluate_and_dispatch(
        db: AsyncSession,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scans all contracts and obligations for upcoming deadlines and overdue milestones.
        Dispatches idempotent notifications subject to user preferences and deduplication.
        """
        today = datetime.now(timezone.utc).date()
        today_str = today.isoformat()

        stats = {
            "evaluated_contracts": 0,
            "evaluated_obligations": 0,
            "notifications_created": 0,
            "skipped_dedup": 0,
            "errors": 0
        }

        # 1. Fetch relevant contracts
        stmt = (
            select(Contract)
            .options(
                selectinload(Contract.obligations),
                selectinload(Contract.approval_steps)
            )
        )
        if organization_id:
            stmt = stmt.where(Contract.organization_id == organization_id)

        res = await db.execute(stmt)
        contracts = res.scalars().all()
        stats["evaluated_contracts"] = len(contracts)

        for c in contracts:
            # Find default recipient users for this organization (Legal Managers / Admins)
            m_stmt = select(OrganizationMember).where(
                OrganizationMember.organization_id == c.organization_id,
                OrganizationMember.status == "ACTIVE"
            )
            m_res = await db.execute(m_stmt)
            members = m_res.scalars().all()
            recipient_user_ids = [m.user_id for m in members if m.role in ["OWNER", "ADMIN", "LEGAL_MANAGER"]]
            if not recipient_user_ids and members:
                recipient_user_ids = [members[0].user_id]

            # A. Evaluate Renewal Notice Deadline
            if c.renewal_date and c.renewal_notice_days:
                notice_dt_str = calculate_notice_deadline(c.renewal_date, c.renewal_notice_days)
                notice_d = parse_iso_date(notice_dt_str)
                if notice_d:
                    days_diff = (notice_d - today).days

                    # Trigger intervals: 30 days, 7 days, 1 day, or overdue (0 or less)
                    intervals = [30, 7, 1]
                    for iv in intervals:
                        if days_diff == iv:
                            p = NotificationPriority.CRITICAL if iv <= 7 else NotificationPriority.IMPORTANT
                            for uid in recipient_user_ids:
                                dedup = generate_deduplication_key(
                                    organization_id=c.organization_id,
                                    contract_id=c.id,
                                    event_type="RENEWAL_NOTICE",
                                    target_date=notice_dt_str,
                                    interval_marker=f"{iv}d"
                                )
                                notif, status = await NotificationDispatcher.dispatch_notification(
                                    db=db,
                                    organization_id=c.organization_id,
                                    user_id=uid,
                                    title=f"Renewal Notice Due in {iv} Days: {c.title}",
                                    message=(
                                        f"Contract notice deadline is on {notice_dt_str} ({iv} days remaining). "
                                        f"Formal notice required to prevent automatic renewal on {c.renewal_date}."
                                    ),
                                    event_type="RENEWAL_NOTICE",
                                    priority=p,
                                    deduplication_key=dedup,
                                    contract_id=c.id,
                                    contract_title=c.title,
                                    target_date=notice_dt_str
                                )
                                if status == "DELIVERED":
                                    stats["notifications_created"] += 1
                                elif status == "SKIPPED_DEDUPLICATION":
                                    stats["skipped_dedup"] += 1

                    # Imminent or overdue notice deadline
                    if days_diff <= 0:
                        for uid in recipient_user_ids:
                            dedup = generate_deduplication_key(
                                organization_id=c.organization_id,
                                contract_id=c.id,
                                event_type="RENEWAL_NOTICE",
                                target_date=notice_dt_str,
                                interval_marker="OVERDUE"
                            )
                            notif, status = await NotificationDispatcher.dispatch_notification(
                                db=db,
                                organization_id=c.organization_id,
                                user_id=uid,
                                title=f"URGENT: Renewal Notice Deadline Reached: {c.title}",
                                message=f"Renewal notice deadline was {notice_dt_str}. Immediate legal review required.",
                                event_type="RENEWAL_NOTICE",
                                priority=NotificationPriority.CRITICAL,
                                deduplication_key=dedup,
                                contract_id=c.id,
                                contract_title=c.title,
                                target_date=notice_dt_str
                            )
                            if status == "DELIVERED":
                                stats["notifications_created"] += 1
                            elif status == "SKIPPED_DEDUPLICATION":
                                stats["skipped_dedup"] += 1

            # B. Evaluate Obligations
            for ob in c.obligations:
                stats["evaluated_obligations"] += 1
                if ob.due_date and ob.status not in ["FULFILLED", "RESOLVED"]:
                    ob_d = parse_iso_date(ob.due_date)
                    if ob_d:
                        days_diff = (ob_d - today).days

                        # 7-day and 1-day reminders
                        for iv in [7, 1]:
                            if days_diff == iv:
                                for uid in recipient_user_ids:
                                    dedup = generate_deduplication_key(
                                        organization_id=c.organization_id,
                                        contract_id=c.id,
                                        event_type="OBLIGATION_DUE",
                                        target_date=ob.due_date,
                                        interval_marker=f"{ob.id}_{iv}d"
                                    )
                                    notif, status = await NotificationDispatcher.dispatch_notification(
                                        db=db,
                                        organization_id=c.organization_id,
                                        user_id=uid,
                                        title=f"Obligation Due in {iv} Day{'s' if iv > 1 else ''}: {ob.title}",
                                        message=f"Responsible party must fulfill '{ob.title}' for {c.title} by {ob.due_date}.",
                                        event_type="OBLIGATION_DUE",
                                        priority=NotificationPriority.IMPORTANT,
                                        deduplication_key=dedup,
                                        contract_id=c.id,
                                        contract_title=c.title,
                                        target_date=ob.due_date,
                                        obligation_id=ob.id
                                    )
                                    if status == "DELIVERED":
                                        stats["notifications_created"] += 1
                                    elif status == "SKIPPED_DEDUPLICATION":
                                        stats["skipped_dedup"] += 1

                        # Overdue obligation
                        if days_diff < 0:
                            for uid in recipient_user_ids:
                                dedup = generate_deduplication_key(
                                    organization_id=c.organization_id,
                                    contract_id=c.id,
                                    event_type="OBLIGATION_DUE",
                                    target_date=ob.due_date,
                                    interval_marker=f"{ob.id}_OVERDUE"
                                )
                                notif, status = await NotificationDispatcher.dispatch_notification(
                                    db=db,
                                    organization_id=c.organization_id,
                                    user_id=uid,
                                    title=f"OVERDUE Obligation: {ob.title}",
                                    message=f"Contract obligation '{ob.title}' on {c.title} was due on {ob.due_date} and is overdue.",
                                    event_type="OBLIGATION_DUE",
                                    priority=NotificationPriority.CRITICAL,
                                    deduplication_key=dedup,
                                    contract_id=c.id,
                                    contract_title=c.title,
                                    target_date=ob.due_date,
                                    obligation_id=ob.id
                                )
                                if status == "DELIVERED":
                                    stats["notifications_created"] += 1
                                elif status == "SKIPPED_DEDUPLICATION":
                                    stats["skipped_dedup"] += 1

        logger.info(f"[NotificationWorker] Completed evaluation cycle: {stats}")
        return stats

async def run_worker_standalone():
    """CLI entrypoint for standalone background worker process."""
    async with AsyncSessionLocal() as session:
        result = await NotificationWorker.evaluate_and_dispatch(session)
        print("Notification Worker Run Result:", result)

if __name__ == "__main__":
    asyncio.run(run_worker_standalone())
