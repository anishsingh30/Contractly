from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class CalendarEvent(Base, TimestampedModel):
    __tablename__ = "calendar_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=True, index=True)
    obligation_id = Column(String(36), ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Event Categories (11 required types):
    # CONTRACT_EFFECTIVE, CONTRACT_EXPIRY, CONTRACT_RENEWAL, RENEWAL_NOTICE,
    # TERMINATION_NOTICE, CONTRACT_TERMINATION, OBLIGATION_DUE, PAYMENT_DEADLINE,
    # APPROVAL_DEADLINE, SIGNATURE_DEADLINE, CUSTOM_DATE
    event_type = Column(String(50), nullable=False, default="CUSTOM_DATE", index=True)
    
    event_date = Column(String(20), nullable=False, index=True)  # YYYY-MM-DD
    priority = Column(String(20), nullable=False, default="IMPORTANT")  # CRITICAL, IMPORTANT, INFORMATIONAL
    status = Column(String(20), nullable=False, default="UPCOMING")  # UPCOMING, DUE_SOON, OVERDUE, COMPLETED, CANCELLED
    
    # Source & Verification:
    # CONTRACT_LIFECYCLE, OBLIGATION, INTELLIGENCE, USER_CUSTOM, CALCULATED_REMINDER
    source_type = Column(String(50), nullable=False, default="USER_CUSTOM")
    is_verified = Column(Boolean, default=True)  # False if extracted by doc intelligence needing review
    is_important = Column(Boolean, default=False)  # User explicit Mark as Important
    
    created_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    contract = relationship("Contract", backref="calendar_events")
    obligation = relationship("Obligation", backref="calendar_events")
