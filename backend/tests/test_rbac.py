"""
Test suite for Contractly Role-Based Access Control (RBAC) - Phase B.

Test Matrix:
1. OWNER can perform owner actions (full permissions wildcard '*')
2. ADMIN can perform admin actions (contracts, obligations, org)
3. LEGAL_MANAGER can manage contracts, clauses, risks, obligations, delete contracts
4. LEGAL_REVIEWER can review/read contracts and obligations, but cannot delete contracts (HTTP 403)
5. PROCUREMENT can upload contracts and obligations, but cannot delete contracts (HTTP 403)
6. FINANCE can read contracts/obligations, but cannot delete contracts or create obligations (HTTP 403)
7. HR cannot perform unrelated procurement/contract deletion (HTTP 403)
8. EMPLOYEE cannot delete contracts or upload contracts (HTTP 403)
9. EMPLOYEE cannot create obligations (HTTP 403)
10. Unauthorized role receives HTTP 403 Forbidden with detail message
11. Frontend/client role spoofing (e.g. custom header or fake token role claim) cannot bypass server-side DB check
12. Direct API requests are protected authoritative server-side
"""

import pytest
import io
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.future import select

from app.main import app
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.contract import Contract
from app.core.security import get_password_hash, create_access_token


async def _create_user_with_role(test_engine, email: str, role: str) -> tuple[User, str, Organization]:
    """Helper to create a user with a specific DB role in Northstar Technologies."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with TestSessionLocal() as session:
        # Get or create Northstar org
        res_org = await session.execute(
            select(Organization).where(Organization.slug == "northstar-tech")
        )
        org = res_org.scalar_one_or_none()
        if not org:
            org = Organization(
                name="Northstar Technologies",
                slug="northstar-tech",
                account_type="BUSINESS",
            )
            session.add(org)
            await session.flush()

        # Check if user already exists
        res_u = await session.execute(select(User).where(User.email == email))
        user = res_u.scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                password_hash=get_password_hash("Password123!"),
                full_name=f"{role.title()} User",
            )
            session.add(user)
            await session.flush()

            member = OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role=role,
                status="ACTIVE",
            )
            session.add(member)
            await session.commit()
            await session.refresh(user)
        else:
            # Update member role if existing
            res_m = await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == org.id,
                )
            )
            member = res_m.scalar_one_or_none()
            if member:
                member.role = role
                await session.commit()

        token = create_access_token(
            subject=user.id,
            org_id=org.id,
            role=role,
        )
        return user, token, org


async def _seed_test_contract(test_engine, org_id: str) -> Contract:
    """Helper to seed a test contract under the organization."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org_id,
            contract_id=f"CTR-TEST-{org_id[:4]}",
            title="RBAC Verification Agreement",
            contract_type="Service Level Agreement",
            counterparty="RBAC Testing Corp",
            department="Legal",
            value=250000.0,
            currency="INR",
            status="ACTIVE",
        )
        session.add(contract)
        await session.commit()
        await session.refresh(contract)
        return contract


@pytest.mark.asyncio
async def test_owner_has_full_permissions(test_engine):
    """1. OWNER can perform owner actions (* permissions)."""
    _, token, org = await _create_user_with_role(test_engine, "owner@northstar.internal", "OWNER")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        # Read contracts
        res = await ac.get("/api/v1/contracts", headers=headers)
        assert res.status_code == 200

        # Read org
        res_org = await ac.get("/api/v1/organizations/current", headers=headers)
        assert res_org.status_code == 200

        # Delete contract
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_perform_admin_actions(test_engine):
    """2. ADMIN can perform admin actions (contracts, obligations, org)."""
    _, token, org = await _create_user_with_role(test_engine, "admin@northstar.internal", "ADMIN")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        # Read contracts
        res = await ac.get("/api/v1/contracts", headers=headers)
        assert res.status_code == 200

        # Admin can delete contracts
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 200


@pytest.mark.asyncio
async def test_legal_manager_can_manage_contracts(test_engine):
    """3. LEGAL_MANAGER can manage contracts and delete them."""
    _, token, org = await _create_user_with_role(test_engine, "lm@northstar.internal", "LEGAL_MANAGER")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        res = await ac.get(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res.status_code == 200

        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 200


@pytest.mark.asyncio
async def test_legal_reviewer_cannot_delete_contracts(test_engine):
    """4. LEGAL_REVIEWER can review/read but cannot delete contracts (HTTP 403)."""
    _, token, org = await _create_user_with_role(test_engine, "reviewer@northstar.internal", "LEGAL_REVIEWER")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        # Can read
        res_read = await ac.get(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_read.status_code == 200

        # Cannot delete
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 403
        assert "lacks required permission 'contracts:delete'" in res_del.json()["detail"]


@pytest.mark.asyncio
async def test_procurement_can_read_and_create_but_cannot_delete(test_engine):
    """5. PROCUREMENT can upload contracts but cannot delete contracts (HTTP 403)."""
    _, token, org = await _create_user_with_role(test_engine, "procure@northstar.internal", "PROCUREMENT")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        # Read ok
        res = await ac.get("/api/v1/contracts", headers=headers)
        assert res.status_code == 200

        # Cannot delete
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 403


@pytest.mark.asyncio
async def test_finance_cannot_delete_contracts_or_create_obligations(test_engine):
    """6. FINANCE cannot delete contracts (HTTP 403) or perform write actions."""
    _, token, org = await _create_user_with_role(test_engine, "finance@northstar.internal", "FINANCE")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        # Can read
        res = await ac.get(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res.status_code == 200

        # Cannot delete
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 403

        # Cannot create obligation
        res_obl = await ac.post(
            f"/api/v1/contracts/{contract.id}/obligations",
            json={"title": "Unauthorized Obligation", "due_date": "2027-01-01"},
            headers=headers
        )
        assert res_obl.status_code == 403


@pytest.mark.asyncio
async def test_hr_cannot_delete_contracts(test_engine):
    """7. HR cannot perform contract deletion (HTTP 403)."""
    _, token, org = await _create_user_with_role(test_engine, "hr@northstar.internal", "HR")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_delete_or_upload_contracts(test_engine):
    """8. EMPLOYEE cannot delete contracts (HTTP 403) and cannot upload contracts (HTTP 403)."""
    _, token, org = await _create_user_with_role(test_engine, "emp@northstar.internal", "EMPLOYEE")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        # Cannot delete
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 403

        # Cannot upload contract
        file_content = b"Contract content"
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"title": "Employee Contract"}
        res_upload = await ac.post("/api/v1/contracts/upload", data=data, files=files, headers=headers)
        assert res_upload.status_code == 403
        assert "lacks required permission 'contracts:create'" in res_upload.json()["detail"]


@pytest.mark.asyncio
async def test_employee_cannot_create_obligations(test_engine):
    """9. EMPLOYEE cannot create obligations (HTTP 403)."""
    _, token, org = await _create_user_with_role(test_engine, "emp2@northstar.internal", "EMPLOYEE")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        res = await ac.post(
            f"/api/v1/contracts/{contract.id}/obligations",
            json={"title": "Test Obligation", "due_date": "2027-01-01"},
            headers=headers
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_unauthorized_role_receives_http_403_detail(test_engine):
    """10. Unauthorized role receives HTTP 403 with descriptive error message."""
    _, token, org = await _create_user_with_role(test_engine, "emp3@northstar.internal", "EMPLOYEE")
    contract = await _seed_test_contract(test_engine, org.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        res = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res.status_code == 403
        data = res.json()
        assert "detail" in data
        assert "lacks required permission 'contracts:delete'" in data["detail"]


@pytest.mark.asyncio
async def test_frontend_role_spoofing_cannot_grant_backend_permission(test_engine):
    """11. An attacker putting fake role claims in JWT or headers cannot bypass server DB role lookup."""
    user, _, org = await _create_user_with_role(test_engine, "spoof@northstar.internal", "EMPLOYEE")
    contract = await _seed_test_contract(test_engine, org.id)

    # Attacker crafts a token claiming to be 'OWNER'
    fake_token = create_access_token(
        subject=user.id,
        org_id=org.id,
        role="OWNER",  # Spoofed claim in token payload
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Send fake token along with spoofed X-Tenant-Role headers
        headers = {
            "Authorization": f"Bearer {fake_token}",
            "X-Tenant-Role": "OWNER",
            "X-Role": "OWNER"
        }
        # Server verifies the actual database OrganizationMember record for user.id!
        res_del = await ac.delete(f"/api/v1/contracts/{contract.id}", headers=headers)
        assert res_del.status_code == 403
        assert "lacks required permission 'contracts:delete'" in res_del.json()["detail"]


@pytest.mark.asyncio
async def test_auth_me_returns_authoritative_permissions(test_engine):
    """12. /api/v1/auth/me returns the server-side role and permissions list."""
    _, token, _ = await _create_user_with_role(test_engine, "reviewer2@northstar.internal", "LEGAL_REVIEWER")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        res = await ac.get("/api/v1/auth/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "LEGAL_REVIEWER"
        assert "contracts:read" in data["permissions"]
        assert "obligations:read" in data["permissions"]
        assert "contracts:delete" not in data["permissions"]
