from sqlalchemy import Column, String, Text, Index
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid

class AuditLog(Base, TimestampedModel):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), nullable=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    object_type = Column(String(50), nullable=False)
    object_id = Column(String(100), nullable=False)
    detail = Column(Text, nullable=False)
    ip_address = Column(String(50), default="127.0.0.1")

    __table_args__ = (
        Index("ix_audit_logs_user_email_created_at", "user_email", "created_at"),
        Index("ix_audit_logs_org_created_at", "organization_id", "created_at"),
    )
