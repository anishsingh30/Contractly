from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class ContractNoteCreate(BaseModel):
    title: Optional[str] = None
    content: str
    reminder_date: Optional[str] = None  # YYYY-MM-DD
    is_important: bool = False
    calendar_event_id: Optional[str] = None
    obligation_id: Optional[str] = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Note content cannot be empty")
        return v.strip()

class ContractNoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    reminder_date: Optional[str] = None
    is_important: Optional[bool] = None

class ContractNoteResponse(BaseModel):
    id: str
    organization_id: str
    contract_id: str
    author_user_id: str
    author_name: str
    title: Optional[str] = None
    content: str
    reminder_date: Optional[str] = None
    is_important: bool = False
    calendar_event_id: Optional[str] = None
    obligation_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
