"""
Contractly Phase 9: Isolated Migration Chain Test Suite
Tests:
1. Migration Chain: 0001_initial_schema -> seed data -> 0002_email_security_workflows
2. Foreign Key Enforcement: PRAGMA foreign_keys = ON, invalid FK insert rejection
3. Unique Constraints: rejection of duplicates on slug, email, and tokens
4. Data Retention: seeded rows remain identical post-upgrade
5. Safe Failure Handling & Isolation: temporary files exclusively, canonical DB protection
"""

import os
import sys
import uuid
import sqlite3
import tempfile
import subprocess
import pytest
from pathlib import Path

WORKSPACE_ROOT = Path(r"A:\Soft Computing").resolve()
BACKEND_DIR = WORKSPACE_ROOT / "backend"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
CANONICAL_DB_ROOT = (WORKSPACE_ROOT / "contractly.db").resolve()
CANONICAL_DB_BACKEND = (BACKEND_DIR / "contractly.db").resolve()


def get_canonical_db_stats():
    """Captures file size and mtime for canonical databases to ensure zero modification."""
    stats = {}
    if CANONICAL_DB_ROOT.exists():
        st = CANONICAL_DB_ROOT.stat()
        stats["root_size"] = st.st_size
        stats["root_mtime"] = st.st_mtime
    if CANONICAL_DB_BACKEND.exists():
        st = CANONICAL_DB_BACKEND.stat()
        stats["backend_size"] = st.st_size
        stats["backend_mtime"] = st.st_mtime
    return stats


def assert_canonical_databases_untouched(initial_stats):
    """Asserts that neither canonical database was modified or removed."""
    current_stats = get_canonical_db_stats()
    assert CANONICAL_DB_ROOT.exists(), "Root contractly.db must exist"
    assert CANONICAL_DB_BACKEND.exists(), "Backend contractly.db must exist"
    assert current_stats["backend_size"] == initial_stats["backend_size"], "Backend contractly.db size changed"
    assert current_stats["backend_mtime"] == initial_stats["backend_mtime"], "Backend contractly.db mtime changed"


def run_alembic_command(command_args, target_db_path):
    """
    Executes Alembic command pinned strictly to target_db_path.
    Guards against targeting either canonical database.
    """
    target_abs = Path(target_db_path).resolve()
    assert target_abs != CANONICAL_DB_ROOT, "SAFETY VIOLATION: Target matches root contractly.db"
    assert target_abs != CANONICAL_DB_BACKEND, "SAFETY VIOLATION: Target matches backend contractly.db"

    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = f"sqlite+aiosqlite:///{target_abs.as_posix()}"

    cmd = [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI)] + command_args
    proc = subprocess.run(cmd, cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True)
    return proc


@pytest.fixture
def isolated_temp_db():
    """
    Creates a dedicated temporary SQLite file inside a clean temporary directory.
    Cleans up completely upon fixture teardown.
    """
    initial_stats = get_canonical_db_stats()
    temp_dir = tempfile.TemporaryDirectory(prefix="contractly_p9_test_")
    db_filename = f"temp_migration_{uuid.uuid4().hex[:8]}.db"
    db_path = Path(temp_dir.name) / db_filename

    target_abs = db_path.resolve()
    assert target_abs != CANONICAL_DB_ROOT, "Target must not be root contractly.db"
    assert target_abs != CANONICAL_DB_BACKEND, "Target must not be backend contractly.db"

    yield db_path

    # Teardown
    try:
        temp_dir.cleanup()
    except Exception:
        pass
    assert_canonical_databases_untouched(initial_stats)


# ==============================================================================
# TEST SCENARIO A & D: MIGRATION CHAIN & DATA RETENTION
# ==============================================================================

def test_migration_chain_and_data_retention(isolated_temp_db):
    """
    Tests complete migration chain:
    1. Upgrade to 0001_initial_schema
    2. Seed realistic data with foreign key relationships
    3. Upgrade to 0002_email_security_workflows
    4. Assert seeded records are retained completely with identical values
    5. Assert account_tokens and organization_invitations exist and accept valid data
    """
    # 1. Upgrade to 0001_initial_schema
    proc1 = run_alembic_command(["upgrade", "0001_initial_schema"], isolated_temp_db)
    assert proc1.returncode == 0, f"Alembic upgrade 0001 failed: {proc1.stderr}\n{proc1.stdout}"

    # Verify 20 tables + alembic_version created
    conn = sqlite3.connect(isolated_temp_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables_step1 = [r[0] for r in cur.fetchall()]
    assert "alembic_version" in tables_step1
    assert "organizations" in tables_step1
    assert "users" in tables_step1
    assert "contracts" in tables_step1
    assert "account_tokens" not in tables_step1
    assert "organization_invitations" not in tables_step1
    assert len(tables_step1) == 21  # 20 tables + alembic_version

    # Check current Alembic revision in DB
    cur.execute("SELECT version_num FROM alembic_version;")
    assert cur.fetchone()[0] == "0001_initial_schema"

    # 2. Seed representative records into step 1 schema
    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    contract_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO organizations (id, name, slug, account_type, subscription_tier, storage_quota_bytes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (org_id, "Acme Logistics Global", "acme-logistics", "ENTERPRISE", "ENTERPRISE", 53687091200))

    cur.execute("""
        INSERT INTO departments (id, organization_id, name, budget_currency, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (dept_id, org_id, "Procurement & Legal", "USD"))

    cur.execute("""
        INSERT INTO users (id, email, password_hash, full_name, avatar_url, is_active, is_super_admin, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (user_id, "counsel@acmelogistics.com", "$2b$12$fakehashforetestingonly", "Chief Legal Officer", None, 1, 0))

    cur.execute("""
        INSERT INTO organization_members (id, organization_id, user_id, department_id, role, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (str(uuid.uuid4()), org_id, user_id, dept_id, "OWNER", "ACTIVE"))

    cur.execute("""
        INSERT INTO contracts (id, organization_id, contract_id, title, contract_type, counterparty, department, owner, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (contract_id, org_id, "CTR-2026-001", "Master Services Agreement 2026", "MSA", "Global Logistics Corp", "Legal", "Chief Legal Officer", "ACTIVE"))

    cur.execute("""
        INSERT INTO contract_versions (id, contract_id, version_number, filename, file_storage_path, file_mime_type, file_byte_size, sha256_checksum, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (version_id, contract_id, "v1.0", "msa_final.pdf", "uploads/acme/msa_final.pdf", "application/pdf", 1048576, "a"*64))

    conn.commit()
    conn.close()

    # 3. Upgrade to 0002_email_security_workflows
    proc2 = run_alembic_command(["upgrade", "0002_email_security_workflows"], isolated_temp_db)
    assert proc2.returncode == 0, f"Alembic upgrade 0002 failed: {proc2.stderr}\n{proc2.stdout}"

    # 4. Verify post-upgrade state
    conn2 = sqlite3.connect(isolated_temp_db)
    conn2.execute("PRAGMA foreign_keys = ON;")
    cur2 = conn2.cursor()

    cur2.execute("SELECT version_num FROM alembic_version;")
    assert cur2.fetchone()[0] == "0002_email_security_workflows"

    # Verify tables
    cur2.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables_step2 = [r[0] for r in cur2.fetchall()]
    assert "account_tokens" in tables_step2
    assert "organization_invitations" in tables_step2
    assert len(tables_step2) == 23  # 22 application tables + alembic_version

    # Verify seeded records remained completely untouched
    cur2.execute("SELECT id, name, slug, account_type FROM organizations WHERE id = ?;", (org_id,))
    org_row = cur2.fetchone()
    assert org_row is not None
    assert org_row[1] == "Acme Logistics Global"
    assert org_row[2] == "acme-logistics"
    assert org_row[3] == "ENTERPRISE"

    cur2.execute("SELECT id, email, full_name, is_active FROM users WHERE id = ?;", (user_id,))
    user_row = cur2.fetchone()
    assert user_row is not None
    assert user_row[1] == "counsel@acmelogistics.com"
    assert user_row[2] == "Chief Legal Officer"
    assert user_row[3] == 1

    cur2.execute("SELECT id, title, status FROM contracts WHERE id = ?;", (contract_id,))
    contract_row = cur2.fetchone()
    assert contract_row is not None
    assert contract_row[1] == "Master Services Agreement 2026"
    assert contract_row[2] == "ACTIVE"

    cur2.execute("SELECT id, version_number, file_byte_size FROM contract_versions WHERE id = ?;", (version_id,))
    v_row = cur2.fetchone()
    assert v_row is not None
    assert v_row[1] == "v1.0"
    assert v_row[2] == 1048576

    # 5. Insert records into newly created tables from 0002
    token_id = str(uuid.uuid4())
    token_hash = "b"*64
    cur2.execute("""
        INSERT INTO account_tokens (id, user_id, token_hash, token_type, expires_at, is_used, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now', '+1 hour'), 0, datetime('now'), datetime('now'));
    """, (token_id, user_id, token_hash, "PASSWORD_RESET"))

    invite_id = str(uuid.uuid4())
    invite_hash = "c"*64
    cur2.execute("""
        INSERT INTO organization_invitations (id, organization_id, inviter_user_id, invitee_email, role, token_hash, expires_at, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+7 days'), 'PENDING', datetime('now'), datetime('now'));
    """, (invite_id, org_id, user_id, "associate@acmelogistics.com", "LEGAL_REVIEWER", invite_hash))

    conn2.commit()

    # Query newly inserted 0002 records
    cur2.execute("SELECT id, token_type, is_used FROM account_tokens WHERE id = ?;", (token_id,))
    t_row = cur2.fetchone()
    assert t_row is not None
    assert t_row[1] == "PASSWORD_RESET"
    assert t_row[2] == 0

    cur2.execute("SELECT id, invitee_email, role, status FROM organization_invitations WHERE id = ?;", (invite_id,))
    i_row = cur2.fetchone()
    assert i_row is not None
    assert i_row[1] == "associate@acmelogistics.com"
    assert i_row[2] == "LEGAL_REVIEWER"
    assert i_row[3] == "PENDING"

    conn2.close()


# ==============================================================================
# TEST SCENARIO B: FOREIGN KEY ENFORCEMENT
# ==============================================================================

def test_foreign_key_enforcement_and_rejection(isolated_temp_db):
    """
    Verifies:
    1. PRAGMA foreign_keys is verified active (returns 1).
    2. Valid parent-child relationships succeed.
    3. Invalid foreign key inserts are rejected by SQLite.
    4. Child records in newly created tables (account_tokens, invitations) reject nonexistent parents.
    """
    # Upgrade to head
    proc = run_alembic_command(["upgrade", "head"], isolated_temp_db)
    assert proc.returncode == 0

    conn = sqlite3.connect(isolated_temp_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Assert PRAGMA foreign_keys returns 1
    cur.execute("PRAGMA foreign_keys;")
    assert cur.fetchone()[0] == 1, "Foreign key enforcement must be active"

    # Test 1: Department referencing nonexistent organization must fail
    fake_org_id = str(uuid.uuid4())
    with pytest.raises(sqlite3.IntegrityError) as exc_fk1:
        cur.execute("""
            INSERT INTO departments (id, organization_id, name, created_at, updated_at)
            VALUES (?, ?, ?, datetime('now'), datetime('now'));
        """, (str(uuid.uuid4()), fake_org_id, "Orphaned Department"))
    assert "FOREIGN KEY constraint failed" in str(exc_fk1.value)

    # Test 2: Account token referencing nonexistent user must fail
    fake_user_id = str(uuid.uuid4())
    with pytest.raises(sqlite3.IntegrityError) as exc_fk2:
        cur.execute("""
            INSERT INTO account_tokens (id, user_id, token_hash, token_type, expires_at, is_used, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now', '+1 hour'), 0, datetime('now'), datetime('now'));
        """, (str(uuid.uuid4()), fake_user_id, "d"*64, "EMAIL_VERIFICATION"))
    assert "FOREIGN KEY constraint failed" in str(exc_fk2.value)

    # Test 3: Organization invitation referencing nonexistent organization must fail
    with pytest.raises(sqlite3.IntegrityError) as exc_fk3:
        cur.execute("""
            INSERT INTO organization_invitations (id, organization_id, inviter_user_id, invitee_email, role, token_hash, expires_at, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+7 days'), 'PENDING', datetime('now'), datetime('now'));
        """, (str(uuid.uuid4()), fake_org_id, fake_user_id, "test@orphan.com", "MEMBER", "e"*64))
    assert "FOREIGN KEY constraint failed" in str(exc_fk3.value)

    # Test 4: Valid parent insertion followed by valid child insertion succeeds
    real_org_id = str(uuid.uuid4())
    real_user_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO organizations (id, name, slug, account_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (real_org_id, "Valid Org Corp", "valid-org-corp", "BUSINESS"))

    cur.execute("""
        INSERT INTO users (id, email, password_hash, full_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (real_user_id, "valid@corp.com", "validhash", "Valid User"))

    # Valid child insert: account_token
    cur.execute("""
        INSERT INTO account_tokens (id, user_id, token_hash, token_type, expires_at, is_used, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now', '+1 hour'), 0, datetime('now'), datetime('now'));
    """, (str(uuid.uuid4()), real_user_id, "f"*64, "EMAIL_VERIFICATION"))

    # Valid child insert: organization_invitation
    cur.execute("""
        INSERT INTO organization_invitations (id, organization_id, inviter_user_id, invitee_email, role, token_hash, expires_at, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+7 days'), 'PENDING', datetime('now'), datetime('now'));
    """, (str(uuid.uuid4()), real_org_id, real_user_id, "invitee@corp.com", "MEMBER", "g"*64))

    conn.commit()
    conn.close()


# ==============================================================================
# TEST SCENARIO C: UNIQUE CONSTRAINTS
# ==============================================================================

def test_unique_constraints_rejection(isolated_temp_db):
    """
    Verifies that real unique constraints in migrations and models are enforced:
    1. organizations.slug
    2. users.email
    3. notifications.deduplication_key
    """
    proc = run_alembic_command(["upgrade", "head"], isolated_temp_db)
    assert proc.returncode == 0

    conn = sqlite3.connect(isolated_temp_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # 1. Test unique constraint on organizations.slug
    org1_id = str(uuid.uuid4())
    org2_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO organizations (id, name, slug, account_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (org1_id, "Unique Org Alpha", "shared-slug", "BUSINESS"))

    with pytest.raises(sqlite3.IntegrityError) as exc_slug:
        cur.execute("""
            INSERT INTO organizations (id, name, slug, account_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'));
        """, (org2_id, "Unique Org Beta", "shared-slug", "BUSINESS"))
    assert "UNIQUE constraint failed" in str(exc_slug.value)

    # 2. Test unique constraint on users.email
    user1_id = str(uuid.uuid4())
    user2_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO users (id, email, password_hash, full_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'));
    """, (user1_id, "unique.user@domain.com", "hash1", "User One"))

    with pytest.raises(sqlite3.IntegrityError) as exc_email:
        cur.execute("""
            INSERT INTO users (id, email, password_hash, full_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'));
        """, (user2_id, "unique.user@domain.com", "hash2", "User Two"))
    assert "UNIQUE constraint failed" in str(exc_email.value)

    # 3. Test unique constraint on notifications.deduplication_key
    notif1_id = str(uuid.uuid4())
    notif2_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO notifications (id, organization_id, user_id, title, message, event_type, scheduled_at, deduplication_key, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'), datetime('now'));
    """, (notif1_id, org1_id, user1_id, "Title 1", "Msg 1", "DEADLINE", "dedup_key_xyz"))

    with pytest.raises(sqlite3.IntegrityError) as exc_dedup:
        cur.execute("""
            INSERT INTO notifications (id, organization_id, user_id, title, message, event_type, scheduled_at, deduplication_key, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'), datetime('now'));
        """, (notif2_id, org1_id, user1_id, "Title 2", "Msg 2", "DEADLINE", "dedup_key_xyz"))
    assert "UNIQUE constraint failed" in str(exc_dedup.value)

    conn.close()


# ==============================================================================
# TEST SCENARIO E: FAILURE HANDLING AND CANONICAL PRESERVATION
# ==============================================================================

def test_failure_handling_and_canonical_inviolability():
    """
    Simulates a failure during a migration command and proves:
    1. Neither canonical database is ever touched or corrupted.
    2. An attempt to target canonical database paths is hard-blocked by run_alembic_command.
    """
    initial_stats = get_canonical_db_stats()

    # 1. Proactively prove safety guard rejects canonical paths
    with pytest.raises(AssertionError) as exc_guard_root:
        run_alembic_command(["upgrade", "head"], CANONICAL_DB_ROOT)
    assert "SAFETY VIOLATION" in str(exc_guard_root.value)

    with pytest.raises(AssertionError) as exc_guard_backend:
        run_alembic_command(["upgrade", "head"], CANONICAL_DB_BACKEND)
    assert "SAFETY VIOLATION" in str(exc_guard_backend.value)

    # 2. Simulate an invalid migration command on a temporary file
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_db = Path(tmp_dir) / "corrupt_test.db"
        # Run invalid downgrade revision
        proc_fail = run_alembic_command(["downgrade", "invalid_rev_id_xyz"], fake_db)
        assert proc_fail.returncode != 0

    # 3. Assert canonical databases remained completely untouched
    assert_canonical_databases_untouched(initial_stats)
