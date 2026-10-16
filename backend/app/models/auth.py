import enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utc_now

class AccountTokenType(str, enum.Enum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"

class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"

class RefreshToken(Base, TimestampedModel):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    family_id = Column(String(36), nullable=False, index=True)
    family_created_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_ip = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class AccountToken(Base, TimestampedModel):
    """
    Cryptographically secure single-use account workflow token.
    Used for email verification and password reset.
    Stores only SHA-256 token hashes in database.
    """
    __tablename__ = "account_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    token_type = Column(String(30), nullable=False, index=True)  # EMAIL_VERIFICATION, PASSWORD_RESET
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        now = utc_now()
        # Handle timezone-naive comparison safely
        exp = self.expires_at.replace(tzinfo=now.tzinfo) if self.expires_at.tzinfo is None else self.expires_at
        return now > exp


class OrganizationInvitation(Base, TimestampedModel):
    """
    Secure organization membership invitation.
    Scoped to an organization and recipient email with single-use hashed token.
    """
    __tablename__ = "organization_invitations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    inviter_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invitee_email = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="MEMBER")
    token_hash = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(30), nullable=False, default="PENDING")  # PENDING, ACCEPTED, DECLINED, REVOKED, EXPIRED
    accepted_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization")
    inviter = relationship("User")

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        now = utc_now()
        exp = self.expires_at.replace(tzinfo=now.tzinfo) if self.expires_at.tzinfo is None else self.expires_at
        return now > exp

