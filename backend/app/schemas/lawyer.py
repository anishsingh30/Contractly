from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.lawyer import (
    LawyerVerificationStatus,
    MatterStatus,
    MatterPermissionLevel,
    MatterSenderType,
    MatterDeclineReason,
)


# ============================================================================
# Legacy Inquiry Compatibility Schemas
# ============================================================================

class LawyerInquiryRequest(BaseModel):
    lawyer_id: str
    lawyer_name: Optional[str] = None
    preferred_time_slot: Optional[str] = "Next Available Slot"
    client_notes: Optional[str] = Field(default="", max_length=2000)
    title: Optional[str] = None
    counterparty_name: Optional[str] = None
    urgency: Optional[str] = None


class LawyerInquiryResponse(BaseModel):
    inquiry_id: str
    status: str
    lawyer_name: str
    preferred_time_slot: str
    message: str
    limitations_notice: str
    matter_id: Optional[str] = None
    inquiry_reference: Optional[str] = None
    success: bool = True


# ============================================================================
# Advocate Profile & Public Directory Schemas
# ============================================================================
# Advocate Profile & Public Directory Schemas
# ============================================================================

class PublicLawyerProfileResponse(BaseModel):
    """
    Client-safe public advocate profile schema.
    Strict privacy guarantee: NEVER includes private contact details,
    internal notes, credential document paths, or reviewer notes.
    """
    id: str
    user_id: str
    full_name: str
    professional_title: Optional[str] = "Advocate"
    firm_name: str
    organization_id: str
    bar_council_number: Optional[str] = None
    state_bar_council: str
    admitted_jurisdictions: str
    practice_areas: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    experience_years: int
    consultation_fee: str
    consultation_duration_minutes: int = 30
    bio: Optional[str] = None
    is_available_for_inquiries: bool
    verification_status: str
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Backwards compatibility alias for existing routes and tests
LawyerProfileResponse = PublicLawyerProfileResponse


class AdminLawyerProfileResponse(PublicLawyerProfileResponse):
    """
    Platform administrator advocate profile schema.
    Contains private administrative verification and contact details.
    RESTRICTED strictly to authenticated Platform Administrators.
    """
    email: str
    phone_number: Optional[str] = None
    private_address: Optional[str] = None
    internal_notes: Optional[str] = None
    credential_documents: List[Dict[str, Any]] = Field(default_factory=list)
    is_published: bool = False
    verified_by_user_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminLawyerCreateRequest(BaseModel):
    """Payload for Platform Admin to create or onboard a lawyer profile."""
    full_name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., min_length=5, max_length=255)
    phone_number: Optional[str] = Field(default=None, max_length=50)
    professional_title: Optional[str] = Field(default="Advocate", max_length=100)
    firm_name: Optional[str] = Field(default=None, max_length=255)
    bar_council_number: str = Field(..., min_length=3, max_length=100)
    state_bar_council: str = Field(..., min_length=2, max_length=100)
    admitted_jurisdictions: str = Field(..., min_length=2, max_length=500)
    practice_areas: List[str] = Field(default_factory=list)
    qualifications: Optional[List[str]] = Field(default_factory=list)
    languages: Optional[List[str]] = Field(default_factory=list)
    experience_years: int = Field(default=0, ge=0, le=70)
    consultation_fee: Optional[str] = Field(default="INR 0", max_length=100)
    consultation_duration_minutes: Optional[int] = Field(default=30, ge=15, le=180)
    bio: Optional[str] = Field(default=None, max_length=5000)
    internal_notes: Optional[str] = Field(default=None, max_length=5000)
    is_available_for_inquiries: bool = Field(default=True)
    is_published: bool = Field(default=False)


class AdminLawyerUpdateRequest(BaseModel):
    """Payload for Platform Admin to edit an existing lawyer profile."""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    professional_title: Optional[str] = None
    firm_name: Optional[str] = None
    bar_council_number: Optional[str] = None
    state_bar_council: Optional[str] = None
    admitted_jurisdictions: Optional[str] = None
    practice_areas: Optional[List[str]] = None
    qualifications: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    experience_years: Optional[int] = Field(default=None, ge=0, le=70)
    consultation_fee: Optional[str] = None
    consultation_duration_minutes: Optional[int] = Field(default=None, ge=15, le=180)
    bio: Optional[str] = None
    internal_notes: Optional[str] = None
    is_available_for_inquiries: Optional[bool] = None
    is_published: Optional[bool] = None


class AdminLawyerPublishRequest(BaseModel):
    is_published: bool = Field(..., description="Set to true to publish, false to unpublish")


class AdminLawyerAvailabilityRequest(BaseModel):
    is_available_for_inquiries: bool = Field(..., description="Set to true if accepting inquiries")


class LawyerProfileUpdateRequest(BaseModel):
    firm_name: Optional[str] = None
    state_bar_council: Optional[str] = None
    admitted_jurisdictions: Optional[str] = None
    practice_areas: Optional[List[str]] = None
    experience_years: Optional[int] = Field(default=None, ge=0, le=70)
    consultation_fee: Optional[str] = None
    bio: Optional[str] = None
    is_available_for_inquiries: Optional[bool] = None


class LawyerVerificationDecisionRequest(BaseModel):
    decision: str = Field(..., description="'VERIFY' or 'REJECT'")
    reason: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        clean = (v or "").strip().upper()
        if clean not in ("VERIFY", "REJECT"):
            raise ValueError("Decision must be either 'VERIFY' or 'REJECT'.")
        return clean


# ============================================================================
# Legal Matter Intake & Lifecycle Schemas
# ============================================================================

class LegalHelpInquiryCreate(BaseModel):
    lawyer_user_id: str = Field(..., description="Target advocate's user ID")
    title: str = Field(..., min_length=3, max_length=500)
    matter_type: str = Field(default="CONTRACT_REVIEW", min_length=2, max_length=100)
    counterparty_name: str = Field(..., min_length=1, max_length=255, description="Opposing party name for conflict checking")
    contract_id: Optional[str] = Field(default=None, description="Client agreement ID to link to matter")
    preferred_time_slot: Optional[str] = Field(default=None, max_length=100)
    client_notes: Optional[str] = Field(default=None, max_length=3000)


class MatterSummaryResponse(BaseModel):
    id: str
    matter_code: str
    title: str
    matter_type: str
    status: str
    client_organization_id: str
    client_organization_name: str
    client_user_id: Optional[str]
    client_user_name: Optional[str]
    lawyer_organization_id: str
    lawyer_organization_name: str
    lawyer_user_id: Optional[str]
    lawyer_user_name: Optional[str]
    counterparty_name: str
    contract_id: Optional[str]
    contract_title: Optional[str] = None
    conflict_cleared: bool
    client_consent_given: bool
    has_active_grant: bool
    grant_permission_level: Optional[str] = None
    preferred_time_slot: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatterDetailResponse(MatterSummaryResponse):
    conflict_cleared_at: Optional[datetime] = None
    client_consent_at: Optional[datetime] = None
    client_notes: Optional[str] = None
    scoping_notes: Optional[str] = None
    decline_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    has_admin_review: bool = False
    last_admin_review_at: Optional[datetime] = None
    admin_review_reason: Optional[str] = None


class ClarificationRequestPayload(BaseModel):
    scoping_question: str = Field(..., min_length=5, max_length=2000)


class ClarificationResponsePayload(BaseModel):
    scoping_answer: str = Field(..., min_length=2, max_length=3000)


class ConflictCheckCertificationPayload(BaseModel):
    certified_clear: bool = Field(..., description="Must certify that no conflict of interest exists")
    conflict_notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("certified_clear")
    @classmethod
    def validate_certified(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must explicitly certify conflict clearance before accepting.")
        return v


class MatterAcceptPayload(BaseModel):
    confirmed_slot: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class MatterDeclinePayload(BaseModel):
    decline_reason: MatterDeclineReason
    notes: Optional[str] = Field(default=None, max_length=1000)


class ClientConsentPayload(BaseModel):
    consent_given: bool = Field(..., description="Explicit client consent to authorize contract document sharing")
    permission_level: MatterPermissionLevel = Field(
        default=MatterPermissionLevel.READ_ONLY,
        description="Level of document access: READ_ONLY or REDLINE_COLLABORATIVE"
    )

    @field_validator("consent_given")
    @classmethod
    def validate_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Explicit consent must be set to true to authorize document access.")
        return v


class MatterWithdrawPayload(BaseModel):
    cancellation_reason: Optional[str] = Field(default=None, max_length=1000)


class MatterResolvePayload(BaseModel):
    resolution_summary: str = Field(..., min_length=5, max_length=3000)


# ============================================================================
# Document & Redline Schemas
# ============================================================================

class MatterDocumentVersionItem(BaseModel):
    version_id: str
    version_number: str
    filename: Optional[str]
    file_byte_size: int
    sha256_checksum: str
    page_count: Optional[int]
    created_at: datetime


class MatterRedlineProposalCreate(BaseModel):
    section_title: str = Field(..., min_length=2, max_length=255)
    original_text: str = Field(..., min_length=1)
    suggested_text: str = Field(..., min_length=1)
    rationale: Optional[str] = Field(default=None, max_length=2000)
    clause_id: Optional[str] = None


class MatterRedlineResponse(BaseModel):
    id: str
    contract_id: str
    section_title: str
    original_text: str
    suggested_text: str
    rationale: Optional[str]
    status: str
    author: str
    created_at: datetime


# ============================================================================
# Matter Messaging Schemas
# ============================================================================

class MatterMessageCreate(BaseModel):
    message_text: str = Field(..., min_length=1, max_length=5000)
    is_internal_note: bool = Field(
        default=False,
        description="Private internal chambers note invisible to client users"
    )
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class MatterMessageResponse(BaseModel):
    id: str
    matter_id: str
    sender_user_id: str
    sender_name: str
    sender_type: str
    message_text: str
    is_internal_note: bool
    attachments: List[Dict[str, Any]]
    created_at: datetime


class ConversationItemResponse(BaseModel):
    matter_id: str
    matter_code: str
    title: str
    status: str
    client_organization_name: str
    client_user_name: Optional[str] = None
    lawyer_organization_name: str
    lawyer_user_name: Optional[str] = None
    contract_title: Optional[str] = None
    last_message_text: Optional[str] = None
    last_message_at: Optional[datetime] = None
    last_message_sender_type: Optional[str] = None
    message_count: int = 0
    has_admin_review: bool = False
    last_admin_review_at: Optional[datetime] = None
    admin_review_reason: Optional[str] = None
    is_active_for_messaging: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminConversationItem(BaseModel):
    matter_id: str
    matter_code: str
    title: str
    status: str
    client_organization_id: str
    client_organization_name: str
    client_user_email: Optional[str] = None
    client_user_name: Optional[str] = None
    lawyer_organization_name: str
    lawyer_user_email: Optional[str] = None
    lawyer_user_name: Optional[str] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    review_status: str = "UNREVIEWED"  # "REVIEWED" or "UNREVIEWED"
    last_reviewed_at: Optional[datetime] = None
    last_reviewed_by: Optional[str] = None
    last_review_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminConversationReviewPayload(BaseModel):
    review_reason: Optional[str] = Field(default=None, max_length=255, description="Legitimate administrative purpose for oversight review")
    reason: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000, description="Optional administrative notes")

    def get_reason(self) -> str:
        return (self.review_reason or self.reason or "Administrative Compliance Review").strip()


class AdminConversationNotePayload(BaseModel):
    note_text: str = Field(..., min_length=3, max_length=3000, description="Administrative oversight note")


class AdminConversationReviewResponse(BaseModel):
    matter_id: str
    matter_code: str
    title: str
    status: str
    review_status: str
    reviewed_at: datetime
    reviewed_by: str
    review_reason: str
    messages: List[MatterMessageResponse]
    audit_history: List[Dict[str, Any]]
    admin_notes: List[Dict[str, Any]]


class AdminConsultationRequestItem(BaseModel):
    matter_id: str
    matter_code: str
    title: str
    status: str
    client_organization_id: str
    client_organization_name: str
    client_user_id: Optional[str] = None
    client_user_name: Optional[str] = None
    client_user_email: Optional[str] = None
    lawyer_organization_id: str
    lawyer_organization_name: str
    lawyer_user_id: Optional[str] = None
    lawyer_user_name: Optional[str] = None
    lawyer_user_email: Optional[str] = None
    counterparty_name: str
    preferred_time_slot: Optional[str] = None
    client_notes: Optional[str] = None
    initial_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminConsultationDecisionPayload(BaseModel):
    decision: Optional[str] = None
    action: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("decision", mode="before")
    @classmethod
    def validate_decision(cls, v: Any) -> Optional[str]:
        if v:
            clean = str(v).strip().upper()
            if clean not in ("APPROVE", "REJECT"):
                raise ValueError("Decision must be either 'APPROVE' or 'REJECT'.")
            return clean
        return None

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v: Any) -> Optional[str]:
        if v:
            clean = str(v).strip().upper()
            if clean not in ("APPROVE", "REJECT"):
                raise ValueError("Action must be either 'APPROVE' or 'REJECT'.")
            return clean
        return None
