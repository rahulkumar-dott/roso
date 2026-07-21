"""Module 10 - Audit Logging (cross-cutting).

`log()` only stages the row via `db.add()`; it does not commit. Callers should
commit alongside their own primary-action commit so the audit entry is
persisted atomically with the change it describes.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AuditLog


def log(
    db: Session,
    *,
    action: str,
    entity_id: str,
    field: str | None = None,
    before: Any = None,
    after: Any = None,
    actor: str = "admin_poc",
) -> AuditLog:
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_id=entity_id,
        field=field,
        before_value=before,
        after_value=after,
    )
    db.add(entry)
    return entry


def recent(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "actor": row.actor,
            "action": row.action,
            "entity_id": row.entity_id,
            "field": row.field,
            "before_value": row.before_value,
            "after_value": row.after_value,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
