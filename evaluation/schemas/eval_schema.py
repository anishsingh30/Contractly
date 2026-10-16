from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class GroundTruthClause(BaseModel):
    id: str
    section_number: str
    title: str
    category: str
    text_snippet: str
    page_number: int = 1

class GroundTruthRisk(BaseModel):
    category: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    risk_title: str
    section_number: Optional[str] = None

class GroundTruthObligation(BaseModel):
    responsible_party: str
    obligation_text: str
    frequency: str = "ONE_TIME"  # ONE_TIME, MONTHLY, QUARTERLY, ANNUAL, CONDITIONAL
    section_number: Optional[str] = None

class GroundTruthParty(BaseModel):
    name: str
    role: Optional[str] = None

class GroundTruthDate(BaseModel):
    date_type: str  # EFFECTIVE, EXPIRY, RENEWAL, EXECUTION
    raw_text: str
    normalized_iso: Optional[str] = None

class GroundTruthQA(BaseModel):
    question_id: str
    question: str
    expected_answer_facts: List[str]
    expected_source_sections: List[str]
    is_answerable: bool = True
    unacceptable_claims: List[str] = []

class GroundTruthInjection(BaseModel):
    attack_id: str
    malicious_text: str
    attack_objective: str
    forbidden_outputs: List[str]

class EvaluationDocument(BaseModel):
    document_id: str
    title: str
    document_type: str
    raw_text: str
    scenario_tag: str  # e.g., "UNCAPPED_LIABILITY", "AUTOMATIC_RENEWAL"
    clauses: List[GroundTruthClause] = []
    risks: List[GroundTruthRisk] = []
    obligations: List[GroundTruthObligation] = []
    parties: List[GroundTruthParty] = []
    dates: List[GroundTruthDate] = []
    qa_pairs: List[GroundTruthQA] = []
    injections: List[GroundTruthInjection] = []

class MetricScore(BaseModel):
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0

class ClassificationCategoryScore(BaseModel):
    category: str
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

class EvaluationFailure(BaseModel):
    document_id: str
    failure_type: str  # MISSED_CLAUSE, WRONG_CATEGORY, FALSE_RISK, MISSED_RISK, WRONG_SEVERITY, MISSED_OBLIGATION, WRONG_DATE, RETRIEVAL_MISS, WRONG_CITATION, UNSUPPORTED_ANSWER, PROMPT_INJECTION_FAILURE
    input_text: str
    expected: Any
    actual: Any
    detail: str

class EvaluationReport(BaseModel):
    report_id: str
    timestamp: str
    dataset_summary: Dict[str, Any]
    clause_extraction: MetricScore
    clause_classification: Dict[str, Any]  # accuracy, macro_f1, per_category
    risk_detection: Dict[str, Any]         # precision, recall, f1, severity_agreement
    obligation_detection: MetricScore
    metadata_extraction: Dict[str, Any]    # party_accuracy, date_accuracy
    retrieval_performance: Dict[str, Any]  # hit_rate, recall@1, recall@3, recall@5
    qa_grounding: Dict[str, Any]           # fact_support_rate, citation_accuracy, hallucination_rate
    security_performance: Dict[str, Any]   # attack_success_rate
    failures: List[EvaluationFailure]
    decision_gates: Dict[str, Any]         # fine_tuning_decision, vector_db_decision
