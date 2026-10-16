from app.services.email.provider import (
    EmailProvider,
    EmailDeliveryResult,
    SMTPEmailProvider,
    MockEmailProvider,
    DisabledEmailProvider,
    get_email_provider,
    get_mock_email_provider,
    email_service,
    get_email_service_health
)
from app.services.email.templates import (
    render_renewal_notice_email,
    render_overdue_obligation_email,
    render_critical_deadline_email,
    render_approval_request_email,
    render_test_notification_email,
    render_verification_email,
    render_password_reset_email,
    render_invitation_email
)

__all__ = [
    "EmailProvider",
    "EmailDeliveryResult",
    "SMTPEmailProvider",
    "MockEmailProvider",
    "DisabledEmailProvider",
    "get_email_provider",
    "get_mock_email_provider",
    "email_service",
    "get_email_service_health",
    "render_renewal_notice_email",
    "render_overdue_obligation_email",
    "render_critical_deadline_email",
    "render_approval_request_email",
    "render_test_notification_email",
    "render_verification_email",
    "render_password_reset_email",
    "render_invitation_email"
]

