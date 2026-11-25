from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import (
    get_current_user, get_scoped_conversation_query, verify_conversation_access,
    has_permission, Permissions
)
from backend.app.models.models import (
    User, UserRole, Conversation, ConversationMessage, Lead,
    ConversationChannel, ConversationStatus, MessageSenderType, MessageType,
    PipelineStage
)
from backend.app.schemas.conversation import (
    ConversationOut, ConversationDetailOut, ConversationMessageOut,
    SendMessageRequest, TakeoverToggleRequest, AssignConversationRequest,
    WebhookMessagePayload
)
from backend.app.services.llm_client import is_llm_configured, generate_chat_completion

router = APIRouter(prefix="/conversations", tags=["Omnichannel Conversations Inbox"])


@router.get("", response_model=List[ConversationOut])
def list_conversations(
    channel: Optional[ConversationChannel] = None,
    status_filter: Optional[ConversationStatus] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns customer conversations strictly scoped to authenticated user's authorization.
    - Sales Agent: Strictly assigned conversations
    - Team Leader: Team conversations
    - Sales Manager & Company Admin: All company conversations
    """
    query = db.query(Conversation)
    query = get_scoped_conversation_query(query, current_user)

    if channel:
        query = query.filter(Conversation.channel == channel)
    if status_filter:
        query = query.filter(Conversation.status == status_filter)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Conversation.customer_name.ilike(term)) |
            (Conversation.customer_phone.ilike(term)) |
            (Conversation.last_message_text.ilike(term))
        )

    conversations = (
        query.order_by(Conversation.last_message_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    out = []
    for c in conversations:
        out.append(ConversationOut(
            id=c.id,
            company_id=c.company_id,
            lead_id=c.lead_id,
            lead_name=c.lead.full_name if c.lead else None,
            assigned_agent_id=c.assigned_agent_id,
            assigned_agent_name=c.assigned_agent.full_name if c.assigned_agent else None,
            team_id=c.team_id,
            team_name=c.team.name if c.team else None,
            channel=c.channel,
            status=c.status,
            customer_name=c.customer_name,
            customer_phone=c.customer_phone,
            customer_identifier=c.customer_identifier,
            unread_count=c.unread_count,
            ai_enabled=c.ai_enabled,
            human_takeover=c.human_takeover,
            last_message_text=c.last_message_text,
            last_message_time=c.last_message_time,
            ai_summary=c.ai_summary or "",
            created_at=c.created_at,
            updated_at=c.updated_at
        ))
    return out


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves conversation and its full message history."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    verify_conversation_access(current_user, conv)

    # Mark as read for this user if they are the assigned agent
    if conv.assigned_agent_id == current_user.id and conv.unread_count > 0:
        conv.unread_count = 0
        db.commit()

    can_view_private_notes = has_permission(current_user, Permissions.CONVERSATIONS_VIEW_PRIVATE_NOTES)

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    messages_out = []
    for m in messages:
        if m.is_internal_note and not can_view_private_notes:
            continue
        messages_out.append(ConversationMessageOut(
            id=m.id,
            conversation_id=m.conversation_id,
            company_id=m.company_id,
            sender_type=m.sender_type,
            sender_id=m.sender_id,
            sender_name=m.sender.full_name if m.sender else None,
            message_type=m.message_type,
            content=m.content,
            audio_url=m.audio_url,
            audio_duration=m.audio_duration,
            is_internal_note=m.is_internal_note,
            is_read=m.is_read,
            created_at=m.created_at
        ))

    return ConversationDetailOut(
        id=conv.id,
        company_id=conv.company_id,
        lead_id=conv.lead_id,
        lead_name=conv.lead.full_name if conv.lead else None,
        assigned_agent_id=conv.assigned_agent_id,
        assigned_agent_name=conv.assigned_agent.full_name if conv.assigned_agent else None,
        team_id=conv.team_id,
        team_name=conv.team.name if conv.team else None,
        channel=conv.channel,
        status=conv.status,
        customer_name=conv.customer_name,
        customer_phone=conv.customer_phone,
        customer_identifier=conv.customer_identifier,
        unread_count=conv.unread_count,
        ai_enabled=conv.ai_enabled,
        human_takeover=conv.human_takeover,
        last_message_text=conv.last_message_text,
        last_message_time=conv.last_message_time,
        ai_summary=conv.ai_summary or "",
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages_out
    )


@router.post("/{conversation_id}/messages", response_model=ConversationMessageOut)
def send_conversation_message(
    conversation_id: int,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sends an agent response or private internal note."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    verify_conversation_access(current_user, conv)

    now = datetime.utcnow()
    sender_type = MessageSenderType.AGENT

    msg = ConversationMessage(
        conversation_id=conv.id,
        company_id=conv.company_id,
        sender_type=sender_type,
        sender_id=current_user.id,
        message_type=payload.message_type,
        content=payload.content.strip(),
        audio_url=payload.audio_url,
        audio_duration=payload.audio_duration,
        is_internal_note=payload.is_internal_note,
        is_read=True,
        created_at=now
    )
    db.add(msg)

    if not payload.is_internal_note:
        conv.last_message_text = payload.content.strip()
        conv.last_message_time = now
        conv.status = ConversationStatus.WAITING_CLIENT
        conv.human_takeover = True  # Agent took over manually

    db.commit()
    db.refresh(msg)

    return ConversationMessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        company_id=msg.company_id,
        sender_type=msg.sender_type,
        sender_id=msg.sender_id,
        sender_name=current_user.full_name,
        message_type=msg.message_type,
        content=msg.content,
        audio_url=msg.audio_url,
        audio_duration=msg.audio_duration,
        is_internal_note=msg.is_internal_note,
        is_read=msg.is_read,
        created_at=msg.created_at
    )


@router.post("/{conversation_id}/takeover")
def toggle_human_takeover(
    conversation_id: int,
    payload: TakeoverToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    verify_conversation_access(current_user, conv)

    conv.human_takeover = payload.human_takeover
    conv.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "conversation_id": conv.id,
        "human_takeover": conv.human_takeover,
        "message": "Human takeover enabled" if conv.human_takeover else "AI assistant resumed"
    }


@router.post("/{conversation_id}/assign")
def assign_conversation(
    conversation_id: int,
    payload: AssignConversationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    verify_conversation_access(current_user, conv)

    target_agent = db.query(User).filter(
        User.id == payload.agent_id,
        User.company_id == current_user.company_id
    ).first()
    if not target_agent:
        raise HTTPException(status_code=404, detail="Target agent not found in company")

    conv.assigned_agent_id = target_agent.id
    if target_agent.team_id:
        conv.team_id = target_agent.team_id
    conv.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "conversation_id": conv.id,
        "assigned_agent": target_agent.full_name
    }


@router.post("/{conversation_id}/summarize")
def generate_ai_summary(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates an automated executive summary of the conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    verify_conversation_access(current_user, conv)

    messages = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conv.id,
            ConversationMessage.is_internal_note == False
        )
        .order_by(ConversationMessage.created_at.asc())
        .limit(30)
        .all()
    )

    if not messages:
        return {"summary": "لا توجد رسائل كافية لتوليد ملخص."}

    text_history = "\n".join([f"{m.sender_type.value}: {m.content}" for m in messages])

    summary = ""
    if is_llm_configured():
        system_prompt = (
            "أنت خبير مبيعات ومحلل CRM عقاري مصري. لخص المحادثة التالية في جملتين إلى 3 جمل باللغة العربية: "
            "اذكر اهتمام العميل، الميزانية إن وجدت، أي اعتراض أو استفسار، والإجراء القادم المقترح."
        )
        reply = generate_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_history}
            ],
            temperature=0.2,
            max_tokens=200
        )
        if reply:
            summary = reply.strip()

    if not summary:
        # High quality heuristic summary
        summary = f"محادثة عبر {conv.channel.value} مع العميل {conv.customer_name}. آخر تواصل: {conv.last_message_text[:80]}... بانتظار المتابعة."

    conv.ai_summary = summary
    conv.updated_at = datetime.utcnow()
    db.commit()

    return {"summary": summary}


@router.post("/webhook")
def handle_incoming_channel_webhook(
    payload: WebhookMessagePayload,
    db: Session = Depends(get_db)
):
    """
    Webhook intake for WhatsApp, Meta (Facebook / Instagram), and SMS.
    Matches lead by phone, associates conversation, or creates new inbound lead.
    """
    # Find matching company lead by phone
    lead = db.query(Lead).filter(Lead.phone == payload.customer_phone).first()

    company_id = lead.company_id if lead else 1  # Default to primary tenant if new number
    now = datetime.utcnow()

    # Find or create conversation
    conv = db.query(Conversation).filter(
        Conversation.company_id == company_id,
        Conversation.customer_phone == payload.customer_phone,
        Conversation.channel == payload.channel
    ).first()

    if not conv:
        assigned_agent_id = lead.assigned_agent_id if lead else None
        team_id = lead.team_id if lead else None

        conv = Conversation(
            company_id=company_id,
            lead_id=lead.id if lead else None,
            assigned_agent_id=assigned_agent_id,
            team_id=team_id,
            channel=payload.channel,
            status=ConversationStatus.OPEN,
            customer_name=lead.full_name if lead else payload.customer_name or "عميل جديد",
            customer_phone=payload.customer_phone,
            customer_identifier=payload.customer_identifier,
            unread_count=1,
            ai_enabled=True,
            human_takeover=False,
            last_message_text=payload.content,
            last_message_time=now,
            created_at=now,
            updated_at=now
        )
        db.add(conv)
        db.flush()
    else:
        conv.last_message_text = payload.content
        conv.last_message_time = now
        conv.unread_count += 1
        conv.status = ConversationStatus.OPEN
        conv.updated_at = now

    # Insert message
    msg = ConversationMessage(
        conversation_id=conv.id,
        company_id=company_id,
        sender_type=MessageSenderType.CUSTOMER,
        message_type=payload.message_type,
        content=payload.content,
        audio_url=payload.audio_url,
        is_internal_note=False,
        is_read=False,
        created_at=now
    )
    db.add(msg)
    db.commit()

    return {
        "status": "success",
        "conversation_id": conv.id,
        "customer": conv.customer_name,
        "unread_count": conv.unread_count
    }

