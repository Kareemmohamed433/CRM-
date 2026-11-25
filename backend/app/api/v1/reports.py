from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles
from backend.app.models.models import Lead, Activity, Property, User, UserRole, PipelineStage

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("/overview")
def get_reports_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.TEAM_LEADER, UserRole.SUPER_ADMIN]))
) -> Dict[str, Any]:
    company_id = current_user.company_id

    # 1. Pipeline distribution
    stages = [
        PipelineStage.NEW, PipelineStage.CONTACTED, PipelineStage.QUALIFIED,
        PipelineStage.INTERESTED, PipelineStage.VISIT_SCHEDULED, PipelineStage.VISIT_COMPLETED,
        PipelineStage.NEGOTIATION, PipelineStage.RESERVATION, PipelineStage.WON, PipelineStage.LOST
    ]
    funnel = []
    for s in stages:
        cnt = db.query(Lead).filter(Lead.company_id == company_id, Lead.pipeline_stage == s).count()
        funnel.append({"stage": s.value, "count": cnt})

    # 2. Source distribution
    source_counts = (
        db.query(Lead.source, func.count(Lead.id))
        .filter(Lead.company_id == company_id)
        .group_by(Lead.source)
        .all()
    )
    sources = [{"source": src or "Unknown", "count": cnt} for src, cnt in source_counts]

    # 3. Objections & Lost reasons breakdown
    objection_counts = (
        db.query(Activity.objection, func.count(Activity.id))
        .filter(
            Activity.company_id == company_id,
            Activity.objection != "",
            Activity.objection != None
        )
        .group_by(Activity.objection)
        .all()
    )
    objections = [{"reason": obj, "count": cnt} for obj, cnt in objection_counts]

    # 4. Conversion funnel rates
    total_leads = db.query(Lead).filter(Lead.company_id == company_id).count()
    visited_leads = db.query(Lead).filter(
        Lead.company_id == company_id,
        Lead.pipeline_stage.in_([PipelineStage.VISIT_COMPLETED, PipelineStage.NEGOTIATION, PipelineStage.RESERVATION, PipelineStage.WON])
    ).count()
    won_leads = db.query(Lead).filter(Lead.company_id == company_id, Lead.pipeline_stage == PipelineStage.WON).count()

    lead_to_visit_rate = round((visited_leads / total_leads * 100), 1) if total_leads > 0 else 0.0
    visit_to_won_rate = round((won_leads / visited_leads * 100), 1) if visited_leads > 0 else 0.0

    return {
        "funnel": funnel,
        "sources": sources,
        "objections": objections,
        "conversions": {
            "total_leads": total_leads,
            "visited_leads": visited_leads,
            "won_leads": won_leads,
            "lead_to_visit_rate": lead_to_visit_rate,
            "visit_to_won_rate": visit_to_won_rate
        }
    }
