from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.contract import Contract, ContractApprovalStep
from app.models.obligation import Obligation
from app.models.calendar import CalendarEvent

def parse_iso_date(date_str: Optional[str]) -> Optional[date]:
    """Safely parses YYYY-MM-DD or ISO timestamp into a date object."""
    if not date_str:
        return None
    cleaned = str(date_str).strip()
    # If contains 'T' or space, take just date part
    if "T" in cleaned:
        cleaned = cleaned.split("T")[0]
    elif " " in cleaned:
        cleaned = cleaned.split(" ")[0]
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").date()
    except Exception:
        return None

def calculate_notice_deadline(target_date_str: Optional[str], notice_days: Optional[int]) -> Optional[str]:
    """
    Computes formal notice deadline = target_date - notice_days.
    Returns ISO string 'YYYY-MM-DD' or None.
    """
    dt = parse_iso_date(target_date_str)
    if not dt or notice_days is None or notice_days <= 0:
        return None
    deadline = dt - timedelta(days=int(notice_days))
    return deadline.isoformat()

@dataclass
class UnifiedCalendarEvent:
    id: str
    organization_id: str
    contract_id: Optional[str]
    contract_title: Optional[str]
    counterparty: Optional[str]
    obligation_id: Optional[str]
    title: str
    description: Optional[str]
    event_type: str
    event_date: str  # YYYY-MM-DD
    priority: str    # CRITICAL, IMPORTANT, INFORMATIONAL
    status: str      # UPCOMING, DUE_SOON, OVERDUE, COMPLETED, CANCELLED
    source_type: str # CONTRACT_LIFECYCLE, OBLIGATION, CALCULATED_REMINDER, USER_CUSTOM, INTELLIGENCE
    is_verified: bool
    is_important: bool
    is_custom: bool

class CalendarService:
    @staticmethod
    async def get_organization_events(
        db: AsyncSession,
        organization_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        contract_id: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None
    ) -> List[UnifiedCalendarEvent]:
        """
        Gathers both database-persisted custom calendar events and dynamic contractual lifecycle
        deadlines for the tenant, performing deduplication and status evaluation.
        """
        today = datetime.now(timezone.utc).date()
        start_d = parse_iso_date(start_date)
        end_d = parse_iso_date(end_date)

        # 1. Fetch persisted custom events from calendar_events table
        custom_stmt = select(CalendarEvent).where(
            CalendarEvent.organization_id == organization_id
        )
        if contract_id:
            custom_stmt = custom_stmt.where(CalendarEvent.contract_id == contract_id)
        if category:
            custom_stmt = custom_stmt.where(CalendarEvent.event_type == category)
        if priority:
            custom_stmt = custom_stmt.where(CalendarEvent.priority == priority)

        custom_res = await db.execute(custom_stmt)
        persisted_events = custom_res.scalars().all()

        results: List[UnifiedCalendarEvent] = []
        dedup_keys = set()

        for ev in persisted_events:
            ev_date = parse_iso_date(ev.event_date)
            if not ev_date:
                continue
            if start_d and ev_date < start_d:
                continue
            if end_d and ev_date > end_d:
                continue

            # Determine dynamic status if not already completed/cancelled
            st = ev.status
            if st not in ["COMPLETED", "CANCELLED"]:
                if ev_date < today:
                    st = "OVERDUE"
                elif today <= ev_date <= today + timedelta(days=7):
                    st = "DUE_SOON"
                else:
                    st = "UPCOMING"

            contract_title = ev.contract.title if ev.contract else None
            counterparty = ev.contract.counterparty if ev.contract else None

            key = f"{ev.contract_id}:{ev.event_type}:{ev.event_date}"
            dedup_keys.add(key)

            results.append(UnifiedCalendarEvent(
                id=ev.id,
                organization_id=ev.organization_id,
                contract_id=ev.contract_id,
                contract_title=contract_title,
                counterparty=counterparty,
                obligation_id=ev.obligation_id,
                title=ev.title,
                description=ev.description,
                event_type=ev.event_type,
                event_date=ev.event_date,
                priority=ev.priority,
                status=st,
                source_type=ev.source_type,
                is_verified=ev.is_verified,
                is_important=ev.is_important,
                is_custom=True
            ))

        # 2. Fetch active Contracts for the organization
        c_stmt = (
            select(Contract)
            .where(Contract.organization_id == organization_id)
            .options(selectinload(Contract.obligations), selectinload(Contract.approval_steps))
        )
        if contract_id:
            c_stmt = c_stmt.where(Contract.id == contract_id)

        c_res = await db.execute(c_stmt)
        contracts = c_res.scalars().all()

        for c in contracts:
            # A. Contract Effective Date
            if c.start_date:
                key = f"{c.id}:CONTRACT_EFFECTIVE:{c.start_date}"
                if key not in dedup_keys:
                    d = parse_iso_date(c.start_date)
                    if d and (not start_d or d >= start_d) and (not end_d or d <= end_d):
                        if not category or category == "CONTRACT_EFFECTIVE":
                            p = "INFORMATIONAL"
                            st = "COMPLETED" if d < today else "UPCOMING"
                            results.append(UnifiedCalendarEvent(
                                id=f"derived-{c.id}-effective",
                                organization_id=c.organization_id,
                                contract_id=c.id,
                                contract_title=c.title,
                                counterparty=c.counterparty,
                                obligation_id=None,
                                title=f"Contract Effective: {c.title}",
                                description=f"Agreement commencement date for {c.title} with {c.counterparty}.",
                                event_type="CONTRACT_EFFECTIVE",
                                event_date=c.start_date,
                                priority=p,
                                status=st,
                                source_type="CONTRACT_LIFECYCLE",
                                is_verified=True,
                                is_important=False,
                                is_custom=False
                            ))

            # B. Renewal Notice Deadline
            if c.renewal_date and c.renewal_notice_days:
                notice_dt = calculate_notice_deadline(c.renewal_date, c.renewal_notice_days)
                if notice_dt:
                    key = f"{c.id}:RENEWAL_NOTICE:{notice_dt}"
                    if key not in dedup_keys:
                        d = parse_iso_date(notice_dt)
                        if d and (not start_d or d >= start_d) and (not end_d or d <= end_d):
                            if not category or category == "RENEWAL_NOTICE":
                                p = "CRITICAL" if d <= today + timedelta(days=7) else "IMPORTANT"
                                st = "OVERDUE" if d < today else ("DUE_SOON" if d <= today + timedelta(days=7) else "UPCOMING")
                                results.append(UnifiedCalendarEvent(
                                    id=f"derived-{c.id}-renewal-notice",
                                    organization_id=c.organization_id,
                                    contract_id=c.id,
                                    contract_title=c.title,
                                    counterparty=c.counterparty,
                                    obligation_id=None,
                                    title=f"Renewal Notice Deadline: {c.title}",
                                    description=(
                                        f"Requires {c.renewal_notice_days} days prior notice before {c.renewal_date} "
                                        f"to terminate or negotiate non-renewal."
                                    ),
                                    event_type="RENEWAL_NOTICE",
                                    event_date=notice_dt,
                                    priority=p,
                                    status=st,
                                    source_type="CALCULATED_REMINDER",
                                    is_verified=True,
                                    is_important=True,
                                    is_custom=False
                                ))

            # C. Renewal Date
            if c.renewal_date:
                key = f"{c.id}:CONTRACT_RENEWAL:{c.renewal_date}"
                if key not in dedup_keys:
                    d = parse_iso_date(c.renewal_date)
                    if d and (not start_d or d >= start_d) and (not end_d or d <= end_d):
                        if not category or category == "CONTRACT_RENEWAL":
                            p = "IMPORTANT"
                            st = "OVERDUE" if d < today else ("DUE_SOON" if d <= today + timedelta(days=7) else "UPCOMING")
                            results.append(UnifiedCalendarEvent(
                                id=f"derived-{c.id}-renewal",
                                organization_id=c.organization_id,
                                contract_id=c.id,
                                contract_title=c.title,
                                counterparty=c.counterparty,
                                obligation_id=None,
                                title=f"Contract Renewal: {c.title}",
                                description=f"Scheduled renewal milestone for {c.title}. Auto-renew is {'enabled' if c.auto_renew else 'disabled'}.",
                                event_type="CONTRACT_RENEWAL",
                                event_date=c.renewal_date,
                                priority=p,
                                status=st,
                                source_type="CONTRACT_LIFECYCLE",
                                is_verified=True,
                                is_important=False,
                                is_custom=False
                            ))

            # D. Expiry Date (Contract End Date)
            if c.expiry_date:
                key = f"{c.id}:CONTRACT_EXPIRY:{c.expiry_date}"
                if key not in dedup_keys:
                    d = parse_iso_date(c.expiry_date)
                    if d and (not start_d or d >= start_d) and (not end_d or d <= end_d):
                        if not category or category == "CONTRACT_EXPIRY":
                            p = "CRITICAL" if d <= today + timedelta(days=30) else "IMPORTANT"
                            st = "OVERDUE" if d < today else ("DUE_SOON" if d <= today + timedelta(days=7) else "UPCOMING")
                            results.append(UnifiedCalendarEvent(
                                id=f"derived-{c.id}-expiry",
                                organization_id=c.organization_id,
                                contract_id=c.id,
                                contract_title=c.title,
                                counterparty=c.counterparty,
                                obligation_id=None,
                                title=f"Contract End Date: {c.title}",
                                description=f"Final expiration and end of term date for {c.title}.",
                                event_type="CONTRACT_EXPIRY",
                                event_date=c.expiry_date,
                                priority=p,
                                status=st,
                                source_type="CONTRACT_LIFECYCLE",
                                is_verified=True,
                                is_important=(p == "CRITICAL" or p == "IMPORTANT"),
                                is_custom=False
                            ))

            # E. Termination Notice Deadline
            if c.expiry_date and c.termination_notice_days:
                term_notice_dt = calculate_notice_deadline(c.expiry_date, c.termination_notice_days)
                if term_notice_dt:
                    key = f"{c.id}:TERMINATION_NOTICE:{term_notice_dt}"
                    if key not in dedup_keys:
                        d = parse_iso_date(term_notice_dt)
                        if d and (not start_d or d >= start_d) and (not end_d or d <= end_d):
                            if not category or category == "TERMINATION_NOTICE":
                                p = "CRITICAL" if d <= today + timedelta(days=7) else "IMPORTANT"
                                st = "OVERDUE" if d < today else ("DUE_SOON" if d <= today + timedelta(days=7) else "UPCOMING")
                                results.append(UnifiedCalendarEvent(
                                    id=f"derived-{c.id}-term-notice",
                                    organization_id=c.organization_id,
                                    contract_id=c.id,
                                    contract_title=c.title,
                                    counterparty=c.counterparty,
                                    obligation_id=None,
                                    title=f"Termination Notice Deadline: {c.title}",
                                    description=f"{c.termination_notice_days} days prior notice required before {c.expiry_date} to terminate for convenience.",
                                    event_type="TERMINATION_NOTICE",
                                    event_date=term_notice_dt,
                                    priority=p,
                                    status=st,
                                    source_type="CALCULATED_REMINDER",
                                    is_verified=True,
                                    is_important=True,
                                    is_custom=False
                                ))

            # F. Contract Termination Date (if formally set)
            if c.termination_date:
                key = f"{c.id}:CONTRACT_TERMINATION:{c.termination_date}"
                if key not in dedup_keys:
                    d = parse_iso_date(c.termination_date)
                    if d and (not start_d or d >= start_d) and (not end_d or d <= end_d):
                        if not category or category == "CONTRACT_TERMINATION":
                            results.append(UnifiedCalendarEvent(
                                id=f"derived-{c.id}-termination",
                                organization_id=c.organization_id,
                                contract_id=c.id,
                                contract_title=c.title,
                                counterparty=c.counterparty,
                                obligation_id=None,
                                title=f"Contract Terminated: {c.title}",
                                description=f"Early termination execution date. Reason: {c.termination_reason or 'Not specified'}",
                                event_type="CONTRACT_TERMINATION",
                                event_date=c.termination_date,
                                priority="CRITICAL",
                                status="COMPLETED",
                                source_type="CONTRACT_LIFECYCLE",
                                is_verified=True,
                                is_important=True,
                                is_custom=False
                            ))

            # G. Obligations
            for ob in c.obligations:
                if ob.due_date:
                    key = f"{c.id}:OBLIGATION_DUE:{ob.due_date}:{ob.id}"
                    if key not in dedup_keys:
                        d = parse_iso_date(ob.due_date)
                        if d and (not start_d or d >= start_d) and (not end_d or d <= end_d):
                            ev_type = "PAYMENT_DEADLINE" if "pay" in ob.title.lower() or "invoice" in ob.title.lower() else "OBLIGATION_DUE"
                            if not category or category == ev_type or category == "OBLIGATION_DUE":
                                st = ob.status
                                if ob.status not in ["FULFILLED", "RESOLVED"]:
                                    if d < today:
                                        st = "OVERDUE"
                                    elif today <= d <= today + timedelta(days=7):
                                        st = "DUE_SOON"
                                    else:
                                        st = "UPCOMING"
                                p = "CRITICAL" if st == "OVERDUE" else ("IMPORTANT" if st == "DUE_SOON" else "INFORMATIONAL")
                                results.append(UnifiedCalendarEvent(
                                    id=f"derived-ob-{ob.id}",
                                    organization_id=c.organization_id,
                                    contract_id=c.id,
                                    contract_title=c.title,
                                    counterparty=c.counterparty,
                                    obligation_id=ob.id,
                                    title=f"Obligation Due: {ob.title}",
                                    description=ob.description,
                                    event_type=ev_type,
                                    event_date=ob.due_date,
                                    priority=p,
                                    status=st,
                                    source_type="OBLIGATION",
                                    is_verified=True,
                                    is_important=(p == "CRITICAL" or p == "IMPORTANT"),
                                    is_custom=False
                                ))

            # H. Pending Approvals
            for step in c.approval_steps:
                if step.decision == "PENDING" and c.status == "PENDING_APPROVAL":
                    # If contract has an expiry or 7-day default approval target
                    appr_target = (today + timedelta(days=3)).isoformat()
                    key = f"{c.id}:APPROVAL_DEADLINE:{step.id}"
                    if key not in dedup_keys:
                        if not category or category == "APPROVAL_DEADLINE":
                            results.append(UnifiedCalendarEvent(
                                id=f"derived-appr-{step.id}",
                                organization_id=c.organization_id,
                                contract_id=c.id,
                                contract_title=c.title,
                                counterparty=c.counterparty,
                                obligation_id=None,
                                title=f"Approval Deadline ({step.role}): {c.title}",
                                description=f"Pending approval sign-off assigned to {step.assigned_user} ({step.role}).",
                                event_type="APPROVAL_DEADLINE",
                                event_date=appr_target,
                                priority="IMPORTANT",
                                status="DUE_SOON",
                                source_type="CONTRACT_LIFECYCLE",
                                is_verified=True,
                                is_important=True,
                                is_custom=False
                            ))

        # Sort chronologically by event_date, prioritizing contract milestones (end date, renewal, notice) before obligations
        def event_sort_key(ev: UnifiedCalendarEvent):
            type_rank = 0 if ev.event_type in ("CONTRACT_EXPIRY", "CONTRACT_RENEWAL", "RENEWAL_NOTICE", "TERMINATION_NOTICE") else 1
            priority_rank = 0 if ev.priority == "CRITICAL" else (1 if ev.priority == "IMPORTANT" else 2)
            return (ev.event_date, type_rank, priority_rank, ev.title)

        results.sort(key=event_sort_key)
        return results
