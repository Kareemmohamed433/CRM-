import os
import json
import logging
import random
from typing import Dict, Any, Optional, List
import httpx

from backend.app.core.config import settings

logger = logging.getLogger("marketing.gemini")

# Predefined rotation of strategic topics focused strictly on NEXORA Smart Replies & AI automation
MARKETING_TOPICS = [
    {
        "topic": "الردود الذكية وتأخر الرد على العملاء",
        "pain_point": "تأخر الرد على استفسارات العملاء على الواتساب وفيسبوك يضيع أكثر من 40% من فرص البيع العقاري لصالح المنافسين.",
        "solution": "NEXORA Smart Replies ترد فوراً على مدار الساعة، وتحدد متطلبات العميل وترتب موعد المعاينة آلياً.",
    },
    {
        "topic": "إدارة محادثات الواتساب ومبيعات الـ 24 ساعة",
        "pain_point": "الرسائل خارج ساعات العمل الرسمية تظل معلقة حتى الصباح ويفقد العميل اهتمامه.",
        "solution": "مساعد المبيعات الذكي من NEXORA يتفاعل مع العميل في أي وقت بالذكاء الاصطناعي وباللهجة المناسبة دون توقف.",
    },
    {
        "topic": "توفير وقت أصحاب الشركات وفرق المبيعات",
        "pain_point": "مسؤولو المبيعات يستهلكون ساعات يومياً في الإجابة عن نفس الأسئلة المتكررة وتفريغ البيانات يدوياً.",
        "solution": "أتمتة ذكية تصفي العملاء المحتملين وتسجل بياناتهم فوراً في نظام الـ CRM ليفرغ الفريق لإغلاق الصفقات.",
    },
    {
        "topic": "صندوق محادثات موحد لكل قنوات التواصل",
        "pain_point": "تشتت الرسائل بين رسائل صفحة الفيسبوك، وإنستجرام، ورسائل الواتساب لكل بائع على حدة.",
        "solution": "منصة NEXORA تجمع كل المحادثات في شاشة واحدة منظمة مع تحكم كامل وإشراف إداري لحظي.",
    },
    {
        "topic": "تحسين تجربة العميل وزيادة معدل إغلاق الصفقات",
        "pain_point": "العملاء يبحثون عن إجابات دقيقة حول الأسعار، المساحات، وأنظمة السداد خلال أول دقيقة.",
        "solution": "NEXORA تقدم ترشيحات ذكية للوحدات المتاحة متوافقة تماماً مع ميزانية العميل مع إرسال تفاصيل العرض فوراً.",
    },
    {
        "topic": "الذكاء الاصطناعي للشركات العقارية ورواد الأعمال",
        "pain_point": "الاعتقاد بأن الذكاء الاصطناعي معقد أو مخصص فقط للشركات العالمية الضخمة.",
        "solution": "نظام NEXORA جاهز للعمل فوراً، سهل الاستخدام، ويرفع إنتاجية فريق المبيعات بنسبة تتجاوز 300%.",
    },
]


class GeminiContentService:
    """
    Modular content generator for daily marketing copy and image prompts using Google Gemini API.
    Includes smart fallback to local copywriting engine if Gemini credentials are not configured or quota is exceeded.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip()
        self.model = (model or getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")).strip()
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate_marketing_package(
        self,
        custom_topic: Optional[str] = None,
        recent_topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates:
        - topic: Selected topic name
        - headline: Punchy Arabic headline (max 8-10 words)
        - caption: Persuasive Arabic post copy (no emojis, professional, clear CTA, slogan)
        - image_prompt: English visual prompt for FLUX.1 Schnell
        """
        # Select topic avoiding recent repetition
        selected_seed = self._pick_topic(custom_topic, recent_topics)

        if self.is_configured():
            try:
                result = await self._call_gemini_api(selected_seed)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini API generation failed ({e}), falling back to local engine")

        # Fallback to local marketing engine
        return self._generate_local_package(selected_seed)

    def _pick_topic(self, custom_topic: Optional[str], recent_topics: Optional[List[str]]) -> Dict[str, str]:
        if custom_topic:
            return {
                "topic": custom_topic,
                "pain_point": f"التحديات التسويقية المتعلقة بـ {custom_topic}.",
                "solution": "حلول NEXORA الذكية لأتمتة الردود وإدارة المحادثات بكفاءة واحترافية.",
            }

        recent = set(recent_topics or [])
        available = [t for t in MARKETING_TOPICS if t["topic"] not in recent]
        if not available:
            available = MARKETING_TOPICS

        return random.choice(available)

    async def _call_gemini_api(self, seed: Dict[str, str]) -> Optional[Dict[str, Any]]:
        prompt = f"""
أنت مدير تسويق عقاري وكاتب إعلانات محترف لمنصة NEXORA المتخصصة في الردود الذكية (NEXORA Smart Replies) وأتمتة محادثات الواتساب ومبيعات الشركات.

الموضوع المطلوب لليوم: {seed['topic']}
نقطة الألم: {seed['pain_point']}
الحل المقترح: {seed['solution']}

المطلوب بدقة:
1. headline: عنوان إعلاني قوي باللغة العربية بلهجة بيزنس راقية (أقصى حد 7 إلى 9 كلمات). بدون أي إيموجي نهائياً.
2. caption: منشور تسويقي عربي احترافي ومقنع للشركات العقارية وأصحاب الأعمال.
   - ركز على أهمية الرد الفوري ومضاعفة المبيعات.
   - ممنوع استخدام الإيموجي نهائياً في المنشور.
   - اختم المنشور بدعوة واضحة لاتخاذ إجراء (Call to Action) لطلب تجربة النظام مجاناً.
   - أضف شعار البراند في النهاية:
     NEXORA — Smart Replies. Smarter Business.
3. image_prompt: وصف احترافي دقيق باللغة الإنجليزية لتوليد صورة خلفية تسويقية عبر نموذج FLUX.1 Schnell.
   - المواصفات البصرية الإلزامية للصورة:
     Deep navy background (#050817), subtle glowing neon cyan (#00D5E9) and electric purple (#7650F5) ambient rim lighting.
     Modern luxury tech aesthetic, floating 3D holographic smartphone and message cards showing smart business communication.
     Photorealistic studio render, cinematic volumetric lighting, 8k resolution, clean composition.
     STRICT RULE: Do NOT generate any text, words, letters, logos, or watermarks in the image.

أخرج الإجابة فقط بصيغة JSON صالحة بالشكل التالي:
{{
  "topic": "{seed['topic']}",
  "headline": "العنوان هنا",
  "caption": "نص المنشور الكامل هنا",
  "image_prompt": "English image prompt here"
}}
"""
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 1200,
                "responseMimeType": "application/json"
            }
        }

        url = f"{self.base_url}?key={self.api_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"Gemini API returned status {response.status_code}: {response.text}")
                return None

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not content_text:
                return None

            try:
                parsed = json.loads(content_text)
                return {
                    "topic": seed["topic"],
                    "headline": parsed.get("headline", "").replace("😊", "").replace("🚀", "").strip(),
                    "caption": parsed.get("caption", "").strip(),
                    "image_prompt": parsed.get("image_prompt", "").strip(),
                }
            except Exception as je:
                logger.error(f"Failed to parse Gemini JSON output: {je}. Raw: {content_text}")
                return None

    def _generate_local_package(self, seed: Dict[str, str]) -> Dict[str, Any]:
        """High-grade local copywriting engine with zero external dependencies."""
        headlines = [
            f"كل ثانية تأخير في الرد بتكلف شركتك عميل محتمل",
            f"خدمة عملاء ومبيعات 24 ساعة بدون انقطاع مع NEXORA",
            f"حول محادثات الواتساب لصفقات عقارية ناجحة بذكاء",
            f"وفر 70% من وقت فريق المبيعات وضاعف سرعة الاستجابة",
            f"إدارة ذكية لكل قنوات التواصل في شاشة واحدة متكاملة",
        ]

        headline = random.choice(headlines)
        caption = (
            f"هل تعلم أن أكثر من 40% من العملاء المحتملين في السوق العقاري يتجهون للمنافسين إذا لم يتلقوا رداً خلال الدقائق الخمس الأولى؟\n\n"
            f"{seed['pain_point']}\n\n"
            f"مع نظام NEXORA Smart Replies، لست بحاجة للقلق بعد اليوم بشأن الرسائل المتراكمة خارج أوقات العمل أو بطء الاستجابة.\n\n"
            f"{seed['solution']}\n\n"
            f"مميزات النظام لشركتك:\n"
            f"- استجابة فورية على مدار الساعة لرسائل الواتساب وقنوات التواصل.\n"
            f"- تصفية ذكية للميزانية والاهتمامات وتحديد مواعيد المعاينات تلقائياً.\n"
            f"- صندوق محادثات موحد مع ربط مباشر ببيانات الـ CRM.\n"
            f"- تقارير أداء فورية لتقييم سرعة الإغلاق ورضا العملاء.\n\n"
            f"اكتشف كيف يمكن لأتمتة المبيعات الذكية أن تنقل أداء فريقك لمستوى جديد.\n"
            f"تواصل معنا اليوم لحجز عرض توضيحي مباشر وتجربة النظام مجاناً.\n\n"
            f"NEXORA — Smart Replies. Smarter Business."
        )

        image_prompt = (
            f"Futuristic luxury 3D tech advertising scene, deep navy background #050817, "
            f"subtle glowing neon cyan #00D5E9 and electric purple #7650F5 ambient lighting. "
            f"Floating holographic glass panels showing sleek modern business message bubbles and AI automation nodes. "
            f"Premium dark SaaS visual aesthetics, cinematic volumetric lighting, 8k resolution, minimalist elegance. "
            f"No text, no words, no logos, clean high quality studio composition."
        )

        return {
            "topic": seed["topic"],
            "headline": headline,
            "caption": caption,
            "image_prompt": image_prompt,
        }

