import logging
from typing import Optional, List, Dict
from fastapi import HTTPException
from app.config import settings
from app.schemas.ai import GeneralChatResponse
from app.services.ai.gemini_provider import (
    GeminiProvider,
    gemini_provider as default_gemini_provider,
    GeminiConfigurationError,
    GeminiTimeoutError,
    GeminiRateLimitError,
    GeminiAuthError,
    GeminiUnavailableError,
    GeminiBadRequestError,
    GeminiResponseParsingError,
    GeminiProviderError,
    sanitize_error_detail
)
from app.services.ai.prompts import GENERAL_ASSISTANT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

STANDARD_LEGAL_DISCLAIMER = (
    "This is an informational explanation and does not constitute legal advice."
)

async def ask_contractly_chat(
    message: str,
    provider: Optional[GeminiProvider] = None,
    history: Optional[List[Dict[str, str]]] = None
) -> GeneralChatResponse:
    """
    Executes general Contractly assistant conversation.
    Answers CLM concepts, workflow guidance, and legal terminology.
    Does NOT access specific contract context or produce binding legal conclusions.
    """
    clean_message = message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if len(clean_message) > settings.GEMINI_MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message exceeds maximum allowed length of {settings.GEMINI_MAX_QUESTION_LENGTH} characters."
        )

    active_provider = provider or default_gemini_provider

    if not active_provider.is_configured():
        logger.error("Gemini provider is not configured.")
        raise HTTPException(
            status_code=503,
            detail="AI service is not configured. Please set GEMINI_API_KEY in backend environment."
        )

    try:
        reply_text = await active_provider.generate_content(
            prompt=clean_message,
            system_instruction=GENERAL_ASSISTANT_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=800,
            history=history
        )

        return GeneralChatResponse(
            reply=reply_text.strip(),
            disclaimer=STANDARD_LEGAL_DISCLAIMER
        )

    except GeminiConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI service is not configured. Please set GEMINI_API_KEY in backend environment."
        ) from exc
    except GeminiTimeoutError as exc:
        raise HTTPException(status_code=504, detail="AI service request timed out.") from exc
    except GeminiRateLimitError as exc:
        raise HTTPException(status_code=429, detail="AI rate limit reached. Please retry in a moment.") from exc
    except GeminiAuthError as exc:
        raise HTTPException(status_code=502, detail="Upstream AI authentication error. Please verify API key permissions.") from exc
    except GeminiBadRequestError as exc:
        raise HTTPException(status_code=400, detail=sanitize_error_detail(f"AI request rejected by provider: {str(exc)}")) from exc
    except GeminiResponseParsingError as exc:
        raise HTTPException(status_code=502, detail="Invalid or empty response received from AI provider.") from exc
    except GeminiUnavailableError as exc:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Upstream provider is experiencing high load.") from exc
    except GeminiProviderError as exc:
        raise HTTPException(status_code=502, detail=sanitize_error_detail(f"AI provider error (service unavailable): {str(exc)}")) from exc
