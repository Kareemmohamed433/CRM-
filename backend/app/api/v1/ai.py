from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import User, FollowUp, Activity, Lead, PriorityLevel, FollowUpStatus, ActivityType
from backend.app.schemas.ai import (
    DailyBriefingResponse, AIChatRequest, AIChatResponse, AIActionDraft
)
from backend.app.services.ai_service import generate_daily_briefing, process_ai_chat_command
from backend.app.services.audit_service import log_audit_event

router = APIRouter(prefix="/ai", tags=["AI Assistant & Tools"])


@router.get("/briefing", response_model=DailyBriefingResponse)
def get_daily_briefing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return generate_daily_briefing(db=db, current_user=current_user)


@router.post("/chat", response_model=AIChatResponse)
def chat_with_crm_assistant(
    req: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    last_user_message = next(
        (m.content for m in reversed(req.messages) if m.role == "user"), ""
    )
    if not last_user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    messages_history = [{"role": m.role, "content": m.content} for m in req.messages]
    response = process_ai_chat_command(
        db=db,
        current_user=current_user,
        user_query=last_user_message,
        lead_id=req.lead_id,
        current_context=req.current_context,
        messages_history=messages_history,
    )
    return response


class ExecuteActionRequest(BaseModel):
    action: AIActionDraft


@router.post("/execute-action")
def execute_approved_ai_action(
    req: ExecuteActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes an action proposed by the AI assistant ONLY after explicit user confirmation.
    """
    draft = req.action
    payload = draft.payload

    if draft.action_type == "create_followup":
        lead_id = payload.get("lead_id")
        lead = db.query(Lead).filter(Lead.id == lead_id, Lead.company_id == current_user.company_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        due_date_str = payload.get("due_date")
        due_date = datetime.fromisoformat(due_date_str) if due_date_str else datetime.utcnow()

        new_f = FollowUp(
            company_id=current_user.company_id,
            lead_id=lead.id,
            assigned_user_id=current_user.id,
            team_id=lead.team_id,
            follow_up_type=payload.get("follow_up_type", "Call"),
            purpose=payload.get("purpose", "متابعة مجدولة عبر المساعد الذكي"),
            due_date=due_date,
            priority=PriorityLevel.HIGH,
            status=FollowUpStatus.PENDING,
            notes="تم الإنشاء والموافقة عبر المساعد الذكي Nexora AI"
        )
        db.add(new_f)
        lead.next_followup_date = due_date

        log_audit_event(
            db=db,
            company_id=current_user.company_id,
            action="AI_CREATE_FOLLOWUP",
            entity_type="FollowUp",
            entity_id=lead.id,
            actor_id=current_user.id,
            after_state={"due_date": due_date.isoformat(), "purpose": new_f.purpose}
        )

        db.commit()
        return {"status": "success", "message": "تم تأكيد وإنشاء المتابعة بنجاح في النظام."}

    if draft.action_type == "create_lead":
        from backend.app.services.crm_operator_service import get_crm_operator
        from backend.app.schemas.crm_actions import CreateLeadDraft
        lead_draft = CreateLeadDraft(**payload)
        res = get_crm_operator()._execute_create_lead(
            db=db,
            current_user=current_user,
            draft=lead_draft,
            ctx={"draft": payload}
        )
        if res.execution_result and res.execution_result.get("success"):
            return {
                "status": "success",
                "message": res.reply,
                "lead_id": res.execution_result.get("lead_id"),
                "full_name": res.execution_result.get("full_name")
            }
        else:
            raise HTTPException(status_code=400, detail=res.reply)

    raise HTTPException(status_code=400, detail=f"Unsupported action type: {draft.action_type}")
