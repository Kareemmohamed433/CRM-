from datetime import datetime, time, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import (
    Lead, FollowUp, Appointment, Property, Activity, User, UserRole, Team,
    Company, Conversation, SalesAgentProfile, VoiceMetric,
    PipelineStage, FollowUpStatus, PropertyStatus, AppointmentStatus, ConversationStatus
)
from backend.app.services.voice_metrics_service import get_voice_analytics

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics")
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    now = datetime.utcnow()
    start_today = datetime.combine(now.date(), time.min)
    end_today = datetime.combine(now.date(), time.max)
    company_id = current_user.company_id

    # Common counts scoped to company
    leads_query = db.query(Lead).filter(Lead.company_id == company_id)
    followups_query = db.query(FollowUp).filter(FollowUp.company_id == company_id)
    appointments_query = db.query(Appointment).filter(Appointment.company_id == company_id)
    conversations_query = db.query(Conversation).filter(Conversation.company_id == company_id)

    is_agent = current_user.role == UserRole.SALES_AGENT
    is_team_leader = current_user.role == UserRole.TEAM_LEADER

    if is_agent:
        leads_query = leads_query.filter(Lead.assigned_agent_id == current_user.id)
        followups_query = followups_query.filter(FollowUp.assigned_user_id == current_user.id)
        appointments_query = appointments_query.filter(Appointment.user_id == current_user.id)
        conversations_query = conversations_query.filter(Conversation.assigned_agent_id == current_user.id)
    elif is_team_leader and current_user.team_id:
        leads_query = leads_query.filter(
            (Lead.team_id == current_user.team_id) | (Lead.assigned_agent_id == current_user.id)
        )
        followups_query = followups_query.filter(
            (FollowUp.team_id == current_user.team_id) | (FollowUp.assigned_user_id == current_user.id)
        )
        conversations_query = conversations_query.filter(
            (Conversation.team_id == current_user.team_id) | (Conversation.assigned_agent_id == current_user.id)
        )

    # 1. Metric Counts
    total_leads = leads_query.count()
    new_leads = leads_query.filter(Lead.pipeline_stage == PipelineStage.NEW).count()
    won_deals = leads_query.filter(Lead.pipeline_stage == PipelineStage.WON).count()
    lost_deals = leads_query.filter(Lead.pipeline_stage == PipelineStage.LOST).count()

    # Overdue and Due Today follow-ups
    pending_followups = followups_query.filter(
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.DUE_TODAY, FollowUpStatus.OVERDUE])
    ).all()

    overdue_count = sum(1 for f in pending_followups if f.due_date < start_today)
    due_today_count = sum(1 for f in pending_followups if start_today <= f.due_date <= end_today)

    # Today's visits
    today_visits = appointments_query.filter(
        Appointment.start_time >= start_today,
        Appointment.start_time <= end_today,
        Appointment.status == AppointmentStatus.SCHEDULED
    ).count()

    # Stalled leads (No next action)
    stalled_leads_count = leads_query.filter(
        Lead.next_followup_date == None,
        Lead.do_not_contact == False
    ).count()

    # Active & Unread Conversations
    total_conversations = conversations_query.count()
    unread_conversations = conversations_query.filter(Conversation.unread_count > 0).count()
    open_conversations = conversations_query.filter(Conversation.status == ConversationStatus.OPEN).count()

    # 2. Pipeline Funnel Breakdown
    stages = [
        PipelineStage.NEW, PipelineStage.CONTACTED, PipelineStage.QUALIFIED,
        PipelineStage.INTERESTED, PipelineStage.VISIT_SCHEDULED, PipelineStage.VISIT_COMPLETED,
        PipelineStage.NEGOTIATION, PipelineStage.RESERVATION, PipelineStage.WON, PipelineStage.LOST
    ]
    pipeline_funnel = []
    for st in stages:
        cnt = leads_query.filter(Lead.pipeline_stage == st).count()
        pipeline_funnel.append({"stage": st.value, "count": cnt})

    # 3. Leads by Source
    source_counts = (
        db.query(Lead.source, func.count(Lead.id))
        .filter(Lead.company_id == company_id)
        .group_by(Lead.source)
        .all()
    )
    leads_by_source = [{"source": src or "Direct", "count": cnt} for src, cnt in source_counts]

    # 4. Inventory Metrics (Company wide)
    total_units = db.query(Property).filter(Property.company_id == company_id).count()
    available_units = db.query(Property).filter(
        Property.company_id == company_id,
        Property.availability_status == PropertyStatus.AVAILABLE
    ).count()
    reserved_units = db.query(Property).filter(
        Property.company_id == company_id,
        Property.availability_status == PropertyStatus.RESERVED
    ).count()
    sold_units = db.query(Property).filter(
        Property.company_id == company_id,
        Property.availability_status == PropertyStatus.SOLD
    ).count()

    # 5. Conversion Rate calculation
    conv_rate = (won_deals / total_leads * 100) if total_leads > 0 else 0.0

    # 6. Leaderboard for Managers & Admins
    agent_leaderboard = []
    if current_user.role in [UserRole.SALES_MANAGER, UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN, UserRole.TEAM_LEADER]:
        agents_q = db.query(User).filter(
            User.company_id == company_id,
            User.role == UserRole.SALES_AGENT
        )
        if current_user.role == UserRole.TEAM_LEADER and current_user.team_id:
            agents_q = agents_q.filter(User.team_id == current_user.team_id)

        company_agents = agents_q.all()
        for ag in company_agents:
            ag_leads = db.query(Lead).filter(Lead.assigned_agent_id == ag.id).count()
            ag_won = db.query(Lead).filter(Lead.assigned_agent_id == ag.id, Lead.pipeline_stage == PipelineStage.WON).count()
            ag_visits = db.query(Activity).filter(Activity.user_id == ag.id, Activity.activity_type == "VISIT").count()
            ag_conv = round((ag_won / ag_leads * 100), 1) if ag_leads > 0 else 0.0
            agent_leaderboard.append({
                "agent_id": ag.id,
                "agent_name": ag.full_name,
                "team_name": ag.team.name if ag.team else "General",
                "leads_count": ag_leads,
                "won_deals": ag_won,
                "visits_count": ag_visits,
                "conversion_rate": ag_conv,
            })
        agent_leaderboard.sort(key=lambda x: x["won_deals"], reverse=True)

    # 7. Role-Specific Personal Workspace Data
    personal_workspace = {}
    if is_agent:
        prof = db.query(SalesAgentProfile).filter(SalesAgentProfile.user_id == current_user.id).first()
        target_sales = prof.monthly_target_sales if prof else 10000000.0
        target_visits = prof.target_visits_per_month if prof else 20
        actual_visits = db.query(Activity).filter(
            Activity.user_id == current_user.id,
            Activity.activity_type == "VISIT"
        ).count()
        personal_workspace = {
            "target_sales": target_sales,
            "target_visits": target_visits,
            "actual_visits": actual_visits,
            "visits_progress": min(100.0, round((actual_visits / target_visits * 100), 1)) if target_visits else 0.0,
            "assigned_active_leads": leads_query.filter(~Lead.pipeline_stage.in_([PipelineStage.WON, PipelineStage.LOST])).count(),
            "unread_messages": unread_conversations
        }

    # 8. Team Workspace Data for Team Leader
    team_workspace = {}
    if is_team_leader:
        team = db.query(Team).filter(Team.id == current_user.team_id).first() if current_user.team_id else None
        team_members_count = db.query(User).filter(User.team_id == current_user.team_id).count() if current_user.team_id else 1
        team_workspace = {
            "team_name": team.name if team else "My Team",
            "members_count": team_members_count,
            "leaderboard": agent_leaderboard
        }

    # 9. Smart Business Insights (Evidence-based alerts)
    insights = []
    if overdue_count > 0:
        insights.append({
            "type": "warning",
            "title": "متابعات متأخرة تتطلب تدخلاً",
            "message": f"يوجد {overdue_count} متابعة متأخرة تجاوزت موعدها المحدد ويجب التواصل مع العملاء اليوم.",
            "rule": "overdue_tasks > 0",
            "action_link": "/followups"
        })
    if stalled_leads_count > 0:
        insights.append({
            "type": "info",
            "title": "عملاء محتملون بدون إجراء قادم",
            "message": f"تم رصد {stalled_leads_count} عميل نشط بدون جدولة موعد أو متابعة قادمة.",
            "rule": "leads_without_next_action",
            "action_link": "/leads"
        })
    if unread_conversations > 0:
        insights.append({
            "type": "alert",
            "title": "محادثات عملاء غير مقروءة",
            "message": f"يوجد {unread_conversations} رسائل جديدة واردة عبر القنوات تحتاج رداً سريعاً للحفاظ على معدل التحويل.",
            "rule": "unread_conversations > 0",
            "action_link": "/ai-assistant"
        })

    # 10. Voice & AI Telemetry KPI
    voice_kpi = get_voice_analytics(db=db, company_id=company_id, days=7)

    # 11. Super Admin Platform Overview (if Super Admin)
    platform_overview = None
    if current_user.role == UserRole.SUPER_ADMIN:
        total_companies = db.query(Company).count()
        total_users = db.query(User).count()
        platform_overview = {
            "total_companies": total_companies,
            "total_platform_users": total_users,
            "system_health": "Optimal",
            "database_driver": "SQLite 3.x (Production PostgreSQL ready)",
        }

    return {
        "role": current_user.role.value,
        "user_name": current_user.full_name,
        "company_id": current_user.company_id,
        "company_name": current_user.company.name if current_user.company else "Nexora CRM",
        "workspace": current_user.role.value,
        "summary": {
            "total_leads": total_leads,
            "new_leads": new_leads,
            "due_today_followups": due_today_count,
            "overdue_followups": overdue_count,
            "today_visits": today_visits,
            "stalled_leads": stalled_leads_count,
            "won_deals": won_deals,
            "conversion_rate": round(conv_rate, 1),
            "total_conversations": total_conversations,
            "unread_conversations": unread_conversations,
            "open_conversations": open_conversations,
        },
        "pipeline_funnel": pipeline_funnel,
        "leads_by_source": leads_by_source,
        "inventory": {
            "total_units": total_units,
            "available_units": available_units,
            "reserved_units": reserved_units,
            "sold_units": sold_units,
        },
        "agent_leaderboard": agent_leaderboard,
        "personal_workspace": personal_workspace,
        "team_workspace": team_workspace,
        "insights": insights,
        "voice_kpi": voice_kpi,
        "platform_overview": platform_overview
    }
