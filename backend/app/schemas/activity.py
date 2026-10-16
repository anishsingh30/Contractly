from typing import List, Optional
from pydantic import BaseModel, Field

class ActivityItem(BaseModel):
    id: str
    timestamp: str
    formatted_time: str
    actor_email: str
    actor_name: str
    action: str
    action_label: str
    object_type: str
    object_id: str
    item_reference: str
    item_link: Optional[str] = None
    summary: str
    detail: str
    status: str
    scope: str

class ActivityListResponse(BaseModel):
    items: List[ActivityItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    current_scope: str
    can_view_organization_activity: bool
    available_action_types: List[str]

class ActivityDetailResponse(BaseModel):
    id: str
    timestamp: str
    formatted_time: str
    actor_email: str
    actor_name: str
    action: str
    action_label: str
    object_type: str
    object_id: str
    item_reference: str
    item_link: Optional[str] = None
    summary: str
    detail: str
    status: str
    ip_address: Optional[str] = None
    organization_id: Optional[str] = None
