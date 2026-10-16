import logging
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class GeminiProviderError(Exception):
    """Base error for Gemini provider operations."""
    pass

class GeminiConfigurationError(GeminiProviderError):
    """Raised when Gemini API key or required settings are missing."""
    pass

class GeminiAuthError(GeminiProviderError):
    """Raised when authentication with Gemini fails (HTTP 401 / 403)."""
    pass

class GeminiRateLimitError(GeminiProviderError):
    """Raised when rate limits or quotas are exceeded (HTTP 429)."""
    pass

class GeminiTimeoutError(GeminiProviderError):
    """Raised when request to Gemini times out."""
    pass

class GeminiUnavailableError(GeminiProviderError):
    """Raised when upstream Gemini service is unavailable (HTTP 500 / 502 / 503 / 504)."""
    pass

class GeminiBadRequestError(GeminiProviderError):
    """Raised when upstream Gemini service rejects request parameters or structure (HTTP 400)."""
    pass

class GeminiResponseParsingError(GeminiProviderError):
    """Raised when Gemini response is empty or cannot be parsed."""
    pass

def sanitize_error_detail(detail: str) -> str:
    """Removes sensitive API keys, authorization tokens, or URL query secrets from error messages."""
    import re
    cleaned = detail or ""
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY in cleaned:
        cleaned = cleaned.replace(settings.GEMINI_API_KEY, "[REDACTED]")
    cleaned = re.sub(r'AIza[0-9A-Za-z_-]{10,}', '[REDACTED]', cleaned)
    cleaned = re.sub(r'(key|api_key|token)=[0-9A-Za-z_-]+', r'\1=[REDACTED]', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'https?://[^\s]+', '[ENDPOINT_URL]', cleaned)
    return cleaned

class GeminiProvider:
    """
    Server-side Google Gemini REST API client.
    Handles communication with Google's generativelanguage v1beta API safely.
    Ensures credentials remain server-side and never leak into logs or responses.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self._explicit_api_key = api_key
        self._explicit_model = model
        self._explicit_base_url = base_url
        self._explicit_timeout = timeout

    @property
    def _api_key(self) -> str:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return settings.GEMINI_API_KEY

    @property
    def model(self) -> str:
        if self._explicit_model is not None:
            return self._explicit_model
        return settings.GEMINI_MODEL

    @property
    def base_url(self) -> str:
        if self._explicit_base_url is not None:
            return self._explicit_base_url.rstrip("/")
        return settings.GEMINI_API_BASE_URL.rstrip("/")

    @property
    def timeout(self) -> float:
        if self._explicit_timeout is not None:
            return self._explicit_timeout
        return settings.GEMINI_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        """Returns True if a non-empty, non-placeholder API key is configured."""
        key = self._api_key
        if not key or not key.strip():
            return False
        if key.strip().upper() in ("YOUR_GEMINI_API_KEY_HERE", "PLACEHOLDER", "NONE"):
            return False
        return True

    def _normalize_contents(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Normalizes multi-turn conversation contents for Google's Gemini API:
        1. Strips text and skips turns with empty content.
        2. Discards introductory model greetings before the first user turn.
        3. Enforces strict alternation (merging consecutive turns with identical roles).
        4. Appends the current prompt as user.
        """
        contents: List[Dict[str, Any]] = []

        if history:
            normalized_turns: List[Dict[str, str]] = []
            for turn in history:
                text = (turn.get("content") or turn.get("text") or "").strip()
                if not text:
                    continue
                role = (turn.get("role") or "user").lower()
                gemini_role = "model" if role in ("assistant", "model") else "user"

                # Drop leading model greetings before any user turn
                if not normalized_turns and gemini_role == "model":
                    continue

                if normalized_turns and normalized_turns[-1]["role"] == gemini_role:
                    normalized_turns[-1]["text"] += f"\n\n{text}"
                else:
                    normalized_turns.append({"role": gemini_role, "text": text})

            for n_turn in normalized_turns:
                contents.append({
                    "role": n_turn["role"],
                    "parts": [{"text": n_turn["text"]}]
                })

        clean_prompt = prompt.strip()
        if contents and contents[-1]["role"] == "user":
            # If the last turn in history was already user, insert interim acknowledgement
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})

        contents.append({
            "role": "user",
            "parts": [{"text": clean_prompt}]
        })

        return contents

    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Sends generation request to Gemini REST API with automated transient retries.
        Never logs or exposes the API key.
        """
        if not self.is_configured():
            raise GeminiConfigurationError(
                "Gemini API key is not configured in backend environment configuration (GEMINI_API_KEY)."
            )

        endpoint = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self._api_key}
        contents = self._normalize_contents(prompt=prompt, history=history)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens
            }
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        logger.info("Executing Gemini content generation [model=%s, timeout=%.1fs]", self.model, self.timeout)

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        endpoint,
                        params=params,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        prompt_feedback = data.get("promptFeedback", {})
                        block_reason = prompt_feedback.get("blockReason")
                        if block_reason:
                            raise GeminiProviderError(f"Prompt was blocked by safety filter: {block_reason}")
                        raise GeminiResponseParsingError("Gemini returned an empty candidate list.")

                    candidate = candidates[0]
                    finish_reason = candidate.get("finishReason")
                    if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
                        raise GeminiProviderError(f"Generation was halted due to content policy: {finish_reason}")

                    parts = candidate.get("content", {}).get("parts", [])
                    text_response = "".join(part.get("text", "") for part in parts).strip()
                    if not text_response:
                        raise GeminiResponseParsingError("Gemini candidate did not contain any text content.")
                    return text_response

                # Model 404 or quota-exhausted fallback to alternative active model
                fallback_model = "gemini-flash-lite-latest" if self.model != "gemini-flash-lite-latest" else "gemini-flash-latest"
                if (response.status_code == 404 or (response.status_code == 429 and "quota" in response.text.lower())) and attempt == 0:
                    logger.warning(
                        "Configured model '%s' returned status %d. Attempting fallback to '%s'.",
                        self.model,
                        response.status_code,
                        fallback_model
                    )
                    fallback_endpoint = f"{self.base_url}/models/{fallback_model}:generateContent"
                    try:
                        async with httpx.AsyncClient(timeout=self.timeout) as client:
                            fb_response = await client.post(
                                fallback_endpoint,
                                params=params,
                                json=payload,
                                headers={"Content-Type": "application/json"}
                            )
                        if fb_response.status_code == 200:
                            data = fb_response.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                text = "".join(part.get("text", "") for part in parts).strip()
                                if text:
                                    return text
                    except Exception as fb_exc:
                        logger.warning("Fallback model '%s' invocation failed: %s", fallback_model, fb_exc)

                # Transient 5xx / 429 retries
                if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    logger.warning(
                        "Gemini API returned status %d on attempt %d. Retrying in %ds...",
                        response.status_code,
                        attempt + 1,
                        attempt + 1
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue

                if response.status_code in (401, 403):
                    logger.error("Gemini authentication failed [status=%d]", response.status_code)
                    raise GeminiAuthError("Gemini authentication failed. Please verify API key configuration.")

                if response.status_code == 429:
                    logger.warning("Gemini rate limit exceeded [status=429]")
                    raise GeminiRateLimitError("Gemini rate limit exceeded. Please retry after a brief delay.")

                if response.status_code == 400:
                    err_msg = "Invalid request syntax or parameters."
                    try:
                        err_msg = response.json().get("error", {}).get("message", err_msg)
                    except Exception:
                        pass
                    if "api key" in err_msg.lower():
                        logger.error("Gemini API authentication failed via 400: %s", err_msg)
                        raise GeminiAuthError(f"Gemini authentication failed: {err_msg}")
                    logger.error("Gemini API bad request [status=400]: %s", err_msg)
                    raise GeminiBadRequestError(f"Bad request to Gemini: {err_msg}")

                if response.status_code >= 500:
                    logger.error("Gemini upstream service unavailable [status=%d]", response.status_code)
                    raise GeminiUnavailableError("Gemini service is currently unavailable. Please try again later.")

                logger.error("Gemini API call returned status %d", response.status_code)
                raise GeminiProviderError(f"Gemini API returned error status {response.status_code}.")

            except httpx.TimeoutException as exc:
                logger.error("Gemini API call timed out after %.1f seconds", self.timeout)
                raise GeminiTimeoutError(f"Gemini request timed out after {self.timeout} seconds.") from exc
            except (GeminiProviderError,):
                raise
            except Exception as exc:
                logger.error("Unexpected error during Gemini API invocation: %s", type(exc).__name__)
                raise GeminiProviderError("Unexpected failure communicating with Gemini provider.") from exc

# Default singleton instance
gemini_provider = GeminiProvider()
