"""
Appointment Tools for NEXORA AI CRM Assistant.
Handles meeting & site visit scheduling, schedule conflict detection, updates, and cancellations.
"""

from datetime import datetime, timedelta, date, time
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc

from backend.app.models.models import (
    Appointment, Lead, Property, User, AppointmentStatus, Activity, ActivityType
)
from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult
from backend.app.services.egyptian_nlp import parse_egyptian_date_time


@ai_tool_registry.register(
    name="get_appointments",
    description="استعراض المواعيد واجتماعات العملاء والزيارات الميدانية المجدولة.",
    category="appointment",
    parameters_schema={
        "properties": {
            "start_date": {"type": "string", "description": "تاريخ البداية بصيغة YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "تاريخ النهاية بصيغة YYYY-MM-DD"},
            "customer_id": {"type": "integer", "description": "معرف العميل لتصفية مواعيده الخاصة"}
        }
    }
)
def get_appointments(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    start_d_str = params.get("start_date")
    end_d_str = params.get("end_date")
    customer_id = params.get("customer_id")

    q = db.query(Appointment).filter(Appointment.company_id == user.company_id)
    if user.role.value == "SALES_AGENT":
        q = q.filter(Appointment.user_id == user.id)

    if customer_id:
        q = q.filter(Appointment.lead_id == customer_id)

    if start_d_str:
        try:
            sd = datetime.strptime(start_d_str, "%Y-%m-%d")
            q = q.filter(Appointment.start_time >= sd)
        except ValueError:
            pass

    if end_d_str:
        try:
            ed = datetime.strptime(end_d_str, "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(Appointment.start_time < ed)
        except ValueError:
            pass

    appts = q.order_by(asc(Appointment.start_time)).all()
    items = []
    for a in appts:
        items.append({
            "id": a.id,
            "title": a.title,
            "lead_name": a.lead.full_name if a.lead else "عميل",
            "start_time": a.start_time.strftime("%Y-%m-%d %I:%M %p") if a.start_time else None,
            "end_time": a.end_time.strftime("%I:%M %p") if a.end_time else None,
            "location": a.location,
            "status": a.status.value if a.status else "SCHEDULED",
            "notes": a.notes
        })

    msg = f"تم العثور على {len(items)} موعد مجدول."
    return ToolResult(success=True, data=items, message=msg)


@ai_tool_registry.register(
    name="create_appointment",
    description="حجز وتأكيد موعد اجتماع أو معاينة مع عميل بعد التحقق من عدم وجود تعارض في الجدول.",
    category="appointment",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"},
            "title": {"type": "string", "description": "عنوان الموعد (مثال: معاينة فيلا في التجمع)"},
            "start_time": {"type": "string", "description": "وقت بداية الموعد بصيغة ISO"},
            "end_time": {"type": "string", "description": "وقت انتهاء الموعد بصيغة ISO (افتراضيًا بعد ساعة)"},
            "location": {"type": "string", "description": "مكان الاجتماع أو المعاينة"},
            "property_id": {"type": "integer", "description": "معرف الوحدة المعروضة (اختياري)"},
            "notes": {"type": "string", "description": "ملاحظات إضافية"}
        },
        "required": ["customer_id", "title", "start_time"]
    }
)
def create_appointment(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    title = (params.get("title") or "اجتماع مع عميل").strip()
    start_str = params.get("start_time")
    end_str = params.get("end_time")
    location = (params.get("location") or "المقر الرئيسي").strip()
    property_id = params.get("property_id")
    notes = params.get("notes", "")

    lead = db.query(Lead).filter(Lead.id == customer_id, Lead.company_id == user.company_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    # Parse start_time
    try:
        if "T" in start_str:
            start_dt = datetime.fromisoformat(start_str.replace("Z", ""))
        else:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        parsed_dt, _ = parse_egyptian_date_time(start_str)
        if parsed_dt:
            start_dt = parsed_dt
        else:
            return ToolResult(success=False, error="Invalid start time", message="صيغة وقت بداية الموعد غير صحيحة.")

    if end_str:
        try:
            if "T" in end_str:
                end_dt = datetime.fromisoformat(end_str.replace("Z", ""))
            else:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            end_dt = start_dt + timedelta(hours=1)
    else:
        end_dt = start_dt + timedelta(hours=1)

    # Conflict check for the user
    conflict = db.query(Appointment).filter(
        Appointment.company_id == user.company_id,
        Appointment.user_id == user.id,
        Appointment.status != AppointmentStatus.CANCELLED,
        or_(
            and_(Appointment.start_time <= start_dt, Appointment.end_time > start_dt),
            and_(Appointment.start_time < end_dt, Appointment.end_time >= end_dt),
            and_(Appointment.start_time >= start_dt, Appointment.end_time <= end_dt)
        )
    ).first()

    conflict_warning = ""
    if conflict:
        c_title = conflict.title
        c_time = conflict.start_time.strftime("%I:%M %p")
        conflict_warning = f" (تنبيه: يوجد تعارض مع موعدك الآخر: '{c_title}' الساعة {c_time})"

    # Validate property if provided
    prop = None
    if property_id:
        prop = db.query(Property).filter(Property.id == property_id, Property.company_id == user.company_id).first()

    appt = Appointment(
        company_id=user.company_id,
        lead_id=lead.id,
        user_id=user.id,
        property_id=prop.id if prop else None,
        title=title,
        appointment_type="VISIT" if ("معاينة" in title or prop) else "MEETING",
        start_time=start_dt,
        end_time=end_dt,
        location=location,
        notes=notes or "",
        status=AppointmentStatus.SCHEDULED
    )
    db.add(appt)

    # Log activity
    act = Activity(
        company_id=user.company_id,
        lead_id=lead.id,
        property_id=prop.id if prop else None,
        user_id=user.id,
        activity_type=ActivityType.MEETING,
        summary=f"تأكيد وحجز موعد: {title} في {location} ({start_dt.strftime('%Y-%m-%d %I:%M %p')})"
    )
    db.add(act)
    db.commit()

    time_fmt = start_dt.strftime("%Y-%m-%d الساعة %I:%M %p")
    return ToolResult(
        success=True,
        data={"appointment_id": appt.id, "start_time": start_dt.isoformat()},
        message=f"تم تأكيد وحجز الموعد بنجاح: '{title}' مع {lead.full_name} في {time_fmt} ({location}).{conflict_warning}"
    )


@ai_tool_registry.register(
    name="cancel_appointment",
    description="إلغاء موعد أو معاينة مع عميل وتسجيل سبب الإلغاء.",
    category="appointment",
    parameters_schema={
        "properties": {
            "appointment_id": {"type": "integer", "description": "معرف الموعد (ID)"},
            "reason": {"type": "string", "description": "سبب الإلغاء"}
        },
        "required": ["appointment_id"]
    }
)
def cancel_appointment(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    appointment_id = params.get("appointment_id")
    reason = params.get("reason", "بناءً على طلب العميل")

    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.company_id == user.company_id
    ).first()
    if not appt:
        return ToolResult(success=False, error="Appointment not found", message=f"الموعد رقم #{appointment_id} غير موجود.")

    appt.status = AppointmentStatus.CANCELLED
    if reason:
        appt.notes = f"{appt.notes}\n[تم الإلغاء: {reason}]".strip()

    if appt.lead_id:
        act = Activity(
            company_id=user.company_id,
            lead_id=appt.lead_id,
            user_id=user.id,
            activity_type=ActivityType.NOTE,
            summary=f"إلغاء الموعد '{appt.title}': {reason}"
        )
        db.add(act)

    db.commit()
    return ToolResult(
        success=True,
        data={"appointment_id": appt.id, "status": "CANCELLED"},
        message=f"تم إلغاء الموعد '{appt.title}' بنجاح."
    )

