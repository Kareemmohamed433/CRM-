import re
import logging
from datetime import datetime, timedelta, time, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.permissions import has_permission, Permissions, get_scoped_lead_query
from backend.app.models.models import (
    Lead, User, UserRole, Activity, FollowUp, Appointment, Property,
    PipelineStage, PriorityLevel, FollowUpStatus, ActivityType, AppointmentStatus,
    LeadAssignmentHistory
)
from backend.app.schemas.crm_actions import (
    CRMOperationType, ConversationState, CreateLeadDraft, UpdateLeadDraft,
    CreateFollowUpDraft, CreateAppointmentDraft, CreateReminderDraft, CRMOperatorResult
)
from backend.app.schemas.lead import LeadCreate
from backend.app.services.scoring_service import calculate_lead_score
from backend.app.services.audit_service import log_audit_event
from backend.app.services.matching_service import find_alternative_properties
from backend.app.services.voice_service import parse_arabic_monetary_value
from backend.app.services.llm_client import is_llm_configured, generate_chat_completion, generate_json_chat
from backend.app.services.person_resolver import resolve_person, plan_task_target
from backend.app.services.appointment_handler import (
    AppointmentHandlerMixin, has_date_words, fmt_date, fmt_time, appointment_flow_pending,
    looks_like_appointment_request
)
from backend.app.services.egyptian_nlp import (
    extract_person_name, parse_egyptian_date_time, score_lead_match,
    normalize_arabic_digits, normalize_arabic_text, get_current_cairo_time
)

from backend.app.services.conversation_state_manager import ConversationStateManager
from backend.app.services.ai_tools import ai_tool_registry

logger = logging.getLogger(__name__)


def extract_egyptian_phone(text: str) -> Optional[str]:
    """
    Extracts and validates an Egyptian mobile phone number.
    Egyptian mobiles: 11 digits starting with 010, 011, 012, or 015,
    or with country code +201... / 201...
    """
    normalized = normalize_arabic_digits(text)
    
    # 1. Match international format: +2010... or 2010...
    intl_match = re.search(r"(?:\+?20|0020)\s*(1[0125]\d{8})\b", normalized)
    if intl_match:
        return f"0{intl_match.group(1)}"

    # 2. Match standard mobile: 010..., 011..., 012..., 015...
    mobile_match = re.search(r"\b(01[0125]\d{8})\b", normalized)
    if mobile_match:
        return mobile_match.group(1)

    # 3. Match separated digits e.g. 010 2295 7599 or 010-2295-7599
    digits_only = re.sub(r"[^\d]", "", normalized)
    sub_match = re.search(r"(01[0125]\d{8})", digits_only)
    if sub_match:
        return sub_match.group(1)

    return None


def is_invalid_phone_attempt(text: str) -> bool:
    """Detects if user attempted to supply a phone number that is malformed/invalid."""
    norm = normalize_arabic_digits(text)
    phone_keyword = any(k in norm for k in ["رقم", "تليفون", "موبايل", "phone", "01"])
    digits = re.sub(r"[^\d]", "", norm)
    if phone_keyword and digits and len(digits) < 10:
        return True
    if digits and len(digits) in [3, 4, 5, 6, 7, 8, 9] and digits.startswith("01"):
        return True
    return False


def extract_intent_type(text: str) -> Optional[str]:
    """Detects real estate intent type (BUY vs RENT vs SELL). Handles corrections."""
    t = text.lower()
    if "شراء" in t or "شرا" in t or "تمليك" in t or "buy" in t:
        return "BUY"
    if "إيجار" in t or "ايجار" in t or "rent" in t:
        return "RENT"
    if "بيع" in t or "عرض للبيع" in t or "sell" in t:
        return "SELL"
    return None


def extract_location(text: str) -> Optional[str]:
    """Extracts Egyptian real-estate location preferences, handling corrections."""
    t = text
    if "مش" in t:
        parts = t.split("مش")
        target_part = parts[0]
        for loc in ["التجمع الخامس", "التجمع", "الشيخ زايد", "زايد", "العاصمة الإدارية", "العاصمة", "مدينة نصر", "الساحل الشمالي", "المعادي", "الشروق", "أكتوبر", "6 أكتوبر"]:
            if loc in target_part:
                return "التجمع الخامس" if loc in ["التجمع", "التجمع الخامس"] else ("الشيخ زايد" if loc in ["زايد", "الشيخ زايد"] else loc)

    locations_map = {
        "التجمع الخامس": "التجمع الخامس",
        "التجمع": "التجمع الخامس",
        "الشيخ زايد": "الشيخ زايد",
        "زايد": "الشيخ زايد",
        "العاصمة الإدارية": "العاصمة الإدارية",
        "العاصمة": "العاصمة الإدارية",
        "مدينة نصر": "مدينة نصر",
        "الساحل الشمالي": "الساحل الشمالي",
        "الساحل": "الساحل الشمالي",
        "المعادي": "المعادي",
        "الشروق": "الشروق",
        "6 أكتوبر": "6 أكتوبر",
        "أكتوبر": "6 أكتوبر",
    }
    for k, v in locations_map.items():
        if k in t:
            return v
    return None


def extract_source(text: str) -> Optional[str]:
    """Extracts lead acquisition source."""
    t = text.lower()
    if any(k in t for k in ["فيسبوك", "فيس بوك", "facebook", "fb", "إعلان فيسبوك", "اعلان فيس"]):
        return "إعلان فيسبوك"
    if any(k in t for k in ["انستجرام", "انستغرام", "instagram"]):
        return "إعلان انستجرام"
    if any(k in t for k in ["جوجل", "google"]):
        return "Google Ads"
    if any(k in t for k in ["ترشيح", "معارف", "توصية", "referral"]):
        return "ترشيح (Referral)"
    if any(k in t for k in ["مكالمة باردة", "باردة", "cold call"]):
        return "Cold Call"
    if any(k in t for k in ["معرض", "سيتي سكيب", "event"]):
        return "معرض عقاري"
    return None


def extract_budget(text: str) -> Optional[float]:
    """Extracts budget, respecting corrections like 'الميزانية مش 5 مليون، 4 مليون'."""
    t = text
    corr_match = re.search(r"الميزانية\s+مش\s+[^\s،,]+\s*(?:مليون|ملايين)?\s*(?:،|,|\s)\s*(\d+(?:\.\d+)?)\s*(?:مليون|ملايين)?", t)
    if corr_match:
        try:
            val = float(corr_match.group(1))
            return val * 1_000_000 if val < 1000 else val
        except Exception:
            pass

    if "مش" in t:
        parts = t.split("مش")
        if len(parts) > 1:
            after_mosh = parts[1]
            val = parse_arabic_monetary_value(after_mosh)
            if val is not None:
                return val

    return parse_arabic_monetary_value(t)



def clean_task_purpose(text: str) -> str:
    """Cleans task purpose / title by removing dates, times, and filler prefixes."""
    if not text:
        return "مهمة"
    t = text.strip()
    # Remove relative date keywords
    t = re.sub(r"\b(?:بكرة|بكره|غدا|غداً|النهاردة|النهارده|اليوم|بعد بكرة|بعد غد|الأسبوع الجاي|الاسبوع الجاي|الأسبوع القادم|الاسبوع القادم)\b", "", t)
    # Remove time mentions
    t = re.sub(r"\b(?:الساعة|الساعه)\s*\d+(?::\d+)?\s*(?:ونص|وربع|وتلت|وثلث)?\s*(?:الصبح|صباحا|صباحاً|بالليل|مساء|مساءً|العصر|الظهر)?\b", "", t)
    t = re.sub(r"\b(?:الساعة|الساعه)?\s*(?:واحدة|وحده|اتنين|اثنين|تلاتة|ثلاثة|اربعة|أربعة|خمسة|ستة|سبعة|تمانية|ثمانية|تسعة|عشرة|حداشر|اتناشر)\s*(?:الصبح|صباحا|صباحاً|بالليل|مساء|مساءً)?\b", "", t)
    t = re.sub(r"\b(?:الصبح|صباحا|صباحاً|بالليل|مساء|مساءً|عصرا|عصراً|ظهرا|ظهراً)\b", "", t)

    # Clean leading conjunctions/prepositions
    t = re.sub(r"^(?:لـ|ل|علشان|عشان|بخصوص|عن)\s*", "", t.strip())
    # Clean leading verb prefixes e.g. "لمراجعة" -> "مراجعة"
    if t.startswith("مراجعة") or t.startswith("متابعة") or t.startswith("تجهيز") or t.startswith("إرسال") or t.startswith("ارسال") or t.startswith("زيارة"):
        pass
    else:
        t = re.sub(r"^ل", "", t)

    t = re.sub(r"\s+", " ", t).strip(" .،,؟?-")
    return t or "مهمة"


def check_egyptian_time_details(text: str):
    """
    Extracts time information and determines if it is ambiguous (missing AM/PM).
    Returns (has_time, hour, minute, clarity):
      clarity in ('AM', 'PM', '24H', 'AMBIGUOUS', None)
    """
    norm = normalize_arabic_digits(text.lower().strip())

    AR_HOURS = {
        'واحدة': 1, 'وحده': 1, 'اتنين': 2, 'اثنين': 2, 'تلاتة': 3, 'ثلاثة': 3,
        'اربعة': 4, 'أربعة': 4, 'خمسة': 5, 'ستة': 6, 'سبعة': 7, 'تمانية': 8, 'ثمانية': 8,
        'تسعة': 9, 'عشرة': 10, 'حداشر': 11, 'اتناشر': 12
    }

    has_am = any(k in norm for k in ['الصبح', 'صباحا', 'صباحاً', 'am'])
    has_pm = any(k in norm for k in ['بالليل', 'مساء', 'مساءً', 'pm', 'العصر', 'بعد الظهر'])
    has_noon = 'الظهر' in norm

    m = re.search(
        r'(?:الساعة|الساعه)?\s*(\d{1,2}|واحدة|وحده|اتنين|اثنين|تلاتة|ثلاثة|اربعة|أربعة|خمسة|ستة|سبعة|تمانية|ثمانية|تسعة|عشرة|حداشر|اتناشر)(?::(\d{2}))?\s*(ونص|وربع|وتلت|وثلث)?',
        norm
    )
    if not m:
        return False, None, None, None

    raw_h = m.group(1)
    raw_m = m.group(2)
    frac = m.group(3)

    if raw_h.isdigit():
        h = int(raw_h)
    elif raw_h in AR_HOURS:
        h = AR_HOURS[raw_h]
    else:
        return False, None, None, None

    minute = 0
    if raw_m and raw_m.isdigit():
        minute = int(raw_m)
    elif frac:
        if 'نص' in frac:
            minute = 30
        elif 'ربع' in frac:
            minute = 15
        elif 'تلت' in frac or 'ثلث' in frac:
            minute = 20

    if h > 12:
        return True, h, minute, '24H'
    elif has_am:
        final_h = 0 if h == 12 else h
        return True, final_h, minute, 'AM'
    elif has_pm:
        final_h = 12 if h == 12 else h + 12
        return True, final_h, minute, 'PM'
    elif has_noon:
        return True, 12, minute, 'AM'
    else:
        return True, h, minute, 'AMBIGUOUS'


def extract_property_query_filters(query: str, existing_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    import re
    filters = dict(existing_filters or {})
    q = query.lower().strip()

    # 1. Location / Governorate / Area
    gov_map = {
        'القاهرة': 'القاهرة', 'cairo': 'القاهرة',
        'الجيزة': 'الجيزة', 'giza': 'الجيزة',
        'الإسكندرية': 'الإسكندرية', 'alexandria': 'الإسكندرية',
        'البحر الأحمر': 'البحر الأحمر', 'red sea': 'البحر الأحمر',
        'الساحل': 'الساحل الشمالي', 'north coast': 'الساحل الشمالي'
    }
    for k, v in gov_map.items():
        if k in q:
            filters['governorate'] = v
            break

    areas_map = {
        'التجمع الخامس': 'التجمع الخامس',
        'التجمع': 'التجمع الخامس',
        'new cairo': 'التجمع الخامس',
        'الشيخ زايد': 'الشيخ زايد',
        'زايد': 'الشيخ زايد',
        'sheikh zayed': 'الشيخ زايد',
        '6 أكتوبر': '6 أكتوبر',
        'أكتوبر': '6 أكتوبر',
        'october': '6 أكتوبر',
        'مدينة نصر': 'مدينة نصر',
        'nasr city': 'مدينة نصر',
        'مصر الجديدة': 'مصر الجديدة',
        'heliopolis': 'مصر الجديدة',
        'المعادي': 'المعادي',
        'maadi': 'المعادي',
        'الشروق': 'الشروق',
        'shorouk': 'الشروق',
        'مدينتي': 'مدينتي',
        'madinaty': 'مدينتي',
        'العاصمة الإدارية': 'العاصمة الإدارية',
        'العاصمة': 'العاصمة الإدارية',
        'new capital': 'العاصمة الإدارية',
        'المستقبل': 'مدينة المستقبل',
        'الرحاب': 'الرحاب'
    }
    for k, v in areas_map.items():
        if k in q:
            filters['location'] = v
            break

    # 2. Property Type
    type_map = {
        'شقة': 'Apartment', 'شقق': 'Apartment', 'apartment': 'Apartment',
        'فيلا': 'Villa', 'فيلات': 'Villa', 'villa': 'Villa',
        'دوبلكس': 'Duplex', 'duplex': 'Duplex',
        'تاون هاوس': 'Townhouse', 'تاونهاوس': 'Townhouse', 'townhouse': 'Townhouse',
        'توين هاوس': 'Twinhouse', 'توينهاوس': 'Twinhouse', 'twinhouse': 'Twinhouse',
        'بنتهاوس': 'Penthouse', 'penthouse': 'Penthouse',
        'استوديو': 'Studio', 'استديو': 'Studio', 'studio': 'Studio',
        'مكتب': 'Office', 'تجاري': 'Commercial'
    }
    for k, v in type_map.items():
        if k in q:
            filters['property_type'] = v
            break

    # 3. Budget / Max Price
    budget_patterns = [
        r'(?:لحد|في حدود|بحد أقصى|أقل من|سعرها|ميزانية|أقصى سعر|حتى)\s*(\d+(?:\.\d+)?)\s*(مليون|م|million)',
        r'(\d+(?:\.\d+)?)\s*(?:مليون|م|million)',
        r'(?:لحد|في حدود|بحد أقصى|أقل من|حتى)\s*(\d{6,})'
    ]
    for pat in budget_patterns:
        m = re.search(pat, q)
        if m:
            val = float(m.group(1))
            if len(m.groups()) > 1 and m.group(2) in ('مليون', 'م', 'million'):
                val = val * 1_000_000
            elif val < 100:
                val = val * 1_000_000
            filters['max_price'] = val
            break

    # 4. Bedrooms
    bed_patterns = [
        (r'(?:خليها|عايز|تكون|فيها)\s*(\d+)\s*(?:غرف|غرفة|نوم)', lambda m: int(m.group(1))),
        (r'(\d+)\s*(?:غرف|غرفة|نوم)', lambda m: int(m.group(1))),
        (r'غرفتين', lambda m: 2),
        (r'(?:تلات|ثلاث)\s*غرف', lambda m: 3),
        (r'(?:أربع|اربع)\s*غرف', lambda m: 4),
        (r'(?:خمس|خمسة)\s*غرف', lambda m: 5),
    ]
    for pat, parser in bed_patterns:
        m = re.search(pat, q)
        if m:
            filters['bedrooms'] = parser(m)
            break

    # 5. Sorting / Comparison
    if any(k in q for k in ['الأرخص', 'أرخص', 'وريني الأرخص', 'أقل سعر', 'cheapest']):
        filters['sort_by'] = 'price_asc'
    elif any(k in q for k in ['الأغلى', 'أغلى', 'أعلى سعر', 'most expensive']):
        filters['sort_by'] = 'price_desc'
    elif any(k in q for k in ['أكبر شوية', 'أكبر مساحة', 'عايز أكبر', 'مفيش حاجة أكبر']):
        filters['sort_by'] = 'area_desc'
        if 'min_area' not in filters:
            filters['min_area'] = 140.0
        else:
            filters['min_area'] += 20.0
    elif any(k in q for k in ['أصغر', 'أصغر مساحة']):
        filters['sort_by'] = 'area_asc'

    return filters


class ConversationalCRMOperator(AppointmentHandlerMixin):
    """
    Conversational CRM Operator for Nexora CRM.
    Behaves as a professional Egyptian real-estate sales operations assistant.
    Accurately classifies user intent, manages multi-turn context and drafts,
    handles smart reminders and CRM follow-ups, and executes verified database transactions.
    """

    def _finalize_turn(
        self,
        db: Session,
        current_user: User,
        state_dto: Any,
        res: CRMOperatorResult
    ) -> CRMOperatorResult:
        try:
            state_dto.intent = res.operation.value if hasattr(res.operation, 'value') else str(res.operation)
            state_dto.missing_fields = res.missing_fields
            state_dto.confirmation_preview = res.confirmation_preview or {}
            if res.suggested_tools_called:
                state_dto.pending_tool = res.suggested_tools_called[0]
            for k, v in res.current_context.items():
                if k not in ("state", "operation", "missing_fields", "confirmation_preview"):
                    state_dto.collected_fields[k] = v
            ConversationStateManager.save_state(db, state_dto)
            res.current_context["conversation_id"] = state_dto.conversation_id
        except Exception as e:
            logger.warning(f"[CRMOperator] Failed syncing conversation state: {e}")
        return res

    def process_turn(
        self,
        db: Session,
        current_user: User,
        user_query: str,
        current_context: Optional[Dict[str, Any]] = None,
        messages_history: Optional[List[Dict[str, str]]] = None,
    ) -> CRMOperatorResult:
        ctx = dict(current_context or {})
        q = user_query.strip()
        q_lower = q.lower()

        state_dto = ConversationStateManager.get_or_create_state(
            db, current_user,
            conversation_id=ctx.get("conversation_id"),
            legacy_context=ctx
        )
        # If client passes explicit context (e.g. with draft or lead_id),
        # only fill in missing fields from state_dto if they don't contradict the current draft
        if not ctx.get("operation") and not ctx.get("draft"):
            for k, v in state_dto.collected_fields.items():
                if k not in ctx:
                    ctx[k] = v
        elif "draft" in ctx:
            ctx.pop("lead_id", None)

        logger.info(f"[CRMOperator] Processing turn from user '{current_user.email}': '{q}'")

        # ---------------------------------------------------------------------
        # 0. Handle Cancellations
        # ---------------------------------------------------------------------
        if any(k in q_lower for k in ["إلغي", "الغي", "إلغاء", "الغاء", "كنسل", "تراجع", "مش عايز اسجل", "مش عايز اكمل", "cancel"]):
            return CRMOperatorResult(
                reply="تم إلغاء العملية بناءً على طلبك يا فندم. لو احتجت أي مساعدة تانية في السي آر إم أنا تحت أمرك.",
                conversation_state=ConversationState.CANCELLED,
                operation=CRMOperationType.GENERAL_QUESTION,
                current_context={},
                missing_fields=[]
            )

        # ---------------------------------------------------------------------
        # 0.1 Handle Objections & Incomplete Data Complaints
        # ---------------------------------------------------------------------
        if self._is_objection(q):
            lead_id = ctx.get("lead_id")
            if lead_id:
                existing_lead = db.query(Lead).filter(
                    Lead.id == lead_id,
                    Lead.company_id == current_user.company_id
                ).first()
                if existing_lead:
                    reply = (
                        f"معاك حق تماماً يا فندم، بعتذر لحضرتك جداً على التسرع. "
                        f"العميل {existing_lead.full_name} مسجل بالفعل في النظام برقم #{existing_lead.id}. "
                        f"نقدر نحدّث ونكمل باقي بياناته فوراً بدون إنشاء عميل مكرر. إيه الميزانية أو البيانات اللي تحب نضيفها؟"
                    )
                    return CRMOperatorResult(
                        reply=reply,
                        reply_audio=reply,
                        conversation_state=ConversationState.COLLECTING_INFO,
                        operation=CRMOperationType.UPDATE_LEAD,
                        current_context={
                            "operation": CRMOperationType.UPDATE_LEAD.value,
                            "state": ConversationState.COLLECTING_INFO.value,
                            "lead_id": existing_lead.id,
                            "lead_name": existing_lead.full_name
                        },
                        missing_fields=["budget"]
                    )

            # If draft was not created yet:
            draft_dict = ctx.get("draft", {})
            draft = CreateLeadDraft(**draft_dict) if draft_dict else CreateLeadDraft()
            reply = (
                f"معاك حق يا فندم، بعتذر لحضرتك جداً. لسه ماسجلتش العميل في السي آر إم "
                f"ومحتفظ بكل البيانات اللي قولتهالي. ممكن تقولي الميزانية كام أو إيه البيانات اللي تحب نضيفها؟"
            )
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={
                    "operation": CRMOperationType.CREATE_LEAD.value,
                    "state": ConversationState.COLLECTING_INFO.value,
                    "draft": draft.model_dump()
                },
                missing_fields=draft.missing_required_fields()
            )

        # ---------------------------------------------------------------------
        # 1. State Recovery & Active Operation Detection
        # ---------------------------------------------------------------------
        active_op = ctx.get("operation")
        active_state = ctx.get("state", ConversationState.IDLE.value)

        logger.info(
            f"[CRMOperator] ctx keys={list(ctx.keys())} op={active_op} state={active_state} "
            f"history_len={len(messages_history or [])}"
        )

        # Appointment flow whose context was lost on the client: recover it from history
        if not active_op and messages_history and appointment_flow_pending(messages_history, q):
            return self._handle_create_appointment(
                db, current_user, q, {}, history=messages_history
            )

        # Reconstruct draft from history if context was lost
        if not active_op and messages_history:
            ctx = self._reconstruct_context_from_history(messages_history)
            active_op = ctx.get("operation")
            active_state = ctx.get("state", ConversationState.IDLE.value)

        # ---------------------------------------------------------------------
        # 0.2 Handle Active UPDATE_LEAD Operation
        # ---------------------------------------------------------------------
        if active_op == CRMOperationType.UPDATE_LEAD.value:
            return self._handle_update_lead_turn(db, current_user, q, ctx)

        # ---------------------------------------------------------------------
        # 1.5 Continue an active CREATE_APPOINTMENT flow (multi-turn)
        # ---------------------------------------------------------------------
        if active_op == CRMOperationType.CREATE_APPOINTMENT.value and active_state in [
            ConversationState.COLLECTING_INFO.value,
            ConversationState.READY_FOR_CONFIRMATION.value,
        ]:
            return self._handle_create_appointment(db, current_user, q, ctx, history=messages_history)

        # ---------------------------------------------------------------------
        # 2. User Intent Classification
        # ---------------------------------------------------------------------
        intent, route = self._route_intent(q, active_op, active_state, messages_history)
        logger.info(f"[CRMOperator] Classified intent: {intent.value} (active_op={active_op}, active_state={active_state})")

        # ---------------------------------------------------------------------
        # 2.5 Handle CREATE_APPOINTMENT Operation (new request)
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.CREATE_APPOINTMENT:
            return self._handle_create_appointment(db, current_user, q, ctx, history=messages_history)

        # ---------------------------------------------------------------------
        # 3. Handle CREATE_REMINDER Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.CREATE_REMINDER or (active_op == CRMOperationType.CREATE_REMINDER.value and active_state in [ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value]):
            return self._handle_create_reminder_turn(db, current_user, q, ctx)

        # ---------------------------------------------------------------------
        # 4. Handle CREATE_FOLLOWUP / CREATE_TASK Operation
        # ---------------------------------------------------------------------
        if intent in [CRMOperationType.CREATE_FOLLOWUP, CRMOperationType.CREATE_TASK] or (active_op in [CRMOperationType.CREATE_FOLLOWUP.value, CRMOperationType.CREATE_TASK.value] and active_state in [ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value]):
            return self._handle_create_followup(db, current_user, q, ctx)

        # ---------------------------------------------------------------------
        # 5. Handle CREATE_LEAD Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.CREATE_LEAD or (active_op == CRMOperationType.CREATE_LEAD.value and active_state in [ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value]):
            return self._handle_create_lead_turn(db, current_user, q, ctx)

        # ---------------------------------------------------------------------
        # 6. Handle DAILY_AGENDA Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.DAILY_AGENDA:
            return self._handle_daily_agenda(
                db, current_user, q, route.get("target_date"), route.get("scope")
            )

        # ---------------------------------------------------------------------
        # 7. Handle SEARCH_OVERDUE_FOLLOWUPS Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.SEARCH_OVERDUE_FOLLOWUPS:
            return self._handle_overdue_followups(db, current_user)

        # ---------------------------------------------------------------------
        # 7.5 Handle SALES_SUMMARY Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.SALES_SUMMARY:
            tool_res = ai_tool_registry.execute("get_sales_summary", db, current_user, {"period": "month"})
            return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                reply=tool_res.message,
                reply_audio=tool_res.message,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.SALES_SUMMARY,
                execution_result=tool_res.data,
                suggested_tools_called=["get_sales_summary"]
            ))

        # ---------------------------------------------------------------------
        # 7.6 Handle TEAM_PERFORMANCE Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.TEAM_PERFORMANCE:
            tool_res = ai_tool_registry.execute("get_team_performance", db, current_user, {})
            return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                reply=tool_res.message,
                reply_audio=tool_res.message,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.TEAM_PERFORMANCE,
                execution_result=tool_res.data,
                suggested_tools_called=["get_team_performance"]
            ))

        # ---------------------------------------------------------------------
        # 7.7 Handle CUSTOMER_PIPELINE Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.CUSTOMER_PIPELINE:
            tool_res = ai_tool_registry.execute("get_customer_pipeline", db, current_user, {})
            return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                reply=tool_res.message,
                reply_audio=tool_res.message,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.CUSTOMER_PIPELINE,
                execution_result=tool_res.data,
                suggested_tools_called=["get_customer_pipeline"]
            ))

        # ---------------------------------------------------------------------
        # 7.8 Handle CUSTOMER_HISTORY Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.CUSTOMER_HISTORY:
            lead_res = resolve_person(q, db, current_user.company_id)
            lead_id = lead_res.get("lead_id") or ctx.get("lead_id")
            if lead_id:
                tool_res = ai_tool_registry.execute("get_customer_history", db, current_user, {"customer_id": lead_id})
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply=tool_res.message,
                    reply_audio=tool_res.message,
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.CUSTOMER_HISTORY,
                    execution_result={"timeline": tool_res.data},
                    suggested_tools_called=["get_customer_history"]
                ))
            else:
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply="مين العميل اللي تحب أعرض لحضرتك سجله التاريخي؟",
                    reply_audio="مين العميل اللي تحب أعرض لحضرتك سجله التاريخي؟",
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=CRMOperationType.CUSTOMER_HISTORY,
                    missing_fields=["customer_id"]
                ))

        # ---------------------------------------------------------------------
        # 7.9 Handle PROPERTY_OFFER Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.PROPERTY_OFFER:
            lead_res = resolve_person(q, db, current_user.company_id)
            lead_id = lead_res.get("lead_id") or ctx.get("lead_id")
            prop_id = ctx.get("property_id")
            if lead_id and not prop_id:
                first_prop = db.query(Property).filter(Property.company_id == current_user.company_id).first()
                if first_prop:
                    prop_id = first_prop.id
            if lead_id and prop_id:
                tool_res = ai_tool_registry.execute("prepare_property_message", db, current_user, {"customer_id": lead_id, "property_id": prop_id})
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply=tool_res.message,
                    reply_audio="تم تجهيز رسالة الواتساب للعميل بالمواصفات والسعر ونظام السداد.",
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.PROPERTY_OFFER,
                    execution_result=tool_res.data,
                    suggested_tools_called=["prepare_property_message"]
                ))
            elif not lead_id:
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply="تحب أجهز رسالة العرض لأي عميل؟",
                    reply_audio="تحب أجهز رسالة العرض لأي عميل؟",
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=CRMOperationType.PROPERTY_OFFER,
                    missing_fields=["customer_id"]
                ))

        # ---------------------------------------------------------------------
        # 8. Handle SUMMARIZE_TASKS Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.SUMMARIZE_TASKS:
            return self._handle_summarize_tasks(db, current_user)

        # ---------------------------------------------------------------------
        # 9. Handle SEARCH_PROPERTIES Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.SEARCH_PROPERTIES:
            return self._handle_search_properties(db, current_user, q, ctx, messages_history)

        # ---------------------------------------------------------------------
        # 10. Handle SEARCH_LEADS Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.SEARCH_LEADS:
            return self._handle_search_leads(db, current_user, q)

        # ---------------------------------------------------------------------
        # 11. Handle General Inquiries / Fallback
        # ---------------------------------------------------------------------
        return self._handle_general_query(db, current_user, q, messages_history)

    def _classify_intent(
        self,
        query: str,
        active_op: Optional[str],
        active_state: str
    ) -> CRMOperationType:
        q = query.lower().strip()

        # 1. Reminder Intent takes highest priority (even if client words or names are present)
        reminder_triggers = [
            "فكرني", "فكرنى", "ذكرني", "تذكير", "حطلي تذكير", "حط تذكير", "اعمل تذكير",
            "متنسنيش", "عايز تذكير", "نبهني", "remind me", "reminder"
        ]
        if any(k in q for k in reminder_triggers):
            return CRMOperationType.CREATE_REMINDER

        # If already in an active CREATE_REMINDER flow
        if active_op == CRMOperationType.CREATE_REMINDER.value and active_state in [ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value]:
            return CRMOperationType.CREATE_REMINDER

        # 1.5 An explicit appointment request wins over follow-up wording:
        # "ضيف معاد ... لعمل متابعة مع العميل X" is an appointment whose purpose is a follow-up.
        in_followup_flow = (
            active_op in [CRMOperationType.CREATE_FOLLOWUP.value, CRMOperationType.CREATE_TASK.value]
            and active_state in [ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value]
        )
        if not in_followup_flow and looks_like_appointment_request(q):
            return CRMOperationType.CREATE_APPOINTMENT

        # 2. Explicit CRM Follow-up intent (without reminder wording)
        followup_triggers = [
            "سجل متابعة", "سجل متابعه", "عايز أتابع مع", "عايز اتابع مع", "أتابع مع",
            "اتابع مع", "حددلي متابعة", "اعمل متابعة", "متابعة مع العميل", "متابعه مع العميل",
            "سجل متابعه لأحمد", "سجل متابعة لاحمد", "create followup"
        ]
        if any(k in q for k in followup_triggers):
            return CRMOperationType.CREATE_FOLLOWUP

        # 2.1 Explicit task intent ("سجل مهمة لـ ...", "كلف احمد ...")
        task_triggers = [
            "سجل مهمة", "سجل مهمه", "سجلي مهمة", "سجلي مهمه", "اعمل مهمة", "اعمل مهمه",
            "ضيف مهمة", "ضيف مهمه", "أضف مهمة", "اضف مهمة", "اضافة مهمة", "إضافة مهمة",
            "عين مهمة", "عيّن مهمة", "اسند مهمة", "أسند مهمة", "كلف ", "create task",
        ]
        if any(k in q for k in task_triggers):
            return CRMOperationType.CREATE_TASK

        if active_op in [CRMOperationType.CREATE_FOLLOWUP.value, CRMOperationType.CREATE_TASK.value] and active_state in [ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value]:
            return CRMOperationType.CREATE_FOLLOWUP

        # 3. Appointments & Inspections
        appointment_triggers = [
            "حدد ميعاد", "احجز معاينة", "جدول ميعاد", "معاد معاينة", "موعد معاينة",
            "عندي مقابلة", "عندي ميعاد", "احجز ميعاد للعميل"
        ]
        appt_nouns = ["معاد", "ميعاد", "موعد", "مقابلة", "مقابله", "اجتماع"]
        appt_verbs = ["اضيف", "أضيف", "ضيف", "سجل", "احجز", "حدد", "جدول", "اعمل", "عايز", "عندي"]
        # Questions ("إيه المعاد؟") and past-tense logs ("قابلت العميل امبارح") are NOT new bookings
        appt_excluded = [
            "ايه", "إيه", "امتى", "إمتى", "قابلت", "كلمت", "اتصلت", "عملت", "خلصت",
            "امبارح", "إمبارح", "أمس", "اتقابلنا", "سجلت",
        ]
        if any(k in q for k in appointment_triggers) or (
            not any(x in q for x in appt_excluded)
            and any(n in q for n in appt_nouns)
            and any(v in q for v in appt_verbs)
        ):
            return CRMOperationType.CREATE_APPOINTMENT

        # 4. Explicit Lead Creation (ONLY when user explicitly requests adding/registering a new client)
        lead_creation_triggers = [
            "عايز أضيف عميل جديد", "عايز اضيف عميل جديد", "عايز أضيف عميل", "عايز اضيف عميل",
            "أضف عميل جديد", "اضف عميل جديد", "أضف عميل", "اضف عميل", "ضيف عميل جديد",
            "سجل عميل جديد", "تسجيل عميل جديد", "انشاء عميل جديد", "أضف عميل للسي آر إم",
            "سجل بيانات العميل ده", "عميل جديد اسمه"
        ]
        if any(k in q for k in lead_creation_triggers):
            return CRMOperationType.CREATE_LEAD

        # If already inside an active CREATE_LEAD flow
        if active_op == CRMOperationType.CREATE_LEAD.value and active_state in [ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value]:
            return CRMOperationType.CREATE_LEAD

        # 5. Overdue Follow-ups Search
        if any(k in q for k in ["المتابعات المتأخرة", "المتابعات المتاخرة", "المتأخرات", "المتاخرات", "متأخر عندي", "متابعات متأخرة"]):
            return CRMOperationType.SEARCH_OVERDUE_FOLLOWUPS

        # 5.5 Sales Summary & Reports
        if any(k in q for k in ["ملخص المبيعات", "ايرادات", "إيرادات", "ارقام المبيعات", "أرقام المبيعات", "تقرير المبيعات", "sales summary"]):
            return CRMOperationType.SALES_SUMMARY

        # 5.6 Team Performance
        if any(k in q for k in ["اداء الفريق", "أداء الفريق", "اداء المبيعات", "أداء المبيعات", "مؤشرات الفريق", "انجاز الفريق", "team performance"]):
            return CRMOperationType.TEAM_PERFORMANCE

        # 5.7 Customer Pipeline Stages
        if any(k in q for k in ["مراحل البيع", "خط الانابيب", "خط الأنابيب", "توزيع العملاء", "pipeline"]):
            return CRMOperationType.CUSTOMER_PIPELINE

        # 5.8 Customer History & Timeline
        if any(k in q for k in ["تاريخ العميل", "سجل العميل", "انشطة العميل", "أنشطة العميل", "مكالمات العميل", "تاريخ التواصل"]):
            return CRMOperationType.CUSTOMER_HISTORY

        # 5.9 Property Offer / WhatsApp Pitch
        if any(k in q for k in ["رسالة واتساب", "رساله واتساب", "عرض عقاري", "عرض سعر", "ابعت عرض", "تجهيز عرض", "property offer"]):
            return CRMOperationType.PROPERTY_OFFER

        # 6. Task Summarization
        if any(k in q for k in ["لخص لي مهام", "لخص مهام", "تلخيص المهام", "ملخص المهام", "summarize tasks"]):
            return CRMOperationType.SUMMARIZE_TASKS

        # 7. Daily Agenda & Briefing
        if self._is_agenda_query(query) or any(k in q for k in ["مواعيد اليوم", "متابعات اليوم", "جدولي", "جدول اليوم", "إيه اللي ورايا", "ورايا ايه", "عندي إيه بكرة", "عندي ايه بكرة", "اعرضلي مواعيدي", "overdue", "agenda", "briefing"]):
            return CRMOperationType.DAILY_AGENDA

        # 8. Properties Search & Inventory
        if active_op == CRMOperationType.SEARCH_PROPERTIES.value and any(k in q for k in [
            "خليها", "غرف", "غرفة", "أرخص", "الأرخص", "أكبر", "أصغر", "الأغلى", "أغلى",
            "مليون", "ألف", "ميزانية", "سعر", "قارن", "مقارنة", "فيديو", "صور", "كام شقة",
            "كام وحدة", "نفس المنطقة", "دي", "الاتنين", "وريني", "التجمع", "زايد", "مدينة نصر", "أكتوبر", "المعادي", "الشروق", "القاهرة", "الجيزة"
        ]):
            return CRMOperationType.SEARCH_PROPERTIES

        if any(k in q for k in [
            "شقق", "شقة", "عقارات", "وحدات متاحة", "دورلي على", "عندك وحدات", "فلل", "فيلا",
            "دوبلكس", "بميزانية", "وحدات في", "كام شقة", "كام وحدة", "مخزون", "قارن بين",
            "قارنلي", "فيديو الوحدة", "فيديو ليها", "صور الوحدة", "مخزون الوحدات"
        ]):
            return CRMOperationType.SEARCH_PROPERTIES

        # 9. Search Leads
        if any(k in q for k in ["وريني عملاء", "ابحث عن عميل", "دور على عميل", "مين العملاء", "عملاء التجمع", "عملاء زايد"]):
            return CRMOperationType.SEARCH_LEADS

        return CRMOperationType.GENERAL_QUESTION

    # -------------------------------------------------------------------------
    # LLM INTENT ROUTER
    # -------------------------------------------------------------------------
    _ROUTER_INTENTS = {
        "daily_agenda": CRMOperationType.DAILY_AGENDA,
        "overdue_followups": CRMOperationType.SEARCH_OVERDUE_FOLLOWUPS,
        "summarize_tasks": CRMOperationType.SUMMARIZE_TASKS,
        "search_properties": CRMOperationType.SEARCH_PROPERTIES,
        "search_leads": CRMOperationType.SEARCH_LEADS,
        "create_appointment": CRMOperationType.CREATE_APPOINTMENT,
        "create_reminder": CRMOperationType.CREATE_REMINDER,
        "create_followup": CRMOperationType.CREATE_FOLLOWUP,
        "create_lead": CRMOperationType.CREATE_LEAD,
        "sales_summary": CRMOperationType.SALES_SUMMARY,
        "team_performance": CRMOperationType.TEAM_PERFORMANCE,
        "customer_pipeline": CRMOperationType.CUSTOMER_PIPELINE,
        "customer_history": CRMOperationType.CUSTOMER_HISTORY,
        "property_offer": CRMOperationType.PROPERTY_OFFER,
        "log_activity": CRMOperationType.GENERAL_QUESTION,
        "general": CRMOperationType.GENERAL_QUESTION,
    }
    # The LLM may only START flows that ask for explicit confirmation before saving.
    # create_followup saves immediately, so it still requires explicit wording (rule-based).
    _LLM_BLOCKED_ACTIONS = {CRMOperationType.CREATE_FOLLOWUP, CRMOperationType.CREATE_TASK}
    _CREATE_INTENTS = {
        CRMOperationType.CREATE_LEAD, CRMOperationType.CREATE_REMINDER,
        CRMOperationType.CREATE_FOLLOWUP, CRMOperationType.CREATE_TASK,
        CRMOperationType.CREATE_APPOINTMENT,
    }
    _route_cache: Dict[Any, Any] = {}

    def _llm_route(self, q: str, history: Optional[List[Dict[str, str]]]) -> Optional[Dict[str, Any]]:
        """Asks the LLM what the user wants. Returns a validated dict or None (caller falls back to rules)."""
        if not is_llm_configured():
            return None
        ref = get_current_cairo_time()
        weekdays = ["الاتنين", "التلات", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        system = (
            "أنت راوتر نوايا لنظام Nexora CRM العقاري، والمستخدمين مندوبين مبيعات بيتكلموا بالعامية المصرية "
            "وممكن يغلطوا في الإملاء. مهمتك تفهم المستخدم عايز إيه وترجع JSON فقط من غير أي شرح.\n"
            f"النهاردة: {ref.date().isoformat()} ({weekdays[ref.weekday()]}).\n"
            "النوايا الممكنة:\n"
            "- daily_agenda: عايز يعرف عنده إيه (مواعيد أو متابعات أو مهام) النهاردة أو بكرة أو يوم معين. "
            "أمثلة: 'عندي اي بكره', 'ورايا ايه', 'جدولي الخميس', 'مواعيدي بكرة'.\n"
            "- overdue_followups: المتابعات المتأخرة.\n"
            "- summarize_tasks: تلخيص المهام.\n"
            "- search_properties: بحث عن وحدات أو عقارات متاحة.\n"
            "- search_leads: بحث عن عملاء أو عرضهم.\n"
            "- create_appointment: عايز يحجز أو يضيف موعد/مقابلة/معاينة/مكالمة محددة مع عميل.\n"
            "- create_reminder: تذكير شخصي.\n"
            "- create_followup: تسجيل متابعة مع عميل.\n"
            "- create_lead: إضافة عميل جديد.\n"
            "- log_activity: بيحكي عن مكالمة أو زيارة أو مقابلة حصلت فعلاً وعايز يسجلها.\n"
            "- general: أي حاجة تانية (سؤال عام، سلام، شكر، كلام مش مفهوم).\n"
            "قواعد: 'عندي اي مشكلة في العقد' مش daily_agenda. لو الجملة قصيرة وغامضة (مثلاً 'متابعات') "
            "اعتمد على المحادثة السابقة. target_date للـ daily_agenda بس، بصيغة YYYY-MM-DD (بكرة = النهاردة+1)، "
            "أو null. scope قايمة من 'appointments' و'followups'، وسيبها فاضية لو عايز الاتنين.\n"
            'رجّع بالشكل ده بس: {"intent": "...", "confidence": 0.0, "target_date": null, "scope": []}'
        )
        msgs = [{"role": "system", "content": system}]
        for h in (history or [])[-4:]:
            role, content = h.get("role"), (h.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": content[:300]})
        if not (msgs[-1]["role"] == "user" and msgs[-1]["content"] == q[:300]):
            msgs.append({"role": "user", "content": q[:300]})

        try:
            data = generate_json_chat(msgs, temperature=0.0, max_tokens=200, timeout=6.0)
        except Exception as e:
            logger.warning(f"[CRMOperator] LLM router failed: {e}")
            return None
        if not isinstance(data, dict):
            return None
        key = str(data.get("intent", "")).strip().lower()
        if key not in self._ROUTER_INTENTS:
            return None
        try:
            conf = float(data.get("confidence", 0.7))
        except (TypeError, ValueError):
            conf = 0.7

        target = None
        raw_date = data.get("target_date")
        if isinstance(raw_date, str) and raw_date.strip():
            try:
                d = date.fromisoformat(raw_date.strip()[:10])
                if abs((d - ref.date()).days) <= 90:
                    target = d
            except ValueError:
                target = None
        raw_scope = data.get("scope")
        scope = {s for s in raw_scope if s in ("appointments", "followups")} if isinstance(raw_scope, list) else set()
        return {
            "key": key, "intent": self._ROUTER_INTENTS[key], "confidence": conf,
            "target_date": target, "scope": scope,
        }

    def _route_intent(
        self,
        q: str,
        active_op: Optional[str],
        active_state: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[CRMOperationType, Dict[str, Any]]:
        """
        LLM-first understanding with deterministic safety rails:
        - A running multi-turn flow is never interrupted by the router.
        - Explicit create phrases (rules) win over the LLM for anything that writes data.
        - The LLM can only start flows that ask for confirmation; follow-up creation needs explicit wording.
        - If the LLM is off / fails / is unsure, the keyword rules decide.
        """
        rule_intent = self._classify_intent(q, active_op, active_state)
        in_flow = bool(active_op) and active_state in (
            ConversationState.COLLECTING_INFO.value, ConversationState.READY_FOR_CONFIRMATION.value
        )
        if in_flow:
            return rule_intent, {}

        today_iso = get_current_cairo_time().date().isoformat()
        tail = tuple((h.get("role"), (h.get("content") or "")[:80]) for h in (history or [])[-4:])
        cache_key = (q, active_op, active_state, today_iso, tail)
        routed = self._route_cache.get(cache_key, "MISS")
        if routed == "MISS":
            routed = self._llm_route(q, history)
            if len(self._route_cache) > 256:
                self._route_cache.clear()
            self._route_cache[cache_key] = routed

        if not routed or routed["confidence"] < 0.55:
            return rule_intent, {}

        llm_intent = routed["intent"]
        logger.info(
            f"[CRMOperator] LLM router: {routed['key']} (conf={routed['confidence']}, "
            f"date={routed['target_date']}, scope={sorted(routed['scope'])}); rules said {rule_intent.value}"
        )
        if rule_intent in self._CREATE_INTENTS:
            return rule_intent, routed          # explicit write verbs in the text win
        if llm_intent in self._LLM_BLOCKED_ACTIONS:
            return rule_intent, routed          # never auto-start an immediate-save action
        if llm_intent == CRMOperationType.GENERAL_QUESTION and rule_intent != CRMOperationType.GENERAL_QUESTION:
            return rule_intent, routed          # specialized rules win over general fallback
        return llm_intent, routed

    def _is_agenda_query(self, query: str) -> bool:
        """Spelling-tolerant detection of 'what do I have today/tomorrow' questions."""
        n = normalize_arabic_text(normalize_arabic_digits(query))
        words = n.replace("؟", " ").replace("?", " ").split()
        direct = [
            "ورايا", "جدولي", "جدول اليوم", "جدول بكره", "مواعيدي", "مواعيد اليوم", "مواعيد بكره",
            "متابعات اليوم", "متابعات بكره", "مهامي", "مهام اليوم", "مهام بكره", "اجنده", "اجندتي",
            "agenda", "briefing",
        ]
        if any(k in n for k in direct):
            return True
        has_have = any(w in words for w in ["عندي", "عندى", "عليا"])
        asks_what = any(w in words for w in [
            "اي", "ايه", "ايش", "شو", "اعرف", "قولي", "قوللي", "وريني", "عرفني", "اعرضلي",
        ])
        topic = has_date_words(query) or any(
            k in n for k in ["مواعيد", "متابعات", "مهام", "معاد", "ميعاد", "شغل"]
        )
        return has_have and asks_what and topic

    def _is_objection(self, query: str) -> bool:
        q = query.lower().strip()
        objection_phrases = [
            "ما سألتنيش", "ما سألتش", "ماطلبتش مني", "ما طلبتش", "ازاي سجلت", "إزاي سجلت",
            "طب إزاي", "طب ازاي", "لسه ماقولتلكش", "لسه ما كملتش", "عايز أكمل البيانات",
            "عايز اكمل البيانات", "البيانات ناقصة", "انت ماسألتنيش", "إنت ما سألتنيش",
            "ليه سجلت", "ازاي تسجل", "إزاي تسجل", "ماخدتش مني", "ما اخدتش مني",
            "ولا ميزانية ولا حاجة", "بدون ميزانية", "من غير ميزانية"
        ]
        return any(p in q for p in objection_phrases)

    def _is_explicit_confirmation(self, query: str) -> bool:
        q = query.lower().strip()
        # If the user expresses an objection, hesitation, inquiry, or confusion, it is NOT confirmation
        if self._is_objection(q):
            return False

        hesitations = ["مش فاهم", "مش فاهمة", "يعني ايه", "كنت عايز", "عايز اسجل", "عايز اضيف", "ليه", "قصدك", "أكتوبر", "اكتوبر"]
        if any(k in q for k in hesitations):
            return False

        # If negated
        if any(neg in q for neg in ["مش", "لا مش", "بلاش", "ما تسجلش", "استنى"]):
            return False

        # Check for direct affirmative confirmation phrases
        explicit_confirmations = [
            "تأكيد وتنفيذ الإجراء في crm", "تأكيد وتنفيذ الإجراء في السي آر إم",
            "تأكيد وتنفيذ الإجراء", "تأكيد وتنفيذ", "تأكيد", "أعتمد", "اعتمد",
            "أيوه سجل", "ايوه سجل", "ايوة سجل", "تمام سجل", "سجل يا فندم", "سجل الآن",
            "سجل دلوقتي", "نعم سجل", "تمام اعتمد", "اعتمد التسجيل", "احفظ البيانات",
            "تمام احفظ", "موافق سجل", "أكد التسجيل", "اكيد سجل", "تمام يا باشا سجل",
            "تمام يا فندم سجل", "ايوه", "أيوه", "نعم", "موافق", "تمام كده سجل", "سجل خلاص", "confirm",
            "لا كده تمام", "لا تمام", "كده تمام", "تمام كده", "كله تمام", "كده مظبوط", "مظبوط سجل",
            "زي الفل سجل", "زي الفل اعتمد", "تمام يا باشا", "تمام كده يا فندم", "اعتمد كده"
        ]
        for phrase in explicit_confirmations:
            if phrase in q:
                return True

        tokens = [w.strip(".,!؟،") for w in q.split()]
        if len(tokens) <= 3 and any(w in tokens for w in ["سجل", "احفظ", "اعتمد", "أعتمد", "تأكيد"]):
            return True

        return False

    # -------------------------------------------------------------------------
    # SMART REMINDER & CRM FOLLOWUP IMPLEMENTATION
    # -------------------------------------------------------------------------

    def _handle_create_reminder_turn(
        self,
        db: Session,
        current_user: User,
        query: str,
        ctx: Dict[str, Any]
    ) -> CRMOperatorResult:
        """
        Manages smart reminder and follow-up creation in natural Egyptian Arabic:
        1. Understands relative dates (بكرة, بعد بكرة, الخميس) and times (الساعة 5, الصبح).
        2. Searches authorized CRM leads without jumping to lead creation.
        3. Supports 3 distinct lead matching outcomes (1 match, multiple matches, 0 matches).
        4. Distinguishes Personal Reminders from CRM Follow-ups.
        5. Executes database transaction upon explicit confirmation without duplication.
        """
        q = query.strip()
        q_lower = q.lower()

        # Load draft from context
        draft_dict = ctx.get("draft", {})
        draft = CreateReminderDraft(**draft_dict) if draft_dict else CreateReminderDraft()

        # Check if user wants to switch from personal reminder to new lead creation
        if any(k in q_lower for k in ["ضيفه كعميل جديد", "ضيفه عميل", "عميل جديد", "سجل كعميل", "سجله عميل"]):
            cand_name = draft.candidate_name or draft.lead_name or extract_person_name(q) or "العميل"
            new_lead_draft = CreateLeadDraft(full_name=cand_name)
            reply = f"تمام يا فندم، هنسجل {cand_name} كعميل جديد في النظام. ممكن رقم تليفونه؟"
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={
                    "operation": CRMOperationType.CREATE_LEAD.value,
                    "state": ConversationState.COLLECTING_INFO.value,
                    "draft": new_lead_draft.model_dump()
                },
                missing_fields=new_lead_draft.missing_required_fields()
            )

        # Check if user requested personal reminder when asked
        if any(k in q_lower for k in ["سجل تذكير شخصي", "تذكير شخصي", "سجلها كتذكير شخصي", "تذكير", "شخصي"]):
            cand_name = draft.candidate_name or "العميل"
            draft.reminder_type = "personal_reminder"
            draft.lead_id = None
            draft.purpose = f"متابعة مع {cand_name}"
            reply = f"تمام، جهزت التذكير الشخصي لمتابعة {cand_name} بكرة. تحب أعتمد وأسجل التذكير في مهامك؟"
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.READY_FOR_CONFIRMATION,
                operation=CRMOperationType.CREATE_REMINDER,
                current_context={
                    "operation": CRMOperationType.CREATE_REMINDER.value,
                    "state": ConversationState.READY_FOR_CONFIRMATION.value,
                    "draft": draft.model_dump()
                },
                confirmation_preview={
                    "reminder_type": "تذكير شخصي",
                    "purpose": draft.purpose,
                    "due_date": draft.due_date
                }
            )

        # Detect confirmation when in READY_FOR_CONFIRMATION
        if ctx.get("state") == ConversationState.READY_FOR_CONFIRMATION.value and self._is_explicit_confirmation(q):
            return self._execute_create_reminder(db, current_user, draft, ctx)

        # Detect time specification during ongoing reminder turn
        if draft.lead_id or draft.candidate_name:
            if any(k in q_lower for k in ["من غير وقت", "بدون وقت", "مش محدد وقت", "تخطي"]):
                lead_name = draft.lead_name or draft.candidate_name or "العميل"
                draft.has_specific_time = False
                reply = f"تمام، متابعة مع {lead_name} بكرة من غير وقت محدد. أعتمدها وأسجلها في السي آر إم؟"
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.READY_FOR_CONFIRMATION,
                    operation=CRMOperationType.CREATE_REMINDER,
                    current_context={
                        "operation": CRMOperationType.CREATE_REMINDER.value,
                        "state": ConversationState.READY_FOR_CONFIRMATION.value,
                        "draft": draft.model_dump()
                    },
                    confirmation_preview={
                        "reminder_type": "متابعة عميل CRM" if draft.lead_id else "تذكير شخصي",
                        "lead_id": draft.lead_id,
                        "lead_name": lead_name,
                        "due_date": draft.due_date,
                        "purpose": draft.purpose
                    }
                )

            # Check if user gave a time e.g. "الساعة 5"
            time_dt, has_time = parse_egyptian_date_time(q)
            if has_time:
                draft.has_specific_time = True
                draft.due_date = time_dt.isoformat()
                time_str = f"الساعة {time_dt.strftime('%I:%M').lstrip('0')} {'مساءً' if time_dt.hour >= 12 else 'صباحاً'}"
                draft.due_time = time_str
                lead_name = draft.lead_name or draft.candidate_name or "العميل"
                reply = f"تمام، متابعة مع {lead_name} بكرة {time_str}. أعتمدها وأسجلها في السي آر إم؟"
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.READY_FOR_CONFIRMATION,
                    operation=CRMOperationType.CREATE_REMINDER,
                    current_context={
                        "operation": CRMOperationType.CREATE_REMINDER.value,
                        "state": ConversationState.READY_FOR_CONFIRMATION.value,
                        "draft": draft.model_dump()
                    },
                    confirmation_preview={
                        "reminder_type": "متابعة عميل CRM" if draft.lead_id else "تذكير شخصي",
                        "lead_id": draft.lead_id,
                        "lead_name": lead_name,
                        "due_date": draft.due_date,
                        "due_time": draft.due_time,
                        "purpose": draft.purpose
                    }
                )

        # ---------------------------------------------------------------------
        # Initial Extraction for CREATE_REMINDER
        # ---------------------------------------------------------------------
        due_dt, has_time = parse_egyptian_date_time(q)
        draft.due_date = due_dt.isoformat()
        draft.has_specific_time = has_time
        if has_time:
            draft.due_time = f"الساعة {due_dt.strftime('%I:%M').lstrip('0')} {'مساءً' if due_dt.hour >= 12 else 'صباحاً'}"

        extracted_name = extract_person_name(q)
        if extracted_name:
            draft.candidate_name = extracted_name
            draft.purpose = f"متابعة مع {extracted_name}"

            # Search authorized leads within tenant
            scoped_leads_query = get_scoped_lead_query(db.query(Lead), current_user)
            company_leads = scoped_leads_query.all()

            # Rank matching leads
            matched_leads = []
            for lead in company_leads:
                s = score_lead_match(lead.full_name, extracted_name)
                if s >= 0.7:
                    matched_leads.append((s, lead))

            matched_leads.sort(key=lambda x: x[0], reverse=True)

            if len(matched_leads) == 1:
                # Exactly one matching lead found in user's authorized scope
                matched = matched_leads[0][1]
                draft.lead_id = matched.id
                draft.lead_name = matched.full_name
                draft.reminder_type = "crm_followup"
                draft.purpose = f"متابعة مع {matched.full_name}"

                reply = f"أكيد، لقيت العميل {matched.full_name}. هربط التذكير بملفه. تحب تحدد الساعة ولا أخليه من غير وقت؟"
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=CRMOperationType.CREATE_REMINDER,
                    current_context={
                        "operation": CRMOperationType.CREATE_REMINDER.value,
                        "state": ConversationState.COLLECTING_INFO.value,
                        "draft": draft.model_dump()
                    }
                )

            elif len(matched_leads) > 1:
                # Ambiguous: multiple matching leads
                names_desc = "، ".join([f"{l[1].full_name} (#{l[1].id})" for l in matched_leads[:3]])
                draft.ambiguous_leads = [{"id": l[1].id, "name": l[1].full_name} for l in matched_leads[:3]]
                reply = f"لقيت أكتر من عميل باسم {extracted_name} ({names_desc}). تقصد أنهي واحد؟"
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=CRMOperationType.CREATE_REMINDER,
                    current_context={
                        "operation": CRMOperationType.CREATE_REMINDER.value,
                        "state": ConversationState.COLLECTING_INFO.value,
                        "draft": draft.model_dump()
                    }
                )

            else:
                # No matching client in CRM
                draft.reminder_type = "personal_reminder"
                draft.lead_id = None
                reply = f"ملقتش عميل بالاسم ده في النظام. تحب أسجل تذكير شخصي باسم {extracted_name}، ولا تضيفه كعميل جديد؟"
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=CRMOperationType.CREATE_REMINDER,
                    current_context={
                        "operation": CRMOperationType.CREATE_REMINDER.value,
                        "state": ConversationState.COLLECTING_INFO.value,
                        "draft": draft.model_dump()
                    }
                )

        # Reminder without a specific client name
        draft.reminder_type = "personal_reminder"
        draft.purpose = q
        reply = f"حاضر، هسجلك تذكير بخصوص {q} بكرة. تحب أعتمد التذكير في مهامك؟"
        return CRMOperatorResult(
            reply=reply,
            reply_audio=reply,
            conversation_state=ConversationState.READY_FOR_CONFIRMATION,
            operation=CRMOperationType.CREATE_REMINDER,
            current_context={
                "operation": CRMOperationType.CREATE_REMINDER.value,
                "state": ConversationState.READY_FOR_CONFIRMATION.value,
                "draft": draft.model_dump()
            },
            confirmation_preview={
                "reminder_type": "تذكير شخصي",
                "purpose": draft.purpose,
                "due_date": draft.due_date
            }
        )

    def _execute_create_reminder(
        self,
        db: Session,
        current_user: User,
        draft: CreateReminderDraft,
        ctx: Dict[str, Any]
    ) -> CRMOperatorResult:
        """Executes actual database persistence for reminder or follow-up."""
        # Prevent duplicate creation
        if ctx.get("followup_id"):
            reply = f"المتابعة مسجلة بالفعل في النظام برقم #{ctx.get('followup_id')}."
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.CONFIRMED,
                operation=CRMOperationType.CREATE_REMINDER,
                execution_result={"success": True, "followup_id": ctx.get("followup_id")}
            )

        due_date_str = draft.due_date
        due_dt = datetime.fromisoformat(due_date_str) if due_date_str else get_current_cairo_time().replace(tzinfo=None) + timedelta(days=1)

        try:
            if draft.reminder_type == "crm_followup" and draft.lead_id:
                lead = db.query(Lead).filter(
                    Lead.id == draft.lead_id,
                    Lead.company_id == current_user.company_id
                ).first()
                if not lead:
                    return CRMOperatorResult(
                        reply="لم أتمكن من العثور على العميل في النظام.",
                        conversation_state=ConversationState.ERROR
                    )

                new_f = FollowUp(
                    company_id=current_user.company_id,
                    lead_id=lead.id,
                    assigned_user_id=current_user.id,
                    team_id=lead.team_id,
                    follow_up_type="Call",
                    purpose=draft.purpose or f"متابعة مع {lead.full_name}",
                    due_date=due_dt,
                    priority=PriorityLevel.MEDIUM,
                    status=FollowUpStatus.PENDING,
                    notes="تم الإنشاء عبر مساعد Nexora AI الذكي"
                )
                db.add(new_f)
                lead.next_followup_date = due_dt
                db.commit()
                db.refresh(new_f)

                time_info = f" {draft.due_time}" if draft.due_time else ""
                reply = f"تمام، اتسجلت المتابعة بنجاح برقم #{new_f.id} للعميل {lead.full_name}{time_info}. هتلاقيها في مهامك."
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.CONFIRMED,
                    operation=CRMOperationType.CREATE_REMINDER,
                    current_context={
                        "operation": CRMOperationType.CREATE_REMINDER.value,
                        "state": ConversationState.CONFIRMED.value,
                        "followup_id": new_f.id,
                        "lead_id": lead.id
                    },
                    execution_result={
                        "success": True,
                        "followup_id": new_f.id,
                        "lead_id": lead.id,
                        "due_date": due_dt.isoformat()
                    },
                    suggested_tools_called=["create_crm_followup"],
                    related_links=[{"title": lead.full_name, "url": f"/leads/{lead.id}"}]
                )
            else:
                # Personal reminder (lead_id is None)
                cand = draft.candidate_name or draft.lead_name or "مهمة شخصية"
                purpose = draft.purpose or f"متابعة مع {cand}"
                new_f = FollowUp(
                    company_id=current_user.company_id,
                    lead_id=None,
                    assigned_user_id=current_user.id,
                    team_id=current_user.team_id,
                    follow_up_type="Personal Reminder",
                    purpose=purpose,
                    due_date=due_dt,
                    priority=PriorityLevel.MEDIUM,
                    status=FollowUpStatus.PENDING,
                    notes="تذكير شخصي تم إنشاؤه عبر المساعد الذكي"
                )
                db.add(new_f)
                db.commit()
                db.refresh(new_f)

                reply = f"تمام، اتسجل التذكير الشخصي بنجاح برقم #{new_f.id}. هتلاقيه في مهامك."
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.CONFIRMED,
                    operation=CRMOperationType.CREATE_REMINDER,
                    current_context={
                        "operation": CRMOperationType.CREATE_REMINDER.value,
                        "state": ConversationState.CONFIRMED.value,
                        "followup_id": new_f.id
                    },
                    execution_result={
                        "success": True,
                        "followup_id": new_f.id,
                        "due_date": due_dt.isoformat()
                    },
                    suggested_tools_called=["create_personal_reminder"]
                )
        except Exception as e:
            db.rollback()
            logger.error(f"[CRMOperator] Failed to persist reminder to DB: {e}", exc_info=True)
            return CRMOperatorResult(
                reply=f"حدث خطأ أثناء حفظ التذكير في قاعدة البيانات: {str(e)}.",
                conversation_state=ConversationState.ERROR
            )

    # -------------------------------------------------------------------------
    # TASK / FOLLOW-UP  (person-aware: lead vs colleague, always with confirmation)
    # -------------------------------------------------------------------------

    _TASK_STOP_WORDS = {
        "بكرة", "بكره", "النهارده", "النهاردة", "انهارده", "عشان", "علشان", "بخصوص", "عن",
        "الساعة", "الساعه", "الصبح", "بعد", "يوم", "الاسبوع", "الأسبوع",
    }
    _SELF_WORDS = {"نفسي", "نفسى", "ليا", "لي", "لىّ", "عندي"}

    @classmethod
    def _extract_task_target(cls, q: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Pulls (recipient_name, task_text) from "سجلي مهمة لـ Dalia Fouad لمراجعة عقد العميل بكرة".
        Works with Latin and Arabic names; independent of extract_person_name.
        """
        m = re.search(
            r"(?:مهمة|مهمه|متابعة|متابعه|كلف|اسند|أسند|عين|عيّن)\s+(?:لـ|ل|مع|إلى|الى)\s*(.+)$", q
        )
        if not m:
            return None, None
        tokens = m.group(1).split()
        if not tokens or tokens[0].strip(".,،؟?") in cls._SELF_WORDS:
            return None, None

        name: List[str] = []
        idx = 0
        for idx, t in enumerate(tokens):
            tc = t.strip(".,،؟?")
            is_latin = bool(re.match(r"^[A-Za-z]", tc))
            if tc in cls._TASK_STOP_WORDS or len(name) >= 3:
                break
            if name and not is_latin and re.match(r"^ل.{4,}$", tc):   # "لمراجعة" starts the task text
                break
            name.append(tc)
        else:
            idx = len(tokens)

        rest_tokens = [t.strip(".,،؟?") for t in tokens[idx:]]
        while rest_tokens and rest_tokens[-1] in cls._TASK_STOP_WORDS:
            rest_tokens.pop()
        if rest_tokens and re.match(r"^ل.{4,}$", rest_tokens[0]):
            rest_tokens[0] = rest_tokens[0][1:]
        rest = " ".join(rest_tokens).strip() or None
        return (" ".join(name).strip() or None), rest

    @staticmethod
    def _extract_task_purpose(q: str) -> Optional[str]:
        """Pulls the 'what' out of the sentence ("... لمراجعة عقد العميل") instead of storing the whole sentence."""
        m = re.search(r"(?:^|\s)(?:علشان|عشان|بخصوص|عن|لمراجعة|لمتابعة|لتجهيز)\s+(.+)$", q)
        if m:
            raw = m.group(1).strip(" .،؟?")
            return clean_task_purpose(raw) or None
        return None

    def _fuzzy_resolve_person(self, db: Session, current_user: User, name: str) -> Dict[str, List]:
        """resolve_person (ilike) + fuzzy fallback so أ/إ/ا و ة/ه و ى/ي ما تبوظش المطابقة."""
        res = resolve_person(db, current_user, name)

        if not res["leads"]:
            scoped = get_scoped_lead_query(db.query(Lead), current_user).all()
            scored = sorted(
                ((score_lead_match(l.full_name, name), l) for l in scoped),
                key=lambda x: x[0], reverse=True,
            )
            res["leads"] = [l for sc, l in scored if sc >= 0.7][:5]

        if not res["users"]:
            colleagues = db.query(User).filter(
                User.company_id == current_user.company_id,
                User.is_active == True,  # noqa: E712
                User.id != current_user.id,
            ).all()
            scored = sorted(
                ((score_lead_match(u.full_name, name), u) for u in colleagues),
                key=lambda x: x[0], reverse=True,
            )
            res["users"] = [u for sc, u in scored if sc >= 0.7][:5]
        return res

    def _advance_task_or_ask_time(
        self, op: CRMOperationType, plan: Dict[str, Any], current_user: User
    ) -> CRMOperatorResult:
        """
        Enforces Part 1: Scheduled time is mandatory before confirmation.
        If date alone was provided, asks for time.
        If time is ambiguous (1-12 without AM/PM), asks for AM/PM clarification.
        """
        plan["purpose"] = clean_task_purpose(plan.get("purpose", ""))

        # 1. Missing time altogether -> ask "الساعة كام؟"
        if not plan.get("has_time"):
            reply = "تمام، تحب تحدد المهمة الساعة كام؟"
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=op,
                current_context={
                    "operation": op.value,
                    "state": ConversationState.COLLECTING_INFO.value,
                    "task_ask": {
                        "step": "need_time",
                        "plan": plan,
                    }
                }
            )

        # 2. Time is present but ambiguous (1-12 without AM/PM) -> ask "صباحاً ولا مساءً؟"
        if plan.get("time_clarity") == "AMBIGUOUS" and plan.get("pending_hour"):
            h = plan["pending_hour"]
            reply = f"تقصد {h} صباحًا ولا {h} مساءً؟"
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=op,
                current_context={
                    "operation": op.value,
                    "state": ConversationState.COLLECTING_INFO.value,
                    "task_ask": {
                        "step": "need_ampm",
                        "plan": plan,
                        "pending_hour": h,
                        "pending_minute": plan.get("pending_minute", 0)
                    }
                }
            )

        # 3. Time is completely clear -> display preview and ask for explicit confirmation
        return self._task_confirmation_result(op, plan, current_user)

    def _task_confirmation_result(
        self, op: CRMOperationType, plan: Dict[str, Any], current_user: User
    ) -> CRMOperatorResult:
        due_dt = datetime.fromisoformat(plan["due_date"])
        when = due_dt.strftime("%Y-%m-%d") + (f" الساعة {due_dt.strftime('%H:%M')}" if plan.get("has_time") else "")

        if plan.get("lead_name") and plan["assigned_user_id"] != current_user.id:
            reply = (
                f"هسجل المهمة دي:\n"
                f"• الموظف المكلف: {plan['assignee_name']}\n"
                f"• العميل: {plan['lead_name']} (#{plan['lead_id']})\n"
                f"• المهمة: {plan.get('purpose', 'مهمة')}\n"
                f"• الموعد: {when}\n"
                f"أعتمد وأسجل المهمة في النظام؟"
            )
            kind_label = "مهمة لزميل مرتبطة بعميل"
        elif plan["target_kind"] == "lead":
            reply = (f"جهزت متابعة للعميل {plan['lead_name']} بتاريخ {when}. "
                     f"تحب أعتمدها وأسجلها في مهامك؟")
            kind_label = "متابعة عميل"
        elif plan["target_kind"] == "colleague":
            reply = (f"جهزت مهمة لـ {plan['assignee_name']} بتاريخ {when}"
                     f"{': ' + plan['purpose'] if plan.get('purpose') else ''}. تحب أعتمدها؟")
            kind_label = "مهمة لزميل"
        else:
            reply = (f"جهزت مهمة ليك بتاريخ {when}"
                     f"{': ' + plan['purpose'] if plan.get('purpose') else ''}. تحب أعتمدها؟")
            kind_label = "مهمة شخصية"

        return CRMOperatorResult(
            reply=reply,
            reply_audio=reply,
            conversation_state=ConversationState.READY_FOR_CONFIRMATION,
            operation=op,
            current_context={
                "operation": op.value,
                "state": ConversationState.READY_FOR_CONFIRMATION.value,
                "task_plan": plan,
            },
            confirmation_preview={
                "type": kind_label,
                "lead_id": plan.get("lead_id"),
                "lead_name": plan.get("lead_name"),
                "assigned_user_id": plan.get("assigned_user_id"),
                "assignee_name": plan.get("assignee_name"),
                "purpose": plan.get("purpose"),
                "due_date": plan["due_date"],
            },
        )

    def _handle_create_followup(
        self,
        db: Session,
        current_user: User,
        query: str,
        ctx: Dict[str, Any]
    ) -> CRMOperatorResult:
        """
        Task / follow-up creation. Uses person_resolver to decide whether the name is a
        LEAD (customer) or a USER (colleague), enforces the role-rank rules, requires mandatory
        scheduled time with AM/PM clarification, and ALWAYS asks for confirmation before writing anything.
        """
        q = query.strip()
        q_lower = q.lower()

        if ctx.get("operation") in (CRMOperationType.CREATE_FOLLOWUP.value, CRMOperationType.CREATE_TASK.value):
            op = CRMOperationType(ctx["operation"])
        elif any(k in q_lower for k in ["مهمة", "مهمه", "مهام", "task", "كلف"]):
            op = CRMOperationType.CREATE_TASK
        else:
            op = CRMOperationType.CREATE_FOLLOWUP

        # ---- A. A plan is waiting for confirmation ---------------------------------
        plan = ctx.get("task_plan")
        if plan and ctx.get("state") == ConversationState.READY_FOR_CONFIRMATION.value:
            if self._is_explicit_confirmation(q):
                return self._execute_task_plan(db, current_user, plan, ctx, op)
            new_dt, new_has_time = parse_egyptian_date_time(q)
            if new_has_time:  # user is adjusting the time
                plan = dict(plan, due_date=new_dt.isoformat(), has_time=True)
                return self._task_confirmation_result(op, plan, current_user)
            if len(q.split()) <= 4:  # short, unclear reply -> keep waiting
                return self._task_confirmation_result(op, plan, current_user)
            # long text = a brand-new request, fall through as a fresh turn
            ctx = {}

        # ---- B. We asked a clarifying question; this turn is the answer -------------
        ask = ctx.get("task_ask")
        forced_lead: Optional[Lead] = None
        force_kind: Optional[str] = None

        if ask and ask.get("step") == "need_time":
            plan = ask.get("plan", {})
            has_t, h, m, clarity = check_egyptian_time_details(q)
            if not has_t:
                parsed_dt, parsed_has_t = parse_egyptian_date_time(q)
                if parsed_has_t:
                    has_t = True
                    h = parsed_dt.hour
                    m = parsed_dt.minute
                    clarity = "EXACT"

            if not has_t or h is None:
                reply = "تحب تحدد الموعد الساعة كام بالظبط؟ (مثلاً: الساعة 9 صباحاً أو 6 مساءً)"
                return CRMOperatorResult(
                    reply=reply, reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=op,
                    current_context=ctx
                )

            if clarity == "AMBIGUOUS" and 1 <= h <= 12:
                reply = f"تقصد {h} صباحًا ولا {h} مساءً؟"
                return CRMOperatorResult(
                    reply=reply, reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=op,
                    current_context={
                        "operation": op.value,
                        "state": ConversationState.COLLECTING_INFO.value,
                        "task_ask": {
                            "step": "need_ampm",
                            "plan": plan,
                            "pending_hour": h,
                            "pending_minute": m or 0
                        }
                    }
                )

            # Hour is unambiguous
            due_dt = datetime.fromisoformat(plan["due_date"]).replace(hour=h, minute=m or 0, second=0, microsecond=0)
            plan["due_date"] = due_dt.isoformat()
            plan["has_time"] = True
            plan["time_clarity"] = clarity
            return self._task_confirmation_result(op, plan, current_user)

        elif ask and ask.get("step") == "need_ampm":
            plan = ask.get("plan", {})
            pending_h = ask.get("pending_hour", 9)
            pending_m = ask.get("pending_minute", 0)

            is_pm = any(k in q.lower() for k in ["مساء", "مساءً", "بالليل", "pm", "العصر"])
            is_am = any(k in q.lower() for k in ["صباح", "صباحا", "صباحاً", "الصبح", "am"])

            if not is_pm and not is_am:
                reply = f"تقصد {pending_h} صباحًا ولا {pending_h} مساءً؟"
                return CRMOperatorResult(
                    reply=reply, reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=op,
                    current_context=ctx
                )

            if is_pm:
                final_h = 12 if pending_h == 12 else pending_h + 12
            else:
                final_h = 0 if pending_h == 12 else pending_h

            due_dt = datetime.fromisoformat(plan["due_date"]).replace(hour=final_h, minute=pending_m, second=0, microsecond=0)
            plan["due_date"] = due_dt.isoformat()
            plan["has_time"] = True
            plan["time_clarity"] = "EXACT"
            return self._task_confirmation_result(op, plan, current_user)

        elif ask and ask.get("step") == "need_customer":
            target_user_id = ask["assigned_user_id"]
            target_user = db.query(User).filter(User.id == target_user_id).first()
            purpose = ask.get("purpose")
            due_dt = datetime.fromisoformat(ask["due_date"])
            has_time = bool(ask.get("has_time"))
            time_clarity = ask.get("time_clarity")
            pending_hour = ask.get("pending_hour")
            pending_minute = ask.get("pending_minute", 0)

            cust_name = extract_person_name(q) or re.sub(r"^(?:العميل|عميل|اسم العميل|اسمه)\s*", "", q).strip(" .،؟?")
            leads = get_scoped_lead_query(db.query(Lead), current_user).all()
            matches = [l for l in leads if score_lead_match(l.full_name, cust_name) >= 0.7]
            exact = [l for l in matches if normalize_arabic_text(l.full_name) == normalize_arabic_text(cust_name)]
            if len(exact) == 1:
                matches = exact

            if not matches:
                reply = f"ملقتش عميل باسم {cust_name} في النظام. اتأكد من اسم العميل أو ضيفه في النظام الأول."
                return CRMOperatorResult(
                    reply=reply, reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=op,
                    current_context=ctx
                )

            lead = matches[0]
            if lead.assigned_agent_id != target_user.id:
                owner = db.query(User).filter(User.id == lead.assigned_agent_id).first()
                owner_name = owner.full_name if owner else "مستشار آخر"
                reply = (
                    f"العميل {lead.full_name} مسجل بالفعل ولكن يتبع المستشار ({owner_name}) وليس {target_user.full_name}. "
                    f"هل تريد المتابعة بدون تغيير المالك أم طلب نقل العميل أولاً؟"
                )
                return CRMOperatorResult(
                    reply=reply, reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=op,
                    current_context={
                        "operation": op.value,
                        "state": ConversationState.COLLECTING_INFO.value,
                        "task_ask": {
                            "step": "ownership_conflict",
                            "assigned_user_id": target_user.id,
                            "assignee_name": target_user.full_name,
                            "lead_id": lead.id,
                            "lead_name": lead.full_name,
                            "purpose": clean_task_purpose(purpose),
                            "due_date": due_dt.isoformat(),
                            "has_time": has_time,
                            "time_clarity": time_clarity,
                            "pending_hour": pending_hour,
                            "pending_minute": pending_minute
                        }
                    }
                )

            plan = {
                "target_kind": "colleague_with_lead",
                "lead_id": lead.id,
                "lead_name": lead.full_name,
                "assigned_user_id": target_user.id,
                "assignee_name": target_user.full_name,
                "purpose": clean_task_purpose(purpose) or f"مهمة من {current_user.full_name}",
                "due_date": due_dt.isoformat(),
                "has_time": has_time,
                "time_clarity": time_clarity,
                "pending_hour": pending_hour,
                "pending_minute": pending_minute
            }
            return self._advance_task_or_ask_time(op, plan, current_user)

        elif ask and ask.get("step") == "ownership_conflict":
            target_user_id = ask["assigned_user_id"]
            target_user = db.query(User).filter(User.id == target_user_id).first()
            purpose = ask.get("purpose")
            due_dt = datetime.fromisoformat(ask["due_date"])
            has_time = bool(ask.get("has_time"))
            time_clarity = ask.get("time_clarity")
            pending_hour = ask.get("pending_hour")
            pending_minute = ask.get("pending_minute", 0)
            lead_id = ask["lead_id"]
            lead_name = ask["lead_name"]

            if any(k in q for k in ["بدون تغيير", "بدون نقل", "تابع", "كمل", "سجل", "ايوه", "أيوه", "نعم", "موافق", "تمام"]):
                plan = {
                    "target_kind": "colleague_with_lead",
                    "lead_id": lead_id,
                    "lead_name": lead_name,
                    "assigned_user_id": target_user.id,
                    "assignee_name": target_user.full_name,
                    "purpose": clean_task_purpose(purpose) or f"مهمة من {current_user.full_name}",
                    "due_date": due_dt.isoformat(),
                    "has_time": has_time,
                    "time_clarity": time_clarity,
                    "pending_hour": pending_hour,
                    "pending_minute": pending_minute
                }
                return self._advance_task_or_ask_time(op, plan, current_user)
            elif any(k in q for k in ["نقل", "انقل", "طلب نقل"]):
                reply = f"تقدر تطلب نقل العميل {lead_name} من صفحة تفاصيل العميل أو عبر طلب نقل رسمي للمدير."
                return CRMOperatorResult(
                    reply=reply, reply_audio=reply,
                    conversation_state=ConversationState.IDLE,
                    operation=op,
                    current_context={}
                )

        elif ask:
            name = ask["name"]
            purpose = ask.get("purpose")
            due_dt = datetime.fromisoformat(ask["due_date"])
            has_time = bool(ask.get("has_time"))
            time_clarity = ask.get("time_clarity")
            pending_hour = ask.get("pending_hour")
            pending_minute = ask.get("pending_minute", 0)

            pick = re.search(r"#\s*(\d+)", q)
            if pick:
                forced_lead = get_scoped_lead_query(db.query(Lead), current_user).filter(
                    Lead.id == int(pick.group(1))
                ).first()
            elif re.search(r"زميل|موظف", q):
                force_kind = "user"
            elif "عميل" in q:
                force_kind = "lead"
            else:
                name = extract_person_name(q) or q.strip(" .،؟?") or name
        # ---- C. Fresh request --------------------------------------------------------
        else:
            name, rest = self._extract_task_target(q)
            if not name:
                name = extract_person_name(q)
            raw_purp = rest or self._extract_task_purpose(q) or ""
            if name and name in raw_purp:
                raw_purp = raw_purp.replace(name, "")
            purpose = clean_task_purpose(raw_purp)
            due_dt, date_has_time = parse_egyptian_date_time(q)

            # Check time specificity & clarity
            has_t, h, m, clarity = check_egyptian_time_details(q)
            actual_has_time = has_t or date_has_time
            time_clarity = clarity
            pending_hour = h
            pending_minute = m

        # A recipient was clearly written but we could not read it -> ask, don't guess
        if not name and not ask and re.search(r"(?:مهمة|مهمه)\s+(?:لـ|ل)\s*\S", q) and not re.search(
            r"(?:مهمة|مهمه)\s+(?:لـ|ل)\s*(?:نفسي|نفسى|ليا|لي)\b", q
        ):
            reply = "مين الشخص اللي عايز تسجل له المهمة؟ اكتب الاسم بالظبط."
            return CRMOperatorResult(
                reply=reply, reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=op,
                current_context={
                    "operation": op.value,
                    "state": ConversationState.COLLECTING_INFO.value,
                    "task_ask": {
                        "name": "",
                        "purpose": purpose,
                        "due_date": due_dt.isoformat(),
                        "has_time": actual_has_time,
                        "time_clarity": time_clarity,
                        "pending_hour": pending_hour,
                        "pending_minute": pending_minute
                    },
                },
            )

        # No name at all -> personal task for the current user
        if not name:
            personal_purpose = clean_task_purpose(purpose or re.sub(
                r"^(?:سجلي?|اعمل|ضيف|أضف|اضف)\s+(?:لي\s+)?(?:مهمة|مهمه|متابعة|متابعه)\s*", "", q
            ).strip() or "مهمة شخصية")
            plan = {
                "target_kind": "self",
                "lead_id": None,
                "lead_name": None,
                "assigned_user_id": current_user.id,
                "assignee_name": current_user.full_name,
                "purpose": personal_purpose,
                "due_date": due_dt.isoformat(),
                "has_time": actual_has_time,
                "time_clarity": time_clarity,
                "pending_hour": pending_hour,
                "pending_minute": pending_minute
            }
            return self._advance_task_or_ask_time(op, plan, current_user)

        # ---- Resolve the name: lead or colleague? ------------------------------------
        if forced_lead:
            res = {"leads": [forced_lead], "users": []}
        else:
            res = self._fuzzy_resolve_person(db, current_user, name)
            if force_kind == "user":
                res["leads"] = []
            elif force_kind == "lead":
                res["users"] = []

        # Nobody found: offer personal reminder / new lead
        if not res["leads"] and not res["users"]:
            reply = f"ملقتش حد باسم {name} لا في العملاء ولا في الفريق. تحب أسجل تذكير شخصي باسم {name}، ولا تضيفه كعميل جديد؟"
            draft = CreateReminderDraft(candidate_name=name)
            draft.due_date = due_dt.isoformat()
            draft.has_specific_time = actual_has_time
            draft.purpose = clean_task_purpose(f"متابعة مع {name}")
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.CREATE_REMINDER,
                current_context={
                    "operation": CRMOperationType.CREATE_REMINDER.value,
                    "state": ConversationState.COLLECTING_INFO.value,
                    "draft": draft.model_dump(),
                },
            )

        decision = plan_task_target(current_user, res)

        if decision["action"] == "ask":
            return CRMOperatorResult(
                reply=decision["message"],
                reply_audio=decision["message"],
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=op,
                current_context={
                    "operation": op.value,
                    "state": ConversationState.COLLECTING_INFO.value,
                    "task_ask": {
                        "name": name,
                        "purpose": purpose,
                        "due_date": due_dt.isoformat(),
                        "has_time": actual_has_time,
                        "time_clarity": time_clarity,
                        "pending_hour": pending_hour,
                        "pending_minute": pending_minute
                    },
                },
            )

        if decision["action"] == "refuse":
            return CRMOperatorResult(
                reply=decision["message"],
                reply_audio=decision["message"],
                conversation_state=ConversationState.IDLE,
                operation=op,
                current_context={},
            )

        # action == "create"
        if decision["lead_id"]:
            lead = res["leads"][0]
            plan = {
                "target_kind": "lead",
                "lead_id": lead.id,
                "lead_name": lead.full_name,
                "assigned_user_id": current_user.id,
                "assignee_name": current_user.full_name,
                "purpose": clean_task_purpose(f"متابعة مع {lead.full_name}" + (f": {purpose}" if purpose else "")),
                "due_date": due_dt.isoformat(),
                "has_time": actual_has_time,
                "time_clarity": time_clarity,
                "pending_hour": pending_hour,
                "pending_minute": pending_minute
            }
            return self._advance_task_or_ask_time(op, plan, current_user)
        else:
            target = next(u for u in res["users"] if u.id == decision["assigned_user_id"])
            if any(w in (purpose or "") for w in ["العميل", "عميل", "عقد العميل", "ملف العميل"]):
                reply = f"تمام، لقيت الموظف {target.full_name}. محتاج أعرف اسم العميل المرتبط بالمهمة علشان أتأكد إن العميل موجود في النظام وتابع ليه."
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=op,
                    current_context={
                        "operation": op.value,
                        "state": ConversationState.COLLECTING_INFO.value,
                        "task_ask": {
                            "step": "need_customer",
                            "assigned_user_id": target.id,
                            "assignee_name": target.full_name,
                            "purpose": clean_task_purpose(purpose),
                            "due_date": due_dt.isoformat(),
                            "has_time": actual_has_time,
                            "time_clarity": time_clarity,
                            "pending_hour": pending_hour,
                            "pending_minute": pending_minute
                        }
                    }
                )

            plan = {
                "target_kind": "colleague",
                "lead_id": None,
                "lead_name": None,
                "assigned_user_id": target.id,
                "assignee_name": target.full_name,
                "purpose": clean_task_purpose(purpose or f"مهمة من {current_user.full_name}"),
                "due_date": due_dt.isoformat(),
                "has_time": actual_has_time,
                "time_clarity": time_clarity,
                "pending_hour": pending_hour,
                "pending_minute": pending_minute
            }
            return self._advance_task_or_ask_time(op, plan, current_user)

    def _execute_task_plan(
        self,
        db: Session,
        current_user: User,
        plan: Dict[str, Any],
        ctx: Dict[str, Any],
        op: CRMOperationType,
    ) -> CRMOperatorResult:
        """Persists a confirmed task. Permissions are re-checked here, not trusted from the client context."""
        if ctx.get("followup_id"):
            reply = f"المهمة مسجلة بالفعل برقم #{ctx['followup_id']}."
            return CRMOperatorResult(
                reply=reply, reply_audio=reply,
                conversation_state=ConversationState.CONFIRMED, operation=op,
                execution_result={"success": True, "followup_id": ctx["followup_id"]},
            )

        try:
            due_dt = datetime.fromisoformat(plan["due_date"])

            lead = None
            if plan.get("lead_id"):
                lead = get_scoped_lead_query(db.query(Lead), current_user).filter(
                    Lead.id == plan["lead_id"]
                ).first()
                if not lead:
                    return CRMOperatorResult(
                        reply="مقدرتش أوصل للعميل ده أو مش ضمن صلاحياتك.",
                        conversation_state=ConversationState.ERROR, operation=op,
                    )

            assignee = current_user
            if plan["assigned_user_id"] != current_user.id:
                assignee = db.query(User).filter(
                    User.id == plan["assigned_user_id"],
                    User.company_id == current_user.company_id,
                    User.is_active == True,  # noqa: E712
                ).first()
                if not assignee:
                    return CRMOperatorResult(
                        reply="مقدرتش ألاقي الزميل ده في الشركة.",
                        conversation_state=ConversationState.ERROR, operation=op,
                    )
                check = plan_task_target(current_user, {"leads": [], "users": [assignee]})
                if check["action"] != "create":
                    return CRMOperatorResult(
                        reply=check["message"], reply_audio=check["message"],
                        conversation_state=ConversationState.IDLE, operation=op,
                        current_context={},
                    )

            new_f = FollowUp(
                company_id=current_user.company_id,
                lead_id=lead.id if lead else None,
                assigned_user_id=assignee.id,
                created_by_id=current_user.id,
                team_id=lead.team_id if lead else assignee.team_id,
                follow_up_type="Call" if lead else "Task",
                purpose=plan.get("purpose") or "مهمة",
                due_date=due_dt,
                priority=PriorityLevel.MEDIUM,
                status=FollowUpStatus.PENDING,
                notes=("تم الإنشاء عبر مساعد Nexora AI الذكي" if assignee.id == current_user.id
                       else f"مهمة من {current_user.full_name} عبر مساعد Nexora AI الذكي"),
            )
            db.add(new_f)
            if lead:
                lead.next_followup_date = due_dt
            db.commit()
            db.refresh(new_f)

            if lead and assignee.id != current_user.id:
                reply = f"تمام، اتسجلت المهمة برقم #{new_f.id} وتم تعيينها لـ {assignee.full_name} للعميل {lead.full_name}."
            elif lead:
                reply = f"تمام، اتسجلت المتابعة برقم #{new_f.id} للعميل {lead.full_name} بتاريخ {due_dt.strftime('%Y-%m-%d')}."
            elif assignee.id != current_user.id:
                reply = f"تمام، اتسجلت المهمة برقم #{new_f.id} وتم تعيينها لـ {assignee.full_name}."
            else:
                reply = f"تمام، اتسجلت المهمة برقم #{new_f.id}. هتلاقيها في مهامك."

            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.CONFIRMED,
                operation=op,
                current_context={
                    "operation": op.value,
                    "state": ConversationState.CONFIRMED.value,
                    "followup_id": new_f.id,
                },
                execution_result={
                    "success": True, "followup_id": new_f.id,
                    "lead_id": lead.id if lead else None,
                    "assigned_user_id": assignee.id,
                    "due_date": due_dt.isoformat(),
                },
                suggested_tools_called=["create_crm_followup" if lead else "create_task"],
                related_links=[{"title": lead.full_name, "url": f"/leads/{lead.id}"}] if lead else [],
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[CRMOperator] Failed to persist task: {e}", exc_info=True)
            return CRMOperatorResult(
                reply=f"حصل خطأ أثناء حفظ المهمة: {str(e)}.",
                conversation_state=ConversationState.ERROR, operation=op,
            )

    # -------------------------------------------------------------------------
    # LEAD CREATION & UPDATE IMPLEMENTATION
    # -------------------------------------------------------------------------

    def _handle_update_lead_turn(
        self,
        db: Session,
        current_user: User,
        query: str,
        ctx: Dict[str, Any]
    ) -> CRMOperatorResult:
        lead_id = ctx.get("lead_id")
        lead = db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.company_id == current_user.company_id
        ).first() if lead_id else None

        if not lead:
            return CRMOperatorResult(
                reply="لم أتمكن من العثور على العميل لتحديثه يا فندم في هذه الشركة.",
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.GENERAL_QUESTION,
                current_context={}
            )

        updated_fields = []
        b = extract_budget(query)
        if b is not None:
            lead.budget_max = b
            updated_fields.append(f"الميزانية ({b:,.0f} جنيه)")

        it = extract_intent_type(query)
        if it:
            lead.tags = it
            it_ar = "شراء" if it == "BUY" else ("إيجار" if it == "RENT" else "بيع")
            lead.notes = f"{lead.notes or ''} [طلب: {it_ar}]".strip()
            updated_fields.append(f"نوع الطلب ({it_ar})")

        loc = extract_location(query)
        if loc:
            lead.preferred_location = loc
            updated_fields.append(f"المنطقة ({loc})")

        if updated_fields:
            db.commit()
            db.refresh(lead)
            fields_str = " و".join(updated_fields)
            reply = f"تم تحديث بيانات العميل {lead.full_name} (#{lead.id}) بنجاح! تم حفظ {fields_str}."
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.CONFIRMED,
                operation=CRMOperationType.UPDATE_LEAD,
                current_context={"operation": CRMOperationType.UPDATE_LEAD.value, "state": ConversationState.CONFIRMED.value, "lead_id": lead.id},
                execution_result={"success": True, "lead_id": lead.id, "full_name": lead.full_name, "budget_max": lead.budget_max}
            )
        else:
            reply = f"تمام يا فندم، أنا جاهز لتحديث بيانات العميل {lead.full_name} (#{lead.id}). ممكن تقولي الميزانية أو المنطقة أو نوع الطلب المطلوب؟"
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.UPDATE_LEAD,
                current_context=ctx
            )

    def _handle_create_lead_turn(
        self,
        db: Session,
        current_user: User,
        query: str,
        ctx: Dict[str, Any]
    ) -> CRMOperatorResult:
        q = query.strip()
        q_lower = q.lower()

        draft_dict = ctx.get("draft", {})
        draft = CreateLeadDraft(**draft_dict) if draft_dict else CreateLeadDraft()

        # If context was already marked as READY_FOR_CONFIRMATION, treat omitted intent/budget as skipped
        if ctx.get("state") == ConversationState.READY_FOR_CONFIRMATION.value:
            if not draft.intent_type:
                draft.intent_type_skipped = True
            if draft.budget is None or draft.budget <= 0:
                draft.budget_skipped = True

        # Detect Clarification Questions
        if any(k in q_lower for k in ["مش فاهم", "مش فاهمة", "انا كنت عايز اسجل", "عايز اسجل العميل ده", "يعني ايه"]):
            reply = (
                f"أنا مكمل معاك نفس تسجيل العميل {draft.full_name or 'الجديد'}، "
                f"وكل بياناته مسجلة عندي ومعدلة بنجاح. محتاج بس تأكيدك النهائي عشان أضيفه في النظام فوراً."
            )
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.READY_FOR_CONFIRMATION,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.READY_FOR_CONFIRMATION.value, "draft": draft.model_dump()},
                missing_fields=[],
                confirmation_preview=self._format_lead_preview(draft)
            )

        # Detect Confirmation when Ready
        if self._is_explicit_confirmation(q) and draft.is_complete():
            return self._execute_create_lead(db, current_user, draft, ctx)

        # Explicit Skip
        is_skip = any(k in q_lower for k in ["تخطي", "مش محدد", "مش عارف", "بعدين", "تجاوز", "مش دلوقتي", "skip", "مش مهم", "تعدي", "ولا حاجة", "بدون"])
        if is_skip and draft.phone:
            if not draft.intent_type and not draft.intent_type_skipped:
                draft.intent_type_skipped = True
            elif draft.budget is None and not draft.budget_skipped:
                draft.budget_skipped = True
                draft.budget = None

        # 1. Phone extraction
        extracted_phone = extract_egyptian_phone(q)
        if extracted_phone:
            draft.phone = extracted_phone
        elif is_invalid_phone_attempt(q) and not draft.phone:
            return CRMOperatorResult(
                reply="رقم التليفون غير صالح وغير صحيح يا فندم. يرجى إدخال رقم محمول مصري صحيح مكون من 11 رقماً (مثل 01012345678).",
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.COLLECTING_INFO.value, "draft": draft.model_dump()},
                missing_fields=["phone"]
            )

        # 2. Name extraction
        extracted_name = extract_person_name(q)
        if extracted_name and (not draft.full_name or "اسمه" in q or "مش اسم" in q):
            draft.full_name = extracted_name

        # 3. Intent type
        extracted_intent = extract_intent_type(q)
        if extracted_intent:
            draft.intent_type = extracted_intent

        # 4. Budget
        extracted_budget = extract_budget(q)
        if extracted_budget:
            draft.budget = extracted_budget

        # 5. Location
        extracted_loc = extract_location(q)
        if extracted_loc:
            draft.preferred_location = extracted_loc

        # 6. Source
        extracted_src = extract_source(q)
        if extracted_src:
            draft.source = extracted_src

        # Missing fields check
        missing = draft.missing_required_fields()
        is_confirmation = self._is_explicit_confirmation(q)

        if missing and not is_confirmation:
            next_missing = missing[0]
            if next_missing == "phone":
                reply = f"تمام يا فندم، هسجل العميل {draft.full_name}. ممكن رقم تليفونه؟"
            elif next_missing == "full_name":
                reply = "تمام يا فندم، ممكن اسم العميل بالكامل؟"
            elif next_missing == "intent_type":
                reply = f"تمام يا فندم، رقم التليفون اتسجل. نوع الطلب إيه؟ (شراء ولا إيجار؟ أو قولي تخطي لو مش محدد)"
            elif next_missing == "budget":
                reply = f"إيه الميزانية المتوقعة للعميل؟ (تقدر تقول تخطي لو مش محددة)"
            else:
                reply = f"ممكن توضح {next_missing}؟"

            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.COLLECTING_INFO.value, "draft": draft.model_dump()},
                missing_fields=missing
            )

        if not draft.is_complete():
            next_missing = draft.missing_required_fields()[0]
            if next_missing == "phone":
                reply = f"عشان أقدر أسجل العميل {draft.full_name} في النظام، محتاج رقم تليفونه الأول."
            elif next_missing == "full_name":
                reply = "عشان أقدر أسجل العميل في النظام، محتاج اسم العميل بالكامل."
            elif next_missing == "intent_type":
                reply = f"محتاج أعرف نوع الطلب (شراء أو إيجار) أو قولي تخطي لو مش محدد."
            else:
                reply = f"محتاج أعرف الميزانية المتوقعة أو قولي تخطي عشان أعتمد التسجيل."

            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.COLLECTING_INFO.value, "draft": draft.model_dump()},
                missing_fields=draft.missing_required_fields()
            )

        # Ready for confirmation
        preview = self._format_lead_preview(draft)
        intent_ar = "شراء" if draft.intent_type == "BUY" else ("إيجار" if draft.intent_type == "RENT" else ("بيع" if draft.intent_type == "SELL" else "غير محدد"))
        budget_str = f"{draft.budget:,.0f} جنيه" if draft.budget is not None and draft.budget > 0 else "غير محددة"
        loc_str = draft.preferred_location or "غير محددة"

        reply = (
            f"جهزت بيانات العميل:\n"
            f"• الاسم: {draft.full_name}\n"
            f"• الهاتف: {draft.phone}\n"
            f"• نوع الطلب: {intent_ar}\n"
            f"• الميزانية: {budget_str}\n"
            f"• المنطقة: {loc_str}\n"
            f"تحب أعتمد وأسجل العميل في السي آر إم؟"
        )
        return CRMOperatorResult(
            reply=reply,
            reply_audio=f"جهزت بيانات العميل {draft.full_name}. نوع الطلب {intent_ar} والميزانية {budget_str}. تحب أعتمد وأسجل العميل؟",
            conversation_state=ConversationState.READY_FOR_CONFIRMATION,
            operation=CRMOperationType.CREATE_LEAD,
            current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.READY_FOR_CONFIRMATION.value, "draft": draft.model_dump()},
            missing_fields=[],
            confirmation_preview=preview
        )

    def _execute_create_lead(
        self,
        db: Session,
        current_user: User,
        draft: CreateLeadDraft,
        ctx: Dict[str, Any]
    ) -> CRMOperatorResult:
        if not has_permission(current_user, Permissions.LEADS_MANAGE):
            return CRMOperatorResult(
                reply="عذراً يا فندم، الحساب غير مصرح له وليس لديك صلاحية لإضافة أو تعديل العملاء (LEADS_MANAGE).",
                conversation_state=ConversationState.ERROR,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.ERROR.value, "draft": draft.model_dump()}
            )

        clean_phone = draft.phone.strip()
        existing_phone = db.query(Lead).filter(
            Lead.company_id == current_user.company_id,
            Lead.phone == clean_phone
        ).first()

        if existing_phone:
            reply = f"عذراً يا فندم، في عميل تاني مسجل بالفعل بنفس رقم التليفون ({clean_phone}). تحب نعدل رقم التليفون ولا نشوف بيانات العميل المسجل؟"
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.COLLECTING_INFO,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.COLLECTING_INFO.value, "draft": draft.model_dump()},
                missing_fields=["phone"]
            )

        try:
            assigned_agent = current_user.id if current_user.role == UserRole.SALES_AGENT else None
            intent_label = "شراء" if draft.intent_type == "BUY" else ("إيجار" if draft.intent_type == "RENT" else ("بيع" if draft.intent_type == "SELL" else None))
            notes_content = draft.notes or ""
            if intent_label:
                notes_content = f"{notes_content} [طلب: {intent_label}]".strip()

            budget_val = float(draft.budget) if draft.budget is not None and draft.budget > 0 else None
            budget_label = f"{budget_val:,.0f} جنيه" if budget_val is not None else "غير محددة"

            new_lead = Lead(
                company_id=current_user.company_id,
                full_name=draft.full_name.strip(),
                phone=clean_phone,
                email=draft.email.strip().lower() if draft.email else None,
                source=draft.source or "Meta Ads",
                preferred_location=draft.preferred_location or "",
                budget_max=budget_val,
                budget_min=None,
                pipeline_stage=PipelineStage.NEW,
                priority=PriorityLevel.MEDIUM,
                assigned_agent_id=assigned_agent,
                team_id=current_user.team_id,
                notes=notes_content,
                tags=draft.intent_type or ""
            )

            score, factors, prio = calculate_lead_score(new_lead)
            new_lead.score = score
            new_lead.score_factors = factors
            new_lead.priority = prio

            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)

            if new_lead.assigned_agent_id:
                assign_hist = LeadAssignmentHistory(
                    company_id=current_user.company_id,
                    lead_id=new_lead.id,
                    previous_agent_id=None,
                    new_agent_id=new_lead.assigned_agent_id,
                    changed_by_id=current_user.id,
                    reason="Conversational AI Assistant Lead Creation"
                )
                db.add(assign_hist)
                db.commit()

            log_audit_event(
                db=db,
                company_id=current_user.company_id,
                action="AI_CREATE_LEAD",
                entity_type="Lead",
                entity_id=new_lead.id,
                actor_id=current_user.id,
                after_state={"full_name": new_lead.full_name, "phone": new_lead.phone, "budget": new_lead.budget_max}
            )

            type_summary = f"نوع الطلب ({intent_label})" if intent_label else "نوع الطلب (غير محدد)"
            reply = f"تم تسجيل العميل {new_lead.full_name} بنجاح في النظام برقم #{new_lead.id}! تم حفظ الهاتف ({new_lead.phone}) و{type_summary} والميزانية ({budget_label})."

            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.CONFIRMED,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.CONFIRMED.value, "lead_id": new_lead.id},
                execution_result={
                    "success": True,
                    "lead_id": new_lead.id,
                    "full_name": new_lead.full_name,
                    "phone": new_lead.phone,
                    "pipeline_stage": new_lead.pipeline_stage.value,
                    "score": new_lead.score
                },
                suggested_tools_called=["create_lead_in_db"],
                related_links=[{"title": new_lead.full_name, "url": f"/leads/{new_lead.id}"}]
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[CRMOperator] Failed to persist lead to DB: {e}", exc_info=True)
            reply = f"حدث خطأ أثناء حفظ العميل في قاعدة البيانات: {str(e)}. تم حفظ المسودة لتتمكن من إعادة المحاولة."
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.READY_FOR_CONFIRMATION,
                operation=CRMOperationType.CREATE_LEAD,
                current_context={"operation": CRMOperationType.CREATE_LEAD.value, "state": ConversationState.READY_FOR_CONFIRMATION.value, "draft": draft.model_dump()}
            )

    def _format_lead_preview(self, draft: CreateLeadDraft) -> Dict[str, Any]:
        return {
            "full_name": draft.full_name,
            "phone": draft.phone,
            "source": draft.source or "إعلان فيسبوك",
            "intent_type": draft.intent_type or "غير محدد",
            "budget": draft.budget,
            "preferred_location": draft.preferred_location or "غير محددة",
        }

    # -------------------------------------------------------------------------
    # DAILY AGENDA, OVERDUE & TASK SUMMARIZATION
    # -------------------------------------------------------------------------

    def _handle_daily_agenda(
        self,
        db: Session,
        current_user: User,
        query: str = "",
        target_date: Optional[date] = None,
        scope: Optional[set] = None,
    ) -> CRMOperatorResult:
        """Verified appointments + follow-ups for the requested day (default today), Cairo time."""
        ref = get_current_cairo_time().replace(tzinfo=None)
        target = ref.date()
        if target_date:
            target = target_date
        elif query and has_date_words(query):
            target = parse_egyptian_date_time(query, ref)[0].date()
        want_app = not scope or "appointments" in scope
        want_fu = not scope or "followups" in scope
        is_today = target == ref.date()
        start_day = datetime.combine(target, time.min)
        end_day = datetime.combine(target, time.max)
        when = fmt_date(target.isoformat(), ref.date())

        f_query = db.query(FollowUp).filter(
            FollowUp.company_id == current_user.company_id,
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.OVERDUE, FollowUpStatus.DUE_TODAY])
        )
        if current_user.role == UserRole.SALES_AGENT:
            f_query = f_query.filter(FollowUp.assigned_user_id == current_user.id)
        followups = f_query.all()

        day_followups = sorted(
            [f for f in followups if start_day <= f.due_date <= end_day], key=lambda f: f.due_date
        )
        overdue = [f for f in followups if f.due_date < start_day] if is_today else []

        app_query = db.query(Appointment).filter(
            Appointment.company_id == current_user.company_id,
            Appointment.start_time >= start_day,
            Appointment.start_time <= end_day,
            Appointment.status == AppointmentStatus.SCHEDULED
        )
        if current_user.role == UserRole.SALES_AGENT:
            app_query = app_query.filter(Appointment.user_id == current_user.id)
        appointments = sorted(
            [a for a in app_query.all() if start_day <= a.start_time <= end_day],
            key=lambda a: a.start_time,
        )

        if not want_app:
            appointments = []
        if not want_fu:
            day_followups, overdue = [], []

        if not (appointments or day_followups or overdue):
            what = "مواعيد" if not want_fu else ("متابعات" if not want_app else "مواعيد ولا متابعات")
            reply = f"مفيش عندك {what} مجدولة {when} يا فندم."
            return CRMOperatorResult(
                reply=reply, reply_audio=reply,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.DAILY_AGENDA,
                suggested_tools_called=["get_daily_agenda"],
            )

        lines = [f"جدولك {when}:"]
        if appointments:
            lines.append(f"المواعيد ({len(appointments)}):")
            for a in appointments:
                loc = f" - {a.location}" if getattr(a, "location", "") else ""
                lines.append(f"- {fmt_time(a.start_time.strftime('%H:%M'))}: {a.title}{loc}")
        if day_followups:
            lines.append(f"المتابعات ({len(day_followups)}):")
            for f in day_followups[:8]:
                lead_name = f.lead.full_name if f.lead else "تذكير شخصي"
                lines.append(f"- {lead_name}: {f.purpose}")
        if overdue:
            lines.append(f"متابعات متأخرة ({len(overdue)}):")
            for o in overdue[:3]:
                lead_name = o.lead.full_name if o.lead else "تذكير شخصي"
                lines.append(f"- {lead_name}: {o.purpose}")

        parts = []
        if appointments:
            parts.append(f"{len(appointments)} مواعيد")
        if day_followups:
            parts.append(f"{len(day_followups)} متابعات")
        if overdue:
            parts.append(f"{len(overdue)} متابعات متأخرة")
        audio = f"عندك {when}: " + " و ".join(parts) + "."
        links = [{"title": f.lead.full_name, "url": f"/leads/{f.lead_id}"} for f in day_followups if f.lead_id and f.lead]

        return CRMOperatorResult(
            reply="\n".join(lines),
            reply_audio=audio,
            conversation_state=ConversationState.IDLE,
            operation=CRMOperationType.DAILY_AGENDA,
            suggested_tools_called=["list_due_followups", "get_daily_agenda"],
            related_links=links,
        )

    def _handle_overdue_followups(self, db: Session, current_user: User) -> CRMOperatorResult:
        """Retrieves overdue followups for current user."""
        now = datetime.utcnow()
        start_day = datetime.combine(now.date(), time.min)

        f_query = db.query(FollowUp).filter(
            FollowUp.company_id == current_user.company_id,
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.OVERDUE, FollowUpStatus.DUE_TODAY]),
            FollowUp.due_date < start_day
        )
        if current_user.role == UserRole.SALES_AGENT:
            f_query = f_query.filter(FollowUp.assigned_user_id == current_user.id)

        overdue = f_query.order_by(FollowUp.due_date.asc()).limit(5).all()

        if overdue:
            lines = [f"عندك {len(overdue)} متابعات متأخرة محتاجة اهتمامك:"]
            links = []
            for o in overdue:
                lead_name = o.lead.full_name if o.lead else "تذكير شخصي"
                due_str = o.due_date.strftime("%Y-%m-%d")
                lines.append(f"• **{lead_name}**: {o.purpose} (مستحقة منذ {due_str})")
                if o.lead_id:
                    links.append({"title": lead_name, "url": f"/leads/{o.lead_id}"})
            reply = "\n".join(lines)
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.SEARCH_OVERDUE_FOLLOWUPS,
                suggested_tools_called=["list_due_followups"],
                related_links=links
            )
        else:
            reply = "معندكش أي متابعات متأخرة حالياً يا فندم، جدولك ممتاز!"
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.SEARCH_OVERDUE_FOLLOWUPS,
                suggested_tools_called=["list_due_followups"]
            )

    def _handle_summarize_tasks(self, db: Session, current_user: User) -> CRMOperatorResult:
        """Summarizes today and tomorrow's upcoming tasks and followups."""
        now = datetime.utcnow()
        start_today = datetime.combine(now.date(), time.min)
        end_tomorrow = datetime.combine((now + timedelta(days=1)).date(), time.max)

        f_query = db.query(FollowUp).filter(
            FollowUp.company_id == current_user.company_id,
            FollowUp.assigned_user_id == current_user.id,
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.DUE_TODAY]),
            FollowUp.due_date >= start_today,
            FollowUp.due_date <= end_tomorrow
        ).all()

        reply = f"عندك {len(f_query)} مهام ومتابعات مجدولة لليوم وغداً."
        return CRMOperatorResult(
            reply=reply,
            reply_audio=reply,
            conversation_state=ConversationState.IDLE,
            operation=CRMOperationType.SUMMARIZE_TASKS,
            suggested_tools_called=["summarize_tasks"]
        )

    # -------------------------------------------------------------------------
    # PROPERTIES & LEADS SEARCH
    # -------------------------------------------------------------------------

    def _handle_search_properties(
        self,
        db: Session,
        current_user: User,
        query: str,
        current_context: Optional[Dict[str, Any]] = None,
        messages_history: Optional[List[Dict[str, str]]] = None
    ) -> CRMOperatorResult:
        """
        Conversational property search operator with multi-turn filter preservation.
        Understands colloquial Egyptian Arabic queries, comparison, media inquiries,
        and inventory breakdowns while maintaining filters across turns.
        """
        ctx = dict(current_context or {})
        q = query.strip()
        q_lower = q.lower()

        last_prop_ids = ctx.get("last_property_ids", [])
        active_filters = dict(ctx.get("property_filters") or {})

        # 1. Comparison Intent ("قارن بين الاتنين", "قارن بينهم")
        if any(k in q_lower for k in ["قارن", "مقارنة", "الفرق بينهم", "مين احسن", "مين أفضل"]):
            import re
            mentioned_ids = [int(n) for n in re.findall(r'\b\d+\b', q)]
            target_ids = []
            if len(mentioned_ids) >= 2:
                for mid in mentioned_ids:
                    p = db.query(Property).filter(
                        Property.company_id == current_user.company_id,
                        or_(Property.id == mid, Property.unit_number == str(mid))
                    ).first()
                    if p and p.id not in target_ids:
                        target_ids.append(p.id)
            if len(target_ids) < 2 and len(last_prop_ids) >= 2:
                target_ids = last_prop_ids[:2]

            if len(target_ids) >= 2:
                tool_res = ai_tool_registry.execute_tool(
                    "compare_properties", db, current_user, {"property_ids": target_ids}
                )
                return CRMOperatorResult(
                    reply=tool_res.message or "تمت المقارنة بين الوحدتين بنجاح.",
                    reply_audio=tool_res.message,
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.SEARCH_PROPERTIES,
                    suggested_tools_called=["compare_properties"],
                    current_context=ctx,
                    related_links=[{"title": "إدارة المناطق والمخزون العقاري", "url": "/properties-management"}]
                )
            else:
                reply = "تحب أقارن بين أي وحدتين؟ يرجى تحديد أرقام الوحدات أو استعراض الوحدات المتاحة أولاً."
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.SEARCH_PROPERTIES,
                    current_context=ctx
                )

        # 2. Media / Video Intent ("عندكم فيديو ليها؟", "وريني الفيديو", "صورها")
        if any(k in q_lower for k in ["فيديو", "فيديوهات", "فديو", "صور", "صوره", "صورها", "video", "photos"]):
            target_id = None
            import re
            m = re.search(r'\b\d+\b', q)
            if m:
                mid = int(m.group(0))
                p = db.query(Property).filter(
                    Property.company_id == current_user.company_id,
                    or_(Property.id == mid, Property.unit_number == str(mid))
                ).first()
                if p:
                    target_id = p.id
            if not target_id and last_prop_ids:
                target_id = last_prop_ids[0]

            if target_id:
                tool_res = ai_tool_registry.execute_tool(
                    "get_property_media", db, current_user, {"property_id": target_id}
                )
                return CRMOperatorResult(
                    reply=tool_res.message,
                    reply_audio=tool_res.message,
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.SEARCH_PROPERTIES,
                    suggested_tools_called=["get_property_media"],
                    current_context=ctx,
                    related_links=[{"title": "استعراض الوحدة بالمخزون", "url": "/properties-management"}]
                )

        # 3. Location Inventory Count Intent ("عندنا كام شقة في التجمع؟", "مخزون الشيخ زايد")
        if any(k in q_lower for k in ["كام شقة", "كام وحدة", "مخزون", "عدد الوحدات", "كم شقة", "كم وحدة"]):
            updated_filters = extract_property_query_filters(q, active_filters)
            loc = updated_filters.get("location")
            gov = updated_filters.get("governorate")
            prop_type = updated_filters.get("property_type")
            tool_res = ai_tool_registry.execute_tool(
                "get_location_inventory", db, current_user,
                {"location": loc, "governorate": gov, "property_type": prop_type}
            )
            return CRMOperatorResult(
                reply=tool_res.message,
                reply_audio=tool_res.message,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.SEARCH_PROPERTIES,
                suggested_tools_called=["get_location_inventory"],
                current_context=ctx,
                related_links=[{"title": "المناطق والمخزون العقاري", "url": "/properties-management"}]
            )

        # 4. Standard Property Search with Filter Accumulation
        updated_filters = extract_property_query_filters(q, active_filters)
        ctx["property_filters"] = updated_filters

        # Check if user mentioned an unregistered location
        req_location = updated_filters.get("location")
        if req_location:
            from backend.app.models.models import District, City, Governorate
            loc_reg = db.query(District).filter(
                (District.name_ar.ilike(f"%{req_location}%")) | (District.name_en.ilike(f"%{req_location}%"))
            ).first() or db.query(City).filter(
                (City.name_ar.ilike(f"%{req_location}%")) | (City.name_en.ilike(f"%{req_location}%"))
            ).first() or db.query(Governorate).filter(
                (Governorate.name_ar.ilike(f"%{req_location}%")) | (Governorate.name_en.ilike(f"%{req_location}%"))
            ).first()
            if not loc_reg:
                reply = f"المنطقة ({req_location}) غير مسجلة حالياً في قاعدة البيانات والمخزون العقاري."
                return CRMOperatorResult(
                    reply=reply,
                    reply_audio=reply,
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.SEARCH_PROPERTIES,
                    suggested_tools_called=["search_available_properties"],
                    current_context=ctx
                )

        tool_res = ai_tool_registry.execute_tool(
            "search_available_properties", db, current_user, updated_filters
        )

        matched_props = tool_res.data or []
        ctx["last_property_ids"] = [p["id"] for p in matched_props]

        links = []
        for p in matched_props:
            links.append({"title": f"الوحدة {p['unit_number']}", "url": "/properties-management"})

        reply = tool_res.message or ""

        # Friendly follow-up prompt if only governorate was given
        if updated_filters.get("governorate") and not updated_filters.get("location"):
            gov_name = updated_filters["governorate"]
            reply += f"\n\n💡 تحب أحددلك البحث في منطقة أو حي معين في {gov_name} (زي التجمع الخامس، الشيخ زايد، مدينة نصر، المعادي...)؟"

        return CRMOperatorResult(
            reply=reply,
            reply_audio=reply,
            conversation_state=ConversationState.IDLE,
            operation=CRMOperationType.SEARCH_PROPERTIES,
            suggested_tools_called=["search_available_properties", "search_properties"],
            current_context=ctx,
            related_links=links
        )

    def _handle_search_leads(self, db: Session, current_user: User, query: str) -> CRMOperatorResult:
        """Searches authorized leads for current user."""
        q_leads = get_scoped_lead_query(db.query(Lead), current_user)
        name = extract_person_name(query)
        loc = extract_location(query)

        if name:
            q_leads = q_leads.filter(Lead.full_name.ilike(f"%{name}%"))
        if loc:
            q_leads = q_leads.filter(Lead.preferred_location.ilike(f"%{loc}%"))

        leads = q_leads.limit(5).all()
        if leads:
            lines = [f"وجدت {len(leads)} عملاء مطابقين للبحث:"]
            links = []
            for l in leads:
                lines.append(f"• **{l.full_name}** | الهاتف: {l.phone} | المرحلة: {l.pipeline_stage.value} | النقاط: {l.score}")
                links.append({"title": l.full_name, "url": f"/leads/{l.id}"})
            reply = "\n".join(lines)
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.SEARCH_LEADS,
                suggested_tools_called=["search_leads"],
                related_links=links
            )
        else:
            reply = "لم يتم العثور على عملاء مطابقين لمعايير البحث في قائمة عملائك المصرح لك بالاطلاع عليها."
            return CRMOperatorResult(
                reply=reply,
                reply_audio=reply,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.SEARCH_LEADS,
                suggested_tools_called=["search_leads"]
            )

    def _handle_general_query(
        self,
        db: Session,
        current_user: User,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> CRMOperatorResult:
        """Handles general inquiries concisely without hallucinating CRM records."""
        try:
            if is_llm_configured():
                system_instruction = (
                    "أنت موظف عمليات CRM (CRM Operator) في نظام Nexora العقاري. "
                    "مهمتك مساعدة الموظف في إدارة علاقات العملاء بدقة وإيجاز. "
                    "أجب باختصار وبلهجة مصرية مهنية. لا تقدم نصائح مبيعات أو استراتيجيات غير مطلوبة. "
                    "لا تخترع بيانات عملاء أو أرقام غير موجودة. "
                    "ممنوع تقول إنك سجلت أو نفذت أو حفظت أي حاجة؛ التنفيذ بيتم بس من خلال النظام. "
                    "لو المستخدم طلب تسجيل موعد أو عميل أو متابعة ومفيش تنفيذ حصل، قوله إنك محتاج تفاصيل أكتر. "
                    "إنت في الرد ده ملكش وصول لبيانات النظام، فماتقولش 'هجيبلك القائمة' وماتسألش أسئلة توضيحية كتير. "
                    "لو سأل عن مواعيده أو متابعاته أو عملائه، وجّهه يكتب مثلاً: 'عندي ايه بكرة' أو 'المتابعات المتأخرة' أو 'دور على عميل اسمه ...'."
                )
                messages = [{"role": "system", "content": system_instruction}]
                for h in (history or [])[-6:]:
                    role = h.get("role")
                    content = (h.get("content") or "").strip()
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": content})
                if not (messages[-1]["role"] == "user" and messages[-1]["content"] == query.strip()):
                    messages.append({"role": "user", "content": query})
                llm_reply = generate_chat_completion(messages=messages)
                if llm_reply:
                    return CRMOperatorResult(
                        reply=llm_reply,
                        reply_audio=llm_reply,
                        conversation_state=ConversationState.IDLE,
                        operation=CRMOperationType.GENERAL_QUESTION,
                        suggested_tools_called=["qwen_llm_assistant"]
                    )
        except Exception:
            pass

        reply = "أهلاً بك! أنا مشغل عمليات Nexora CRM. يمكنك أن تطلب مني: إضافة عميل جديد، تسجيل تذكير أو متابعة، البحث عن عملاء، أو فحص الوحدات المتاحة."
        return CRMOperatorResult(
            reply=reply,
            reply_audio=reply,
            conversation_state=ConversationState.IDLE,
            operation=CRMOperationType.GENERAL_QUESTION
        )

    def _reconstruct_context_from_history(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Reconstructs draft context from previous user turns if context was omitted.
        Strictly distinguishes lead creation from reminders and follow-ups.
        """
        has_lead_intent = False
        has_reminder_intent = False
        has_followup_intent = False

        lead_draft = CreateLeadDraft()

        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                c_low = content.lower()

                if any(k in c_low for k in ["فكرني", "فكرنى", "ذكرني", "تذكير", "حطلي تذكير", "متنسنيش", "عايز تذكير"]):
                    has_reminder_intent = True

                if any(k in c_low for k in ["سجل متابعة", "سجل متابعه", "عايز أتابع مع", "عايز اتابع مع"]):
                    has_followup_intent = True

                if any(k in c_low for k in ["عايز أضيف عميل", "عايز اضيف عميل", "عميل جديد", "أضف عميل", "اضف عميل", "ضيف عميل", "سجل عميل جديد"]):
                    has_lead_intent = True

                if has_lead_intent:
                    name = extract_person_name(content)
                    if name:
                        lead_draft.full_name = name
                    phone = extract_egyptian_phone(content)
                    if phone:
                        lead_draft.phone = phone
                    intent = extract_intent_type(content)
                    if intent:
                        lead_draft.intent_type = intent
                    src = extract_source(content)
                    if src:
                        lead_draft.source = src
                    b = extract_budget(content)
                    if b:
                        lead_draft.budget = b
                    loc = extract_location(content)
                    if loc:
                        lead_draft.preferred_location = loc

        if has_reminder_intent and not has_lead_intent:
            return {
                "operation": CRMOperationType.CREATE_REMINDER.value,
                "state": ConversationState.COLLECTING_INFO.value
            }

        if has_followup_intent and not has_lead_intent:
            return {
                "operation": CRMOperationType.CREATE_FOLLOWUP.value,
                "state": ConversationState.COLLECTING_INFO.value
            }

        if has_lead_intent:
            state = ConversationState.READY_FOR_CONFIRMATION.value if lead_draft.is_complete() else ConversationState.COLLECTING_INFO.value
            return {
                "operation": CRMOperationType.CREATE_LEAD.value,
                "state": state,
                "draft": lead_draft.model_dump()
            }

        return {}


# Global singleton instance
_operator = ConversationalCRMOperator()


def get_crm_operator() -> ConversationalCRMOperator:
    return _operator