import re
import secrets
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union, Tuple
from jose import jwt, JWTError, ExpiredSignatureError
import bcrypt
from app.config import settings

def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Enforces password complexity:
    - At least 8 characters
    - At least one numeric digit
    - At least one special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-\\\/+=;~`\[\]]", password):
        return False, "Password must contain at least one special character."
    return True, None

def get_password_hash(password: str) -> str:
    # Ensure password fits within bcrypt 72 bytes limit safely
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(
    subject: Union[str, Any],
    org_id: Optional[str] = None,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None
) -> str:
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": now_utc
    }
    if org_id:
        to_encode["org_id"] = org_id
    if role:
        to_encode["role"] = role
    if additional_claims:
        to_encode.update(additional_claims)
        
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    Decodes and validates an access token.
    Raises ExpiredSignatureError if expired, JWTError if invalid or wrong token type.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type: expected access token")
    if "sub" not in payload:
        raise JWTError("Invalid token: missing subject claim")
    return payload

def decode_token(token: str) -> Optional[dict]:
    """Legacy helper for backward compatibility."""
    try:
        return decode_access_token(token)
    except JWTError:
        return None

def generate_refresh_token() -> str:
    """Generates a cryptographically secure, high-entropy raw refresh token."""
    return secrets.token_urlsafe(48)

def hash_refresh_token(token: str) -> str:
    """Hashes a refresh token using SHA-256 for secure database persistence."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
