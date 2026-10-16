import logging
import smtplib
import socket
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

@dataclass
class EmailDeliveryResult:
    success: bool
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 1

class EmailProvider(ABC):
    @abstractmethod
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> EmailDeliveryResult:
        """Sends an email and returns the delivery result."""
        pass

class DisabledEmailProvider(EmailProvider):
    """
    Safe fallback when email sending is disabled or not configured.
    Explicitly reports unavailable status without disclosing sensitive information.
    """
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> EmailDeliveryResult:
        missing = []
        if not (settings.EMAIL_SERVICE_ENABLED or settings.EMAIL_ENABLED):
            missing.append("EMAIL_SERVICE_ENABLED is false")
        if not settings.SMTP_HOST:
            missing.append("SMTP_HOST is empty")

        detail = f"Email delivery is unconfigured or disabled ({', '.join(missing) if missing else 'EMAIL_SERVICE_ENABLED=false'})."
        logger.info(
            f"[DisabledEmailProvider] Delivery suppressed for recipient {to_email}. "
            f"Subject: '{subject}'. Reason: {detail}"
        )
        return EmailDeliveryResult(
            success=False,
            error_message=detail,
            attempts=0
        )

class MockEmailProvider(EmailProvider):
    """
    In-memory email provider for deterministic automated testing.
    Supports simulated failures, timeouts, and provider rejections.
    """
    def __init__(self):
        self.sent_emails: List[Dict[str, Any]] = []
        self.simulate_failure: bool = False
        self.simulate_timeout: bool = False
        self.simulate_rejection: bool = False

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> EmailDeliveryResult:
        if self.simulate_timeout:
            logger.warning(f"[MockEmailProvider] Simulated timeout for delivery to {to_email}")
            return EmailDeliveryResult(
                success=False,
                error_message="Simulated upstream timeout during email transmission.",
                attempts=settings.EMAIL_MAX_RETRIES
            )

        if self.simulate_rejection:
            logger.warning(f"[MockEmailProvider] Simulated provider rejection for recipient {to_email}")
            return EmailDeliveryResult(
                success=False,
                error_message="Simulated upstream recipient address rejection (550 Mailbox unavailable).",
                attempts=1
            )

        if self.simulate_failure:
            logger.warning(f"[MockEmailProvider] Simulated general delivery failure to {to_email}")
            return EmailDeliveryResult(
                success=False,
                error_message="Simulated email transport network failure.",
                attempts=settings.EMAIL_MAX_RETRIES
            )

        msg_id = f"mock-msg-{uuid.uuid4()}"
        record = {
            "id": msg_id,
            "to": to_email,
            "subject": subject,
            "html": html_body,
            "text": text_body,
            "timestamp": time.time()
        }
        self.sent_emails.append(record)
        logger.info(f"[MockEmailProvider] Recorded mock email to {to_email} with subject '{subject}'")
        return EmailDeliveryResult(success=True, provider_message_id=msg_id, attempts=1)

    def clear(self) -> None:
        self.sent_emails.clear()
        self.simulate_failure = False
        self.simulate_timeout = False
        self.simulate_rejection = False

    def get_sent_emails(self) -> List[Dict[str, Any]]:
        return list(self.sent_emails)

    def find_email(self, to_email: str, subject_keyword: Optional[str] = None) -> Optional[Dict[str, Any]]:
        for item in reversed(self.sent_emails):
            if item["to"] == to_email:
                if subject_keyword is None or subject_keyword.lower() in item["subject"].lower():
                    return item
        return None

class SMTPEmailProvider(EmailProvider):
    """
    Production-grade SMTP provider supporting STARTTLS, authentication,
    bounded retries, connection timeouts, and secret-safe error sanitization.
    """
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: Optional[bool] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None
    ):
        self.host = host if host is not None else settings.SMTP_HOST
        self.port = port if port is not None else settings.SMTP_PORT
        self.username = username if username is not None else settings.SMTP_USERNAME
        self.password = password if password is not None else settings.SMTP_PASSWORD
        self.from_email = from_email if from_email is not None else (settings.EMAIL_FROM_ADDRESS or settings.EMAIL_FROM)
        self.use_tls = use_tls if use_tls is not None else settings.EMAIL_USE_TLS
        self.timeout = timeout if timeout is not None else settings.EMAIL_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.EMAIL_MAX_RETRIES

    def _sanitize_error(self, exc: Exception) -> str:
        """Strips potential credentials or server paths from error strings."""
        raw = str(exc)
        if self.password and self.password in raw:
            raw = raw.replace(self.password, "******")
        if self.username and self.username in raw:
            raw = raw.replace(self.username, "[USER]")
        return raw[:250]

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> EmailDeliveryResult:
        if not self.host or not self.host.strip():
            return EmailDeliveryResult(
                success=False,
                error_message="SMTP_HOST is not configured.",
                attempts=0
            )

        msg_id = f"smtp-{uuid.uuid4()}"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg["Message-ID"] = f"<{msg_id}@contractly.internal>"

        part_text = MIMEText(text_body, "plain", "utf-8")
        part_html = MIMEText(html_body, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        last_error = None
        attempts = 0

        for attempt in range(1, self.max_retries + 1):
            attempts = attempt
            try:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    if self.use_tls:
                        server.starttls()
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    
                    refused = server.sendmail(self.from_email, [to_email], msg.as_string())
                    if refused:
                        sanitized_refused = self._sanitize_error(Exception(str(refused)))
                        logger.warning(f"[SMTPEmailProvider] Recipient rejected: {to_email}")
                        return EmailDeliveryResult(
                            success=False,
                            error_message=f"Recipient address refused: {sanitized_refused}",
                            attempts=attempts
                        )

                logger.info(f"[SMTPEmailProvider] Successfully delivered email to {to_email}: '{subject}' (attempt {attempt})")
                return EmailDeliveryResult(
                    success=True,
                    provider_message_id=msg_id,
                    attempts=attempts
                )
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, socket.timeout, TimeoutError, ConnectionError) as net_err:
                last_error = self._sanitize_error(net_err)
                logger.warning(f"[SMTPEmailProvider] Connection error on attempt {attempt}/{self.max_retries}: {last_error}")
                if attempt < self.max_retries:
                    time.sleep(0.1 * attempt)
            except smtplib.SMTPAuthenticationError as auth_err:
                # Do not retry bad credentials
                last_error = self._sanitize_error(auth_err)
                logger.error(f"[SMTPEmailProvider] Authentication error: {last_error}")
                return EmailDeliveryResult(
                    success=False,
                    error_message=f"SMTP authentication failure: {last_error}",
                    attempts=attempts
                )
            except Exception as exc:
                last_error = self._sanitize_error(exc)
                logger.error(f"[SMTPEmailProvider] Delivery exception on attempt {attempt}: {last_error}")
                if attempt < self.max_retries:
                    time.sleep(0.1 * attempt)

        return EmailDeliveryResult(
            success=False,
            error_message=f"SMTP delivery failed after {attempts} attempts: {last_error}",
            attempts=attempts
        )

class TransactionalEmailProvider(EmailProvider):
    """
    Adapter for transactional HTTP email APIs (e.g. SendGrid, Resend, Postmark).
    """
    def __init__(self, api_key: Optional[str] = None, from_email: Optional[str] = None):
        self.api_key = api_key
        self.from_email = from_email or (settings.EMAIL_FROM_ADDRESS or settings.EMAIL_FROM)

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> EmailDeliveryResult:
        if not self.api_key:
            return EmailDeliveryResult(
                success=False,
                error_message="Transactional email API key is not configured.",
                attempts=0
            )
        # Production HTTP client transmission stub
        return EmailDeliveryResult(
            success=False,
            error_message="Transactional API provider is configured in standby mode.",
            attempts=1
        )

_mock_instance: Optional[MockEmailProvider] = None

def get_email_provider() -> EmailProvider:
    global _mock_instance
    is_enabled = settings.EMAIL_SERVICE_ENABLED or settings.EMAIL_ENABLED
    if not is_enabled:
        return DisabledEmailProvider()

    provider_name = (settings.EMAIL_PROVIDER or "smtp").strip().lower()
    if provider_name == "mock":
        if _mock_instance is None:
            _mock_instance = MockEmailProvider()
        return _mock_instance

    if provider_name == "smtp":
        return SMTPEmailProvider()

    if provider_name in ("transactional", "sendgrid", "resend"):
        return TransactionalEmailProvider()

    return DisabledEmailProvider()

def get_mock_email_provider() -> MockEmailProvider:
    """Returns the singleton mock email provider instance for inspection during testing."""
    global _mock_instance
    if _mock_instance is None:
        _mock_instance = MockEmailProvider()
    return _mock_instance

class EmailDeliveryService:
    """
    High-level asynchronous email delivery service wrapper.
    Ensures safe error logging and consistent return semantics.
    """
    @staticmethod
    def get_provider() -> EmailProvider:
        return get_email_provider()

    @staticmethod
    async def send_email(
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> EmailDeliveryResult:
        provider = get_email_provider()
        return provider.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

email_service = EmailDeliveryService()

def get_email_service_health() -> Dict[str, Any]:
    """
    Returns safe, non-sensitive operational readiness diagnostics for the email service.
    Guarantees that credentials, passwords, and API keys are NEVER exposed.
    """
    is_enabled = bool(settings.EMAIL_SERVICE_ENABLED or settings.EMAIL_ENABLED)
    provider_name = (settings.EMAIL_PROVIDER or "smtp").strip().lower()

    missing = []
    if not is_enabled:
        missing.append("EMAIL_SERVICE_ENABLED=false")

    if provider_name == "smtp":
        if not settings.SMTP_HOST:
            missing.append("SMTP_HOST")
        if not settings.SMTP_USERNAME:
            missing.append("SMTP_USERNAME")
        if not settings.SMTP_PASSWORD:
            missing.append("SMTP_CREDENTIAL")
    elif provider_name in ("transactional", "sendgrid", "resend"):
        if not getattr(settings, "TRANSACTIONAL_EMAIL_API_KEY", None):
            missing.append("TRANSACTIONAL_EMAIL_API_KEY")

    is_configured = (len(missing) == 0) and is_enabled
    if provider_name == "mock" and is_enabled:
        is_configured = True
        missing = []

    return {
        "enabled": is_enabled,
        "provider": provider_name,
        "status": "READY" if is_configured else ("UNCONFIGURED" if is_enabled else "DISABLED"),
        "is_configured": is_configured,
        "configured": is_configured,
        "missing_configuration": missing,
        "missing_fields": missing,
        "diagnostics": {
            "host_configured": bool(settings.SMTP_HOST),
            "port": settings.SMTP_PORT,
            "username_configured": bool(settings.SMTP_USERNAME),
            "tls_enabled": settings.EMAIL_USE_TLS,
            "from_address": settings.EMAIL_FROM_ADDRESS or settings.EMAIL_FROM,
            "timeout_seconds": settings.EMAIL_TIMEOUT_SECONDS,
            "max_retries": settings.EMAIL_MAX_RETRIES,
            "app_base_url": settings.APP_BASE_URL
        }
    }
