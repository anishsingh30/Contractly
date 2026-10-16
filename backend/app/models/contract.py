from sqlalchemy import Column, String, Numeric, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class Contract(Base, TimestampedModel):
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(String(50), nullable=False, index=True)  # e.g., CTR-2026-0842
    title = Column(String(500), nullable=False)
    contract_type = Column(String(100), nullable=False)
    counterparty = Column(String(255), nullable=False)
    department = Column(String(100), default="Legal")
    owner = Column(String(255), default="Legal Manager")
    value = Column(Numeric(15, 2), default=0.0)
    currency = Column(String(3), default="INR")
    start_date = Column(String(20), nullable=True)
    expiry_date = Column(String(20), nullable=True)
    renewal_date = Column(String(20), nullable=True)
    auto_renew = Column(Boolean, default=False)
    renewal_notice_days = Column(Integer, default=30)
    termination_notice_days = Column(Integer, default=30)
    termination_date = Column(String(20), nullable=True)
    termination_reason = Column(Text, nullable=True)
    status = Column(String(50), default="UNDER_REVIEW", nullable=False, index=True)
    composite_risk_score = Column(Integer, default=0)
    risk_level = Column(String(20), default="LOW")
    version = Column(String(20), default="v1.0")
    governing_law = Column(String(255), default="Laws of India")
    tags = Column(String(500), default="")  # comma-separated

    # Relationships
    organization = relationship("Organization", back_populates="contracts")
    versions = relationship("ContractVersion", back_populates="contract", cascade="all, delete-orphan", order_by="ContractVersion.created_at.desc()")
    clauses = relationship("ContractClause", back_populates="contract", cascade="all, delete-orphan")
    risks = relationship("ContractRisk", back_populates="contract", cascade="all, delete-orphan")
    obligations = relationship("Obligation", back_populates="contract", cascade="all, delete-orphan")
    approval_steps = relationship("ContractApprovalStep", back_populates="contract", cascade="all, delete-orphan", order_by="ContractApprovalStep.step_order")
    redlines = relationship("ContractRedline", back_populates="contract", cascade="all, delete-orphan")

class ContractVersion(Base, TimestampedModel):
    __tablename__ = "contract_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(String(20), nullable=False, default="v1.0")
    filename = Column(String(255), nullable=True)
    file_storage_path = Column(String(500), nullable=False)
    file_mime_type = Column(String(100), nullable=False)
    file_byte_size = Column(Integer, nullable=False)
    sha256_checksum = Column(String(64), nullable=False)
    page_count = Column(Integer, nullable=True, default=1)
    char_count = Column(Integer, nullable=True, default=0)
    word_count = Column(Integer, nullable=True, default=0)
    raw_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    parser_status = Column(String(50), default="COMPLETED")  # UPLOADED, PARSING, ANALYZING, COMPLETED, FAILED
    processing_started_at = Column(String(50), nullable=True)
    processing_completed_at = Column(String(50), nullable=True)
    processing_error = Column(Text, nullable=True)
    change_summary = Column(Text, nullable=True)
    created_by = Column(String(255), default="System")

    contract = relationship("Contract", back_populates="versions")

class ContractClause(Base, TimestampedModel):
    __tablename__ = "contract_clauses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_version_id = Column(String(36), nullable=True)
    clause_title = Column(String(255), nullable=False)
    section_number = Column(String(50), default="Section 1.0")
    original_text = Column(Text, nullable=False)
    plain_language = Column(Text, nullable=False)
    why_it_matters = Column(Text, nullable=False)
    potential_concern = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    risk_level = Column(String(20), default="LOW")
    category = Column(String(100), default="General")
    page_number = Column(Integer, nullable=True)
    position_order = Column(Integer, nullable=True, default=0)
    start_pos = Column(Integer, nullable=True)
    end_pos = Column(Integer, nullable=True)

    contract = relationship("Contract", back_populates="clauses")

class ContractRisk(Base, TimestampedModel):
    __tablename__ = "contract_risks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_version_id = Column(String(36), nullable=True)
    clause_id = Column(String(36), nullable=True)
    section_number = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    severity = Column(String(20), nullable=False, default="LOW")
    risk_title = Column(String(255), nullable=False)
    potential_impact = Column(Text, nullable=False)
    remedy_recommendation = Column(Text, nullable=False)
    status = Column(String(30), default="OPEN")

    contract = relationship("Contract", back_populates="risks")

class ContractApprovalStep(Base, TimestampedModel):
    __tablename__ = "contract_approval_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False, default=1)
    role = Column(String(100), nullable=False)
    assigned_user = Column(String(255), nullable=False)
    decision = Column(String(20), default="PENDING")  # PENDING, APPROVED, REJECTED
    decided_at = Column(String(50), nullable=True)
    comments = Column(Text, nullable=True)

    contract = relationship("Contract", back_populates="approval_steps")

class ContractRedline(Base, TimestampedModel):
    __tablename__ = "contract_redlines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    clause_id = Column(String(36), nullable=True)
    section_title = Column(String(255), nullable=False)
    original_text = Column(Text, nullable=False)
    suggested_text = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(String(20), default="PENDING", index=True)  # PENDING, ACCEPTED, REJECTED, MODIFIED
    author = Column(String(255), nullable=False)
    comment = Column(Text, nullable=True)

    contract = relationship("Contract", back_populates="redlines")

