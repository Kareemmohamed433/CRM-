from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from backend.app.models.models import ConversationChannel, ConversationStatus, MessageSenderType, MessageType


class ConversationMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    company_id: int
    sender_type: MessageSenderType
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    message_type: MessageType
    content: str
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    is_internal_note: bool = False
    is_read: bool = False
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    assigned_agent_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None

    channel: ConversationChannel
    status: ConversationStatus
    customer_name: str
    customer_phone: Optional[str] = None
    customer_identifier: Optional[str] = None

    unread_count: int = 0
    ai_enabled: bool = True
    human_takeover: bool = False
    last_message_text: str = ""
    last_message_time: datetime
    ai_summary: Optional[str] = ""
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationOut):
    messages: List[ConversationMessageOut] = []


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    message_type: MessageType = MessageType.TEXT
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    is_internal_note: bool = False


class TakeoverToggleRequest(BaseModel):
    human_takeover: bool


class AssignConversationRequest(BaseModel):
    agent_id: int


class WebhookMessagePayload(BaseModel):
    channel: ConversationChannel = ConversationChannel.WHATSAPP
    customer_phone: str
    customer_name: Optional[str] = "عميل جديد"
    customer_identifier: Optional[str] = None
    content: str
    message_type: MessageType = MessageType.TEXT
    audio_url: Optional[str] = None
    signature: Optional[str] = None

