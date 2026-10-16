from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.dependencies import get_current_active_user, get_current_tenant
from app.models.user import User
from app.models.organization import Organization
from app.models.contract import Contract
from app.models.calendar import CalendarEvent
from app.models.note import ContractNote
from app.schemas.task import ThingToDoItem, ThingsToDoListResponse
from app.services.calendar.calendar_service import parse_iso_date, calculate_notice_deadline

router = APIRouter(prefix="/tasks", tags=["Things You Need to Do"])

@router.get("/things-to-do", response_model=ThingsToDoListResponse)
async def list_things_to_do(
    priority: Optional[str] = Query(None, description="Filter by priority: CRITICAL, IMPORTANT, INFORMATIONAL"),
    contract_id: Optional[str] = Query(None, description="Filter by contract ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Derives genuine, outstanding actionable responsibilities from real contracts, obligations,
    approvals, unverified extracted dates, and important notes for the active tenant.
    Never returns fabricated or hardcoded items.
    """
    today = datetime.now(timezone.utc).date()
    items: List[ThingToDoItem] = []

    # 1. Fetch contracts with obligations and approval steps
    c_stmt = (
        select(Contract)
        .where(Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.obligations),
            selectinload(Contract.approval_steps)
        )
    )
    if contract_id:
        c_stmt = c_stmt.where(Contract.id == contract_id)

    c_res = await db.execute(c_stmt)
    contracts = c_res.scalars().all()

    for c in contracts:
        # A. Pending Approval Steps
        for step in c.approval_steps:
            if step.decision == "PENDING" and c.status == "PENDING_APPROVAL":
                items.append(ThingToDoItem(
                    id=f"task-appr-{step.id}",
                    task_type="COMPLETE_APPROVAL",
                    title=f"Review & Sign-Off Contract: {c.title}",
                    contract_id=c.id,
                    contract_title=c.title,
                    counterparty=c.counterparty,
                    due_date=(today + timedelta(days=3)).isoformat(),
                    priority="CRITICAL" if step.role in ["LEGAL_MANAGER", "OWNER"] else "IMPORTANT",
                    status="PENDING",
                    responsible_role=step.role,
                    reason=f"Assigned to {step.assigned_user} ({step.role}) for formal lifecycle gate sign-off.",
                    action_type="APPROVE_STEP",
                    target_id=step.id
                ))

        # B. Pending Signature Review
        if c.status in ["PENDING_SIGNATURE", "UNDER_REVIEW"]:
            items.append(ThingToDoItem(
                id=f"task-lifecycle-{c.id}",
                task_type="REVIEW_SIGNATURE",
                title=f"Advance Contract Lifecycle: {c.title}",
                contract_id=c.id,
                contract_title=c.title,
                counterparty=c.counterparty,
                due_date=c.expiry_date,
                priority="IMPORTANT",
                status="IN_REVIEW",
                responsible_role=c.owner or "Legal Reviewer",
                reason=f"Contract is currently in '{c.status}'. Requires final terms check or counterparty signature.",
                action_type="VIEW_CONTRACT",
                target_id=c.id
            ))

        # C. Approaching Renewal Notice Deadline
        if c.renewal_date and c.renewal_notice_days:
            notice_str = calculate_notice_deadline(c.renewal_date, c.renewal_notice_days)
            notice_d = parse_iso_date(notice_str)
            if notice_d:
                days_to_notice = (notice_d - today).days
                if days_to_notice <= 30:
                    p = "CRITICAL" if days_to_notice <= 7 else "IMPORTANT"
                    st = "OVERDUE" if days_to_notice < 0 else "DUE_SOON"
                    items.append(ThingToDoItem(
                        id=f"task-renewal-notice-{c.id}",
                        task_type="CONFIRM_NOTICE_DEADLINE",
                        title=f"Address Renewal Notice Deadline: {c.title}",
                        contract_id=c.id,
                        contract_title=c.title,
                        counterparty=c.counterparty,
                        due_date=notice_str,
                        priority=p,
                        status=st,
                        responsible_role="Contract Manager",
                        reason=(
                            f"Requires formal notice {c.renewal_notice_days} days prior to {c.renewal_date}. "
                            f"{days_to_notice} days remaining before automatic rollover."
                        ),
                        action_type="VIEW_CONTRACT",
                        target_id=c.id
                    ))

        # D. Obligations Requiring Evidence or Overdue Resolution
        for ob in c.obligations:
            if ob.status not in ["FULFILLED", "RESOLVED", "WAIVED"]:
                ob_d = parse_iso_date(ob.due_date)
                is_overdue = ob_d and ob_d < today
                is_due_soon = ob_d and today <= ob_d <= today + timedelta(days=7)

                if is_overdue or ob.status == "OVERDUE":
                    items.append(ThingToDoItem(
                        id=f"task-ob-overdue-{ob.id}",
                        task_type="RESOLVE_OVERDUE_OBLIGATION",
                        title=f"Resolve Overdue Obligation: {ob.title}",
                        contract_id=c.id,
                        contract_title=c.title,
                        counterparty=c.counterparty,
                        due_date=ob.due_date,
                        priority="CRITICAL",
                        status="OVERDUE",
                        responsible_role=ob.responsible_owner or "Responsible Party",
                        reason=f"Obligation due on {ob.due_date} is overdue. Compliance documentation required.",
                        action_type="UPLOAD_EVIDENCE",
                        target_id=ob.id
                    ))
                elif is_due_soon or ob.status == "DUE_SOON":
                    items.append(ThingToDoItem(
                        id=f"task-ob-evidence-{ob.id}",
                        task_type="SUBMIT_EVIDENCE",
                        title=f"Submit Obligation Evidence: {ob.title}",
                        contract_id=c.id,
                        contract_title=c.title,
                        counterparty=c.counterparty,
                        due_date=ob.due_date,
                        priority="IMPORTANT",
                        status="DUE_SOON",
                        responsible_role=ob.responsible_owner or "Contract Manager",
                        reason=f"Compliance deadline approaching on {ob.due_date}. Upload certificate or audit evidence.",
                        action_type="UPLOAD_EVIDENCE",
                        target_id=ob.id
                    ))
                else:
                    items.append(ThingToDoItem(
                        id=f"task-ob-upcoming-{ob.id}",
                        task_type="TRACK_OBLIGATION",
                        title=f"Upcoming Obligation: {ob.title}",
                        contract_id=c.id,
                        contract_title=c.title,
                        counterparty=c.counterparty,
                        due_date=ob.due_date,
                        priority="IMPORTANT" if (ob_d and ob_d <= today + timedelta(days=30)) else "INFORMATIONAL",
                        status=ob.status or "UPCOMING",
                        responsible_role=ob.responsible_owner or "Contract Manager",
                        reason=f"Scheduled obligation due on {ob.due_date or 'unspecified date'}. Compliance tracking active.",
                        action_type="UPLOAD_EVIDENCE",
                        target_id=ob.id
                    ))

    # 2. Check for Unverified Extracted Dates or Calendar Reminders
    cal_stmt = select(CalendarEvent).where(
        CalendarEvent.organization_id == tenant.id,
        CalendarEvent.is_verified == False
    )
    if contract_id:
        cal_stmt = cal_stmt.where(CalendarEvent.contract_id == contract_id)
    cal_res = await db.execute(cal_stmt)
    unverified_events = cal_res.scalars().all()

    for ev in unverified_events:
        items.append(ThingToDoItem(
            id=f"task-verify-{ev.id}",
            task_type="VERIFY_DATE",
            title=f"Verify Extracted Date: {ev.title}",
            contract_id=ev.contract_id,
            contract_title=ev.contract.title if ev.contract else None,
            counterparty=ev.contract.counterparty if ev.contract else None,
            due_date=ev.event_date,
            priority="IMPORTANT",
            status="PENDING",
            responsible_role="Legal Reviewer",
            reason=f"Extracted by document intelligence for date {ev.event_date}. Requires human verification.",
            action_type="VERIFY_DATE",
            target_id=ev.id
        ))

    # 3. Check for Important Notes with approaching reminder dates
    note_stmt = select(ContractNote).join(Contract).where(
        ContractNote.organization_id == tenant.id,
        ContractNote.is_important == True,
        ContractNote.reminder_date != None
    )
    if contract_id:
        note_stmt = note_stmt.where(ContractNote.contract_id == contract_id)
    note_res = await db.execute(note_stmt)
    notes = note_res.scalars().all()

    for n in notes:
        n_d = parse_iso_date(n.reminder_date)
        if n_d and n_d <= today + timedelta(days=7):
            items.append(ThingToDoItem(
                id=f"task-note-{n.id}",
                task_type="IMPORTANT_NOTE",
                title=f"Follow Up on Note: {n.title or 'Contract Memo'}",
                contract_id=n.contract_id,
                contract_title=n.contract.title if n.contract else None,
                counterparty=n.contract.counterparty if n.contract else None,
                due_date=n.reminder_date,
                priority="IMPORTANT",
                status="DUE_SOON" if n_d >= today else "OVERDUE",
                responsible_role=n.author_name,
                reason=n.content[:150] + ("..." if len(n.content) > 150 else ""),
                action_type="VIEW_CONTRACT",
                target_id=n.contract_id
            ))

    # Apply filters
    filtered = items
    if priority:
        filtered = [x for x in filtered if x.priority == priority]
    if status:
        filtered = [x for x in filtered if x.status == status]

    # Sort: CRITICAL first, then by due date
    filtered.sort(key=lambda x: (
        0 if x.priority == "CRITICAL" else (1 if x.priority == "IMPORTANT" else 2),
        x.due_date or "9999-99-99"
    ))

    crit_cnt = sum(1 for x in filtered if x.priority == "CRITICAL")
    imp_cnt = sum(1 for x in filtered if x.priority == "IMPORTANT")
    distinct_contracts = {x.contract_id for x in filtered if x.contract_id}

    return ThingsToDoListResponse(
        items=filtered,
        total_count=len(filtered),
        critical_count=crit_cnt,
        important_count=imp_cnt,
        distinct_contracts_count=len(distinct_contracts)
    )

