from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class PlaybookRuleCreateRequest(BaseModel):
    category: str
    preferred_standard: str
    fallback_acceptable: str
    prohibited_terms: List[str] = []
    negotiation_guidance: str

class PlaybookRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    category: str
    preferred_standard: str
    fallback_acceptable: str
    prohibited_terms: List[str] = []
    negotiation_guidance: str
    created_at: datetime
