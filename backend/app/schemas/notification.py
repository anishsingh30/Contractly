from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Any
from datetime import datetime

class NotificationResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    contract_id: Optional[str] = None
    obligation_id: Optional[str] = None
    calendar_event_id: Optional[str] = None
    event_type: str
    priority: str
    title: str
    message: str
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivery_channel: str
    delivery_status: str
    is_read: bool
    read_at: Optional[datetime] = None
    retry_count: int = 0
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None

class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    unread_count: int
    unread_messages_count: int = 0
    total_count: int

class UserNotificationPreferenceUpdate(BaseModel):
    email_notifications_enabled: Optional[bool] = None
    renewal_reminders: Optional[bool] = None
    notice_deadline_reminders: Optional[bool] = None
    obligation_reminders: Optional[bool] = None
    approval_reminders: Optional[bool] = None
    critical_events_enabled: Optional[bool] = None
    reminder_intervals: Optional[List[int]] = None
    daily_notification_limit: Optional[int] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    preferred_notification_email: Optional[EmailStr] = None

    @field_validator("preferred_notification_email", mode="before")
    @classmethod
    def clean_preferred_email(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

class UserNotificationPreferenceResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    email_notifications_enabled: bool
    renewal_reminders: bool
    notice_deadline_reminders: bool
    obligation_reminders: bool
    approval_reminders: bool
    critical_events_enabled: bool
    reminder_intervals: List[int]
    daily_notification_limit: int
    quiet_hours_enabled: bool
    quiet_hours_start: str
    quiet_hours_end: str
    preferred_notification_email: Optional[str] = None
    email_service_enabled: bool = False
    email_provider_status: str = "Disabled"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class TestEmailRequest(BaseModel):
    recipient_email: Optional[EmailStr] = None

    @field_validator("recipient_email", mode="before")
    @classmethod
    def clean_recipient_email(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

class EvaluateWorkerResponse(BaseModel):
    evaluated_contracts: int
    evaluated_obligations: int
    notifications_created: int
    skipped_dedup: int
    errors: int
