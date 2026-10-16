from typing import Optional
from fastapi import Request, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, OrganizationMember
from app.models.organization import Organization

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

async def get_current_token(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme)
) -> str:
    """
    Extracts the access token either from the Authorization Bearer header
    or from the HttpOnly access token cookie.
    Rejects missing tokens with 401 Unauthorized.
    """
    if bearer_token:
        return bearer_token
    
    cookie_token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        return cookie_token
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials required.",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_user(
    token: str = Depends(get_current_token),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Validates the access token signature and expiration, retrieves the user,
    and ensures strict authentication. Never falls back to hardcoded users.
    """
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer error=\"token_expired\""},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user record not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user

async def get_current_active_user(
    user: User = Depends(get_current_user)
) -> User:
    """
    Ensures that the authenticated user account is active.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
        )
    return user

async def get_current_tenant(
    token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_active_user),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db)
) -> Organization:
    """
    Resolves the organization tenant for the active user.
    Enforces that:
    1. If X-Tenant-ID is provided, it is checked against active OrganizationMember.
       If user is not an active member, immediately raises HTTP 403 Forbidden!
    2. If token contains an org_id claim, verify user has active membership in that org.
    3. Otherwise, defaults to user's first active membership.
    4. Never falls back to unassociated default organizations.
    """
    # 1. If explicit X-Tenant-ID header is provided, validate membership or fail immediately
    if x_tenant_id:
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == x_tenant_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.status == "ACTIVE"
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Not an active member of organization '{x_tenant_id}'."
            )
        org_stmt = select(Organization).where(Organization.id == x_tenant_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar_one_or_none()
        if org:
            return org
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found."
        )

    # 2. Check token's scoped org_id claim
    try:
        payload = decode_access_token(token)
        scoped_org_id = payload.get("org_id")
    except Exception:
        scoped_org_id = None

    if scoped_org_id:
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == scoped_org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.status == "ACTIVE"
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()
        if membership:
            org_stmt = select(Organization).where(Organization.id == scoped_org_id)
            org_res = await db.execute(org_stmt)
            org = org_res.scalar_one_or_none()
            if org:
                return org

    # 3. Default to user's first active membership
    stmt = select(OrganizationMember).where(
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.status == "ACTIVE"
    )
    result = await db.execute(stmt)
    first_member = result.scalars().first()
    
    if first_member:
        org_stmt = select(Organization).where(Organization.id == first_member.organization_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar_one_or_none()
        if org:
            return org

    # 4. No fallback! Strict tenant boundary enforcement
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No active organization tenant found for user."
    )

async def get_current_member(
    current_user: User = Depends(get_current_active_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> OrganizationMember:
    """
    Resolves the authoritative database OrganizationMember record for the caller
    in the active tenant organization. Never trusts frontend client claims.
    """
    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == tenant.id,
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.status == "ACTIVE"
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: No active membership found for user in organization {tenant.id}."
        )
    return membership

def require_permission(permission: str):
    """
    Reusable authorization dependency enforcing role-based access control.
    Verifies that the caller's server-side role holds the required permission.
    Returns HTTP 403 Forbidden if unauthorized.
    """
    from app.core.permissions import has_permission

    async def permission_checker(
        membership: OrganizationMember = Depends(get_current_member)
    ) -> OrganizationMember:
        if not has_permission(membership.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{membership.role}' lacks required permission '{permission}'."
            )
        return membership

    return permission_checker

async def get_current_platform_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Enforces that the caller is an active platform operational administrator.
    Strictly isolates platform administration from customer organization roles.
    Customer organization owners or admins cannot access platform endpoints.
    """
    role = getattr(current_user, "platform_role", None)
    if not role and current_user.is_super_admin:
        role = "PLATFORM_SUPER_ADMIN"

    if role not in ("PLATFORM_SUPER_ADMIN", "PLATFORM_SUPPORT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Platform administrator privileges required.",
        )
    return current_user

def require_platform_permission(permission: str):
    """
    Enforces specific platform operational permissions.
    """
    from app.core.permissions import has_platform_permission

    async def platform_permission_checker(
        platform_user: User = Depends(get_current_platform_user),
    ) -> User:
        role = getattr(platform_user, "platform_role", None) or ("PLATFORM_SUPER_ADMIN" if platform_user.is_super_admin else None)
        if not role or not has_platform_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Platform role '{role}' lacks required permission '{permission}'.",
            )
        return platform_user

    return platform_permission_checker

