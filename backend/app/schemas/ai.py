from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class VoiceTranscribeAndExtractRequest(BaseModel):
    transcript_text: Optional[str] = None  # Direct text or transcription from voice
    language: str = "ar"  # "ar" (Arabic / Egyptian Arabic) or "en"
    target_form: str = "activity"  # "activity" | "lead" | "followup" | "appointment"


class ExtractedField(BaseModel):
    field_name: str
    field_label: str
    value: Any
    confidence: float = 1.0


class VoiceExtractionResponse(BaseModel):
    raw_transcript: str
    detected_intent: str
    target_form: str
    extracted_fields: Dict[str, Any]
    matched_lead_id: Optional[int] = None
    matched_lead_name: Optional[str] = None
    matched_property_id: Optional[int] = None
    matched_property_unit: Optional[str] = None
    ambiguities: List[str] = []
    requires_confirmation: bool = True
    suggested_action: Optional[str] = None


class DailyBriefingResponse(BaseModel):
    greeting: str
    summary_text: str
    date_formatted: str
    metrics: Dict[str, int]
    due_today_followups: List[Dict[str, Any]]
    overdue_followups: List[Dict[str, Any]]
    today_visits: List[Dict[str, Any]]
    leads_no_next_action: List[Dict[str, Any]]
    recommendations: List[str]


class AIChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class AIChatRequest(BaseModel):
    messages: List[AIChatMessage]
    lead_id: Optional[int] = None
    current_context: Optional[Dict[str, Any]] = None


class AIActionDraft(BaseModel):
    action_type: str  # "create_followup" | "create_activity" | "create_lead" | "reassign_lead" | "update_lead_stage"
    description: str
    payload: Dict[str, Any]
    is_consequential: bool = True


class AIChatResponse(BaseModel):
    reply: str
    suggested_tools_called: List[str] = []
    action_draft: Optional[AIActionDraft] = None
    related_links: List[Dict[str, str]] = []
    current_context: Optional[Dict[str, Any]] = None
    conversation_state: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    operation: Optional[str] = None


class VoiceConversationMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class VoiceConversationRequest(BaseModel):
    messages: List[VoiceConversationMessage]
    current_context: Optional[Dict[str, Any]] = None
    lead_id: Optional[int] = None
    target_form: str = "activity"


class VoiceConversationResponse(BaseModel):
    reply_text: str
    reply_audio_text: str
    conversation_state: str  # "COLLECTING_INFO" | "READY_FOR_CONFIRMATION" | "CONFIRMED"
    extracted_context: Dict[str, Any]
    missing_fields: List[str] = []
    confirmation_preview: Optional[Dict[str, Any]] = None
    action_draft: Optional[AIActionDraft] = None
    matched_lead: Optional[Dict[str, Any]] = None
    matched_property: Optional[Dict[str, Any]] = None
    ambiguities: List[str] = []
    execution_result: Optional[Dict[str, Any]] = None


class VoiceConfirmAndSaveRequest(BaseModel):
    extracted_context: Dict[str, Any]
    explicit_confirmation: bool = True
    action_draft: Optional[AIActionDraft] = None


class VoiceConfirmAndSaveResponse(BaseModel):
    success: bool
    activity_id: int
    followup_id: Optional[int] = None
    lead_id: int
    lead_name: str
    message: str
    pipeline_stage: str
    score: int


class VoiceTranscriptionResponse(BaseModel):
    transcript: str
    language: str = "ar"
    confidence: float = 1.0
