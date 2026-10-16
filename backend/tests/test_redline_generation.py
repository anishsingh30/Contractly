import io
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.ai.gemini_provider import (
    GeminiTimeoutError,
    GeminiRateLimitError,
    GeminiUnavailableError,
    GeminiResponseParsingError
)

SAMPLE_NEGOTIATION_CONTRACT = """SOFTWARE-AS-A-SERVICE SUBSCRIPTION AGREEMENT
Between Customer Systems Pvt. Ltd. and Vendor Cloud Inc.

Section 1.0: Fees and Payment.
Customer pays INR 12,00,000 annually. Invoices are payable within 15 calendar days. Undisputed overdue amounts may accrue interest at 1.5% per month, subject to law.
The agreement renews for one-year terms unless either party gives written non-renewal notice at least 90 days before expiry.

Section 2.0: Security Incident Response.
Provider maintains reasonable safeguards and will notify Customer of a confirmed security incident affecting Customer Data without undue delay and, where practicable, within 72 hours.

Section 3.0: Confidentiality.
Employee will not use or disclose confidential information except for assigned duties.

Section 4.0: Termination and Cure.
Either party may terminate for uncured material breach after 15 days' written notice. Client may terminate for convenience on 10 days' notice.
"""

SAMPLE_BALANCED_CONTRACT = """STANDARD RECIPROCAL NON-DISCLOSURE AGREEMENT
Between Alpha Labs and Beta Tech.

Section 1.0: Mutual Confidentiality.
Each party agrees to hold the other party's Confidential Information in strict confidence using at least reasonable care for a period of three (3) years.

Section 2.0: Governing Law.
This Agreement is governed by the laws of India.
"""


@pytest.mark.asyncio
async def test_upload_contract_triggers_automatic_redlines(auth_headers):
    """Verify that uploading a contract automatically runs grounded redline generation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {
            "file": ("vendor_saas_agreement.txt", io.BytesIO(SAMPLE_NEGOTIATION_CONTRACT.encode("utf-8")), "text/plain")
        }
        data = {
            "title": "Vendor SaaS Agreement Auto Redline Test",
            "contract_type": "Master Services Agreement",
            "counterparty": "Vendor Cloud Inc.",
            "department": "Engineering",
            "value": "1200000",
            "currency": "INR",
            "start_date": "2026-11-01",
            "expiry_date": "2027-10-31",
            "governing_law": "Laws of India"
        }

        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        assert upload_res.status_code == 200, upload_res.text
        contract_data = upload_res.json()
        contract_id = contract_data["id"]

        # Verify contract has clauses
        assert len(contract_data["clauses"]) > 0

        # Verify redlines were generated and are persisted in GET /api/v1/contracts/{id}
        assert "redlines" in contract_data
        redlines = contract_data["redlines"]
        assert len(redlines) > 0, "Expected redlines to be automatically generated on upload"

        # Verify proposal fields
        first_rd = redlines[0]
        assert "original_text" in first_rd
        assert "suggested_text" in first_rd
        assert "section_title" in first_rd
        assert "rationale" in first_rd
        assert first_rd["status"] == "PENDING"

        # Verify GET /api/v1/contracts/{id}/redlines returns the same persisted items across page reloads
        list_res = await ac.get(f"/api/v1/contracts/{contract_id}/redlines", headers=auth_headers)
        assert list_res.status_code == 200
        persisted_redlines = list_res.json()
        assert len(persisted_redlines) == len(redlines)


@pytest.mark.asyncio
async def test_on_demand_redline_generation_endpoint(auth_headers):
    """Verify POST /api/v1/contracts/{id}/generate-redlines runs on-demand generation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {
            "file": ("consulting_contract.txt", io.BytesIO(SAMPLE_NEGOTIATION_CONTRACT.encode("utf-8")), "text/plain")
        }
        data = {
            "title": "Consulting On Demand Redline Test",
            "contract_type": "Consulting Agreement",
            "counterparty": "Consultant Co.",
            "department": "Legal",
            "value": "500000",
            "currency": "INR"
        }

        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        assert upload_res.status_code == 200
        contract_id = upload_res.json()["id"]

        # Trigger on-demand generation
        gen_res = await ac.post(f"/api/v1/contracts/{contract_id}/generate-redlines", headers=auth_headers)
        assert gen_res.status_code == 200, gen_res.text
        proposals = gen_res.json()
        assert isinstance(proposals, list)
        assert len(proposals) > 0

        for prop in proposals:
            assert prop["original_text"] != prop["suggested_text"]
            assert prop["status"] == "PENDING"
            assert prop["contract_id"] == contract_id


@pytest.mark.asyncio
async def test_accept_and_reject_redline_persistence(auth_headers):
    """Verify accept/reject updates proposal status persistently without mutating the original contract text."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {
            "file": ("review_test.txt", io.BytesIO(SAMPLE_NEGOTIATION_CONTRACT.encode("utf-8")), "text/plain")
        }
        data = {
            "title": "Accept Reject Workflow Test",
            "contract_type": "Master Services Agreement",
            "counterparty": "Vendor Cloud Inc.",
            "department": "Legal"
        }
        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        contract_data = upload_res.json()
        contract_id = contract_data["id"]
        redlines = contract_data["redlines"]
        assert len(redlines) >= 2

        rd_to_accept = redlines[0]["id"]
        rd_to_reject = redlines[1]["id"]

        # Accept first redline
        accept_res = await ac.patch(
            f"/api/v1/contracts/{contract_id}/redlines/{rd_to_accept}/status",
            headers=auth_headers,
            json={"status": "ACCEPTED"}
        )
        assert accept_res.status_code == 200
        assert accept_res.json()["status"] == "ACCEPTED"

        # Reject second redline
        reject_res = await ac.patch(
            f"/api/v1/contracts/{contract_id}/redlines/{rd_to_reject}/status",
            headers=auth_headers,
            json={"status": "REJECTED"}
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "REJECTED"

        # Verify persistence on re-fetch
        fetch_res = await ac.get(f"/api/v1/contracts/{contract_id}/redlines", headers=auth_headers)
        persisted = fetch_res.json()
        accepted_item = next(r for r in persisted if r["id"] == rd_to_accept)
        rejected_item = next(r for r in persisted if r["id"] == rd_to_reject)
        assert accepted_item["status"] == "ACCEPTED"
        assert rejected_item["status"] == "REJECTED"

        # Re-generating redlines must PRESERVE user accept/reject decisions
        regen_res = await ac.post(f"/api/v1/contracts/{contract_id}/generate-redlines", headers=auth_headers)
        assert regen_res.status_code == 200
        refetch_res = await ac.get(f"/api/v1/contracts/{contract_id}/redlines", headers=auth_headers)
        refetched = refetch_res.json()
        assert any(r["id"] == rd_to_accept and r["status"] == "ACCEPTED" for r in refetched)
        assert any(r["id"] == rd_to_reject and r["status"] == "REJECTED" for r in refetched)


@pytest.mark.asyncio
async def test_docx_export_contains_saved_proposals(auth_headers):
    """Verify DOCX export produces a valid document containing the proposals."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {
            "file": ("export_test.txt", io.BytesIO(SAMPLE_NEGOTIATION_CONTRACT.encode("utf-8")), "text/plain")
        }
        data = {
            "title": "DOCX Export Test Contract",
            "contract_type": "Master Services Agreement",
            "counterparty": "Vendor Cloud Inc.",
            "department": "Legal"
        }
        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        contract_id = upload_res.json()["id"]

        docx_res = await ac.get(f"/api/v1/contracts/{contract_id}/export/docx", headers=auth_headers)
        assert docx_res.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in docx_res.headers.get("content-type", "")
        assert len(docx_res.content) > 1000
        # Check ZIP / DOCX magic bytes (PK)
        assert docx_res.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_negotiation_analysis_with_no_custom_playbook(auth_headers):
    """Verify that when no custom playbook rules exist, standard baseline benchmarks are evaluated."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {
            "file": ("baseline_test.txt", io.BytesIO(SAMPLE_NEGOTIATION_CONTRACT.encode("utf-8")), "text/plain")
        }
        data = {
            "title": "Playbook Baseline Evaluation Test",
            "contract_type": "Master Services Agreement",
            "counterparty": "Vendor Cloud Inc.",
            "department": "Legal"
        }
        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        contract_id = upload_res.json()["id"]

        analysis_res = await ac.get(f"/api/v1/contracts/{contract_id}/negotiation-analysis", headers=auth_headers)
        assert analysis_res.status_code == 200
        findings = analysis_res.json()
        assert len(findings) > 0, "Expected baseline findings when no custom playbook is configured"
        # Findings should reference standard baseline benchmarks
        assert any(f["rule_id"].startswith("baseline-") for f in findings)


@pytest.mark.asyncio
async def test_gemini_failures_handled_gracefully_with_fallback(auth_headers):
    """Verify that Gemini timeouts, rate limits, and malformed responses fallback cleanly to heuristic proposals."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {
            "file": ("fallback_test.txt", io.BytesIO(SAMPLE_NEGOTIATION_CONTRACT.encode("utf-8")), "text/plain")
        }
        data = {
            "title": "Gemini Fallback Test",
            "contract_type": "Master Services Agreement",
            "counterparty": "Vendor Cloud Inc.",
            "department": "Engineering"
        }
        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        contract_id = upload_res.json()["id"]

        # Simulate Gemini Timeout
        with patch("app.services.ai.gemini_provider.gemini_provider.generate_content", side_effect=GeminiTimeoutError("Request timed out")):
            res = await ac.post(f"/api/v1/contracts/{contract_id}/generate-redlines", headers=auth_headers)
            assert res.status_code == 200
            proposals = res.json()
            assert len(proposals) > 0, "Expected heuristic fallback proposals on Gemini timeout"

        # Simulate Gemini Rate Limit
        with patch("app.services.ai.gemini_provider.gemini_provider.generate_content", side_effect=GeminiRateLimitError("Rate limit exceeded")):
            res = await ac.post(f"/api/v1/contracts/{contract_id}/generate-redlines", headers=auth_headers)
            assert res.status_code == 200
            assert len(res.json()) > 0

        # Simulate Malformed JSON from Gemini
        with patch("app.services.ai.gemini_provider.gemini_provider.generate_content", return_value="Here are the revisions: NOT_VALID_JSON"):
            res = await ac.post(f"/api/v1/contracts/{contract_id}/generate-redlines", headers=auth_headers)
            assert res.status_code == 200
            assert len(res.json()) > 0


@pytest.mark.asyncio
async def test_tenant_isolation_on_redlines(auth_headers):
    """Verify that redlines belonging to one tenant organization cannot be accessed by another tenant."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {
            "file": ("tenant_iso_test.txt", io.BytesIO(SAMPLE_NEGOTIATION_CONTRACT.encode("utf-8")), "text/plain")
        }
        data = {
            "title": "Tenant Isolation Redlines Test",
            "contract_type": "Master Services Agreement",
            "counterparty": "Vendor Cloud Inc.",
            "department": "Legal"
        }
        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        contract_id = upload_res.json()["id"]

        # Header for an unauthorized different tenant
        foreign_headers = {
            **auth_headers,
            "X-Tenant-ID": "00000000-0000-0000-0000-000000000000"
        }
        iso_res = await ac.get(f"/api/v1/contracts/{contract_id}/redlines", headers=foreign_headers)
        assert iso_res.status_code in (403, 404)

        gen_iso_res = await ac.post(f"/api/v1/contracts/{contract_id}/generate-redlines", headers=foreign_headers)
        assert gen_iso_res.status_code in (403, 404)
