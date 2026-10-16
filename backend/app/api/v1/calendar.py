from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies import get_current_active_user, get_current_tenant
from app.models.user import User
from app.models.organization import Organization
from app.models.contract import Contract
from app.models.obligation import Obligation
from app.models.calendar import CalendarEvent
from app.models.audit import AuditLog
from app.models.base import generate_uuid
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse
)
from app.services.calendar.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["Contract Calendar"])

@router.get("/events", response_model=List[CalendarEventResponse])
async def list_calendar_events(
    start_date: Optional[str] = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date filter YYYY-MM-DD"),
    contract_id: Optional[str] = Query(None, description="Filter by contract ID"),
    category: Optional[str] = Query(None, description="Filter by event category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all contractual deadlines and user-created custom calendar events for the active tenant.
    Performs tenant isolation, automatic date-math derivation, and deduplication.
    """
    events = await CalendarService.get_organization_events(
        db=db,
        organization_id=tenant.id,
        start_date=start_date,
        end_date=end_date,
        contract_id=contract_id,
        category=category,
        priority=priority
    )
    return [
        CalendarEventResponse(
            id=ev.id,
            organization_id=ev.organization_id,
            contract_id=ev.contract_id,
            contract_title=ev.contract_title,
            counterparty=ev.counterparty,
            obligation_id=ev.obligation_id,
            title=ev.title,
            description=ev.description,
            event_type=ev.event_type,
            event_date=ev.event_date,
            priority=ev.priority,
            status=ev.status,
            source_type=ev.source_type,
            is_verified=ev.is_verified,
            is_important=ev.is_important,
            is_custom=ev.is_custom
        )
        for ev in events
    ]

@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar_event(
    req: CalendarEventCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates an explicit custom calendar event for a contract or general legal milestone.
    Enforces strict tenant isolation for linked contracts or obligations.
    """
    # 1. Validate contract association
    contract_title = None
    counterparty = None
    if req.contract_id:
        c_stmt = select(Contract).where(
            Contract.id == req.contract_id,
            Contract.organization_id == tenant.id
        )
        c_res = await db.execute(c_stmt)
        contract = c_res.scalar_one_or_none()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced contract not found in active organization tenant."
            )
        contract_title = contract.title
        counterparty = contract.counterparty

    # 2. Validate obligation association
    if req.obligation_id:
        ob_stmt = select(Obligation).join(Contract).where(
            Obligation.id == req.obligation_id,
            Contract.organization_id == tenant.id
        )
        ob_res = await db.execute(ob_stmt)
        obligation = ob_res.scalar_one_or_none()
        if not obligation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced obligation not found in active organization tenant."
            )

    new_id = generate_uuid()
    new_event = CalendarEvent(
        id=new_id,
        organization_id=tenant.id,
        contract_id=req.contract_id,
        obligation_id=req.obligation_id,
        title=req.title,
        description=req.description,
        event_type=req.event_type,
        event_date=req.event_date,
        priority=req.priority,
        status="UPCOMING",
        source_type="USER_CUSTOM",
        is_verified=True,
        is_important=req.is_important,
        created_by_user_id=current_user.id
    )
    db.add(new_event)

    # Audit log
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="CREATE_CALENDAR_EVENT",
        object_type="CALENDAR_EVENT",
        object_id=new_id,
        detail=f"Created custom calendar event '{req.title}' for date {req.event_date}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(new_event)

    return CalendarEventResponse(
        id=new_event.id,
        organization_id=new_event.organization_id,
        contract_id=new_event.contract_id,
        contract_title=contract_title,
        counterparty=counterparty,
        obligation_id=new_event.obligation_id,
        title=new_event.title,
        description=new_event.description,
        event_type=new_event.event_type,
        event_date=new_event.event_date,
        priority=new_event.priority,
        status=new_event.status,
        source_type=new_event.source_type,
        is_verified=new_event.is_verified,
        is_important=new_event.is_important,
        is_custom=True,
        created_at=new_event.created_at,
        updated_at=new_event.updated_at
    )

@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_calendar_event(
    event_id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves a single calendar event with tenant verification."""
    # Check if this is a derived lifecycle event
    if event_id.startswith("derived-"):
        all_events = await CalendarService.get_organization_events(db, tenant.id)
        for ev in all_events:
            if ev.id == event_id:
                return CalendarEventResponse(
                    id=ev.id,
                    organization_id=ev.organization_id,
                    contract_id=ev.contract_id,
                    contract_title=ev.contract_title,
                    counterparty=ev.counterparty,
                    obligation_id=ev.obligation_id,
                    title=ev.title,
                    description=ev.description,
                    event_type=ev.event_type,
                    event_date=ev.event_date,
                    priority=ev.priority,
                    status=ev.status,
                    source_type=ev.source_type,
                    is_verified=ev.is_verified,
                    is_important=ev.is_important,
                    is_custom=ev.is_custom
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found.")

    stmt = select(CalendarEvent).where(
        CalendarEvent.id == event_id,
        CalendarEvent.organization_id == tenant.id
    )
    res = await db.execute(stmt)
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found.")

    return CalendarEventResponse(
        id=ev.id,
        organization_id=ev.organization_id,
        contract_id=ev.contract_id,
        contract_title=ev.contract.title if ev.contract else None,
        counterparty=ev.contract.counterparty if ev.contract else None,
        obligation_id=ev.obligation_id,
        title=ev.title,
        description=ev.description,
        event_type=ev.event_type,
        event_date=ev.event_date,
        priority=ev.priority,
        status=ev.status,
        source_type=ev.source_type,
        is_verified=ev.is_verified,
        is_important=ev.is_important,
        is_custom=True,
        created_at=ev.created_at,
        updated_at=ev.updated_at
    )

@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: str,
    req: CalendarEventUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Updates a calendar event, such as marking completed, verified, or important."""
    stmt = select(CalendarEvent).where(
        CalendarEvent.id == event_id,
        CalendarEvent.organization_id == tenant.id
    )
    res = await db.execute(stmt)
    ev = res.scalar_one_or_none()

    if not ev:
        # If derived event, instantiate a persisted override record
        if event_id.startswith("derived-"):
            all_events = await CalendarService.get_organization_events(db, tenant.id)
            matched = next((e for e in all_events if e.id == event_id), None)
            if not matched:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found.")
            ev = CalendarEvent(
                id=generate_uuid(),
                organization_id=tenant.id,
                contract_id=matched.contract_id,
                obligation_id=matched.obligation_id,
                title=req.title or matched.title,
                description=req.description or matched.description,
                event_type=matched.event_type,
                event_date=req.event_date or matched.event_date,
                priority=req.priority or matched.priority,
                status=req.status or matched.status,
                source_type="CALCULATED_REMINDER",
                is_verified=req.is_verified if req.is_verified is not None else matched.is_verified,
                is_important=req.is_important if req.is_important is not None else matched.is_important,
                created_by_user_id=current_user.id
            )
            db.add(ev)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found.")
    else:
        if req.title is not None:
            ev.title = req.title
        if req.description is not None:
            ev.description = req.description
        if req.event_date is not None:
            ev.event_date = req.event_date
        if req.priority is not None:
            ev.priority = req.priority
        if req.status is not None:
            ev.status = req.status
        if req.is_verified is not None:
            ev.is_verified = req.is_verified
        if req.is_important is not None:
            ev.is_important = req.is_important

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="UPDATE_CALENDAR_EVENT",
        object_type="CALENDAR_EVENT",
        object_id=ev.id,
        detail=f"Updated calendar event '{ev.title}' (status={ev.status}, priority={ev.priority})",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(ev)

    return CalendarEventResponse(
        id=ev.id,
        organization_id=ev.organization_id,
        contract_id=ev.contract_id,
        contract_title=ev.contract.title if ev.contract else None,
        counterparty=ev.contract.counterparty if ev.contract else None,
        obligation_id=ev.obligation_id,
        title=ev.title,
        description=ev.description,
        event_type=ev.event_type,
        event_date=ev.event_date,
        priority=ev.priority,
        status=ev.status,
        source_type=ev.source_type,
        is_verified=ev.is_verified,
        is_important=ev.is_important,
        is_custom=True,
        created_at=ev.created_at,
        updated_at=ev.updated_at
    )

@router.delete("/events/{event_id}", status_code=status.HTTP_200_OK)
async def delete_calendar_event(
    event_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Cancels or deletes a calendar event with tenant verification."""
    stmt = select(CalendarEvent).where(
        CalendarEvent.id == event_id,
        CalendarEvent.organization_id == tenant.id
    )
    res = await db.execute(stmt)
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found.")

    await db.delete(ev)
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="DELETE_CALENDAR_EVENT",
        object_type="CALENDAR_EVENT",
        object_id=event_id,
        detail=f"Removed calendar event '{ev.title}'",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()

    return {"message": "Calendar event deleted successfully."}
