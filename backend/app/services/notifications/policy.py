import json
from enum import Enum
from typing import Tuple, List, Optional, Any
from datetime import datetime, timezone

class NotificationPriority(str, Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    INFORMATIONAL = "INFORMATIONAL"

def parse_intervals(intervals_json_or_str: Optional[str]) -> List[int]:
    if not intervals_json_or_str:
        return [30, 7, 1]
    try:
        data = json.loads(intervals_json_or_str)
        if isinstance(data, list):
            return [int(x) for x in data]
    except Exception:
        pass
    return [30, 7, 1]

def generate_deduplication_key(
    organization_id: str,
    contract_id: Optional[str],
    event_type: str,
    target_date: str,
    interval_marker: str
) -> str:
    """
    Constructs a deterministic, unique deduplication key for a reminder.
    Example: 'tenant-123:ctr-456:RENEWAL_NOTICE:2026-12-01:30d'
    """
    cid = contract_id or "global"
    return f"{organization_id}:{cid}:{event_type}:{target_date}:{interval_marker}"

def is_notification_eligible(
    priority: str,
    event_type: str,
    email_enabled_globally: bool,
    user_pref: Optional[Any] = None,
    is_user_marked_important: bool = False
) -> Tuple[bool, str, str]:
    """
    Evaluates whether an event qualifies for notification delivery.
    Returns: (is_eligible, channel, reason)
    channel is 'EMAIL', 'IN_APP', or 'BOTH'.
    """
    # 1. In-app notifications are always eligible for the notification center
    if not email_enabled_globally:
        return True, "IN_APP", "Email disabled globally in config; eligible for in-app center only."

    if not user_pref or not user_pref.email_notifications_enabled:
        return True, "IN_APP", "User has email notifications disabled in preferences."

    # 2. Category preference checks
    if "RENEWAL" in event_type and not getattr(user_pref, "renewal_reminders", True):
        return True, "IN_APP", "User disabled renewal reminders."
    if "NOTICE" in event_type and not getattr(user_pref, "notice_deadline_reminders", True):
        return True, "IN_APP", "User disabled notice deadline reminders."
    if "OBLIGATION" in event_type and not getattr(user_pref, "obligation_reminders", True):
        return True, "IN_APP", "User disabled obligation reminders."
    if "APPROVAL" in event_type and not getattr(user_pref, "approval_reminders", True):
        return True, "IN_APP", "User disabled approval reminders."

    # 3. Priority policy rules
    if priority == NotificationPriority.CRITICAL:
        # Critical events always qualify for email (subject to rate limiting & dedup)
        return True, "BOTH", "Critical priority event eligible for email delivery."

    if priority == NotificationPriority.IMPORTANT or is_user_marked_important:
        # Important events qualify if allowed by category preferences
        return True, "BOTH", "Important priority event eligible for email delivery."

    # 4. Informational events: NEVER send email by default
    return True, "IN_APP", "Informational event: in-app notification only."
