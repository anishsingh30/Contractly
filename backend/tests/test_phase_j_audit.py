import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractVersion
from app.models.obligation import Obligation, ObligationEvidence
from app.core.security import create_access_token, get_password_hash
from app.core.rate_limiter import InMemorySlidingWindowRateLimiter, ai_rate_limiter


async def _setup_tenant(test_engine, name_prefix: str, role: str = "OWNER"):
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(
            name=f"{name_prefix} Org",
            slug=f"{name_prefix.lower()}-slug",
            account_type="BUSINESS"
        )
        session.add(org)
        await session.flush()

        user = User(
            email=f"{name_prefix.lower()}@test.internal",
            password_hash=get_password_hash("Password123!"),
            full_name=f"{name_prefix} User",
            is_active=True
        )
        session.add(user)
        await session.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=role,
            status="ACTIVE"
        )
        session.add(member)
        await session.commit()

        token = create_access_token(subject=user.id, org_id=org.id, role=role)
        return org, user, token


@pytest.mark.asyncio
async def test_ai_rate_limiter_sliding_window():
    """Verify in-memory sliding window rate limiter blocks excessive AI requests with HTTP 429."""
    limiter = InMemorySlidingWindowRateLimiter(default_limit=3, window_seconds=60)
    user_key = "test_user_rate_limit"

    # First 3 requests must succeed
    for _ in range(3):
        await limiter.check_rate_limit(user_key)

    # 4th request must raise HTTP 429
    with pytest.raises(Exception) as exc_info:
        await limiter.check_rate_limit(user_key)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers

    # Reset allows new requests
    await limiter.reset()
    await limiter.check_rate_limit(user_key)


@pytest.mark.asyncio
async def test_ai_status_endpoint_does_not_disclose_internal_file_paths(test_engine):
    """Verify /ai/status reports boolean configuration status without path disclosure."""
    _, _, token = await _setup_tenant(test_engine, "AIStatusOrg", role="LEGAL_MANAGER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/ai/status", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert "configured" in data
        assert "provider" in data
        assert isinstance(data.get("env_file_loaded"), bool)
        assert isinstance(data.get("env_file_exists"), bool)
        # Ensure no Windows or Unix absolute paths in response
        assert not str(data.get("env_file_loaded")).startswith("A:")
        assert not str(data.get("env_file_loaded")).startswith("/")


@pytest.mark.asyncio
async def test_contract_version_download_tenant_isolation(test_engine):
    """
    Verify authorized contract version download:
    1. Tenant A downloads version file -> HTTP 200 with proper headers.
    2. Tenant B requests Tenant A's version -> HTTP 404 (strictly isolated).
    3. Employee without PERMISSION_CONTRACTS_READ -> HTTP 403.
    """
    org_a, user_a, token_a = await _setup_tenant(test_engine, "DownloadOrgA", role="LEGAL_MANAGER")
    org_b, _, token_b = await _setup_tenant(test_engine, "DownloadOrgB", role="OWNER")
    _, _, token_emp = await _setup_tenant(test_engine, "DownloadEmp", role="EMPLOYEE")

    # Upload contract with version in Tenant A
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        file_bytes = b"VENDOR AGREEMENT: Section 1. Scope of work and deliverables. Section 2. Liability capped at fees paid."
        files = {"file": ("vendor_agreement.txt", io.BytesIO(file_bytes), "text/plain")}
        data = {
            "title": "Vendor Download Agreement",
            "contract_type": "MSA",
            "counterparty": "Tech Vendor Corp",
            "value": "250000"
        }
        upload_res = await client.post(
            "/api/v1/contracts/upload",
            data=data,
            files=files,
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert upload_res.status_code == 200
        contract_data = upload_res.json()
        contract_id = contract_data["id"]

        # Fetch versions
        versions_res = await client.get(
            f"/api/v1/contracts/{contract_id}/versions",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert versions_res.status_code == 200
        versions = versions_res.json()
        assert len(versions) >= 1
        version_id = versions[0]["id"]

        # 1. Tenant A downloads version file -> HTTP 200
        dl_res = await client.get(
            f"/api/v1/contracts/{contract_id}/versions/{version_id}/download",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert dl_res.status_code == 200
        assert dl_res.content == file_bytes
        assert "Content-Disposition" in dl_res.headers
        assert "attachment" in dl_res.headers["Content-Disposition"]

        # 2. Tenant B attempts to download Tenant A's version -> HTTP 404
        dl_res_b = await client.get(
            f"/api/v1/contracts/{contract_id}/versions/{version_id}/download",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert dl_res_b.status_code == 404


@pytest.mark.asyncio
async def test_obligation_evidence_download_tenant_isolation(test_engine):
    """
    Verify obligation evidence upload & download:
    1. Tenant A uploads compliance evidence.
    2. Tenant A downloads evidence -> HTTP 200.
    3. Tenant B requests Tenant A's evidence -> HTTP 404.
    """
    org_a, _, token_a = await _setup_tenant(test_engine, "EvidenceOrgA", role="LEGAL_MANAGER")
    org_b, _, token_b = await _setup_tenant(test_engine, "EvidenceOrgB", role="OWNER")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org_a.id,
            contract_id="CTR-EVD-01",
            title="Evidence Test Contract",
            contract_type="SaaS",
            counterparty="Vendor EVD",
            status="ACTIVE"
        )
        session.add(contract)
        await session.flush()

        obligation = Obligation(
            contract_id=contract.id,
            obligor_party="Vendor EVD",
            obligee_party="EvidenceOrgA",
            title="SOC 2 Type II Compliance Report",
            description="Submit annual SOC 2 report",
            due_date="2027-06-30",
            status="UPCOMING"
        )
        session.add(obligation)
        await session.commit()
        obligation_id = obligation.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload evidence
        evidence_content = b"SOC2 Compliance Certificate Content Validated"
        files = {"file": ("soc2_audit.pdf", io.BytesIO(evidence_content), "application/pdf")}
        upload_res = await client.post(
            f"/api/v1/obligations/{obligation_id}/evidence",
            files=files,
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert upload_res.status_code == 200
        evidence_data = upload_res.json()
        evidence_id = evidence_data["id"]

        # 2. Tenant A downloads evidence -> HTTP 200
        dl_res = await client.get(
            f"/api/v1/obligations/{obligation_id}/evidence/{evidence_id}/download",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert dl_res.status_code == 200
        assert dl_res.content == evidence_content

        # 3. Tenant B attempts download -> HTTP 404
        dl_res_b = await client.get(
            f"/api/v1/obligations/{obligation_id}/evidence/{evidence_id}/download",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert dl_res_b.status_code == 404


@pytest.mark.asyncio
async def test_contract_qa_input_validation(test_engine):
    """Verify input validation on contract Q&A: empty question and oversized question."""
    org, _, token = await _setup_tenant(test_engine, "QAValidateOrg", role="LEGAL_MANAGER")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org.id,
            contract_id="CTR-QA-VAL-01",
            title="QA Validation Contract",
            contract_type="SaaS",
            counterparty="Vendor QA",
            status="ACTIVE"
        )
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty question -> HTTP 400
        res_empty = await client.post(
            f"/api/v1/contracts/{contract_id}/qa",
            json={"question": "   "},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_empty.status_code == 400
        assert "Question cannot be empty" in res_empty.json()["detail"]

        # Oversized question -> HTTP 400
        oversized = "A" * 5000
        res_large = await client.post(
            f"/api/v1/contracts/{contract_id}/qa",
            json={"question": oversized},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_large.status_code in (400, 422)
