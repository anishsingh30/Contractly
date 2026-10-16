from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies import get_current_active_user, get_current_tenant, get_current_member
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.contract import Contract
from app.models.note import ContractNote
from app.models.audit import AuditLog
from app.models.base import generate_uuid
from app.schemas.note import (
    ContractNoteCreate,
    ContractNoteUpdate,
    ContractNoteResponse
)

router = APIRouter(prefix="/contracts/{contract_id}/notes", tags=["Contract Notes"])

@router.get("", response_model=List[ContractNoteResponse])
async def list_contract_notes(
    contract_id: str,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Lists all persistent notes associated with a contract for the active tenant."""
    # Validate contract tenant ownership
    c_stmt = select(Contract).where(Contract.id == contract_id, Contract.organization_id == tenant.id)
    c_res = await db.execute(c_stmt)
    contract = c_res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found in active organization.")

    stmt = (
        select(ContractNote)
        .where(
            ContractNote.contract_id == contract_id,
            ContractNote.organization_id == tenant.id
        )
        .order_by(ContractNote.created_at.desc())
    )
    res = await db.execute(stmt)
    notes = res.scalars().all()
    return notes

@router.post("", response_model=ContractNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_contract_note(
    contract_id: str,
    req: ContractNoteCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Creates a persistent note on a contract with optional reminder date and importance flag."""
    c_stmt = select(Contract).where(Contract.id == contract_id, Contract.organization_id == tenant.id)
    c_res = await db.execute(c_stmt)
    contract = c_res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found in active organization.")

    new_id = generate_uuid()
    note = ContractNote(
        id=new_id,
        organization_id=tenant.id,
        contract_id=contract_id,
        author_user_id=current_user.id,
        author_name=current_user.full_name,
        title=req.title,
        content=req.content,
        reminder_date=req.reminder_date,
        is_important=req.is_important,
        calendar_event_id=req.calendar_event_id,
        obligation_id=req.obligation_id
    )
    db.add(note)

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="CREATE_CONTRACT_NOTE",
        object_type="CONTRACT_NOTE",
        object_id=new_id,
        detail=f"Added note to contract '{contract.title}' (important={req.is_important})",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(note)

    return note

@router.patch("/{note_id}", response_model=ContractNoteResponse)
async def update_contract_note(
    contract_id: str,
    note_id: str,
    req: ContractNoteUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    membership: OrganizationMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db)
):
    """Updates an existing note. Only the author or organization admins/managers may edit notes."""
    stmt = select(ContractNote).where(
        ContractNote.id == note_id,
        ContractNote.contract_id == contract_id,
        ContractNote.organization_id == tenant.id
    )
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract note not found.")

    if note.author_user_id != current_user.id and membership.role not in ["OWNER", "ADMIN", "LEGAL_MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit notes created by yourself."
        )

    if req.title is not None:
        note.title = req.title
    if req.content is not None:
        note.content = req.content
    if req.reminder_date is not None:
        note.reminder_date = req.reminder_date
    if req.is_important is not None:
        note.is_important = req.is_important

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="UPDATE_CONTRACT_NOTE",
        object_type="CONTRACT_NOTE",
        object_id=note_id,
        detail=f"Updated note {note_id} on contract {contract_id}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(note)

    return note

@router.delete("/{note_id}", status_code=status.HTTP_200_OK)
async def delete_contract_note(
    contract_id: str,
    note_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    membership: OrganizationMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db)
):
    """Deletes an existing note. Permitted for the author or organization admins."""
    stmt = select(ContractNote).where(
        ContractNote.id == note_id,
        ContractNote.contract_id == contract_id,
        ContractNote.organization_id == tenant.id
    )
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract note not found.")

    if note.author_user_id != current_user.id and membership.role not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete notes created by yourself."
        )

    await db.delete(note)
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=current_user.email,
        action="DELETE_CONTRACT_NOTE",
        object_type="CONTRACT_NOTE",
        object_id=note_id,
        detail=f"Deleted note {note_id} on contract {contract_id}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    await db.commit()

    return {"message": "Contract note deleted successfully."}
