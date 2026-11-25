"""
Inventory & Property Tools for NEXORA AI CRM Assistant.
Handles real estate unit searches, specs inspection, availability, comparison, media,
and project/location inventory breakdown.
Strictly respects multi-tenancy (company_id), location boundaries, and honest availability.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc, func

from backend.app.models.models import (
    Property, Project, PropertyStatus, User, PropertyImage, PropertyVideo,
    Governorate, City, District, Lead
)
from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult
from backend.app.services.matching_service import find_alternative_properties


def _format_property_summary(p: Property) -> Dict[str, Any]:
    proj_name = p.project.name if p.project else "عقار مستقل"
    primary_img = next((img.image_url for img in p.images if img.is_primary), None)
    if not primary_img and p.images:
        primary_img = p.images[0].image_url

    videos_data = [
        {"id": v.id, "url": v.video_url, "type": v.video_type, "title": v.title}
        for v in p.videos
    ] if p.videos else []

    return {
        "id": p.id,
        "unit_number": p.unit_number,
        "title": p.title or f"{p.property_type} - {p.unit_number}",
        "property_type": p.property_type,
        "project_id": p.project_id,
        "project_name": proj_name,
        "location": p.location,
        "city": p.city,
        "area": p.area,
        "bedrooms": p.bedrooms,
        "bathrooms": p.bathrooms,
        "floor": p.floor,
        "view": p.view,
        "finishing_status": p.finishing_status,
        "delivery_date": p.delivery_date,
        "total_price": p.total_price,
        "price_per_sqm": round(p.total_price / p.area, 2) if p.area else 0,
        "currency": p.currency or "EGP",
        "down_payment": p.down_payment,
        "installment_plan": p.installment_plan,
        "availability_status": p.availability_status.value if hasattr(p.availability_status, 'value') else str(p.availability_status),
        "primary_image_url": primary_img,
        "images_count": len(p.images) if p.images else 0,
        "videos_count": len(videos_data),
        "videos": videos_data,
        "description": p.description or ""
    }


@ai_tool_registry.register(
    name="search_available_properties",
    description="البحث الدقيق في محفظة العقارات المتاحة بالمحافظة، المنطقة، المشروع، نوع الوحدة، الميزانية، وعدد الغرف.",
    category="inventory",
    parameters_schema={
        "properties": {
            "governorate": {"type": "string", "description": "المحافظة (مثل: القاهرة، الجيزة، الإسكندرية)"},
            "location": {"type": "string", "description": "المنطقة أو الحي (مثل: التجمع الخامس، الشيخ زايد، مدينة نصر، المعادي)"},
            "project_name": {"type": "string", "description": "اسم المشروع العقاري"},
            "project_id": {"type": "integer", "description": "معرف المشروع (ID)"},
            "property_type": {"type": "string", "description": "نوع العقار (Apartment, Villa, Duplex, Townhouse, Penthouse)"},
            "min_price": {"type": "number", "description": "الحد الأدنى للسعر بالجنيه"},
            "max_price": {"type": "number", "description": "الحد الأقصى للسعر بالجنيه"},
            "bedrooms": {"type": "integer", "description": "عدد غرف النوم"},
            "bathrooms": {"type": "integer", "description": "عدد الحمامات"},
            "min_area": {"type": "number", "description": "الحد الأدنى للمساحة بالمتر المربع"},
            "max_area": {"type": "number", "description": "الحد الأقصى للمساحة بالمتر المربع"},
            "sort_by": {"type": "string", "description": "الترتيب: price_asc, price_desc, area_asc, area_desc"},
            "include_archived": {"type": "boolean", "description": "تضمين الوحدات المؤرشفة (افتراضي False)"},
            "limit": {"type": "integer", "description": "أقصى عدد وحدات يتم إرجاعها (افتراضي 10)"}
        }
    }
)
def search_available_properties(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    query = db.query(Property).filter(Property.company_id == user.company_id)

    include_archived = params.get("include_archived", False)
    if not include_archived:
        query = query.filter(
            Property.is_archived == False,  # noqa: E712
            Property.availability_status != PropertyStatus.ARCHIVED
        )

    # Exclude sold/reserved by default unless status is specified
    status_filter = params.get("status")
    if status_filter:
        query = query.filter(Property.availability_status == status_filter)
    else:
        query = query.filter(Property.availability_status == PropertyStatus.AVAILABLE)

    governorate = params.get("governorate")
    if governorate:
        gov_match = db.query(Governorate).filter(
            (Governorate.name_ar.ilike(f"%{governorate}%")) | (Governorate.name_en.ilike(f"%{governorate}%"))
        ).first()
        if gov_match:
            query = query.filter(
                or_(
                    Property.governorate_id == gov_match.id,
                    Property.location.ilike(f"%{governorate}%"),
                    Property.city.ilike(f"%{governorate}%")
                )
            )
        else:
            query = query.filter(
                or_(
                    Property.location.ilike(f"%{governorate}%"),
                    Property.city.ilike(f"%{governorate}%")
                )
            )

    location = params.get("location")
    if location:
        loc_str = f"%{location}%"
        query = query.filter(
            or_(
                Property.location.ilike(loc_str),
                Property.city.ilike(loc_str),
                Property.title.ilike(loc_str)
            )
        )

    project_id = params.get("project_id")
    if project_id:
        query = query.filter(Property.project_id == project_id)

    project_name = params.get("project_name")
    if project_name:
        query = query.join(Property.project).filter(Project.name.ilike(f"%{project_name}%"))

    property_type = params.get("property_type")
    if property_type:
        query = query.filter(Property.property_type.ilike(f"%{property_type}%"))

    min_price = params.get("min_price")
    if min_price is not None:
        query = query.filter(Property.total_price >= float(min_price))

    max_price = params.get("max_price")
    if max_price is not None:
        query = query.filter(Property.total_price <= float(max_price))

    bedrooms = params.get("bedrooms")
    if bedrooms is not None:
        query = query.filter(Property.bedrooms == int(bedrooms))

    bathrooms = params.get("bathrooms")
    if bathrooms is not None:
        query = query.filter(Property.bathrooms >= int(bathrooms))

    min_area = params.get("min_area")
    if min_area is not None:
        query = query.filter(Property.area >= float(min_area))

    max_area = params.get("max_area")
    if max_area is not None:
        query = query.filter(Property.area <= float(max_area))

    # Sorting
    sort_by = params.get("sort_by", "price_asc")
    if sort_by == "price_desc":
        query = query.order_by(Property.total_price.desc())
    elif sort_by == "area_desc":
        query = query.order_by(Property.area.desc())
    elif sort_by == "area_asc":
        query = query.order_by(Property.area.asc())
    else:
        query = query.order_by(Property.total_price.asc())

    limit = params.get("limit", 10)
    matched = query.limit(limit).all()

    if not matched:
        loc_desc = f" في '{location}'" if location else ""
        budget_desc = f" بميزانية حتى {max_price:,.0f} جنيه" if max_price else ""
        return ToolResult(
            success=True,
            data=[],
            message=f"عذرًا، لا توجد وحدات متاحة حاليًا تطابق معايير البحث{loc_desc}{budget_desc}."
        )

    results = [_format_property_summary(p) for p in matched]

    msg_lines = [f"تم العثور على {len(results)} وحدة متاحة:"]
    for idx, r in enumerate(results[:5], 1):
        media_info = []
        if r["images_count"] > 0:
            media_info.append(f"{r['images_count']} صور")
        if r["videos_count"] > 0:
            media_info.append(f"{r['videos_count']} فيديو")
        media_txt = f" [{', '.join(media_info)}]" if media_info else ""

        msg_lines.append(
            f"{idx}. وحدة {r['unit_number']} ({r['property_type']}) - مشروع {r['project_name']} ({r['location']}) "
            f"- مساحة {r['area']}م² - {r['bedrooms']} غرف - السعر: {r['total_price']:,.0f} {r['currency']}"
            f" ({r['installment_plan']}){media_txt}"
        )

    return ToolResult(
        success=True,
        data=results,
        message="\n".join(msg_lines)
    )


# Backward compatibility registration for search_properties
@ai_tool_registry.register(
    name="search_properties",
    description="البحث في محفظة العقارات والوحدات المتاحة بالموقع ونوع الوحدة والميزانية وعدد الغرف.",
    category="inventory",
    parameters_schema={
        "properties": {
            "location": {"type": "string", "description": "المنطقة (مثال: التجمع الخامس، الشيخ زايد، مدينة نصر، العاصمة)"},
            "property_type": {"type": "string", "description": "نوع العقار (Apartment, Villa, Duplex, Townhouse, Penthouse)"},
            "min_price": {"type": "number", "description": "الحد الأدنى للسعر بالجنيه"},
            "max_price": {"type": "number", "description": "الحد الأقصى للسعر بالجنيه"},
            "bedrooms": {"type": "integer", "description": "عدد غرف النوم"},
            "strict_location": {"type": "boolean", "description": "الالتزام الصارم بالمنطقة المحددة (افتراضي True)"}
        }
    }
)
def search_properties_alias(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    return search_available_properties(db, user, params)


@ai_tool_registry.register(
    name="get_location_inventory",
    description="استعراض إحصائيات وتوزيع المخزون العقاري حسب المحافظة أو المنطقة أو المشروع (عدد الوحدات المتاحة، المحجوزة، والمباعة).",
    category="inventory",
    parameters_schema={
        "properties": {
            "location": {"type": "string", "description": "اسم المنطقة أو المدينة (مثل: التجمع الخامس، الشيخ زايد، مدينة نصر)"},
            "governorate": {"type": "string", "description": "اسم المحافظة (مثل: القاهرة، الجيزة)"},
            "property_type": {"type": "string", "description": "نوع العقار (اختياري)"}
        }
    }
)
def get_location_inventory(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    location = params.get("location")
    governorate = params.get("governorate")
    property_type = params.get("property_type")

    query = db.query(Property).filter(Property.company_id == user.company_id, Property.is_archived == False)  # noqa: E712

    if location:
        query = query.filter(
            or_(
                Property.location.ilike(f"%{location}%"),
                Property.city.ilike(f"%{location}%")
            )
        )
    if governorate:
        gov_match = db.query(Governorate).filter(
            (Governorate.name_ar.ilike(f"%{governorate}%")) | (Governorate.name_en.ilike(f"%{governorate}%"))
        ).first()
        if gov_match:
            query = query.filter(
                or_(
                    Property.governorate_id == gov_match.id,
                    Property.location.ilike(f"%{governorate}%"),
                    Property.city.ilike(f"%{governorate}%")
                )
            )
    if property_type:
        query = query.filter(Property.property_type.ilike(f"%{property_type}%"))

    props = query.all()
    total = len(props)
    avail = sum(1 for p in props if p.availability_status == PropertyStatus.AVAILABLE)
    reserved = sum(1 for p in props if p.availability_status == PropertyStatus.RESERVED)
    sold = sum(1 for p in props if p.availability_status == PropertyStatus.SOLD)

    # Breakdown by projects
    projects_breakdown = {}
    for p in props:
        p_name = p.project.name if p.project else "عقارات مستقلة"
        if p_name not in projects_breakdown:
            projects_breakdown[p_name] = {"total": 0, "available": 0, "reserved": 0, "sold": 0}
        projects_breakdown[p_name]["total"] += 1
        if p.availability_status == PropertyStatus.AVAILABLE:
            projects_breakdown[p_name]["available"] += 1
        elif p.availability_status == PropertyStatus.RESERVED:
            projects_breakdown[p_name]["reserved"] += 1
        elif p.availability_status == PropertyStatus.SOLD:
            projects_breakdown[p_name]["sold"] += 1

    loc_name = location or governorate or "كافة المناطق"
    msg_lines = [
        f"📊 **مخزون الوحدات في {loc_name}:**",
        f"• الإجمالي: {total} وحدة",
        f"• المتاح للبيع: {avail} وحدة",
        f"• المحجوز: {reserved} وحدة",
        f"• المباع: {sold} وحدة",
        "",
        "**توزيع المشروعات:**"
    ]
    for proj, stats in projects_breakdown.items():
        msg_lines.append(f"• {proj}: {stats['available']} متاح من أصل {stats['total']}")

    return ToolResult(
        success=True,
        data={
            "location": loc_name,
            "total_units": total,
            "available_units": avail,
            "reserved_units": reserved,
            "sold_units": sold,
            "projects_breakdown": projects_breakdown
        },
        message="\n".join(msg_lines)
    )


@ai_tool_registry.register(
    name="get_property_details",
    description="استعراض كافة التفاصيل والمواصفات الفنية والصور والفيديوهات وأنظمة السداد لوحدة عقارية محددة.",
    category="inventory",
    parameters_schema={
        "properties": {
            "property_id": {"type": "integer", "description": "معرف الوحدة (ID)"}
        },
        "required": ["property_id"]
    }
)
def get_property_details(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    property_id = params.get("property_id")
    if not property_id:
        return ToolResult(success=False, error="Property ID is required", message="يرجى تحديد رقم الوحدة.")

    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == user.company_id
    ).first()

    if not prop:
        return ToolResult(success=False, error="Property not found", message=f"الوحدة رقم #{property_id} غير موجودة.")

    data = _format_property_summary(prop)

    # Detailed image links and video links
    data["images"] = [
        {"id": img.id, "url": img.image_url, "caption": img.caption, "is_primary": img.is_primary}
        for img in prop.images
    ]
    data["videos"] = [
        {"id": vid.id, "url": vid.video_url, "type": vid.video_type, "title": vid.title}
        for vid in prop.videos
    ]

    media_notes = []
    if data["images"]:
        media_notes.append(f"مرفق {len(data['images'])} صور للوحدة")
    if data["videos"]:
        media_notes.append(f"مرفق {len(data['videos'])} فيديو استعراضي للوحدة")
    media_txt = f"\n🎥 الوسائط: {', '.join(media_notes)}" if media_notes else ""

    msg = (
        f"تفاصيل الوحدة {prop.unit_number} ({prop.property_type}) - مشروع {data['project_name']}:\n"
        f"الموقع: {prop.location} ({prop.city}) | المساحة: {prop.area}م² | الغرف: {prop.bedrooms} نوم، {prop.bathrooms} حمام | الدور: {prop.floor}\n"
        f"الإطلالة: {prop.view} | التشطيب: {prop.finishing_status} | الاستلام: {prop.delivery_date}\n"
        f"السعر الإجمالي: {prop.total_price:,.0f} {prop.currency} (سعر المتر: {data['price_per_sqm']:,.0f} {prop.currency})\n"
        f"المقدم: {prop.down_payment:,.0f} {prop.currency} | نظام السداد: {prop.installment_plan} | الحالة: {data['availability_status']}{media_txt}"
    )

    return ToolResult(success=True, data=data, message=msg)


@ai_tool_registry.register(
    name="compare_properties",
    description="المقارنة التفصيلية بين وحدتين عقاريتين أو أكثر جنباً إلى جنب (الأسعار، سعر المتر، المساحات، الغرف، الإطلالة، نظام السداد).",
    category="inventory",
    parameters_schema={
        "properties": {
            "property_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "قائمة بأرقام الوحدات (IDs) المراد المقارنة بينها"
            }
        },
        "required": ["property_ids"]
    }
)
def compare_properties(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    prop_ids = params.get("property_ids", [])
    if not prop_ids or len(prop_ids) < 2:
        return ToolResult(
            success=False,
            error="At least 2 property IDs required",
            message="يرجى تحديد وحدتين على الأقل للمقارنة بينهما."
        )

    props = db.query(Property).filter(
        Property.id.in_(prop_ids),
        Property.company_id == user.company_id
    ).all()

    if len(props) < 2:
        return ToolResult(
            success=False,
            error="Properties not found",
            message="لم يتم العثور على الوحدات المحددة في قاعدة بيانات شركتك للمقارنة."
        )

    items = [_format_property_summary(p) for p in props]

    # Generate comparison summary
    lines = ["⚖️ **مقارنة تفصيلية بين الوحدات:**", ""]
    for idx, p in enumerate(items, 1):
        lines.append(
            f"**{idx}. وحدة {p['unit_number']}** ({p['property_type']}) - {p['project_name']}:\n"
            f"   • الموقع: {p['location']}\n"
            f"   • المساحة: {p['area']}م² | {p['bedrooms']} غرف، {p['bathrooms']} حمام\n"
            f"   • السعر: {p['total_price']:,.0f} {p['currency']} (سعر المتر: {p['price_per_sqm']:,.0f} {p['currency']})\n"
            f"   • المقدم: {p['down_payment']:,.0f} {p['currency']} | التقسيط: {p['installment_plan']}\n"
            f"   • التشطيب: {p['finishing_status']} | الاستلام: {p['delivery_date']}\n"
        )

    # Highlight differences
    cheapest = min(items, key=lambda x: x["total_price"])
    largest = max(items, key=lambda x: x["area"])
    best_sqm = min(items, key=lambda x: x["price_per_sqm"])

    lines.append("💡 **الخلاصة والتقييم:**")
    lines.append(f"• **أقل سعر إجمالي:** الوحدة {cheapest['unit_number']} ({cheapest['total_price']:,.0f} {cheapest['currency']})")
    lines.append(f"• **أكبر مساحة:** الوحدة {largest['unit_number']} ({largest['area']}م²)")
    lines.append(f"• **أفضل قيمة لسعر المتر:** الوحدة {best_sqm['unit_number']} ({best_sqm['price_per_sqm']:,.0f} {best_sqm['currency']}/م²)")

    return ToolResult(
        success=True,
        data={
            "properties": items,
            "cheapest_id": cheapest["id"],
            "largest_id": largest["id"],
            "best_sqm_id": best_sqm["id"]
        },
        message="\n".join(lines)
    )


@ai_tool_registry.register(
    name="get_property_media",
    description="استعراض وسائط الوحدة العقارية (الصور والفيديوهات المرفوعة وروابط YouTube و Google Drive).",
    category="inventory",
    parameters_schema={
        "properties": {
            "property_id": {"type": "integer", "description": "معرف الوحدة (ID)"}
        },
        "required": ["property_id"]
    }
)
def get_property_media(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    property_id = params.get("property_id")
    if not property_id:
        return ToolResult(success=False, error="Property ID is required", message="يرجى تحديد رقم الوحدة.")

    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == user.company_id
    ).first()

    if not prop:
        return ToolResult(success=False, error="Property not found", message=f"الوحدة رقم #{property_id} غير موجودة.")

    images = [
        {"id": img.id, "url": img.image_url, "caption": img.caption, "is_primary": img.is_primary}
        for img in prop.images
    ]
    videos = [
        {"id": vid.id, "url": vid.video_url, "type": vid.video_type, "title": vid.title}
        for vid in prop.videos
    ]

    lines = [f"📸 **وسائط الوحدة {prop.unit_number} ({prop.property_type}):**"]
    if images:
        lines.append(f"• يتوفر عدد {len(images)} صور للوحدة.")
    else:
        lines.append("• لا توجد صور مرفوعة للوحدة بعد.")

    if videos:
        lines.append(f"• يتوفر عدد {len(videos)} فيديو:")
        for v in videos:
            lines.append(f"  - [{v['type']}] {v['title']}: {v['url']}")
    else:
        lines.append("• لا توجد فيديوهات مسجلة للوحدة.")

    return ToolResult(
        success=True,
        data={
            "property_id": prop.id,
            "unit_number": prop.unit_number,
            "images": images,
            "videos": videos
        },
        message="\n".join(lines)
    )


@ai_tool_registry.register(
    name="get_property_recommendations",
    description="اقتراح أفضل الوحدات المناسبة لعميل معين بناءً على ميزانيته ومتطلباته المسجلة أو معايير محددة.",
    category="inventory",
    parameters_schema={
        "properties": {
            "lead_id": {"type": "integer", "description": "معرف العميل (اختياري)"},
            "location": {"type": "string", "description": "المنطقة المفضلة"},
            "budget": {"type": "number", "description": "الميزانية المتاحة"},
            "bedrooms": {"type": "integer", "description": "عدد الغرف المطلوب"}
        }
    }
)
def get_property_recommendations(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    lead_id = params.get("lead_id")
    location = params.get("location")
    budget = params.get("budget")
    bedrooms = params.get("bedrooms")

    lead_name = ""
    if lead_id:
        lead = db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.company_id == user.company_id
        ).first()
        if lead:
            lead_name = lead.full_name
            budget = budget or lead.budget_max
            location = location or lead.preferred_location
            bedrooms = bedrooms or lead.bedrooms

    matched = find_alternative_properties(
        db=db,
        company_id=user.company_id,
        max_price=budget,
        preferred_location=location,
        bedrooms=bedrooms,
        limit=5
    )

    if not matched:
        return ToolResult(
            success=True,
            data=[],
            message="لم نتمكن من إيجاد وحدات ترشيحية تطابق المتطلبات بدقة في المخزون الحالي."
        )

    for_who = f"للعميل {lead_name}" if lead_name else "المقترحة"
    lines = [f"🌟 **أفضل الوحدات {for_who}:**"]
    for idx, p in enumerate(matched, 1):
        lines.append(
            f"{idx}. وحدة {p.get('unit_number')} بمشروع {p.get('project_name')} ({p.get('location')}) "
            f"- مساحة {p.get('area')}م² - بسعر {p.get('total_price', 0):,.0f} جنيه ({p.get('installment_plan')})"
        )

    return ToolResult(
        success=True,
        data=matched,
        message="\n".join(lines)
    )
