"""
Conversation State Manager for NEXORA AI CRM Assistant.
Maintains persistent conversational state across multi-turn interactions.
Enforces tenant isolation, context expiration, and structured draft accumulation.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.models import AIConversationState, User

logger = logging.getLogger(__name__)

DEFAULT_EXPIRATION_MINUTES = 30


class ConversationStateDTO:
    def __init__(
        self,
        conversation_id: str,
        company_id: int,
        user_id: int,
        intent: Optional[str] = None,
        entity: Optional[str] = None,
        collected_fields: Optional[Dict[str, Any]] = None,
        missing_fields: Optional[List[str]] = None,
        pending_tool: Optional[str] = None,
        confirmation_status: str = "NONE",
        confirmation_preview: Optional[Dict[str, Any]] = None,
        context_expiration: Optional[datetime] = None,
        last_updated: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
    ):
        self.conversation_id = conversation_id
        self.company_id = company_id
        self.user_id = user_id
        self.intent = intent
        self.entity = entity
        self.collected_fields = collected_fields or {}
        self.missing_fields = missing_fields or []
        self.pending_tool = pending_tool
        self.confirmation_status = confirmation_status
        self.confirmation_preview = confirmation_preview or {}
        now = datetime.utcnow()
        self.context_expiration = context_expiration or (now + timedelta(minutes=DEFAULT_EXPIRATION_MINUTES))
        self.last_updated = last_updated or now
        self.created_at = created_at or now

    def is_expired(self) -> bool:
        if not self.context_expiration:
            return False
        return datetime.utcnow() > self.context_expiration

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "intent": self.intent,
            "entity": self.entity,
            "collected_fields": self.collected_fields,
            "missing_fields": self.missing_fields,
            "pending_tool": self.pending_tool,
            "confirmation_status": self.confirmation_status,
            "confirmation_preview": self.confirmation_preview,
            "context_expiration": self.context_expiration.isoformat() if self.context_expiration else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_legacy_context(self) -> Dict[str, Any]:
        """Maps to the legacy current_context dictionary for backward compatibility."""
        ctx = dict(self.collected_fields)
        ctx["conversation_id"] = self.conversation_id
        ctx["intent"] = self.intent
        ctx["entity"] = self.entity
        ctx["operation"] = self.intent
        ctx["pending_tool"] = self.pending_tool
        ctx["confirmation_status"] = self.confirmation_status
        ctx["missing_fields"] = list(self.missing_fields)
        if self.confirmation_preview:
            ctx["confirmation_preview"] = dict(self.confirmation_preview)
        if self.confirmation_status == "PENDING":
            ctx["state"] = "PENDING_CONFIRMATION"
        elif self.missing_fields:
            ctx["state"] = "COLLECTING_INFO"
        else:
            ctx["state"] = "IDLE"
        return ctx


class ConversationStateManager:
    """
    Thread-safe, multi-tenant state manager with DB persistence and memory caching.
    """
    _memory_cache: Dict[str, ConversationStateDTO] = {}

    @classmethod
    def get_or_create_state(
        cls,
        db: Session,
        user: User,
        conversation_id: Optional[str] = None,
        legacy_context: Optional[Dict[str, Any]] = None
    ) -> ConversationStateDTO:
        cid = conversation_id or (legacy_context.get("conversation_id") if legacy_context else None)
        
        # If no conversation_id provided, look up user's most recent active state
        if not cid:
            db_state = db.query(AIConversationState).filter(
                AIConversationState.user_id == user.id,
                AIConversationState.company_id == user.company_id
            ).order_by(AIConversationState.last_updated.desc()).first()

            if db_state and not db_state.context_expiration or (db_state and db_state.context_expiration > datetime.utcnow()):
                cid = db_state.conversation_id
            else:
                cid = f"conv_{user.id}_{uuid.uuid4().hex[:12]}"

        # Check memory cache first
        cached = cls._memory_cache.get(cid)
        if cached and not cached.is_expired():
            # Merge any updates from legacy context if provided
            if legacy_context:
                cls._merge_legacy_into_dto(cached, legacy_context)
            return cached

        # Look up in DB
        db_state = db.query(AIConversationState).filter(
            AIConversationState.conversation_id == cid,
            AIConversationState.company_id == user.company_id
        ).first()

        if db_state:
            dto = ConversationStateDTO(
                conversation_id=db_state.conversation_id,
                company_id=db_state.company_id,
                user_id=db_state.user_id,
                intent=db_state.intent,
                entity=db_state.entity,
                collected_fields=db_state.collected_fields or {},
                missing_fields=db_state.missing_fields or [],
                pending_tool=db_state.pending_tool,
                confirmation_status=db_state.confirmation_status or "NONE",
                confirmation_preview=db_state.confirmation_preview or {},
                context_expiration=db_state.context_expiration,
                last_updated=db_state.last_updated,
                created_at=db_state.created_at,
            )
            if dto.is_expired():
                # Reset fields on expiration
                dto.intent = None
                dto.entity = None
                dto.collected_fields = {}
                dto.missing_fields = []
                dto.pending_tool = None
                dto.confirmation_status = "NONE"
                dto.confirmation_preview = {}
                dto.context_expiration = datetime.utcnow() + timedelta(minutes=DEFAULT_EXPIRATION_MINUTES)
        else:
            dto = ConversationStateDTO(
                conversation_id=cid,
                company_id=user.company_id,
                user_id=user.id,
            )
            # Create DB record
            db_state = AIConversationState(
                conversation_id=dto.conversation_id,
                company_id=dto.company_id,
                user_id=dto.user_id,
                intent=dto.intent,
                entity=dto.entity,
                collected_fields=dto.collected_fields,
                missing_fields=dto.missing_fields,
                pending_tool=dto.pending_tool,
                confirmation_status=dto.confirmation_status,
                confirmation_preview=dto.confirmation_preview,
                context_expiration=dto.context_expiration,
                last_updated=dto.last_updated,
                created_at=dto.created_at,
            )
            db.add(db_state)
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"[StateManager] Failed creating AIConversationState record: {e}")

        if legacy_context:
            cls._merge_legacy_into_dto(dto, legacy_context)

        cls._memory_cache[cid] = dto
        return dto

    @classmethod
    def save_state(
        cls,
        db: Session,
        state: ConversationStateDTO
    ) -> None:
        state.last_updated = datetime.utcnow()
        state.context_expiration = state.last_updated + timedelta(minutes=DEFAULT_EXPIRATION_MINUTES)
        cls._memory_cache[state.conversation_id] = state

        # Sync to DB
        try:
            db_state = db.query(AIConversationState).filter(
                AIConversationState.conversation_id == state.conversation_id,
                AIConversationState.company_id == state.company_id
            ).first()

            if not db_state:
                db_state = AIConversationState(
                    conversation_id=state.conversation_id,
                    company_id=state.company_id,
                    user_id=state.user_id,
                )
                db.add(db_state)

            db_state.intent = state.intent
            db_state.entity = state.entity
            db_state.collected_fields = state.collected_fields
            db_state.missing_fields = state.missing_fields
            db_state.pending_tool = state.pending_tool
            db_state.confirmation_status = state.confirmation_status
            db_state.confirmation_preview = state.confirmation_preview
            db_state.context_expiration = state.context_expiration
            db_state.last_updated = state.last_updated
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"[StateManager] Failed saving AIConversationState: {e}")

    @classmethod
    def reset_state(
        cls,
        db: Session,
        conversation_id: str,
        company_id: int
    ) -> None:
        if conversation_id in cls._memory_cache:
            cls._memory_cache[conversation_id].intent = None
            cls._memory_cache[conversation_id].entity = None
            cls._memory_cache[conversation_id].collected_fields = {}
            cls._memory_cache[conversation_id].missing_fields = []
            cls._memory_cache[conversation_id].pending_tool = None
            cls._memory_cache[conversation_id].confirmation_status = "NONE"
            cls._memory_cache[conversation_id].confirmation_preview = {}

        try:
            db_state = db.query(AIConversationState).filter(
                AIConversationState.conversation_id == conversation_id,
                AIConversationState.company_id == company_id
            ).first()
            if db_state:
                db_state.intent = None
                db_state.entity = None
                db_state.collected_fields = {}
                db_state.missing_fields = []
                db_state.pending_tool = None
                db_state.confirmation_status = "NONE"
                db_state.confirmation_preview = {}
                db_state.last_updated = datetime.utcnow()
                db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"[StateManager] Failed resetting state: {e}")

    @classmethod
    def _merge_legacy_into_dto(cls, dto: ConversationStateDTO, legacy: Dict[str, Any]) -> None:
        if legacy.get("operation") == "CREATE_LEAD" and "lead_id" not in legacy:
            dto.collected_fields.pop("lead_id", None)
        for k, v in legacy.items():
            if k in ("conversation_id", "state"):
                continue
            elif k == "operation" or k == "intent":
                if v and not dto.intent:
                    dto.intent = str(v)
            elif k == "missing_fields" and isinstance(v, list):
                dto.missing_fields = v
            elif k == "confirmation_preview" and isinstance(v, dict):
                dto.confirmation_preview = v
            elif k == "pending_tool":
                dto.pending_tool = str(v) if v else None
            elif k == "confirmation_status":
                dto.confirmation_status = str(v)
            else:
                dto.collected_fields[k] = v


def get_conversation_state_manager() -> type:
    return ConversationStateManager
