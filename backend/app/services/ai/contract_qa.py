import logging
from typing import Optional
from fastapi import HTTPException
from app.config import settings
from app.models.contract import Contract
from app.schemas.ai import ContractQAResponse
from app.services.ai.gemini_provider import (
    GeminiProvider,
    gemini_provider as default_gemini_provider,
    GeminiConfigurationError,
    GeminiTimeoutError,
    GeminiRateLimitError,
    GeminiAuthError,
    GeminiBadRequestError,
    GeminiResponseParsingError,
    GeminiUnavailableError,
    GeminiProviderError,
    sanitize_error_detail
)
from app.services.ai.prompts import CONTRACT_QA_SYSTEM_PROMPT, GROUNDED_FALLBACK_ANSWER
from app.services.ai.context_builder import retrieve_relevant_contract_context

logger = logging.getLogger(__name__)

async def ask_contract_qa(
    contract: Contract,
    question: str,
    provider: Optional[GeminiProvider] = None
) -> ContractQAResponse:
    """
    Executes grounded Q&A against a specific contract.
    Retrieves structured context, defends against prompt injection,
    calls Gemini with strict system directives, and returns database-backed citations.
    """
    clean_question = question.strip()
    if not clean_question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if len(clean_question) > settings.GEMINI_MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Question exceeds maximum allowed length of {settings.GEMINI_MAX_QUESTION_LENGTH} characters."
        )

    # 1. Structured Retrieval without Vector DB
    context_str, sources, has_relevant_context = retrieve_relevant_contract_context(
        contract=contract,
        question=clean_question
    )

    # If completely irrelevant and no contract facts exist for this query
    if not has_relevant_context:
        logger.info("No relevant contract context found for query on contract %s", contract.id)
        return ContractQAResponse(
            answer=GROUNDED_FALLBACK_ANSWER,
            confidence="grounded",
            sources=[]
        )

    active_provider = provider or default_gemini_provider

    # Verify provider configuration
    if not active_provider.is_configured():
        logger.error("Gemini provider is not configured.")
        raise HTTPException(
            status_code=503,
            detail="AI service is not configured. Please set GEMINI_API_KEY in backend environment."
        )

    # 2. Build User Prompt with Untrusted Document Boundary
    user_prompt = (
        "=== CONTRACT CONTEXT (UNTRUSTED DOCUMENT MATERIAL) ===\n"
        f"{context_str}\n"
        "=== END CONTRACT CONTEXT ===\n\n"
        f"QUESTION: {clean_question}\n\n"
        "Please provide a direct, grounded answer based strictly on the CONTRACT CONTEXT above."
    )

    try:
        raw_answer = await active_provider.generate_content(
            prompt=user_prompt,
            system_instruction=CONTRACT_QA_SYSTEM_PROMPT,
            temperature=0.1,  # Low temperature for strict factual grounding
            max_output_tokens=700
        )

        final_answer = raw_answer.strip()
        if not final_answer:
            final_answer = GROUNDED_FALLBACK_ANSWER

        citation_str = (
            f"{sources[0].section} ({sources[0].title})" if sources and sources[0].title
            else "General Provisions"
        )
        return ContractQAResponse(
            answer=final_answer,
            confidence="grounded",
            sources=sources,
            citation=citation_str
        )

    except GeminiConfigurationError as exc:
        raise HTTPException(status_code=503, detail="AI service is not configured. Please set GEMINI_API_KEY in backend environment.") from exc
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
