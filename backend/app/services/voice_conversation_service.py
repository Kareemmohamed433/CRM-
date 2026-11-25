import re
from datetime import datetime, timedelta, time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Lead, Property, User, UserRole, Activity, FollowUp, ActivityType, PriorityLevel,
    FollowUpStatus, PipelineStage
)
from backend.app.schemas.ai import (
    VoiceConversationRequest, VoiceConversationResponse,
    VoiceConfirmAndSaveRequest, VoiceConfirmAndSaveResponse,
    AIActionDraft
)
from backend.app.services.voice_service import parse_arabic_monetary_value
from backend.app.services.llm_client import is_llm_configured, generate_json_chat
from backend.app.services.scoring_service import calculate_lead_score
from backend.app.services.audit_service import log_audit_event
from backend.app.schemas.crm_actions import CRMOperationType


def parse_relative_arabic_date(text: str) -> Optional[datetime]:
    """Parses relative Arabic dates like 'بكرة', 'غداً', 'بعد يومين', 'الخميس', 'الأسبوع الجاي'."""
    t = text.lower()
    now = datetime.utcnow()

    if any(k in t for k in ["بكرة", "غدا", "غداً", "بكره", "tomorrow"]):
        return now + timedelta(days=1)
    if any(k in t for k in ["بعد يومين", "بعد يومان", "يومين", "2 days"]):
        return now + timedelta(days=2)
    if any(k in t for k in ["بعد تلات ايام", "بعد 3 ايام", "3 days"]):
        return now + timedelta(days=3)
    if any(k in t for k in ["الاسبوع الجاي", "الأسبوع الجاي", "الاسبوع القادم", "الأسبوع القادم", "next week"]):
        return now + timedelta(days=7)
    if any(k in t for k in ["الخميس", "يوم الخميس"]):
        # Find next Thursday
        days_ahead = (3 - now.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return now + timedelta(days=days_ahead)
    if any(k in t for k in ["الأحد", "الاحد"]):
        days_ahead = (6 - now.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return now + timedelta(days=days_ahead)
    if any(k in t for k in ["الاثنين", "الإثنين"]):
        days_ahead = (0 - now.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return now + timedelta(days=days_ahead)

    # Date regex match like 2026-10-30 or 30/10
    match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), 14, 0)
        except Exception:
            pass

    return None


ALLOWED_LLM_FIELDS = {
    "lead_name", "activity_type", "preferred_location", "customer_stated_budget",
    "objection", "outcome", "next_action", "sentiment", "suggested_followup_date",
}


def _scoped_leads(db: Session, company_id: int, user: Optional[User]) -> List[Lead]:
    """Leads the current user is allowed to see (company isolation + role scope)."""
    q = db.query(Lead).filter(Lead.company_id == company_id)
    if user is not None:
        if user.role == UserRole.SALES_AGENT:
            q = q.filter(Lead.assigned_agent_id == user.id)
        elif user.role == UserRole.TEAM_LEADER and user.team_id:
            q = q.filter(Lead.team_id == user.team_id)
    return q.all()


def _user_can_access_lead(user: User, lead: Lead) -> bool:
    if lead.company_id != user.company_id:
        return False
    if user.role == UserRole.SALES_AGENT:
        return lead.assigned_agent_id == user.id
    if user.role == UserRole.TEAM_LEADER and user.team_id:
        return lead.team_id == user.team_id or lead.assigned_agent_id == user.id
    return True


def extract_entities_from_text(
    db: Session,
    company_id: int,
    text: str,
    accumulated: Dict[str, Any],
    user: Optional[User] = None,
) -> Dict[str, Any]:
    """
    Extracts entities from the text and merges with existing accumulated context.
    Strictly verifies leads and properties against the company tenant.
    """
    context = dict(accumulated or {})
    raw = text.strip()
    raw_lower = raw.lower()

    # 1. Lead Matching (only if not already matched or text mentions another lead)
    NAME_TRANSLITERATION = {
        "أحمد": "ahmed", "احمد": "ahmed",
        "محمود": "mahmoud",
        "محمد": "mohamed",
        "تامر": "tamer",
        "ياسر": "yasser",
        "منى": "mona",
        "سارة": "sara",
        "مصطفى": "mostafa",
        "خالد": "khaled",
    }
    all_leads = _scoped_leads(db, company_id, user)
    matching_leads = []
    for lead in all_leads:
        full_lower = lead.full_name.lower() if lead.full_name else ""
        first_name = full_lower.split()[0] if full_lower else ""
        
        matched = False
        if (first_name and len(first_name) >= 3 and first_name in raw_lower) or (full_lower and full_lower in raw_lower):
            matched = True
        else:
            for ar_name, en_name in NAME_TRANSLITERATION.items():
                if ar_name in raw and (first_name == en_name or en_name in full_lower):
                    matched = True
                    break
        if matched:
            matching_leads.append(lead)

    # Disambiguate if user provided both first and last name (e.g. 'أحمد محمود' vs 'أحمد جمال' / 'مصطفى محمود')
    if len(matching_leads) > 1:
        both_matches = []
        for lead in matching_leads:
            full_lower = lead.full_name.lower() if lead.full_name else ""
            parts = full_lower.split()
            if len(parts) >= 2:
                first_n, last_n = parts[0], parts[-1]
                first_ar = [ar for ar, en in NAME_TRANSLITERATION.items() if en == first_n]
                last_ar = [ar for ar, en in NAME_TRANSLITERATION.items() if en == last_n]
                has_first = (first_n in raw_lower) or any(ar in raw for ar in first_ar)
                has_last = (last_n in raw_lower) or any(ar in raw for ar in last_ar)
                if has_first and has_last:
                    both_matches.append(lead)
        if both_matches:
            matching_leads = both_matches

    if len(matching_leads) > 1:
        specific_matches = []
        for lead in matching_leads:
            full_lower = lead.full_name.lower() if lead.full_name else ""
            parts = full_lower.split()
            if len(parts) >= 2:
                last_name = parts[-1]
                ar_lasts = [ar for ar, en in NAME_TRANSLITERATION.items() if en == last_name]
                if last_name in raw_lower or any(ar in raw for ar in ar_lasts):
                    specific_matches.append(lead)
        if len(specific_matches) == 1:
            matching_leads = specific_matches

    if len(matching_leads) == 1:
        context["lead_id"] = matching_leads[0].id
        context["lead_name"] = matching_leads[0].full_name
        context["lead_phone"] = matching_leads[0].phone
        context.pop("ambiguities", None)
    elif len(matching_leads) > 1 and not context.get("lead_id"):
        context["ambiguities"] = [
            f"وجدنا أكثر من عميل مطابق: {', '.join([l.full_name for l in matching_leads])}. يرجى توضيح اسم العميل بالكامل."
        ]

    # 2. Activity Type detection
    if any(k in raw_lower for k in ["معاينة", "عاين", "نزلت مع", "زيارة", "شفنا", "الموقع", "visit"]):
        context["activity_type"] = ActivityType.VISIT.value
    elif any(k in raw_lower for k in ["واتساب", "شات", "رسالة", "whatsapp", "بعتله"]):
        context["activity_type"] = ActivityType.WHATSAPP.value
    elif any(k in raw_lower for k in ["قابلت", "اجتماع", "مكتب", "meeting", "قعدت مع"]):
        context["activity_type"] = ActivityType.MEETING.value
    elif any(k in raw_lower for k in ["كلمت", "اتصلت", "مكالمة", "تليفون", "call", "phone"]):
        context["activity_type"] = ActivityType.CALL.value
    elif not context.get("activity_type"):
        context["activity_type"] = ActivityType.CALL.value

    # 3. Location detection
    if any(k in raw_lower for k in ["تجمع", "new cairo"]):
        context["preferred_location"] = "New Cairo / التجمع"
    elif any(k in raw_lower for k in ["زايد", "zayed", "أكتوبر", "october"]):
        context["preferred_location"] = "Sheikh Zayed / زايد"
    elif any(k in raw_lower for k in ["عاصمة", "capital"]):
        context["preferred_location"] = "New Capital / العاصمة الإدارية"
    elif any(k in raw_lower for k in ["ساحل", "coast"]):
        context["preferred_location"] = "North Coast / الساحل الشمالي"

    # 4. Property matching if unit or project mentioned
    props = []
    if any(k in raw_lower for k in ["وحدة", "شقة", "unit"]) or re.search(r"\d", raw):
        props = db.query(Property).filter(Property.company_id == company_id).all()
    for p in props:
        if p.unit_number and (f"وحدة {p.unit_number}".lower() in raw_lower or f"شقة {p.unit_number}".lower() in raw_lower or p.unit_number.lower() in raw_lower):
            context["property_id"] = p.id
            context["property_unit"] = p.unit_number
            break

    # 5. Objections & Outcomes
    if any(k in raw_lower for k in ["مش مقتنع بالسعر", "السعر عالي", "غالي", "سعر", "سعرها", "price"]):
        context["objection"] = "Price too high / السعر مرتفع"
        context["outcome"] = "Completed - Price Objection"
    elif any(k in raw_lower for k in ["المقدم", "down payment", "الدفعة الأولى"]):
        context["objection"] = "Down payment too high / المقدم كبير"
        context["outcome"] = "Completed - Down Payment Objection"
    elif any(k in raw_lower for k in ["الموقع", "بعيد", "location", "مكان"]):
        context["objection"] = "Location unsuitable / الموقع غير مناسب"
        context["outcome"] = "Completed - Location Objection"
    elif any(k in raw_lower for k in ["المساحة", "التقسيمة", "layout", "صغيرة"]):
        context["objection"] = "Area or layout unsuitable / المساحة أو التقسيمة غير مناسبة"
        context["outcome"] = "Completed - Layout Objection"

    # 6. Budget extraction
    monetary = parse_arabic_monetary_value(raw)
    if monetary:
        context["customer_stated_budget"] = monetary
        context["budget_max"] = monetary

    # 7. Follow-up Date parsing
    parsed_date = parse_relative_arabic_date(raw)
    if parsed_date:
        context["suggested_followup_date"] = parsed_date.strftime("%Y-%m-%dT14:00:00")

    # 8. Next Action & Sentiment
    if any(k in raw_lower for k in ["هيرد", "هيفكر", "متابعة", "أكلمه", "اتابع", "follow"]):
        context["next_action"] = "متابعة مع العميل وعرض وحدات بديلة تناسب الميزانية"
    elif context.get("objection") and not context.get("next_action"):
        context["next_action"] = "البحث عن بدائل مناسبة للميزانية والموقع المطلوب"

    if context.get("objection"):
        context["sentiment"] = "Hesitant"
    elif any(k in raw_lower for k in ["مهتم", "متحمس", "عجبته", "interested"]):
        context["sentiment"] = "Interested"
    elif not context.get("sentiment"):
        context["sentiment"] = "Neutral"

    return context


def check_missing_critical_fields(context: Dict[str, Any]) -> List[str]:
    """
    Identifies what essential information is still missing before saving to CRM.
    """
    missing = []
    if not context.get("lead_id"):
        missing.append("lead_name")
    if not context.get("customer_stated_budget") and context.get("objection") and "Price" in context.get("objection", ""):
        missing.append("customer_stated_budget")
    if not context.get("suggested_followup_date"):
        missing.append("suggested_followup_date")
    return missing


def llm_turn(
    req: VoiceConversationRequest,
    ctx: Dict[str, Any],
    missing: List[str],
    ambiguities: List[str],
    agent_name: str,
) -> Optional[Dict[str, Any]]:
    """Single LLM call per turn: returns {"fields": {...new fields...}, "reply": "short Egyptian reply"}."""
    safe_ctx = {k: v for k, v in ctx.items() if k not in ("ambiguities", "lead_phone")}
    system = (
        f"أنت مساعد صوتي مصري لنظام Nexora CRM العقاري، بتكلم المندوب {agent_name}. "
        "ردك جملة أو اتنين بالكتير بالعامية المصرية، من غير رموز ولا إيموجي، ومناسب للنطق. "
        "اسأل عن حاجة واحدة بس ناقصة في المرة، وماتسألش على حاجة المندوب قالها قبل كده في المحادثة. "
        f"البيانات المتجمعة لحد دلوقتي: {safe_ctx}. الناقص: {missing}. تعارضات: {ambiguities}. "
        "لو فيه أكتر من عميل بنفس الاسم اسأله عن الاسم الكامل أو آخر أرقام التليفون. "
        'رجّع JSON بس بالشكل: {"fields": {الحقول الجديدة اللي ظهرت في كلامه}, "reply": "ردك"} '
        f"والحقول المسموحة: {sorted(ALLOWED_LLM_FIELDS)}. تاريخ المتابعة بصيغة ISO (YYYY-MM-DDTHH:MM:SS)."
    )
    msgs = [{"role": "system", "content": system}] + [
        {"role": m.role, "content": m.content} for m in req.messages[-6:]
    ]
    data = generate_json_chat(msgs, max_tokens=160, timeout=8.0)
    return data if isinstance(data, dict) else None


def process_voice_conversation(
    db: Session,
    current_user: User,
    req: VoiceConversationRequest
) -> VoiceConversationResponse:
    """
    Handles a full multi-turn voice/text conversation with:
    - Accumulated memory context across turns.
    - Missing information detection and conversational probing in Egyptian Arabic.
    - Confirmation preview generation when ready.
    """
    if not req.messages:
        return VoiceConversationResponse(
            reply_text="أهلاً بك! أنا مساعد Nexora الصوتي. اتفضل احكيلي عن مكالمتك أو معاينتك مع العميل اليوم وسأقوم بتسجيلها وتحديث ملفه فوراً.",
            reply_audio_text="أهلاً بك يا فندم! أنا مساعد Nexora الصوتي. اتفضل احكيلي عن مكالمتك أو معاينتك مع العميل وسأقوم بتسجيلها وتحديث ملفه فوراً.",
            conversation_state="COLLECTING_INFO",
            extracted_context={},
            missing_fields=["lead_name", "suggested_followup_date"]
        )

    # 1. Update accumulated context from the conversation
    current_context = dict(req.current_context or {})
    last_user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")

    # Check if this is a Lead Creation or non-activity CRM operation
    is_lead_op = (
        req.target_form == "lead"
        or current_context.get("operation") == "CREATE_LEAD"
        or any(k in last_user_msg.lower() for k in [
            "عايز أضيف عميل", "عايز اضيف عميل", "عميل جديد", "أضف عميل", "اضف عميل",
            "تسجيل عميل", "سجل عميل جديد", "انشاء عميل"
        ])
    )
    # Appointments & reminders are executed by the CRM operator (not the activity-logging path)
    from backend.app.services.crm_operator_service import get_crm_operator
    _operator = get_crm_operator()
    _active_op = current_context.get("operation")
    messages_history = [{"role": m.role, "content": m.content} for m in req.messages]
    _intent, _route = _operator._route_intent(
        last_user_msg, _active_op, current_context.get("state", "IDLE"), messages_history
    )
    is_operator_op = (
        is_lead_op
        or _active_op in ("CREATE_APPOINTMENT", "CREATE_REMINDER")
        or _intent in (
            CRMOperationType.CREATE_APPOINTMENT, CRMOperationType.CREATE_REMINDER,
            CRMOperationType.DAILY_AGENDA, CRMOperationType.SEARCH_OVERDUE_FOLLOWUPS,
            CRMOperationType.SUMMARIZE_TASKS,
        )
    )
    if is_operator_op:
        res = _operator.process_turn(
            db=db,
            current_user=current_user,
            user_query=last_user_msg,
            current_context=current_context,
            messages_history=messages_history
        )
        return VoiceConversationResponse(
            reply_text=res.reply,
            reply_audio_text=res.reply_audio or res.reply,
            conversation_state=res.conversation_state.value,
            extracted_context=res.current_context,
            missing_fields=res.missing_fields,
            confirmation_preview=res.confirmation_preview,
            execution_result=res.execution_result
        )

    # Run deterministic extraction first
    updated_context = extract_entities_from_text(
        db=db,
        company_id=current_user.company_id,
        text=last_user_msg,
        accumulated=current_context,
        user=current_user,
    )

    # 2. Check explicit lead_id override if provided in request
    if req.lead_id and not updated_context.get("lead_id"):
        lead = db.query(Lead).filter(Lead.id == req.lead_id, Lead.company_id == current_user.company_id).first()
        if lead and _user_can_access_lead(current_user, lead):
            updated_context["lead_id"] = lead.id
            updated_context["lead_name"] = lead.full_name
            updated_context["lead_phone"] = lead.phone

    # 3. One LLM call per turn (with chat history): extracts new fields AND writes the spoken reply
    pre_missing = check_missing_critical_fields(updated_context)
    turn = None
    if is_llm_configured():
        turn = llm_turn(
            req=req,
            ctx=updated_context,
            missing=pre_missing,
            ambiguities=updated_context.get("ambiguities", []),
            agent_name=current_user.full_name.split()[0] if current_user.full_name else "",
        )
    if turn:
        fields = turn.get("fields") or {}
        if isinstance(fields, dict):
            # A name from the LLM is verified against the DB, never trusted as an id
            if fields.get("lead_name") and not updated_context.get("lead_id"):
                updated_context = extract_entities_from_text(
                    db=db,
                    company_id=current_user.company_id,
                    text=str(fields["lead_name"]),
                    accumulated=updated_context,
                    user=current_user,
                )
            for k, v in fields.items():
                if k in ALLOWED_LLM_FIELDS and k != "lead_name" and v and not updated_context.get(k):
                    updated_context[k] = v

    # 4. Check missing fields
    missing_fields = check_missing_critical_fields(updated_context)

    # Check if user explicitly asked to confirm / save in their message
    user_wants_to_confirm = any(k in last_user_msg.lower() for k in [
        "اعتمد", "احفظ", "سجل", "تمام كدة", "تمام كده", "أكد", "confirm", "save"
    ])

    is_ready_for_confirmation = (len(missing_fields) == 0) or (user_wants_to_confirm and updated_context.get("lead_id"))

    # 5. Build spoken Egyptian Arabic response
    lead_name = updated_context.get("lead_name", "")
    lead_id = updated_context.get("lead_id")
    act_type = updated_context.get("activity_type", "CALL")
    act_type_ar = "معاينة" if act_type == "VISIT" else "مكالمة"
    objection = updated_context.get("objection", "")
    budget = updated_context.get("customer_stated_budget")
    location = updated_context.get("preferred_location", "")
    followup_date = updated_context.get("suggested_followup_date", "")

    reply_text = ""
    reply_audio_text = ""

    if not is_ready_for_confirmation:
        # Ask follow-up question naturally in Egyptian Arabic
        if "lead_name" in missing_fields and updated_context.get("ambiguities"):
            reply_text = updated_context["ambiguities"][0]
            reply_audio_text = "لقيت أكتر من عميل بنفس الاسم. ممكن تقولي الاسم بالكامل أو آخر أرقام التليفون؟"
        elif "lead_name" in missing_fields:
            reply_text = "تمام يا فندم، فهمت التفاصيل، بس يا ترى مين العميل اللي تمت المقابلة أو المكالمة معاه؟ عشان نسجل النشاط في حسابه."
            reply_audio_text = "تمام يا فندم، مين العميل اللي تمت المقابلة أو المكالمة معاه؟ عشان نسجل النشاط في حسابه."
        elif "customer_stated_budget" in missing_fields:
            reply_text = f"سجلت ال{act_type_ar} مع العميل **{lead_name}** واعتراضه بخصوص {objection}. يا ترى هو حدد ميزانية معينة أو سقف سعر يقدر يدفعه عشان نرشحله وحدات بديلة؟"
            reply_audio_text = f"سجلت ال{act_type_ar} مع العميل {lead_name} واعتراضه بخصوص السعر. يا ترى حدد ميزانية معينة يقدر يدفعها عشان نرشحله بدائل؟"
        elif "suggested_followup_date" in missing_fields:
            reply_text = f"ممتاز، تم تسجيل تفاصيل ال{act_type_ar} للعميل **{lead_name}**. هل اتفقتوا على موعد محدد للمتابعة القادمة، مثلاً بكرة أو الأسبوع القادم؟"
            reply_audio_text = f"تمام يا فندم. هل اتفقتوا على موعد محدد للمتابعة القادمة مع العميل {lead_name}؟ مثلاً بكرة أو الأسبوع الجاي؟"
        else:
            reply_text = f"تمام يا فندم، سجلت ملاحظاتك بخصوص {lead_name}. هل فيه أي تفاصيل إضافية تحب تضيفها قبل الحفظ؟"
            reply_audio_text = f"تمام يا فندم، سجلت ملاحظاتك. هل فيه أي تفاصيل إضافية تحب تضيفها؟"
        conversation_state = "COLLECTING_INFO"
    else:
        # All info or user requested confirmation
        budget_str = f"{budget:,.0f} ج.م" if budget else "غير محدد بدقة"
        reply_text = (
            f"ممتاز جداً! جمعت كل التفاصيل المطلوبة:\n"
            f"• **العميل:** {lead_name}\n"
            f"• **نوع النشاط:** {act_type_ar}\n"
            f"• **الاعتراض:** {objection or 'لا يوجد اعتراض'}\n"
            f"• **الميزانية المستهدفة:** {budget_str}\n"
            f"• **الموقع:** {location or 'عام'}\n"
            f"• **المتابعة القادمة:** {followup_date or 'خلال 48 ساعة'}\n\n"
            f"جاهز للحفظ الآن في CRM. اضغط على زر **'تأكيد وحفظ في CRM'** أدناه، أو قل لي **'اعتمد وسجل'**."
        )
        reply_audio_text = (
            f"ممتاز جداً! جمعت كل تفاصيل ال{act_type_ar} مع العميل {lead_name}. "
            f"بطاقة التأكيد جاهزة أمامك الآن، اضغط تأكيد وحفظ في السي آر إم أو قولي اعتمد وسجل."
        )
        conversation_state = "READY_FOR_CONFIRMATION"

    # While collecting info, use the LLM's short Egyptian reply (it saw the full history).
    # When ready, keep the deterministic summary so the spoken text always matches the preview card.
    llm_reply = (turn or {}).get("reply")
    if conversation_state == "COLLECTING_INFO" and isinstance(llm_reply, str) and llm_reply.strip():
        reply_text = llm_reply.strip()
        reply_audio_text = re.sub(r"[*#_]", "", reply_text)

    # Build confirmation preview & Action draft if ready
    confirmation_preview = None
    action_draft = None

    if updated_context.get("lead_id"):
        confirmation_preview = {
            "lead_id": updated_context.get("lead_id"),
            "lead_name": updated_context.get("lead_name"),
            "activity_type": updated_context.get("activity_type", "CALL"),
            "preferred_location": updated_context.get("preferred_location"),
            "objection": updated_context.get("objection"),
            "customer_stated_budget": updated_context.get("customer_stated_budget"),
            "suggested_followup_date": updated_context.get("suggested_followup_date"),
            "next_action": updated_context.get("next_action") or "متابعة مع العميل وعرض الوحدات البديلة",
            "sentiment": updated_context.get("sentiment", "Neutral"),
            "summary": last_user_msg or f"نشاط {act_type_ar} مع العميل {lead_name}"
        }

        action_draft = AIActionDraft(
            action_type="create_activity",
            description=f"تسجيل {act_type_ar} للعميل {lead_name} وجدولة متابعة",
            payload=confirmation_preview,
            is_consequential=True
        )

    matched_lead = None
    if lead_id:
        matched_lead = {
            "id": lead_id,
            "full_name": updated_context.get("lead_name"),
            "phone": updated_context.get("lead_phone")
        }

    return VoiceConversationResponse(
        reply_text=reply_text,
        reply_audio_text=reply_audio_text,
        conversation_state=conversation_state,
        extracted_context=updated_context,
        missing_fields=missing_fields,
        confirmation_preview=confirmation_preview,
        action_draft=action_draft,
        matched_lead=matched_lead,
        ambiguities=updated_context.get("ambiguities", [])
    )


def confirm_and_save_voice_activity(
    db: Session,
    current_user: User,
    req: VoiceConfirmAndSaveRequest
) -> VoiceConfirmAndSaveResponse:
    """
    Saves the extracted activity to the database ONLY after explicit user confirmation.
    Enforces authentication, company tenant isolation, role authorization, and updates pipeline/scoring.
    """
    ctx = req.extracted_context
    lead_id = ctx.get("lead_id")
    if not lead_id:
        raise ValueError("Lead ID is missing from extraction context")

    # Strict tenant verification
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.company_id == current_user.company_id
    ).first()
    if not lead or not _user_can_access_lead(current_user, lead):
        raise PermissionError(f"Lead {lead_id} not found or does not belong to user company")

    activity_type_str = ctx.get("activity_type", "CALL").upper()
    act_type = ActivityType.CALL
    if activity_type_str == "VISIT":
        act_type = ActivityType.VISIT
    elif activity_type_str == "WHATSAPP":
        act_type = ActivityType.WHATSAPP
    elif activity_type_str == "MEETING":
        act_type = ActivityType.MEETING

    now = datetime.utcnow()

    # Parse followup date
    followup_dt = None
    if ctx.get("suggested_followup_date"):
        try:
            followup_dt = datetime.fromisoformat(ctx["suggested_followup_date"])
        except Exception:
            followup_dt = now + timedelta(days=2)
    else:
        followup_dt = now + timedelta(days=2)

    # 1. Create Activity
    summary_text = ctx.get("summary") or f"{act_type.value} with customer {lead.full_name}"
    new_act = Activity(
        company_id=current_user.company_id,
        lead_id=lead.id,
        property_id=ctx.get("property_id"),
        user_id=current_user.id,
        activity_type=act_type,
        summary=summary_text,
        outcome=ctx.get("outcome") or "Completed via Voice Assistant",
        objection=ctx.get("objection") or "",
        sentiment=ctx.get("sentiment") or "Neutral",
        next_action=ctx.get("next_action") or "Follow up with customer",
        next_followup_date=followup_dt,
        created_at=now
    )
    db.add(new_act)

    # 2. Update Lead Contact & Pipeline
    lead.last_contact_date = now
    lead.next_followup_date = followup_dt

    if act_type == ActivityType.VISIT:
        lead.pipeline_stage = PipelineStage.VISIT_COMPLETED

    if ctx.get("customer_stated_budget"):
        budget_val = float(ctx["customer_stated_budget"])
        lead.budget_max = budget_val
        if lead.budget_min == 0:
            lead.budget_min = budget_val * 0.7

    if ctx.get("preferred_location") and not lead.preferred_location:
        lead.preferred_location = ctx["preferred_location"]

    # 3. Auto-schedule FollowUp in CRM
    followup_task = FollowUp(
        company_id=current_user.company_id,
        lead_id=lead.id,
        assigned_user_id=lead.assigned_agent_id or current_user.id,
        team_id=lead.team_id,
        follow_up_type="Call",
        purpose=ctx.get("next_action") or f"متابعة نتيجة ال{new_act.activity_type.value} للعميل {lead.full_name}",
        due_date=followup_dt,
        priority=PriorityLevel.HIGH if ctx.get("objection") else PriorityLevel.MEDIUM,
        status=FollowUpStatus.PENDING,
        notes=f"تم الجدولة آلياً عبر مساعد الصوت Nexora AI - النتيجة: {new_act.outcome}"
    )
    db.add(followup_task)

    # 4. Recalculate lead score
    score_val, factors, priority_level = calculate_lead_score(lead)
    lead.score = score_val
    lead.score_factors = factors
    lead.priority = priority_level

    # 5. Log audit event
    log_audit_event(
        db=db,
        company_id=current_user.company_id,
        action="VOICE_ACTIVITY_CONFIRMED",
        entity_type="Activity",
        entity_id=lead.id,
        actor_id=current_user.id,
        after_state={
            "activity_type": act_type.value,
            "objection": new_act.objection,
            "budget": ctx.get("customer_stated_budget"),
            "followup_date": followup_dt.isoformat(),
            "pipeline_stage": lead.pipeline_stage.value
        }
    )

    db.commit()
    db.refresh(new_act)
    db.refresh(followup_task)

    return VoiceConfirmAndSaveResponse(
        success=True,
        activity_id=new_act.id,
        followup_id=followup_task.id,
        lead_id=lead.id,
        lead_name=lead.full_name,
        message="تم تأكيد وحفظ النشاط وتحديث سجل العميل وجدولة المتابعة بنجاح في CRM.",
        pipeline_stage=lead.pipeline_stage.value,
        score=lead.score
    )