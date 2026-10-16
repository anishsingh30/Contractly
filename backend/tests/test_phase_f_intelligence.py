import io
import uuid
import pytest
import pymupdf as fitz
from docx import Document
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractVersion, ContractClause, ContractRisk
from app.core.security import get_password_hash, create_access_token
from app.services.intelligence.parser import parse_pdf, parse_docx, parse_document
from app.services.intelligence.normalizer import normalize_contract_text
from app.services.intelligence.section_detector import detect_sections
from app.services.intelligence.clause_extractor import classify_clause_category, extract_clauses, CLAUSE_CATEGORIES
from app.services.intelligence.metadata_extractor import extract_parties, extract_candidate_dates
from app.services.intelligence.obligation_detector import extract_obligation_candidates
from app.services.intelligence.risk_detector import detect_contract_risks, compute_explainable_risk_score
from app.services.intelligence.pipeline import run_intelligence_pipeline


def generate_synthetic_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def generate_synthetic_docx(paragraphs: list) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


SAMPLE_CONTRACT_TEXT = """
MASTER SERVICES AGREEMENT

This Master Services Agreement is entered into between Acme Global Solutions Private Limited and CyberShield Systems Inc.

1. Definitions
All capitalized terms shall have the meanings ascribed to them in this Agreement.

2. Scope of Services
CyberShield Systems Inc. will provide cybersecurity monitoring and threat response deliverables.

3. Payment Terms
Customer shall pay all undisputed invoices within thirty (30) days from receipt of invoice.

4. Term and Termination
This Agreement commences on 2026-11-01 and shall expire on 2027-10-31. Either party may terminate for convenience upon sixty (60) days advance written notice.

5. Limitation of Liability
Neither party's aggregate liability under this Agreement shall exceed the total fees paid in the twelve (12) months preceding the claim. However, service provider liability shall remain uncapped with respect to confidentiality breaches.

6. Non-Compete and Restrictive Covenants
For a period of 24 months post-termination, receiving party agrees not to engage in competing enterprise cybersecurity software worldwide.

7. Governing Law and Dispute Resolution
This Agreement shall be governed by the laws of India.
"""


def test_pdf_text_extraction():
    pdf_bytes = generate_synthetic_pdf(SAMPLE_CONTRACT_TEXT)
    res = parse_pdf(pdf_bytes, "test_agreement.pdf")
    assert res["page_count"] == 1
    assert "CyberShield Systems Inc." in res["raw_text"]
    assert "Limitation of Liability" in res["raw_text"]
    assert res["word_count"] > 30


def test_docx_text_extraction():
    paragraphs = [
        "MASTER CLOUD AGREEMENT",
        "Entered into between Apex Corp and Beta Ltd.",
        "Section 1.0 Payment: Payment shall be due net 30 days."
    ]
    docx_bytes = generate_synthetic_docx(paragraphs)
    res = parse_docx(docx_bytes, "test_agreement.docx")
    assert "Apex Corp" in res["raw_text"]
    assert "Payment shall be due net 30 days" in res["raw_text"]
    assert res["word_count"] > 10


def test_text_normalization():
    dirty_text = "Section  1.0 \r\n\r\n\r\n\r\n Title   With   Extra   Spaces\u00a0here.\n\n\nBody."
    cleaned = normalize_contract_text(dirty_text)
    assert "\r" not in cleaned
    assert "\u00a0" not in cleaned
    assert "  " not in cleaned
    assert "\n\n\n" not in cleaned


def test_section_detection_and_unknown_preservation():
    sections = detect_sections(SAMPLE_CONTRACT_TEXT)
    assert len(sections) >= 5
    titles = [s["title"].lower() for s in sections]
    assert any("definitions" in t for t in titles)
    assert any("limitation of liability" in t for t in titles)
    assert any("term and termination" in t for t in titles)

    # Test unknown section preserved
    custom_text = "Section 99.0 Custom Galactic Terms\nParties agree to share asteroid mineral samples."
    custom_secs = detect_sections(custom_text)
    assert len(custom_secs) == 1
    assert "Custom Galactic Terms" in custom_secs[0]["title"]
    assert "asteroid mineral samples" in custom_secs[0]["text"]


def test_clause_taxonomy_categorization():
    assert classify_clause_category("Limitation of Liability", "Aggregate damages shall not exceed fees.") == "LIMITATION_OF_LIABILITY"
    assert classify_clause_category("Payment Terms", "Customer shall pay within 30 days.") == "PAYMENT"
    assert classify_clause_category("Restrictive Covenants", "Party will not engage in competing business.") == "NON_COMPETE"
    assert classify_clause_category("Strange Section", "Random unstructured rambling without legal signals.") == "OTHER"


def test_party_and_date_extraction_no_hallucinations():
    parties = extract_parties(SAMPLE_CONTRACT_TEXT)
    party_names = [p["name"] for p in parties]
    assert any("Acme Global Solutions" in n for n in party_names)
    assert any("CyberShield Systems" in n for n in party_names)

    # Verify no hallucination on empty text
    empty_parties = extract_parties("The weather is nice today in the garden.")
    assert len(empty_parties) == 0

    # Date extraction
    sections = detect_sections(SAMPLE_CONTRACT_TEXT)
    candidate_dates = extract_candidate_dates(sections)
    dates_found = [d["date_str"] for d in candidate_dates]
    assert "2026-11-01" in dates_found
    assert "2027-10-31" in dates_found


def test_obligation_candidate_extraction():
    sections = detect_sections(SAMPLE_CONTRACT_TEXT)
    clauses = extract_clauses(sections, contract_id="CTR-TEST")
    obligations = extract_obligation_candidates(clauses)
    assert len(obligations) > 0
    obligation_texts = [o["source_text"].lower() for o in obligations]
    assert any("shall pay" in t or "shall expire" in t or "agrees not to engage" in t for t in obligation_texts)


def test_deterministic_risk_detection_and_scoring():
    sections = detect_sections(SAMPLE_CONTRACT_TEXT)
    clauses = extract_clauses(sections, contract_id="CTR-TEST")
    risks = detect_contract_risks(clauses)
    assert len(risks) >= 2

    risk_categories = [r["category"] for r in risks]
    assert "LIABILITY" in risk_categories
    assert "NON_COMPETE" in risk_categories

    score_info = compute_explainable_risk_score(risks)
    assert score_info["composite_risk_score"] > 30
    assert score_info["risk_level"] in ("HIGH", "CRITICAL")
    assert "detected risk signal" in score_info["explanation"]


@pytest.mark.asyncio
async def test_intelligence_pipeline_and_reprocessing_idempotence(test_engine):
    """
    Verifies that running pipeline populates database records,
    and reprocessing a version does not duplicate clauses or risks.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"Intel Org {suffix}", slug=f"intel-org-{suffix}")
        session.add(org)
        await session.flush()

        user = User(email=f"intel_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="Ian Intel")
        session.add(user)
        await session.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="LEGAL_MANAGER", status="ACTIVE")
        session.add(member)
        await session.flush()

        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-INT-{suffix}",
            title="Intelligence Test Contract",
            contract_type="Master Services Agreement",
            counterparty="CyberShield Systems Inc.",
            owner=user.full_name,
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        version = ContractVersion(
            contract_id=contract.id,
            version_number="v1.0",
            file_storage_path=f"{org.id}/{contract.contract_id}/v1.0/contract.pdf",
            file_mime_type="application/pdf",
            file_byte_size=1024,
            sha256_checksum="abc123sha",
            created_by=user.full_name
        )
        session.add(version)
        await session.commit()

        contract_id = contract.id
        version_id = version.id

    # Run pipeline first time
    async with TestSessionLocal() as session:
        c_obj = await session.get(Contract, contract_id)
        v_obj = await session.get(ContractVersion, version_id)
        res1 = await run_intelligence_pipeline(
            SAMPLE_CONTRACT_TEXT.encode("utf-8"),
            "contract.txt",
            "text/plain",
            c_obj,
            v_obj,
            session,
            auto_commit=True
        )
        assert res1["clauses_count"] > 3
        initial_clauses_count = res1["clauses_count"]
        initial_risks_count = res1["risks_count"]

    # Verify stored counts
    async with TestSessionLocal() as session:
        from sqlalchemy import func, select
        c_count = (await session.execute(select(func.count(ContractClause.id)).where(ContractClause.contract_id == contract_id))).scalar()
        r_count = (await session.execute(select(func.count(ContractRisk.id)).where(ContractRisk.contract_id == contract_id))).scalar()
        assert c_count == initial_clauses_count
        assert r_count == initial_risks_count

    # Reprocess the same version (Idempotence check)
    async with TestSessionLocal() as session:
        c_obj = await session.get(Contract, contract_id)
        v_obj = await session.get(ContractVersion, version_id)
        res2 = await run_intelligence_pipeline(
            SAMPLE_CONTRACT_TEXT.encode("utf-8"),
            "contract.txt",
            "text/plain",
            c_obj,
            v_obj,
            session,
            auto_commit=True
        )
        assert res2["clauses_count"] == initial_clauses_count

    # Verify counts have NOT doubled
    async with TestSessionLocal() as session:
        c_count_after = (await session.execute(select(func.count(ContractClause.id)).where(ContractClause.contract_id == contract_id))).scalar()
        r_count_after = (await session.execute(select(func.count(ContractRisk.id)).where(ContractRisk.contract_id == contract_id))).scalar()
        assert c_count_after == initial_clauses_count
        assert r_count_after == initial_risks_count


@pytest.mark.asyncio
async def test_intelligence_api_endpoints_tenant_isolated_and_rbac(test_engine):
    """
    Verifies that GET /contracts/{id}/intelligence, /clauses, /risks, /metadata
    are tenant isolated and RBAC protected.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org_a = Organization(name=f"Org A {suffix}", slug=f"org-a-{suffix}")
        org_b = Organization(name=f"Org B {suffix}", slug=f"org-b-{suffix}")
        session.add_all([org_a, org_b])
        await session.flush()

        user_a = User(email=f"usera_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="User A")
        user_b = User(email=f"userb_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="User B")
        session.add_all([user_a, user_b])
        await session.flush()

        member_a = OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role="LEGAL_MANAGER", status="ACTIVE")
        member_b = OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role="LEGAL_MANAGER", status="ACTIVE")
        session.add_all([member_a, member_b])
        await session.commit()

        token_a = create_access_token(subject=user_a.id, org_id=org_a.id, role="LEGAL_MANAGER")
        token_b = create_access_token(subject=user_b.id, org_id=org_b.id, role="LEGAL_MANAGER")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User A uploads a contract with sample text
        files = {"file": ("agreement.txt", io.BytesIO(SAMPLE_CONTRACT_TEXT.encode("utf-8")), "text/plain")}
        data = {
            "title": "Confidential Security Agreement",
            "contract_type": "Master Services Agreement",
            "counterparty": "CyberShield Systems Inc.",
            "value": 100000.0,
            "currency": "INR"
        }
        upload_res = await client.post("/api/v1/contracts/upload", headers={"Authorization": f"Bearer {token_a}"}, files=files, data=data)
        assert upload_res.status_code == 200
        contract_data = upload_res.json()
        contract_id = contract_data["id"]

        # User A accesses intelligence endpoint
        intel_res = await client.get(f"/api/v1/contracts/{contract_id}/intelligence", headers={"Authorization": f"Bearer {token_a}"})
        assert intel_res.status_code == 200
        intel = intel_res.json()
        assert intel["contract_id"] == contract_id
        assert len(intel["clauses"]) > 0
        assert len(intel["risks"]) > 0
        assert intel["risk_score_breakdown"]["composite_risk_score"] > 0
        assert len(intel["parties"]) >= 2

        # User A accesses clauses endpoint
        clauses_res = await client.get(f"/api/v1/contracts/{contract_id}/clauses", headers={"Authorization": f"Bearer {token_a}"})
        assert clauses_res.status_code == 200
        assert len(clauses_res.json()) > 0

        # User A accesses risks endpoint
        risks_res = await client.get(f"/api/v1/contracts/{contract_id}/risks", headers={"Authorization": f"Bearer {token_a}"})
        assert risks_res.status_code == 200
        assert len(risks_res.json()) > 0

        # User A accesses metadata endpoint
        meta_res = await client.get(f"/api/v1/contracts/{contract_id}/metadata", headers={"Authorization": f"Bearer {token_a}"})
        assert meta_res.status_code == 200
        assert meta_res.json()["contract_id"] == contract_data["contract_id"]

        # Cross-Tenant isolation check: User B from Org B cannot access Org A's intelligence
        cross_res = await client.get(f"/api/v1/contracts/{contract_id}/intelligence", headers={"Authorization": f"Bearer {token_b}"})
        assert cross_res.status_code == 404

        # Cross-Tenant isolation check on clauses and risks
        cross_clauses = await client.get(f"/api/v1/contracts/{contract_id}/clauses", headers={"Authorization": f"Bearer {token_b}"})
        assert cross_clauses.status_code == 404

        cross_risks = await client.get(f"/api/v1/contracts/{contract_id}/risks", headers={"Authorization": f"Bearer {token_b}"})
        assert cross_risks.status_code == 404


@pytest.mark.asyncio
async def test_version_isolation(test_engine):
    """
    Verifies that clauses from Version 1 and Version 2 are isolated by contract_version_id
    and querying clauses for v1 does not return v2 clauses.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"Vers Org {suffix}", slug=f"vers-org-{suffix}")
        session.add(org)
        await session.flush()

        user = User(email=f"vers_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="Valerie Version")
        session.add(user)
        await session.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="LEGAL_MANAGER", status="ACTIVE")
        session.add(member)
        await session.flush()

        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-VERS-{suffix}",
            title="Multi-Version Contract",
            contract_type="Master Services Agreement",
            counterparty="Vendor Tech",
            owner=user.full_name
        )
        session.add(contract)
        await session.flush()

        v1 = ContractVersion(
            contract_id=contract.id,
            version_number="v1.0",
            file_storage_path=f"{org.id}/{contract.contract_id}/v1.0/doc.pdf",
            file_mime_type="application/pdf",
            file_byte_size=500,
            sha256_checksum="sha1",
            created_by=user.full_name
        )
        v2 = ContractVersion(
            contract_id=contract.id,
            version_number="v2.0",
            file_storage_path=f"{org.id}/{contract.contract_id}/v2.0/doc.pdf",
            file_mime_type="application/pdf",
            file_byte_size=600,
            sha256_checksum="sha2",
            created_by=user.full_name
        )
        session.add_all([v1, v2])
        await session.commit()

        contract_id = contract.id
        v1_id = v1.id
        v2_id = v2.id

    # Populate v1 with text A
    async with TestSessionLocal() as session:
        c_obj = await session.get(Contract, contract_id)
        v1_obj = await session.get(ContractVersion, v1_id)
        text_v1 = "1. Section Alpha\nThis is version 1 alpha content.\n\n2. Section Beta\nThis is version 1 beta content."
        await run_intelligence_pipeline(text_v1.encode("utf-8"), "v1.txt", "text/plain", c_obj, v1_obj, session, auto_commit=True)

    # Populate v2 with text B
    async with TestSessionLocal() as session:
        c_obj = await session.get(Contract, contract_id)
        v2_obj = await session.get(ContractVersion, v2_id)
        text_v2 = "1. Section Gamma\nThis is version 2 gamma content.\n\n2. Section Delta\nThis is version 2 delta content."
        await run_intelligence_pipeline(text_v2.encode("utf-8"), "v2.txt", "text/plain", c_obj, v2_obj, session, auto_commit=True)

    # Verify that clauses for v1 contain Alpha/Beta and NOT Gamma/Delta
    async with TestSessionLocal() as session:
        from sqlalchemy import select
        v1_clauses = (await session.execute(select(ContractClause).where(ContractClause.contract_version_id == v1_id))).scalars().all()
        v2_clauses = (await session.execute(select(ContractClause).where(ContractClause.contract_version_id == v2_id))).scalars().all()

        v1_titles = [c.clause_title for c in v1_clauses]
        v2_titles = [c.clause_title for c in v2_clauses]

        assert any("Alpha" in t for t in v1_titles)
        assert not any("Gamma" in t for t in v1_titles)
        assert any("Gamma" in t for t in v2_titles)
        assert not any("Alpha" in t for t in v2_titles)


@pytest.mark.asyncio
async def test_processing_failure_handling(test_engine):
    """
    Verifies that corrupt or unsupported file processing gracefully marks parser_status as FAILED
    with a sanitized error message and without crashing unhandled.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"Fail Org {suffix}", slug=f"fail-org-{suffix}")
        session.add(org)
        await session.flush()

        user = User(email=f"fail_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="Frank Fail")
        session.add(user)
        await session.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="LEGAL_MANAGER", status="ACTIVE")
        session.add(member)
        await session.flush()

        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-FAIL-{suffix}",
            title="Corrupt File Contract",
            contract_type="Master Services Agreement",
            counterparty="Vendor Tech",
            owner=user.full_name
        )
        session.add(contract)
        await session.flush()

        version = ContractVersion(
            contract_id=contract.id,
            version_number="v1.0",
            file_storage_path=f"{org.id}/{contract.contract_id}/v1.0/corrupted.pdf",
            file_mime_type="application/pdf",
            file_byte_size=12,
            sha256_checksum="badsha",
            created_by=user.full_name
        )
        session.add(version)
        await session.commit()

        contract_id = contract.id
        version_id = version.id

    async with TestSessionLocal() as session:
        c_obj = await session.get(Contract, contract_id)
        v_obj = await session.get(ContractVersion, version_id)
        # Corrupted PDF bytes
        corrupt_bytes = b"%PDF-1.4 garbage corrupted byte stream not a real pdf"
        with pytest.raises(Exception):
            await run_intelligence_pipeline(corrupt_bytes, "corrupted.pdf", "application/pdf", c_obj, v_obj, session, auto_commit=True)

    # Check that version recorded FAILED status and error string
    async with TestSessionLocal() as session:
        v_updated = await session.get(ContractVersion, version_id)
        assert v_updated.parser_status == "FAILED"
        assert v_updated.processing_error is not None
        assert "Document processing failed" in v_updated.processing_error
