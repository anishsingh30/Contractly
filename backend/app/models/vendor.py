from sqlalchemy import Column, String, Numeric, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class Vendor(Base, TimestampedModel):
    __tablename__ = "vendors"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    contract_count = Column(Integer, default=0)
    total_contract_value = Column(Numeric(15, 2), default=0.0)
    risk_rating = Column(String(20), default="LOW")
    compliance_rating = Column(Integer, default=100)
    sla_performance = Column(String(100), default="100% Target Met")
    open_obligations = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    soc2_certified = Column(Boolean, default=False)
    gdpr_compliant = Column(Boolean, default=False)

    organization = relationship("Organization", back_populates="vendors")
