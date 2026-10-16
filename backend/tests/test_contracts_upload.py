import io
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_upload_contract_and_analysis(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Sample legal contract content
        sample_contract = (
            "MASTER CLOUD SERVICES AGREEMENT\n\n"
            "This Agreement is between Northstar Technologies and CloudProvider Inc.\n\n"
            "Section 11.0: Limitation of Liability.\n"
            "Neither party shall be liable for consequential damages. Service Provider liability shall remain uncapped with respect to gross negligence and confidentiality breaches.\n\n"
            "Section 14.0: Termination for Convenience.\n"
            "Either party may terminate this agreement upon providing sixty (60) days advance written notice.\n\n"
            "Section 9.0: Restrictive Covenants.\n"
            "For a period of 24 months, recipient agrees not to engage in competing enterprise software business worldwide.\n"
        )
        file_bytes = sample_contract.encode("utf-8")
        
        files = {
            "file": ("sample_cloud_agreement.txt", io.BytesIO(file_bytes), "text/plain")
        }
        data = {
            "title": "Automated Test Cloud Agreement",
            "contract_type": "Master Services Agreement",
            "counterparty": "CloudProvider Inc.",
            "department": "Engineering",
            "value": "2500000",
            "currency": "INR",
            "start_date": "2026-11-01",
            "expiry_date": "2027-10-31",
            "governing_law": "Laws of India"
        }

        # Upload
        upload_res = await ac.post("/api/v1/contracts/upload", headers=auth_headers, data=data, files=files)
        assert upload_res.status_code == 200, upload_res.text
        contract_data = upload_res.json()
        
        assert contract_data["title"] == "Automated Test Cloud Agreement"
        assert contract_data["counterparty"] == "CloudProvider Inc."
        assert len(contract_data["clauses"]) > 0
        assert len(contract_data["risks"]) > 0
        assert contract_data["composite_risk_score"] > 0
        
        # Verify contract is retrievable via GET /api/v1/contracts/{id}
        contract_id = contract_data["id"]
        detail_res = await ac.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["id"] == contract_id
        assert detail["status"] == "UNDER_REVIEW"

        # Verify Q&A endpoint
        with patch("app.services.ai.contract_qa.default_gemini_provider.is_configured", return_value=True), \
             patch("app.services.ai.contract_qa.default_gemini_provider.generate_content", return_value="Under Section 11.0, liability is capped at fees paid."):
            qa_res = await ac.post(f"/api/v1/contracts/{contract_id}/qa", headers=auth_headers, json={"question": "What is the limitation of liability?"})
            assert qa_res.status_code == 200
            qa_data = qa_res.json()
            assert "answer" in qa_data
            assert "citation" in qa_data
            assert "sources" in qa_data
