import os
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract
from app.models.obligation import Obligation, ObligationEvidence
from app.models.audit import AuditLog
from app.schemas.obligation import (
    ObligationResponse,
    ObligationEvidenceResponse,
    ObligationCreateRequest,
    ObligationStatusUpdateRequest,
)
from app.dependencies import get_current_tenant, get_current_active_user, require_permission
from app.core.permissions import (
    PERMISSION_OBLIGATIONS_READ,
    PERMISSION_OBLIGATIONS_CREATE,
    PERMISSION_OBLIGATIONS_UPDATE,
    PERMISSION_OBLIGATIONS_UPLOAD_EVIDENCE
)
from app.services.storage import storage_client
from app.core.upload_validator import read_and_validate_upload, EVIDENCE_ALLOWED_EXTENSIONS
from app.config import settings

router = APIRouter(tags=["Obligations"])

def apply_deterministic_overdue(obligations: List[Obligation]) -> List[Obligation]:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for o in obligations:
        if o.due_date and o.due_date < today_str and o.status not in ("FULFILLED", "RESOLVED", "WAIVED", "COMPLETED"):
            o.status = "OVERDUE"
    return obligations

@router.get("/obligations", response_model=List[ObligationResponse])
async def list_all_tenant_obligations(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_OBLIGATIONS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    List all obligations across all contracts belonging to this tenant organization.
    Powers the global Contract Watch & Compliance monitor.
    """
    stmt = (
        select(Obligation)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id)
        .options(selectinload(Obligation.evidence))
        .order_by(Obligation.due_date.asc())
    )
    res = await db.execute(stmt)
    return apply_deterministic_overdue(res.scalars().all())

@router.get("/contracts/{contract_id}/obligations", response_model=List[ObligationResponse])
async def list_contract_obligations(
    contract_id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_OBLIGATIONS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    List obligations for a specific contract.
    """
    contract_stmt = select(Contract).where(
        Contract.id == contract_id,
        Contract.organization_id == tenant.id
    )
    c_res = await db.execute(contract_stmt)
    contract = c_res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    stmt = (
        select(Obligation)
        .where(Obligation.contract_id == contract_id)
        .options(selectinload(Obligation.evidence))
        .order_by(Obligation.due_date.asc())
    )
    res = await db.execute(stmt)
    return apply_deterministic_overdue(res.scalars().all())

@router.post("/contracts/{contract_id}/obligations", response_model=ObligationResponse)
async def create_obligation(
    contract_id: str,
    data: ObligationCreateRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_OBLIGATIONS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new obligation for a contract.
    """
    contract_stmt = select(Contract).where(
        Contract.id == contract_id,
        Contract.organization_id == tenant.id
    )
    c_res = await db.execute(contract_stmt)
    contract = c_res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    obligation = Obligation(
        contract_id=contract.id,
        obligor_party=data.obligor_party,
        obligee_party=data.obligee_party,
        title=data.title,
        description=data.description,
        due_date=data.due_date,
        frequency=data.frequency,
        penalty_clause=data.penalty_clause,
        responsible_owner=data.responsible_owner,
        status=data.status
    )
    db.add(obligation)

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="OBLIGATION_CREATED",
        object_type="OBLIGATION",
        object_id=obligation.id,
        detail=f"Created obligation '{obligation.title}' on contract {contract.contract_id}."
    )
    db.add(audit)
    await db.commit()
    await db.refresh(obligation)

    # Reload with evidence relationship
    stmt = (
        select(Obligation)
        .where(Obligation.id == obligation.id)
        .options(selectinload(Obligation.evidence))
    )
    res = await db.execute(stmt)
    return res.scalar_one()

@router.patch("/obligations/{obligation_id}/status", response_model=ObligationResponse)
async def update_obligation_status(
    obligation_id: str,
    data: ObligationStatusUpdateRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_OBLIGATIONS_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Update status of an obligation (e.g. FULFILLED, AT_RISK, RESOLVED).
    """
    stmt = (
        select(Obligation)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(
            Obligation.id == obligation_id,
            Contract.organization_id == tenant.id
        )
        .options(selectinload(Obligation.evidence))
    )
    res = await db.execute(stmt)
    obligation = res.scalar_one_or_none()
    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    obligation.status = data.status
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="OBLIGATION_STATUS_UPDATED",
        object_type="OBLIGATION",
        object_id=obligation.id,
        detail=f"Updated obligation status to {data.status}."
    )
    db.add(audit)
    await db.commit()
    await db.refresh(obligation)
    return obligation

@router.post("/obligations/{obligation_id}/evidence", response_model=ObligationEvidenceResponse)
async def upload_obligation_evidence(
    obligation_id: str,
    file: UploadFile = File(...),
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_OBLIGATIONS_UPLOAD_EVIDENCE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload compliance evidence document for an obligation.
    """
    stmt = (
        select(Obligation)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(
            Obligation.id == obligation_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    obligation = res.scalar_one_or_none()
    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    file_bytes, safe_evidence_name, _mime = await read_and_validate_upload(
        file=file,
        max_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        allowed_extensions=EVIDENCE_ALLOWED_EXTENSIONS,
        strict_signature=False
    )
    evidence_rel_path = f"{tenant.id}/evidence/{obligation_id}/{safe_evidence_name}"
    storage_client.save_file(evidence_rel_path, file_bytes, tenant_id=tenant.id)

    evidence = ObligationEvidence(
        obligation_id=obligation.id,
        file_name=file.filename,
        file_storage_path=evidence_rel_path,
        uploaded_by=user.full_name if user else "Legal Team",
        status="UNDER_REVIEW"
    )
    db.add(evidence)
    await db.flush()

    # Automatically set obligation status to FULFILLED or UNDER_REVIEW
    obligation.status = "FULFILLED"

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email if user else "system@contractly.internal",
        action="EVIDENCE_UPLOADED",
        object_type="OBLIGATION_EVIDENCE",
        object_id=evidence.id,
        detail=f"Uploaded evidence '{file.filename}' for obligation '{obligation.title}'."
    )
    db.add(audit)
    await db.commit()
    await db.refresh(evidence)
    return evidence


@router.get("/obligations/{obligation_id}/evidence/{evidence_id}/download")
async def download_obligation_evidence(
    obligation_id: str,
    evidence_id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_OBLIGATIONS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    Securely download obligation compliance evidence document.
    Enforces tenant boundaries, read permissions, and directory traversal defense.
    """
    stmt = (
        select(ObligationEvidence)
        .join(Obligation, ObligationEvidence.obligation_id == Obligation.id)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(
            Obligation.id == obligation_id,
            ObligationEvidence.id == evidence_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    evidence = res.scalar_one_or_none()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence record not found.")

    try:
        content = storage_client.get_file(evidence.file_storage_path, tenant_id=tenant.id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evidence file not found in storage.")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    safe_filename = "".join(c for c in (evidence.file_name or "evidence.pdf") if c.isalnum() or c in "._- ")

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff"
        }
    )
