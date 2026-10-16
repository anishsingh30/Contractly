from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class ContractNote(Base, TimestampedModel):
    __tablename__ = "contract_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    author_name = Column(String(255), nullable=False)

    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    reminder_date = Column(String(20), nullable=True)  # Optional YYYY-MM-DD reminder
    is_important = Column(Boolean, default=False)

    # Optional associations
    calendar_event_id = Column(String(36), ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True)
    obligation_id = Column(String(36), ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    contract = relationship("Contract", backref="notes")
    author = relationship("User", backref="contract_notes")
