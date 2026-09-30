from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit_event(
    db: Session,
    *,
    actor_id: UUID | None,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    purpose: str | None,
    ip_address: str | None,
    user_agent: str | None,
    success: bool,
) -> AuditLog:
    previous = db.scalar(
        select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
    )
    previous_hash = previous.row_hash if previous else ""
    created_at = datetime.now(timezone.utc)
    event = {
        "actor_id": str(actor_id) if actor_id else None,
        "actor_role": actor_role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "purpose": purpose,
        "success": success,
        "created_at": created_at.isoformat(),
        "prev_hash": previous_hash,
    }
    row_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    audit_log = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        purpose=purpose,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        prev_hash=previous_hash,
        row_hash=row_hash,
        created_at=created_at,
    )
    db.add(audit_log)
    return audit_log
