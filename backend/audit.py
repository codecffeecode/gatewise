import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        actor_user_id=actor_user_id,
        org_id=org_id,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        metadata_=metadata,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
