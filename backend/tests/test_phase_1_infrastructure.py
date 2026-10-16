import os
import io
import uuid
import pytest
import sqlite3
import zipfile
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.config import settings
from app.core.database import engine, get_db
from app.core.rate_limiter import auth_rate_limiter
from app.core.upload_validator import (
    read_and_validate_upload,
    validate_file_signature,
    sanitize_filename,
    CONTRACT_ALLOWED_EXTENSIONS,
    EVIDENCE_ALLOWED_EXTENSIONS
)
from fastapi import UploadFile, HTTPException


# ============================================================================
# 1. SECURE DOCUMENT UPLOADS TESTS
# ============================================================================

def test_sanitize_filename():
    assert sanitize_filename("contract 2026.pdf") == "contract_2026.pdf"
    assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("..\\..\\windows\\system32.docx") == "system32.docx"
    assert sanitize_filename(None, default_name="fallback.pdf") == "fallback.pdf"


def test_file_signature_validation():
    # Valid PDF
    validate_file_signature(b"%PDF-1.4 test content", ".pdf")

    # Invalid PDF (missing %PDF)
    with pytest.raises(HTTPException) as exc:
        validate_file_signature(b"NOT_A_PDF content", ".pdf")
    assert exc.value.status_code == 415

    # Executable masquerading as PDF
    with pytest.raises(HTTPException) as exc:
        validate_file_signature(b"MZ\x90\x00executable content", ".pdf")
    assert exc.value.status_code == 415

    # Valid DOCX (ZIP containing word/document.xml)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<xml></xml>")
        zf.writestr("word/document.xml", "<xml>doc</xml>")
    valid_docx_bytes = buf.getvalue()
    validate_file_signature(valid_docx_bytes, ".docx")

    # Invalid DOCX (random bytes)
    with pytest.raises(HTTPException) as exc:
        validate_file_signature(b"PK\x03\x04corrupted zip", ".docx")
    assert exc.value.status_code == 415

    # Valid TXT
    validate_file_signature(b"This is a valid contract agreement text.", ".txt")

    # Text containing null bytes
    with pytest.raises(HTTPException) as exc:
        validate_file_signature(b"Binary\x00data\x00here", ".txt")
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_chunked_oversize_rejection():
    # Test bounded chunk reading rejecting files larger than max_bytes
    dummy_file = io.BytesIO(b"%PDF-1.4" + b"A" * 1024)
    upload = UploadFile(filename="oversized.pdf", file=dummy_file)

    # Set artificial max limit of 500 bytes
    with pytest.raises(HTTPException) as exc:
        await read_and_validate_upload(upload, max_bytes=500)
    assert exc.value.status_code == 413
    assert "exceeds maximum permitted size" in exc.value.detail


@pytest.mark.asyncio
async def test_upload_unsupported_extension_rejection():
    dummy_file = io.BytesIO(b"echo 'malicious script'")
    upload = UploadFile(filename="script.sh", file=dummy_file)

    with pytest.raises(HTTPException) as exc:
        await read_and_validate_upload(upload, allowed_extensions=CONTRACT_ALLOWED_EXTENSIONS)
    assert exc.value.status_code == 415
    assert "Unsupported file type" in exc.value.detail


@pytest.mark.asyncio
async def test_upload_empty_file_rejection():
    dummy_file = io.BytesIO(b"")
    upload = UploadFile(filename="empty.pdf", file=dummy_file)

    with pytest.raises(HTTPException) as exc:
        await read_and_validate_upload(upload)
    assert exc.value.status_code == 400
    assert "Uploaded file is empty" in exc.value.detail


# ============================================================================
# 2. AUTHENTICATION ENDPOINT ABUSE PROTECTION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_auth_rate_limiter_repeated_failed_logins():
    await auth_rate_limiter.reset()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        test_email = f"bruteforce_{uuid.uuid4().hex[:6]}@example.com"

        # Attempt multiple logins with invalid credentials
        for i in range(5):
            resp = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": "WrongPassword123!"
            })
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Invalid email or password."

        # The 6th attempt should be blocked with HTTP 429
        blocked_resp = await ac.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "WrongPassword123!"
        })
        assert blocked_resp.status_code == 429
        assert "Too many failed login attempts" in blocked_resp.json()["detail"]
        assert "retry-after" in blocked_resp.headers

    await auth_rate_limiter.reset()


@pytest.mark.asyncio
async def test_auth_login_success_clears_failures():
    await auth_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register user
        unique = uuid.uuid4().hex[:6]
        user_email = f"success_{unique}@corp.internal"
        pwd = "SafePassword123!"
        reg = await ac.post("/api/v1/auth/register", json={
            "email": user_email,
            "password": pwd,
            "full_name": "Success User",
            "organization_name": f"Success Org {unique}",
            "role": "LEGAL_MANAGER",
            "account_type": "BUSINESS"
        })
        assert reg.status_code == 200

        # 2 failed attempts
        for _ in range(2):
            await ac.post("/api/v1/auth/login", json={"email": user_email, "password": "BadPassword"})

        # Successful attempt
        good_login = await ac.post("/api/v1/auth/login", json={"email": user_email, "password": pwd})
        assert good_login.status_code == 200

        # Verify failed attempts counter was reset for this email
        failed_count = await auth_rate_limiter.backend.get_count(
            f"auth:failed:email:{user_email.lower().strip()}",
            settings.AUTH_LOGIN_WINDOW_SECONDS
        )
        assert failed_count == 0

    await auth_rate_limiter.reset()


# ============================================================================
# 3. HEALTH CHECK TESTS (HEALTHY & DEGRADED / UNAVAILABLE)
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_healthy():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "dependencies" in data
        assert data["dependencies"]["database"]["status"] == "healthy"
        assert data["dependencies"]["storage"]["status"] == "healthy"
        # Confirm no sensitive database connection details or paths are exposed
        body_text = resp.text.lower()
        assert "password" not in body_text
        assert "secret" not in body_text
        assert ".db" not in body_text
        assert "sqlite" not in body_text


@pytest.mark.asyncio
async def test_health_check_database_unavailable():
    # Mock failing database dependency
    async def failing_get_db():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Simulated DB connection failure")
        yield mock_session

    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = failing_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/health")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["dependencies"]["database"]["status"] == "unhealthy"
            # Sensitive internal tracebacks must not be leaked
            assert "Simulated DB connection failure" not in resp.text
    finally:
        if prev_override is not None:
            app.dependency_overrides[get_db] = prev_override
        else:
            app.dependency_overrides.pop(get_db, None)


# ============================================================================
# 4. POSTGRESQL CONFIGURATION READINESS TESTS
# ============================================================================

def test_postgresql_connection_pool_configuration():
    from app.config import Settings
    # Verify default pool settings
    test_settings = Settings()
    assert test_settings.DB_POOL_SIZE == 10
    assert test_settings.DB_MAX_OVERFLOW == 20
    assert test_settings.DB_POOL_TIMEOUT_SECONDS == 30.0
    assert test_settings.DB_POOL_RECYCLE_SECONDS == 1800
    assert test_settings.DB_POOL_PRE_PING is True


# ============================================================================
# 5. ALEMBIC MIGRATION ON DISPOSABLE DATABASE (SAFE & NON-DESTRUCTIVE)
# ============================================================================

def test_alembic_migration_on_disposable_database():
    import subprocess
    import sys

    # Define a disposable SQLite file separate from contractly.db
    disposable_db = os.path.abspath("test_disposable_migration.db")
    if os.path.exists(disposable_db):
        os.remove(disposable_db)

    # Use ALEMBIC_DATABASE_URL to target the disposable database
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = f"sqlite+aiosqlite:///{disposable_db.replace('\\', '/')}"

    backend_dir = os.path.abspath("backend")
    alembic_ini = os.path.join(backend_dir, "alembic.ini")

    # 1. Run alembic upgrade head
    cmd_upgrade = [sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head"]
    proc = subprocess.run(cmd_upgrade, cwd=backend_dir, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"Alembic upgrade failed: {proc.stderr} {proc.stdout}"

    # 2. Verify all 20 tables exist in disposable database
    conn = sqlite3.connect(disposable_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic_%' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()

    expected_tables = {
        'audit_logs', 'calendar_events', 'contract_approval_steps', 'contract_clauses',
        'contract_notes', 'contract_redlines', 'contract_risks', 'contract_versions',
        'contracts', 'departments', 'notifications', 'obligation_evidence',
        'obligations', 'organization_members', 'organizations', 'playbook_rules',
        'refresh_tokens', 'user_notification_preferences', 'users', 'vendors'
    }
    assert expected_tables.issubset(set(tables)), f"Missing tables: {expected_tables - set(tables)}"

    # 3. Run alembic downgrade base
    cmd_downgrade = [sys.executable, "-m", "alembic", "-c", alembic_ini, "downgrade", "base"]
    proc_down = subprocess.run(cmd_downgrade, cwd=backend_dir, env=env, capture_output=True, text=True)
    assert proc_down.returncode == 0, f"Alembic downgrade failed: {proc_down.stderr} {proc_down.stdout}"

    # 4. Clean up disposable database
    if os.path.exists(disposable_db):
        os.remove(disposable_db)

    # 5. Verify contractly.db was not modified or removed
    assert os.path.exists("contractly.db"), "Canonical contractly.db must remain intact"
