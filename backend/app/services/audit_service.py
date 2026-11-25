from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.models import AuditLog


def log_audit_event(
    db: Session,
    company_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    actor_id: Optional[int] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
):
    audit_entry = AuditLog(
        company_id=company_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state or {},
        after_state=after_state or {},
    )
    db.add(audit_entry)
    db.commit()
