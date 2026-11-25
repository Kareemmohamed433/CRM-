"""
Follow-up Tools for NEXORA AI CRM Assistant.
Handles customer-centric follow-up inquiries, scheduling, and outcome recording.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.models import FollowUp, Lead, User, FollowUpStatus, PriorityLevel, Activity, ActivityType
from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult
from backend.app.services.egyptian_nlp import parse_egyptian_date_time


@ai_tool_registry.register(
    name="get_customer_followups",
    description="استعراض كافة المتابعات والمهام الخاصة بعميل محدد لمعرفة تاريخ التواصل وحالة المتابعة.",
    category="followup",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"},
            "status": {"type": "string", "description": "تصفية بالحالة (PENDING, COMPLETED, OVERDUE)"}
        },
        "required": ["customer_id"]
    }
)
def get_customer_followups(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    status_filter = params.get("status")

    lead = db.query(Lead).filter(Lead.id == customer_id, Lead.company_id == user.company_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    q = db.query(FollowUp).filter(
        FollowUp.company_id == user.company_id,
        FollowUp.lead_id == customer_id
    )
    if status_filter:
        q = q.filter(FollowUp.status == status_filter)

    followups = q.order_by(desc(FollowUp.due_date)).all()
    items = []
    for f in followups:
        items.append({
            "id": f.id,
            "purpose": f.purpose,
            "due_date": f.due_date.strftime("%Y-%m-%d %I:%M %p") if f.due_date else None,
            "status": f.status.value if f.status else "PENDING",
            "priority": f.priority.value if f.priority else "MEDIUM",
            "notes": f.notes,
            "completion_outcome": f.completion_outcome
        })

    msg = f"يوجد {len(items)} متابعات مسجلة للعميل {lead.full_name}."
    return ToolResult(success=True, data=items, message=msg)


@ai_tool_registry.register(
    name="create_followup",
    description="تسجيل متابعة قادمة لعميل محدد مع تفاصيل الغرض والموعد.",
    category="followup",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"},
            "purpose": {"type": "string", "description": "غرض المتابعة (مثال: اتصال هاتفي لمناقشة طرق السداد)"},
            "due_date": {"type": "string", "description": "تاريخ ووقت المتابعة بصيغة ISO"},
            "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"], "description": "درجة الأولوية"},
            "notes": {"type": "string", "description": "ملاحظات إضافية"}
        },
        "required": ["customer_id", "purpose", "due_date"]
    }
)
def create_followup(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    purpose = (params.get("purpose") or "").strip()
    due_date_str = params.get("due_date")
    priority_str = params.get("priority", "MEDIUM").upper()
    notes = params.get("notes", "")

    lead = db.query(Lead).filter(Lead.id == customer_id, Lead.company_id == user.company_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    try:
        if "T" in due_date_str:
            due_dt = datetime.fromisoformat(due_date_str.replace("Z", ""))
        else:
            due_dt = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        parsed_dt, _ = parse_egyptian_date_time(due_date_str)
        if parsed_dt:
            due_dt = parsed_dt
        else:
            return ToolResult(success=False, error="Invalid date format", message="صيغة وقت المتابعة غير صحيحة.")

    priority_enum = PriorityLevel.MEDIUM
    if priority_str in PriorityLevel.__members__:
        priority_enum = PriorityLevel[priority_str]

    fu = FollowUp(
        company_id=user.company_id,
        lead_id=lead.id,
        assigned_user_id=lead.assigned_agent_id or user.id,
        created_by_id=user.id,
        purpose=purpose,
        due_date=due_dt,
        priority=priority_enum,
        status=FollowUpStatus.PENDING,
        notes=notes or ""
    )
    db.add(fu)
    lead.next_followup_date = due_dt
    db.commit()

    time_fmt = due_dt.strftime("%Y-%m-%d الساعة %I:%M %p")
    return ToolResult(
        success=True,
        data={"followup_id": fu.id, "due_date": due_dt.isoformat()},
        message=f"تم تسجيل متابعة جديدة مع العميل {lead.full_name} في {time_fmt}: {purpose}."
    )


@ai_tool_registry.register(
    name="complete_followup",
    description="إغلاق وتوثيق نتيجة متابعة مع عميل وتحديث المرحلة البيعية.",
    category="followup",
    parameters_schema={
        "properties": {
            "followup_id": {"type": "integer", "description": "معرف المتابعة (ID)"},
            "completion_outcome": {"type": "string", "description": "ملخص ما تم خلال المتابعة"}
        },
        "required": ["followup_id", "completion_outcome"]
    }
)
def complete_followup(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    followup_id = params.get("followup_id")
    outcome = (params.get("completion_outcome") or "").strip()

    fu = db.query(FollowUp).filter(FollowUp.id == followup_id, FollowUp.company_id == user.company_id).first()
    if not fu:
        return ToolResult(success=False, error="Follow-up not found", message=f"المتابعة رقم #{followup_id} غير موجودة.")

    fu.status = FollowUpStatus.COMPLETED
    fu.completed_at = datetime.utcnow()
    fu.completion_outcome = outcome

    if fu.lead_id:
        # Also log activity
        act = Activity(
            company_id=user.company_id,
            lead_id=fu.lead_id,
            user_id=user.id,
            activity_type=ActivityType.CALL,
            summary=f"إتمام متابعة ({fu.purpose}): {outcome}",
            outcome=outcome
        )
        db.add(act)

    db.commit()
    return ToolResult(
        success=True,
        data={"followup_id": fu.id},
        message=f"تم تسجيل إتمام المتابعة بنجاح وتوثيق النتيجة: {outcome}."
    )

