import re
import calendar
from datetime import datetime, timedelta, time, timezone
from typing import Optional, Tuple, List, Dict, Any
from backend.app.core.config import settings

# Eastern Arabic numerals mapping
EASTERN_ARABIC_NUMERALS = {
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
}

# Common Egyptian & Arabic names transliteration mapping
AR_TO_EN_NAMES = {
    'احمد': 'ahmed', 'أحمد': 'ahmed', 'إحمد': 'ahmed',
    'محمد': 'mohamed', 'محمود': 'mahmoud', 'كريم': 'karim',
    'علي': 'ali', 'حسن': 'hassan', 'يوسف': 'youssef',
    'تامر': 'tamer', 'سامي': 'sami', 'خالد': 'khaled',
    'طارق': 'tarek', 'جمال': 'gamal', 'منى': 'mona',
    'سارة': 'sara', 'ساره': 'sara', 'مصطفى': 'mostafa',
    'مصطفي': 'mostafa', 'ياسر': 'yasser', 'حسين': 'hussein',
    'عمر': 'omar', 'عمرو': 'amr', 'ابراهيم': 'ibrahim',
    'إبراهيم': 'ibrahim', 'هاني': 'hany', 'اشرف': 'ashraf',
    'أيمن': 'ayman', 'ايمن': 'ayman', 'وليد': 'walid'
}

EN_TO_AR_NAMES = {v: k for k, v in AR_TO_EN_NAMES.items()}
EN_TO_AR_NAMES['mohamd'] = 'محمد'
EN_TO_AR_NAMES['mohammad'] = 'محمد'
EN_TO_AR_NAMES['muhammad'] = 'محمد'
EN_TO_AR_NAMES['ahmad'] = 'أحمد'
EN_TO_AR_NAMES['kareem'] = 'كريم'
EN_TO_AR_NAMES['youssef'] = 'يوسف'
EN_TO_AR_NAMES['joseph'] = 'يوسف'
EN_TO_AR_NAMES['sarah'] = 'سارة'


def get_current_cairo_time() -> datetime:
    """Returns the current datetime in Egypt local timezone with safe Windows fallback."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
    except Exception:
        tz = timezone(timedelta(hours=2))
    return datetime.now(tz)


def normalize_arabic_digits(text: str) -> str:
    """Converts Eastern Arabic numerals (٠-٩) to standard ASCII digits (0-9)."""
    if not text:
        return ""
    res = []
    for ch in text:
        res.append(EASTERN_ARABIC_NUMERALS.get(ch, ch))
    return "".join(res)


def normalize_arabic_text(text: str) -> str:
    """Normalizes Arabic letters for robust fuzzy matching."""
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r'[أإآ]', 'ا', s)
    s = re.sub(r'ة', 'ه', s)
    s = re.sub(r'ى', 'ي', s)
    s = re.sub(r'[\u064B-\u065F]', '', s)  # Remove tashkeel
    return s


def extract_person_name(text: str) -> Optional[str]:
    """
    Extracts person name (single or multi-word, Arabic or English) from phrases like:
    - 'اسمه ahmed mohamd'
    - 'عميل متابعة اسمه أحمد محمد'
    - 'فكرني بكرة أكلم أحمد محمد'
    - 'ضيف عميل جديد اسمه كريم'
    - 'سجل متابعة لأحمد بكرة'
    """
    t = text.strip()

    # Correction patterns: 'الاسم مش X قصدي Y'
    corr_match = re.search(
        r'(?:الاسم\s+مش|مش\s+اسم|اسمه\s+مش)\s+[^\s،.]+\s*(?:،|,|\s)+قصدي\s+([a-zA-Z\u0600-\u06FF]+(?:\s+[a-zA-Z\u0600-\u06FF]+)?)',
        t
    )
    if corr_match:
        return corr_match.group(1).strip()

    patterns = [
        r'(?:عميل\s+جديد\s+اسمه|عميل\s+اسمه|اسمه|اسم\s+العميل)\s+([a-zA-Z\u0600-\u06FF]+(?:\s+[a-zA-Z\u0600-\u06FF]+)?)',
        r'(?:ضيف\s+عميل\s+اسمه|أضف\s+عميل\s+اسمه|سجل\s+عميل\s+اسمه)\s+([a-zA-Z\u0600-\u06FF]+(?:\s+[a-zA-Z\u0600-\u06FF]+)?)',
        r'(?:أكلم|اكلم|أتصل بـ|اتصل بـ|أتصل ب|اتصل ب|أراجع مع|اراجع مع|أتابع مع|اتابع مع|متابعة مع|متابعه مع)\s+([a-zA-Z\u0600-\u06FF]+(?:\s+[a-zA-Z\u0600-\u06FF]+)?)',
        r'(?:متابعة لـ|متابعة ل|متابعه لـ|متابعه ل)\s*([a-zA-Z\u0600-\u06FF]+(?:\s+[a-zA-Z\u0600-\u06FF]+)?)',
        r'(?:الاسم\s*:?\s*)([a-zA-Z\u0600-\u06FF]+(?:\s+[a-zA-Z\u0600-\u06FF]+)?)',
    ]

    stopwords = {
        'جديد', 'عقار', 'شقة', 'فيلا', 'ايه', 'هو', 'عميل', 'حلو', 'بكرة', 'بكره',
        'النهاردة', 'النهارده', 'اليوم', 'كده', 'ده', 'دي', 'يا', 'فندم', 'معايا',
        'عندي', 'واحد', 'في', 'من', 'على', 'عن',
        'الساعة', 'الساعه', 'مكالمة', 'مكالمه', 'مقابلة', 'مقابله', 'معاد', 'ميعاد'
    }

    for p in patterns:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            raw_cand = m.group(1).strip()
            words = [w for w in raw_cand.split() if w.lower() not in stopwords]
            if words:
                return ' '.join(words)

    return None


def score_lead_match(lead_name: str, target_name: str) -> float:
    """
    Calculates match confidence between a CRM lead's full_name and a search query name.
    Supports Arabic, English, and cross-transliterations.
    Returns a score between 0.0 and 1.0.
    """
    if not lead_name or not target_name:
        return 0.0

    norm_lead = normalize_arabic_text(lead_name)
    norm_target = normalize_arabic_text(target_name)

    if norm_target == norm_lead or norm_target in norm_lead or norm_lead in norm_target:
        return 1.0

    lead_tokens = norm_lead.split()
    target_tokens = norm_target.split()

    matched = 0
    for t in target_tokens:
        t_en = AR_TO_EN_NAMES.get(t, t)
        t_ar = EN_TO_AR_NAMES.get(t, t)
        for lt in lead_tokens:
            lt_en = AR_TO_EN_NAMES.get(lt, lt)
            lt_ar = EN_TO_AR_NAMES.get(lt, lt)
            if t == lt or t_en == lt_en or t_ar == lt_ar or (len(t) >= 4 and t in lt) or (len(lt) >= 4 and lt in t):
                matched += 1
                break

    if matched == len(target_tokens) and len(target_tokens) > 0:
        return 0.95
    if matched > 0 and len(target_tokens) > 0:
        return 0.5 * (matched / len(target_tokens))

    return 0.0


def parse_egyptian_date_time(text: str, ref_now: Optional[datetime] = None) -> Tuple[datetime, bool]:
    """
    Parses relative Egyptian Arabic date and time expressions:
    - Dates: 'بكرة', 'النهاردة', 'بعد بكرة', 'الأسبوع الجاي', 'يوم الخميس', 'أول الشهر', 'آخر الشهر'
    - Times: 'الساعة 5', 'الساعة خمسة ونص', 'الساعة 10 الصبح', 'بعد الظهر', 'بالليل'
    Returns (datetime, has_specific_time).
    """
    if ref_now is None:
        ref_now = get_current_cairo_time()

    norm_t = normalize_arabic_digits(text.lower().strip())

    # 1. Date resolution
    target_date = None

    if any(k in norm_t for k in ['بعد بكرة', 'بعد بكره', 'بعد غد', 'بعد يومين']):
        target_date = ref_now.date() + timedelta(days=2)
    elif any(k in norm_t for k in ['بكرة', 'بكره', 'غدا', 'غداً', 'tomorrow']):
        target_date = ref_now.date() + timedelta(days=1)
    elif any(k in norm_t for k in ['النهاردة', 'النهارده', 'اليوم', 'today']):
        target_date = ref_now.date()
    elif any(k in norm_t for k in ['الاسبوع الجاي', 'الأسبوع الجاي', 'الاسبوع القادم', 'الأسبوع القادم', 'next week']):
        target_date = ref_now.date() + timedelta(days=7)
    elif any(k in norm_t for k in ['اول الشهر', 'أول الشهر']):
        year = ref_now.year + (1 if ref_now.month == 12 else 0)
        month = 1 if ref_now.month == 12 else ref_now.month + 1
        target_date = datetime(year, month, 1).date()
    elif any(k in norm_t for k in ['اخر الشهر', 'آخر الشهر']):
        _, last_day = calendar.monthrange(ref_now.year, ref_now.month)
        target_date = datetime(ref_now.year, ref_now.month, last_day).date()
    else:
        weekdays = {
            'السبت': 5, 'الاحد': 6, 'الأحد': 6, 'الاثنين': 0, 'الإثنين': 0,
            'الثلاثاء': 1, 'التلات': 1, 'الاربعاء': 2, 'الأربعاء': 2,
            'الخميس': 3, 'الجمعة': 4, 'الجمعه': 4
        }
        for day_name, day_idx in weekdays.items():
            if day_name in norm_t:
                days_ahead = (day_idx - ref_now.weekday() + 7) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = ref_now.date() + timedelta(days=days_ahead)
                break

    if not target_date:
        target_date = ref_now.date() + timedelta(days=1)

    # 2. Time resolution
    has_specific_time = False
    hour = 12
    minute = 0

    AR_NUM_HOURS = {
        'واحدة': 1, 'وحده': 1, 'اتنين': 2, 'اثنين': 2, 'تلاتة': 3, 'ثلاثة': 3,
        'اربعة': 4, 'أربعة': 4, 'خمسة': 5, 'ستة': 6, 'سبعة': 7, 'تمانية': 8, 'ثمانية': 8,
        'تسعة': 9, 'عشرة': 10, 'حداشر': 11, 'اتناشر': 12
    }

    time_match = re.search(
        r'(?:الساعة|الساعه)?\s*(\d{1,2}|واحدة|وحده|اتنين|اثنين|تلاتة|ثلاثة|اربعة|أربعة|خمسة|ستة|سبعة|تمانية|ثمانية|تسعة|عشرة|حداشر|اتناشر)(?::(\d{2}))?\s*(ونص|وربع|وتلت|وثلث)?\s*(الصبح|صباحا|صباحاً|بالليل|مساء|مساءً|العصر|الظهر|بعد الظهر)?',
        norm_t
    )

    found_hour = None
    found_minute = 0
    period = None

    if time_match:
        raw_h = time_match.group(1)
        raw_m = time_match.group(2)
        fraction = time_match.group(3)
        period = time_match.group(4)

        if raw_h and raw_h.isdigit():
            found_hour = int(raw_h)
        elif raw_h in AR_NUM_HOURS:
            found_hour = AR_NUM_HOURS[raw_h]

        if raw_m and raw_m.isdigit():
            found_minute = int(raw_m)
        elif fraction:
            if 'نص' in fraction:
                found_minute = 30
            elif 'ربع' in fraction:
                found_minute = 15
            elif 'تلت' in fraction or 'ثلث' in fraction:
                found_minute = 20

    if found_hour is not None and 1 <= found_hour <= 24:
        has_specific_time = True
        hour = found_hour
        minute = found_minute
        if period:
            if any(p in period for p in ['بالليل', 'مساء', 'مساءً', 'بعد الظهر', 'العصر']) and hour < 12:
                hour += 12
            elif any(p in period for p in ['الصبح', 'صباحا', 'صباحاً']) and hour == 12:
                hour = 0
        else:
            if 1 <= hour <= 7:
                hour += 12
    elif any(p in norm_t for p in ['الصبح', 'صباحا', 'صباحاً']):
        has_specific_time = True
        hour = 10
        minute = 0
    elif any(p in norm_t for p in ['بعد الظهر', 'الظهر']):
        has_specific_time = True
        hour = 14
        minute = 0
    elif any(p in norm_t for p in ['العصر']):
        has_specific_time = True
        hour = 16
        minute = 0
    elif any(p in norm_t for p in ['بالليل', 'مساء', 'مساءً']):
        has_specific_time = True
        hour = 19
        minute = 0

    result_dt = datetime.combine(target_date, time(hour, minute))
    return result_dt, has_specific_time