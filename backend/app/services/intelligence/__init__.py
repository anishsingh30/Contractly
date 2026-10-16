"""
Contractly Contract Intelligence Engine
Deterministic Document Ingestion, Normalization, Segmentation & Intelligence Extraction
"""
from app.services.intelligence.parser import parse_document
from app.services.intelligence.normalizer import normalize_contract_text
from app.services.intelligence.section_detector import detect_sections
from app.services.intelligence.clause_extractor import extract_clauses, CLAUSE_CATEGORIES
from app.services.intelligence.metadata_extractor import extract_parties, extract_candidate_dates
from app.services.intelligence.obligation_detector import extract_obligation_candidates
from app.services.intelligence.risk_detector import detect_contract_risks, compute_explainable_risk_score
from app.services.intelligence.financial_extractor import extract_contract_financials
from app.services.intelligence.pipeline import run_intelligence_pipeline

__all__ = [
    "parse_document",
    "normalize_contract_text",
    "detect_sections",
    "extract_clauses",
    "CLAUSE_CATEGORIES",
    "extract_parties",
    "extract_candidate_dates",
    "extract_contract_financials",
    "extract_obligation_candidates",
    "detect_contract_risks",
    "compute_explainable_risk_score",
    "run_intelligence_pipeline",
]
