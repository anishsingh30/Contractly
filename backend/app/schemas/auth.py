from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from app.core.security import validate_password_strength

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization_name: Optional[str] = None
    account_type: str = "INDIVIDUAL"  # INDIVIDUAL, BUSINESS, ENTERPRISE, LEGAL_PROFESSIONAL
    role: Optional[str] = None  # Ignored on server-side creation; registrant is always assigned OWNER

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        is_valid, err_msg = validate_password_strength(v)
        if not is_valid:
            raise ValueError(err_msg)
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()

    @field_validator("organization_name")
    @classmethod
    def validate_org_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Organization name cannot be blank if provided")
        return v.strip() if v else None

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        clean = (v or "").strip().upper()
        if clean in ("PLATFORM_ADMIN", "SUPER_ADMIN", "PLATFORM_SUPER_ADMIN", "PLATFORM_SUPPORT"):
            raise ValueError("Platform administrative roles cannot be requested as customer account types.")
        valid = {"INDIVIDUAL", "PERSONAL", "BUSINESS", "ENTERPRISE", "LEGAL_PROFESSIONAL", "PROFESSIONAL", "LAWYER"}
        if clean not in valid:
            raise ValueError(f"Invalid account type '{v}'. Allowed types: INDIVIDUAL, BUSINESS, ENTERPRISE, LEGAL_PROFESSIONAL.")
        return clean

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    role: str = "LEGAL_MANAGER"
    account_type: str = "BUSINESS"
    subscription_tier: Optional[str] = "COMMUNITY"
    permissions: List[str] = []
    entitlements: Optional[Dict[str, Any]] = None
    email_verification_status: str = "BLOCKED_UNCONFIGURED"
    is_super_admin: bool = False
    platform_role: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    refresh_token: Optional[str] = None

class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None

class SwitchTenantRequest(BaseModel):
    organization_id: str

class MessageResponse(BaseModel):
    message: str

class InviteMemberRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "MEMBER"  # OWNER, ADMIN, LEGAL_MANAGER, LEGAL_REVIEWER, PROCUREMENT, FINANCE, HR, MEMBER, VIEWER
    department_id: Optional[str] = None

class MemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    role: str
    status: str
    created_at: Optional[str] = None

class DepartmentCreateRequest(BaseModel):
    name: str
    budget_currency: str = "INR"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Department name cannot be empty")
        return v.strip()

class DepartmentResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    budget_currency: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        is_valid, err_msg = validate_password_strength(v)
        if not is_valid:
            raise ValueError(err_msg)
        return v

class VerifyEmailRequest(BaseModel):
    token: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class VerificationStatusResponse(BaseModel):
    email_delivery_configured: bool
    verification_status: str
    provider: Optional[str] = None
    detail: Optional[str] = None

class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: str = "MEMBER"  # OWNER, ADMIN, LEGAL_MANAGER, LEGAL_REVIEWER, PROCUREMENT, FINANCE, HR, MEMBER, VIEWER

class InvitationResponse(BaseModel):
    id: str
    organization_id: str
    organization_name: Optional[str] = None
    invitee_email: str
    role: str
    status: str
    expires_at: str
    created_at: str
    email_sent: bool = False
    delivery_status: Optional[str] = None

class AcceptInvitationRequest(BaseModel):
    token: str
    full_name: Optional[str] = None
    password: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            is_valid, err_msg = validate_password_strength(v)
            if not is_valid:
                raise ValueError(err_msg)
        return v

class DeclineInvitationRequest(BaseModel):
    token: str

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Full name cannot be empty")
            return clean
        return None

