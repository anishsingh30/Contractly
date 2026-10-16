import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.contract import Contract, ContractVersion, ContractClause, ContractRisk
from app.models.obligation import Obligation
from app.services.intelligence.parser import parse_document
from app.services.intelligence.normalizer import normalize_contract_text
from app.services.intelligence.section_detector import detect_sections
from app.services.intelligence.clause_extractor import extract_clauses
from app.services.intelligence.metadata_extractor import extract_parties, extract_candidate_dates, detect_renewal_metadata
from app.services.intelligence.obligation_detector import extract_obligation_candidates
from app.services.intelligence.risk_detector import detect_contract_risks, compute_explainable_risk_score


async def run_intelligence_pipeline(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    contract: Contract,
    version: ContractVersion,
    db: AsyncSession,
    auto_commit: bool = True
) -> Dict[str, Any]:
    """
    Executes the deterministic contract intelligence pipeline:
    1. Parse raw document (PDF, DOCX, TXT)
    2. Normalize text (preserve paragraph and section boundaries)
    3. Detect sections and segment document
    4. Extract structured clauses with controlled taxonomy
    5. Extract parties, candidate dates, and renewal metadata
    6. Extract actionable obligation candidates
    7. Detect deterministic risks & compute explainable score
    8. Persist results idempotently (replacing previous version clauses/risks)
    9. Update processing states and contract metrics
    """
    contract = await db.merge(contract)
    version = await db.merge(version)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    version.parser_status = "PARSING"
    version.processing_started_at = now_iso
    await db.flush()

    try:
        # Step 1: Parse Document
        parse_result = parse_document(file_bytes, filename, mime_type)
        raw_text = parse_result["raw_text"]
        pages = parse_result.get("pages", [])

        version.raw_text = raw_text
        version.page_count = parse_result.get("page_count", 1)
        version.char_count = parse_result.get("char_count", len(raw_text))
        version.word_count = parse_result.get("word_count", len(raw_text.split()))

        # Step 2: Normalize Text
        version.parser_status = "ANALYZING"
        await db.flush()

        normalized_text = normalize_contract_text(raw_text)
        version.normalized_text = normalized_text

        # Step 3: Detect Sections
        sections = detect_sections(normalized_text, pages=pages)

        # Step 4: Extract Clauses
        extracted_clauses = extract_clauses(sections, contract_id=contract.id, version_id=version.id)

        # Step 5: Extract Parties, Dates & Renewal Metadata
        parties = extract_parties(normalized_text)
        candidate_dates = extract_candidate_dates(sections)
        renewal_meta = detect_renewal_metadata(normalized_text)

        # Update contract renewal flags if not manually set
        if renewal_meta["auto_renew"] and not contract.auto_renew:
            contract.auto_renew = True
        if renewal_meta.get("renewal_notice_days"):
            contract.renewal_notice_days = renewal_meta["renewal_notice_days"]
        if renewal_meta.get("termination_notice_days"):
            contract.termination_notice_days = renewal_meta["termination_notice_days"]

        # Step 6: Extract Obligations
        obligation_candidates = extract_obligation_candidates(extracted_clauses)

        # Step 7: Detect Risks & Compute Explainable Risk Score
        detected_risks = detect_contract_risks(extracted_clauses)
        score_info = compute_explainable_risk_score(detected_risks)

        contract.composite_risk_score = score_info["composite_risk_score"]
        contract.risk_level = score_info["risk_level"]

        # Step 8: Idempotent Database Persistence
        # Purge existing clauses and risks for this specific version to avoid duplication on reprocessing
        await db.execute(
            delete(ContractClause).where(
                ContractClause.contract_id == contract.id,
                ContractClause.contract_version_id == version.id
            )
        )
        await db.execute(
            delete(ContractRisk).where(
                ContractRisk.contract_id == contract.id,
                ContractRisk.contract_version_id == version.id
            )
        )
        await db.flush()

        # Insert new clauses
        saved_clauses: List[ContractClause] = []
        clause_id_map: Dict[str, str] = {}  # section_number -> clause.id

        for c_data in extracted_clauses:
            clause_obj = ContractClause(
                contract_id=contract.id,
                contract_version_id=version.id,
                clause_title=c_data["clause_title"],
                section_number=c_data["section_number"],
                original_text=c_data["original_text"],
                plain_language=c_data["plain_language"],
                why_it_matters=c_data["why_it_matters"],
                potential_concern=c_data.get("potential_concern"),
                suggested_action=c_data.get("suggested_action"),
                risk_level=c_data["risk_level"],
                category=c_data["category"],
                page_number=c_data.get("page_number", 1),
                position_order=c_data.get("position_order", 0),
                start_pos=c_data.get("start_pos"),
                end_pos=c_data.get("end_pos")
            )
            db.add(clause_obj)
            saved_clauses.append(clause_obj)

        await db.flush()

        for c_obj in saved_clauses:
            clause_id_map[c_obj.section_number] = c_obj.id

        # Insert risks with mapped clause IDs
        for r_data in detected_risks:
            mapped_clause_id = clause_id_map.get(r_data.get("section_number"))
            risk_obj = ContractRisk(
                contract_id=contract.id,
                contract_version_id=version.id,
                clause_id=mapped_clause_id,
                section_number=r_data.get("section_number"),
                category=r_data.get("category"),
                severity=r_data["severity"],
                risk_title=r_data["risk_title"],
                potential_impact=r_data["potential_impact"],
                remedy_recommendation=r_data["remedy_recommendation"],
                status=r_data["status"]
            )
            db.add(risk_obj)

        # Link obligations to clauses where applicable
        for ob_data in obligation_candidates[:5]:  # create top actionable obligations if none exist
            existing_obs = await db.execute(
                select(Obligation).where(
                    Obligation.contract_id == contract.id,
                    Obligation.title == ob_data["title"]
                )
            )
            if not existing_obs.scalars().first():
                ob_obj = Obligation(
                    contract_id=contract.id,
                    contract_version_id=version.id,
                    clause_id=clause_id_map.get(ob_data.get("section_number")),
                    obligor_party=ob_data.get("responsible_party", "Contract Party"),
                    obligee_party=contract.counterparty or "Company",
                    title=ob_data["title"],
                    description=ob_data["source_text"],
                    due_date=contract.expiry_date,
                    frequency=ob_data.get("frequency", "ONE_TIME"),
                    source_text=ob_data.get("source_text"),
                    status="UPCOMING"
                )
                db.add(ob_obj)

        # Step 9: Finalize Processing State
        version.parser_status = "COMPLETED"
        version.processing_completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        version.processing_error = None

        if auto_commit:
            await db.commit()
            await db.refresh(version)
            await db.refresh(contract)

        return {
            "status": "COMPLETED",
            "page_count": version.page_count,
            "char_count": version.char_count,
            "word_count": version.word_count,
            "sections_count": len(sections),
            "clauses_count": len(saved_clauses),
            "risks_count": len(detected_risks),
            "obligations_count": len(obligation_candidates),
            "parties": parties,
            "candidate_dates": candidate_dates,
            "risk_score_breakdown": score_info
        }

    except Exception as exc:
        version.parser_status = "FAILED"
        version.processing_completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        version.processing_error = f"Document processing failed: {str(exc)[:250]}"
        if auto_commit:
            await db.commit()
            await db.refresh(version)
        raise
