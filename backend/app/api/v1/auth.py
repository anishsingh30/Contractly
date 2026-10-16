import logging
import re
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func
from app.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token
)
from app.models.base import utc_now, generate_uuid, ensure_utc
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.auth import RefreshToken, AccountToken, AccountTokenType
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    RefreshRequest,
    SwitchTenantRequest,
    MessageResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    ResendVerificationRequest,
    VerificationStatusResponse,
    UpdateProfileRequest
)
from app.dependencies import get_current_active_user, get_current_token
from app.core.security import decode_access_token
from app.core.permissions import get_role_permissions
from app.core.rate_limiter import auth_rate_limiter
from app.core.entitlements import (
    normalize_account_type,
    get_default_storage_quota,
    get_default_subscription_tier,
    get_account_entitlements,
    is_personal_workspace
)
from app.services.email.provider import email_service, get_email_service_health
from app.services.email.templates import (
    render_verification_email,
    render_password_reset_email
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

async def resolve_user_verification_status(db: AsyncSession, user_id: str) -> str:
    """
    Determines honest email verification status for a user:
    - VERIFIED: User has consumed a valid email verification token.
    - PENDING_VERIFICATION: Email provider is configured, but account is not yet verified.
    - BLOCKED_UNCONFIGURED: Email provider is not configured.
    """
    try:
        stmt = select(AccountToken).where(
            AccountToken.user_id == user_id,
            AccountToken.token_type == AccountTokenType.EMAIL_VERIFICATION.value,
            AccountToken.is_used == True
        )
        res = await db.execute(stmt)
        if res.scalars().first():
            return "VERIFIED"
    except Exception as e:
        logger.warning(f"Could not query account verification tokens (table may not exist in current schema): {e}")

    health = get_email_service_health()
    if not health["configured"]:
        return "BLOCKED_UNCONFIGURED"
    return "PENDING_VERIFICATION"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    Sets secure, HttpOnly authentication cookies for browser clients.
    Uses samesite="none" when secure=True to support cross-origin cloud deployments (e.g. Vercel + Render).
    """
    samesite_val = "none" if settings.SECURE_COOKIES else "lax"
    # 15-minute access token cookie
    response.set_cookie(
        key=settings.ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite=samesite_val,
        secure=settings.SECURE_COOKIES,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    # 7-day rotating refresh token cookie
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite=samesite_val,
        secure=settings.SECURE_COOKIES,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/"
    )

def clear_auth_cookies(response: Response) -> None:
    """
    Clears all authentication cookies from the client browser.
    """
    samesite_val = "none" if settings.SECURE_COOKIES else "lax"
    response.delete_cookie(
        key=settings.ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=samesite_val,
        secure=settings.SECURE_COOKIES
    )
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=samesite_val,
        secure=settings.SECURE_COOKIES
    )

@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    client_ip = request.client.host if request.client else "127.0.0.1"
    await auth_rate_limiter.check_register_rate_limit(client_ip)

    # Check if email already registered
    stmt = select(User).where(User.email == req.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    norm_type = normalize_account_type(req.account_type)

    # Enforce organization name for multi-user organizational workspaces
    if norm_type in ("BUSINESS", "ENTERPRISE") and (not req.organization_name or not req.organization_name.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Organization name is required when registering a {norm_type.capitalize()} workspace."
        )

    # Establish clean workspace title
    if req.organization_name and req.organization_name.strip():
        org_name = req.organization_name.strip()
    elif norm_type == "INDIVIDUAL":
        org_name = f"{req.full_name.strip()}'s Personal Workspace"
    elif norm_type == "LEGAL_PROFESSIONAL":
        org_name = f"{req.full_name.strip()} Legal Practice"
    else:
        org_name = f"{req.full_name.strip()}'s Workspace"

    # Unique slug generation
    base_slug = re.sub(r'[^a-z0-9\-]', '', org_name.lower().strip().replace(" ", "-")) or "workspace"
    slug = base_slug
    stmt_slug = select(Organization).where(Organization.slug == slug)
    existing_slug = await db.execute(stmt_slug)
    if existing_slug.scalar_one_or_none():
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    sub_tier = get_default_subscription_tier(norm_type)
    quota_bytes = get_default_storage_quota(norm_type)

    # Security Rule: The registrant is ALWAYS assigned role="OWNER" of their created workspace.
    # Client-supplied role names or admin flags are strictly disregarded.
    assigned_role = "OWNER"

    try:
        # 1. Create User
        new_user = User(
            email=req.email,
            password_hash=get_password_hash(req.password),
            full_name=req.full_name,
            is_active=True
        )
        db.add(new_user)
        await db.flush()

        # 2. Create Organization
        new_org = Organization(
            name=org_name,
            slug=slug,
            account_type=norm_type,
            subscription_tier=sub_tier,
            storage_quota_bytes=quota_bytes
        )
        db.add(new_org)
        await db.flush()

        # 3. Create Member Link (Atomic Owner assignment)
        member = OrganizationMember(
            organization_id=new_org.id,
            user_id=new_user.id,
            role=assigned_role,
            status="ACTIVE"
        )
        db.add(member)
        await db.flush()

        # 4. Issue short-lived access token
        access_token = create_access_token(
            subject=new_user.id,
            org_id=new_org.id,
            role=assigned_role
        )

        # 5. Issue rotating refresh token
        raw_refresh = generate_refresh_token()
        now = utc_now()
        refresh_record = RefreshToken(
            user_id=new_user.id,
            token_hash=hash_refresh_token(raw_refresh),
            family_id=generate_uuid(),
            family_created_at=now,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
            created_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:255]
        )
        db.add(refresh_record)

        # 6. Issue initial email verification token
        raw_verify_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_verify_token.encode()).hexdigest()
        try:
            async with db.begin_nested():
                verify_token_record = AccountToken(
                    user_id=new_user.id,
                    token_hash=token_hash,
                    token_type=AccountTokenType.EMAIL_VERIFICATION.value,
                    expires_at=now + timedelta(hours=24),
                    is_used=False
                )
                db.add(verify_token_record)
                await db.flush()
        except Exception as e:
            logger.warning(
                f"Account tokens table not available in current database schema ({type(e).__name__}); skipping initial verification token record."
            )
        await db.commit()

        # 7. Deliver verification email if email service is active
        email_health = get_email_service_health()
        if email_health["configured"]:
            verify_url = f"{settings.APP_BASE_URL.rstrip('/')}/verify-email?token={raw_verify_token}"
            subject, html, text = render_verification_email(new_user.full_name, verify_url)
            try:
                await email_service.send_email(new_user.email, subject, html, text)
            except Exception as e:
                logger.warning(f"Initial verification email send failed: {type(e).__name__}")
    except Exception:
        await db.rollback()
        raise

    # Set secure cookies for browser clients
    set_auth_cookies(response, access_token, raw_refresh)

    entitlements = get_account_entitlements(norm_type, sub_tier, assigned_role)
    init_verification_status = "PENDING_VERIFICATION" if email_health["configured"] else "BLOCKED_UNCONFIGURED"

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=raw_refresh,
        user=UserResponse(
            id=new_user.id,
            email=new_user.email,
            full_name=new_user.full_name,
            organization_id=new_org.id,
            organization_name=new_org.name,
            role=assigned_role,
            account_type=norm_type,
            subscription_tier=sub_tier,
            permissions=sorted(list(get_role_permissions(assigned_role))),
            entitlements=entitlements,
            email_verification_status=init_verification_status,
            is_super_admin=bool(getattr(new_user, "is_super_admin", False)),
            platform_role=getattr(new_user, "platform_role", None)
        )
    )

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    clean_email = req.email.strip().lower()
    client_ip = request.client.host if request.client else "127.0.0.1"
    await auth_rate_limiter.check_login_rate_limit(client_ip, clean_email)

    try:
        stmt = select(User).where(func.lower(User.email) == clean_email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
    except Exception as db_err:
        logging.getLogger("app.api.v1.auth").exception("Database query error during login: %s", db_err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection temporarily unavailable. Please retry in a few moments."
        )

    if not user or not verify_password(req.password, user.password_hash):
        await auth_rate_limiter.record_login_failure(client_ip, clean_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Clear prior failed login attempts on successful credentials
    await auth_rate_limiter.record_login_success(client_ip, clean_email)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive."
        )

    # Fetch active organization membership
    m_stmt = select(OrganizationMember).where(
        OrganizationMember.user_id == user.id,
        OrganizationMember.status == "ACTIVE"
    )
    m_res = await db.execute(m_stmt)
    membership = m_res.scalars().first()

    org_id = None
    org_name = None
    role = "LEGAL_MANAGER"
    account_type = "BUSINESS"
    subscription_tier = "COMMUNITY"

    if membership:
        org_id = membership.organization_id
        role = membership.role
        o_stmt = select(Organization).where(Organization.id == org_id)
        o_res = await db.execute(o_stmt)
        org = o_res.scalar_one_or_none()
        if org:
            org_name = org.name
            account_type = org.account_type
            subscription_tier = org.subscription_tier or "COMMUNITY"

    # Issue access token
    access_token = create_access_token(
        subject=user.id,
        org_id=org_id,
        role=role
    )

    # Issue rotating refresh token
    raw_refresh = generate_refresh_token()
    now = utc_now()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        family_id=generate_uuid(),
        family_created_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        is_revoked=False,
        created_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:255]
    )
    db.add(refresh_record)
    await db.commit()

    v_status = await resolve_user_verification_status(db, user.id)
    if settings.ENFORCE_EMAIL_VERIFICATION and v_status != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification is required before logging in. Please check your inbox for the verification link."
        )

    # Set secure HttpOnly cookies
    set_auth_cookies(response, access_token, raw_refresh)

    entitlements = get_account_entitlements(account_type, subscription_tier, role)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=raw_refresh,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            organization_id=org_id,
            organization_name=org_name,
            role=role,
            account_type=account_type,
            subscription_tier=subscription_tier,
            permissions=sorted(list(get_role_permissions(role))),
            entitlements=entitlements,
            email_verification_status=v_status,
            is_super_admin=bool(getattr(user, "is_super_admin", False)),
            platform_role=getattr(user, "platform_role", None)
        )
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    # 1. Read refresh token from HttpOnly cookie or request body
    raw_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not raw_token and body and body.refresh_token:
        raw_token = body.refresh_token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required."
        )

    # 2. Hash token and query database
    t_hash = hash_refresh_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == t_hash)
    res = await db.execute(stmt)
    token_record = res.scalar_one_or_none()

    if not token_record:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token."
        )

    now = utc_now()

    # 3. Security Check: Detect Refresh Token Reuse / Replay Attack (with 30s concurrent rotation grace period)
    if token_record.is_revoked:
        revoked_at = ensure_utc(token_record.revoked_at) if token_record.revoked_at else None
        grace_seconds = getattr(settings, "REFRESH_TOKEN_GRACE_SECONDS", 0)
        is_grace_window = (grace_seconds > 0) and revoked_at and ((now - revoked_at) <= timedelta(seconds=grace_seconds))

        if is_grace_window:
            # Concurrent refresh request within 30-second rotation grace window.
            # Find the active unrevoked successor token in the family to prevent race-condition session destruction.
            succ_stmt = select(RefreshToken).where(
                RefreshToken.family_id == token_record.family_id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > now
            ).order_by(RefreshToken.created_at.desc())
            succ_res = await db.execute(succ_stmt)
            active_token = succ_res.scalars().first()
            if active_token:
                # Retrieve user to issue access token
                u_stmt = select(User).where(User.id == active_token.user_id)
                u_res = await db.execute(u_stmt)
                user = u_res.scalar_one_or_none()
                if user and user.is_active:
                    m_stmt = select(OrganizationMember).where(
                        OrganizationMember.user_id == user.id,
                        OrganizationMember.status == "ACTIVE"
                    )
                    m_res = await db.execute(m_stmt)
                    membership = m_res.scalars().first()
                    org_id = membership.organization_id if membership else None
                    role = membership.role if membership else "LEGAL_MANAGER"
                    o_name = None
                    acc_type = "BUSINESS"
                    sub_tier = "COMMUNITY"
                    if org_id:
                        o_stmt = select(Organization).where(Organization.id == org_id)
                        o_res = await db.execute(o_stmt)
                        org = o_res.scalar_one_or_none()
                        if org:
                            o_name = org.name
                            acc_type = org.account_type
                            sub_tier = org.subscription_tier or "COMMUNITY"

                    new_access_token = create_access_token(
                        subject=user.id,
                        org_id=org_id,
                        role=role
                    )
                    # Update access token cookie
                    response.set_cookie(
                        key=settings.ACCESS_TOKEN_COOKIE_NAME,
                        value=new_access_token,
                        httponly=True,
                        samesite="lax",
                        secure=settings.SECURE_COOKIES,
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        path="/"
                    )
                    entitlements = get_account_entitlements(acc_type, sub_tier, role)
                    v_status = await resolve_user_verification_status(db, user.id)
                    return TokenResponse(
                        access_token=new_access_token,
                        token_type="bearer",
                        refresh_token="rotated_concurrently",
                        user=UserResponse(
                            id=user.id,
                            email=user.email,
                            full_name=user.full_name,
                            avatar_url=user.avatar_url,
                            organization_id=org_id,
                            organization_name=o_name,
                            role=role,
                            account_type=acc_type,
                            subscription_tier=sub_tier,
                            permissions=sorted(list(get_role_permissions(role))),
                            entitlements=entitlements,
                            email_verification_status=v_status,
                            is_super_admin=getattr(user, "is_super_admin", False),
                            platform_role=getattr(user, "platform_role", None)
                        )
                    )

        # Revoke the entire token family immediately!
        fam_stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == token_record.family_id)
            .values(is_revoked=True, revoked_at=now)
        )
        await db.execute(fam_stmt)
        await db.commit()
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_REUSE_DETECTED: Revoked refresh token presented. All sessions in this lineage have been terminated."
        )

    # 4. Check expiration (7-day window)
    if ensure_utc(token_record.expires_at) < now:
        token_record.is_revoked = True
        token_record.revoked_at = now
        await db.commit()
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again."
        )

    # 5. Check maximum absolute session lifetime (30 days)
    session_age = now - ensure_utc(token_record.family_created_at)
    if session_age > timedelta(days=settings.SESSION_MAX_LIFETIME_DAYS):
        token_record.is_revoked = True
        token_record.revoked_at = now
        await db.commit()
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SESSION_EXPIRED: Maximum session lifetime exceeded. Please log in again."
        )

    # 6. Verify user is active
    u_stmt = select(User).where(User.id == token_record.user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user or not user.is_active:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found."
        )

    # 7. Fetch user organization membership & role
    m_stmt = select(OrganizationMember).where(
        OrganizationMember.user_id == user.id,
        OrganizationMember.status == "ACTIVE"
    )
    m_res = await db.execute(m_stmt)
    membership = m_res.scalars().first()

    org_id = None
    org_name = None
    role = "LEGAL_MANAGER"
    account_type = "BUSINESS"
    subscription_tier = "COMMUNITY"

    if membership:
        org_id = membership.organization_id
        role = membership.role
        o_stmt = select(Organization).where(Organization.id == org_id)
        o_res = await db.execute(o_stmt)
        org = o_res.scalar_one_or_none()
        if org:
            org_name = org.name
            account_type = org.account_type
            subscription_tier = org.subscription_tier or "COMMUNITY"

    # 8. Rotate Refresh Token:
    token_record.is_revoked = True
    token_record.revoked_at = now

    # Create new rotating refresh token in the same family
    new_raw_refresh = generate_refresh_token()
    new_refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_raw_refresh),
        family_id=token_record.family_id,
        family_created_at=token_record.family_created_at,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        is_revoked=False,
        created_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:255]
    )
    db.add(new_refresh_record)
    await db.commit()

    # 9. Issue new 15-minute access token
    new_access_token = create_access_token(
        subject=user.id,
        org_id=org_id,
        role=role
    )

    # 10. Set new cookies on response
    set_auth_cookies(response, new_access_token, new_raw_refresh)

    entitlements = get_account_entitlements(account_type, subscription_tier, role)
    v_status = await resolve_user_verification_status(db, user.id)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        refresh_token=new_raw_refresh,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            organization_id=org_id,
            organization_name=org_name,
            role=role,
            account_type=account_type,
            subscription_tier=subscription_tier,
            permissions=sorted(list(get_role_permissions(role))),
            entitlements=entitlements,
            email_verification_status=v_status,
            is_super_admin=bool(getattr(user, "is_super_admin", False)),
            platform_role=getattr(user, "platform_role", None)
        )
    )

@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    raw_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not raw_token and body and body.refresh_token:
        raw_token = body.refresh_token

    if raw_token:
        t_hash = hash_refresh_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == t_hash)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if record and not record.is_revoked:
            record.is_revoked = True
            record.revoked_at = utc_now()
            await db.commit()

    clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out.")

@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_active_user),
    token: str = Depends(get_current_token),
    db: AsyncSession = Depends(get_db)
):
    # Check if token contains a specific scoped org_id
    scoped_org_id = None
    try:
        payload = decode_access_token(token)
        scoped_org_id = payload.get("org_id")
    except Exception:
        pass

    membership = None
    if scoped_org_id:
        m_stmt = select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == scoped_org_id,
            OrganizationMember.status == "ACTIVE"
        )
        m_res = await db.execute(m_stmt)
        membership = m_res.scalar_one_or_none()

    if not membership:
        m_stmt = select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == "ACTIVE"
        )
        m_res = await db.execute(m_stmt)
        membership = m_res.scalars().first()

    org_id = None
    org_name = None
    role = "LEGAL_MANAGER"
    account_type = "BUSINESS"
    subscription_tier = "COMMUNITY"

    if membership:
        org_id = membership.organization_id
        role = membership.role
        o_stmt = select(Organization).where(Organization.id == org_id)
        o_res = await db.execute(o_stmt)
        org = o_res.scalar_one_or_none()
        if org:
            org_name = org.name
            account_type = org.account_type
            subscription_tier = org.subscription_tier or "COMMUNITY"

    entitlements = get_account_entitlements(account_type, subscription_tier, role)
    v_status = await resolve_user_verification_status(db, user.id)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=org_id,
        organization_name=org_name,
        role=role,
        account_type=account_type,
        subscription_tier=subscription_tier,
        permissions=sorted(list(get_role_permissions(role))),
        entitlements=entitlements,
        email_verification_status=v_status,
        is_super_admin=bool(getattr(user, "is_super_admin", False)),
        platform_role=getattr(user, "platform_role", None)
    )

@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_active_user),
    token: str = Depends(get_current_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the authenticated user's profile information.
    Only allows editing safely supported user fields (e.g. full_name).
    Never exposes or permits modifying private fields of other users.
    """
    if body.full_name is not None:
        user.full_name = body.full_name
        await db.commit()
        await db.refresh(user)

    return await get_me(user=user, token=token, db=db)

@router.post("/switch-tenant", response_model=TokenResponse)
async def switch_tenant(
    req: SwitchTenantRequest,
    response: Response,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Switches active organization tenant for the authenticated user.
    Strictly verifies active OrganizationMember in the target organization.
    Returns HTTP 403 Forbidden if user is not an active member.
    Issues a new access token scoped to the target organization and updates cookies.
    """
    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == req.organization_id,
        OrganizationMember.user_id == user.id,
        OrganizationMember.status == "ACTIVE"
    )
    res = await db.execute(stmt)
    membership = res.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Not an active member of organization '{req.organization_id}'."
        )

    # Fetch target organization
    org_stmt = select(Organization).where(Organization.id == req.organization_id)
    org_res = await db.execute(org_stmt)
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target organization not found."
        )

    # Issue new access token scoped to target organization and membership role
    new_access_token = create_access_token(
        subject=user.id,
        org_id=org.id,
        role=membership.role
    )

    # Update access token cookie
    response.set_cookie(
        key=settings.ACCESS_TOKEN_COOKIE_NAME,
        value=new_access_token,
        httponly=True,
        samesite="lax",
        secure=settings.SECURE_COOKIES,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )

    sub_tier = org.subscription_tier or "COMMUNITY"
    entitlements = get_account_entitlements(org.account_type, sub_tier, membership.role)
    v_status = await resolve_user_verification_status(db, user.id)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            organization_id=org.id,
            organization_name=org.name,
            role=membership.role,
            account_type=org.account_type,
            subscription_tier=sub_tier,
            permissions=sorted(list(get_role_permissions(membership.role))),
            entitlements=entitlements,
            email_verification_status=v_status,
            is_super_admin=bool(getattr(user, "is_super_admin", False)),
            platform_role=getattr(user, "platform_role", None)
        )
    )

@router.get("/my-organizations")
async def get_my_organizations(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns only the organizations where the authenticated user has an active membership.
    """
    stmt = (
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, Organization.id == OrganizationMember.organization_id)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == "ACTIVE"
        )
    )
    res = await db.execute(stmt)
    orgs = res.all()
    return [
        {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "account_type": org.account_type,
            "subscription_tier": org.subscription_tier,
            "role": role,
            "is_personal": is_personal_workspace(org.account_type)
        }
        for org, role in orgs
    ]

@router.get("/verification-status", response_model=VerificationStatusResponse)
async def get_verification_status():
    """
    Reports email delivery and verification configuration status.
    Exposes safe diagnostics without secrets or credentials.
    """
    health = get_email_service_health()
    if health["configured"]:
        return VerificationStatusResponse(
            email_delivery_configured=True,
            verification_status="CONFIGURED",
            provider=health["provider"],
            detail="Email delivery service is configured and operational."
        )
    return VerificationStatusResponse(
        email_delivery_configured=False,
        verification_status="BLOCKED_UNCONFIGURED",
        provider=health["provider"],
        detail=f"Email delivery service is unconfigured. Missing: {', '.join(health['missing_fields'])}"
    )

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiates password reset for a user email.
    Always returns a generic message to prevent account enumeration.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    await auth_rate_limiter.check_password_reset_rate_limit(client_ip, req.email)

    stmt = select(User).where(User.email == req.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if user and user.is_active:
        now = utc_now()
        # Invalidate previous unused reset tokens
        stmt_inv = (
            update(AccountToken)
            .where(
                AccountToken.user_id == user.id,
                AccountToken.token_type == AccountTokenType.PASSWORD_RESET.value,
                AccountToken.is_used == False
            )
            .values(is_used=True, used_at=now)
        )
        await db.execute(stmt_inv)

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        reset_token = AccountToken(
            user_id=user.id,
            token_hash=token_hash,
            token_type=AccountTokenType.PASSWORD_RESET.value,
            expires_at=now + timedelta(hours=1),
            is_used=False
        )
        db.add(reset_token)
        await db.commit()

        reset_url = f"{settings.APP_BASE_URL.rstrip('/')}/reset-password?token={raw_token}"
        subject, html, text = render_password_reset_email(user.full_name, reset_url)
        try:
            await email_service.send_email(user.email, subject, html, text)
        except Exception as e:
            logger.warning(f"Failed to dispatch password reset email: {type(e).__name__}")

    return MessageResponse(
        message="If an account exists with this email address, password reset instructions have been sent."
    )

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Resets password using a single-use token.
    Immediately revokes all existing refresh sessions for the account.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    await auth_rate_limiter.check_password_reset_rate_limit(client_ip)

    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    now = utc_now()

    stmt = select(AccountToken).where(
        AccountToken.token_hash == token_hash,
        AccountToken.token_type == AccountTokenType.PASSWORD_RESET.value
    )
    res = await db.execute(stmt)
    token_record = res.scalar_one_or_none()

    if not token_record or token_record.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used password reset token."
        )

    if token_record.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired."
        )

    # Fetch user
    u_stmt = select(User).where(User.id == token_record.user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive or not found."
        )

    # Update password hash
    user.password_hash = get_password_hash(req.new_password)

    # Invalidate token
    token_record.is_used = True
    token_record.used_at = now

    # Revoke all active refresh sessions for user
    stmt_revoke = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked == False
        )
        .values(
            is_revoked=True,
            revoked_at=now
        )
    )
    await db.execute(stmt_revoke)
    await db.commit()

    # Clear auth cookies
    clear_auth_cookies(response)

    return MessageResponse(
        message="Password has been successfully reset. Please log in with your new password."
    )

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    req: VerifyEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Verifies user email address using a single-use token.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    await auth_rate_limiter.check_verification_rate_limit(client_ip)

    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    now = utc_now()

    stmt = select(AccountToken).where(
        AccountToken.token_hash == token_hash,
        AccountToken.token_type == AccountTokenType.EMAIL_VERIFICATION.value
    )
    res = await db.execute(stmt)
    token_record = res.scalar_one_or_none()

    if not token_record or token_record.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used email verification token."
        )

    if token_record.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification token has expired."
        )

    token_record.is_used = True
    token_record.used_at = now
    await db.commit()

    return MessageResponse(
        message="Email address has been successfully verified."
    )

@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    req: ResendVerificationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Resends email verification instructions.
    Returns explicit 503 if provider is unconfigured.
    Returns generic privacy-safe response if provider is active.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    await auth_rate_limiter.check_verification_rate_limit(client_ip, req.email)

    health = get_email_service_health()
    if not health["configured"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery service is currently unconfigured. Cannot dispatch verification emails."
        )

    stmt = select(User).where(User.email == req.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if user and user.is_active:
        # Check if already verified
        v_stmt = select(AccountToken).where(
            AccountToken.user_id == user.id,
            AccountToken.token_type == AccountTokenType.EMAIL_VERIFICATION.value,
            AccountToken.is_used == True
        )
        v_res = await db.execute(v_stmt)
        if not v_res.scalars().first():
            now = utc_now()
            # Invalidate prior unused tokens
            stmt_inv = (
                update(AccountToken)
                .where(
                    AccountToken.user_id == user.id,
                    AccountToken.token_type == AccountTokenType.EMAIL_VERIFICATION.value,
                    AccountToken.is_used == False
                )
                .values(is_used=True, used_at=now)
            )
            await db.execute(stmt_inv)

            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            new_token = AccountToken(
                user_id=user.id,
                token_hash=token_hash,
                token_type=AccountTokenType.EMAIL_VERIFICATION.value,
                expires_at=now + timedelta(hours=24),
                is_used=False
            )
            db.add(new_token)
            await db.commit()

            verify_url = f"{settings.APP_BASE_URL.rstrip('/')}/verify-email?token={raw_token}"
            subject, html, text = render_verification_email(user.full_name, verify_url)
            try:
                await email_service.send_email(user.email, subject, html, text)
            except Exception as e:
                logger.warning(f"Failed to resend verification email: {type(e).__name__}")

    return MessageResponse(
        message="If an unverified account exists with this email address, a verification link has been sent."
    )

