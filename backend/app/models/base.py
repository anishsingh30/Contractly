import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from app.core.database import Base

def utc_now() -> datetime:
    """Returns current UTC timestamp as a timezone-naive datetime object, ensuring compatibility
    with both SQLite and PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns under asyncpg."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def ensure_utc(dt: datetime) -> datetime:
    if dt is None:
        return dt
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class TimestampedModel:
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

def generate_uuid() -> str:
    return str(uuid.uuid4())
