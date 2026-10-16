import io
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_tenant_data_isolation():
    import uuid
    uid = uuid.uuid4().hex[:6]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register User in Tenant Alpha
        reg_alpha = {
            "email": f"alpha_counsel_{uid}@alpha.internal",
            "password": "Password123!",
            "full_name": "Alpha Counsel",
            "organization_name": f"Alpha Corporation {uid}",
            "account_type": "BUSINESS"
        }
        res_a = await ac.post("/api/v1/auth/register", json=reg_alpha)
        assert res_a.status_code == 200
        token_alpha = res_a.json()["access_token"]
        headers_alpha = {"Authorization": f"Bearer {token_alpha}"}

        # 2. Register User in Tenant Beta
        reg_beta = {
            "email": f"beta_counsel_{uid}@beta.internal",
            "password": "Password123!",
            "full_name": "Beta Counsel",
            "organization_name": f"Beta Holdings {uid}",
            "account_type": "BUSINESS"
        }
        res_b = await ac.post("/api/v1/auth/register", json=reg_beta)
        assert res_b.status_code == 200
        token_beta = res_b.json()["access_token"]
        headers_beta = {"Authorization": f"Bearer {token_beta}"}

        # 3. Tenant Alpha uploads a confidential contract
        doc_content = b"CONFIDENTIAL ALPHA CORP CONTRACT TERMS: Section 1.0 General Terms."
        files = {"file": ("alpha_confidential.txt", io.BytesIO(doc_content), "text/plain")}
        data = {
            "title": "Alpha Confidential IP Agreement",
            "contract_type": "IP License",
            "counterparty": "Secret Partner Ltd.",
            "value": "10000000"
        }
        upload_a = await ac.post("/api/v1/contracts/upload", headers=headers_alpha, data=data, files=files)
        assert upload_a.status_code == 200
        contract_alpha_id = upload_a.json()["id"]

        # 4. Tenant Alpha can access their own contract
        fetch_a = await ac.get(f"/api/v1/contracts/{contract_alpha_id}", headers=headers_alpha)
        assert fetch_a.status_code == 200
        assert fetch_a.json()["id"] == contract_alpha_id

        # 5. MANDATORY SECURITY CHECK: Tenant Beta attempts to access Tenant Alpha's contract
        fetch_b = await ac.get(f"/api/v1/contracts/{contract_alpha_id}", headers=headers_beta)
        # MUST return 404 Not Found (or 403 Forbidden) - tenant boundary enforced!
        assert fetch_b.status_code in (403, 404), f"Cross-tenant leak! Received status {fetch_b.status_code}"

        # 6. Tenant Beta lists contracts - Tenant Alpha's contract MUST NOT appear in the list
        list_b = await ac.get("/api/v1/contracts", headers=headers_beta)
        assert list_b.status_code == 200
        beta_contracts = list_b.json()
        beta_contract_ids = [c["id"] for c in beta_contracts]
        assert contract_alpha_id not in beta_contract_ids
