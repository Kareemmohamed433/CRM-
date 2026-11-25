"""
Property Offer & WhatsApp Tools for NEXORA AI CRM Assistant.
Handles tailored Egyptian Arabic property pitches, offer records, status transitions,
and customer feedback recording.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.models import (
    PropertyOffer, PropertyOfferStatus, Property, Lead, User, Activity, ActivityType
)
from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult


@ai_tool_registry.register(
    name="prepare_property_message",
    description="صياغة رسالة واتساب باللهجة المصرية الراقية لتقديم وحدة عقارية لعميل بمواصفاتها وخطة السداد.",
    category="offer",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"},
            "property_id": {"type": "integer", "description": "معرف الوحدة (ID)"},
            "custom_price": {"type": "number", "description": "سعر خاص للعميل إذا وُجد"},
            "tone": {"type": "string", "enum": ["PROFESSIONAL_EGYPTIAN", "DIRECT", "LUXURY"], "description": "نبرة الرسالة"}
        },
        "required": ["customer_id", "property_id"]
    }
)
def prepare_property_message(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    property_id = params.get("property_id")
    custom_price = params.get("custom_price")

    lead = db.query(Lead).filter(Lead.id == customer_id, Lead.company_id == user.company_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    prop = db.query(Property).filter(Property.id == property_id, Property.company_id == user.company_id).first()
    if not prop:
        return ToolResult(success=False, error="Property not found", message=f"الوحدة رقم #{property_id} غير موجودة.")

    price = custom_price or prop.total_price
    proj_name = prop.project.name if prop.project else "المشروع المميز"
    dev_name = prop.project.developer if prop.project else ""

    agent_name = user.full_name
    first_name = lead.full_name.split()[0] if lead.full_name else ""
    greeting = f"مساء الخير أستاذ {first_name}" if first_name else "مساء الخير يا فندم"

    msg_lines = [
        f"{greeting}، مع حضرتك {agent_name} من شركة NEXORA Real Estate.",
        f"بناءً على طلب حضرتك واهتمامك بمنطقة {prop.location}، جهزت لحضرتك فرصة ممتازة جدًا في مشروع {proj_name}{f' لشركة {dev_name}' if dev_name else ''}:",
        "",
        f"📍 الموقع: {prop.location} - {prop.city}",
        f"🏠 نوع الوحدة: {prop.property_type} (رقم {prop.unit_number})",
        f"📐 المساحة: {prop.area} م² ({prop.bedrooms} غرف نوم | {prop.bathrooms} حمام)",
        f"🌿 الإطلالة: {prop.view} | التشطيب: {prop.finishing_status}",
        f"🔑 الاستلام: {prop.delivery_date}",
        "",
        f"💰 السعر الإجمالي: {price:,.0f} {prop.currency}",
        f"💳 نظام السداد: {prop.installment_plan}",
        f"💵 المقدم: {prop.down_payment:,.0f} {prop.currency}" if prop.down_payment else "",
        "",
        "لو حضرتك تحب نحدد موعد لمعاينة الوحدة على الطبيعة أو لمراجعة خطة الأقساط، أنا تحت أمرك في أي وقت!"
    ]
    # Filter empty lines
    full_message = "\n".join([line for line in msg_lines if line is not None])

    return ToolResult(
        success=True,
        data={
            "customer_id": lead.id,
            "customer_phone": lead.phone,
            "property_id": prop.id,
            "message_text": full_message,
            "price": price
        },
        message=f"تم إعداد رسالة الواتساب للعميل {lead.full_name}:\n\n{full_message}"
    )


@ai_tool_registry.register(
    name="create_property_offer",
    description="إنشاء وتسجيل عرض عقاري رسمي للعميل في النظام وربطه بالوحدة والموظف المسؤول.",
    category="offer",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"},
            "property_id": {"type": "integer", "description": "معرف الوحدة (ID)"},
            "custom_price": {"type": "number", "description": "السعر المخصص بالعرض"},
            "message_text": {"type": "string", "description": "نص الرسالة أو تفاصيل العرض"}
        },
        "required": ["customer_id", "property_id"]
    }
)
def create_property_offer(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    property_id = params.get("property_id")
    custom_price = params.get("custom_price")
    message_text = params.get("message_text")

    lead = db.query(Lead).filter(Lead.id == customer_id, Lead.company_id == user.company_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    prop = db.query(Property).filter(Property.id == property_id, Property.company_id == user.company_id).first()
    if not prop:
        return ToolResult(success=False, error="Property not found", message=f"الوحدة رقم #{property_id} غير موجودة.")

    offer = PropertyOffer(
        company_id=user.company_id,
        lead_id=lead.id,
        property_id=prop.id,
        created_by_id=user.id,
        status=PropertyOfferStatus.PREPARED,
        custom_price=custom_price or prop.total_price,
        message_text=message_text or "",
        shared_via="WHATSAPP"
    )
    db.add(offer)

    # Activity log
    act = Activity(
        company_id=user.company_id,
        lead_id=lead.id,
        property_id=prop.id,
        user_id=user.id,
        activity_type=ActivityType.OFFER_SENT,
        summary=f"تجهيز عرض عقاري لوحدة {prop.unit_number} بمشروع {prop.project.name if prop.project else ''}"
    )
    db.add(act)
    db.commit()

    return ToolResult(
        success=True,
        data={"offer_id": offer.id, "status": "PREPARED"},
        message=f"تم تسجيل العرض العقاري رقم #{offer.id} للعميل {lead.full_name} بنجاح (حالة العرض: جاهز للمشاركة)."
    )


@ai_tool_registry.register(
    name="get_customer_property_offers",
    description="استعراض كافة العروض والوحدات العقارية التي تم تقديمها للعميل وموقف كل عرض.",
    category="offer",
    parameters_schema={
        "properties": {
            "customer_id": {"type": "integer", "description": "معرف العميل (ID)"}
        },
        "required": ["customer_id"]
    }
)
def get_customer_property_offers(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    customer_id = params.get("customer_id")
    lead = db.query(Lead).filter(Lead.id == customer_id, Lead.company_id == user.company_id).first()
    if not lead:
        return ToolResult(success=False, error="Customer not found", message=f"العميل رقم #{customer_id} غير موجود.")

    offers = db.query(PropertyOffer).filter(
        PropertyOffer.lead_id == customer_id,
        PropertyOffer.company_id == user.company_id
    ).order_by(desc(PropertyOffer.created_at)).all()

    items = []
    for o in offers:
        items.append({
            "offer_id": o.id,
            "property_id": o.property_id,
            "unit_number": o.property.unit_number if o.property else "",
            "project_name": o.property.project.name if (o.property and o.property.project) else "",
            "price": o.custom_price,
            "status": o.status.value if o.status else "PREPARED",
            "shared_at": o.shared_at.isoformat() if o.shared_at else None,
            "customer_feedback": o.customer_feedback
        })

    msg = f"يوجد {len(items)} عرض عقاري مسجل للعميل {lead.full_name}."
    return ToolResult(success=True, data=items, message=msg)


@ai_tool_registry.register(
    name="record_customer_feedback",
    description="تسجيل رد فعل أو ملاحظات أو اعتراضات العميل على وحدة عقارية تم عرضها عليه.",
    category="offer",
    parameters_schema={
        "properties": {
            "offer_id": {"type": "integer", "description": "معرف العرض (ID)"},
            "feedback": {"type": "string", "description": "انطباع العميل (مثال: السعر مناسب ولكن يفضل دور أعلى)"},
            "status": {"type": "string", "enum": ["ACCEPTED", "REJECTED", "SHARED"], "description": "تحديث حالة العرض"}
        },
        "required": ["offer_id", "feedback"]
    }
)
def record_customer_feedback(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    offer_id = params.get("offer_id")
    feedback = (params.get("feedback") or "").strip()
    status_str = params.get("status")

    offer = db.query(PropertyOffer).filter(
        PropertyOffer.id == offer_id,
        PropertyOffer.company_id == user.company_id
    ).first()
    if not offer:
        return ToolResult(success=False, error="Offer not found", message=f"العرض رقم #{offer_id} غير موجود.")

    offer.customer_feedback = feedback
    offer.feedback_recorded_at = datetime.utcnow()

    if status_str and status_str in PropertyOfferStatus.__members__:
        offer.status = PropertyOfferStatus[status_str]

    # Log activity
    if offer.lead_id:
        act = Activity(
            company_id=user.company_id,
            lead_id=offer.lead_id,
            property_id=offer.property_id,
            user_id=user.id,
            activity_type=ActivityType.NOTE,
            summary=f"تسجيل ملاحظات العميل على العرض #{offer.id}: {feedback}",
            outcome=status_str or "FEEDBACK_LOGGED"
        )
        db.add(act)

    db.commit()
    return ToolResult(
        success=True,
        data={"offer_id": offer.id, "status": offer.status.value},
        message=f"تم تسجيل ملاحظات العميل على العرض #{offer.id} بنجاح: '{feedback}'."
    )

