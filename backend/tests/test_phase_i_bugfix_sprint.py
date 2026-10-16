import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract
from app.models.obligation import Obligation
from app.services.calendar.calendar_service import CalendarService
from app.config import settings

async def setup_test_tenant(test_engine, name_prefix="SprintFix"):
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"{name_prefix} Org {suffix}", slug=f"{name_prefix.lower()}-org-{suffix}")
        session.add(org)
        await session.flush()

        user = User(
            email=f"{name_prefix.lower()}_{suffix}@example.com",
            password_hash=get_password_hash("Password123!"),
            full_name=f"{name_prefix} User {suffix}"
        )
        session.add(user)
        await session.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="OWNER"
        )
        session.add(member)
        await session.commit()

        token = create_access_token(subject=user.id, org_id=org.id, role="OWNER")
        return {
            "org_id": org.id,
            "user_id": user.id,
            "user_email": user.email,
            "token": token
        }

@pytest.mark.anyio
async def test_calendar_contract_end_date_milestone_priority(test_engine):
    """
    Regression Test for Issue 1:
    - Contract end date (2027-10-31) must produce a verified CONTRACT_EXPIRY calendar event.
    - Title must be 'Contract End Date: <title>'.
    - Event must be sorted with high priority before obligations on the same day.
    """
    tenant = await setup_test_tenant(test_engine, "EndDate")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=tenant["org_id"],
            contract_id="CTR-TEST-2027",
            contract_type="SaaS Agreement",
            counterparty="Global Cloud Corp",
            title="SaaS Master Agreement 2027",
            status="ACTIVE",
            start_date="2026-11-01",
            expiry_date="2027-10-31",
            renewal_date="2027-10-31",
            renewal_notice_days=30,
            auto_renew=True
        )
        session.add(contract)
        await session.flush()

        # Add 5 obligations on the same date (2027-10-31)
        for i in range(5):
            ob = Obligation(
                contract_id=contract.id,
                obligor_party="Vendor",
                obligee_party="Customer",
                title=f"Compliance Deliverable #{i+1}",
                description="Annual SOC2 submission",
                due_date="2027-10-31",
                status="UPCOMING"
            )
            session.add(ob)
        await session.commit()

        # Generate and retrieve events via CalendarService
        events = await CalendarService.get_organization_events(session, tenant["org_id"])
        assert len(events) >= 2

        # Verify Expiry / End Date event
        expiry_events = [e for e in events if e.event_type == "CONTRACT_EXPIRY"]
        assert len(expiry_events) == 1
        end_event = expiry_events[0]
        assert end_event.event_date == "2027-10-31"
        assert end_event.title == "Contract End Date: SaaS Master Agreement 2027"
        assert end_event.is_verified is True

    # Test via API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/calendar/events",
            headers={"Authorization": f"Bearer {tenant['token']}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 6

        # Check date 2027-10-31 events
        oct31_events = [e for e in data if e["event_date"].startswith("2027-10-31")]
        assert len(oct31_events) >= 6
        # First event on that date must be Contract End Date or Renewal milestone
        assert oct31_events[0]["event_type"] in ("CONTRACT_EXPIRY", "CONTRACT_RENEWAL")

@pytest.mark.anyio
async def test_notification_preferences_empty_string_email_validation(test_engine):
    """
    Regression Test for Issue 3:
    - Sending empty string or whitespace in preferred_notification_email must not raise 422 Unprocessable Entity.
    - Preferences must persist cleanly and reload correctly.
    - Response must include email_service_enabled and email_provider_status.
    """
    tenant = await setup_test_tenant(test_engine, "PrefsFix")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch initial preferences
        get_res = await client.get(
            "/api/v1/notifications/preferences",
            headers={"Authorization": f"Bearer {tenant['token']}"}
        )
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert "email_service_enabled" in get_data
        assert "email_provider_status" in get_data

        # 2. Update with empty string email (should sanitize to None, not 422)
        update_res = await client.put(
            "/api/v1/notifications/preferences",
            json={
                "email_notifications_enabled": True,
                "preferred_notification_email": "",
                "daily_notification_limit": 25,
                "quiet_hours_enabled": True,
                "quiet_hours_start": "23:00",
                "quiet_hours_end": "07:00"
            },
            headers={"Authorization": f"Bearer {tenant['token']}"}
        )
        assert update_res.status_code == 200, f"Expected 200 but got {update_res.status_code}: {update_res.text}"
        updated_data = update_res.json()
        assert updated_data["email_notifications_enabled"] is True
        assert updated_data["daily_notification_limit"] == 25
        assert updated_data["quiet_hours_enabled"] is True

        # 3. Reload preferences and verify persistence
        reload_res = await client.get(
            "/api/v1/notifications/preferences",
            headers={"Authorization": f"Bearer {tenant['token']}"}
        )
        assert reload_res.status_code == 200
        reloaded = reload_res.json()
        assert reloaded["email_notifications_enabled"] is True
        assert reloaded["daily_notification_limit"] == 25
        assert reloaded["quiet_hours_start"] == "23:00"

@pytest.mark.anyio
async def test_truthful_email_transport_status_reporting(test_engine):
    """
    Regression Test for Issue 4:
    - Test email endpoint must report truthful failure when EMAIL_ENABLED=False.
    - Must not fabricate delivery or return fake success.
    """
    tenant = await setup_test_tenant(test_engine, "TruthEmail")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/notifications/test-email",
            json={"recipient_email": tenant["user_email"]},
            headers={"Authorization": f"Bearer {tenant['token']}"}
        )
        assert res.status_code == 200
        data = res.json()
        # With default settings (EMAIL_ENABLED=False), must report success=False truthfully
        if not settings.EMAIL_ENABLED:
            assert data["success"] is False
            assert "disabled" in data["message"].lower()

@pytest.mark.anyio
async def test_ask_contractly_error_handling_when_unconfigured(test_engine):
    """
    Regression Test for Issue 5:
    - POST /api/v1/ai/chat must return a clean, actionable 503 error when Gemini API key is placeholder/missing.
    - Must not crash with 500 or expose internal stack traces.
    """
    tenant = await setup_test_tenant(test_engine, "AskAI")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/ai/chat",
            json={"message": "What is an auto-renewal clause?"},
            headers={"Authorization": f"Bearer {tenant['token']}"}
        )
        # In test environment without a real live Gemini key:
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("YOUR_"):
            assert res.status_code == 503
            data = res.json()
            assert "AI service is not configured" in data["detail"]
            assert "GEMINI_API_KEY" in data["detail"]

@pytest.mark.anyio
async def test_tenant_isolation_on_preferences(test_engine):
    """
    Verify Tenant A's preferences are completely isolated from Tenant B.
    """
    tenant_a = await setup_test_tenant(test_engine, "TenantA")
    tenant_b = await setup_test_tenant(test_engine, "TenantB")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenant A sets daily limit to 42
        await client.put(
            "/api/v1/notifications/preferences",
            json={"daily_notification_limit": 42},
            headers={"Authorization": f"Bearer {tenant_a['token']}"}
        )

        # Tenant B gets preferences, must see default 10, not 42
        b_res = await client.get(
            "/api/v1/notifications/preferences",
            headers={"Authorization": f"Bearer {tenant_b['token']}"}
        )
        assert b_res.status_code == 200
        assert b_res.json()["daily_notification_limit"] == 10
