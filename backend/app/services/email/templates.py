from typing import Tuple
from app.config import settings

def _base_email_layout(
    headline: str,
    contract_title: str,
    event_type_label: str,
    due_date: str,
    urgency_badge: str,
    why_it_matters: str,
    recommended_action: str,
    action_url: str,
    action_button_label: str
) -> Tuple[str, str]:
    """
    Renders standardized HTML and plain text email following Contractly's design palette:
    Warm Ivory (#F7F3EA), Charcoal (#242321), Deep Olive (#3F4634), Sand (#DED6C8).
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{headline} - Contractly</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F7F3EA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #242321;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F7F3EA; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 600px; background-color: #FCFAF5; border: 1px solid #DED6C8; border-radius: 4px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <!-- Header -->
          <tr>
            <td style="padding: 24px 32px; border-bottom: 1px solid #DED6C8; background-color: #FCFAF5;">
              <span style="font-family: Georgia, serif; font-size: 20px; font-weight: bold; letter-spacing: 2px; color: #242321;">CONTRACTLY</span>
              <span style="font-family: monospace; font-size: 11px; color: #6F6A61; margin-left: 12px; text-transform: uppercase; letter-spacing: 1px;">Contracts, handled with clarity</span>
            </td>
          </tr>

          <!-- Main Body -->
          <tr>
            <td style="padding: 32px;">
              <div style="margin-bottom: 20px;">
                <span style="display: inline-block; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; padding: 4px 10px; border-radius: 2px; background-color: #EFECE3; color: #3F4634; border: 1px solid #DED6C8;">
                  {urgency_badge}
                </span>
                <h1 style="font-family: Georgia, serif; font-size: 22px; font-weight: bold; color: #242321; margin: 16px 0 8px 0;">
                  {headline}
                </h1>
                <p style="font-size: 13px; color: #6F6A61; margin: 0;">
                  Contract: <strong>{contract_title}</strong>
                </p>
              </div>

              <!-- Metadata Box -->
              <table role="presentation" width="100%" style="background-color: #F7F3EA; border: 1px solid #DED6C8; border-radius: 2px; margin-bottom: 24px; padding: 16px;">
                <tr>
                  <td style="padding: 6px 12px; font-size: 12px; color: #6F6A61; width: 140px; font-weight: 600; text-transform: uppercase; font-family: monospace;">Event Type:</td>
                  <td style="padding: 6px 12px; font-size: 13px; color: #242321; font-weight: 600;">{event_type_label}</td>
                </tr>
                <tr>
                  <td style="padding: 6px 12px; font-size: 12px; color: #6F6A61; font-weight: 600; text-transform: uppercase; font-family: monospace;">Target Date:</td>
                  <td style="padding: 6px 12px; font-size: 13px; color: #242321; font-weight: 600; font-family: monospace;">{due_date}</td>
                </tr>
              </table>

              <!-- Explanation & Actions -->
              <div style="margin-bottom: 20px;">
                <h3 style="font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; color: #242321; margin-bottom: 6px;">Why This Needs Your Attention</h3>
                <p style="font-size: 14px; line-height: 1.5; color: #3A3835; margin: 0;">{why_it_matters}</p>
              </div>

              <div style="margin-bottom: 28px;">
                <h3 style="font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; color: #242321; margin-bottom: 6px;">Recommended Next Action</h3>
                <p style="font-size: 14px; line-height: 1.5; color: #3A3835; margin: 0;">{recommended_action}</p>
              </div>

              <!-- CTA Button -->
              <div style="text-align: left; margin-bottom: 24px;">
                <a href="{action_url}" style="display: inline-block; background-color: #3F4634; color: #FCFAF5; font-size: 13px; font-weight: 600; text-decoration: none; padding: 10px 22px; border-radius: 2px;">
                  {action_button_label} →
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #F7F3EA; border-top: 1px solid #DED6C8; font-size: 11px; color: #6F6A61; line-height: 1.5;">
              <p style="margin: 0 0 4px 0;">
                You received this notification because your Contractly account is assigned to this contract or responsibility.
              </p>
              <p style="margin: 0;">
                Confidentiality Notice: Contractly emails contain operational deadline notices only. Complete contracts and sensitive terms remain secured inside your authenticated workspace.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    text = f"""CONTRACTLY — Contracts, handled with clarity
==================================================

{urgency_badge}: {headline}
Contract: {contract_title}

Event Type: {event_type_label}
Target Date: {due_date}

WHY THIS NEEDS YOUR ATTENTION:
{why_it_matters}

RECOMMENDED NEXT ACTION:
{recommended_action}

Access your Contractly workspace:
{action_url}

--------------------------------------------------
Confidentiality Notice: Complete contracts and sensitive terms remain secured inside your authenticated workspace.
"""
    return html, text


def render_renewal_notice_email(
    contract_title: str,
    days_remaining: int,
    notice_deadline: str,
    renewal_date: str,
    contract_id: str
) -> Tuple[str, str]:
    action_url = f"{settings.APP_BASE_URL}/"
    urgency_badge = "CRITICAL DEADLINE" if days_remaining <= 7 else "IMPORTANT REMINDER"
    headline = f"Renewal Notice Deadline Approaching ({days_remaining} Days Remaining)"
    why_it_matters = (
        f"The contractual renewal notice deadline is on {notice_deadline}. If formal notice of non-renewal "
        f"or renegotiation is not tendered by this date, the contract may automatically renew on {renewal_date}."
    )
    recommended_action = (
        "Review the counterparty performance, assess budget commitments, and record your decision in the "
        "Contractly Watchlist to either proceed with renewal or issue formal notice."
    )
    return _base_email_layout(
        headline=headline,
        contract_title=contract_title,
        event_type_label="Renewal Notice Deadline",
        due_date=notice_deadline,
        urgency_badge=urgency_badge,
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=action_url,
        action_button_label="Review Contract Renewal"
    )


def render_overdue_obligation_email(
    contract_title: str,
    obligation_title: str,
    due_date: str,
    responsible_party: str,
    contract_id: str
) -> Tuple[str, str]:
    action_url = f"{settings.APP_BASE_URL}/"
    headline = f"Overdue Contract Obligation: {obligation_title}"
    why_it_matters = (
        f"The affirmative contractual obligation '{obligation_title}' was scheduled for completion by {due_date}. "
        f"Failure to fulfill or provide compliance evidence may trigger penalty clauses or material breach conditions."
    )
    recommended_action = (
        "Submit required compliance evidence or update the obligation resolution status in the Contractly Watch dashboard."
    )
    return _base_email_layout(
        headline=headline,
        contract_title=contract_title,
        event_type_label="Overdue Obligation",
        due_date=due_date,
        urgency_badge="CRITICAL ACTION REQUIRED",
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=action_url,
        action_button_label="View Obligation & Upload Evidence"
    )


def render_critical_deadline_email(
    contract_title: str,
    event_title: str,
    event_type: str,
    due_date: str,
    details: str,
    contract_id: str
) -> Tuple[str, str]:
    action_url = f"{settings.APP_BASE_URL}/"
    headline = f"Critical Contract Deadline: {event_title}"
    why_it_matters = details or f"An urgent contractual deadline ({event_type}) is due on {due_date}."
    recommended_action = "Review the contract in Contractly and complete the outstanding responsibility."
    return _base_email_layout(
        headline=headline,
        contract_title=contract_title,
        event_type_label=event_type,
        due_date=due_date,
        urgency_badge="CRITICAL",
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=action_url,
        action_button_label="Open Contract"
    )


def render_approval_request_email(
    contract_title: str,
    role: str,
    contract_id: str
) -> Tuple[str, str]:
    action_url = f"{settings.APP_BASE_URL}/"
    headline = f"Contract Approval Requested: {contract_title}"
    why_it_matters = (
        f"The contract has been submitted for formal lifecycle sign-off. As {role}, your review and decision "
        "are required before the agreement can advance to final signature and execution."
    )
    recommended_action = "Inspect redlines, clauses, and risk assessment in Contractly, then approve or reject with comments."
    return _base_email_layout(
        headline=headline,
        contract_title=contract_title,
        event_type_label="Contract Approval Step",
        due_date="Pending Review",
        urgency_badge="IMPORTANT",
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=action_url,
        action_button_label="Review & Approve Contract"
    )


def render_test_notification_email(
    recipient_email: str
) -> Tuple[str, str]:
    action_url = f"{settings.APP_BASE_URL}/"
    headline = "Test Notification — Contractly Email Delivery"
    why_it_matters = (
        "This is an administrative test email confirming that your email service configuration "
        "and SMTP transport are functioning correctly."
    )
    recommended_action = "No further action is required. Your Contractly email notifications are operational."
    return _base_email_layout(
        headline=headline,
        contract_title="System Configuration Check",
        event_type_label="Administrative Test",
        due_date="Now",
        urgency_badge="INFORMATIONAL",
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=action_url,
        action_button_label="Return to Workspace"
    )


def render_verification_email(
    full_name: str,
    verification_url: str
) -> Tuple[str, str, str]:
    subject = "[Contractly] Verify Your Account Email"
    headline = "Verify Your Contractly Account Email"
    why_it_matters = (
        f"Hello {full_name}, please confirm your email address to complete your account setup and enable "
        "verified alerts for your agreements and obligations."
    )
    recommended_action = "Click the button below to verify your email address. This verification link expires in 24 hours."
    html, text = _base_email_layout(
        headline=headline,
        contract_title="Account Security Verification",
        event_type_label="Email Verification",
        due_date="Expires in 24 hours",
        urgency_badge="ACCOUNT SECURITY",
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=verification_url,
        action_button_label="Verify Email Address"
    )
    return subject, html, text


def render_password_reset_email(
    full_name: str,
    reset_url: str
) -> Tuple[str, str, str]:
    subject = "[Contractly] Password Reset Request"
    headline = "Password Reset Request"
    why_it_matters = (
        f"Hello {full_name}, a request was received to reset the password for your Contractly account. "
        "If you did not initiate this request, you can safely ignore this email; your existing password remains secure."
    )
    recommended_action = "Click the link below to choose a new password. For security, this single-use link expires in 1 hour."
    html, text = _base_email_layout(
        headline=headline,
        contract_title="Account Security Alert",
        event_type_label="Password Reset",
        due_date="Expires in 1 hour",
        urgency_badge="SECURITY ACTION",
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=reset_url,
        action_button_label="Reset Your Password"
    )
    return subject, html, text


def render_invitation_email(
    org_name: str,
    inviter_name: str,
    role: str,
    invite_url: str
) -> Tuple[str, str, str]:
    subject = f"[Contractly] Invitation to join {org_name}"
    headline = f"You've been invited to join {org_name} on Contractly"
    why_it_matters = (
        f"{inviter_name} has invited you to collaborate in the '{org_name}' workspace as a {role.replace('_', ' ').title()}. "
        "Contractly provides a shared legal environment for reviewing contracts, tracking obligations, and managing approvals."
    )
    recommended_action = "Click below to review and accept your organization invitation. This invitation link expires in 7 days."
    html, text = _base_email_layout(
        headline=headline,
        contract_title=f"{org_name} Workspace",
        event_type_label="Organization Invitation",
        due_date="Expires in 7 days",
        urgency_badge="COLLABORATION INVITATION",
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        action_url=invite_url,
        action_button_label="Accept Workspace Invitation"
    )
    return subject, html, text


