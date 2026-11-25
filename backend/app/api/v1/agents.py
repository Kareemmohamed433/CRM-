from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_permission, Permissions
from backend.app.models.models import (
    User, UserRole, Team, Lead, Activity, FollowUp, SalesAgentProfile,
    LeadAssignmentHistory, Notification, PipelineStage, ActivityType, FollowUpStatus
)
from backend.app.schemas.agent import (
    AgentWithStatsOut, SalesAgentProfileOut, SalesAgentProfileUpdate, BulkLeadTransferRequest
)

router = APIRouter(prefix="/agents", tags=["Sales Agents Management"])


@router.get("", response_model=List[AgentWithStatsOut])
def list_sales_agents(
    team_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists sales agents within authorized organizational scope.
    - Company Admin & Sales Manager: All company sales agents
    - Team Leader: Agents in their team
    - Sales Agent: Sees themselves
    """
    company_id = current_user.company_id
    query = db.query(User).filter(
        User.company_id == company_id,
        User.role == UserRole.SALES_AGENT
    )

    if current_user.role == UserRole.SALES_AGENT:
        query = query.filter(User.id == current_user.id)
    elif current_user.role == UserRole.TEAM_LEADER:
        if current_user.team_id:
            query = query.filter(User.team_id == current_user.team_id)
        else:
            query = query.filter(User.id == current_user.id)
    elif team_id:
        query = query.filter(User.team_id == team_id)

    agents = query.all()
    results = []

    for ag in agents:
        # Fetch or auto-create profile if missing
        prof = db.query(SalesAgentProfile).filter(SalesAgentProfile.user_id == ag.id).first()
        if not prof:
            prof = SalesAgentProfile(
                user_id=ag.id,
                company_id=company_id,
                personality_prompt="مندوب مبيعات عقاري محترف، ودود ولبق، يتحدث باللهجة المصرية الطبيعية بإيجاز واحترافية.",
                preferred_voice="ar-EG-SalmaNeural",
                speaking_rate="+20%",
                working_hours_start="09:00",
                working_hours_end="18:00",
                max_active_leads=50,
                is_accepting_leads=True,
                monthly_target_sales=10000000.0,
                target_visits_per_month=20,
            )
            db.add(prof)
            db.flush()

        # Compute agent stats
        total_leads = db.query(Lead).filter(Lead.assigned_agent_id == ag.id).count()
        active_leads = db.query(Lead).filter(
            Lead.assigned_agent_id == ag.id,
            ~Lead.pipeline_stage.in_([PipelineStage.WON, PipelineStage.LOST])
        ).count()
        won_leads = db.query(Lead).filter(
            Lead.assigned_agent_id == ag.id,
            Lead.pipeline_stage == PipelineStage.WON
        ).count()
        conversion = round((won_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

        visits = db.query(Activity).filter(
            Activity.user_id == ag.id,
            Activity.activity_type == ActivityType.VISIT
        ).count()

        overdue_tasks = db.query(FollowUp).filter(
            FollowUp.assigned_user_id == ag.id,
            FollowUp.due_date < datetime.utcnow(),
            FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.OVERDUE, FollowUpStatus.DUE_TODAY])
        ).count()

        results.append(AgentWithStatsOut(
            id=ag.id,
            company_id=ag.company_id,
            email=ag.email,
            full_name=ag.full_name,
            phone=ag.phone,
            role=ag.role,
            is_active=ag.is_active,
            team_id=ag.team_id,
            team_name=ag.team.name if ag.team else None,
            profile=SalesAgentProfileOut.model_validate(prof) if prof else None,
            total_assigned_leads=total_leads,
            active_leads=active_leads,
            won_leads=won_leads,
            conversion_rate=conversion,
            completed_visits=visits,
            overdue_followups=overdue_tasks
        ))

    db.commit()
    return results


@router.get("/{agent_id}", response_model=AgentWithStatsOut)
def get_sales_agent_detail(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ag = db.query(User).filter(
        User.id == agent_id,
        User.company_id == current_user.company_id
    ).first()
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found in company")

    if current_user.role == UserRole.SALES_AGENT and current_user.id != agent_id:
        raise HTTPException(status_code=403, detail="Cannot view another agent profile")
    if current_user.role == UserRole.TEAM_LEADER and ag.team_id != current_user.team_id and ag.id != current_user.id:
        raise HTTPException(status_code=403, detail="Agent not in your assigned team")

    prof = db.query(SalesAgentProfile).filter(SalesAgentProfile.user_id == ag.id).first()
    total_leads = db.query(Lead).filter(Lead.assigned_agent_id == ag.id).count()
    active_leads = db.query(Lead).filter(
        Lead.assigned_agent_id == ag.id,
        ~Lead.pipeline_stage.in_([PipelineStage.WON, PipelineStage.LOST])
    ).count()
    won_leads = db.query(Lead).filter(Lead.assigned_agent_id == ag.id, Lead.pipeline_stage == PipelineStage.WON).count()
    conversion = round((won_leads / total_leads * 100), 1) if total_leads > 0 else 0.0
    visits = db.query(Activity).filter(Activity.user_id == ag.id, Activity.activity_type == ActivityType.VISIT).count()
    overdue_tasks = db.query(FollowUp).filter(
        FollowUp.assigned_user_id == ag.id,
        FollowUp.due_date < datetime.utcnow(),
        FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.OVERDUE, FollowUpStatus.DUE_TODAY])
    ).count()

    return AgentWithStatsOut(
        id=ag.id,
        company_id=ag.company_id,
        email=ag.email,
        full_name=ag.full_name,
        phone=ag.phone,
        role=ag.role,
        is_active=ag.is_active,
        team_id=ag.team_id,
        team_name=ag.team.name if ag.team else None,
        profile=SalesAgentProfileOut.model_validate(prof) if prof else None,
        total_assigned_leads=total_leads,
        active_leads=active_leads,
        won_leads=won_leads,
        conversion_rate=conversion,
        completed_visits=visits,
        overdue_followups=overdue_tasks
    )


@router.patch("/{agent_id}/profile", response_model=SalesAgentProfileOut)
def update_sales_agent_profile(
    agent_id: int,
    payload: SalesAgentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates AI personality, voice parameters, sales targets, or working hours."""
    ag = db.query(User).filter(
        User.id == agent_id,
        User.company_id == current_user.company_id
    ).first()
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found in company")

    # Only manager/admin or agent themselves can edit personality/voice
    if current_user.role == UserRole.SALES_AGENT and current_user.id != agent_id:
        raise HTTPException(status_code=403, detail="Cannot edit another agent's profile")

    prof = db.query(SalesAgentProfile).filter(SalesAgentProfile.user_id == ag.id).first()
    if not prof:
        prof = SalesAgentProfile(user_id=ag.id, company_id=current_user.company_id)
        db.add(prof)

    update_dict = payload.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if value is not None:
            setattr(prof, key, value)

    db.commit()
    db.refresh(prof)
    return prof


@router.post("/{agent_id}/transfer-leads")
def bulk_transfer_agent_leads(
    agent_id: int,
    payload: BulkLeadTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permissions.CUSTOMERS_REASSIGN))
):
    """
    Reassigns leads from source agent to target agent with historical audit tracking.
    Enforces tenant boundaries and prevents cross-company leakage.
    """
    source_agent = db.query(User).filter(
        User.id == agent_id,
        User.company_id == current_user.company_id
    ).first()
    target_agent = db.query(User).filter(
        User.id == payload.target_agent_id,
        User.company_id == current_user.company_id
    ).first()

    if not source_agent or not target_agent:
        raise HTTPException(status_code=404, detail="Source or target agent not found in company")

    # Find leads to transfer
    query = db.query(Lead).filter(
        Lead.company_id == current_user.company_id,
        Lead.assigned_agent_id == source_agent.id
    )
    if payload.lead_ids:
        query = query.filter(Lead.id.in_(payload.lead_ids))
    else:
        # Only transfer active leads
        query = query.filter(~Lead.pipeline_stage.in_([PipelineStage.WON, PipelineStage.LOST]))

    leads_to_transfer = query.all()
    if not leads_to_transfer:
        return {"success": True, "transferred_count": 0, "message": "No matching leads found to transfer"}

    now = datetime.utcnow()
    for lead in leads_to_transfer:
        prev_id = lead.assigned_agent_id
        lead.assigned_agent_id = target_agent.id
        if target_agent.team_id:
            lead.team_id = target_agent.team_id

        # Record assignment history
        history = LeadAssignmentHistory(
            company_id=current_user.company_id,
            lead_id=lead.id,
            previous_agent_id=prev_id,
            new_agent_id=target_agent.id,
            changed_by_id=current_user.id,
            reason=f"{payload.reason} - {payload.notes}".strip(" -"),
            created_at=now
        )
        db.add(history)

    # Notify target agent
    notif = Notification(
        company_id=current_user.company_id,
        user_id=target_agent.id,
        title="Leads Reassigned to You",
        message=f"{len(leads_to_transfer)} leads were transferred to you by {current_user.full_name}: {payload.reason}",
        link="/leads",
        notification_type="LEAD_ASSIGNED",
        is_read=False,
        created_at=now
    )
    db.add(notif)
    db.commit()

    return {
        "success": True,
        "transferred_count": len(leads_to_transfer),
        "target_agent": target_agent.full_name,
        "reason": payload.reason
    }
