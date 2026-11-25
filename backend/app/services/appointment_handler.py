"""
appointment_handler.py
======================
يتحط في: backend/app/services/appointment_handler.py

بيضيف للـ ConversationalCRMOperator القدرة على تسجيل المواعيد فعلاً في جدول appointments،
بحوار متعدد الخطوات (عميل -> يوم -> ساعة -> نوع -> مكان) وتأكيد صريح قبل الحفظ.
خطوات التركيب (تعديلات صغيرة) في آخر الملف.
"""
import difflib
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.core.permissions import get_scoped_lead_query
from backend.app.models.models import Lead, User, Appointment, AppointmentStatus
from backend.app.schemas.crm_actions import (
    CRMOperationType, ConversationState, CRMOperatorResult
)
from backend.app.services.audit_service import log_audit_event
from backend.app.services.egyptian_nlp import (
    extract_person_name, parse_egyptian_date_time, score_lead_match,
    normalize_arabic_digits, normalize_arabic_text, get_current_cairo_time
)

logger = logging.getLogger(__name__)

APPT_OP = CRMOperationType.CREATE_APPOINTMENT.value

# type -> (Arabic label, duration in minutes, needs physical location)
APPT_TYPES = {
    "Phone Call": ("مكالمة", 30, False),
    "Video Call": ("مكالمة فيديو", 30, False),
    "Office Meeting": ("مقابلة", 60, False),
    "Property Visit": ("معاينة", 60, True),
}

# Only words that parse_egyptian_date_time actually understands
_DATE_WORDS = [
    "بعد بكرة", "بعد بكره", "بعد غد", "بكرة", "بكره", "غدا", "غداً",
    "النهاردة", "النهارده", "اليوم", "الاسبوع الجاي", "الأسبوع الجاي",
    "الاسبوع القادم", "الأسبوع القادم", "اول الشهر", "أول الشهر",
    "اخر الشهر", "آخر الشهر", "السبت", "الاحد", "الأحد", "الاثنين", "الإثنين",
    "الثلاثاء", "التلات", "الاربعاء", "الأربعاء", "الخميس", "الجمعة", "الجمعه",
    "tomorrow", "today",
]

_NAME_NOISE = {
    "الساعة", "الساعه", "بكرة", "بكره", "النهاردة", "النهارده", "اليوم",
    "مكالمة", "مكالمه", "في", "على", "عن", "عميل", "العميل", "مع", "ده", "دي",
}
_LOCATION_NOISE = {"عادي", "بس", "يعني", "كده", "طبعا", "طبعاً", "خلاص"}
_ORDINALS = {"الاول": 1, "الأول": 1, "اول": 1, "التاني": 2, "الثاني": 2, "التالت": 3, "الثالث": 3}
_AR_WEEKDAYS = ["الاتنين", "التلات", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


# ----------------------------------------------------------------------------
# Pure helpers (no DB) - easy to unit test
# ----------------------------------------------------------------------------

def has_date_words(text: str) -> bool:
    t = normalize_arabic_digits(text.lower())
    return any(w in t for w in _DATE_WORDS)


def detect_appointment_type(text: str) -> Optional[str]:
    t = normalize_arabic_text(text)
    if any(k in t for k in ["زووم", "zoom", "فيديو", "video", "تيمز", "teams"]):
        return "Video Call"
    if any(k in t for k in ["مكالمه", "مكامله", "مكلمه", "مكالما", "تليفون", "اتصال", "call", "phone"]):
        return "Phone Call"
    if any(k in t for k in ["معاينه", "زياره", "visit"]):
        return "Property Visit"
    if any(k in t for k in ["حضوري", "مكتب", "اجتماع", "office"]):
        return "Office Meeting"
    return None  # "مقابلة" لوحدها غامضة -> نسأل


_CLIENT_WORDS = ("العميل", "عميل", "للعميل", "بالعميل")


def _is_noise_word(w: str) -> bool:
    """Noise word, including typos of 'العميل' such as 'العميبل' / 'العمبل'."""
    if w in _NAME_NOISE:
        return True
    n = normalize_arabic_text(w)
    return any(difflib.SequenceMatcher(None, n, c).ratio() >= 0.8 for c in _CLIENT_WORDS)


def _clean_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    words = [w for w in name.split() if not _is_noise_word(w)]
    return " ".join(words) if words else None


def find_leads_in_text(candidates: List[Tuple[int, str]], text: str) -> List[int]:
    """
    Fallback lead lookup that scans the whole sentence instead of trusting the extracted name.
    candidates = [(lead_id, full_name)]. Returns ids of the best matches (full-name hit first,
    then 2-word windows, then single words).
    """
    norm_text = normalize_arabic_text(normalize_arabic_digits(text))
    words = [w.strip(" .،,؟?!") for w in norm_text.split()]
    words = [w for w in words if w]

    full = [lid for lid, name in candidates if name and normalize_arabic_text(name) in norm_text]
    if full:
        return full

    for size in (2, 1):
        hits: List[int] = []
        for i in range(len(words) - size + 1):
            window = " ".join(words[i:i + size])
            if _is_noise_word(window) or len(window) < 3:
                continue
            for lid, name in candidates:
                if lid not in hits and score_lead_match(name, window) >= 0.95:
                    hits.append(lid)
        if hits:
            return hits
    return []


def _clean_location(text: str) -> Optional[str]:
    words = [w for w in text.strip(" .،,؟?!").split() if w not in _LOCATION_NOISE]
    loc = " ".join(words).strip()
    return loc[:100] if loc else None


def extract_appointment_location(text: str, awaiting: Optional[str]) -> Optional[str]:
    m = re.search(r"(?:المكان|مكانها|مكانه)\s*:?\s*(?:في|فى|ف)?\s*([^\d،,.\n]+)", text)
    if m:
        return _clean_location(m.group(1))
    m = re.search(r"(?:^|\s)(?:في|فى|ف)\s+(الشركة|الشركه|المكتب|الموقع|الكومباوند|المشروع)(?:\s|$)", text)
    if m:
        return m.group(1)
    if awaiting == "location" and not re.search(r"\d", text):
        return _clean_location(text)
    return None


def _pick_candidate(text: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    t = normalize_arabic_digits(text)
    m = re.search(r"#?(\d+)", t)
    if m:
        n = int(m.group(1))
        for c in candidates:
            if c["id"] == n:
                return c
        if 1 <= n <= len(candidates):
            return candidates[n - 1]
    for word, idx in _ORDINALS.items():
        if word in t and idx <= len(candidates):
            return candidates[idx - 1]
    return None


def fmt_time(hhmm: str) -> str:
    h, m = [int(x) for x in hhmm.split(":")]
    period = "صباحاً" if h < 12 else "مساءً"
    return f"{(h % 12) or 12}:{m:02d} {period}"


def fmt_date(iso_date: str, today) -> str:
    d = datetime.fromisoformat(iso_date).date()
    diff = (d - today).days
    rel = {0: "النهاردة", 1: "بكرة", 2: "بعد بكرة"}.get(diff, "")
    base = f"{_AR_WEEKDAYS[d.weekday()]} {d.strftime('%d/%m')}"
    return f"{rel} {base}".strip()


def missing_appointment_fields(draft: Dict[str, Any]) -> List[str]:
    m = []
    if not draft.get("lead_id"):
        m.append("lead")
    if not draft.get("date"):
        m.append("date")
    if not draft.get("time"):
        m.append("time")
    if not draft.get("type"):
        m.append("type")
    elif APPT_TYPES[draft["type"]][2] and not draft.get("location"):
        m.append("location")
    return m


def merge_appointment_info(text: str, draft: Dict[str, Any], ref_now: datetime) -> Dict[str, Any]:
    """Merges whatever the user said in this turn into the draft. Never overwrites with guesses."""
    q = normalize_arabic_digits(text.strip())
    norm = normalize_arabic_text(q)
    awaiting = draft.get("awaiting")

    # 1) Lead: pick from earlier candidates, or extract a name
    picked = None
    if awaiting == "lead" and draft.get("candidates"):
        picked = _pick_candidate(q, draft["candidates"])
    if picked:
        draft["lead_id"], draft["lead_name"] = picked["id"], picked["name"]
        draft["candidates"] = []
        return draft  # a number like "2" must not be parsed as an hour

    name = _clean_name(extract_person_name(q))
    if not name and awaiting == "lead" and not re.search(r"\d", q) and len(q.split()) <= 4:
        name = _clean_name(q.strip(" .،,؟?!"))
    if name:
        draft["lead_query"] = name
        draft["lead_text"] = q
        for k in ("lead_id", "lead_name"):
            draft.pop(k, None)
        draft["candidates"] = []

    # 2) Date: only when the user actually said a date word (never silently default)
    if has_date_words(q):
        dt, _ = parse_egyptian_date_time(q, ref_now)
        draft["date"] = dt.date().isoformat()

    # 3) Time
    if re.search(r"\d|الساع|الصبح|صباح|ظهر|عصر|مساء|بالليل", norm):
        dt, has_t = parse_egyptian_date_time(q, ref_now)
        if has_t:
            draft["time"] = dt.strftime("%H:%M")

    # 4) Type + location
    t = detect_appointment_type(q)
    if t:
        draft["type"] = t
    elif not draft.get("type"):
        draft["type"] = "Office Meeting"
    loc = extract_appointment_location(q, awaiting)
    if loc:
        draft["location"] = loc
    return draft


def _snapshot(draft: Dict[str, Any]) -> str:
    keep = {k: draft.get(k) for k in ("lead_id", "lead_query", "date", "time", "type", "location")}
    return json.dumps(keep, sort_keys=True, ensure_ascii=False)


_QUESTIONS = {
    "lead": "المعاد ده مع أنهي عميل؟ قولي الاسم.",
    "date": "تحب المعاد يبقى أنهي يوم؟",
    "time": "الساعة كام بالظبط؟",
    "type": "هتبقى مكالمة، ولا مقابلة حضورية، ولا زووم؟",
    "location": "فين المكان؟",
}



# ----------------------------------------------------------------------------
# Stateless recovery: rebuild the draft from chat history when the client
# did not send current_context back (or it was lost).
# ----------------------------------------------------------------------------

_READY_HEADER = "هسجل المعاد ده:"
_APPT_TRIGGERS = [
    "حدد ميعاد", "احجز معاينة", "جدول ميعاد", "معاد معاينة", "موعد معاينة",
    "عندي مقابلة", "عندي ميعاد", "احجز ميعاد للعميل",
]
_APPT_NOUNS = ["معاد", "ميعاد", "موعد", "مقابلة", "مقابله", "اجتماع"]
_APPT_VERBS = ["اضيف", "أضيف", "ضيف", "سجل", "احجز", "حدد", "جدول", "اعمل", "عايز", "عندي"]
_APPT_EXCLUDED = [
    "ايه", "إيه", "امتى", "إمتى", "قابلت", "كلمت", "اتصلت", "عملت", "خلصت",
    "امبارح", "إمبارح", "أمس", "اتقابلنا", "سجلت",
]


def looks_like_appointment_request(text: str) -> bool:
    """Same rule as _classify_intent's appointment block (kept here so it can be reused)."""
    q = (text or "").lower().strip()
    if any(k in q for k in _APPT_TRIGGERS):
        return True
    if any(x in q for x in _APPT_EXCLUDED):
        return False
    if any(n in q for n in _APPT_NOUNS) and any(v in q for v in _APPT_VERBS):
        return True
    has_have = any(w in q for w in ["عندي", "عندى", "معايا", "عامل"])
    has_time = any(w in q for w in ["الساعة", "الساعه", "ساعة", "ساعه"]) or has_date_words(q) or bool(re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:الصبح|صباح|مساء|بالليل|عصر|ظهر)", q))
    has_party = any(w in q for w in ["عميل", "عمييل", "مع ", "للعميل"])
    has_verb = any(v in q for v in ["ضيف", "سجل", "احجز", "جدول", "رتب"])
    if has_have and has_time and (has_party or has_verb):
        return True
    return False


def _history_before_current(history: Optional[List[Dict[str, Any]]], q: str) -> List[Dict[str, Any]]:
    """History without the current user message (clients usually include it as the last item)."""
    h = list(history or [])
    if h and h[-1].get("role") == "user" and (h[-1].get("content") or "").strip() == q.strip():
        h = h[:-1]
    return h


def _assistant_awaiting(content: str) -> Optional[str]:
    for key, question in _QUESTIONS.items():
        if question in (content or ""):
            return key
    return None


def appointment_flow_pending(history: Optional[List[Dict[str, Any]]], q: str) -> bool:
    """True when the last assistant message was one of the appointment questions / the confirmation card."""
    h = _history_before_current(history, q)
    last_assistant = next((m for m in reversed(h) if m.get("role") == "assistant"), None)
    if not last_assistant:
        return False
    content = last_assistant.get("content") or ""
    if not (_assistant_awaiting(content) or content.startswith(_READY_HEADER)):
        return False
    return any(m.get("role") == "user" and looks_like_appointment_request(m.get("content", "")) for m in h)


def rebuild_appointment_draft(
    history: Optional[List[Dict[str, Any]]], q: str, ref_now: datetime
) -> Tuple[Dict[str, Any], bool]:
    """
    Replays the user turns of the current appointment flow.
    Returns (draft, was_ready_for_confirmation).
    """
    h = _history_before_current(history, q)
    start = None
    for i, m in enumerate(h):
        if m.get("role") == "user" and looks_like_appointment_request(m.get("content", "")):
            start = i
    if start is None:
        return {}, False

    draft: Dict[str, Any] = {}
    awaiting: Optional[str] = None
    was_ready = False
    for m in h[start:]:
        role, content = m.get("role"), m.get("content") or ""
        if role == "assistant":
            awaiting = _assistant_awaiting(content)
            was_ready = content.startswith(_READY_HEADER)
        elif role == "user":
            draft["awaiting"] = awaiting
            merge_appointment_info(content, draft, ref_now)
            was_ready = False
    draft["awaiting"] = awaiting
    return draft, was_ready

# ----------------------------------------------------------------------------
# Mixin
# ----------------------------------------------------------------------------

class AppointmentHandlerMixin:
    """Mixed into ConversationalCRMOperator. Relies on self._is_explicit_confirmation."""

    def _appt_result(self, reply, state, draft=None, missing=None, preview=None,
                     execution=None, ctx_extra=None, audio=None, links=None):
        context = {"operation": APPT_OP, "state": state.value}
        if draft is not None:
            context["appt_draft"] = draft
        if ctx_extra:
            context.update(ctx_extra)
        return CRMOperatorResult(
            reply=reply,
            reply_audio=audio or reply,
            conversation_state=state,
            operation=CRMOperationType.CREATE_APPOINTMENT,
            current_context=context,
            missing_fields=missing or [],
            confirmation_preview=preview,
            execution_result=execution,
            suggested_tools_called=["create_appointment"] if execution else [],
            related_links=links or [],
        )

    def _handle_create_appointment(
        self, db: Session, current_user: User, query: str, ctx: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> CRMOperatorResult:
        q = query.strip()
        ref_now = get_current_cairo_time()
        active = (
            ctx.get("operation") == APPT_OP
            and ctx.get("state") in (ConversationState.COLLECTING_INFO.value,
                                     ConversationState.READY_FOR_CONFIRMATION.value)
        )
        draft: Dict[str, Any] = dict(ctx.get("appt_draft") or {}) if active else {}
        was_ready = active and ctx.get("state") == ConversationState.READY_FOR_CONFIRMATION.value

        # Client did not send the draft back -> recover it from the chat history
        if not draft and history and appointment_flow_pending(history, q):
            draft, was_ready = rebuild_appointment_draft(history, q, ref_now)
            active = bool(draft)
            logger.info(f"[CRMOperator] Recovered appointment draft from history: {_snapshot(draft)}")

        # A) Explicit confirmation of a complete draft -> persist
        if was_ready and not missing_appointment_fields(draft) and self._is_explicit_confirmation(q):
            return self._execute_create_appointment(db, current_user, draft)

        # B) Merge what the user just said
        before = _snapshot(draft)
        merge_appointment_info(q, draft, ref_now)
        changed = _snapshot(draft) != before

        # C) Resolve the lead against authorized leads only
        if not draft.get("lead_id") and draft.get("lead_query"):
            err = self._resolve_appointment_lead(db, current_user, draft)
            if err:
                return err

        # D) Ask for the next missing field (one question per turn)
        missing = missing_appointment_fields(draft)
        if missing:
            nxt = missing[0]
            draft["awaiting"] = nxt
            ack = ""
            if not active and changed:
                bits = []
                if draft.get("lead_name"):
                    bits.append(f"مع {draft['lead_name']}")
                if draft.get("date"):
                    bits.append(fmt_date(draft["date"], ref_now.date()))
                if draft.get("time"):
                    bits.append(f"الساعة {fmt_time(draft['time'])}")
                if bits:
                    ack = "فهمت: " + "، ".join(bits) + ". "
            reply = ack + _QUESTIONS[nxt]
            return self._appt_result(reply, ConversationState.COLLECTING_INFO, draft, missing)

        # E) Complete: validate time is in the future
        start = datetime.fromisoformat(f"{draft['date']}T{draft['time']}:00")
        if start < ref_now.replace(tzinfo=None):
            draft["date"] = None
            draft["awaiting"] = "date"
            return self._appt_result(
                "الميعاد ده عدّى بالفعل. تحب نحدده يوم تاني؟",
                ConversationState.COLLECTING_INFO, draft, ["date"],
            )

        # F) Ready: if the user said something that changed nothing, ask what to change
        if was_ready and not changed:
            return self._appt_result(
                "تحب أعدّل إيه في المعاد؟ (اليوم، الساعة، النوع، المكان)، أو قول تأكيد وأنا أسجله.",
                ConversationState.READY_FOR_CONFIRMATION, draft,
            )

        draft["awaiting"] = None
        label = APPT_TYPES[draft["type"]][0]
        lines = [
            "هسجل المعاد ده:",
            f"- العميل: {draft['lead_name']} (#{draft['lead_id']})",
            f"- النوع: {label}",
            f"- الميعاد: {fmt_date(draft['date'], ref_now.date())} الساعة {fmt_time(draft['time'])}",
        ]
        if draft.get("location"):
            lines.append(f"- المكان: {draft['location']}")
        lines.append("أأكد التسجيل؟ (لو قصدك الساعة صباحاً قولي وأنا أعدّلها)")
        preview = {
            "action": "create_appointment",
            "lead_id": draft["lead_id"],
            "lead_name": draft["lead_name"],
            "appointment_type": draft["type"],
            "start_time": start.isoformat(),
            "location": draft.get("location", ""),
        }
        audio = (f"هسجل {label} مع {draft['lead_name']} {fmt_date(draft['date'], ref_now.date())} "
                 f"الساعة {fmt_time(draft['time'])}. أأكد؟")
        return self._appt_result(
            "\n".join(lines), ConversationState.READY_FOR_CONFIRMATION, draft,
            preview=preview, audio=audio,
        )

    def _resolve_appointment_lead(self, db, current_user, draft) -> Optional[CRMOperatorResult]:
        """Fills draft['lead_id'/'lead_name'] or returns a clarification result."""
        name = draft["lead_query"]
        leads = get_scoped_lead_query(db.query(Lead), current_user).all()
        matches = [l for l in leads if score_lead_match(l.full_name, name) >= 0.7]
        exact = [l for l in matches if normalize_arabic_text(l.full_name) == normalize_arabic_text(name)]
        if len(exact) == 1:
            matches = exact
        # A full lead name appearing in the sentence beats a partial extracted name ("Ahmed")
        sentence = normalize_arabic_text(draft.get("lead_text") or "")
        in_sentence = [l for l in leads if l.full_name and normalize_arabic_text(l.full_name) in sentence]
        if len(in_sentence) == 1:
            matches = in_sentence
        if not matches:
            ids = find_leads_in_text([(l.id, l.full_name) for l in leads], draft.get("lead_text") or name)
            matches = [l for l in leads if l.id in ids]
            if len(matches) > 1:
                full_hit = [l for l in matches if normalize_arabic_text(l.full_name)
                            in normalize_arabic_text(draft.get("lead_text") or "")]
                if len(full_hit) == 1:
                    matches = full_hit

        if len(matches) == 1:
            draft["lead_id"], draft["lead_name"] = matches[0].id, matches[0].full_name
            draft["candidates"] = []
            return None

        draft["awaiting"] = "lead"
        if len(matches) > 1:
            top = matches[:4]
            draft["candidates"] = [{"id": l.id, "name": l.full_name} for l in top]
            names = "، ".join(f"{i}) {l.full_name} (#{l.id})" for i, l in enumerate(top, 1))
            return self._appt_result(
                f"لقيت أكتر من عميل باسم {name}: {names}. تقصد أنهي واحد؟",
                ConversationState.COLLECTING_INFO, draft, ["lead"],
            )
        draft["candidates"] = []
        lead_sentence = normalize_arabic_text(draft.get("lead_text") or "")
        if any(w in lead_sentence for w in ["ضيف", "سجل", "جديد"]) or "عميل" in lead_sentence or "عمييل" in lead_sentence:
            from backend.app.models.models import PipelineStage
            new_lead = Lead(
                company_id=current_user.company_id,
                full_name=name,
                phone="",
                pipeline_stage=PipelineStage.NEW,
                assigned_agent_id=current_user.id,
                notes="تم إنشاؤه تلقائياً أثناء جدولة موعد عبر Nexora AI"
            )
            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)
            draft["lead_id"], draft["lead_name"] = new_lead.id, new_lead.full_name
            return None

        draft.pop("lead_query", None)
        return self._appt_result(
            f"ملقتش عميل باسم {name} في النظام. المعاد لازم يتربط بعميل مسجل، "
            f"فاكتبلي اسم تاني، أو قولي ضيفه كعميل جديد ونكمل.",
            ConversationState.COLLECTING_INFO, draft, ["lead"],
        )

    def _execute_create_appointment(self, db, current_user, draft) -> CRMOperatorResult:
        start = datetime.fromisoformat(f"{draft['date']}T{draft['time']}:00")
        label, minutes, _ = APPT_TYPES[draft["type"]]
        end = start + timedelta(minutes=minutes)
        try:
            lead = (
                get_scoped_lead_query(db.query(Lead), current_user)
                .filter(Lead.id == draft["lead_id"]).first()
            )
            if not lead:
                return self._appt_result(
                    "مقدرتش أوصل للعميل ده في النظام. اتأكد من الاسم وجرب تاني.",
                    ConversationState.ERROR,
                )

            conflict = db.query(Appointment).filter(
                Appointment.company_id == current_user.company_id,
                Appointment.user_id == current_user.id,
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.start_time < end,
                Appointment.end_time > start,
            ).first()
            if conflict and not (conflict.lead_id == lead.id and conflict.start_time == start):
                draft["time"] = None
                draft["awaiting"] = "time"
                return self._appt_result(
                    f"عندك '{conflict.title}' من {conflict.start_time.strftime('%I:%M %p')} "
                    f"لـ {conflict.end_time.strftime('%I:%M %p')} وده بيتعارض مع الميعاد. تحب نغير الساعة؟",
                    ConversationState.COLLECTING_INFO, draft, ["time"],
                )

            dup = db.query(Appointment).filter(
                Appointment.lead_id == lead.id,
                Appointment.user_id == current_user.id,
                Appointment.start_time == start,
                Appointment.status == AppointmentStatus.SCHEDULED,
            ).first()
            if dup:
                return self._appt_result(
                    f"المعاد ده مسجل قبل كده برقم #{dup.id}.",
                    ConversationState.CONFIRMED, None,
                    execution={"success": True, "appointment_id": dup.id, "duplicate": True},
                    ctx_extra={"appointment_id": dup.id},
                )

            appt = Appointment(
                company_id=current_user.company_id,
                lead_id=lead.id,
                user_id=current_user.id,
                title=f"{label} مع {lead.full_name}",
                appointment_type=draft["type"],
                start_time=start,
                end_time=end,
                location=draft.get("location", ""),
                notes="تم الإنشاء عبر مساعد Nexora AI الذكي",
                status=AppointmentStatus.SCHEDULED,
            )
            db.add(appt)
            db.commit()
            db.refresh(appt)

            try:
                log_audit_event(
                    db, current_user.company_id, "CREATE", "Appointment", appt.id,
                    actor_id=current_user.id,
                    after_state={"lead_id": lead.id, "start_time": start.isoformat(),
                                 "type": draft["type"]},
                )
            except Exception as audit_err:  # audit must never undo the booking
                logger.warning(f"[CRMOperator] Audit log failed for appointment {appt.id}: {audit_err}")

            reply = (f"تمام، اتسجل المعاد برقم #{appt.id}: {label} مع {lead.full_name} "
                     f"{fmt_date(draft['date'], get_current_cairo_time().date())} "
                     f"الساعة {fmt_time(draft['time'])}.")
            return self._appt_result(
                reply, ConversationState.CONFIRMED, None,
                execution={"success": True, "appointment_id": appt.id, "lead_id": lead.id,
                           "start_time": start.isoformat()},
                ctx_extra={"appointment_id": appt.id, "lead_id": lead.id},
                links=[{"title": lead.full_name, "url": f"/leads/{lead.id}"}],
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[CRMOperator] Failed to persist appointment: {e}", exc_info=True)
            return self._appt_result(
                "حصلت مشكلة وأنا بحفظ المعاد، ومتسجلش. جرب تاني بعد شوية.",
                ConversationState.ERROR, draft,
            )


# ----------------------------------------------------------------------------
# INTEGRATION (4 small edits)
# ----------------------------------------------------------------------------
#
# 1) crm_operator_service.py -- imports + class declaration
#
#       from backend.app.services.appointment_handler import AppointmentHandlerMixin
#       class ConversationalCRMOperator(AppointmentHandlerMixin):
#
# 2) crm_operator_service.py -- process_turn: route BEFORE `intent = self._classify_intent(...)`
#
#       if active_op == CRMOperationType.CREATE_APPOINTMENT.value and active_state in [
#           ConversationState.COLLECTING_INFO.value,
#           ConversationState.READY_FOR_CONFIRMATION.value,
#       ]:
#           return self._handle_create_appointment(db, current_user, q, ctx)
#
#    ...and right after the classification:
#
#       if intent == CRMOperationType.CREATE_APPOINTMENT:
#           return self._handle_create_appointment(db, current_user, q, ctx)
#
# 3) crm_operator_service.py -- _classify_intent: replace the appointment_triggers block
#
#       appointment_triggers = [
#           "حدد ميعاد", "احجز معاينة", "جدول ميعاد", "معاد معاينة", "موعد معاينة",
#           "عندي مقابلة", "عندي ميعاد", "احجز ميعاد للعميل",
#       ]
#       appt_nouns = ["معاد", "ميعاد", "موعد", "مقابلة", "مقابله", "اجتماع"]
#       appt_verbs = ["اضيف", "أضيف", "ضيف", "سجل", "احجز", "حدد", "جدول", "اعمل", "عايز", "عندي"]
#       is_question = any(w in q for w in ["ايه", "إيه", "امتى", "إمتى"])
#       if any(k in q for k in appointment_triggers) or (
#           not is_question
#           and any(n in q for n in appt_nouns)
#           and any(v in q for v in appt_verbs)
#       ):
#           return CRMOperationType.CREATE_APPOINTMENT
#
# 4) crm_operator_service.py -- _handle_general_query: stop the LLM from claiming actions.
#    Add to system_instruction:
#       " ممنوع تقول إنك سجلت أو نفذت أو حفظت أي حاجة؛ التنفيذ بيتم بس من خلال النظام."
#
# 5) voice_conversation_service.py -- process_voice_conversation: widen is_lead_op so
#    appointments/reminders/follow-ups reach the operator in the voice path too:
#
#       from backend.app.services.crm_operator_service import get_crm_operator
#       _op = get_crm_operator()
#       _intent = _op._classify_intent(last_user_msg, current_context.get("operation"),
#                                      current_context.get("state", "IDLE"))
#       is_operator_op = is_lead_op or _intent in (
#           CRMOperationType.CREATE_APPOINTMENT,
#           CRMOperationType.CREATE_REMINDER,
#           CRMOperationType.CREATE_FOLLOWUP,
#       ) or current_context.get("operation") == "CREATE_APPOINTMENT"
#
#    (ثم استخدم is_operator_op بدل is_lead_op في الـ if)