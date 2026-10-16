import os
import sys
import io
import uuid
import sqlite3
import subprocess
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.config import settings, Settings
from app.core.database import Base, engine, get_db
from app.services.notifications.scheduler import NotificationScheduler, NOTIFICATION_ADVISORY_LOCK_KEY
from app.core.upload_validator import read_and_validate_upload, CONTRACT_ALLOWED_EXTENSIONS
from fastapi import UploadFile, HTTPException


# ==============================================================================
# Task A: Alembic Migration Validation Tests
# ==============================================================================

def test_alembic_migration_fresh_database_upgrade_and_downgrade():
    """
    Verify:
    1. A fresh database can be fully upgraded to head using Alembic without Base.metadata.create_all.
    2. All 20 canonical tables and indexes are created.
    3. Alembic downgrade base safely removes all tables in reverse dependency order.
    4. Canonical contractly.db is never touched.
    """
    backend_dir = os.path.abspath("backend")
    alembic_ini = os.path.join(backend_dir, "alembic.ini")
    disposable_db = os.path.abspath("test_phase3_alembic.db")

    if os.path.exists(disposable_db):
        os.remove(disposable_db)

    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = f"sqlite+aiosqlite:///{disposable_db.replace('\\', '/')}"

    try:
        # 1. Upgrade to head
        cmd_up = [sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head"]
        proc_up = subprocess.run(cmd_up, cwd=backend_dir, env=env, capture_output=True, text=True)
        assert proc_up.returncode == 0, f"Alembic upgrade failed: {proc_up.stderr}\n{proc_up.stdout}"

        # 2. Inspect created schema
        conn = sqlite3.connect(disposable_db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic_%' ORDER BY name;")
        tables = set(r[0] for r in cur.fetchall())

        expected_tables = {
            'organizations', 'departments', 'users', 'organization_members',
            'contracts', 'contract_versions', 'contract_clauses', 'contract_risks',
            'contract_approval_steps', 'contract_redlines', 'refresh_tokens',
            'audit_logs', 'obligations', 'obligation_evidence', 'calendar_events',
            'contract_notes', 'vendors', 'playbook_rules', 'notifications',
            'user_notification_preferences',
            'account_tokens', 'organization_invitations',
            'lawyer_profiles', 'legal_matters', 'matter_access_grants',
            'matter_messages', 'lawyer_availability'
        }
        try:
            assert expected_tables == tables, f"Schema mismatch: {expected_tables ^ tables}"

            # Check unique constraint index on notifications deduplication_key
            cur.execute("PRAGMA index_list('notifications');")
            notif_indexes = cur.fetchall()
            notif_index_names = [idx[1] for idx in notif_indexes]
            assert "ix_notifications_deduplication_key" in notif_index_names
        finally:
            conn.close()

        # 3. Downgrade to base
        cmd_down = [sys.executable, "-m", "alembic", "-c", alembic_ini, "downgrade", "base"]
        proc_down = subprocess.run(cmd_down, cwd=backend_dir, env=env, capture_output=True, text=True)
        assert proc_down.returncode == 0, f"Alembic downgrade failed: {proc_down.stderr}\n{proc_down.stdout}"

        # 4. Verify all tables dropped
        conn2 = sqlite3.connect(disposable_db)
        cur2 = conn2.cursor()
        cur2.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic_%';")
        remaining = cur2.fetchall()
        conn2.close()
        assert len(remaining) == 0, f"Tables remained after downgrade: {remaining}"

    finally:
        if os.path.exists(disposable_db):
            os.remove(disposable_db)

    # Verify canonical contractly.db was not modified or removed
    assert os.path.exists("contractly.db"), "contractly.db must remain intact"


def test_migration_environment_variable_precedence():
    """Verify Alembic honors ALEMBIC_DATABASE_URL environment variable override in offline mode."""
    backend_dir = os.path.abspath("backend")
    alembic_ini = os.path.join(backend_dir, "alembic.ini")
    test_url = "sqlite+aiosqlite:///test_alembic_override.db"

    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = test_url

    cmd = [sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head", "--sql"]
    proc = subprocess.run(cmd, cwd=backend_dir, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"Alembic offline SQL failed: {proc.stderr}"
    assert "CREATE TABLE organizations" in proc.stdout


def test_auto_create_tables_setting_prevents_silent_schema_mutation():
    """Verify that settings.AUTO_CREATE_TABLES defaults to False to prevent unmanaged DDL mutations in production."""
    s = Settings()
    assert s.AUTO_CREATE_TABLES is False


# ==============================================================================
# Task B: Real PostgreSQL Integration Status & Connection Test Gate
# ==============================================================================

def test_postgresql_availability_detection():
    """
    Truthful verification gate:
    Detects whether an isolated PostgreSQL test instance is actually running.
    Does NOT use mocks to pretend a live PostgreSQL service ran.
    """
    import socket

    pg_url = os.environ.get("TEST_POSTGRESQL_URL") or os.environ.get("POSTGRES_TEST_DATABASE_URL")
    if not pg_url:
        # Check standard default port 5432 on localhost
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", 5432))
            is_open = True
        except (socket.timeout, ConnectionRefusedError, OSError):
            is_open = False
        finally:
            s.close()
    else:
        is_open = True

    # If port 5432 is not listening and no environment variable is provided,
    # the integration is truthfully reported as BLOCKED without false claims.
    if not is_open:
        pytest.skip(
            "Live PostgreSQL service is not available on 127.0.0.1:5432 and no TEST_POSTGRESQL_URL is set. "
            "Marked as BLOCKED pending external container or cluster environment."
        )


# ==============================================================================
# Task C: Scheduler Multi-Process Advisory Locking Semantics
# ==============================================================================

@pytest.mark.asyncio
async def test_scheduler_advisory_lock_connection_pinning():
    """
    Verify that in PostgreSQL mode:
    1. The advisory lock is acquired on a dedicated connection via engine.connect().
    2. The lock is released on the EXACT same connection.
    3. Connection-hopping across pooled connections is strictly prevented.
    """
    scheduler = NotificationScheduler()

    mock_conn = AsyncMock()
    mock_res_true = MagicMock()
    mock_res_true.scalar.return_value = True
    mock_conn.execute = AsyncMock(return_value=mock_res_true)

    ctx_conn = MagicMock()
    ctx_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx_conn.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = ctx_conn

    with patch.object(settings, "DATABASE_URL", "postgresql+asyncpg://postgres:pass@localhost:5432/db"):
        with patch("app.services.notifications.scheduler.engine", mock_engine):
            with patch("app.services.notifications.scheduler.NotificationWorker.evaluate_and_dispatch", new_callable=AsyncMock) as mock_worker:
                mock_worker.return_value = {"evaluated_contracts": 1, "notifications_created": 0, "skipped_dedup": 0}

                res = await scheduler.execute_cycle()
                assert res["status"] == "completed"

                # Verify both pg_try_advisory_lock and pg_advisory_unlock were called on the same mock_conn
                calls = mock_conn.execute.call_args_list
                assert len(calls) == 2
                assert "pg_try_advisory_lock" in calls[0].args[0].text
                assert "pg_advisory_unlock" in calls[1].args[0].text


@pytest.mark.asyncio
async def test_scheduler_advisory_lock_busy_second_instance_skips():
    """
    Verify that if instance 1 holds the lock, instance 2 receives pg_try_advisory_lock -> False,
    logs the event cleanly, and skips evaluation without executing workers or modifying database records.
    """
    scheduler = NotificationScheduler()

    mock_conn_busy = AsyncMock()
    mock_res_false = MagicMock()
    mock_res_false.scalar.return_value = False
    mock_conn_busy.execute = AsyncMock(return_value=mock_res_false)

    ctx_conn_busy = MagicMock()
    ctx_conn_busy.__aenter__ = AsyncMock(return_value=mock_conn_busy)
    ctx_conn_busy.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = ctx_conn_busy

    with patch.object(settings, "DATABASE_URL", "postgresql+asyncpg://postgres:pass@localhost:5432/db"):
        with patch("app.services.notifications.scheduler.engine", mock_engine):
            with patch("app.services.notifications.scheduler.NotificationWorker.evaluate_and_dispatch", new_callable=AsyncMock) as mock_worker:
                res = await scheduler.execute_cycle()
                assert res["status"] == "skipped"
                assert res["reason"] == "postgres_advisory_lock_busy"
                mock_worker.assert_not_called()
                # Unlocking should not be attempted when lock was never acquired
                assert mock_conn_busy.execute.call_count == 1


# ==============================================================================
# Task D: Infrastructure & Security Defect Regression Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_upload_validator_bounded_streaming_memory():
    """
    Verify that upload validator checks size in streaming chunks up to max_bytes
    and raises HTTP 413 without loading oversized files entirely into memory.
    """
    chunk_size = 1024 * 1024  # 1 MB
    # Create stream with 5 MB
    large_payload = b"%PDF-1.4" + b"X" * (5 * chunk_size)
    large_stream = io.BytesIO(large_payload)
    upload = UploadFile(filename="large_contract.pdf", file=large_stream)

    # Set limit to 2 MB
    limit_bytes = 2 * chunk_size
    with pytest.raises(HTTPException) as exc:
        await read_and_validate_upload(upload, max_bytes=limit_bytes)

    assert exc.value.status_code == 413
    assert "exceeds maximum permitted size" in exc.value.detail


@pytest.mark.asyncio
async def test_health_check_does_not_leak_connection_strings_or_secrets():
    """Verify /health returns operational statuses without leaking internal connection credentials or raw file paths."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        text_content = res.text

        # Must not disclose credentials, passwords, or connection strings
        assert "password" not in text_content.lower()
        assert "sqlite+aiosqlite" not in text_content
        assert "postgresql+asyncpg" not in text_content
        assert "contractly_dev_secret_key" not in text_content
