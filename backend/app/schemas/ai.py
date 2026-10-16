from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ContractQARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="User question about the contract")

class ContractQASource(BaseModel):
    clause_id: Optional[str] = None
    section: Optional[str] = None
    title: Optional[str] = None
    page: Optional[int] = 1
    excerpt: Optional[str] = None

class ContractQAResponse(BaseModel):
    answer: str
    confidence: str = "grounded"
    sources: List[ContractQASource] = []
    citation: Optional[str] = None

class GeneralChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Educational query about CLM, terminology, or workflows")
    history: Optional[List[Dict[str, str]]] = Field(default=None, description="Optional previous message turns")

class GeneralChatResponse(BaseModel):
    reply: str
    disclaimer: str = "This is an informational explanation and does not constitute legal advice."
