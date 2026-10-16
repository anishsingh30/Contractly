from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class CalendarEventCreate(BaseModel):
    contract_id: Optional[str] = None
    obligation_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str = "CUSTOM_DATE"
    event_date: str  # YYYY-MM-DD
    priority: str = "IMPORTANT"  # CRITICAL, IMPORTANT, INFORMATIONAL
    is_important: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Event title cannot be empty")
        return v.strip()

    @field_validator("event_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError("Invalid event_date format; expected YYYY-MM-DD")
        return v.strip()

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None  # UPCOMING, DUE_SOON, OVERDUE, COMPLETED, CANCELLED
    is_verified: Optional[bool] = None
    is_important: Optional[bool] = None

class CalendarEventResponse(BaseModel):
    id: str
    organization_id: str
    contract_id: Optional[str] = None
    contract_title: Optional[str] = None
    counterparty: Optional[str] = None
    obligation_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str
    event_date: str
    priority: str
    status: str
    source_type: str
    is_verified: bool
    is_important: bool
    is_custom: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
