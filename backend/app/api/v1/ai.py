import logging
from fastapi import APIRouter, Depends
from app.models.organization import Organization
from app.models.user import User
from app.dependencies import get_current_active_user, get_current_tenant
from app.schemas.ai import GeneralChatRequest, GeneralChatResponse
from app.services.ai.general_assistant import ask_contractly_chat

from app.core.rate_limiter import ai_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/chat", response_model=GeneralChatResponse)
async def general_chat(
    payload: GeneralChatRequest,
    current_user: User = Depends(get_current_active_user),
    _tenant: Organization = Depends(get_current_tenant)
):
    """
    General Contractly Assistant endpoint.
    Answers CLM concepts, workflows, and terminology in an educational, safe manner.
    Tenant-authenticated and distinct from contract-grounded Q&A.
    Protected by sliding-window rate limiting.
    """
    await ai_rate_limiter.check_rate_limit(f"user:{current_user.id}")
    return await ask_contractly_chat(
        message=payload.message,
        history=payload.history
    )

@router.get("/status")
async def ai_status(
    _current_user: User = Depends(get_current_active_user),
    _tenant: Organization = Depends(get_current_tenant)
):
    """
    Returns AI service configuration status without exposing sensitive credentials.
    Tenant-authenticated.
    """
    import os
    from app.services.ai.gemini_provider import gemini_provider
    from app.config import BACKEND_ENV_PATH
    return {
        "configured": gemini_provider.is_configured(),
        "model": gemini_provider.model,
        "provider": "gemini",
        "env_file_loaded": os.path.exists(BACKEND_ENV_PATH),
        "env_file_exists": os.path.exists(BACKEND_ENV_PATH)
    }
