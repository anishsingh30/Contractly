import pytest
import io
import zipfile
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from fastapi import HTTPException
from app.core.upload_validator import validate_file_signature
from app.services.parsing.pdf_parser import extract_text_from_pdf, MAX_PDF_PAGES
from app.services.parsing.docx_parser import extract_text_from_docx
from app.services.ai.redline_service import (
    generate_contract_redlines,
    generate_heuristic_redlines,
    sanitize_redline_text,
    STANDARD_PLAYBOOK_BENCHMARKS
)
from app.models.contract import Contract, ContractClause
from app.models.organization import Organization
from app.models.user import User


def test_pdf_page_limit_enforced():
    """Verify that PDFs exceeding MAX_PDF_PAGES raise ValueError to prevent page-flood DoS."""
    import pymupdf as fitz
    doc = fitz.open()
    # Add 251 blank pages
    for _ in range(MAX_PDF_PAGES + 1):
        doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    with pytest.raises(ValueError, match="exceeds maximum allowable limit"):
        extract_text_from_pdf(pdf_bytes)


def test_zip_slip_rejection():
    """Verify that archives with directory traversal paths in entry names are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("../../etc/passwd", "malicious_content")
    bad_docx = buf.getvalue()

    with pytest.raises(HTTPException) as exc_info:
        validate_file_signature(bad_docx, ".docx")
    assert exc_info.value.status_code == 400
    assert "path traversal" in exc_info.value.detail.lower()


def test_decompression_bomb_rejection():
    """Verify that archives with suspicious compression ratios or huge uncompressed size are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", b"0" * (70 * 1024 * 1024))
    bomb_docx = buf.getvalue()

    with pytest.raises(HTTPException) as exc_info:
        validate_file_signature(bomb_docx, ".docx")
    assert exc_info.value.status_code == 413
    assert "decompression bomb" in exc_info.value.detail.lower()


def test_sanitize_redline_text_xss_and_control_chars():
    """Verify that HTML scripts, iframes, and null bytes are thoroughly stripped."""
    dangerous_input = "Approved <script>alert('xss')</script> language\x00 with <iframe src='evil.com'></iframe> terms."
    sanitized = sanitize_redline_text(dangerous_input)
    assert "<script>" not in sanitized
    assert "alert" not in sanitized
    assert "<iframe>" not in sanitized
    assert "\x00" not in sanitized
    assert sanitized == "Approved  language with  terms."


def test_heuristic_redlines_uncapped_liability_coverage():
    """Verify that uncapped liability clauses generate mandatory redline proposals."""
    mock_contract = Contract(
        id="c-liability-test",
        organization_id="org-1",
        title="Vendor Agreement",
        contract_type="MSA",
        counterparty="Cloud Corp"
    )
    mock_clause = ContractClause(
        id="cl-liab-1",
        contract_id="c-liability-test",
        clause_title="Limitation of Liability",
        section_number="8.1",
        category="Liability",
        original_text="Neither party shall have any limit or cap on its liability under this Agreement. Liability shall be uncapped and unlimited."
    )

    proposals = generate_heuristic_redlines(mock_contract, [mock_clause], [])
    assert len(proposals) >= 1
    p = proposals[0]
    assert p["priority"] == "MANDATORY"
    assert "twelve (12) months" in p["suggested_text"]
    assert p["clause_id"] == "cl-liab-1"


def test_heuristic_redlines_unilateral_indemnity_coverage():
    """Verify that unilateral customer indemnification generates recommended redlines."""
    mock_contract = Contract(
        id="c-indemnity-test",
        organization_id="org-1",
        title="Consulting Agreement",
        contract_type="SOW",
        counterparty="Consultant LLC"
    )
    mock_clause = ContractClause(
        id="cl-indem-1",
        contract_id="c-indemnity-test",
        clause_title="Indemnification",
        section_number="9.2",
        category="Indemnification",
        original_text="Customer shall defend, indemnify, and hold harmless Consultant from any third-party claims arising out of this Agreement."
    )

    proposals = generate_heuristic_redlines(mock_contract, [mock_clause], [])
    assert len(proposals) >= 1
    p = proposals[0]
    assert p["priority"] == "RECOMMENDED"
    assert "Each party" in p["suggested_text"]


@pytest.mark.asyncio
async def test_generate_redlines_endpoint_rbac(test_engine):
    """Verify that POST /{id}/generate-redlines requires redlines:manage permission."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from app.core.security import create_access_token, get_password_hash
    from app.models.user import OrganizationMember

    transport = ASGITransport(app=app)
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        org = Organization(id="org-rbac-redline", name="RBAC Test Org", slug="rbac-test-org")
        session.add(org)
        await session.flush()

        emp_user = User(
            id="user-emp-redline",
            email="emp@rbactest.com",
            password_hash=get_password_hash("Pass123!"),
            full_name="Employee Tester",
            is_active=True
        )
        owner_user = User(
            id="user-owner-redline",
            email="owner@rbactest.com",
            password_hash=get_password_hash("Pass123!"),
            full_name="Owner Tester",
            is_active=True
        )
        session.add_all([emp_user, owner_user])
        await session.flush()

        m_emp = OrganizationMember(organization_id=org.id, user_id=emp_user.id, role="EMPLOYEE")
        m_owner = OrganizationMember(organization_id=org.id, user_id=owner_user.id, role="OWNER")
        contract = Contract(
            id="c-rbac-redline-1",
            organization_id=org.id,
            contract_id="CTR-2026-9999",
            title="RBAC Redline Contract",
            contract_type="NDA",
            counterparty="Acme Corp",
            status="UNDER_REVIEW"
        )
        clause = ContractClause(
            id="cl-rbac-1",
            contract_id=contract.id,
            clause_title="Confidentiality",
            section_number="2.1",
            category="Confidentiality",
            original_text="Each party agrees to hold in confidence all proprietary materials.",
            plain_language="All proprietary materials held in confidence.",
            why_it_matters="Protects confidential information."
        )
        session.add_all([m_emp, m_owner, contract, clause])
        await session.commit()

    emp_token = create_access_token(subject=emp_user.id, org_id=org.id, role="EMPLOYEE")
    owner_token = create_access_token(subject=owner_user.id, org_id=org.id, role="OWNER")

    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Employee without redlines:manage must be rejected with 403 Forbidden
        emp_res = await ac.post(f"/api/v1/contracts/{contract.id}/generate-redlines", headers=emp_headers)
        assert emp_res.status_code == 403

        # Owner with redlines:manage is authorized (200 OK)
        owner_res = await ac.post(f"/api/v1/contracts/{contract.id}/generate-redlines", headers=owner_headers)
        assert owner_res.status_code == 200
        res_data = owner_res.json()
        assert isinstance(res_data, list)
        assert len(res_data) >= 1

