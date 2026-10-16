from typing import Set, Dict

# Explicit Permission Constants
PERMISSION_CONTRACTS_READ = "contracts:read"
PERMISSION_CONTRACTS_CREATE = "contracts:create"
PERMISSION_CONTRACTS_DELETE = "contracts:delete"
PERMISSION_CONTRACTS_TRANSITION = "contracts:transition"
PERMISSION_CONTRACTS_TERMINATE = "contracts:terminate"
PERMISSION_CONTRACTS_RENEW = "contracts:renew"

PERMISSION_REDLINES_READ = "redlines:read"
PERMISSION_REDLINES_MANAGE = "redlines:manage"

PERMISSION_OBLIGATIONS_READ = "obligations:read"
PERMISSION_OBLIGATIONS_CREATE = "obligations:create"
PERMISSION_OBLIGATIONS_UPDATE = "obligations:update"
PERMISSION_OBLIGATIONS_UPLOAD_EVIDENCE = "obligations:upload_evidence"

PERMISSION_ORG_READ = "org:read"
PERMISSION_ORG_MANAGE = "org:manage"
PERMISSION_AUDIT_READ = "audit:read"

PERMISSION_VENDORS_READ = "vendors:read"
PERMISSION_VENDORS_MANAGE = "vendors:manage"
PERMISSION_PLAYBOOK_READ = "playbook:read"
PERMISSION_PLAYBOOK_MANAGE = "playbook:manage"
PERMISSION_APPROVALS_DECIDE = "approvals:decide"

# Comprehensive Role-to-Permissions Mapping for Contractly
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "OWNER": {
        "*"
    },
    "ADMIN": {
        "org:read",
        "org:manage",
        "audit:read",
        "contracts:*",
        "obligations:*",
        "vendors:*",
        "playbook:*",
        "approvals:*",
        "redlines:*",
    },
    "LEGAL_MANAGER": {
        "org:read",
        "audit:read",
        "contracts:*",
        "obligations:*",
        "vendors:*",
        "playbook:*",
        "approvals:*",
        "redlines:*",
    },
    "LEGAL_REVIEWER": {
        "org:read",
        "audit:read",
        "contracts:read",
        "contracts:transition",
        "redlines:read",
        "redlines:manage",
        "obligations:read",
        "obligations:upload_evidence",
        "vendors:read",
        "playbook:read",
        "approvals:decide",
    },
    "PROCUREMENT": {
        "org:read",
        "contracts:read",
        "contracts:create",
        "contracts:transition",
        "redlines:read",
        "obligations:read",
        "obligations:create",
        "obligations:update",
        "obligations:upload_evidence",
        "vendors:*",
        "approvals:decide",
    },
    "FINANCE": {
        "org:read",
        "contracts:read",
        "obligations:read",
        "vendors:read",
        "approvals:decide",
    },
    "HR": {
        "org:read",
        "contracts:read",
        "contracts:create",
        "obligations:read",
        "approvals:decide",
    },
    "EMPLOYEE": {
        "org:read",
        "contracts:read_own",
        "requests:create",
    },
    "MEMBER": {
        "org:read",
        "contracts:read_own",
        "requests:create",
    },
    "VIEWER": {
        "org:read",
        "contracts:read",
        "obligations:read",
    },
}

# Explicit Platform Operational Permission Constants (Section 2 & 3)
PLATFORM_PERM_SYSTEM_READ = "platform:system_read"
PLATFORM_PERM_METRICS_READ = "platform:metrics_read"
PLATFORM_PERM_TENANTS_READ = "platform:tenants_read"
PLATFORM_PERM_AUDIT_READ = "platform:audit_read"
PLATFORM_PERM_SYSTEM_MANAGE = "platform:system_manage"
PLATFORM_PERM_CONVERSATIONS_OVERSIGHT = "platform:conversations:oversight"

# Platform Role-to-Permissions Mapping (Strictly Isolated from Customer Content)
PLATFORM_ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "PLATFORM_SUPER_ADMIN": {
        "platform:*",
    },
    "PLATFORM_SUPPORT": {
        "platform:system_read",
        "platform:metrics_read",
        "platform:tenants_read",
        "platform:audit_read",
    },
}

def has_permission(role: str, permission: str) -> bool:
    """
    Checks if a customer organization role possesses the specified permission.
    Supports global wildcard '*' and domain wildcards like 'contracts:*'.
    """
    perms = ROLE_PERMISSIONS.get(role.upper(), set())
    if "*" in perms:
        return True
    if permission in perms:
        return True
    # Domain wildcard check: 'contracts:*' matches 'contracts:read'
    if ":" in permission:
        domain = permission.split(":", 1)[0]
        if f"{domain}:*" in perms:
            return True
    return False

def has_platform_permission(role: str, permission: str) -> bool:
    """
    Checks if a platform operational role possesses the specified platform permission.
    Supports platform wildcard 'platform:*'.
    """
    perms = PLATFORM_ROLE_PERMISSIONS.get(role.upper(), set())
    if "*" in perms or "platform:*" in perms:
        return True
    if permission in perms:
        return True
    return False

def get_role_permissions(role: str) -> Set[str]:
    """Returns the set of permissions assigned to a given customer role."""
    return ROLE_PERMISSIONS.get(role.upper(), set())

def get_platform_role_permissions(role: str) -> Set[str]:
    """Returns the set of permissions assigned to a given platform role."""
    return PLATFORM_ROLE_PERMISSIONS.get(role.upper(), set())

