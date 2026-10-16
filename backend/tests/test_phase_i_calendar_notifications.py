import pytest
import uuid
from datetime import datetime, date, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractApprovalStep
from app.models.obligation import Obligation
from app.models.calendar import CalendarEvent
from app.models.note import ContractNote
from app.models.notification import Notification, UserNotificationPreference
from app.services.notifications.policy import NotificationPriority, generate_deduplication_key, is_notification_eligible
from app.services.notifications.worker import NotificationWorker
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.email.provider import MockEmailProvider, DisabledEmailProvider, EmailDeliveryResult
from app.services.email.templates import (
    render_renewal_notice_email,
    render_overdue_obligation_email,
    render_critical_deadline_email
)

async def setup_test_tenant(test_engine, name_prefix="PhaseI"):
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
            "email": user.email,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
            "suffix": suffix
        }


@pytest.mark.asyncio
async def test_calendar_event_generation_and_notice_calculation(test_engine):
    """
    Verifies that calendar events are dynamically generated from contract lifecycle dates,
    correctly computing notice deadlines (renewal_date - renewal_notice_days).
    """
    ctx = await setup_test_tenant(test_engine, "CalGen")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    today = date.today()
    renewal = today + timedelta(days=60)
    
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=ctx["org_id"],
            contract_id=f"CTR-{ctx['suffix']}",
            title="SaaS Subscription Agreement",
            contract_type="SaaS",
            counterparty="Vendor Tech Inc",
            status="ACTIVE",
            start_date=(today - timedelta(days=300)).isoformat(),
            expiry_date=(today + timedelta(days=65)).isoformat(),
            renewal_date=renewal.isoformat(),
            renewal_notice_days=30,
            termination_notice_days=15
        )
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/calendar/events", headers=ctx["headers"])
        assert res.status_code == 200
        events = res.json()
        assert len(events) >= 3
        
        # Verify renewal notice deadline calculation
        notice_events = [e for e in events if e["event_type"] == "RENEWAL_NOTICE"]
        assert len(notice_events) == 1
        expected_notice_date = (renewal - timedelta(days=30)).isoformat()
        assert notice_events[0]["event_date"] == expected_notice_date
        assert notice_events[0]["contract_id"] == contract_id
        assert notice_events[0]["source_type"] == "CALCULATED_REMINDER"


@pytest.mark.asyncio
async def test_custom_calendar_event_crud_and_tenant_isolation(test_engine):
    """
    Tests creating, updating, completing custom calendar events and verifies tenant isolation.
    """
    tenant_a = await setup_test_tenant(test_engine, "TenA")
    tenant_b = await setup_test_tenant(test_engine, "TenB")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create custom event in Tenant A
        payload = {
            "title": "Quarterly Vendor Security Review",
            "event_type": "CUSTOM_DATE",
            "event_date": (date.today() + timedelta(days=14)).isoformat(),
            "priority": "HIGH",
            "description": "Annual SOC2 review meeting"
        }
        res = await client.post("/api/v1/calendar/events", headers=tenant_a["headers"], json=payload)
        assert res.status_code == 201
        event = res.json()
        event_id = event["id"]
        assert event["title"] == payload["title"]
        assert event["priority"] == "HIGH"
        assert event["status"] == "UPCOMING"
        assert event["is_custom"] is True

        # Tenant B cannot view or modify Tenant A's event
        res_b = await client.get(f"/api/v1/calendar/events/{event_id}", headers=tenant_b["headers"])
        assert res_b.status_code == 404

        res_b_update = await client.patch(
            f"/api/v1/calendar/events/{event_id}",
            headers=tenant_b["headers"],
            json={"status": "COMPLETED"}
        )
        assert res_b_update.status_code == 404

        # Tenant A completes the event
        res_a_update = await client.patch(
            f"/api/v1/calendar/events/{event_id}",
            headers=tenant_a["headers"],
            json={"status": "COMPLETED"}
        )
        assert res_a_update.status_code == 200
        assert res_a_update.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_contract_notes_crud_and_isolation(test_engine):
    """
    Tests creating, viewing, updating notes on contracts with tenant isolation.
    """
    ctx_a = await setup_test_tenant(test_engine, "NotesA")
    ctx_b = await setup_test_tenant(test_engine, "NotesB")
    
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        c_a = Contract(
            organization_id=ctx_a["org_id"],
            contract_id=f"CTR-{ctx_a['suffix']}",
            title="Confidential Licensing Agreement",
            contract_type="Licensing",
            counterparty="Licensee Corp",
            status="ACTIVE"
        )
        session.add(c_a)
        await session.commit()
        contract_a_id = c_a.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create note on Contract A
        note_payload = {
            "title": "Renegotiation Notice",
            "content": "Finance requested renegotiation of seat pricing before Q3.",
            "is_important": True,
            "reminder_date": (date.today() + timedelta(days=20)).isoformat()
        }
        res = await client.post(
            f"/api/v1/contracts/{contract_a_id}/notes",
            headers=ctx_a["headers"],
            json=note_payload
        )
        assert res.status_code == 201
        note = res.json()
        note_id = note["id"]
        assert note["title"] == note_payload["title"]
        assert note["is_important"] is True

        # Tenant B attempting to access Contract A's notes is rejected (404)
        res_b = await client.get(
            f"/api/v1/contracts/{contract_a_id}/notes",
            headers=ctx_b["headers"]
        )
        assert res_b.status_code == 404

        # Update note by author
        res_update = await client.patch(
            f"/api/v1/contracts/{contract_a_id}/notes/{note_id}",
            headers=ctx_a["headers"],
            json={"title": "Updated Renegotiation Notice"}
        )
        assert res_update.status_code == 200
        assert res_update.json()["title"] == "Updated Renegotiation Notice"


@pytest.mark.asyncio
async def test_things_you_need_to_do_derived_responsibilities(test_engine):
    """
    Verifies that the Things You Need to Do endpoint derives actionable tasks
    from real database records (pending approvals, overdue obligations).
    """
    ctx = await setup_test_tenant(test_engine, "Tasks")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    today = date.today()
    async with TestSessionLocal() as session:
        # 1. Contract pending approval
        c1 = Contract(
            organization_id=ctx["org_id"],
            contract_id=f"CTR-TASK1-{ctx['suffix']}",
            title="Vendor Master Services Agreement",
            contract_type="MSA",
            counterparty="Vendor Co",
            status="PENDING_APPROVAL"
        )
        session.add(c1)
        await session.flush()
        
        step = ContractApprovalStep(
            contract_id=c1.id,
            step_order=1,
            role="LEGAL_COUNSEL",
            assigned_user="legal@northstar.internal",
            decision="PENDING"
        )
        session.add(step)
        
        # 2. Overdue obligation
        c2 = Contract(
            organization_id=ctx["org_id"],
            contract_id=f"CTR-TASK2-{ctx['suffix']}",
            title="Data Protection Agreement",
            contract_type="DPA",
            counterparty="Cloud Host",
            status="ACTIVE"
        )
        session.add(c2)
        await session.flush()
        
        ob = Obligation(
            contract_id=c2.id,
            obligor_party="Vendor",
            obligee_party="Customer",
            title="Deliver Annual SOC2 Type II Report",
            description="Provide independent SOC2 audit report",
            due_date=(today - timedelta(days=5)).isoformat(),
            status="OPEN"
        )
        session.add(ob)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/tasks/things-to-do", headers=ctx["headers"])
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        tasks = data["items"]
        assert len(tasks) >= 2
        
        task_types = [t["task_type"] for t in tasks]
        assert "COMPLETE_APPROVAL" in task_types
        assert "RESOLVE_OVERDUE_OBLIGATION" in task_types
        
        overdue_task = next(t for t in tasks if t["task_type"] == "RESOLVE_OVERDUE_OBLIGATION")
        assert overdue_task["priority"] == "CRITICAL"
        assert overdue_task["contract_title"] == "Data Protection Agreement"


@pytest.mark.asyncio
async def test_notification_preferences_and_quiet_hours(test_engine):
    """
    Tests reading and updating user notification preferences, verifying
    persistence and field validation.
    """
    ctx = await setup_test_tenant(test_engine, "Pref")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default preferences: email is disabled by default for safety
        res = await client.get("/api/v1/notifications/preferences", headers=ctx["headers"])
        assert res.status_code == 200
        pref = res.json()
        assert pref["email_notifications_enabled"] is False
        assert pref["renewal_reminders"] is True

        # Update preferences
        update_data = {
            "email_notifications_enabled": True,
            "renewal_reminders": True,
            "reminder_intervals": [30, 14, 7],
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "daily_notification_limit": 5
        }
        res_update = await client.patch(
            "/api/v1/notifications/preferences",
            headers=ctx["headers"],
            json=update_data
        )
        assert res_update.status_code == 200
        updated = res_update.json()
        assert updated["email_notifications_enabled"] is True
        assert updated["reminder_intervals"] == [30, 14, 7]
        assert updated["daily_notification_limit"] == 5
        assert updated["quiet_hours_enabled"] is True


@pytest.mark.asyncio
async def test_notification_deduplication_and_worker_idempotency(test_engine):
    """
    Verifies that running the NotificationWorker multiple times
    does NOT duplicate notifications for the same underlying contractual deadline.
    """
    ctx = await setup_test_tenant(test_engine, "Dedup")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    # Contract with renewal notice due in exactly 7 days
    target_date = datetime.now(timezone.utc).date() + timedelta(days=7)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=ctx["org_id"],
            contract_id=f"CTR-DEDUP-{ctx['suffix']}",
            title="Cloud Hosting Enterprise Master Agreement",
            contract_type="Cloud",
            counterparty="Cloud Provider Inc",
            status="ACTIVE",
            renewal_date=(target_date + timedelta(days=30)).isoformat(),
            renewal_notice_days=30  # Notice deadline is exactly target_date (7 days from now)
        )
        session.add(contract)
        await session.commit()

    # First execution of worker evaluation
    async with TestSessionLocal() as session:
        stats1 = await NotificationWorker.evaluate_and_dispatch(session, organization_id=ctx["org_id"])
        assert stats1["notifications_created"] >= 1

    # Second execution: deduplication must block re-creating the notification
    async with TestSessionLocal() as session:
        stats2 = await NotificationWorker.evaluate_and_dispatch(session, organization_id=ctx["org_id"])
        assert stats2["notifications_created"] == 0
        assert stats2["skipped_dedup"] >= 1

    # Check notification in database
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/notifications", headers=ctx["headers"])
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        notifs = data["items"]
        assert len(notifs) >= 1
        
        # Test mark as read
        notif_id = notifs[0]["id"]
        res_read = await client.patch(
            f"/api/v1/notifications/{notif_id}/read",
            headers=ctx["headers"]
        )
        assert res_read.status_code == 200
        assert res_read.json()["is_read"] is True


@pytest.mark.asyncio
async def test_email_providers_and_template_rendering():
    """
    Verifies MockEmailProvider and DisabledEmailProvider abstractions,
    and checks template generation aesthetics and content.
    """
    # 1. DisabledEmailProvider should return success=False safely without errors
    disabled_provider = DisabledEmailProvider()
    res_dis = disabled_provider.send_email(
        to_email="legal@example.com",
        subject="Test Notice",
        html_body="<p>Test</p>",
        text_body="Test"
    )
    assert res_dis.success is False
    assert "disabled" in res_dis.error_message.lower()

    # 2. MockEmailProvider should record deliveries
    mock_provider = MockEmailProvider()
    res_mock = mock_provider.send_email(
        to_email="legal@example.com",
        subject="Test Notice",
        html_body="<p>Test</p>",
        text_body="Test"
    )
    assert res_mock.success is True
    assert len(mock_provider.sent_emails) == 1
    assert mock_provider.sent_emails[0]["to"] == "legal@example.com"

    # 3. Test template generation
    html, text = render_renewal_notice_email(
        contract_title="Master Services Agreement",
        days_remaining=7,
        notice_deadline="2026-11-01",
        renewal_date="2026-12-01",
        contract_id="test-ctr-123"
    )
    assert "Master Services Agreement" in html
    assert "2026-11-01" in html
    assert "CONTRACTLY" in html
    assert "2026-11-01" in text


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected():
    """
    Verifies that all new Phase I endpoints reject unauthenticated requests with 401.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Calendar events
        res = await client.get("/api/v1/calendar/events")
        assert res.status_code == 401

        # Tasks
        res = await client.get("/api/v1/tasks/things-to-do")
        assert res.status_code == 401

        # Notifications
        res = await client.get("/api/v1/notifications")
        assert res.status_code == 401

        # Preferences
        res = await client.get("/api/v1/notifications/preferences")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_association_rejection(test_engine):
    """
    Verifies that attempts to associate a calendar event or note with a contract
    belonging to another tenant are strictly rejected.
    """
    tenant_a = await setup_test_tenant(test_engine, "IsoA")
    tenant_b = await setup_test_tenant(test_engine, "IsoB")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        c_a = Contract(
            organization_id=tenant_a["org_id"],
            contract_id=f"CTR-{tenant_a['suffix']}",
            title="Tenant A Proprietary Agreement",
            contract_type="IP",
            counterparty="Third Party",
            status="ACTIVE"
        )
        session.add(c_a)
        await session.commit()
        contract_a_id = c_a.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenant B attempting to create an event referencing Tenant A's contract
        res_event = await client.post(
            "/api/v1/calendar/events",
            headers=tenant_b["headers"],
            json={
                "title": "Unauthorized Milestone",
                "contract_id": contract_a_id,
                "event_type": "CUSTOM_DATE",
                "event_date": "2026-12-31"
            }
        )
        assert res_event.status_code == 404

        # Tenant B attempting to create a note on Tenant A's contract
        res_note = await client.post(
            f"/api/v1/contracts/{contract_a_id}/notes",
            headers=tenant_b["headers"],
            json={"content": "Spying on tenant A"}
        )
        assert res_note.status_code == 404


@pytest.mark.asyncio
async def test_mark_all_read_and_evaluation_endpoint(test_engine):
    """
    Verifies marking all notifications as read and triggering the worker evaluation endpoint.
    """
    ctx = await setup_test_tenant(test_engine, "MarkAll")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSessionLocal() as session:
        n1 = Notification(
            organization_id=ctx["org_id"],
            user_id=ctx["user_id"],
            event_type="CUSTOM",
            priority="INFORMATIONAL",
            title="Notice 1",
            message="Message 1",
            delivery_channel="IN_APP",
            delivery_status="DELIVERED",
            is_read=False
        )
        n2 = Notification(
            organization_id=ctx["org_id"],
            user_id=ctx["user_id"],
            event_type="CUSTOM",
            priority="INFORMATIONAL",
            title="Notice 2",
            message="Message 2",
            delivery_channel="IN_APP",
            delivery_status="DELIVERED",
            is_read=False
        )
        session.add_all([n1, n2])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check unread count
        count_res = await client.get("/api/v1/notifications/unread-count", headers=ctx["headers"])
        assert count_res.status_code == 200
        assert count_res.json()["unread_count"] >= 2

        # Mark all read
        mark_res = await client.post("/api/v1/notifications/mark-all-read", headers=ctx["headers"])
        assert mark_res.status_code == 200

        # Unread count should now be 0
        count_res_after = await client.get("/api/v1/notifications/unread-count", headers=ctx["headers"])
        assert count_res_after.status_code == 200
        assert count_res_after.json()["unread_count"] == 0

        # Trigger worker evaluation API
        eval_res = await client.post("/api/v1/notifications/evaluate-and-dispatch", headers=ctx["headers"])
        assert eval_res.status_code == 200
        data = eval_res.json()
        assert "evaluated_contracts" in data
        assert "notifications_created" in data
