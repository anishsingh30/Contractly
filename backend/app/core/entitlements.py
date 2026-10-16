"""
Contractly Account Types, Subscription Plans, and Feature Entitlements Engine.

Strictly separates:
1. Account Type: INDIVIDUAL (Personal), BUSINESS, ENTERPRISE, LEGAL_PROFESSIONAL.
2. Subscription Tier / Plan: COMMUNITY, STARTER, BUSINESS_PRO, ENTERPRISE.
3. Organization Membership: Tenant association.
4. Role: Operational role within the organization (OWNER, ADMIN, LEGAL_MANAGER, etc.).
"""

from enum import Enum
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.permissions import has_permission, PERMISSION_ORG_MANAGE, PERMISSION_AUDIT_READ, PERMISSION_PLAYBOOK_MANAGE

class AccountType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    PERSONAL = "PERSONAL" # Alias for INDIVIDUAL
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"
    LEGAL_PROFESSIONAL = "LEGAL_PROFESSIONAL"
    PROFESSIONAL = "PROFESSIONAL" # Alias for LEGAL_PROFESSIONAL

class SubscriptionPlan(str, Enum):
    COMMUNITY = "COMMUNITY"
    FREE = "FREE" # Alias for COMMUNITY
    STARTER = "STARTER"
    BUSINESS_PRO = "BUSINESS_PRO"
    ENTERPRISE = "ENTERPRISE"

STORAGE_QUOTA_BY_ACCOUNT_TYPE = {
    "INDIVIDUAL": 1 * 1024 * 1024 * 1024,       # 1 GB
    "PERSONAL": 1 * 1024 * 1024 * 1024,         # 1 GB
    "BUSINESS": 10 * 1024 * 1024 * 1024,       # 10 GB
    "ENTERPRISE": 100 * 1024 * 1024 * 1024,    # 100 GB
    "LEGAL_PROFESSIONAL": 25 * 1024 * 1024 * 1024, # 25 GB
    "PROFESSIONAL": 25 * 1024 * 1024 * 1024,   # 25 GB
}

DEFAULT_SUBSCRIPTION_BY_ACCOUNT = {
    "INDIVIDUAL": "COMMUNITY",
    "PERSONAL": "COMMUNITY",
    "BUSINESS": "BUSINESS_PRO",
    "ENTERPRISE": "ENTERPRISE",
    "LEGAL_PROFESSIONAL": "STARTER",
    "PROFESSIONAL": "STARTER",
}

VALID_CUSTOMER_ACCOUNT_TYPES = {"INDIVIDUAL", "BUSINESS", "ENTERPRISE", "LEGAL_PROFESSIONAL"}

def normalize_account_type(raw_type: Optional[str]) -> str:
    """Normalizes customer account type string into canonical identifier."""
    if not raw_type:
        return "INDIVIDUAL"
    cleaned = raw_type.strip().upper()
    if cleaned in ("INDIVIDUAL", "PERSONAL"):
        return "INDIVIDUAL"
    if cleaned in ("LEGAL_PROFESSIONAL", "PROFESSIONAL", "LAWYER"):
        return "LEGAL_PROFESSIONAL"
    if cleaned == "ENTERPRISE":
        return "ENTERPRISE"
    if cleaned == "BUSINESS":
        return "BUSINESS"
    # Legacy compatibility: if a legacy organization record has PLATFORM_ADMIN, map safely to ENTERPRISE
    if cleaned == "PLATFORM_ADMIN":
        return "ENTERPRISE"
    return cleaned

def is_personal_workspace(account_type: Optional[str]) -> bool:
    """Checks whether the account type corresponds to a personal / individual workspace."""
    return normalize_account_type(account_type) == "INDIVIDUAL"

def get_default_storage_quota(account_type: Optional[str]) -> int:
    """Returns default storage quota bytes for a given account type."""
    norm = normalize_account_type(account_type)
    return STORAGE_QUOTA_BY_ACCOUNT_TYPE.get(norm, 10 * 1024 * 1024 * 1024)

def get_default_subscription_tier(account_type: Optional[str]) -> str:
    """Returns safe default subscription tier for account onboarding."""
    norm = normalize_account_type(account_type)
    return DEFAULT_SUBSCRIPTION_BY_ACCOUNT.get(norm, "COMMUNITY")

def get_account_entitlements(
    account_type: Optional[str],
    subscription_tier: Optional[str] = "COMMUNITY",
    role: Optional[str] = "OWNER"
) -> Dict[str, Any]:
    """
    Computes active feature entitlements based strictly on the decoupling of:
    1. Account Type
    2. Subscription Plan
    3. Organization Membership Role
    """
    norm_type = normalize_account_type(account_type)
    norm_tier = (subscription_tier or "COMMUNITY").strip().upper()
    role_upper = (role or "MEMBER").strip().upper()

    is_personal = (norm_type == "INDIVIDUAL")
    is_org_owner_or_admin = role_upper in ("OWNER", "ADMIN") or has_permission(role_upper, PERMISSION_ORG_MANAGE)

    # Entitlements derivation
    # 1. Member invitations: strictly disallowed in Individual personal workspaces
    can_invite_members = (not is_personal) and is_org_owner_or_admin

    # 2. Department management: only for organizational workspaces
    can_manage_departments = (not is_personal) and is_org_owner_or_admin

    # 3. Audit trail visibility: requires business/enterprise/professional and role audit:read
    can_view_audit_logs = (not is_personal) and (has_permission(role_upper, PERMISSION_AUDIT_READ) or is_org_owner_or_admin)

    # 4. Playbook / Negotiation rules management
    can_manage_playbook = (not is_personal) and (has_permission(role_upper, PERMISSION_PLAYBOOK_MANAGE) or is_org_owner_or_admin)

    # 5. Multi-party approvals flow: organizational only
    can_access_approvals = not is_personal

    # 6. Vendor management
    can_manage_vendors = not is_personal

    # 7. Core CLM capabilities available across all workspaces
    can_export_docx = True
    can_use_ai_qa = True
    can_manage_obligations = True
    can_view_calendar = True

    return {
        "account_type": norm_type,
        "subscription_tier": norm_tier,
        "role": role_upper,
        "is_personal": is_personal,
        "workspace_category": "personal" if is_personal else "organization",
        "can_invite_members": can_invite_members,
        "can_manage_departments": can_manage_departments,
        "can_view_audit_logs": can_view_audit_logs,
        "can_manage_playbook": can_manage_playbook,
        "can_access_approvals": can_access_approvals,
        "can_manage_vendors": can_manage_vendors,
        "can_export_docx": can_export_docx,
        "can_use_ai_qa": can_use_ai_qa,
        "can_manage_obligations": can_manage_obligations,
        "can_view_calendar": can_view_calendar,
        "storage_quota_bytes": STORAGE_QUOTA_BY_ACCOUNT_TYPE.get(norm_type, 10 * 1024 * 1024 * 1024)
    }

def enforce_entitlement(
    account_type: Optional[str],
    subscription_tier: Optional[str],
    role: Optional[str],
    feature_name: str,
    action_description: str
) -> None:
    """
    Enforces that the current tenant and user role possess the required entitlement.
    Raises HTTP 403 Forbidden if not entitled.
    """
    entitlements = get_account_entitlements(account_type, subscription_tier, role)
    if not entitlements.get(feature_name, False):
        norm_type = entitlements["account_type"]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Feature '{action_description}' is not permitted for {norm_type} workspace "
                f"under role '{role}'."
            )
        )
