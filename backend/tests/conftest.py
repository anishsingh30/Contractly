"""
Pytest configuration for the Contractly backend test suite.

Provides:
- An ephemeral, per-session in-memory SQLite database so tests never touch
  the real contractly.db on disk.
- A seed fixture that creates the default dev-fallback user and organization
  expected by `get_current_user` / `get_current_tenant` in dependencies.py
  when no Bearer token is supplied.
"""

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.main import app

# ── In-memory SQLite (shared cache so all connections see the same data) ──────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:?cache=shared"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def test_engine():
    """Create tables once per test-session on the in-memory database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with engine.begin() as conn:
        # Import all models so they are registered with Base.metadata
        import app.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def override_db(test_engine):
    """
    Override the FastAPI `get_db` dependency so every request in tests uses
    the shared in-memory engine instead of the production database.
    """
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def _get_test_db():
        async with TestSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def isolate_test_dependencies(test_engine):
    """
    Function-scoped fixture ensuring strict test isolation:
    1. Re-asserts app.dependency_overrides[get_db] points to the in-memory test engine.
    2. Resets all rate limiters before and after the test.
    3. Cleans up any leaked test-specific dependency overrides (e.g., auth mocks) in teardown.
    """
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def _get_test_db():
        async with TestSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    # Ensure get_db is always active before test runs
    app.dependency_overrides[get_db] = _get_test_db

    # Clean rate limiters before test
    from app.core.rate_limiter import auth_rate_limiter, ai_rate_limiter
    for limiter in (auth_rate_limiter, ai_rate_limiter):
        if hasattr(limiter, "backend"):
            if hasattr(limiter.backend, "_history"):
                limiter.backend._history.clear()
            if hasattr(limiter.backend, "_fallback") and hasattr(limiter.backend._fallback, "_history"):
                limiter.backend._fallback._history.clear()

    yield

    # Teardown: purge any leaked overrides created during test execution
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = _get_test_db

    # Clean rate limiters after test
    for limiter in (auth_rate_limiter, ai_rate_limiter):
        if hasattr(limiter, "backend"):
            if hasattr(limiter.backend, "_history"):
                limiter.backend._history.clear()
            if hasattr(limiter.backend, "_fallback") and hasattr(limiter.backend._fallback, "_history"):
                limiter.backend._fallback._history.clear()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def seed_dev_user(override_db, test_engine):
    """
    Seed the default dev-fallback user and organization that
    `get_current_user` / `get_current_tenant` in dependencies.py
    expect when no JWT token is supplied by a test.
    """
    from sqlalchemy.future import select
    from app.models.user import User, OrganizationMember
    from app.models.organization import Organization
    from app.core.security import get_password_hash

    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with TestSessionLocal() as session:
        # Check if already seeded (idempotent)
        result = await session.execute(
            select(User).where(User.email == "legal@northstar.internal")
        )
        if result.scalar_one_or_none() is not None:
            return

        # Seed org
        org = Organization(
            name="Northstar Technologies",
            slug="northstar-tech",
            account_type="BUSINESS",
        )
        session.add(org)
        await session.flush()

        # Seed user
        user = User(
            email="legal@northstar.internal",
            password_hash=get_password_hash("Password123!"),
            full_name="Legal Manager",
        )
        session.add(user)
        await session.flush()

        # Seed membership
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="LEGAL_MANAGER",
        )
        session.add(member)
        await session.commit()


@pytest_asyncio.fixture
async def auth_headers(override_db, seed_dev_user, test_engine):
    """
    Returns valid Authorization Bearer headers for the seeded Northstar legal manager.
    Used for tests that require authentication.
    """
    from sqlalchemy.future import select
    from app.models.user import User, OrganizationMember
    from app.core.security import create_access_token

    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "legal@northstar.internal")
        )
        user = result.scalar_one()
        m_res = await session.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == user.id)
        )
        member = m_res.scalar_one()
        token = create_access_token(
            subject=user.id,
            org_id=member.organization_id,
            role=member.role
        )
        return {"Authorization": f"Bearer {token}"}
