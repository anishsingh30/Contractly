from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class Obligation(Base, TimestampedModel):
    __tablename__ = "obligations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    obligor_party = Column(String(255), nullable=False)
    obligee_party = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    due_date = Column(String(20), nullable=True)
    frequency = Column(String(30), default="ONE_TIME")
    penalty_clause = Column(String(255), nullable=True)
    responsible_owner = Column(String(255), default="Contract Manager")
    clause_id = Column(String(36), nullable=True)
    contract_version_id = Column(String(36), nullable=True)
    source_text = Column(Text, nullable=True)
    status = Column(String(30), default="UPCOMING")  # UPCOMING, DUE_SOON, FULFILLED, OVERDUE, POTENTIAL_NON_COMPLIANCE

    contract = relationship("Contract", back_populates="obligations")
    evidence = relationship("ObligationEvidence", back_populates="obligation", cascade="all, delete-orphan")

class ObligationEvidence(Base, TimestampedModel):
    __tablename__ = "obligation_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    obligation_id = Column(String(36), ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_storage_path = Column(String(500), nullable=False)
    uploaded_by = Column(String(255), default="Current User")
    status = Column(String(30), default="UNDER_REVIEW")

    obligation = relationship("Obligation", back_populates="evidence")
