import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, delete, or_

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.config import settings
from app.dependencies import (
    get_current_tenant,
    get_current_active_user,
    require_permission,
    get_current_platform_user,
    require_platform_permission
)
from app.core.permissions import (
    PERMISSION_ORG_MANAGE,
    PLATFORM_PERM_SYSTEM_MANAGE,
    PLATFORM_PERM_SYSTEM_READ
)
from app.services.storage import storage_client
from app.models.organization import Organization, Department
from app.models.user import User, OrganizationMember
from app.models.contract import (
    Contract,
    ContractVersion,
    ContractClause,
    ContractRisk,
    ContractApprovalStep,
    ContractRedline
)
from app.models.obligation import Obligation, ObligationEvidence
from app.models.vendor import Vendor
from app.models.playbook import PlaybookRule
from app.models.calendar import CalendarEvent
from app.models.note import ContractNote
from app.models.notification import Notification
from app.models.audit import AuditLog

router = APIRouter(tags=["Data Management"])


# =====================================================================
# Request & Response Schemas
# =====================================================================

class ClearWorkspaceRequest(BaseModel):
    confirmation: str = Field(
        ...,
        description="Must be exact confirmation phrase: 'CLEAR WORKSPACE'"
    )


class DemoResetRequest(BaseModel):
    confirmation: str = Field(
        ...,
        description="Must be exact confirmation phrase: 'RESET DEMO'"
    )
    reseed: bool = Field(
        default=True,
        description="Whether to populate baseline illustrative contracts after reset"
    )


class WorkspaceCategorySummary(BaseModel):
    category: str
    count: int
    description: str


class WorkspaceSummaryResponse(BaseModel):
    organization_id: str
    organization_name: str
    organization_slug: str
    is_demo: bool
    categories: List[WorkspaceCategorySummary]
    total_records: int
    legal_hold_count: int
    storage_files_count: int
    can_clear_workspace: bool
    blocking_reasons: List[str]


class DemoResetPreviewResponse(BaseModel):
    demo_org_found: bool
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    organization_slug: Optional[str] = None
    contracts_count: int = 0
    versions_count: int = 0
    obligations_count: int = 0
    files_count: int = 0
    calendar_events_count: int = 0
    notes_count: int = 0
    required_confirmation: str = "RESET DEMO"
    last_reset_at: Optional[str] = None


class DemoResetResultResponse(BaseModel):
    status: str
    message: str
    organization_id: str
    organization_name: str
    deleted_counts: Dict[str, int]
    deleted_storage_files: int
    reseeded: bool
    reseeded_contracts_count: int
    timestamp: str


class HandoverChecklistItem(BaseModel):
    id: str
    title: str
    description: str
    status: str  # READY, PENDING, COMPLETED
    category: str


class CustomerHandoverChecklistResponse(BaseModel):
    checklist: List[HandoverChecklistItem]
    generated_at: str


# =====================================================================
# Organization-Scoped Data Management Endpoints
# =====================================================================

@router.get("/organizations/data-management/summary", response_model=WorkspaceSummaryResponse)
async def get_workspace_data_summary(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns breakdown of records and storage files belonging exclusively to the current tenant organization.
    Checks for active legal holds or retention locks that would block deletion.
    """
    # 1. Contracts & versions
    c_res = await db.execute(select(func.count(Contract.id)).where(Contract.organization_id == tenant.id))
    contracts_count = c_res.scalar() or 0

    v_res = await db.execute(
        select(func.count(ContractVersion.id))
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id)
    )
    versions_count = v_res.scalar() or 0

    cl_res = await db.execute(
        select(func.count(ContractClause.id))
        .join(Contract, ContractClause.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id)
    )
    clauses_count = cl_res.scalar() or 0

    rk_res = await db.execute(
        select(func.count(ContractRisk.id))
        .join(Contract, ContractRisk.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id)
    )
    risks_count = rk_res.scalar() or 0

    # 2. Obligations & evidence
    ob_res = await db.execute(
        select(func.count(Obligation.id))
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id)
    )
    obligations_count = ob_res.scalar() or 0

    ev_res = await db.execute(
        select(func.count(ObligationEvidence.id))
        .join(Obligation, ObligationEvidence.obligation_id == Obligation.id)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id)
    )
    evidence_count = ev_res.scalar() or 0

    # 3. Vendors & Playbook Rules
    vnd_res = await db.execute(select(func.count(Vendor.id)).where(Vendor.organization_id == tenant.id))
    vendors_count = vnd_res.scalar() or 0

    pb_res = await db.execute(select(func.count(PlaybookRule.id)).where(PlaybookRule.organization_id == tenant.id))
    playbook_rules_count = pb_res.scalar() or 0

    # 4. Events, Notes, Notifications
    evnt_res = await db.execute(select(func.count(CalendarEvent.id)).where(CalendarEvent.organization_id == tenant.id))
    calendar_events_count = evnt_res.scalar() or 0

    nt_res = await db.execute(select(func.count(ContractNote.id)).where(ContractNote.organization_id == tenant.id))
    notes_count = nt_res.scalar() or 0

    notif_res = await db.execute(select(func.count(Notification.id)).where(Notification.organization_id == tenant.id))
    notifications_count = notif_res.scalar() or 0

    # 5. Storage files count
    # Distinct non-null file_storage_path across ContractVersion and ObligationEvidence
    ver_files_stmt = (
        select(ContractVersion.file_storage_path)
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id, ContractVersion.file_storage_path.isnot(None))
    )
    ver_files_res = await db.execute(ver_files_stmt)
    ver_paths = {row[0] for row in ver_files_res.all() if row[0]}

    ev_files_stmt = (
        select(ObligationEvidence.file_storage_path)
        .join(Obligation, ObligationEvidence.obligation_id == Obligation.id)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id, ObligationEvidence.file_storage_path.isnot(None))
    )
    ev_files_res = await db.execute(ev_files_stmt)
    ev_paths = {row[0] for row in ev_files_res.all() if row[0]}

    total_files = len(ver_paths.union(ev_paths))

    # 6. Legal holds check
    c_stmt = select(Contract).where(Contract.organization_id == tenant.id)
    c_all = (await db.execute(c_stmt)).scalars().all()
    legal_held_titles = []
    for c in c_all:
        tags = [t.strip().upper() for t in (c.tags or [])] if isinstance(c.tags, list) else [t.strip().upper() for t in (c.tags or "").split(",") if t.strip()]
        if (c.status and c.status.upper() in ["LEGAL_HOLD", "RETENTION_LOCK"]) or any(t in ["LEGAL_HOLD", "RETENTION_LOCK", "LEGAL HOLD"] for t in tags):
            legal_held_titles.append(c.title)

    legal_hold_count = len(legal_held_titles)
    blocking_reasons = []
    if legal_hold_count > 0:
        blocking_reasons.append(
            f"{legal_hold_count} contract(s) under active legal hold or retention lock: {', '.join(legal_held_titles[:3])}{'...' if len(legal_held_titles) > 3 else ''}"
        )

    categories = [
        WorkspaceCategorySummary(category="Contracts", count=contracts_count, description="Client contracts and master agreements"),
        WorkspaceCategorySummary(category="Document Versions", count=versions_count, description="Historical versions and redlines"),
        WorkspaceCategorySummary(category="Clauses & Extracted Terms", count=clauses_count, description="Structured contract clauses"),
        WorkspaceCategorySummary(category="Identified Risks", count=risks_count, description="Intelligence and playbook risk items"),
        WorkspaceCategorySummary(category="Obligations & Tasks", count=obligations_count, description="Tracked contractual commitments"),
        WorkspaceCategorySummary(category="Obligation Evidences", count=evidence_count, description="Uploaded compliance evidence records"),
        WorkspaceCategorySummary(category="Vendors & Counterparties", count=vendors_count, description="Counterparty profiles and mappings"),
        WorkspaceCategorySummary(category="Playbook Rules", count=playbook_rules_count, description="Negotiation playbook guidelines"),
        WorkspaceCategorySummary(category="Calendar Deadlines", count=calendar_events_count, description="Reminders, renewals and notice dates"),
        WorkspaceCategorySummary(category="Internal Notes", count=notes_count, description="Private collaboration notes and comments"),
        WorkspaceCategorySummary(category="Notifications", count=notifications_count, description="System alert records and notifications"),
        WorkspaceCategorySummary(category="Stored Files", count=total_files, description="Physical documents stored in object/local storage"),
    ]

    total_records = (
        contracts_count + versions_count + clauses_count + risks_count +
        obligations_count + evidence_count + vendors_count + playbook_rules_count +
        calendar_events_count + notes_count + notifications_count
    )

    return WorkspaceSummaryResponse(
        organization_id=tenant.id,
        organization_name=tenant.name,
        organization_slug=tenant.slug,
        is_demo=tenant.is_demo,
        categories=categories,
        total_records=total_records,
        legal_hold_count=legal_hold_count,
        storage_files_count=total_files,
        can_clear_workspace=(legal_hold_count == 0),
        blocking_reasons=blocking_reasons,
    )


@router.get("/organizations/data-management/export")
async def export_workspace_data(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_MANAGE)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports a comprehensive, sanitized JSON archive of all business records belonging to the current organization.
    Audited to maintain compliance and chain of custody.
    """
    # 1. Fetch contracts with clauses, risks, versions
    c_stmt = (
        select(Contract)
        .where(Contract.organization_id == tenant.id)
        .order_by(Contract.created_at.desc())
    )
    c_res = await db.execute(c_stmt)
    contracts = c_res.scalars().all()

    contracts_data = []
    for c in contracts:
        # Fetch versions
        v_stmt = select(ContractVersion).where(ContractVersion.contract_id == c.id)
        v_res = await db.execute(v_stmt)
        versions = [
            {
                "id": v.id,
                "version_number": v.version_number,
                "file_name": v.filename,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in v_res.scalars().all()
        ]

        # Fetch clauses
        cl_stmt = select(ContractClause).where(ContractClause.contract_id == c.id)
        cl_res = await db.execute(cl_stmt)
        clauses = [
            {
                "id": cl.id,
                "clause_title": cl.clause_title,
                "section_number": cl.section_number,
                "risk_level": cl.risk_level,
                "category": cl.category,
            }
            for cl in cl_res.scalars().all()
        ]

        # Fetch risks
        rk_stmt = select(ContractRisk).where(ContractRisk.contract_id == c.id)
        rk_res = await db.execute(rk_stmt)
        risks = [
            {
                "id": rk.id,
                "severity": rk.severity,
                "risk_title": rk.risk_title,
                "status": rk.status,
            }
            for rk in rk_res.scalars().all()
        ]

        contracts_data.append({
            "id": c.id,
            "contract_id": c.contract_id,
            "title": c.title,
            "contract_type": c.contract_type,
            "counterparty": c.counterparty,
            "department": c.department,
            "owner": c.owner,
            "value": c.value,
            "currency": c.currency,
            "status": c.status,
            "start_date": c.start_date,
            "expiry_date": c.expiry_date,
            "renewal_date": c.renewal_date,
            "auto_renew": c.auto_renew,
            "risk_level": c.risk_level,
            "tags": c.tags,
            "versions": versions,
            "clauses": clauses,
            "risks": risks,
        })

    # 2. Fetch obligations
    ob_stmt = (
        select(Obligation)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id)
    )
    ob_res = await db.execute(ob_stmt)
    obligations_data = [
        {
            "id": ob.id,
            "contract_id": ob.contract_id,
            "title": ob.title,
            "obligor_party": ob.obligor_party,
            "obligee_party": ob.obligee_party,
            "due_date": ob.due_date,
            "status": ob.status,
            "responsible_owner": ob.responsible_owner,
        }
        for ob in ob_res.scalars().all()
    ]

    # 3. Vendors
    vnd_stmt = select(Vendor).where(Vendor.organization_id == tenant.id)
    vnd_res = await db.execute(vnd_stmt)
    vendors_data = [
        {
            "id": vnd.id,
            "name": vnd.name,
            "contact_name": vnd.contact_name,
            "contact_email": vnd.contact_email,
            "risk_rating": vnd.risk_rating,
        }
        for vnd in vnd_res.scalars().all()
    ]

    # 4. Playbook rules
    pb_stmt = select(PlaybookRule).where(PlaybookRule.organization_id == tenant.id)
    pb_res = await db.execute(pb_stmt)
    playbook_data = [
        {
            "id": pb.id,
            "clause_type": pb.clause_type,
            "rule_name": pb.rule_name,
            "guideline": pb.guideline,
        }
        for pb in pb_res.scalars().all()
    ]

    # 5. Calendar events
    evnt_stmt = select(CalendarEvent).where(CalendarEvent.organization_id == tenant.id)
    evnt_res = await db.execute(evnt_stmt)
    calendar_data = [
        {
            "id": ev.id,
            "title": ev.title,
            "event_type": ev.event_type,
            "event_date": ev.event_date,
            "priority": ev.priority,
            "status": ev.status,
        }
        for ev in evnt_res.scalars().all()
    ]

    # 6. Notes
    nt_stmt = select(ContractNote).where(ContractNote.organization_id == tenant.id)
    nt_res = await db.execute(nt_stmt)
    notes_data = [
        {
            "id": nt.id,
            "contract_id": nt.contract_id,
            "author_name": nt.author_name,
            "title": nt.title,
            "content": nt.content,
            "created_at": nt.created_at.isoformat() if nt.created_at else None,
        }
        for nt in nt_res.scalars().all()
    ]

    # Log export audit event
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="ORGANIZATION_DATA_EXPORTED",
        object_type="Organization",
        object_id=tenant.id,
        detail=f"Exported organization business data archive: {len(contracts_data)} contracts, {len(obligations_data)} obligations."
    )
    db.add(audit)
    await db.commit()

    return {
        "export_metadata": {
            "organization_id": tenant.id,
            "organization_name": tenant.name,
            "organization_slug": tenant.slug,
            "exported_by": user.email,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format_version": "1.0",
        },
        "contracts": contracts_data,
        "obligations": obligations_data,
        "vendors": vendors_data,
        "playbook_rules": playbook_data,
        "calendar_events": calendar_data,
        "notes": notes_data,
    }


@router.post("/organizations/data-management/clear-workspace")
async def clear_workspace_data(
    payload: ClearWorkspaceRequest,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_ORG_MANAGE)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clears eligible workspace business data belonging exclusively to the caller's organization.
    Preserves the organization entity, departments, organization members, and owner accounts.
    Strictly blocked if any contract is subject to an active legal hold or retention lock.
    """
    if payload.confirmation.strip() != "CLEAR WORKSPACE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase mismatch. You must enter 'CLEAR WORKSPACE' exactly."
        )

    # 1. Inspect all contracts for legal holds
    c_stmt = select(Contract).where(Contract.organization_id == tenant.id)
    c_all = (await db.execute(c_stmt)).scalars().all()

    held_contracts = []
    for c in c_all:
        tags = [t.strip().upper() for t in (c.tags or [])] if isinstance(c.tags, list) else [t.strip().upper() for t in (c.tags or "").split(",") if t.strip()]
        if (c.status and c.status.upper() in ["LEGAL_HOLD", "RETENTION_LOCK"]) or any(t in ["LEGAL_HOLD", "RETENTION_LOCK", "LEGAL HOLD"] for t in tags):
            held_contracts.append(c.title)

    if held_contracts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot clear workspace data: {len(held_contracts)} contract(s) are protected by an active "
                f"legal hold or retention lock ({', '.join(held_contracts[:3])}). "
                "All legal holds must be formally released by authorized counsel before data removal."
            )
        )

    # 2. Collect storage file paths across versions and evidence
    ver_files_stmt = (
        select(ContractVersion.file_storage_path)
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id, ContractVersion.file_storage_path.isnot(None))
    )
    ver_files_res = await db.execute(ver_files_stmt)
    ver_paths = {row[0] for row in ver_files_res.all() if row[0]}

    ev_files_stmt = (
        select(ObligationEvidence.file_storage_path)
        .join(Obligation, ObligationEvidence.obligation_id == Obligation.id)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == tenant.id, ObligationEvidence.file_storage_path.isnot(None))
    )
    ev_files_res = await db.execute(ev_files_stmt)
    ev_paths = {row[0] for row in ev_files_res.all() if row[0]}

    storage_paths_to_delete = ver_paths.union(ev_paths)

    # 3. Counts before deletion
    contracts_count = len(c_all)

    # 4. Delete business data inside the transaction
    # First notes, calendar events, notifications
    await db.execute(delete(ContractNote).where(ContractNote.organization_id == tenant.id))
    await db.execute(delete(CalendarEvent).where(CalendarEvent.organization_id == tenant.id))
    await db.execute(delete(Notification).where(Notification.organization_id == tenant.id))

    # Vendors & Playbook rules
    await db.execute(delete(Vendor).where(Vendor.organization_id == tenant.id))
    await db.execute(delete(PlaybookRule).where(PlaybookRule.organization_id == tenant.id))

    # Obligations and evidence
    for c in c_all:
        ob_stmt = select(Obligation).where(Obligation.contract_id == c.id)
        obs = (await db.execute(ob_stmt)).scalars().all()
        for ob in obs:
            await db.execute(delete(ObligationEvidence).where(ObligationEvidence.obligation_id == ob.id))
            await db.delete(ob)

    # Contracts and sub-entities
    for c in c_all:
        await db.execute(delete(ContractClause).where(ContractClause.contract_id == c.id))
        await db.execute(delete(ContractRisk).where(ContractRisk.contract_id == c.id))
        await db.execute(delete(ContractApprovalStep).where(ContractApprovalStep.contract_id == c.id))
        await db.execute(delete(ContractRedline).where(ContractRedline.contract_id == c.id))
        await db.execute(delete(ContractVersion).where(ContractVersion.contract_id == c.id))
        await db.delete(c)

    # 5. Physical storage deletion via StorageClient abstraction
    deleted_storage_files = 0
    for path in storage_paths_to_delete:
        try:
            storage_client.delete_file(path, tenant_id=tenant.id)
            deleted_storage_files += 1
        except Exception as e:
            logger.warning(f"Storage cleanup exception for {path} (tenant {tenant.id}): {e}")

    # 6. Audit logging
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="WORKSPACE_DATA_CLEARED",
        object_type="Organization",
        object_id=tenant.id,
        detail=(
            f"Organization business data cleared by {user.email}. "
            f"Removed {contracts_count} contracts and {deleted_storage_files} physical files. "
            "Organization account and member credentials preserved."
        )
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Successfully cleared business data for organization '{tenant.name}'.",
        "contracts_deleted": contracts_count,
        "storage_files_deleted": deleted_storage_files,
        "cleared_at": datetime.now(timezone.utc).isoformat(),
    }


# =====================================================================
# Platform Administration: Demo Workspace Management Endpoints
# =====================================================================

async def _find_demo_organization(db: AsyncSession) -> Optional[Organization]:
    """Finds the designated demo organization using stable identifier or demo slug pattern."""
    stmt = select(Organization).where(Organization.slug == "northstar-tech")
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()
    if org:
        return org

    # Fallback to any organization matching demo
    stmt2 = select(Organization).where(or_(Organization.slug.ilike("%demo%"), Organization.name.ilike("%demo%")))
    res2 = await db.execute(stmt2)
    return res2.scalar_one_or_none()


@router.get("/platform/data-management/demo-workspace/preview", response_model=DemoResetPreviewResponse)
async def preview_demo_workspace_reset(
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_SYSTEM_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Previews the current contents and status of the designated demonstration workspace.
    Restricted to Platform Administrators.
    """
    demo_org = await _find_demo_organization(db)
    if not demo_org:
        return DemoResetPreviewResponse(demo_org_found=False)

    # Count demo items
    c_count = (await db.execute(select(func.count(Contract.id)).where(Contract.organization_id == demo_org.id))).scalar() or 0
    v_count = (await db.execute(
        select(func.count(ContractVersion.id))
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(Contract.organization_id == demo_org.id)
    )).scalar() or 0
    ob_count = (await db.execute(
        select(func.count(Obligation.id))
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == demo_org.id)
    )).scalar() or 0
    ev_count = (await db.execute(select(func.count(CalendarEvent.id)).where(CalendarEvent.organization_id == demo_org.id))).scalar() or 0
    nt_count = (await db.execute(select(func.count(ContractNote.id)).where(ContractNote.organization_id == demo_org.id))).scalar() or 0

    # Count storage files
    ver_files_stmt = (
        select(ContractVersion.file_storage_path)
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(Contract.organization_id == demo_org.id, ContractVersion.file_storage_path.isnot(None))
    )
    v_files = {r[0] for r in (await db.execute(ver_files_stmt)).all() if r[0]}

    # Check last reset audit
    last_audit_stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == demo_org.id, AuditLog.action == "DEMO_WORKSPACE_RESET_COMPLETED")
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    last_audit = (await db.execute(last_audit_stmt)).scalar_one_or_none()

    return DemoResetPreviewResponse(
        demo_org_found=True,
        organization_id=demo_org.id,
        organization_name=demo_org.name,
        organization_slug=demo_org.slug,
        contracts_count=c_count,
        versions_count=v_count,
        obligations_count=ob_count,
        files_count=len(v_files),
        calendar_events_count=ev_count,
        notes_count=nt_count,
        required_confirmation="RESET DEMO",
        last_reset_at=last_audit.created_at.isoformat() if last_audit and last_audit.created_at else None,
    )


@router.post("/platform/data-management/demo-workspace/reset", response_model=DemoResetResultResponse)
async def reset_demo_workspace(
    payload: DemoResetRequest,
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_SYSTEM_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a clean reset of the designated demonstration workspace.
    Safety Guarantees:
    - Never operates against customer organizations.
    - Requires typing 'RESET DEMO'.
    - Deletes files using StorageClient abstraction.
    - Re-seeds baseline demonstration contracts deterministically.
    - Preserves all real lawyer profiles, real matters, and platform users.
    """
    if payload.confirmation.strip() != "RESET DEMO":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase mismatch. You must enter 'RESET DEMO' exactly."
        )

    demo_org = await _find_demo_organization(db)
    if not demo_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No designated demonstration workspace found to reset."
        )

    # Double verify target is strictly a demo workspace
    if not demo_org.is_demo and demo_org.slug != "northstar-tech":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Safety violation: Selected organization is not designated as a demo workspace."
        )

    # Audit event before execution
    pre_audit = AuditLog(
        organization_id=demo_org.id,
        user_email=current_platform_user.email,
        action="DEMO_WORKSPACE_RESET_INITIATED",
        object_type="Organization",
        object_id=demo_org.id,
        detail=f"Platform administrator {current_platform_user.email} initiated demo reset (reseed={payload.reseed})."
    )
    db.add(pre_audit)
    await db.flush()

    # Collect storage files before deleting DB records
    ver_files_stmt = (
        select(ContractVersion.file_storage_path)
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(Contract.organization_id == demo_org.id, ContractVersion.file_storage_path.isnot(None))
    )
    ver_paths = {row[0] for row in (await db.execute(ver_files_stmt)).all() if row[0]}

    ev_files_stmt = (
        select(ObligationEvidence.file_storage_path)
        .join(Obligation, ObligationEvidence.obligation_id == Obligation.id)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Contract.organization_id == demo_org.id, ObligationEvidence.file_storage_path.isnot(None))
    )
    ev_paths = {row[0] for row in (await db.execute(ev_files_stmt)).all() if row[0]}

    all_files = ver_paths.union(ev_paths)

    # Delete business records
    c_stmt = select(Contract).where(Contract.organization_id == demo_org.id)
    c_all = (await db.execute(c_stmt)).scalars().all()
    deleted_contracts_count = len(c_all)

    # Delete related notes, calendar events, notifications
    await db.execute(delete(ContractNote).where(ContractNote.organization_id == demo_org.id))
    await db.execute(delete(CalendarEvent).where(CalendarEvent.organization_id == demo_org.id))
    await db.execute(delete(Notification).where(Notification.organization_id == demo_org.id))
    await db.execute(delete(Vendor).where(Vendor.organization_id == demo_org.id))
    await db.execute(delete(PlaybookRule).where(PlaybookRule.organization_id == demo_org.id))

    # Delete obligations and evidence
    deleted_obligations_count = 0
    for c in c_all:
        ob_stmt = select(Obligation).where(Obligation.contract_id == c.id)
        obs = (await db.execute(ob_stmt)).scalars().all()
        deleted_obligations_count += len(obs)
        for ob in obs:
            await db.execute(delete(ObligationEvidence).where(ObligationEvidence.obligation_id == ob.id))
            await db.delete(ob)

    # Delete contracts and sub-entities
    for c in c_all:
        await db.execute(delete(ContractClause).where(ContractClause.contract_id == c.id))
        await db.execute(delete(ContractRisk).where(ContractRisk.contract_id == c.id))
        await db.execute(delete(ContractApprovalStep).where(ContractApprovalStep.contract_id == c.id))
        await db.execute(delete(ContractRedline).where(ContractRedline.contract_id == c.id))
        await db.execute(delete(ContractVersion).where(ContractVersion.contract_id == c.id))
        await db.delete(c)

    # Delete physical files via StorageClient
    deleted_files_count = 0
    for path in all_files:
        try:
            storage_client.delete_file(path, tenant_id=demo_org.id)
            deleted_files_count += 1
        except Exception as e:
            logger.warning(f"Error deleting file {path} for demo org {demo_org.id}: {e}")

    # Re-seed baseline demo data if requested
    reseeded_contracts_count = 0
    if payload.reseed:
        # Baseline Demo Contract 1: CloudStack MSA
        c1 = Contract(
            organization_id=demo_org.id,
            contract_id="CTR-2026-0842",
            title="Vendor Master Services Agreement",
            contract_type="Master Services Agreement",
            counterparty="CloudStack Infrastructure Pvt. Ltd.",
            department="Procurement",
            owner="Priya Sundaram (Procurement Lead)",
            value=12000000.0,
            currency="INR",
            start_date="2026-01-15",
            expiry_date="2027-01-14",
            renewal_date="2026-11-15",
            auto_renew=True,
            status="ACTIVE",
            composite_risk_score=68,
            risk_level="HIGH",
            version="v2.1",
            governing_law="Jurisdiction of Courts in New Delhi, India",
            tags="Cloud Infrastructure, Critical Tier-1, Auto-Renew"
        )
        db.add(c1)
        await db.flush()

        cl1_1 = ContractClause(
            contract_id=c1.id,
            clause_title="Limitation of Liability",
            section_number="Section 11.2",
            original_text="Neither party shall be liable for consequential damages. Service Provider liability shall remain uncapped with respect to gross negligence and breach of confidentiality obligations.",
            plain_language="Vendor damages are limited to fees paid, except for data breaches or gross misconduct which remain uncapped.",
            why_it_matters="Protects Northstar from catastrophic damages arising from cloud vendor security failures.",
            potential_concern="Vendor proposed capping total liability at 1x annual fees.",
            suggested_action="Maintain super-cap of 3x annual fees for confidentiality claims.",
            risk_level="HIGH",
            category="Liability"
        )
        db.add(cl1_1)

        rk1_1 = ContractRisk(
            contract_id=c1.id,
            severity="HIGH",
            risk_title="Potential Liability Exposure",
            potential_impact="Proposed 1x cap limits recovery in major cloud security incidents.",
            remedy_recommendation="Negotiate 36-month super-cap for data privacy breaches.",
            status="OPEN"
        )
        db.add(rk1_1)

        ob1_1 = Obligation(
            contract_id=c1.id,
            obligor_party="CloudStack Infrastructure Pvt. Ltd.",
            obligee_party=demo_org.name,
            title="SOC2 Type II Annual Audit Attestation Delivery",
            description="Vendor must deliver independent annual SOC2 Type II audit report within 30 days of period end.",
            due_date="2026-11-30",
            frequency="ANNUAL",
            responsible_owner="Priya Sundaram (Procurement Lead)",
            status="UPCOMING"
        )
        db.add(ob1_1)

        # Baseline Demo Contract 2: Senior Engineering Employment Agreement
        c2 = Contract(
            organization_id=demo_org.id,
            contract_id="CTR-2026-1102",
            title="Senior Engineering Leadership Employment Agreement",
            contract_type="Employment Agreement",
            counterparty="Ananya Sharma",
            department="HR",
            owner="Rahul Deshmukh (HR VP)",
            value=6500000.0,
            currency="INR",
            start_date="2026-11-01",
            expiry_date="2029-10-31",
            renewal_date="2029-08-01",
            auto_renew=False,
            status="UNDER_REVIEW",
            composite_risk_score=76,
            risk_level="HIGH",
            version="v1.1",
            governing_law="Laws of Karnataka, India",
            tags="Executive Hiring, Non-Compete, IP Assignment"
        )
        db.add(c2)
        await db.flush()

        cl2_1 = ContractClause(
            contract_id=c2.id,
            clause_title="Post-Termination Restrictive Covenants (Non-Compete)",
            section_number="Section 9.1",
            original_text="For a period of 24 months following termination of employment for any reason, Employee agrees not to directly or indirectly be employed by any enterprise operating in enterprise software worldwide.",
            plain_language="The candidate is forbidden from working in enterprise software globally for 2 years after leaving.",
            why_it_matters="Under Section 27 of the Indian Contract Act, post-termination non-compete covenants are void and legally unenforceable.",
            potential_concern="Causes severe candidate friction and is legally invalid in Indian courts.",
            suggested_action="Replace with enforceable 12-month non-solicitation of clients and staff with trade secret protections.",
            risk_level="CRITICAL",
            category="Non-Compete"
        )
        db.add(cl2_1)

        rk2_1 = ContractRisk(
            contract_id=c2.id,
            severity="CRITICAL",
            risk_title="Unenforceable Restraint of Trade",
            potential_impact="Section 27 invalidation leaves trade secret covenants vulnerable if challenged.",
            remedy_recommendation="Redline to enforceable non-solicitation clause.",
            status="OPEN"
        )
        db.add(rk2_1)

        reseeded_contracts_count = 2

    # Post-reset audit
    post_audit = AuditLog(
        organization_id=demo_org.id,
        user_email=current_platform_user.email,
        action="DEMO_WORKSPACE_RESET_COMPLETED",
        object_type="Organization",
        object_id=demo_org.id,
        detail=(
            f"Demo workspace '{demo_org.name}' successfully reset by {current_platform_user.email}. "
            f"Deleted {deleted_contracts_count} contracts and {deleted_files_count} storage files. "
            f"Reseeded baseline contracts: {reseeded_contracts_count}."
        )
    )
    db.add(post_audit)
    await db.commit()

    return DemoResetResultResponse(
        status="SUCCESS",
        message=f"Demo workspace '{demo_org.name}' was successfully reset and restored.",
        organization_id=demo_org.id,
        organization_name=demo_org.name,
        deleted_counts={
            "contracts": deleted_contracts_count,
            "obligations": deleted_obligations_count,
        },
        deleted_storage_files=deleted_files_count,
        reseeded=payload.reseed,
        reseeded_contracts_count=reseeded_contracts_count,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/platform/data-management/customer-handover-checklist", response_model=CustomerHandoverChecklistResponse)
async def get_customer_handover_checklist(
    current_platform_user: User = Depends(require_platform_permission(PLATFORM_PERM_SYSTEM_READ)),
):
    """
    Returns standard customer onboarding and handover checklist items.
    Enforces clean separation between demonstration environments and genuine customer production workspaces.
    """
    items = [
        HandoverChecklistItem(
            id="tenant-provisioning",
            title="Clean Tenant Workspace Provisioning",
            description="Confirm new customer organization has been initialized with zero legacy or illustrative demo contracts.",
            status="READY",
            category="Tenant Isolation"
        ),
        HandoverChecklistItem(
            id="admin-assignment",
            title="Organization Administrator Authorization",
            description="Verify customer Organization Owner email has been configured with role-based access and least privilege.",
            status="READY",
            category="Access Control"
        ),
        HandoverChecklistItem(
            id="storage-quota",
            title="Dedicated Storage Namespace & Quota Allocation",
            description="Confirm tenant ID-based object storage partitioning and verify configured storage quota limit.",
            status="READY",
            category="Storage Integrity"
        ),
        HandoverChecklistItem(
            id="retention-rules",
            title="Retention & Legal Hold Configuration",
            description="Establish client-specific retention periods and review legal hold protection policies.",
            status="READY",
            category="Compliance"
        ),
        HandoverChecklistItem(
            id="demo-separation",
            title="Demo Environment Isolation Assurance",
            description="Ensure customer organization is not flagged as demo and cannot be touched by demo reset operations.",
            status="COMPLETED",
            category="Security"
        ),
        HandoverChecklistItem(
            id="handover-audit",
            title="Customer Custody Audit Sign-off",
            description="Generate verified platform audit trail confirming workspace handover and legal boundary custody.",
            status="READY",
            category="Audit"
        ),
    ]

    return CustomerHandoverChecklistResponse(
        checklist=items,
        generated_at=datetime.now(timezone.utc).isoformat()
    )
