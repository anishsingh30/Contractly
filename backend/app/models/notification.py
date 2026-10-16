from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utc_now

class Notification(Base, TimestampedModel):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    obligation_id = Column(String(36), ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True)
    calendar_event_id = Column(String(36), ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True)

    event_type = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False, default="IMPORTANT")  # CRITICAL, IMPORTANT, INFORMATIONAL
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    scheduled_at = Column(DateTime, default=utc_now, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    delivery_channel = Column(String(20), default="IN_APP")  # IN_APP, EMAIL, BOTH
    delivery_status = Column(String(20), default="SENT")  # PENDING, SENT, FAILED, SUPPRESSED
    
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)

    provider_message_id = Column(String(255), nullable=True)
    retry_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    # Deduplication key enforces that the same event reminder (e.g. 30-day renewal notice)
    # is never sent multiple times across scheduler runs.
    deduplication_key = Column(String(255), nullable=True, unique=True, index=True)

    # Relationships
    contract = relationship("Contract", backref="notifications")
    user = relationship("User", backref="notifications")


class UserNotificationPreference(Base, TimestampedModel):
    __tablename__ = "user_notification_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    email_notifications_enabled = Column(Boolean, default=False)
    renewal_reminders = Column(Boolean, default=True)
    notice_deadline_reminders = Column(Boolean, default=True)
    obligation_reminders = Column(Boolean, default=True)
    approval_reminders = Column(Boolean, default=True)
    critical_events_enabled = Column(Boolean, default=True)

    # JSON list of days before deadline e.g. "[30, 7, 1]"
    reminder_intervals_json = Column(String(255), default="[30, 7, 1]")
    daily_notification_limit = Column(Integer, default=10)

    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(10), default="22:00")
    quiet_hours_end = Column(String(10), default="08:00")

    preferred_notification_email = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user_preference"),
    )

    user = relationship("User", backref="notification_preferences")
