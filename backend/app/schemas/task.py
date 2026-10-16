from pydantic import BaseModel
from typing import Optional, List

class ThingToDoItem(BaseModel):
    id: str
    task_type: str  # VERIFY_DATE, REVIEW_RENEWAL, SUBMIT_EVIDENCE, COMPLETE_APPROVAL, REVIEW_SIGNATURE, RESOLVE_OVERDUE_OBLIGATION, CONFIRM_NOTICE_DEADLINE
    title: str
    contract_id: Optional[str] = None
    contract_title: Optional[str] = None
    counterparty: Optional[str] = None
    due_date: Optional[str] = None
    priority: str  # CRITICAL, IMPORTANT, INFORMATIONAL
    status: str    # PENDING, DUE_SOON, OVERDUE, IN_REVIEW
    responsible_role: Optional[str] = None
    reason: str
    action_type: str
    target_id: Optional[str] = None

class ThingsToDoListResponse(BaseModel):
    items: List[ThingToDoItem]
    total_count: int
    critical_count: int
    important_count: int
    distinct_contracts_count: int = 0
