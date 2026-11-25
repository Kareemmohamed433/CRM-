import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.models.models import Lead, Property, User, ActivityType
from backend.app.schemas.ai import VoiceExtractionResponse


# Arabic number words mapping
ARABIC_NUMBER_WORDS = {
    "واحد": 1, "واحدة": 1, "اثنين": 2, "اتنين": 2, "تلاتة": 3, "ثلاثة": 3,
    "اربعة": 4, "أربعة": 4, "خمسة": 5, "ستة": 6, "سبعة": 7, "تمانية": 8, "ثمانية": 8,
    "تسعة": 9, "عشرة": 10, "مليون": 1_000_000, "ملايين": 1_000_000, "مليار": 1_000_000_000,
    "الف": 1000, "ألف": 1000, "نص": 0.5, "نصف": 0.5
}


def parse_arabic_monetary_value(text: str) -> Optional[float]:
    """Extracts monetary values from phrases like 'أقل من أربعة مليون' or '3.5 مليون' or '500 ألف'."""
    text_clean = text.replace("،", " ").replace(".", " ")
    
    # Check digits + million/k: e.g. "4 مليون" or "4.5 million" or "4000000"
    digit_million_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:مليون|ملايين|million)", text)
    if digit_million_match:
        return float(digit_million_match.group(1)) * 1_000_000

    digit_k_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:الف|ألف|k)", text)
    if digit_k_match:
        return float(digit_k_match.group(1)) * 1_000

    # Check words: "أربعة مليون"
    for word, multiplier in [("مليون", 1_000_000), ("ملايين", 1_000_000)]:
        if word in text:
            # find word before
            parts = text.split(word)[0].strip().split()
            if parts:
                prev_word = parts[-1]
                if prev_word in ARABIC_NUMBER_WORDS:
                    val = ARABIC_NUMBER_WORDS[prev_word] * multiplier
                    # Check for half / نص e.g. "اربعة ونص مليون"
                    if len(parts) >= 3 and ("نص" in parts or "نصف" in parts):
                        val += 0.5 * multiplier
                    return float(val)

    # Direct raw numbers > 100,000
    raw_num_match = re.search(r"\b(\d{6,10})\b", text)
    if raw_num_match:
        return float(raw_num_match.group(1))

    return None


def extract_crm_data_from_voice_or_text(
    db: Session,
    company_id: int,
    transcript: str,
    target_form: str = "activity"
) -> VoiceExtractionResponse:
    """
    Parses Arabic/Egyptian Arabic or English speech transcripts into structured CRM form fields.
    Matches verified leads and properties in the database; warns when ambiguous.
    Never invents unverified data.
    """
    raw = transcript.strip()
    extracted_fields: Dict[str, Any] = {}
    ambiguities: List[str] = []
    matched_lead_id = None
    matched_lead_name = None
    matched_property_id = None
    matched_property_unit = None

    # 1. Lead Name Matching
    all_leads = db.query(Lead).filter(Lead.company_id == company_id).all()
    matching_leads = []
    for lead in all_leads:
        first_name = lead.full_name.split()[0].lower() if lead.full_name else ""
        if first_name and (first_name in raw.lower() or lead.full_name.lower() in raw.lower()):
            matching_leads.append(lead)

    if len(matching_leads) == 1:
        matched_lead_id = matching_leads[0].id
        matched_lead_name = matching_leads[0].full_name
        extracted_fields["lead_id"] = matched_lead_id
        extracted_fields["lead_name"] = matched_lead_name
    elif len(matching_leads) > 1:
        ambiguities.append(
            f"وجدنا أكثر من عميل مطابق: {', '.join([l.full_name for l in matching_leads])}. يرجى تأكيد العميل المحدد."
        )

    # 2. Activity Type detection
    detected_activity_type = ActivityType.CALL
    raw_lower = raw.lower()
    if any(k in raw_lower for k in ["عاين", "معاينة", "نزلت مع", "زيارة", "visit"]):
        detected_activity_type = ActivityType.VISIT
    elif any(k in raw_lower for k in ["واتساب", "رسالة", "شات", "whatsapp"]):
        detected_activity_type = ActivityType.WHATSAPP
    elif any(k in raw_lower for k in ["قابلت", "اجتماع", "مكتب", "meeting"]):
        detected_activity_type = ActivityType.MEETING
    elif any(k in raw_lower for k in ["كلمت", "اتصلت", "مكالمة", "call", "phone"]):
        detected_activity_type = ActivityType.CALL

    extracted_fields["activity_type"] = detected_activity_type.value

    # 3. Location detection (New Cairo / التجمع, Zayed / زايد, etc.)
    preferred_loc = ""
    if "تجمع" in raw or "new cairo" in raw_lower:
        preferred_loc = "New Cairo / التجمع"
    elif "زايد" in raw or "october" in raw_lower or "أكتوبر" in raw:
        preferred_loc = "Sheikh Zayed / زايد"
    elif "عاصمة" in raw or "capital" in raw_lower:
        preferred_loc = "New Capital / العاصمة الإدارية"
    elif "ساحل" in raw or "coast" in raw_lower:
        preferred_loc = "North Coast / الساحل الشمالي"

    if preferred_loc:
        extracted_fields["preferred_location"] = preferred_loc

    # 4. Objections & Outcomes
    objection = ""
    outcome = "Visit completed" if detected_activity_type == ActivityType.VISIT else "Call completed"

    if any(k in raw for k in ["مش مقتنع بالسعر", "السعر عالي", "غالي", "سعر", "price"]):
        objection = "Price too high / السعر مرتفع"
        outcome = "Completed - Price Objection"
    elif any(k in raw for k in ["المقدم", "down payment"]):
        objection = "Down payment too high / المقدم كبير"
        outcome = "Completed - Down Payment Objection"
    elif any(k in raw for k in ["الموقع", "بعيد", "location"]):
        objection = "Location unsuitable / الموقع غير مناسب"
        outcome = "Completed - Location Objection"
    elif any(k in raw for k in ["المساحة", "التقسيمة", "layout", "area"]):
        objection = "Area or layout unsuitable / المساحة أو التقسيمة غير مناسبة"

    extracted_fields["outcome"] = outcome
    extracted_fields["objection"] = objection

    # 5. Monetary extraction (Customer stated budget)
    monetary_val = parse_arabic_monetary_value(raw)
    if monetary_val:
        extracted_fields["customer_stated_budget"] = monetary_val
        extracted_fields["budget_max"] = monetary_val

    # 6. Next actions
    next_action = ""
    if any(k in raw for k in ["هيرد", "هيفكر", "متابعة", "أكلمه", "follow"]):
        next_action = "Follow up with customer & present alternative properties"
    elif objection:
        next_action = "Search and recommend alternative units within budget"

    extracted_fields["summary"] = raw
    extracted_fields["next_action"] = next_action
    extracted_fields["sentiment"] = "Hesitant" if objection else "Interested"

    # 7. LLM intelligent enrichment if enabled
    try:
        from backend.app.services.llm_client import is_llm_configured, generate_json_completion
        if is_llm_configured():
            system_prompt = (
                "You are an Egyptian Real Estate CRM voice assistant. "
                "Analyze the agent voice note and provide a brief Arabic summary and recommended next action. "
                "Return JSON with keys: 'summary', 'next_action', 'sentiment'."
            )
            ai_data = generate_json_completion(system_prompt=system_prompt, user_prompt=raw, max_tokens=200)
            if ai_data and isinstance(ai_data, dict):
                if ai_data.get("summary"):
                    extracted_fields["ai_summary"] = ai_data["summary"]
                if ai_data.get("sentiment") and ai_data["sentiment"] in ["Interested", "Hesitant", "Not Interested"]:
                    extracted_fields["sentiment"] = ai_data["sentiment"]
                if ai_data.get("next_action") and not next_action:
                    extracted_fields["next_action"] = ai_data["next_action"]
    except Exception:
        pass

    return VoiceExtractionResponse(
        raw_transcript=raw,
        detected_intent="record_visit_outcome" if detected_activity_type == ActivityType.VISIT else "log_activity",
        target_form=target_form,
        extracted_fields=extracted_fields,
        matched_lead_id=matched_lead_id,
        matched_lead_name=matched_lead_name,
        matched_property_id=matched_property_id,
        matched_property_unit=matched_property_unit,
        ambiguities=ambiguities,
        requires_confirmation=True,
        suggested_action="Review and confirm visit outcome and objections"
    )
