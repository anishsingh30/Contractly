from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class ObligationEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    obligation_id: str
    file_name: str
    uploaded_by: str
    status: str = "UNDER_REVIEW"
    created_at: datetime

class ObligationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str
    obligor_party: str
    obligee_party: str
    title: str
    description: str
    due_date: Optional[str] = None
    frequency: str = "ONE_TIME"
    penalty_clause: Optional[str] = None
    responsible_owner: str = "Contract Manager"
    status: str = "UPCOMING"
    created_at: datetime
    evidence: List[ObligationEvidenceResponse] = []

class ObligationCreateRequest(BaseModel):
    obligor_party: str
    obligee_party: str
    title: str
    description: str
    due_date: Optional[str] = None
    frequency: str = "ONE_TIME"
    penalty_clause: Optional[str] = None
    responsible_owner: str = "Contract Manager"
    status: str = "UPCOMING"

class ObligationStatusUpdateRequest(BaseModel):
    status: str
