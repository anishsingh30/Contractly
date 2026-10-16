from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.vendor import Vendor
from app.models.audit import AuditLog
from app.schemas.vendor import VendorCreateRequest, VendorResponse
from app.dependencies import get_current_tenant, get_current_active_user, require_permission
from app.core.permissions import PERMISSION_VENDORS_READ, PERMISSION_VENDORS_MANAGE

router = APIRouter(prefix="/vendors", tags=["Vendors"])

@router.get("", response_model=List[VendorResponse])
async def list_vendors(
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_VENDORS_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    List all vendor profiles strictly isolated to the authenticated tenant organization.
    """
    stmt = (
        select(Vendor)
        .where(Vendor.organization_id == tenant.id)
        .order_by(Vendor.name.asc())
    )
    result = await db.execute(stmt)
    vendors = result.scalars().all()
    return [VendorResponse.model_validate(v) for v in vendors]

@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorCreateRequest,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_VENDORS_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new vendor profile for the authenticated tenant organization.
    """
    vendor = Vendor(
        organization_id=tenant.id,
        name=payload.name,
        contact_email=payload.contact_email,
        contract_count=payload.contract_count,
        total_contract_value=payload.total_contract_value,
        risk_rating=payload.risk_rating,
        compliance_rating=payload.compliance_rating,
        sla_performance=payload.sla_performance,
        open_obligations=payload.open_obligations,
        critical_issues=payload.critical_issues,
        soc2_certified=payload.soc2_certified,
        gdpr_compliant=payload.gdpr_compliant,
    )
    db.add(vendor)
    await db.flush()

    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="VENDOR_PROFILE_CREATED",
        object_type="Vendor",
        object_id=vendor.id,
        detail=f"Created vendor profile for {vendor.name} ({vendor.contact_email})"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(vendor)
    return VendorResponse.model_validate(vendor)

@router.get("/{id}", response_model=VendorResponse)
async def get_vendor(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_VENDORS_READ)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Vendor).where(Vendor.id == id, Vendor.organization_id == tenant.id)
    result = await db.execute(stmt)
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found in this organization tenant.")
    return VendorResponse.model_validate(vendor)

@router.delete("/{id}")
async def delete_vendor(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    user: User = Depends(get_current_active_user),
    _member: OrganizationMember = Depends(require_permission(PERMISSION_VENDORS_MANAGE)),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Vendor).where(Vendor.id == id, Vendor.organization_id == tenant.id)
    result = await db.execute(stmt)
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    
    vendor_name = vendor.name
    await db.delete(vendor)
    audit = AuditLog(
        organization_id=tenant.id,
        user_email=user.email,
        action="VENDOR_PROFILE_DELETED",
        object_type="Vendor",
        object_id=id,
        detail=f"Deleted vendor profile for {vendor_name}"
    )
    db.add(audit)
    await db.commit()
    return {"status": "success", "message": f"Vendor {vendor_name} deleted."}
