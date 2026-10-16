import random
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import (
    Contract,
    ContractVersion,
    ContractClause,
    ContractRisk,
    ContractApprovalStep,
    ContractRedline
)
from app.models.obligation import Obligation
from app.models.playbook import PlaybookRule
from app.models.audit import AuditLog
from app.schemas.contract import (
    ContractResponse,
    ContractClauseResponse,
    ContractRiskResponse,
    ContractApprovalStepResponse,
    ApprovalDecisionRequest,
    ContractVersionResponse,
    ContractRedlineResponse,
    ContractRedlineCreateRequest,
    RedlineStatusUpdateRequest,
    RedlineCommentRequest,
    ContractStatusTransitionRequest,
    ContractTerminationRequest,
    ContractRenewalRequest,
    NegotiationFindingResponse,
    ContractLifecycleSummaryResponse,
    ContractIntelligenceResponse,
    ContractMetadataResponse,
    ExtractedPartyResponse,
    ExtractedDateCandidateResponse,
    ObligationCandidateResponse,
    RiskScoreBreakdownResponse
)
from app.schemas.obligation import ObligationResponse
from app.services.intelligence.pipeline import run_intelligence_pipeline
from app.services.intelligence.metadata_extractor import extract_parties, extract_candidate_dates
from app.services.intelligence.obligation_detector import extract_obligation_candidates
from app.services.intelligence.risk_detector import compute_explainable_risk_score
from app.dependencies import get_current_tenant, get_current_active_user, require_permission
from app.core.permissions import (
    PERMISSION_CONTRACTS_READ,
    PERMISSION_CONTRACTS_CREATE,
    PERMISSION_CONTRACTS_DELETE,
    PERMISSION_CONTRACTS_TRANSITION,
    PERMISSION_CONTRACTS_TERMINATE,
    PERMISSION_CONTRACTS_RENEW,
    PERMISSION_APPROVALS_DECIDE,
    PERMISSION_REDLINES_READ,
    PERMISSION_REDLINES_MANAGE
)
from app.services.storage import storage_client, compute_sha256
from app.services.parsing.parser_factory import parse_document_file
from app.services.ai.analysis_service import analyze_contract_text
from app.schemas.ai import ContractQARequest, ContractQAResponse
from app.services.ai.contract_qa import ask_contract_qa
from app.core.rate_limiter import ai_rate_limiter
from app.core.upload_validator import read_and_validate_upload, CONTRACT_ALLOWED_EXTENSIONS
from app.config import settings
from app.services.export.docx_export import generate_contract_revisions_docx, sanitize_filename
from app.services.ai import generate_contract_redlines, STANDARD_PLAYBOOK_BENCHMARKS
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["Contracts"])


# Controlled Lifecycle State Machine Transitions
VALID_TRANSITIONS = {
    "DRAFT": {"UNDER_REVIEW", "TERMINATED"},
    "UNDER_REVIEW": {"REDLINE", "NEGOTIATION", "PENDING_APPROVAL", "TERMINATED"},
    "REDLINE": {"NEGOTIATION", "UNDER_REVIEW", "PENDING_APPROVAL", "TERMINATED"},
    "NEGOTIATION": {"REDLINE", "UNDER_REVIEW", "PENDING_APPROVAL", "TERMINATED"},
    "PENDING_APPROVAL": {"APPROVED", "UNDER_REVIEW", "REDLINE", "TERMINATED"},
    "APPROVED": {"SIGNED", "ACTIVE", "UNDER_REVIEW", "TERMINATED"},
    "SIGNED": {"ACTIVE", "TERMINATED"},
    "ACTIVE": {"EXPIRING", "RENEWED", "TERMINATED"},
    "EXPIRING": {"RENEWED", "ACTIVE", "TERMINATED"},
    "RENEWED": {"ACTIVE", "EXPIRING", "TERMINATED"},
    "TERMINATED": set(),  # Terminal state
}

def serialize_contract(c: Contract) -> ContractResponse:
    tag_list = [t.strip() for t in c.tags.split(",") if t.strip()] if c.tags else []
    return ContractResponse(
        id=c.id,
        contract_id=c.contract_id,
        title=c.title,
        contract_type=c.contract_type,
        counterparty=c.counterparty,
        department=c.department,
        owner=c.owner,
        value=float(c.value) if c.value is not None else None,
        currency=c.currency or "INR",
        value_basis=getattr(c, "value_basis", "NOT_SPECIFIED") or "NOT_SPECIFIED",
        calculation_explanation=getattr(c, "calculation_explanation", None),
        start_date=c.start_date,
        expiry_date=c.expiry_date,
        end_date=c.expiry_date,
        renewal_date=c.renewal_date,
        auto_renew=c.auto_renew,
        renewal_notice_days=c.renewal_notice_days,
        termination_notice_days=c.termination_notice_days,
        termination_date=c.termination_date,
        termination_reason=c.termination_reason,
        status=c.status,
        composite_risk_score=c.composite_risk_score,
        risk_level=c.risk_level,
        version=c.version,
        governing_law=c.governing_law,
        tags=tag_list,
        created_at=c.created_at,
        clauses=[ContractClauseResponse.model_validate(cl) for cl in (c.clauses or [])],
        risks=[ContractRiskResponse.model_validate(rk) for rk in (c.risks or [])],
        approval_steps=[ContractApprovalStepResponse.model_validate(st) for st in (c.approval_steps or [])],
        redlines=[ContractRedlineResponse.model_validate(rd) for rd in (c.redlines or [])],
        versions=[ContractVersionResponse.model_validate(v) for v in (c.versions or [])]
    )

def compute_renewal_and_health(contract: Contract, overdue_obligations_count: int = 0):
    days_until_expiry = None
    in_notice_window = False
    renewal_status = "Renewal information unavailable"

    if contract.expiry_date:
        try:
            exp_date = datetime.strptime(contract.expiry_date.strip()[:10], "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            days_until_expiry = (exp_date - today).days
            notice_days = contract.renewal_notice_days or 30

            if days_until_expiry < 0:
                renewal_status = "EXPIRED"
            elif days_until_expiry <= notice_days:
                renewal_status = "NOTICE WINDOW"
                in_notice_window = True
            elif days_until_expiry <= 60:
                renewal_status = "EXPIRING"
            else:
                renewal_status = "UPCOMING RENEWAL"
        except Exception:
            renewal_status = "Renewal information unavailable"

    clauses_count = len(contract.clauses or [])
    risks_count = len(contract.risks or [])
    open_risks = [r for r in (contract.risks or []) if r.status == "OPEN"]
    has_high_risk = any(r.severity in ("HIGH", "CRITICAL") for r in open_risks)

    if clauses_count == 0 and risks_count == 0 and overdue_obligations_count == 0:
        health_status = "Not enough information"
        health_reason = "Insufficient contract clauses or risks recorded."
    elif contract.status == "TERMINATED":
        health_status = "POTENTIAL PROBLEM"
        health_reason = f"Contract is terminated. Reason: {contract.termination_reason or 'Not specified'}."
    elif renewal_status == "EXPIRED" or has_high_risk or overdue_obligations_count > 0:
        health_status = "POTENTIAL PROBLEM"
        health_reason = f"High severity factors: {len(open_risks)} open risks, {overdue_obligations_count} overdue obligations, renewal: {renewal_status}."
    elif in_notice_window or contract.status in ("UNDER_REVIEW", "PENDING_APPROVAL", "NEGOTIATION"):
        health_status = "NEEDS ATTENTION"
        health_reason = f"Action required: Lifecycle stage is {contract.status}; renewal notice window active: {in_notice_window}."
    elif days_until_expiry is not None and days_until_expiry <= 60:
        health_status = "UPCOMING"
        health_reason = f"Approaching expiration in {days_until_expiry} days."
    else:
        health_status = "GOOD"
        health_reason = "All contractual milestones, risk levels, and obligations are within target parameters."

    return {
        "health_status": health_status,
        "health_reason": health_reason,
        "renewal_status": renewal_status,
        "days_until_expiry": days_until_expiry,
        "in_notice_window": in_notice_window
    }

def evaluate_contract_playbook(contract: Contract, rules: Optional[List[PlaybookRule]] = None) -> List[NegotiationFindingResponse]:
    findings = []
    clauses_by_category = {}
    for clause in (contract.clauses or []):
        cat_key = clause.category.lower().strip()
        clauses_by_category.setdefault(cat_key, []).append(clause)
        title_key = clause.clause_title.lower().strip()
        clauses_by_category.setdefault(title_key, []).append(clause)

    active_rules: List[Dict[str, Any]] = []
    if rules:
        for r in rules:
            active_rules.append({
                "id": r.id,
                "category": r.category,
                "preferred_standard": r.preferred_standard or "",
                "prohibited_terms": r.prohibited_terms or "",
                "guidance": r.negotiation_guidance or "",
                "fallback": r.fallback_acceptable or "",
                "source": "Custom Organization Playbook"
            })
    else:
        for b in STANDARD_PLAYBOOK_BENCHMARKS:
            active_rules.append({
                "id": b["id"],
                "category": b["category"],
                "preferred_standard": b["preferred_standard"],
                "prohibited_terms": b["prohibited_terms"],
                "guidance": b["guidance"],
                "fallback": b["preferred_standard"],
                "source": "Standard Negotiation Baseline"
            })

    for rule in active_rules:
        r_cat = rule["category"].lower().strip()
        matching_clauses = clauses_by_category.get(r_cat, [])
        if not matching_clauses:
            for c in (contract.clauses or []):
                if r_cat in c.clause_title.lower() or r_cat in c.category.lower():
                    matching_clauses.append(c)

        prohibited = [p.strip().lower() for p in rule["prohibited_terms"].split(",") if p.strip()]

        if not matching_clauses:
            findings.append(
                NegotiationFindingResponse(
                    rule_id=rule["id"],
                    category=rule["category"],
                    status="Potential Negotiation Issue",
                    target_clause=None,
                    clause_title="Missing Clause",
                    finding_summary=f"Negotiation policy recommends a {rule['category']} provision, but no matching clause was detected.",
                    guidance=rule["guidance"],
                    suggested_action=f"Insert standard {rule['category']} language pursuant to negotiation guidelines."
                )
            )
            continue

        for cl in matching_clauses:
            cl_text = (cl.original_text or "").lower()
            found_prohibited = [term for term in prohibited if term in cl_text]

            if found_prohibited:
                findings.append(
                    NegotiationFindingResponse(
                        rule_id=rule["id"],
                        category=rule["category"],
                        status="Potential Negotiation Issue",
                        target_clause=cl.section_number,
                        clause_title=cl.clause_title,
                        finding_summary=f"Prohibited term(s) detected: {', '.join(found_prohibited)} in {cl.section_number or cl.clause_title}.",
                        guidance=rule["guidance"],
                        suggested_action=f"Redline to remove prohibited term(s) and align with preferred standard: {rule['preferred_standard'][:100]}..."
                    )
                )
            else:
                pref_words = [w.lower() for w in rule["preferred_standard"].split() if len(w) > 4][:5]
                matched_words = [w for w in pref_words if w in cl_text]
                if len(matched_words) >= 2 or cl.risk_level == "LOW":
                    findings.append(
                        NegotiationFindingResponse(
                            rule_id=rule["id"],
                            category=rule["category"],
                            status="Rule Match",
                            target_clause=cl.section_number,
                            clause_title=cl.clause_title,
                            finding_summary=f"Clause complies with standard negotiation position for {rule['category']}.",
                            guidance=rule["guidance"],
                            suggested_action="No revision necessary."
                        )
                    )
                else:
                    findings.append(
                        NegotiationFindingResponse(
                            rule_id=rule["id"],
                            category=rule["category"],
                            status="Potential Negotiation Issue",
                            target_clause=cl.section_number,
                            clause_title=cl.clause_title,
                            finding_summary=f"Clause language deviates from preferred standard position for {rule['category']}.",
                            guidance=rule["guidance"],
                            suggested_action=f"Consider fallback position: {rule['fallback']}"
                        )
                    )
    return findings


@router.get("", response_model=List[ContractResponse])
async def list_contracts(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.approval_steps),
            selectinload(Contract.redlines),
            selectinload(Contract.versions)
        )
        .order_by(Contract.created_at.desc())
    )
    result = await db.execute(stmt)
    contracts = result.scalars().all()
    return [serialize_contract(c) for c in contracts]


@router.post("/upload", response_model=ContractResponse)
async def upload_contract(
    file: UploadFile = File(...),
    title: str = Form(...),
    contract_type: str = Form("Master Services Agreement"),
    counterparty: str = Form(...),
    department: str = Form("Legal"),
    value: Optional[float] = Form(None),
    currency: str = Form("INR"),
    start_date: Optional[str] = Form("2026-11-01"),
    expiry_date: Optional[str] = Form("2027-10-31"),
    end_date: Optional[str] = Form(None),
    governing_law: Optional[str] = Form("Laws of India"),
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    content, safe_filename, mime = await read_and_validate_upload(
        file=file,
        max_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        allowed_extensions=CONTRACT_ALLOWED_EXTENSIONS
    )

    sha256 = compute_sha256(content)
    contract_code = f"CTR-2026-{random.randint(1000, 9999)}"
    storage_rel_path = f"{tenant.id}/{contract_code}/v1.0/{safe_filename}"

    # 1. Save binary file partitioned by tenant.id
    storage_client.save_file(storage_rel_path, content, tenant_id=tenant.id)

    # 2. Extract Document Text and Initialize Records
    has_manual_val = (value is not None and value > 0)
    new_contract = Contract(
        organization_id=tenant.id,
        contract_id=contract_code,
        title=title,
        contract_type=contract_type,
        counterparty=counterparty,
        department=department,
        owner=user.full_name,
        value=value if has_manual_val else None,
        currency=currency,
        value_basis="MANUALLY_ENTERED" if has_manual_val else "NOT_SPECIFIED",
        calculation_explanation=f"Manual contract value of {currency} {float(value):,.0f}" if has_manual_val else None,
        start_date=start_date,
        expiry_date=(end_date.strip() if (end_date and end_date.strip()) else expiry_date),
        renewal_date=(end_date.strip() if (end_date and end_date.strip()) else expiry_date),
        renewal_notice_days=30,
        termination_notice_days=30,
        status="UNDER_REVIEW",
        composite_risk_score=0,
        risk_level="LOW",
        version="v1.0",
        governing_law=governing_law or "Laws of India",
        tags=f"{contract_type}, Intake Upload"
    )
    db.add(new_contract)
    await db.flush()

    version_record = ContractVersion(
        contract_id=new_contract.id,
        version_number="v1.0",
        filename=safe_filename,
        file_storage_path=storage_rel_path,
        file_mime_type=mime,
        file_byte_size=len(content),
        sha256_checksum=sha256,
        change_summary="Initial contract ingestion and automated clause parsing.",
        created_by=user.full_name
    )
    db.add(version_record)
    await db.flush()

    # 3. Run Intelligence Pipeline
    await run_intelligence_pipeline(
        content,
        safe_filename,
        mime,
        new_contract,
        version_record,
        db,
        auto_commit=False
    )

    # 4. Create ContractApprovalStep Records
    step1 = ContractApprovalStep(
        contract_id=new_contract.id,
        step_order=1,
        role=f"{department} Department Lead",
        assigned_user=user.full_name,
        decision="PENDING"
    )
    step2 = ContractApprovalStep(
        contract_id=new_contract.id,
        step_order=2,
        role="Legal Manager",
        assigned_user="Legal Team",
        decision="PENDING"
    )
    db.add(step1)
    db.add(step2)

    # 5. Automatic Redline Generation for uploaded contract
    clauses_stmt = select(ContractClause).where(
        ContractClause.contract_id == new_contract.id,
        ContractClause.contract_version_id == version_record.id
    )
    saved_clauses = (await db.execute(clauses_stmt)).scalars().all()

    playbook_rules_stmt = select(PlaybookRule).where(PlaybookRule.organization_id == tenant.id).order_by(PlaybookRule.created_at.asc())
    playbook_rules = (await db.execute(playbook_rules_stmt)).scalars().all()

    try:
        await generate_contract_redlines(
            contract=new_contract,
            clauses=list(saved_clauses),
            playbook_rules=list(playbook_rules),
            db=db,
            author_name="Contractly Analysis Engine",
            auto_commit=False
        )
    except Exception as redline_err:
        logger.warning("Automatic redline generation on upload encountered an error: %s", redline_err)


    # 10. Audit Log
    upload_audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="CONTRACT_UPLOADED",
        object_type="Contract",
        object_id=new_contract.id,
        detail=f"Uploaded and ingested contract '{new_contract.title}' ({new_contract.contract_id})"
    )
    db.add(upload_audit)

    created_audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="CONTRACT_CREATED",
        object_type="Contract",
        object_id=new_contract.id,
        detail=f"Created contract '{new_contract.title}' ({new_contract.contract_id})"
    )
    db.add(created_audit)

    await db.commit()
    await db.refresh(new_contract)

    # Reload full contract relationships
    stmt = (
        select(Contract)
        .where(Contract.id == new_contract.id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.approval_steps),
            selectinload(Contract.redlines),
            selectinload(Contract.versions)
        )
    )
    refreshed = (await db.execute(stmt)).scalar_one()
    return serialize_contract(refreshed)


@router.get("/{id}", response_model=ContractResponse)
async def get_contract_details(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.approval_steps),
            selectinload(Contract.redlines),
            selectinload(Contract.versions)
        )
    )
    res = await db.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")
    return serialize_contract(c)


@router.patch("/{id}/status", response_model=ContractResponse)
async def update_contract_status(
    id: str,
    payload: ContractStatusTransitionRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_TRANSITION)),
    db: AsyncSession = Depends(get_db)
):
    """
    Controlled lifecycle status machine transition.
    Validates tenant isolation, RBAC, and allowed state transitions.
    """
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.approval_steps),
            selectinload(Contract.redlines),
            selectinload(Contract.versions)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    current_status = contract.status.upper()
    next_status = payload.status.upper()

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lifecycle transition from '{current_status}' to '{next_status}'. Allowed transitions: {sorted(list(allowed)) or 'None (terminal state)'}."
        )

    contract.status = next_status

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="STATUS_CHANGED",
        object_type="Contract",
        object_id=contract.id,
        detail=f"Status transitioned from {current_status} to {next_status}. Reason: {payload.reason or 'User workflow transition'}."
    )
    db.add(audit)
    await db.commit()
    await db.refresh(contract)
    return serialize_contract(contract)


@router.post("/{id}/terminate", response_model=ContractResponse)
async def terminate_contract(
    id: str,
    payload: ContractTerminationRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_TERMINATE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Controlled contract termination workflow.
    Validates tenant isolation, RBAC, and records reason/date and audit log.
    """
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.approval_steps),
            selectinload(Contract.redlines),
            selectinload(Contract.versions)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    if contract.status == "TERMINATED":
        raise HTTPException(status_code=400, detail="Contract is already terminated.")

    termination_date = payload.termination_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    contract.status = "TERMINATED"
    contract.termination_date = termination_date
    contract.termination_reason = payload.termination_reason

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="CONTRACT_TERMINATED",
        object_type="Contract",
        object_id=contract.id,
        detail=f"Contract terminated on {termination_date}. Reason: {payload.termination_reason}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(contract)
    return serialize_contract(contract)


@router.post("/{id}/renew", response_model=ContractResponse)
async def renew_contract(
    id: str,
    payload: ContractRenewalRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_RENEW)),
    db: AsyncSession = Depends(get_db)
):
    """
    Controlled contract renewal workflow.
    Validates tenant isolation, RBAC, and updates expiration and status.
    """
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.approval_steps),
            selectinload(Contract.redlines),
            selectinload(Contract.versions)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    if contract.status not in ("ACTIVE", "EXPIRING", "RENEWED"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot renew contract in '{contract.status}' status. Must be ACTIVE or EXPIRING."
        )

    contract.expiry_date = payload.new_expiry_date
    contract.renewal_date = payload.new_expiry_date
    contract.status = "RENEWED"

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="CONTRACT_RENEWED",
        object_type="Contract",
        object_id=contract.id,
        detail=f"Renewed through {payload.new_expiry_date}. Term: {payload.renewal_term_months} months. Notes: {payload.notes or 'None'}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(contract)
    return serialize_contract(contract)


@router.post("/{id}/approvals/{step_id}/decision", response_model=ContractApprovalStepResponse)
async def submit_approval_decision(
    id: str,
    step_id: str,
    payload: ApprovalDecisionRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_APPROVALS_DECIDE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(selectinload(Contract.approval_steps))
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    steps_sorted = sorted(contract.approval_steps, key=lambda s: s.step_order)
    target_step = None
    target_idx = -1
    for idx, step in enumerate(steps_sorted):
        if step.id == step_id:
            target_step = step
            target_idx = idx
            break

    if not target_step:
        raise HTTPException(status_code=404, detail="Approval step not found on this contract.")

    # Prevent submitting decisions on terminal contracts
    if contract.status in ("TERMINATED", "CANCELLED", "EXPIRED"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit approval decision on a {contract.status.lower()} contract."
        )

    # Prevent repeated requests / deciding an already decided step
    if target_step.decision != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Approval step {target_step.step_order} has already been decided ({target_step.decision})."
        )

    # Enforce sequential order: previous step must be approved
    if target_idx > 0:
        prev_step = steps_sorted[target_idx - 1]
        if prev_step.decision != "APPROVED":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot decide step {target_step.step_order}. Prior step {prev_step.step_order} is still {prev_step.decision}."
            )

    target_step.decision = payload.decision
    target_step.decided_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    target_step.comments = payload.comments or f"Decision submitted by {user.full_name}."

    audit_action = "APPROVAL_APPROVED" if payload.decision == "APPROVED" else "APPROVAL_REJECTED"

    if payload.decision == "REJECTED":
        contract.status = "UNDER_REVIEW"
    elif payload.decision == "APPROVED":
        all_approved = all(s.decision == "APPROVED" for s in contract.approval_steps)
        if all_approved:
            contract.status = "APPROVED"

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="APPROVAL_DECISION_SUBMITTED",
        object_type="Approval Step",
        object_id=f"{contract.contract_id} / Step {target_step.step_order}",
        detail=f"{payload.decision} by {user.full_name}: {target_step.comments}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(target_step)

    return ContractApprovalStepResponse.model_validate(target_step)


# --- Contract Versions ---
@router.get("/{id}/versions", response_model=List[ContractVersionResponse])
async def list_contract_versions(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ContractVersion)
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .order_by(ContractVersion.created_at.desc())
    )
    res = await db.execute(stmt)
    return [ContractVersionResponse.model_validate(v) for v in res.scalars().all()]


@router.get("/{id}/versions/{version_id}", response_model=ContractVersionResponse)
async def get_contract_version(
    id: str,
    version_id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ContractVersion)
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(
            Contract.id == id,
            ContractVersion.id == version_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    v = res.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Contract version not found.")
    return ContractVersionResponse.model_validate(v)


@router.get("/{id}/versions/{version_id}/download")
async def download_contract_version(
    id: str,
    version_id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    Securely download contract version document.
    Enforces tenant boundaries, read permissions, and directory traversal defense.
    """
    stmt = (
        select(ContractVersion)
        .join(Contract, ContractVersion.contract_id == Contract.id)
        .where(
            Contract.id == id,
            ContractVersion.id == version_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    v = res.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Contract version not found.")

    try:
        content = storage_client.get_file(v.file_storage_path, tenant_id=tenant.id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Contract document file not found in storage.")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    safe_filename = "".join(c for c in (v.filename or f"contract_{v.version_number}.pdf") if c.isalnum() or c in "._- ")

    return Response(
        content=content,
        media_type=v.file_mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.get("/{id}/export/docx")
async def export_contract_redlines_docx(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export Proposed Revisions (.docx).
    Produces a downloadable Word (.docx) document formatted with styled comparison blocks
    for original versus proposed contract revisions.
    Enforces tenant boundaries, read permissions, and non-destructive output.
    """
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.redlines),
            selectinload(Contract.versions),
            selectinload(Contract.clauses)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    docx_bytes = generate_contract_revisions_docx(contract, exported_by_user=user)

    safe_code = "".join(c for c in (contract.contract_id or "contract") if c.isalnum() or c in "._-")
    safe_filename = f"{safe_code}_proposed_revisions.docx"

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="EXPORT_REDLINES_DOCX",
        object_type="Contract",
        object_id=contract.id,
        detail=f"Exported proposed revisions DOCX for contract {contract.contract_id}."
    )
    db.add(audit)
    await db.commit()

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(len(docx_bytes)),
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.post("/{id}/versions", response_model=ContractVersionResponse)
async def create_contract_version(
    id: str,
    file: UploadFile = File(...),
    change_summary: str = Form("Revision update"),
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(selectinload(Contract.versions))
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    content, safe_filename, mime = await read_and_validate_upload(
        file=file,
        max_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        allowed_extensions=CONTRACT_ALLOWED_EXTENSIONS
    )

    version_count = len(contract.versions) + 1
    new_version_num = f"v{version_count}.0"
    sha256 = compute_sha256(content)
    storage_rel_path = f"{tenant.id}/{contract.contract_id}/{new_version_num}/{safe_filename}"
    storage_client.save_file(storage_rel_path, content, tenant_id=tenant.id)

    new_version = ContractVersion(
        contract_id=contract.id,
        version_number=new_version_num,
        filename=safe_filename,
        file_storage_path=storage_rel_path,
        file_mime_type=mime,
        file_byte_size=len(content),
        sha256_checksum=sha256,
        change_summary=change_summary,
        created_by=user.full_name
    )
    contract.version = new_version_num
    db.add(new_version)
    await db.flush()

    await run_intelligence_pipeline(
        content,
        safe_filename,
        mime,
        contract,
        new_version,
        db,
        auto_commit=False
    )

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="VERSION_CREATED",
        object_type="ContractVersion",
        object_id=new_version.id,
        detail=f"Created {new_version_num} for contract {contract.contract_id}: {change_summary}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(new_version)
    return ContractVersionResponse.model_validate(new_version)


# --- Redlines & Negotiation Markup ---
@router.get("/{id}/redlines", response_model=List[ContractRedlineResponse])
async def list_contract_redlines(
    id: str,
    version_id: Optional[str] = None,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_REDLINES_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ContractRedline)
        .join(Contract, ContractRedline.contract_id == Contract.id)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
    )
    if version_id:
        stmt = stmt.outerjoin(ContractClause, ContractRedline.clause_id == ContractClause.id).where(
            (ContractClause.contract_version_id == version_id) | (ContractRedline.clause_id.is_(None))
        )
    stmt = stmt.order_by(ContractRedline.created_at.asc())
    res = await db.execute(stmt)
    return [ContractRedlineResponse.model_validate(rd) for rd in res.scalars().all()]


@router.post("/{id}/generate-redlines", response_model=List[ContractRedlineResponse])
async def trigger_generate_contract_redlines(
    id: str,
    version_id: Optional[str] = None,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_REDLINES_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    """
    On-demand AI redline generation for an uploaded contract.
    Reads extracted clauses from the specified (or latest) version,
    evaluates against organization playbook rules (or standard CLM benchmarks),
    and creates contract-grounded ContractRedline proposals.
    Protected by PERMISSION_REDLINES_MANAGE and sliding-window rate limiting.
    """
    await ai_rate_limiter.check_rate_limit(f"user:{user.id}")
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.versions),
            selectinload(Contract.clauses)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    target_version = None
    if version_id:
        target_version = next((v for v in contract.versions if v.id == version_id), None)
        if not target_version:
            raise HTTPException(status_code=404, detail="Specified contract version not found.")
    elif contract.versions:
        target_version = contract.versions[0]

    v_id = target_version.id if target_version else None
    clauses = [c for c in contract.clauses if not v_id or c.contract_version_id == v_id] if contract.clauses else []

    if not clauses:
        raise HTTPException(
            status_code=400,
            detail="No clauses found for this contract version. Document analysis must be completed before revisions can be generated."
        )

    # Fetch organization playbook rules
    rule_stmt = select(PlaybookRule).where(PlaybookRule.organization_id == tenant.id).order_by(PlaybookRule.created_at.asc())
    rules_res = await db.execute(rule_stmt)
    playbook_rules = rules_res.scalars().all()

    try:
        new_redlines = await generate_contract_redlines(
            contract=contract,
            clauses=clauses,
            playbook_rules=list(playbook_rules),
            db=db,
            author_name=f"{user.full_name} (AI Assisted)",
            auto_commit=True
        )
    except Exception as exc:
        logger.error("Failed to generate redlines for contract %s: %s", contract.id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"AI redline generation service encountered an error: {str(exc)}"
        )

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="REDLINES_GENERATED",
        object_type="Contract",
        object_id=contract.id,
        detail=f"Generated {len(new_redlines)} proposed redlines for contract '{contract.title}' ({contract.contract_id})."
    )
    db.add(audit)
    await db.commit()

    return [ContractRedlineResponse.model_validate(rd) for rd in new_redlines]



@router.post("/{id}/redlines", response_model=ContractRedlineResponse)
async def create_contract_redline(
    id: str,
    payload: ContractRedlineCreateRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_REDLINES_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contract).where(Contract.id == id, Contract.organization_id == tenant.id)
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    redline = ContractRedline(
        contract_id=contract.id,
        clause_id=payload.clause_id,
        section_title=payload.section_title,
        original_text=payload.original_text,
        suggested_text=payload.suggested_text,
        rationale=payload.rationale,
        status="PENDING",
        author=user.full_name
    )
    db.add(redline)
    await db.flush()

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="REDLINE_CREATED",
        object_type="ContractRedline",
        object_id=redline.id,
        detail=f"Proposed revision on '{payload.section_title}' for {contract.contract_id}."
    )
    db.add(audit)
    await db.commit()
    await db.refresh(redline)
    return ContractRedlineResponse.model_validate(redline)


@router.patch("/{id}/redlines/{redline_id}/status", response_model=ContractRedlineResponse)
async def update_redline_status(
    id: str,
    redline_id: str,
    payload: RedlineStatusUpdateRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_REDLINES_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ContractRedline)
        .join(Contract, ContractRedline.contract_id == Contract.id)
        .where(
            Contract.id == id,
            ContractRedline.id == redline_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    redline = res.scalar_one_or_none()
    if not redline:
        raise HTTPException(status_code=404, detail="Redline item not found.")

    new_st = payload.status.upper()
    if new_st not in ("ACCEPTED", "REJECTED", "MODIFIED", "PENDING"):
        raise HTTPException(status_code=400, detail="Invalid redline status.")

    redline.status = new_st
    audit_action = f"REDLINE_{new_st}" if new_st in ("ACCEPTED", "REJECTED") else "REDLINE_MODIFIED"

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action=audit_action,
        object_type="ContractRedline",
        object_id=redline.id,
        detail=f"Marked redline on '{redline.section_title}' as {new_st} by {user.full_name}."
    )
    db.add(audit)
    await db.commit()
    await db.refresh(redline)
    return ContractRedlineResponse.model_validate(redline)


@router.post("/{id}/redlines/{redline_id}/comment", response_model=ContractRedlineResponse)
async def comment_on_redline(
    id: str,
    redline_id: str,
    payload: RedlineCommentRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_REDLINES_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ContractRedline)
        .join(Contract, ContractRedline.contract_id == Contract.id)
        .where(
            Contract.id == id,
            ContractRedline.id == redline_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    redline = res.scalar_one_or_none()
    if not redline:
        raise HTTPException(status_code=404, detail="Redline item not found.")

    redline.comment = payload.comment

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="REDLINE_COMMENTED",
        object_type="ContractRedline",
        object_id=redline.id,
        detail=f"Comment added by {user.full_name}: {payload.comment[:100]}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(redline)
    return ContractRedlineResponse.model_validate(redline)


# --- Negotiation Analysis & Playbook Rules Integration ---
@router.get("/{id}/negotiation-analysis", response_model=List[NegotiationFindingResponse])
async def get_contract_negotiation_analysis(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    Compares contract clauses against active organization PlaybookRule records.
    Deterministic rule-based evaluation (no AI hallucinations).
    """
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(selectinload(Contract.clauses))
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    rule_stmt = (
        select(PlaybookRule)
        .where(PlaybookRule.organization_id == tenant.id)
        .order_by(PlaybookRule.created_at.asc())
    )
    rules_res = await db.execute(rule_stmt)
    rules = rules_res.scalars().all()

    findings = evaluate_contract_playbook(contract, rules)

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="NEGOTIATION_EVALUATED",
        object_type="Contract",
        object_id=contract.id,
        detail=f"Evaluated {len(rules)} organization playbook rules against contract clauses. Generated {len(findings)} findings."
    )
    db.add(audit)
    await db.commit()

    return findings


# --- Lifecycle Summary & Health ---
@router.get("/{id}/lifecycle-summary", response_model=ContractLifecycleSummaryResponse)
async def get_contract_lifecycle_summary(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.approval_steps),
            selectinload(Contract.obligations)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    # Count overdue obligations deterministically
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    overdue_count = 0
    for o in (contract.obligations or []):
        if o.due_date and o.due_date < today_str and o.status not in ("FULFILLED", "RESOLVED", "WAIVED"):
            overdue_count += 1

    open_risks = [r for r in (contract.risks or []) if r.status == "OPEN"]
    pending_approvals = [s for s in (contract.approval_steps or []) if s.decision == "PENDING"]

    calc = compute_renewal_and_health(contract, overdue_obligations_count=overdue_count)
    allowed_transitions = sorted(list(VALID_TRANSITIONS.get(contract.status.upper(), set())))

    return ContractLifecycleSummaryResponse(
        current_status=contract.status,
        allowed_transitions=allowed_transitions,
        health_status=calc["health_status"],
        health_reason=calc["health_reason"],
        renewal_status=calc["renewal_status"],
        days_until_expiry=calc["days_until_expiry"],
        in_notice_window=calc["in_notice_window"],
        open_risks_count=len(open_risks),
        overdue_obligations_count=overdue_count,
        pending_approval_steps_count=len(pending_approvals)
    )


@router.post("/{id}/qa", response_model=ContractQAResponse)
async def contract_qa(
    id: str,
    query_payload: ContractQARequest,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contract).where(
        Contract.id == id,
        Contract.organization_id == tenant.id
    ).options(
        selectinload(Contract.clauses),
        selectinload(Contract.risks),
        selectinload(Contract.obligations),
        selectinload(Contract.versions)
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")

    await ai_rate_limiter.check_rate_limit(f"user:{_member.user_id}")
    return await ask_contract_qa(contract, query_payload.question)


@router.delete("/{id}")
async def delete_contract(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_DELETE)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contract).where(Contract.id == id, Contract.organization_id == tenant.id)
    res = await db.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found.")

    # Check for active legal hold or retention lock
    tags = [t.strip().upper() for t in (c.tags or [])]
    if (c.status and c.status.upper() in ["LEGAL_HOLD", "RETENTION_LOCK"]) or any(t in ["LEGAL_HOLD", "RETENTION_LOCK", "LEGAL HOLD"] for t in tags):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete contract '{c.title}': Active legal hold or retention lock is in place. Release all legal holds before deleting."
        )

    # Clean up associated physical storage files
    stmt_v = select(ContractVersion).where(ContractVersion.contract_id == id)
    v_res = await db.execute(stmt_v)
    versions = v_res.scalars().all()
    deleted_files = 0
    for v in versions:
        if v.file_storage_path:
            try:
                storage_client.delete_file(v.file_storage_path, tenant_id=tenant.id)
                deleted_files += 1
            except Exception:
                pass

    contract_title = c.title
    await db.delete(c)

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="CONTRACT_DELETED",
        object_type="Contract",
        object_id=id,
        detail=f"Contract '{contract_title}' (ID: {id}) permanently deleted with {len(versions)} version(s) and {deleted_files} physical file(s)."
    )
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": f"Contract '{contract_title}' and associated files deleted successfully."}


@router.get("/clauses/{clause_id}", response_model=ContractClauseResponse)
async def get_contract_clause(
    clause_id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ContractClause)
        .join(Contract, ContractClause.contract_id == Contract.id)
        .where(
            ContractClause.id == clause_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    clause = res.scalar_one_or_none()
    if not clause:
        raise HTTPException(status_code=404, detail="Contract clause not found.")
    return ContractClauseResponse.model_validate(clause)


@router.get("/risks/{risk_id}", response_model=ContractRiskResponse)
async def get_contract_risk(
    risk_id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ContractRisk)
        .join(Contract, ContractRisk.contract_id == Contract.id)
        .where(
            ContractRisk.id == risk_id,
            Contract.organization_id == tenant.id
        )
    )
    res = await db.execute(stmt)
    risk = res.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Contract risk not found.")
    return ContractRiskResponse.model_validate(risk)


@router.get("/{id}/intelligence", response_model=ContractIntelligenceResponse)
async def get_contract_intelligence(
    id: str,
    version_id: Optional[str] = None,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.versions),
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.obligations)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    active_version = None
    if version_id:
        active_version = next((v for v in contract.versions if v.id == version_id), None)
        if not active_version:
            raise HTTPException(status_code=404, detail="Specified contract version not found.")
    elif contract.versions:
        active_version = contract.versions[0]

    v_id = active_version.id if active_version else None
    clauses = [c for c in contract.clauses if not v_id or c.contract_version_id == v_id] if contract.clauses else []
    risks = [r for r in contract.risks if not v_id or r.contract_version_id == v_id] if contract.risks else []

    clauses_data = [
        ContractClauseResponse(
            id=c.id,
            contract_id=c.contract_id,
            contract_version_id=c.contract_version_id,
            clause_title=c.clause_title,
            section_number=c.section_number,
            original_text=c.original_text,
            plain_language=c.plain_language,
            why_it_matters=c.why_it_matters,
            potential_concern=c.potential_concern,
            suggested_action=c.suggested_action,
            risk_level=c.risk_level,
            category=c.category,
            page_number=c.page_number or 1,
            position_order=c.position_order or 0,
            start_pos=c.start_pos,
            end_pos=c.end_pos
        ) for c in clauses
    ]

    risks_data = [
        ContractRiskResponse(
            id=r.id,
            contract_id=r.contract_id,
            contract_version_id=r.contract_version_id,
            clause_id=r.clause_id,
            section_number=r.section_number,
            category=r.category,
            severity=r.severity,
            risk_title=r.risk_title,
            potential_impact=r.potential_impact,
            remedy_recommendation=r.remedy_recommendation,
            status=r.status
        ) for r in risks
    ]

    text_corpus = (active_version.normalized_text or active_version.raw_text or "") if active_version else ""
    parties = extract_parties(text_corpus)
    sections_dummy = [{"section_number": c.section_number, "title": c.clause_title, "text": c.original_text} for c in clauses]
    candidate_dates = extract_candidate_dates(sections_dummy)
    obligation_candidates = extract_obligation_candidates([
        {"id": c.id, "section_number": c.section_number, "clause_title": c.clause_title, "original_text": c.original_text, "category": c.category}
        for c in clauses
    ])

    score_info = compute_explainable_risk_score([{"severity": r.severity} for r in risks])

    renewal_info = {
        "expiry_date": contract.expiry_date,
        "renewal_date": contract.renewal_date,
        "auto_renew": contract.auto_renew,
        "renewal_notice_days": contract.renewal_notice_days,
        "termination_notice_days": contract.termination_notice_days,
        "status": "UPCOMING RENEWAL" if contract.renewal_date else "Renewal information unavailable"
    }

    return ContractIntelligenceResponse(
        contract_id=contract.id,
        version_id=v_id,
        parser_status=active_version.parser_status if active_version else "COMPLETED",
        page_count=active_version.page_count if active_version else 1,
        char_count=active_version.char_count if active_version else len(text_corpus),
        word_count=active_version.word_count if active_version else len(text_corpus.split()),
        processing_started_at=active_version.processing_started_at if active_version else None,
        processing_completed_at=active_version.processing_completed_at if active_version else None,
        processing_error=active_version.processing_error if active_version else None,
        parties=[ExtractedPartyResponse(name=p["name"], role=p["role"], source=p.get("source")) for p in parties],
        candidate_dates=[
            ExtractedDateCandidateResponse(
                date_type=d["date_type"],
                date_str=d["date_str"],
                section_number=d.get("section_number"),
                section_title=d.get("section_title"),
                excerpt=d.get("excerpt")
            ) for d in candidate_dates
        ],
        renewal_info=renewal_info,
        clauses=clauses_data,
        risks=risks_data,
        obligation_candidates=[
            ObligationCandidateResponse(
                title=o["title"],
                clause_id=o.get("clause_id"),
                section_number=o.get("section_number"),
                section_title=o.get("section_title"),
                source_text=o["source_text"],
                responsible_party=o["responsible_party"],
                category=o["category"],
                frequency=o["frequency"],
                confidence=o["confidence"]
            ) for o in obligation_candidates
        ],
        risk_score_breakdown=RiskScoreBreakdownResponse(
            composite_risk_score=score_info["composite_risk_score"],
            risk_level=score_info["risk_level"],
            critical_count=score_info["critical_count"],
            high_count=score_info["high_count"],
            medium_count=score_info["medium_count"],
            low_count=score_info["low_count"],
            explanation=score_info["explanation"]
        )
    )


@router.get("/{id}/clauses", response_model=List[ContractClauseResponse])
async def list_contract_clauses(
    id: str,
    version_id: Optional[str] = None,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contract).where(Contract.id == id, Contract.organization_id == tenant.id)
    contract = (await db.execute(stmt)).scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    query = select(ContractClause).where(ContractClause.contract_id == id)
    if version_id:
        query = query.where(ContractClause.contract_version_id == version_id)
    query = query.order_by(ContractClause.position_order.asc(), ContractClause.created_at.asc())
    clauses = (await db.execute(query)).scalars().all()
    return [ContractClauseResponse.model_validate(c) for c in clauses]


@router.get("/{id}/risks", response_model=List[ContractRiskResponse])
async def list_contract_risks(
    id: str,
    version_id: Optional[str] = None,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contract).where(Contract.id == id, Contract.organization_id == tenant.id)
    contract = (await db.execute(stmt)).scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    query = select(ContractRisk).where(ContractRisk.contract_id == id)
    if version_id:
        query = query.where(ContractRisk.contract_version_id == version_id)
    query = query.order_by(ContractRisk.created_at.asc())
    risks = (await db.execute(query)).scalars().all()
    return [ContractRiskResponse.model_validate(r) for r in risks]


@router.get("/{id}/obligations", response_model=List[ObligationResponse])
async def list_contract_obligations(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Contract).where(Contract.id == id, Contract.organization_id == tenant.id)
    contract = (await db.execute(stmt)).scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    query = (
        select(Obligation)
        .where(Obligation.contract_id == id)
        .options(selectinload(Obligation.evidence))
        .order_by(Obligation.created_at.desc())
    )
    obligations = (await db.execute(query)).scalars().all()
    return [ObligationResponse.model_validate(o) for o in obligations]


@router.get("/{id}/metadata", response_model=ContractMetadataResponse)
async def get_contract_metadata(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(
            selectinload(Contract.versions),
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.obligations)
        )
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    return ContractMetadataResponse(
        contract_id=contract.contract_id,
        title=contract.title,
        counterparty=contract.counterparty,
        status=contract.status,
        current_version=contract.version,
        versions=[ContractVersionResponse.model_validate(v) for v in contract.versions],
        total_clauses=len(contract.clauses),
        total_risks=len(contract.risks),
        total_obligations=len(contract.obligations)
    )


@router.post("/{id}/reprocess", response_model=ContractIntelligenceResponse)
async def reprocess_contract_intelligence(
    id: str,
    version_id: Optional[str] = None,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_CONTRACTS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Contract)
        .where(Contract.id == id, Contract.organization_id == tenant.id)
        .options(selectinload(Contract.versions))
    )
    contract = (await db.execute(stmt)).scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found in this organization tenant.")

    target_version = None
    if version_id:
        target_version = next((v for v in contract.versions if v.id == version_id), None)
        if not target_version:
            raise HTTPException(status_code=404, detail="Specified version not found.")
    elif contract.versions:
        target_version = contract.versions[0]
    else:
        raise HTTPException(status_code=400, detail="Contract has no uploaded versions to reprocess.")

    # Read binary bytes from storage
    try:
        file_bytes = storage_client.read_file(target_version.file_storage_path, tenant_id=tenant.id)
    except Exception:
        file_bytes = (target_version.raw_text or "").encode("utf-8")

    filename = target_version.filename or f"{contract.contract_id}.pdf"
    mime = target_version.file_mime_type or "application/pdf"

    await run_intelligence_pipeline(
        file_bytes,
        filename,
        mime,
        contract,
        target_version,
        db,
        auto_commit=True
    )

    # Refresh proposed redlines as part of reprocessing
    clauses_stmt = select(ContractClause).where(
        ContractClause.contract_id == contract.id,
        ContractClause.contract_version_id == target_version.id
    )
    saved_clauses = (await db.execute(clauses_stmt)).scalars().all()
    playbook_rules_stmt = select(PlaybookRule).where(PlaybookRule.organization_id == tenant.id).order_by(PlaybookRule.created_at.asc())
    playbook_rules = (await db.execute(playbook_rules_stmt)).scalars().all()

    try:
        await generate_contract_redlines(
            contract=contract,
            clauses=list(saved_clauses),
            playbook_rules=list(playbook_rules),
            db=db,
            author_name=f"{user.full_name} (AI Assisted)",
            auto_commit=True
        )
    except Exception as re_err:
        logger.warning("Redline regeneration on reprocess failed: %s", re_err)


    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="INTELLIGENCE_REPROCESSED",
        object_type="Contract",
        object_id=contract.id,
        detail=f"Reprocessed contract intelligence for version {target_version.version_number}."
    )
    db.add(audit)
    await db.commit()

    return await get_contract_intelligence(id=id, version_id=target_version.id, tenant=tenant, _member=_member, db=db)
