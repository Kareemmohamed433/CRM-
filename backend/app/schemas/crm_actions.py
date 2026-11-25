import enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CRMOperationType(str, enum.Enum):
    CREATE_LEAD = "CREATE_LEAD"
    UPDATE_LEAD = "UPDATE_LEAD"
    SEARCH_LEADS = "SEARCH_LEADS"
    CREATE_TASK = "CREATE_TASK"
    CREATE_REMINDER = "CREATE_REMINDER"
    CREATE_FOLLOWUP = "CREATE_FOLLOWUP"
    CREATE_APPOINTMENT = "CREATE_APPOINTMENT"
    COMPLETE_TASK = "COMPLETE_TASK"
    RESCHEDULE_TASK = "RESCHEDULE_TASK"
    DELETE_TASK = "DELETE_TASK"
    DAILY_AGENDA = "DAILY_AGENDA"
    SEARCH_PROPERTIES = "SEARCH_PROPERTIES"
    SEARCH_OVERDUE_FOLLOWUPS = "SEARCH_OVERDUE_FOLLOWUPS"
    SUMMARIZE_TASKS = "SUMMARIZE_TASKS"
    SALES_SUMMARY = "SALES_SUMMARY"
    TEAM_PERFORMANCE = "TEAM_PERFORMANCE"
    CUSTOMER_PIPELINE = "CUSTOMER_PIPELINE"
    CUSTOMER_HISTORY = "CUSTOMER_HISTORY"
    PROPERTY_OFFER = "PROPERTY_OFFER"
    GENERAL_QUESTION = "GENERAL_QUESTION"


class ConversationState(str, enum.Enum):
    IDLE = "IDLE"
    COLLECTING_INFO = "COLLECTING_INFO"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class CreateLeadDraft(BaseModel):
    lead_id: Optional[int] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None
    intent_type: Optional[str] = None  # BUY, RENT, SELL
    intent_type_skipped: bool = False
    budget: Optional[float] = None
    budget_skipped: bool = False
    preferred_location: Optional[str] = None
    location_skipped: bool = False
    notes: Optional[str] = None

    def missing_required_fields(self) -> List[str]:
        missing = []
        if not self.full_name or not self.full_name.strip():
            missing.append("full_name")
        if not self.phone or not self.phone.strip():
            missing.append("phone")
        if not self.intent_type and not self.intent_type_skipped:
            missing.append("intent_type")
        if self.budget is None and not self.budget_skipped:
            missing.append("budget")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_required_fields()) == 0


class UpdateLeadDraft(BaseModel):
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    pipeline_stage: Optional[str] = None
    budget: Optional[float] = None
    phone: Optional[str] = None
    preferred_location: Optional[str] = None
    notes: Optional[str] = None


class CreateReminderDraft(BaseModel):
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    candidate_name: Optional[str] = None
    purpose: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    has_specific_time: bool = False
    reminder_type: str = "personal_reminder"  # "personal_reminder" | "crm_followup"
    priority: str = "MEDIUM"
    notes: Optional[str] = None
    ambiguous_leads: List[Dict[str, Any]] = Field(default_factory=list)


class CreateFollowUpDraft(BaseModel):
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    purpose: Optional[str] = None
    due_date: Optional[str] = None
    follow_up_type: str = "Call"


class CreateAppointmentDraft(BaseModel):
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    title: Optional[str] = None
    start_time: Optional[str] = None
    location: Optional[str] = None


class CRMOperatorResult(BaseModel):
    reply: str
    reply_audio: Optional[str] = None
    conversation_state: ConversationState = ConversationState.IDLE
    operation: CRMOperationType = CRMOperationType.GENERAL_QUESTION
    current_context: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    confirmation_preview: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    suggested_tools_called: List[str] = Field(default_factory=list)
    related_links: List[Dict[str, str]] = Field(default_factory=list)

