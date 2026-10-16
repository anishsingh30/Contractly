from sqlalchemy import Column, String, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class Organization(Base, TimestampedModel):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    account_type = Column(String(30), nullable=False, default="BUSINESS")  # INDIVIDUAL, PERSONAL, BUSINESS, ENTERPRISE, LEGAL_PROFESSIONAL
    subscription_tier = Column(String(50), default="ENTERPRISE")
    storage_quota_bytes = Column(BigInteger, default=10737418240)  # 10 GB

    # Relationships
    departments = relationship("Department", back_populates="organization", cascade="all, delete-orphan")
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    contracts = relationship("Contract", back_populates="organization", cascade="all, delete-orphan")
    vendors = relationship("Vendor", back_populates="organization", cascade="all, delete-orphan")
    playbook_rules = relationship("PlaybookRule", back_populates="organization", cascade="all, delete-orphan")

    @property
    def is_demo(self) -> bool:
        """
        Determines whether this organization is designated as a demonstration workspace.
        Uses stable internal identifier/slug without modifying database schema.
        """
        slug_clean = (self.slug or "").lower().strip()
        name_clean = (self.name or "").lower().strip()
        return slug_clean == "northstar-tech" or "demo" in slug_clean or "demo" in name_clean

class Department(Base, TimestampedModel):
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    budget_currency = Column(String(3), default="INR")

    # Relationships
    organization = relationship("Organization", back_populates="departments")
