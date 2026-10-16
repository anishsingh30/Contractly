import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRESQL_URL"),
    reason="Live PostgreSQL staging database not configured (TEST_POSTGRESQL_URL unset)"
)

@pytest.fixture(scope="module")
def pg_url():
    url = os.environ.get("TEST_POSTGRESQL_URL")
    assert url, "TEST_POSTGRESQL_URL must be provided"
    assert "neon.tech" in url, "Must be a Neon PostgreSQL database"
    return url

@pytest.mark.asyncio
async def test_neon_live_connectivity_and_version(pg_url):
    """Verify live connectivity and PostgreSQL version on Neon staging."""
    engine = create_async_engine(pg_url, echo=False)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT version();"))
        ver = res.scalar()
        assert ver is not None
        assert "PostgreSQL" in ver
    await engine.dispose()

@pytest.mark.asyncio
async def test_neon_live_session_advisory_locking_concurrency(pg_url):
    """
    Verify PostgreSQL session-level advisory locking on Neon direct endpoint:
    1. Connection 1 acquires advisory lock.
    2. Connection 2 attempts to acquire the exact same lock and receives False (busy).
    3. Connection 1 releases the lock.
    4. Connection 2 can now acquire the lock and cleanly releases it.
    """
    engine = create_async_engine(pg_url, echo=False)
    lock_id = 84920482  # Contractly's exact scheduler lock key

    async with engine.connect() as conn1:
        # Acquire on conn1
        r1 = await conn1.execute(text(f"SELECT pg_try_advisory_lock({lock_id});"))
        assert r1.scalar() is True, "conn1 failed to acquire advisory lock"

        # Concurrently try on conn2
        async with engine.connect() as conn2:
            r2 = await conn2.execute(text(f"SELECT pg_try_advisory_lock({lock_id});"))
            assert r2.scalar() is False, "conn2 unexpectedly acquired already-held advisory lock"

        # Release on conn1
        r_rel = await conn1.execute(text(f"SELECT pg_advisory_unlock({lock_id});"))
        assert r_rel.scalar() is True, "conn1 failed to release advisory lock"

        # Now conn3 can acquire it
        async with engine.connect() as conn3:
            r3 = await conn3.execute(text(f"SELECT pg_try_advisory_lock({lock_id});"))
            assert r3.scalar() is True, "conn3 should have acquired the freed advisory lock"
            await conn3.execute(text(f"SELECT pg_advisory_unlock({lock_id});"))

    await engine.dispose()

@pytest.mark.asyncio
async def test_neon_live_foreign_key_constraint_enforcement(pg_url):
    """Verify Neon PostgreSQL strictly rejects foreign key violations."""
    engine = create_async_engine(pg_url, echo=False)
    fake_org_id = str(uuid.uuid4())
    fake_dept_id = str(uuid.uuid4())

    async with engine.connect() as conn:
        async with conn.begin():
            with pytest.raises(Exception) as exc_info:
                await conn.execute(text("""
                    INSERT INTO departments (id, organization_id, name, created_at, updated_at)
                    VALUES (:id, :org_id, 'Orphan Dept', NOW(), NOW());
                """), {"id": fake_dept_id, "org_id": fake_org_id})
            err_msg = str(exc_info.value).lower()
            assert "foreign key" in err_msg or "violates foreign key constraint" in err_msg

    await engine.dispose()

@pytest.mark.asyncio
async def test_neon_live_transaction_lifecycle_uniqueness_and_rollback(pg_url):
    """
    Verify transaction lifecycle, uniqueness enforcement, and complete rollback cleanup.
    """
    engine = create_async_engine(pg_url, echo=False)
    test_org_id = str(uuid.uuid4())
    test_user_id = str(uuid.uuid4())
    test_slug = f"neon-org-{uuid.uuid4().hex[:8]}"
    test_email = f"neon_verify_{uuid.uuid4().hex[:8]}@contractly-staging.internal"

    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            # Insert organization
            await conn.execute(text("""
                INSERT INTO organizations (id, name, slug, created_at, updated_at)
                VALUES (:id, 'Neon Test Org', :slug, NOW(), NOW());
            """), {"id": test_org_id, "slug": test_slug})

            # Insert user
            await conn.execute(text("""
                INSERT INTO users (id, email, password_hash, full_name, is_active, created_at, updated_at)
                VALUES (:id, :email, 'hash_placeholder', 'Neon User', true, NOW(), NOW());
            """), {"id": test_user_id, "email": test_email})

            # Read back
            res = await conn.execute(text("SELECT email, full_name FROM users WHERE id = :id;"), {"id": test_user_id})
            row = res.fetchone()
            assert row is not None
            assert row[0] == test_email

            # Duplicate email unique constraint (using nested savepoint)
            try:
                async with conn.begin_nested():
                    await conn.execute(text("""
                        INSERT INTO users (id, email, password_hash, full_name, is_active, created_at, updated_at)
                        VALUES (:id, :email, 'hash_placeholder2', 'Duplicate User', true, NOW(), NOW());
                    """), {"id": str(uuid.uuid4()), "email": test_email})
                pytest.fail("Expected unique constraint violation on duplicate email")
            except Exception as exc:
                err_msg = str(exc).lower()
                assert "unique" in err_msg or "duplicate key" in err_msg

            # Duplicate slug unique constraint
            try:
                async with conn.begin_nested():
                    await conn.execute(text("""
                        INSERT INTO organizations (id, name, slug, created_at, updated_at)
                        VALUES (:id, 'Duplicate Slug Org', :slug, NOW(), NOW());
                    """), {"id": str(uuid.uuid4()), "slug": test_slug})
                pytest.fail("Expected unique constraint violation on duplicate slug")
            except Exception as exc:
                err_msg2 = str(exc).lower()
                assert "unique" in err_msg2 or "duplicate key" in err_msg2

        finally:
            await trans.rollback()

        # Confirm rollback left database completely clean
        res_org = await conn.execute(text("SELECT count(*) FROM organizations WHERE id = :id;"), {"id": test_org_id})
        assert res_org.scalar() == 0
        res_usr = await conn.execute(text("SELECT count(*) FROM users WHERE id = :id;"), {"id": test_user_id})
        assert res_usr.scalar() == 0

    await engine.dispose()

@pytest.mark.asyncio
async def test_neon_live_tokens_and_invitations_lifecycle(pg_url):
    """
    Verify Phase 5 schema additions (account_tokens and organization_invitations) on Neon:
    1. Insert organization and invited user.
    2. Insert organization invitation record.
    3. Insert account token record (e.g. email verification).
    4. Assert foreign keys, index lookup, and rollback.
    """
    engine = create_async_engine(pg_url, echo=False)
    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    inv_id = str(uuid.uuid4())
    token_id = str(uuid.uuid4())
    test_slug = f"token-test-{uuid.uuid4().hex[:8]}"

    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            # 1. Organization
            await conn.execute(text("""
                INSERT INTO organizations (id, name, slug, created_at, updated_at)
                VALUES (:id, 'Token Org', :slug, NOW(), NOW());
            """), {"id": org_id, "slug": test_slug})

            # 2. User
            await conn.execute(text("""
                INSERT INTO users (id, email, password_hash, full_name, is_active, created_at, updated_at)
                VALUES (:id, :email, 'hash', 'Invited User', true, NOW(), NOW());
            """), {"id": user_id, "email": f"inv_{uuid.uuid4().hex[:6]}@example.com"})

            # 3. Organization Invitation
            await conn.execute(text("""
                INSERT INTO organization_invitations (
                    id, organization_id, inviter_user_id, invitee_email, role, token_hash, status, expires_at, created_at, updated_at
                ) VALUES (
                    :id, :org_id, :inviter_id, 'invitee@example.com', 'LEGAL_REVIEWER', :thash, 'PENDING', NOW() + INTERVAL '7 days', NOW(), NOW()
                );
            """), {
                "id": inv_id,
                "org_id": org_id,
                "inviter_id": user_id,
                "thash": f"hash_{uuid.uuid4().hex}"
            })

            # 4. Account Token
            await conn.execute(text("""
                INSERT INTO account_tokens (
                    id, user_id, token_type, token_hash, expires_at, is_used, created_at, updated_at
                ) VALUES (
                    :id, :user_id, 'EMAIL_VERIFICATION', :thash, NOW() + INTERVAL '1 day', false, NOW(), NOW()
                );
            """), {
                "id": token_id,
                "user_id": user_id,
                "thash": f"tok_{uuid.uuid4().hex}"
            })


            # Query back
            res_inv = await conn.execute(text("SELECT status, role FROM organization_invitations WHERE id = :id;"), {"id": inv_id})
            inv_row = res_inv.fetchone()
            assert inv_row is not None
            assert inv_row[0] == "PENDING"
            assert inv_row[1] == "LEGAL_REVIEWER"

            res_tok = await conn.execute(text("SELECT token_type FROM account_tokens WHERE id = :id;"), {"id": token_id})
            tok_row = res_tok.fetchone()
            assert tok_row is not None
            assert tok_row[0] == "EMAIL_VERIFICATION"

        finally:
            await trans.rollback()

        # Assert clean
        cnt_inv = await conn.execute(text("SELECT count(*) FROM organization_invitations WHERE id = :id;"), {"id": inv_id})
        assert cnt_inv.scalar() == 0
        cnt_tok = await conn.execute(text("SELECT count(*) FROM account_tokens WHERE id = :id;"), {"id": token_id})
        assert cnt_tok.scalar() == 0

    await engine.dispose()
