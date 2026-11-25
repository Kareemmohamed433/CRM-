"""
Customer Tools for NEXORA AI CRM Assistant.
Handles searching, details inspection, historical activities, and profile updates.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from backend.app.models.models import (
    Lead, Activity, FollowUp, Appointment, PropertyOffer, User, UserRole, ActivityType
)
from backend.app.core.permissions import get_scoped_lead_query
from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult
from backend.app.services.audit_service import log_audit_event
from backend.app.services.egyptian_nlp import normalize_arabic_text


@ai_tool_registry.register(
    name="search_customers",
    description="البحث عن العملاء في قاعدة البيانات بالاسم أو رقم الهاتف أو المشروع أو المنطقة.",
    category="customer",
    parameters_schema={
        "properties": {
            "query": {"type": "string", "description": "اسم العميل أو جزء من رقم هاتفه أو المشروع المهتم به"},
            "limit": {"type": "integer", "description": "الحد الأقصى لعدد النتائج (الافتراضي 10)"}
        },
        "required": ["query"]
    }
)
def search_customers(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    query_str = (params.get("query") or "").strip()
    limit = min(params.get("limit", 10), 50)

    if not query_str:
        return ToolResult(success=False, error="Query cannot be empty", message="يرجى كتابة اسم أو رقم هاتف العميل للبحث.")

    base_query = get_scoped_lead_query(db.query(Lead), user)
    clean_q = normalize_arabic_text(query_str)

    leads = base_query.filter(
        or_(
            Lead.full_name.ilike(f"%{query_str}%"),
            Lead.phone.ilike(f"%{query_str}%"),
            Lead.email.ilike(f"%{query_str}%"),
            Lead.notes.ilike(f"%{query_str}%"),
            Lead.tags.ilike(f"%{query_str}%")
        )
    ).limit(limit).all()

    if not leads:
        return ToolResult(
            success=True,
            data=[],
            message=f"لم يتم العثور على أي عميل يطابق '{query_str}'."
        )

    results = []
    for lead in leads:
        results.append({
            "id": lead.id,
            "full_name": lead.full_name,
            "phone": lead.phone,
            "pipeline_stage": lead.pipeline_stage.value if lead.pipeline_stage else None,
            "budget": lead.budget_max,
            "preferred_property_type": getattr(lead, "property_type", None),
            "preferred_location": lead.preferred_location,
            "assigned_agent_id": lead.assigned_agent_id,
            "score": lead.score
        })

    msg = f"تم العثور على {len(results)} عميل يطابق البحث:"
    return ToolResult(success=True, data=results, message=msg)


@ai_tool_registry.register(
    name="get_customer_details",
    description="استرجاع كافة بيانات العميل التفصيلية ورقم ملفه واهتماماته العقارية.",
    category="customer",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"}
        },
        "required": ["customer_id"]
    }
)
def get_customer_details(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    if not customer_id:
        return ToolResult(success=False, error="Customer ID is required", message="يرجى تحديد رقم العميل.")

    base_query = get_scoped_lead_query(db.query(Lead), user)
    lead = base_query.filter(Lead.id == customer_id).first()
    if not lead:
        return ToolResult(
            success=False,
            error=f"Customer with ID {customer_id} not found or unauthorized.",
            message=f"العميل رقم #{customer_id} غير موجود أو لا تملك صلاحية الوصول إليه."
        )

    agent_name = lead.assigned_agent.full_name if lead.assigned_agent else "غير معين"
    data = {
        "id": lead.id,
        "full_name": lead.full_name,
        "phone": lead.phone,
        "email": lead.email,
        "source": lead.source,
        "pipeline_stage": lead.pipeline_stage.value if lead.pipeline_stage else None,
        "priority": lead.priority.value if lead.priority else None,
        "budget": lead.budget_max,
        "preferred_property_type": getattr(lead, "property_type", None),
        "preferred_location": lead.preferred_location,
        "assigned_agent": agent_name,
        "score": lead.score,
        "notes": lead.notes,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "last_contact_date": lead.last_contact_date.isoformat() if lead.last_contact_date else None,
    }

    return ToolResult(
        success=True,
        data=data,
        message=f"بيانات العميل: {lead.full_name} (#{lead.id}) - المرحلة: {lead.pipeline_stage.value if lead.pipeline_stage else 'جديد'}"
    )


@ai_tool_registry.register(
    name="get_customer_history",
    description="عرض السجل التاريخي الكامل للعميل من مكالمات واجتماعات وتحديثات وعروض مرسلة.",
    category="customer",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"},
            "limit": {"type": "integer", "description": "الحد الأقصى لعدد الأحداث"}
        },
        "required": ["customer_id"]
    }
)
def get_customer_history(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    limit = min(params.get("limit", 20), 50)
    if not customer_id:
        return ToolResult(success=False, error="Customer ID is required", message="يرجى تحديد رقم العميل.")

    lead = get_scoped_lead_query(db.query(Lead), user).filter(Lead.id == customer_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    # Fetch activities
    activities = db.query(Activity).filter(
        Activity.company_id == user.company_id,
        Activity.lead_id == customer_id
    ).order_by(desc(Activity.created_at)).limit(limit).all()

    # Fetch appointments
    appointments = db.query(Appointment).filter(
        Appointment.company_id == user.company_id,
        Appointment.lead_id == customer_id
    ).order_by(desc(Appointment.start_time)).limit(limit).all()

    # Fetch property offers
    offers = db.query(PropertyOffer).filter(
        PropertyOffer.company_id == user.company_id,
        PropertyOffer.lead_id == customer_id
    ).order_by(desc(PropertyOffer.created_at)).limit(limit).all()

    timeline = []
    for a in activities:
        timeline.append({
            "type": "ACTIVITY",
            "subtype": a.activity_type.value if a.activity_type else "NOTE",
            "summary": a.summary,
            "outcome": a.outcome,
            "created_at": a.created_at.isoformat() if a.created_at else None
        })

    for appt in appointments:
        timeline.append({
            "type": "APPOINTMENT",
            "title": appt.title,
            "location": appt.location,
            "status": appt.status.value if appt.status else "SCHEDULED",
            "created_at": appt.start_time.isoformat() if appt.start_time else None
        })

    for o in offers:
        timeline.append({
            "type": "OFFER",
            "property_unit": o.property.unit_number if o.property else "",
            "status": o.status.value if o.status else "PREPARED",
            "feedback": o.customer_feedback,
            "created_at": o.created_at.isoformat() if o.created_at else None
        })

    # Sort descending by timestamp
    timeline.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return ToolResult(
        success=True,
        data=timeline[:limit],
        message=f"تم استخراج {len(timeline[:limit])} حدث من السجل التاريخي للعميل {lead.full_name}."
    )


@ai_tool_registry.register(
    name="update_customer",
    description="تحديث بيانات العميل العقارية (الميزانية، المنطقة المفضلة، نوع العقار، الملاحظات).",
    category="customer",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"},
            "budget": {"type": "number", "description": "الميزانية الجديدة بالجنيه"},
            "preferred_location": {"type": "string", "description": "المنطقة المفضلة"},
            "preferred_property_type": {"type": "string", "description": "نوع الوحدة (شقة، فيلا، دوبلكس)"},
            "notes": {"type": "string", "description": "ملاحظات إضافية"}
        },
        "required": ["customer_id"]
    }
)
def update_customer(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    if not customer_id:
        return ToolResult(success=False, error="Customer ID is required", message="يرجى تحديد رقم العميل.")

    lead = get_scoped_lead_query(db.query(Lead), user).filter(Lead.id == customer_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    changes = []
    if "budget" in params and params["budget"] is not None:
        lead.budget_max = float(params["budget"])
        changes.append(f"الميزانية: {lead.budget_max:,.0f} ج.م")

    if "preferred_location" in params and params["preferred_location"]:
        lead.preferred_location = params["preferred_location"]
        changes.append(f"المنطقة: {lead.preferred_location}")

    if "preferred_property_type" in params and params["preferred_property_type"]:
        lead.property_type = params["preferred_property_type"]
        changes.append(f"النوع: {lead.property_type}")

    if "notes" in params and params["notes"]:
        lead.notes = f"{lead.notes}\n{params['notes']}".strip()
        changes.append("إضافة ملاحظات")

    if not changes:
        return ToolResult(success=True, data={"id": lead.id}, message="لم يتم إرسال أي بيانات جديدة لتحديثها.")

    db.commit()
    db.refresh(lead)

    # Log activity note
    act = Activity(
        company_id=user.company_id,
        lead_id=lead.id,
        user_id=user.id,
        activity_type=ActivityType.NOTE,
        summary=f"تحديث بيانات العميل بواسطة المساعد الذكي: {', '.join(changes)}"
    )
    db.add(act)
    db.commit()

    return ToolResult(
        success=True,
        data={"id": lead.id, "changes": changes},
        message=f"تم تحديث بيانات العميل {lead.full_name} بنجاح: {', '.join(changes)}."
    )
