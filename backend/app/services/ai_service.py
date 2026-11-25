from datetime import datetime, date, time, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.models import (
    Lead, FollowUp, Appointment, Property, Activity, User, UserRole,
    FollowUpStatus, PropertyStatus, AppointmentStatus
)
from backend.app.schemas.ai import (
    DailyBriefingResponse, AIChatResponse, AIActionDraft
)
from backend.app.services.matching_service import find_alternative_properties
from backend.app.services.egyptian_nlp import get_current_cairo_time


def generate_daily_briefing(
    db: Session,
    current_user: User
) -> DailyBriefingResponse:
    """
    Constructs an authentic daily work briefing based purely on authorized database records.
    """
    now = get_current_cairo_time().replace(tzinfo=None)
    start_of_today = datetime.combine(now.date(), time.min)
    end_of_today = datetime.combine(now.date(), time.max)

    # Base query for follow-ups scoped to user
    f_query = db.query(FollowUp).filter(
        FollowUp.company_id == current_user.company_id,
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.DUE_TODAY, FollowUpStatus.OVERDUE])
    )
    if current_user.role == UserRole.SALES_AGENT:
        f_query = f_query.filter(FollowUp.assigned_user_id == current_user.id)
    elif current_user.role == UserRole.TEAM_LEADER and current_user.team_id:
        f_query = f_query.filter((FollowUp.team_id == current_user.team_id) | (FollowUp.assigned_user_id == current_user.id))

    all_pending_followups = f_query.all()

    due_today_list = []
    overdue_list = []

    for f in all_pending_followups:
        f_dict = {
            "id": f.id,
            "lead_id": f.lead_id,
            "lead_name": f.lead.full_name if f.lead else "Unknown Lead",
            "purpose": f.purpose,
            "due_date": f.due_date.isoformat(),
            "priority": f.priority.value,
        }
        if f.due_date < start_of_today:
            overdue_list.append(f_dict)
        elif start_of_today <= f.due_date <= end_of_today:
            due_today_list.append(f_dict)

    # Today's appointments/visits
    app_query = db.query(Appointment).filter(
        Appointment.company_id == current_user.company_id,
        Appointment.start_time >= start_of_today,
        Appointment.start_time <= end_of_today,
        Appointment.status == AppointmentStatus.SCHEDULED
    )
    if current_user.role == UserRole.SALES_AGENT:
        app_query = app_query.filter(Appointment.user_id == current_user.id)
    today_appointments = app_query.all()

    today_visits_list = [
        {
            "id": a.id,
            "lead_id": a.lead_id,
            "lead_name": a.lead.full_name if a.lead else "Unknown Lead",
            "title": a.title,
            "time": a.start_time.strftime("%I:%M %p"),
            "location": a.location or "Site Visit",
        }
        for a in today_appointments
    ]

    # Leads with no scheduled follow-up
    lead_query = db.query(Lead).filter(
        Lead.company_id == current_user.company_id,
        Lead.next_followup_date == None,
        Lead.do_not_contact == False
    )
    if current_user.role == UserRole.SALES_AGENT:
        lead_query = lead_query.filter(Lead.assigned_agent_id == current_user.id)
    elif current_user.role == UserRole.TEAM_LEADER and current_user.team_id:
        lead_query = lead_query.filter(Lead.team_id == current_user.team_id)

    stalled_leads = lead_query.limit(5).all()
    leads_no_next_action_list = [
        {
            "id": l.id,
            "full_name": l.full_name,
            "phone": l.phone,
            "pipeline_stage": l.pipeline_stage.value,
            "score": l.score,
        }
        for l in stalled_leads
    ]

    # Build Arabic summary text as requested in prompt:
    # "صباح الخير. عندك النهارده 5 متابعات، منهم متابعة واحدة متأخرة، ومعاينتين. فيه 3 عملاء مهتمين ولسه مفيش خطوة متابعة محددة ليهم."
    greeting = f"صباح الخير يا {current_user.full_name.split()[0]}"
    summary_parts = []
    
    total_followups = len(due_today_list) + len(overdue_list)
    summary_parts.append(f"عندك النهارده {total_followups} متابعات")
    if overdue_list:
        summary_parts.append(f"منهم {len(overdue_list)} متأخرة")
    if today_visits_list:
        summary_parts.append(f"و {len(today_visits_list)} مواعيد/معاينات")
    if leads_no_next_action_list:
        summary_parts.append(f"وفيه {len(leads_no_next_action_list)} عملاء محتاجين تحديد خطوة متابعة قادمة")

    summary_text = "، ".join(summary_parts) + "."

    recommendations = []
    if overdue_list:
        recommendations.append(f"ابدأ بمكالمة المتابعة المتأخرة للعميل {overdue_list[0]['lead_name']} لتجنب فقدان العميل.")
    if leads_no_next_action_list:
        recommendations.append(f"حدد موعد متابعة قادمة للعميل {leads_no_next_action_list[0]['full_name']} لتنشيط الاهتمام.")
    if not recommendations:
        recommendations.append("جدولك منظم اليوم! تفقد قائمة العقارات المتاحة للفرص الجديدة.")

    return DailyBriefingResponse(
        greeting=greeting,
        summary_text=summary_text,
        date_formatted=now.strftime("%A, %d %B %Y"),
        metrics={
            "due_today": len(due_today_list),
            "overdue": len(overdue_list),
            "today_visits": len(today_visits_list),
            "stalled_leads": len(leads_no_next_action_list),
        },
        due_today_followups=due_today_list,
        overdue_followups=overdue_list,
        today_visits=today_visits_list,
        leads_no_next_action=leads_no_next_action_list,
        recommendations=recommendations,
    )


def process_ai_chat_command(
    db: Session,
    current_user: User,
    user_query: str,
    lead_id: Optional[int] = None,
    current_context: Optional[Dict[str, Any]] = None,
    messages_history: Optional[List[Dict[str, str]]] = None,
) -> AIChatResponse:
    """
    Executes authorized CRM actions and manages multi-turn conversational operations
    via the Conversational CRM Operator engine.
    Guarantees reliable intent classification, draft preservation, field validation,
    and verified database persistence without unrequested advice or hallucinations.
    """
    from backend.app.services.crm_operator_service import get_crm_operator
    from backend.app.schemas.crm_actions import CRMOperationType

    operator = get_crm_operator()
    result = operator.process_turn(
        db=db,
        current_user=current_user,
        user_query=user_query,
        current_context=current_context,
        messages_history=messages_history
    )

    action_draft = None
    if result.confirmation_preview and result.operation == CRMOperationType.CREATE_LEAD:
        action_draft = AIActionDraft(
            action_type="create_lead",
            description=f"اعتماد وحفظ العميل {result.confirmation_preview.get('full_name')} في النظام",
            payload=result.confirmation_preview,
            is_consequential=True
        )
    elif result.confirmation_preview:
        action_draft = AIActionDraft(
            action_type="crm_action",
            description=result.reply.split("\n")[0] if result.reply else "تنفيذ إجراء CRM",
            payload=result.confirmation_preview,
            is_consequential=True
        )

    return AIChatResponse(
        reply=result.reply,
        suggested_tools_called=result.suggested_tools_called,
        action_draft=action_draft,
        related_links=result.related_links,
        current_context=result.current_context,
        conversation_state=result.conversation_state.value,
        execution_result=result.execution_result,
        operation=result.operation.value
    )