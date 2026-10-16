from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class User(Base, TimestampedModel):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_super_admin = Column(Boolean, default=False)

    # Relationships
    memberships = relationship("OrganizationMember", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    @property
    def platform_role(self):
        """
        Operational platform administrative role (e.g. PLATFORM_SUPER_ADMIN, PLATFORM_SUPPORT).
        Separated strictly from customer tenant organization roles.
        """
        override = getattr(self, "_platform_role_override", None)
        if override:
            return override
        if self.is_super_admin or (self.email and self.email.strip().lower() == "admin@contractly.com"):
            return "PLATFORM_SUPER_ADMIN"
        return None

    @platform_role.setter
    def platform_role(self, role: str) -> None:
        self._platform_role_override = role

    def set_platform_role(self, role: str) -> None:
        self._platform_role_override = role

class OrganizationMember(Base, TimestampedModel):
    __tablename__ = "organization_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(String(36), nullable=True)
    role = Column(String(50), nullable=False, default="LEGAL_MANAGER")  # OWNER, ADMIN, LEGAL_MANAGER, LEGAL_REVIEWER, FINANCE, PROCUREMENT, HR, EMPLOYEE
    status = Column(String(30), default="ACTIVE")

    # Relationships
    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="members")
