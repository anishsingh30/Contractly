from typing import List
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.playbook import PlaybookRule
from app.models.audit import AuditLog
from app.schemas.playbook import PlaybookRuleCreateRequest, PlaybookRuleResponse
from app.dependencies import get_current_tenant, get_current_active_user, require_permission
from app.core.permissions import PERMISSION_PLAYBOOK_READ, PERMISSION_PLAYBOOK_MANAGE

router = APIRouter(prefix="/playbook", tags=["Playbook"])

def serialize_rule(r: PlaybookRule) -> PlaybookRuleResponse:
    terms = []
    if r.prohibited_terms:
        try:
            terms = json.loads(r.prohibited_terms)
        except Exception:
            terms = [t.strip() for t in r.prohibited_terms.split(",") if t.strip()]
    return PlaybookRuleResponse(
        id=r.id,
        organization_id=r.organization_id,
        category=r.category,
        preferred_standard=r.preferred_standard,
        fallback_acceptable=r.fallback_acceptable,
        prohibited_terms=terms,
        negotiation_guidance=r.negotiation_guidance,
        created_at=r.created_at
    )

@router.get("", response_model=List[PlaybookRuleResponse])
async def list_playbook_rules(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_PLAYBOOK_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    List all negotiation playbook rules strictly isolated to the authenticated tenant organization.
    """
    stmt = (
        select(PlaybookRule)
        .where(PlaybookRule.organization_id == tenant.id)
        .order_by(PlaybookRule.category.asc())
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [serialize_rule(r) for r in rules]

@router.post("", response_model=PlaybookRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_playbook_rule(
    payload: PlaybookRuleCreateRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_PLAYBOOK_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new negotiation playbook rule for the authenticated tenant organization.
    """
    rule = PlaybookRule(
        organization_id=tenant.id,
        category=payload.category,
        preferred_standard=payload.preferred_standard,
        fallback_acceptable=payload.fallback_acceptable,
        prohibited_terms=json.dumps(payload.prohibited_terms),
        negotiation_guidance=payload.negotiation_guidance
    )
    db.add(rule)
    await db.flush()

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="PLAYBOOK_RULE_CREATED",
        object_type="PlaybookRule",
        object_id=rule.id,
        detail=f"Created negotiation playbook rule for {rule.category}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(rule)
    return serialize_rule(rule)

@router.get("/{id}", response_model=PlaybookRuleResponse)
async def get_playbook_rule(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_PLAYBOOK_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(PlaybookRule).where(PlaybookRule.id == id, PlaybookRule.organization_id == tenant.id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Playbook rule not found in this organization tenant.")
    return serialize_rule(rule)

@router.delete("/{id}")
async def delete_playbook_rule(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_PLAYBOOK_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(PlaybookRule).where(PlaybookRule.id == id, PlaybookRule.organization_id == tenant.id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Playbook rule not found.")
    
    category = rule.category
    await db.delete(rule)
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="PLAYBOOK_RULE_DELETED",
        object_type="PlaybookRule",
        object_id=id,
        detail=f"Deleted negotiation playbook rule for {category}"
    )
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": f"Playbook rule for {category} deleted."}
