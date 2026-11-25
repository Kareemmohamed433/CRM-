"""
Task Tools for NEXORA AI CRM Assistant.
Handles agenda retrieval, overdue/upcoming tracking, task creation with mandatory time,
updates, rescheduling, and completions.
"""

from datetime import datetime, timedelta, date, time
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from backend.app.models.models import (
    FollowUp, Appointment, Lead, User, UserRole, FollowUpStatus, PriorityLevel, Activity, ActivityType
)
from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult
from backend.app.services.egyptian_nlp import get_current_cairo_time, parse_egyptian_date_time


@ai_tool_registry.register(
    name="get_daily_agenda",
    description="استعراض الأجندة اليومية للموظف: المواعيد والمهام والمتابعات المجدولة لليوم أو لتاريخ محدد.",
    category="task",
    parameters_schema={
        "properties": {
            "target_date": {"type": "string", "description": "التاريخ المطلوب بصيغة YYYY-MM-DD (افتراضيًا اليوم)"}
        }
    }
)
def get_daily_agenda(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    cairo_now = get_current_cairo_time()
    t_date_str = params.get("target_date")
    if t_date_str:
        try:
            target_d = datetime.strptime(t_date_str, "%Y-%m-%d").date()
        except ValueError:
            target_d = cairo_now.date()
    else:
        target_d = cairo_now.date()

    day_start = datetime.combine(target_d, time.min)
    day_end = datetime.combine(target_d, time.max)

    # 1. Fetch FollowUp tasks
    tasks = db.query(FollowUp).filter(
        FollowUp.company_id == user.company_id,
        FollowUp.assigned_user_id == user.id,
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS, FollowUpStatus.DUE_TODAY]),
        FollowUp.due_date >= day_start,
        FollowUp.due_date <= day_end
    ).order_by(asc(FollowUp.due_date)).all()

    # 2. Fetch Appointments
    appts = db.query(Appointment).filter(
        Appointment.company_id == user.company_id,
        Appointment.user_id == user.id,
        Appointment.start_time >= day_start,
        Appointment.start_time <= day_end
    ).order_by(asc(Appointment.start_time)).all()

    # 3. Check for overdue tasks if querying today
    overdue_count = 0
    if target_d == cairo_now.date():
        overdue_count = db.query(FollowUp).filter(
            FollowUp.company_id == user.company_id,
            FollowUp.assigned_user_id == user.id,
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS, FollowUpStatus.OVERDUE]),
            FollowUp.due_date < day_start
        ).count()

    agenda_items = []
    for a in appts:
        lead_name = a.lead.full_name if a.lead else "عميل"
        t_str = a.start_time.strftime("%I:%M %p") if a.start_time else ""
        agenda_items.append({
            "type": "APPOINTMENT",
            "id": a.id,
            "title": a.title,
            "time": t_str,
            "client": lead_name,
            "location": a.location or "المقر",
            "status": a.status.value if a.status else "SCHEDULED"
        })

    for t in tasks:
        lead_name = t.lead.full_name if t.lead else "مهمة عامة"
        t_str = t.due_date.strftime("%I:%M %p") if t.due_date else ""
        agenda_items.append({
            "type": "TASK",
            "id": t.id,
            "title": t.purpose,
            "time": t_str,
            "client": lead_name,
            "priority": t.priority.value if t.priority else "MEDIUM",
            "status": t.status.value if t.status else "PENDING"
        })

    date_label = "اليوم" if target_d == cairo_now.date() else target_d.strftime("%Y-%m-%d")
    msg_lines = [f"أجندتك لـ {date_label}:"]
    if not agenda_items:
        msg_lines.append("لا توجد مواعيد أو مهام مجدولة.")
    else:
        for idx, item in enumerate(agenda_items, 1):
            if item["type"] == "APPOINTMENT":
                msg_lines.append(f"{idx}. موعد: {item['title']} مع {item['client']} الساعة {item['time']} ({item['location']})")
            else:
                msg_lines.append(f"{idx}. مهمة: {item['title']} للعميل {item['client']} الساعة {item['time']}")

    if overdue_count > 0:
        msg_lines.append(f"تنبيه: لديك {overdue_count} مهام متأخرة تحتاج متابعة عاجلة.")

    return ToolResult(
        success=True,
        data={
            "target_date": target_d.isoformat(),
            "appointments_count": len(appts),
            "tasks_count": len(tasks),
            "overdue_count": overdue_count,
            "items": agenda_items
        },
        message="\n".join(msg_lines)
    )


@ai_tool_registry.register(
    name="get_overdue_tasks",
    description="عرض كافة المهام والمتابعات المتأخرة التي تجاوزت موعد استحقاقها ولم تكتمل بعد.",
    category="task",
    parameters_schema={}
)
def get_overdue_tasks(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    cairo_now = get_current_cairo_time()
    today_start = datetime.combine(cairo_now.date(), time.min)

    overdue = db.query(FollowUp).filter(
        FollowUp.company_id == user.company_id,
        FollowUp.assigned_user_id == user.id,
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS, FollowUpStatus.OVERDUE]),
        FollowUp.due_date < today_start
    ).order_by(asc(FollowUp.due_date)).all()

    items = []
    for t in overdue:
        items.append({
            "id": t.id,
            "purpose": t.purpose,
            "lead_name": t.lead.full_name if t.lead else "بدون عميل",
            "due_date": t.due_date.strftime("%Y-%m-%d %I:%M %p") if t.due_date else None,
            "priority": t.priority.value if t.priority else "MEDIUM"
        })

    if not items:
        return ToolResult(success=True, data=[], message="ممتاز! لا توجد لديك أي مهام متأخرة.")

    msg = f"لديك {len(items)} مهام متأخرة:\n" + "\n".join(
        [f"- {t['purpose']} (العميل: {t['lead_name']}, كان مستحق: {t['due_date']})" for t in items[:10]]
    )
    return ToolResult(success=True, data=items, message=msg)


@ai_tool_registry.register(
    name="get_upcoming_tasks",
    description="عرض المهام والمتابعات المستقبلية للأيام القادمة.",
    category="task",
    parameters_schema={
        "properties": {
            "days": {"type": "integer", "description": "عدد الأيام القادمة للبحث (افتراضي 7)"}
        }
    }
)
def get_upcoming_tasks(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    days = min(params.get("days", 7), 30)
    cairo_now = get_current_cairo_time()
    start_d = datetime.combine(cairo_now.date() + timedelta(days=1), time.min)
    end_d = datetime.combine(cairo_now.date() + timedelta(days=days), time.max)

    tasks = db.query(FollowUp).filter(
        FollowUp.company_id == user.company_id,
        FollowUp.assigned_user_id == user.id,
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS]),
        FollowUp.due_date >= start_d,
        FollowUp.due_date <= end_d
    ).order_by(asc(FollowUp.due_date)).all()

    items = []
    for t in tasks:
        items.append({
            "id": t.id,
            "purpose": t.purpose,
            "lead_name": t.lead.full_name if t.lead else "عام",
            "due_date": t.due_date.strftime("%Y-%m-%d %I:%M %p") if t.due_date else None,
            "priority": t.priority.value if t.priority else "MEDIUM"
        })

    msg = f"لديك {len(items)} مهام مجدولة خلال الـ {days} أيام القادمة."
    return ToolResult(success=True, data=items, message=msg)


@ai_tool_registry.register(
    name="create_task",
    description="إنشاء مهمة أو تذكير متابعة جديد مع تحديد الوقت بدقة والعميل المرتبط.",
    category="task",
    parameters_schema={
        "properties": {
            "title": {"type": "string", "description": "موضوع المهمة أو تفاصيلها"},
            "due_date": {"type": "string", "description": "تاريخ ووقت المهمة بصيغة ISO (YYYY-MM-DDTHH:MM:SS)"},
            "customer_id": {"type": "integer", "description": "معرف العميل المرتبط (اختياري)"},
            "assigned_user_id": {"type": "integer", "description": "معرف الموظف المسند إليه (افتراضي المستخدم الحالي)"},
            "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"], "description": "درجة الأولوية"},
            "notes": {"type": "string", "description": "ملاحظات إضافية"}
        },
        "required": ["title", "due_date"]
    }
)
def create_task(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    title = (params.get("title") or "").strip()
    due_date_str = params.get("due_date")
    customer_id = params.get("customer_id")
    assigned_user_id = params.get("assigned_user_id") or user.id
    priority_str = params.get("priority", "MEDIUM").upper()
    notes = params.get("notes", "")

    if not title:
        return ToolResult(success=False, error="Title is required", message="يرجى توضيح موضوع المهمة.")

    if not due_date_str:
        return ToolResult(success=False, error="Due date and time are required", message="يرجى تحديد وقت وتاريخ المهمة.")

    # Parse due_date
    try:
        if "T" in due_date_str:
            due_dt = datetime.fromisoformat(due_date_str.replace("Z", ""))
        else:
            due_dt = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        # Fallback to date parsing
        parsed_dt, _ = parse_egyptian_date_time(due_date_str)
        if parsed_dt:
            due_dt = parsed_dt
        else:
            return ToolResult(success=False, error="Invalid date format", message="صيغة التاريخ والوقت غير صحيحة.")

    # Validate customer if provided
    lead = None
    if customer_id:
        lead = db.query(Lead).filter(Lead.id == customer_id, Lead.company_id == user.company_id).first()
        if not lead:
            return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    # Validate assigned user
    assignee = db.query(User).filter(User.id == assigned_user_id, User.company_id == user.company_id).first()
    if not assignee:
        assignee = user

    priority_enum = PriorityLevel.MEDIUM
    if priority_str in PriorityLevel.__members__:
        priority_enum = PriorityLevel[priority_str]

    task = FollowUp(
        company_id=user.company_id,
        lead_id=lead.id if lead else None,
        assigned_user_id=assignee.id,
        created_by_id=user.id,
        purpose=title,
        due_date=due_dt,
        priority=priority_enum,
        status=FollowUpStatus.PENDING,
        notes=notes or ""
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Activity log
    act = Activity(
        company_id=user.company_id,
        lead_id=lead.id if lead else None,
        user_id=user.id,
        activity_type=ActivityType.NOTE,
        summary=f"تم إنشاء مهمة جديدة بواسطة المساعد الذكي: {title} في {due_dt.strftime('%Y-%m-%d %I:%M %p')}"
    )
    db.add(act)
    db.commit()

    lead_info = f" للعميل {lead.full_name}" if lead else ""
    time_fmt = due_dt.strftime("%Y-%m-%d الساعة %I:%M %p")
    return ToolResult(
        success=True,
        data={"task_id": task.id, "due_date": due_dt.isoformat()},
        message=f"تم تسجيل المهمة بنجاح: '{title}'{lead_info} - الموعد: {time_fmt}."
    )


@ai_tool_registry.register(
    name="complete_task",
    description="تحديد مهمة أو متابعة كمكتملة وتسجيل نتيجة المتابعة.",
    category="task",
    parameters_schema={
        "properties": {
            "task_id": {"type": "integer", "description": "معرف المهمة (ID)"},
            "outcome": {"type": "string", "description": "نتيجة إتمام المهمة والملاحظات"}
        },
        "required": ["task_id"]
    }
)
def complete_task(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    task_id = params.get("task_id")
    outcome = params.get("outcome", "تم إنجاز المهمة بنجاح")

    task = db.query(FollowUp).filter(FollowUp.id == task_id, FollowUp.company_id == user.company_id).first()
    if not task:
        return ToolResult(success=False, error="Task not found", message=f"المهمة رقم #{task_id} غير موجودة.")

    task.status = FollowUpStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    task.completion_outcome = outcome
    db.commit()

    return ToolResult(
        success=True,
        data={"task_id": task.id, "status": "COMPLETED"},
        message=f"تم تحديد المهمة '{task.purpose}' كمكتملة بنجاح."
    )


@ai_tool_registry.register(
    name="reschedule_task",
    description="تأجيل أو تغيير موعد استحقاق مهمة أو متابعة.",
    category="task",
    parameters_schema={
        "properties": {
            "task_id": {"type": "integer", "description": "معرف المهمة (ID)"},
            "new_due_date": {"type": "string", "description": "الموعد الجديد بصيغة ISO"},
            "reason": {"type": "string", "description": "سبب إعادة الجدولة"}
        },
        "required": ["task_id", "new_due_date"]
    }
)
def reschedule_task(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    task_id = params.get("task_id")
    new_due_str = params.get("new_due_date")
    reason = params.get("reason", "")

    task = db.query(FollowUp).filter(FollowUp.id == task_id, FollowUp.company_id == user.company_id).first()
    if not task:
        return ToolResult(success=False, error="Task not found", message=f"المهمة رقم #{task_id} غير موجودة.")

    try:
        if "T" in new_due_str:
            new_dt = datetime.fromisoformat(new_due_str.replace("Z", ""))
        else:
            new_dt = datetime.strptime(new_due_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        parsed_dt, _ = parse_egyptian_date_time(new_due_str)
        if parsed_dt:
            new_dt = parsed_dt
        else:
            return ToolResult(success=False, error="Invalid date format", message="صيغة الموعد الجديد غير صحيحة.")

    task.due_date = new_dt
    task.status = FollowUpStatus.RESCHEDULED
    if reason:
        task.notes = f"{task.notes}\n[إعادة جدولة: {reason}]".strip()
    db.commit()

    time_fmt = new_dt.strftime("%Y-%m-%d الساعة %I:%M %p")
    return ToolResult(
        success=True,
        data={"task_id": task.id, "new_due_date": new_dt.isoformat()},
        message=f"تمت إعادة جدولة المهمة '{task.purpose}' إلى {time_fmt} بنجاح."
    )

