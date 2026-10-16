from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class PlaybookRule(Base, TimestampedModel):
    __tablename__ = "playbook_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    preferred_standard = Column(Text, nullable=False)
    fallback_acceptable = Column(Text, nullable=False)
    prohibited_terms = Column(Text, default="")  # comma-separated list
    negotiation_guidance = Column(Text, nullable=False)

    organization = relationship("Organization", back_populates="playbook_rules")
