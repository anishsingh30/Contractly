import os
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport, Response, Request

from app.main import app
from app.config import settings
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.core.security import get_password_hash, create_access_token
from app.services.ai.gemini_provider import (
    GeminiProvider,
    GeminiConfigurationError,
    GeminiTimeoutError,
    GeminiRateLimitError,
    GeminiAuthError,
    GeminiBadRequestError,
    GeminiResponseParsingError,
    GeminiUnavailableError,
    GeminiProviderError
)
from app.services.ai.general_assistant import ask_contractly_chat
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

async def create_test_user_and_auth(test_engine, role="LEGAL_MANAGER"):
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    suffix = uuid.uuid4().hex[:6]
    async with TestSessionLocal() as session:
        org = Organization(
            name=f"Chat Org {suffix}",
            slug=f"chat-org-{suffix}",
            account_type="BUSINESS"
        )
        session.add(org)
        await session.flush()

        user = User(
            email=f"chat-{suffix}@test.internal",
            password_hash=get_password_hash("Password123!"),
            full_name=f"Chat User {suffix}"
        )
        session.add(user)
        await session.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=role
        )
        session.add(member)
        await session.commit()

        token = create_access_token(
            subject=user.id,
            org_id=org.id,
            role=role
        )
        return org, user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_successful_general_chat_request(test_engine):
    """Verify successful POST /api/v1/ai/chat returns educational response and disclaimer."""
    org, user, headers = await create_test_user_and_auth(test_engine)

    expected_reply = "An auto-renewal clause automatically extends an agreement unless timely notice is given."
    with patch("app.services.ai.general_assistant.default_gemini_provider.generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = expected_reply
        with patch("app.services.ai.general_assistant.default_gemini_provider.is_configured", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.post(
                    "/api/v1/ai/chat",
                    headers=headers,
                    json={
                        "message": "What is an auto-renewal clause?",
                        "history": [
                            {"role": "user", "content": "Hello"},
                            {"role": "assistant", "content": "Hi! How can I help you understand contracts today?"}
                        ]
                    }
                )
                assert res.status_code == 200
                data = res.json()
                assert data["reply"] == expected_reply
                assert "not constitute legal advice" in data["disclaimer"]


@pytest.mark.asyncio
async def test_missing_api_key_returns_503(test_engine):
    """Verify missing API key returns HTTP 503 with informative configuration instructions."""
    org, user, headers = await create_test_user_and_auth(test_engine)

    with patch("app.services.ai.general_assistant.default_gemini_provider.is_configured", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/ai/chat",
                headers=headers,
                json={"message": "Explain indemnity"}
            )
            assert res.status_code == 503
            assert "AI service is not configured" in res.json()["detail"]
            assert "GEMINI_API_KEY" in res.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_upstream_credentials_returns_502_sanitized(test_engine):
    """Verify upstream authentication failure maps to 502 without leaking secrets."""
    org, user, headers = await create_test_user_and_auth(test_engine)

    with patch(
        "app.services.ai.general_assistant.default_gemini_provider.generate_content",
        side_effect=GeminiAuthError("Google Generative AI returned 401/403: API_KEY_INVALID")
    ):
        with patch("app.services.ai.general_assistant.default_gemini_provider.is_configured", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.post(
                    "/api/v1/ai/chat",
                    headers=headers,
                    json={"message": "Explain indemnity"}
                )
                assert res.status_code == 502
                detail = res.json()["detail"]
                assert "authentication error" in detail.lower()
                assert "AIzaSy" not in detail


@pytest.mark.asyncio
async def test_upstream_rate_limiting_returns_429(test_engine):
    """Verify upstream rate limiting returns HTTP 429 to client."""
    org, user, headers = await create_test_user_and_auth(test_engine)

    with patch(
        "app.services.ai.general_assistant.default_gemini_provider.generate_content",
        side_effect=GeminiRateLimitError("Rate limit exceeded")
    ):
        with patch("app.services.ai.general_assistant.default_gemini_provider.is_configured", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.post(
                    "/api/v1/ai/chat",
                    headers=headers,
                    json={"message": "Explain indemnity"}
                )
                assert res.status_code == 429
                assert "rate limit" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upstream_timeout_returns_504(test_engine):
    """Verify upstream timeout maps to HTTP 504."""
    org, user, headers = await create_test_user_and_auth(test_engine)

    with patch(
        "app.services.ai.general_assistant.default_gemini_provider.generate_content",
        side_effect=GeminiTimeoutError("Provider timed out after 30 seconds")
    ):
        with patch("app.services.ai.general_assistant.default_gemini_provider.is_configured", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.post(
                    "/api/v1/ai/chat",
                    headers=headers,
                    json={"message": "Explain indemnity"}
                )
                assert res.status_code == 504
                assert "timed out" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_malformed_upstream_response_returns_502(test_engine):
    """Verify malformed or empty provider candidates return HTTP 502 parsing error."""
    org, user, headers = await create_test_user_and_auth(test_engine)

    with patch(
        "app.services.ai.general_assistant.default_gemini_provider.generate_content",
        side_effect=GeminiResponseParsingError("Gemini response missing valid text candidates.")
    ):
        with patch("app.services.ai.general_assistant.default_gemini_provider.is_configured", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.post(
                    "/api/v1/ai/chat",
                    headers=headers,
                    json={"message": "Explain indemnity"}
                )
                assert res.status_code == 502
                assert "empty response" in res.json()["detail"].lower() or "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(test_engine):
    """Verify unauthenticated requests to /api/v1/ai/chat are rejected with HTTP 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/ai/chat",
            json={"message": "What is force majeure?"}
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_no_leakage_of_secrets_in_errors(test_engine):
    """Verify API keys and auth headers are never leaked in error messages or response structures."""
    org, user, headers = await create_test_user_and_auth(test_engine)

    secret_key = "AIzaSySecretApiKeyDoNotLeak999"
    with patch(
        "app.services.ai.general_assistant.default_gemini_provider.generate_content",
        side_effect=GeminiProviderError(f"Exception containing {secret_key}")
    ):
        with patch("app.services.ai.general_assistant.default_gemini_provider.is_configured", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.post(
                    "/api/v1/ai/chat",
                    headers=headers,
                    json={"message": "Explain indemnity"}
                )
                # Ensure response text does not contain the secret key even if provider threw it
                # In general_assistant, we sanitize or provider sanitizes
                assert res.status_code == 502
                assert secret_key not in res.text
                assert "[REDACTED]" in res.text


def test_history_normalization_drops_leading_assistant_and_merges():
    """Verify GeminiProvider._normalize_contents discards leading assistant turns and alternates cleanly."""
    provider = GeminiProvider(api_key="test-key")

    raw_history = [
        {"role": "assistant", "content": "Welcome! I am Contractly AI."},
        {"role": "user", "content": "What is an NDA?"},
        {"role": "assistant", "content": "A non-disclosure agreement protects confidential information."},
        {"role": "assistant", "content": "Do you need clarification?"},
        {"role": "user", "content": "Can you give an example?"}
    ]

    contents = provider._normalize_contents(prompt="And what about remedies?", history=raw_history)

    # Must start with 'user'
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "What is an NDA?"

    # Second must be 'model'
    assert contents[1]["role"] == "model"
    # Merged assistant content
    assert "A non-disclosure agreement" in contents[1]["parts"][0]["text"]
    assert "Do you need clarification?" in contents[1]["parts"][0]["text"]

    # Third must be 'user'
    assert contents[2]["role"] == "user"
    assert contents[2]["parts"][0]["text"] == "Can you give an example?"

    # Fourth must be intermediate 'model' acknowledgement to preserve alternation
    assert contents[3]["role"] == "model"
    assert contents[3]["parts"][0]["text"] == "Understood."

    # Fifth must be final prompt as 'user'
    assert contents[4]["role"] == "user"
    assert contents[4]["parts"][0]["text"] == "And what about remedies?"
