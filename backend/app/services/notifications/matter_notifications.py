import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.notification import Notification
from app.models.lawyer import LegalMatter, MatterMessage, LawyerProfile, LawyerVerificationStatus
from app.models.user import User, OrganizationMember
from app.models.base import generate_uuid, utc_now

logger = logging.getLogger(__name__)

async def create_matter_message_notification(
    db: AsyncSession,
    matter: LegalMatter,
    message: MatterMessage,
    sender_user: User,
) -> Optional[Notification]:
    """
    Creates and persists an in-app Notification for the appropriate recipient of a matter message:
    - If sender is CLIENT: recipient is matter's assigned lawyer or legal manager in matter.lawyer_organization_id.
    - If sender is LAWYER: recipient is matter.client_user_id in matter.client_organization_id.
    
    Safeguards:
    - Never notifies the sender about their own message.
    - Never notifies clients of lawyer internal chambers notes.
    - Uses deterministic deduplication key 'matter_msg_{message.id}' to prevent duplicates.
    - Respects tenant and user isolation boundaries.
    - Fallback: Resolves recipient and organization from matter assigned lawyer, lawyer profile, or organization membership.
    """
    try:
        # Internal notes are strictly for legal chambers; client must not be notified
        if message.is_internal_note:
            return None

        recipient_user_id = None
        recipient_org_id = None

        if message.sender_type == "CLIENT":
            # 1. Primary: Assigned lawyer on the matter
            recipient_user_id = matter.lawyer_user_id
            recipient_org_id = matter.lawyer_organization_id

            # 2. If lawyer user not assigned, resolve from lawyer organization's verified profile or legal manager
            if not recipient_user_id and recipient_org_id:
                stmt_prof = select(LawyerProfile.user_id).where(
                    LawyerProfile.organization_id == recipient_org_id,
                    LawyerProfile.verification_status == LawyerVerificationStatus.VERIFIED.value
                ).limit(1)
                res_prof = await db.execute(stmt_prof)
                recipient_user_id = res_prof.scalar_one_or_none()

                if not recipient_user_id:
                    stmt_mem = select(OrganizationMember.user_id).where(
                        OrganizationMember.organization_id == recipient_org_id,
                        OrganizationMember.role.in_(["LEGAL_MANAGER", "OWNER", "ADMIN", "LAWYER"]),
                        OrganizationMember.status == "ACTIVE"
                    ).limit(1)
                    res_mem = await db.execute(stmt_mem)
                    recipient_user_id = res_mem.scalar_one_or_none()

                if recipient_user_id and not matter.lawyer_user_id:
                    matter.lawyer_user_id = recipient_user_id

            # 3. If recipient_org_id missing, resolve from lawyer profile or active membership
            if not recipient_org_id and recipient_user_id:
                stmt_lp = select(LawyerProfile.organization_id).where(LawyerProfile.user_id == recipient_user_id)
                res_lp = await db.execute(stmt_lp)
                recipient_org_id = res_lp.scalar_one_or_none()

                if not recipient_org_id:
                    stmt_om = select(OrganizationMember.organization_id).where(
                        OrganizationMember.user_id == recipient_user_id,
                        OrganizationMember.status == "ACTIVE"
                    ).limit(1)
                    res_om = await db.execute(stmt_om)
                    recipient_org_id = res_om.scalar_one_or_none()

                if recipient_org_id and not matter.lawyer_organization_id:
                    matter.lawyer_organization_id = recipient_org_id

        else: # LAWYER sender -> notify CLIENT
            recipient_user_id = matter.client_user_id
            recipient_org_id = matter.client_organization_id

            if not recipient_user_id and recipient_org_id:
                stmt_mem = select(OrganizationMember.user_id).where(
                    OrganizationMember.organization_id == recipient_org_id,
                    OrganizationMember.status == "ACTIVE"
                ).limit(1)
                res_mem = await db.execute(stmt_mem)
                recipient_user_id = res_mem.scalar_one_or_none()

            if not recipient_org_id and recipient_user_id:
                stmt_om = select(OrganizationMember.organization_id).where(
                    OrganizationMember.user_id == recipient_user_id,
                    OrganizationMember.status == "ACTIVE"
                ).limit(1)
                res_om = await db.execute(stmt_om)
                recipient_org_id = res_om.scalar_one_or_none()

        # Validate recipient exists and is not the sender
        if not recipient_user_id or recipient_user_id == sender_user.id:
            return None

        if not recipient_org_id:
            logger.warning(
                f"Notification skipped: Could not resolve recipient organization ID for matter {matter.id}, recipient {recipient_user_id}"
            )
            return None

        # Check deduplication
        dedup_key = f"matter_msg_{message.id}"
        existing_res = await db.execute(
            select(Notification.id).where(Notification.deduplication_key == dedup_key)
        )
        if existing_res.scalar_one_or_none():
            logger.info(f"Notification with key {dedup_key} already exists. Skipping duplicate.")
            return None

        # Sanitize message preview: limit length, preserve privacy
        preview_text = (message.message_text or "").strip()
        if len(preview_text) > 100:
            preview_text = preview_text[:97] + "..."

        sender_name = sender_user.full_name or "Participant"
        title = f"New message on {matter.matter_code}"
        msg_body = f"{sender_name}: {preview_text}" if preview_text else f"New message from {sender_name}."

        notif = Notification(
            id=generate_uuid(),
            organization_id=recipient_org_id,
            user_id=recipient_user_id,
            contract_id=matter.contract_id,
            event_type="MATTER_MESSAGE_RECEIVED",
            priority="IMPORTANT",
            title=title,
            message=msg_body,
            scheduled_at=utc_now(),
            sent_at=utc_now(),
            delivery_channel="IN_APP",
            delivery_status="SENT",
            is_read=False,
            deduplication_key=dedup_key,
        )
        db.add(notif)
        await db.flush()
        return notif
    except Exception as e:
        logger.error(
            f"Failed to create message notification: {type(e).__name__} - {str(e)}"
        )
        return None
