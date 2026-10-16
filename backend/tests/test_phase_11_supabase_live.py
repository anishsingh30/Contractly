import os
import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# This test suite only runs when TEST_POSTGRESQL_URL is set in environment
pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRESQL_URL"),
    reason="Live PostgreSQL staging database not configured (TEST_POSTGRESQL_URL unset)"
)

@pytest.fixture(scope="module")
def pg_url():
    url = os.environ.get("TEST_POSTGRESQL_URL")
    assert url, "TEST_POSTGRESQL_URL must be provided"
    assert "postgresql" in url, "Must be a PostgreSQL database"
    return url

@pytest.mark.asyncio
async def test_supabase_live_connection_and_version(pg_url):
    """Verify live connectivity and PostgreSQL version on Supabase staging."""
    engine = create_async_engine(pg_url, echo=False)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT version();"))
        ver = res.scalar()
        assert ver is not None
        assert "PostgreSQL" in ver
    await engine.dispose()

@pytest.mark.asyncio
async def test_supabase_live_advisory_locking(pg_url):
    """
    Verify PostgreSQL advisory locking functions properly on Supabase staging:
    1. Connection 1 acquires advisory lock.
    2. Connection 2 attempts to acquire the same lock and receives False (busy).
    3. Connection 1 releases the lock.
    4. Connection 2 can now acquire the lock and releases it.
    """
    engine = create_async_engine(pg_url, echo=False)
    lock_id = 987654321

    async with engine.connect() as conn1:
        # Acquire lock on conn1
        r1 = await conn1.execute(text(f"SELECT pg_try_advisory_lock({lock_id});"))
        assert r1.scalar() is True, "conn1 failed to acquire advisory lock"

        async with engine.connect() as conn2:
            # Try to acquire lock on conn2 (should be busy)
            r2 = await conn2.execute(text(f"SELECT pg_try_advisory_lock({lock_id});"))
            assert r2.scalar() is False, "conn2 unexpectedly acquired an already-held advisory lock"

        # Release lock on conn1
        r_rel = await conn1.execute(text(f"SELECT pg_advisory_unlock({lock_id});"))
        assert r_rel.scalar() is True, "conn1 failed to release advisory lock"

        # Now conn2 can acquire it
        async with engine.connect() as conn3:
            r3 = await conn3.execute(text(f"SELECT pg_try_advisory_lock({lock_id});"))
            assert r3.scalar() is True, "conn3 should have acquired the freed advisory lock"
            await conn3.execute(text(f"SELECT pg_advisory_unlock({lock_id});"))

    await engine.dispose()

@pytest.mark.asyncio
async def test_supabase_live_schema_foreign_key_enforcement(pg_url):
    """
    Verify PostgreSQL strict foreign key enforcement in Supabase staging:
    Attempting to insert a department or contract with a non-existent organization_id must fail.
    """
    engine = create_async_engine(pg_url, echo=False)
    fake_org_id = str(uuid.uuid4())
    fake_dept_id = str(uuid.uuid4())

    async with engine.connect() as conn:
        async with conn.begin():
            # Attempt to insert a department referencing a non-existent organization
            with pytest.raises(Exception) as exc_info:
                await conn.execute(text("""
                    INSERT INTO departments (id, organization_id, name, created_at, updated_at)
                    VALUES (:id, :org_id, 'Orphan Dept', NOW(), NOW());
                """), {
                    "id": fake_dept_id,
                    "org_id": fake_org_id
                })
            err_msg = str(exc_info.value).lower()
            assert "foreign key" in err_msg or "violates foreign key constraint" in err_msg

    await engine.dispose()

@pytest.mark.asyncio
async def test_supabase_live_transactional_lifecycle_and_cleanup(pg_url):
    """
    Verify transactional insert, query, unique constraint, and rollback/cleanup:
    1. Create an organization and user.
    2. Verify retrieval.
    3. Verify unique constraint enforcement (duplicate slug or email).
    4. Clean up test records via rollback.
    """
    engine = create_async_engine(pg_url, echo=False)
    test_org_id = str(uuid.uuid4())
    test_user_id = str(uuid.uuid4())
    test_slug = f"staging-org-{uuid.uuid4().hex[:8]}"
    test_email = f"staging_verify_{uuid.uuid4().hex[:8]}@contractly-staging.internal"

    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            # 1. Insert organization
            await conn.execute(text("""
                INSERT INTO organizations (id, name, slug, created_at, updated_at)
                VALUES (:id, 'Staging Test Org', :slug, NOW(), NOW());
            """), {"id": test_org_id, "slug": test_slug})

            # 2. Insert user
            await conn.execute(text("""
                INSERT INTO users (id, email, password_hash, full_name, is_active, created_at, updated_at)
                VALUES (:id, :email, 'hash_placeholder', 'Staging User', true, NOW(), NOW());
            """), {"id": test_user_id, "email": test_email})

            # 3. Read back
            res = await conn.execute(text("SELECT email, full_name FROM users WHERE id = :id;"), {"id": test_user_id})
            row = res.fetchone()
            assert row is not None
            assert row[0] == test_email
            assert row[1] == "Staging User"

            # 4. Duplicate email unique constraint verification
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

            # 5. Duplicate slug unique constraint verification
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
            # Always roll back so staging database stays completely clean
            await trans.rollback()

        # Verify nothing persisted
        res_org = await conn.execute(text("SELECT count(*) FROM organizations WHERE id = :id;"), {"id": test_org_id})
        assert res_org.scalar() == 0
        res_usr = await conn.execute(text("SELECT count(*) FROM users WHERE id = :id;"), {"id": test_user_id})
        assert res_usr.scalar() == 0

    await engine.dispose()
