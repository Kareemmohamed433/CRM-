"""
Reporting & Sales Analytics Tools for NEXORA AI CRM Assistant.
Computes real database metrics: revenue, deal conversion, pipeline stages, and team activity.
Never fabricates data or uses fake mocks.
"""

from datetime import datetime, timedelta, date, time
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from backend.app.models.models import (
    Lead, PipelineStage, Activity, Appointment, FollowUp, User, UserRole, Team
)
from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult


@ai_tool_registry.register(
    name="get_sales_summary",
    description="استعراض ملخص المبيعات والإيرادات والصفقات الناجحة وحجم خط الأنابيب (Pipeline).",
    category="reporting",
    parameters_schema={
        "properties": {
            "period": {"type": "string", "enum": ["day", "week", "month", "all"], "description": "الفترة الزمنية"}
        }
    }
)
def get_sales_summary(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    period = params.get("period", "month")
    now = datetime.utcnow()

    # Time filter
    start_time = None
    if period == "day":
        start_time = datetime.combine(now.date(), time.min)
    elif period == "week":
        start_time = now - timedelta(days=7)
    elif period == "month":
        start_time = now - timedelta(days=30)

    # Base query for company
    leads_q = db.query(Lead).filter(Lead.company_id == user.company_id)
    if user.role == UserRole.SALES_AGENT:
        leads_q = leads_q.filter(Lead.assigned_agent_id == user.id)

    total_leads = leads_q.count()
    won_leads = leads_q.filter(Lead.pipeline_stage == PipelineStage.WON).all()
    won_count = len(won_leads)
    won_volume = sum((l.budget or 0) for l in won_leads)

    lost_count = leads_q.filter(Lead.pipeline_stage == PipelineStage.LOST).count()
    negotiation_count = leads_q.filter(Lead.pipeline_stage == PipelineStage.NEGOTIATION).count()
    reservation_count = leads_q.filter(Lead.pipeline_stage == PipelineStage.RESERVATION).count()
    active_pipeline = leads_q.filter(
        Lead.pipeline_stage.notin_([PipelineStage.WON, PipelineStage.LOST])
    ).count()

    summary_msg = (
        f"📊 ملخص المبيعات ({'الشهر الحالي' if period == 'month' else period}):\n"
        f"- إجمالي العملاء: {total_leads} عميل\n"
        f"- الصفقات الناجحة (Won): {won_count} صفقة بإجمالي قيمة تقديرية {won_volume:,.0f} ج.م\n"
        f"- صفقات في مرحلة الحجز/التفاوض: {reservation_count + negotiation_count} صفقة\n"
        f"- العملاء النشطين في المراحل البيعية: {active_pipeline} عميل\n"
        f"- صفقات خاسرة (Lost): {lost_count}"
    )

    return ToolResult(
        success=True,
        data={
            "period": period,
            "total_leads": total_leads,
            "won_count": won_count,
            "won_volume": won_volume,
            "active_pipeline": active_pipeline,
            "reservation_count": reservation_count,
            "negotiation_count": negotiation_count,
            "lost_count": lost_count
        },
        message=summary_msg
    )


@ai_tool_registry.register(
    name="get_customer_pipeline",
    description="توزيع العملاء الفعلي على جميع مراحل البيع (Pipeline Stages).",
    category="reporting",
    parameters_schema={}
)
def get_customer_pipeline(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    leads_q = db.query(Lead).filter(Lead.company_id == user.company_id)
    if user.role == UserRole.SALES_AGENT:
        leads_q = leads_q.filter(Lead.assigned_agent_id == user.id)

    stage_counts = (
        db.query(Lead.pipeline_stage, func.count(Lead.id))
        .filter(Lead.company_id == user.company_id)
        .group_by(Lead.pipeline_stage)
        .all()
    )

    stage_map = {stage.value: 0 for stage in PipelineStage}
    for st, count in stage_counts:
        if st:
            stage_map[st.value] = count

    lines = ["توزيع خط الأنابيب (Pipeline):"]
    for s_name, c in stage_map.items():
        if c > 0:
            lines.append(f"- {s_name}: {c} عميل")

    return ToolResult(
        success=True,
        data=stage_map,
        message="\n".join(lines)
    )


@ai_tool_registry.register(
    name="get_team_performance",
    description="استعراض مؤشرات أداء فريق المبيعات (مكالمات، زيارات، صفقات ناجحة لكل موظف).",
    category="reporting",
    parameters_schema={
        "properties": {
            "team_id": {"type": "integer", "description": "معرف الفريق (اختياري)"}
        }
    },
    required_roles=[UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.TEAM_LEADER]
)
def get_team_performance(db: Session, user: User, params: Dict[str, Any]) -> ToolResult:
    agents_q = db.query(User).filter(
        User.company_id == user.company_id,
        User.is_active == True,
        User.role == UserRole.SALES_AGENT
    )
    if user.role == UserRole.TEAM_LEADER and user.team_id:
        agents_q = agents_q.filter(User.team_id == user.team_id)
    elif params.get("team_id"):
        agents_q = agents_q.filter(User.team_id == params["team_id"])

    agents = agents_q.all()
    performance = []
    for agent in agents:
        leads_count = db.query(Lead).filter(Lead.assigned_agent_id == agent.id).count()
        won_count = db.query(Lead).filter(
            Lead.assigned_agent_id == agent.id,
            Lead.pipeline_stage == PipelineStage.WON
        ).count()
        activities_count = db.query(Activity).filter(Activity.user_id == agent.id).count()
        appts_count = db.query(Appointment).filter(Appointment.user_id == agent.id).count()

        performance.append({
            "agent_id": agent.id,
            "name": agent.full_name,
            "leads_count": leads_count,
            "won_deals": won_count,
            "activities_logged": activities_count,
            "appointments": appts_count
        })

    msg_lines = [f"مؤشرات أداء المبيعات ({len(performance)} موظف):"]
    for p in performance[:10]:
        msg_lines.append(f"- {p['name']}: {p['won_deals']} صفقات ناجحة | {p['leads_count']} عميل مسند | {p['activities_logged']} نشاط مسجل")

    return ToolResult(
        success=True,
        data=performance,
        message="\n".join(msg_lines)
    )

