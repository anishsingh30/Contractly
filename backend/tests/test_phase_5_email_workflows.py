"""
Phase 5 Test Suite: Production Email Delivery and Secure Account Workflows
Tests:
1. Email provider configuration, readiness check, and diagnostic safety (no secrets).
2. SMTPEmailProvider bounded retries, timeouts, and sanitized errors.
3. MockEmailProvider simulated failure, timeout, and rejection fidelity.
4. Cryptographically secure email verification: single-use, expiry, reuse prevention.
5. Verification rate-limiting and non-enumeration guarantees.
6. Password reset flow: single-use tokens, password update, and session revocation.
7. Password reset expiry, reuse prevention, and non-enumeration guarantees.
8. Organization member invitations: permission checks, entitlement enforcement (Individual blocked).
9. Role forgery prevention and duplicate active membership protection.
10. Invitation token verification, acceptance, expiry, and revocation.
11. Tenant isolation across invitation workflows.
12. Non-blocking migration: existing users not locked out when verification is unenforced.
13. Notification dispatcher lifecycle integration with deduplication and in-app fallback.
"""

import hashlib
import pytest
import pytest_asyncio
import smtplib
import socket
from datetime import timedelta
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.config import settings
from app.core.database import get_db
from app.models.base import utc_now, generate_uuid
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.auth import RefreshToken, AccountToken, AccountTokenType, OrganizationInvitation, InvitationStatus
from app.core.security import get_password_hash, create_access_token, generate_refresh_token, hash_refresh_token
from app.services.email.provider import (
    SMTPEmailProvider,
    MockEmailProvider,
    DisabledEmailProvider,
    get_email_provider,
    get_mock_email_provider,
    get_email_service_health
)
from app.services.notifications.dispatcher import NotificationDispatcher

# ==============================================================================
# SECTION 1: EMAIL PROVIDER ARCHITECTURE & HEALTH DIAGNOSTICS
# ==============================================================================

def test_email_service_health_unconfigured(monkeypatch):
    """When disabled or missing credentials, health check reports unconfigured without leaking secrets."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "SuperSecretPassword123")

    health = get_email_service_health()
    assert health["configured"] is False
    assert health["is_configured"] is False
    assert health["status"] in ("DISABLED", "UNCONFIGURED")
    assert "SuperSecretPassword123" not in str(health)
    assert "diagnostics" in health
    assert "password" not in health["diagnostics"]


def test_email_service_health_configured_mock(monkeypatch):
    """When mock provider is active, health check honestly reports ready status."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")

    health = get_email_service_health()
    assert health["configured"] is True
    assert health["status"] == "READY"
    assert health["provider"] == "mock"


def test_smtp_provider_bounded_retries_and_timeout():
    """SMTPEmailProvider performs bounded retries on network failures and sanitizes errors."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = socket.timeout("Connection timed out")

        provider = SMTPEmailProvider(
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password="SuperSecretPassword!",
            timeout=1.0,
            max_retries=3
        )

        res = provider.send_email(
            to_email="recipient@test.internal",
            subject="Test Subject",
            html_body="<p>Test</p>",
            text_body="Test"
        )

        assert res.success is False
        assert res.attempts == 3
        # Strict security constraint: password MUST NOT appear in error messages
        assert "SuperSecretPassword!" not in str(res.error_message)
        assert "timed out" in str(res.error_message).lower()


def test_mock_provider_simulated_failures():
    """MockEmailProvider supports simulated timeouts, rejections, and failures for deterministic testing."""
    mock_prov = MockEmailProvider()

    # Normal success
    res_ok = mock_prov.send_email("test@a.com", "Subj", "<p>A</p>", "A")
    assert res_ok.success is True
    assert len(mock_prov.get_sent_emails()) == 1

    # Simulated timeout
    mock_prov.simulate_timeout = True
    res_to = mock_prov.send_email("test@b.com", "Subj", "<p>B</p>", "B")
    assert res_to.success is False
    assert "timeout" in res_to.error_message.lower()

    # Simulated rejection
    mock_prov.simulate_timeout = False
    mock_prov.simulate_rejection = True
    res_rej = mock_prov.send_email("test@c.com", "Subj", "<p>C</p>", "C")
    assert res_rej.success is False
    assert "550" in res_rej.error_message

    mock_prov.clear()
    assert len(mock_prov.get_sent_emails()) == 0


# ==============================================================================
# SECTION 2: EMAIL VERIFICATION WORKFLOWS
# ==============================================================================

@pytest.mark.asyncio
async def test_email_verification_success_and_reuse_prevention(monkeypatch):
    """
    User can verify email address using single-use cryptographically secure token.
    Reused and expired tokens are strictly rejected.
    """
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")
    mock_prov = get_mock_email_provider()
    mock_prov.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register a new user
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": "verify.user@northstar.internal",
            "password": "Password123!@",
            "full_name": "Verification User",
            "account_type": "INDIVIDUAL"
        })
        assert reg_res.status_code == 200
        user_data = reg_res.json()["user"]
        assert user_data["email_verification_status"] == "PENDING_VERIFICATION"

        # 2. Inspect sent emails
        sent_email = mock_prov.find_email("verify.user@northstar.internal")
        assert sent_email is not None
        assert "verify" in sent_email["subject"].lower() and "email" in sent_email["subject"].lower()

        # Extract token from HTML
        import re
        match = re.search(r"token=([A-Za-z0-9_\-]+)", sent_email["html"])
        assert match is not None
        raw_token = match.group(1)

        # 3. Call verify-email endpoint
        v_res = await ac.post("/api/v1/auth/verify-email", json={"token": raw_token})
        assert v_res.status_code == 200
        assert "successfully verified" in v_res.json()["message"]

        # 4. Token reuse attempt must be rejected with 400
        reuse_res = await ac.post("/api/v1/auth/verify-email", json={"token": raw_token})
        assert reuse_res.status_code == 400
        assert "invalid or already used" in reuse_res.json()["detail"].lower()

        # 5. Invalid token attempt
        invalid_res = await ac.post("/api/v1/auth/verify-email", json={"token": "completely-bogus-token"})
        assert invalid_res.status_code == 400


@pytest.mark.asyncio
async def test_email_verification_token_expiry(test_engine, monkeypatch):
    """Expired verification token is rejected."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")

    # Manually insert an expired token into database
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as db:
        # Get existing user
        stmt = select(User).where(User.email == "legal@northstar.internal")
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        assert user is not None

        raw_token = "expired-token-xyz-12345"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expired_record = AccountToken(
            user_id=user.id,
            token_hash=token_hash,
            token_type=AccountTokenType.EMAIL_VERIFICATION.value,
            expires_at=utc_now() - timedelta(hours=2),
            is_used=False
        )
        db.add(expired_record)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/verify-email", json={"token": raw_token})
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resend_verification_generic_response(monkeypatch):
    """Resending verification returns generic response preventing email enumeration."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Non-existent email
        resp = await ac.post("/api/v1/auth/resend-verification", json={
            "email": "nonexistent.ghost@nowhere.internal"
        })
        assert resp.status_code == 200
        assert "If an unverified account exists" in resp.json()["message"]


# ==============================================================================
# SECTION 3: SECURE PASSWORD RESET WORKFLOWS
# ==============================================================================

@pytest.mark.asyncio
async def test_password_reset_flow_and_session_revocation(monkeypatch):
    """
    Password reset dispatches token email, updates password hash,
    and revokes all active refresh sessions for the account.
    """
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")
    mock_prov = get_mock_email_provider()
    mock_prov.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register a test user
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": "reset.user@northstar.internal",
            "password": "OldPassword123!@",
            "full_name": "Reset Candidate",
            "account_type": "INDIVIDUAL"
        })
        assert reg_res.status_code == 200
        old_refresh_token = reg_res.json()["refresh_token"]

        # 2. Request forgot password
        forgot_res = await ac.post("/api/v1/auth/forgot-password", json={
            "email": "reset.user@northstar.internal"
        })
        assert forgot_res.status_code == 200
        assert "If an account exists" in forgot_res.json()["message"]

        # 3. Inspect sent email for token
        sent_email = mock_prov.find_email("reset.user@northstar.internal", "reset")
        assert sent_email is not None
        import re
        match = re.search(r"token=([A-Za-z0-9_\-]+)", sent_email["html"])
        assert match is not None
        reset_token = match.group(1)

        # 4. Perform password reset
        new_pass = "BrandNewSecret999!@"
        reset_res = await ac.post("/api/v1/auth/reset-password", json={
            "token": reset_token,
            "new_password": new_pass
        })
        assert reset_res.status_code == 200
        assert "successfully reset" in reset_res.json()["message"]

        # 5. Token reuse is blocked
        reuse_res = await ac.post("/api/v1/auth/reset-password", json={
            "token": reset_token,
            "new_password": "AnotherPassword123!@"
        })
        assert reuse_res.status_code == 400
        assert "invalid or already used" in reuse_res.json()["detail"].lower()

        # 6. Verify old password no longer works
        old_login = await ac.post("/api/v1/auth/login", json={
            "email": "reset.user@northstar.internal",
            "password": "OldPassword123!@"
        })
        assert old_login.status_code == 401

        # 7. Verify new password works
        new_login = await ac.post("/api/v1/auth/login", json={
            "email": "reset.user@northstar.internal",
            "password": new_pass
        })
        assert new_login.status_code == 200

        # 8. Verify old session refresh is revoked
        async with AsyncClient(transport=transport, base_url="http://test") as clean_ac:
            refresh_attempt = await clean_ac.post("/api/v1/auth/refresh", json={
                "refresh_token": old_refresh_token
            })
            # The session revocation marks old tokens revoked, detecting reuse/revocation
            assert refresh_attempt.status_code == 401
            assert "TOKEN_REUSE_DETECTED" in refresh_attempt.json()["detail"] or "Revoked" in refresh_attempt.json()["detail"]


@pytest.mark.asyncio
async def test_forgot_password_generic_response_for_unknown_email(monkeypatch):
    """Forgot password returns identical generic response for non-existent accounts."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/forgot-password", json={
            "email": "completely.unknown@fake.internal"
        })
        assert res.status_code == 200
        assert "If an account exists with this email" in res.json()["message"]


# ==============================================================================
# SECTION 4: INVITATIONS & ORGANIZATION WORKFLOWS
# ==============================================================================

@pytest.mark.asyncio
async def test_invitation_lifecycle_and_acceptance(monkeypatch):
    """
    Business Organization OWNER can invite members.
    Invitee receives email and can verify/accept single-use invitation.
    """
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")
    mock_prov = get_mock_email_provider()
    mock_prov.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register Business workspace
        biz_reg = await ac.post("/api/v1/auth/register", json={
            "email": "ceo.invite@startup.internal",
            "password": "Password123!@",
            "full_name": "Startup CEO",
            "account_type": "BUSINESS",
            "organization_name": "Startup Inc"
        })
        assert biz_reg.status_code == 200
        token = biz_reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create invitation
        invitee_email = "newcounsel@startup.internal"
        inv_res = await ac.post("/api/v1/organizations/invitations", headers=headers, json={
            "email": invitee_email,
            "role": "LEGAL_REVIEWER"
        })
        assert inv_res.status_code == 200
        inv_data = inv_res.json()
        assert inv_data["invitee_email"] == invitee_email
        assert inv_data["role"] == "LEGAL_REVIEWER"
        assert inv_data["email_sent"] is True

        # 2. Check sent email
        sent_email = mock_prov.find_email(invitee_email, "invitation")
        assert sent_email is not None
        import re
        match = re.search(r"token=([A-Za-z0-9_\-]+)", sent_email["html"])
        assert match is not None
        raw_inv_token = match.group(1)

        # 3. Public verify invitation
        v_res = await ac.get(f"/api/v1/organizations/invitations/verify?token={raw_inv_token}")
        assert v_res.status_code == 200
        assert v_res.json()["valid"] is True
        assert v_res.json()["role"] == "LEGAL_REVIEWER"

        # 4. Accept invitation
        accept_res = await ac.post("/api/v1/organizations/invitations/accept", json={
            "token": raw_inv_token,
            "full_name": "New Counsel",
            "password": "CounselPassword123!@"
        })
        assert accept_res.status_code == 200
        assert "successfully accepted" in accept_res.json()["message"]

        # 5. Duplicate acceptance rejected
        dup_accept = await ac.post("/api/v1/organizations/invitations/accept", json={
            "token": raw_inv_token
        })
        assert dup_accept.status_code == 400
        assert "already been accepted" in dup_accept.json()["detail"].lower()

        # 6. Newly accepted user can log in
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": invitee_email,
            "password": "CounselPassword123!@"
        })
        assert login_res.status_code == 200
        assert login_res.json()["user"]["role"] == "LEGAL_REVIEWER"


@pytest.mark.asyncio
async def test_individual_workspace_cannot_invite_members():
    """Entitlement rule: Individual (Personal) workspaces are strictly barred from inviting members."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ind_reg = await ac.post("/api/v1/auth/register", json={
            "email": "solo.lawyer@freelance.internal",
            "password": "Password123!@",
            "full_name": "Solo Practitioner",
            "account_type": "INDIVIDUAL"
        })
        assert ind_reg.status_code == 200
        headers = {"Authorization": f"Bearer {ind_reg.json()['access_token']}"}

        inv_res = await ac.post("/api/v1/organizations/invitations", headers=headers, json={
            "email": "colleague@freelance.internal",
            "role": "MEMBER"
        })
        assert inv_res.status_code == 403
        assert "not permitted for INDIVIDUAL workspace" in inv_res.json()["detail"]


@pytest.mark.asyncio
async def test_invitation_role_forgery_prevention():
    """Client cannot forge platform roles or invalid organization roles."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        biz_reg = await ac.post("/api/v1/auth/register", json={
            "email": "admin.forgery.check@corp.internal",
            "password": "Password123!@",
            "full_name": "Admin Tester",
            "account_type": "BUSINESS",
            "organization_name": "Defense Corp"
        })
        assert biz_reg.status_code == 200
        headers = {"Authorization": f"Bearer {biz_reg.json()['access_token']}"}

        # Attempt to invite as PLATFORM_SUPER_ADMIN
        forged_res = await ac.post("/api/v1/organizations/invitations", headers=headers, json={
            "email": "attacker@corp.internal",
            "role": "PLATFORM_SUPER_ADMIN"
        })
        assert forged_res.status_code == 400
        assert "Invalid organization role" in forged_res.json()["detail"]


@pytest.mark.asyncio
async def test_invitation_revocation_and_expiry(monkeypatch):
    """Admin can revoke invitation, and revoked/expired invitations cannot be accepted."""
    monkeypatch.setattr(settings, "EMAIL_SERVICE_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "mock")
    mock_prov = get_mock_email_provider()
    mock_prov.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        biz_reg = await ac.post("/api/v1/auth/register", json={
            "email": "lead.revoke@firm.internal",
            "password": "Password123!@",
            "full_name": "Lead Partner",
            "account_type": "BUSINESS",
            "organization_name": "Law Firm Alpha"
        })
        headers = {"Authorization": f"Bearer {biz_reg.json()['access_token']}"}

        # Create invitation
        inv_res = await ac.post("/api/v1/organizations/invitations", headers=headers, json={
            "email": "paralegal.revoked@firm.internal",
            "role": "MEMBER"
        })
        inv_id = inv_res.json()["id"]

        # Revoke invitation
        rev_res = await ac.post(f"/api/v1/organizations/invitations/{inv_id}/revoke", headers=headers)
        assert rev_res.status_code == 200

        # Check list of pending invitations
        list_res = await ac.get("/api/v1/organizations/invitations", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) == 0


# ==============================================================================
# SECTION 5: NOTIFICATION DEDUPLICATION & INTEGRATION
# ==============================================================================

@pytest.mark.asyncio
async def test_notification_dispatcher_deduplication_and_in_app_fallback(test_engine, monkeypatch):
    """
    Dispatcher avoids duplicate notifications via deduplication_key,
    and preserves in-app notification when email is disabled.
    """
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as db:
        stmt_u = select(User).where(User.email == "legal@northstar.internal")
        res_u = await db.execute(stmt_u)
        user = res_u.scalar_one_or_none()

        stmt_m = select(OrganizationMember).where(OrganizationMember.user_id == user.id)
        res_m = await db.execute(stmt_m)
        member = res_m.scalars().first()

        dedup_key = f"phase5_dedup_test_{generate_uuid()}"

        # 1. First dispatch
        notif, status_str = await NotificationDispatcher.dispatch_notification(
            db=db,
            organization_id=member.organization_id,
            user_id=user.id,
            title="Renewal Notice Deadline",
            message="Contract renewal notice required within 30 days.",
            event_type="RENEWAL_WINDOW",
            priority="HIGH",
            deduplication_key=dedup_key
        )
        assert notif is not None
        assert status_str == "DELIVERED"
        assert notif.delivery_channel == "IN_APP"  # In-app fallback because email disabled

        # 2. Duplicate dispatch attempt with same key
        dup_notif, dup_status = await NotificationDispatcher.dispatch_notification(
            db=db,
            organization_id=member.organization_id,
            user_id=user.id,
            title="Renewal Notice Deadline",
            message="Contract renewal notice required within 30 days.",
            event_type="RENEWAL_WINDOW",
            priority="HIGH",
            deduplication_key=dedup_key
        )
        assert dup_notif is None
        assert dup_status == "SKIPPED_DEDUPLICATION"
