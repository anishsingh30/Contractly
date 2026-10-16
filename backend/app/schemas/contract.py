from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class ContractClauseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: Optional[str] = None
    contract_version_id: Optional[str] = None
    clause_title: str
    section_number: str
    original_text: str
    plain_language: str
    why_it_matters: str
    potential_concern: Optional[str] = None
    suggested_action: Optional[str] = None
    risk_level: str = "LOW"
    category: str = "General"
    page_number: Optional[int] = 1
    position_order: Optional[int] = 0
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None

class ContractRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: Optional[str] = None
    contract_version_id: Optional[str] = None
    clause_id: Optional[str] = None
    section_number: Optional[str] = None
    category: Optional[str] = None
    severity: str
    risk_title: str
    potential_impact: str
    remedy_recommendation: str
    status: str = "OPEN"

class ContractVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: str
    filename: Optional[str] = None
    file_storage_path: Optional[str] = None
    file_mime_type: str
    file_byte_size: int
    sha256_checksum: str
    page_count: Optional[int] = 1
    char_count: Optional[int] = 0
    word_count: Optional[int] = 0
    parser_status: Optional[str] = "COMPLETED"
    processing_started_at: Optional[str] = None
    processing_completed_at: Optional[str] = None
    processing_error: Optional[str] = None
    change_summary: Optional[str] = None
    created_by: Optional[str] = "System"
    created_at: datetime

class ContractApprovalStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    step_order: int
    role: str
    assigned_user: str
    decision: str = "PENDING"
    decided_at: Optional[str] = None
    comments: Optional[str] = None

class ContractRedlineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: Optional[str] = None
    clause_id: Optional[str] = None
    section_title: str
    original_text: str
    suggested_text: str
    rationale: Optional[str] = None
    status: str = "PENDING"
    author: str
    comment: Optional[str] = None
    created_at: datetime

class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str
    title: str
    contract_type: str
    counterparty: str
    department: str
    owner: str
    value: Optional[float] = None
    currency: str = "INR"
    value_basis: Optional[str] = "NOT_SPECIFIED"
    calculation_explanation: Optional[str] = None
    start_date: Optional[str] = None
    expiry_date: Optional[str] = None
    end_date: Optional[str] = None
    renewal_date: Optional[str] = None
    auto_renew: bool = False
    renewal_notice_days: Optional[int] = 30
    termination_notice_days: Optional[int] = 30
    termination_date: Optional[str] = None
    termination_reason: Optional[str] = None
    status: str
    composite_risk_score: int = 0
    risk_level: str = "LOW"
    version: str = "v1.0"
    governing_law: str = "Laws of India"
    tags: List[str] = []
    created_at: datetime
    clauses: List[ContractClauseResponse] = []
    risks: List[ContractRiskResponse] = []
    approval_steps: List[ContractApprovalStepResponse] = []
    redlines: List[ContractRedlineResponse] = []
    versions: List[ContractVersionResponse] = []

class ApprovalDecisionRequest(BaseModel):
    decision: str  # "APPROVED" or "REJECTED"
    comments: Optional[str] = None

class ContractCreateRequest(BaseModel):
    title: str
    contract_type: str = "Master Services Agreement"
    counterparty: str
    department: str = "Legal"
    value: float = 0.0
    currency: str = "INR"
    start_date: Optional[str] = None
    expiry_date: Optional[str] = None
    end_date: Optional[str] = None
    governing_law: Optional[str] = "Laws of India"

class ContractStatusTransitionRequest(BaseModel):
    status: str
    reason: Optional[str] = None

class ContractTerminationRequest(BaseModel):
    termination_reason: str
    termination_date: Optional[str] = None

class ContractRenewalRequest(BaseModel):
    new_expiry_date: str
    renewal_term_months: Optional[int] = 12
    notes: Optional[str] = None

class ContractRedlineCreateRequest(BaseModel):
    clause_id: Optional[str] = None
    section_title: str
    original_text: str
    suggested_text: str
    rationale: Optional[str] = None

class RedlineStatusUpdateRequest(BaseModel):
    status: str  # "ACCEPTED", "REJECTED", "MODIFIED"

class RedlineCommentRequest(BaseModel):
    comment: str

class NegotiationFindingResponse(BaseModel):
    rule_id: str
    category: str
    status: str  # "Rule Match" | "Potential Negotiation Issue"
    target_clause: Optional[str] = None
    clause_title: Optional[str] = None
    finding_summary: str
    guidance: str
    suggested_action: Optional[str] = None

class ContractLifecycleSummaryResponse(BaseModel):
    current_status: str
    allowed_transitions: List[str]
    health_status: str  # "GOOD" | "NEEDS ATTENTION" | "UPCOMING" | "POTENTIAL PROBLEM" | "Not enough information"
    health_reason: str
    renewal_status: str  # "UPCOMING RENEWAL" | "NOTICE WINDOW" | "EXPIRING" | "EXPIRED" | "Renewal information unavailable"
    days_until_expiry: Optional[int] = None
    in_notice_window: bool
    open_risks_count: int
    overdue_obligations_count: int
    pending_approval_steps_count: int

class ExtractedPartyResponse(BaseModel):
    name: str
    role: str
    source: Optional[str] = None

class ExtractedDateCandidateResponse(BaseModel):
    date_type: str
    date_str: str
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    excerpt: Optional[str] = None

class ObligationCandidateResponse(BaseModel):
    title: str
    clause_id: Optional[str] = None
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    source_text: str
    responsible_party: str
    category: str
    frequency: str
    confidence: str

class RiskScoreBreakdownResponse(BaseModel):
    composite_risk_score: int
    risk_level: str
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    explanation: str

class ContractIntelligenceResponse(BaseModel):
    contract_id: str
    version_id: Optional[str] = None
    parser_status: str
    page_count: int
    char_count: int
    word_count: int
    processing_started_at: Optional[str] = None
    processing_completed_at: Optional[str] = None
    processing_error: Optional[str] = None
    parties: List[ExtractedPartyResponse] = []
    candidate_dates: List[ExtractedDateCandidateResponse] = []
    renewal_info: dict = {}
    clauses: List[ContractClauseResponse] = []
    risks: List[ContractRiskResponse] = []
    obligation_candidates: List[ObligationCandidateResponse] = []
    risk_score_breakdown: RiskScoreBreakdownResponse

class ContractMetadataResponse(BaseModel):
    contract_id: str
    title: str
    counterparty: str
    status: str
    current_version: str
    versions: List[ContractVersionResponse]
    total_clauses: int
    total_risks: int
    total_obligations: int


