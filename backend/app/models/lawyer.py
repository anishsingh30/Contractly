import enum
from typing import List, Optional
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship, validates, backref
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utc_now


class LawyerVerificationStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class MatterStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    MATTER_ACTIVE = "MATTER_ACTIVE"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class MatterPermissionLevel(str, enum.Enum):
    READ_ONLY = "READ_ONLY"
    REDLINE_COLLABORATIVE = "REDLINE_COLLABORATIVE"


class MatterSenderType(str, enum.Enum):
    CLIENT = "CLIENT"
    LAWYER = "LAWYER"


class MatterDeclineReason(str, enum.Enum):
    CONFLICT_OF_INTEREST = "CONFLICT_OF_INTEREST"
    CAPACITY_FULL = "CAPACITY_FULL"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    OTHER = "OTHER"


class LawyerProfile(Base, TimestampedModel):
    """
    Professional advocate profile and chambers registry.
    Safeguard: verification_status defaults strictly to PENDING_REVIEW.
    Registration as a legal professional does not automatically confer verified status.
    """
    __tablename__ = "lawyer_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    bar_council_number = Column(String(100), unique=True, nullable=False, index=True)
    state_bar_council = Column(String(100), nullable=False)
    admitted_jurisdictions = Column(String(500), nullable=False)
    practice_areas = Column(JSON, nullable=False, default=list)
    experience_years = Column(Integer, nullable=False, default=0)
    consultation_fee = Column(String(100), nullable=False, default="")
    consultation_duration_minutes = Column(Integer, default=30, nullable=False)
    bio = Column(Text, nullable=True)
    is_available_for_inquiries = Column(Boolean, default=True, nullable=False)

    # Public professional enhancement fields
    professional_title = Column(String(100), nullable=True)
    qualifications = Column(JSON, nullable=False, default=list)
    languages = Column(JSON, nullable=False, default=list)

    # Publication lifecycle field
    is_published = Column(Boolean, default=False, nullable=False, index=True)

    # Verification lifecycle fields
    verification_status = Column(
        String(30),
        nullable=False,
        default=LawyerVerificationStatus.PENDING_REVIEW.value,
        index=True
    )
    verified_at = Column(DateTime, nullable=True)
    verified_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    rejection_reason = Column(Text, nullable=True)

    # Private administrative fields (NEVER exposed in public client directory)
    phone_number = Column(String(50), nullable=True)
    internal_notes = Column(Text, nullable=True)
    credential_documents = Column(JSON, nullable=False, default=list)

    # Relationships
    user = relationship(
        "User",
        foreign_keys=[user_id],
        backref=backref("lawyer_profile", uselist=False, cascade="all, delete-orphan")
    )
    organization = relationship("Organization", foreign_keys=[organization_id])
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])
    availability = relationship(
        "LawyerAvailability",
        back_populates="lawyer_profile",
        cascade="all, delete-orphan"
    )

    @validates("verification_status")
    def validate_verification_status(self, key, value):
        if isinstance(value, LawyerVerificationStatus):
            return value.value
        allowed = {s.value for s in LawyerVerificationStatus}
        if value not in allowed:
            raise ValueError(f"Invalid verification status '{value}'. Allowed: {allowed}")
        return value


class LegalMatter(Base, TimestampedModel):
    """
    Central lifecycle entity managing the attorney-client consultation and review workflow.
    Safeguards:
    - Status is governed by strict explicit enum values.
    - Conflict clearance records who certified it and when, not just a boolean.
    - Client consent is represented explicitly and remains separate from lawyer acceptance.
    - Client and lawyer organizations remain strictly segregated.
    """
    __tablename__ = "legal_matters"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    matter_code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    matter_type = Column(String(100), nullable=False)

    # Segregated Tenant Foreign Keys
    client_organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    client_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    lawyer_organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lawyer_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Target Contract Reference (if review is requested on an existing agreement)
    contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Strict Lifecycle Status
    status = Column(
        String(50),
        nullable=False,
        default=MatterStatus.SUBMITTED.value,
        index=True
    )

    # Conflict-of-Interest Verification Safeguards
    counterparty_name = Column(String(255), nullable=False)
    conflict_cleared = Column(Boolean, default=False, nullable=False)
    conflict_cleared_at = Column(DateTime, nullable=True)
    conflict_cleared_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    conflict_notes = Column(Text, nullable=True)

    # Client Consent Safeguards
    client_consent_given = Column(Boolean, default=False, nullable=False)
    client_consent_at = Column(DateTime, nullable=True)
    client_consent_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Scoping & Operational Notes
    preferred_time_slot = Column(String(100), nullable=True)
    client_notes = Column(Text, nullable=True)
    scoping_notes = Column(Text, nullable=True)
    decline_reason = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    client_organization = relationship("Organization", foreign_keys=[client_organization_id])
    client_user = relationship("User", foreign_keys=[client_user_id])
    lawyer_organization = relationship("Organization", foreign_keys=[lawyer_organization_id])
    lawyer_user = relationship("User", foreign_keys=[lawyer_user_id])
    conflict_cleared_by = relationship("User", foreign_keys=[conflict_cleared_by_user_id])
    client_consent_by = relationship("User", foreign_keys=[client_consent_by_user_id])
    contract = relationship("Contract", foreign_keys=[contract_id])

    access_grants = relationship(
        "MatterAccessGrant",
        back_populates="matter",
        cascade="all, delete-orphan"
    )
    messages = relationship(
        "MatterMessage",
        back_populates="matter",
        cascade="all, delete-orphan"
    )

    @validates("status")
    def validate_matter_status(self, key, value):
        if isinstance(value, MatterStatus):
            return value.value
        allowed = {s.value for s in MatterStatus}
        if value not in allowed:
            raise ValueError(f"Invalid matter status '{value}'. Allowed: {allowed}")
        return value

    @validates("decline_reason")
    def validate_decline_reason(self, key, value):
        if value is None:
            return None
        if isinstance(value, MatterDeclineReason):
            return value.value
        allowed = {r.value for r in MatterDeclineReason}
        if value not in allowed:
            raise ValueError(f"Invalid decline reason '{value}'. Allowed: {allowed}")
        return value


class MatterAccessGrant(Base, TimestampedModel):
    """
    Explicit, revocable cross-tenant document authorization token.
    Grants a specific lawyer user permission to inspect or redline an agreement.
    Does NOT store raw document bytes in the database.
    """
    __tablename__ = "matter_access_grants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    matter_id = Column(
        String(36),
        ForeignKey("legal_matters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lawyer_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    permission_level = Column(
        String(50),
        nullable=False,
        default=MatterPermissionLevel.READ_ONLY.value
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    granted_at = Column(DateTime, default=utc_now, nullable=False)
    granted_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    revocation_reason = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("matter_id", "contract_id", "lawyer_user_id", name="uq_matter_contract_lawyer_grant"),
    )

    # Relationships
    matter = relationship("LegalMatter", back_populates="access_grants")
    contract = relationship("Contract", foreign_keys=[contract_id])
    lawyer_user = relationship("User", foreign_keys=[lawyer_user_id])
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by = relationship("User", foreign_keys=[revoked_by_user_id])

    @validates("permission_level")
    def validate_permission_level(self, key, value):
        if isinstance(value, MatterPermissionLevel):
            return value.value
        allowed = {p.value for p in MatterPermissionLevel}
        if value not in allowed:
            raise ValueError(f"Invalid permission level '{value}'. Allowed: {allowed}")
        return value


class MatterMessage(Base, TimestampedModel):
    """
    Threaded client-lawyer communications within an active matter.
    Distinguishes client-visible messages from private internal advocate notes.
    """
    __tablename__ = "matter_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    matter_id = Column(
        String(36),
        ForeignKey("legal_matters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sender_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sender_type = Column(String(20), nullable=False)  # "CLIENT" or "LAWYER"
    message_text = Column(Text, nullable=False)

    # Safeguard: distinguishes internal chambers notes from client-visible messages
    is_internal_note = Column(Boolean, default=False, nullable=False, index=True)

    # Attachment metadata (file storage path & sha256, never raw binary bytes)
    attachments_json = Column(JSON, nullable=False, default=list)

    # Relationships
    matter = relationship("LegalMatter", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_user_id])

    @validates("sender_type")
    def validate_sender_type(self, key, value):
        if isinstance(value, MatterSenderType):
            return value.value
        allowed = {t.value for t in MatterSenderType}
        if value not in allowed:
            raise ValueError(f"Invalid sender type '{value}'. Allowed: {allowed}")
        return value


class LawyerAvailability(Base, TimestampedModel):
    """
    Lawyer working schedule windows for consultation intake.
    """
    __tablename__ = "lawyer_availability"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lawyer_profile_id = Column(
        String(36),
        ForeignKey("lawyer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    day_of_week = Column(Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    start_time = Column(String(10), nullable=False)  # "09:00"
    end_time = Column(String(10), nullable=False)  # "17:00"
    slot_duration_minutes = Column(Integer, default=45, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    lawyer_profile = relationship("LawyerProfile", back_populates="availability")

    __table_args__ = (
        Index("ix_lawyer_avail_profile_day", "lawyer_profile_id", "day_of_week"),
    )
