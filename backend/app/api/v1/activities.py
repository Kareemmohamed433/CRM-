from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, get_scoped_lead_query
from backend.app.models.models import (
    Activity, Lead, Property, User, ActivityType, FollowUp, FollowUpStatus,
    PriorityLevel, PipelineStage
)
from backend.app.schemas.activity import ActivityCreate, ActivityOut, VisitOutcomeCreate
from backend.app.services.matching_service import find_alternative_properties
from backend.app.services.scoring_service import calculate_lead_score

router = APIRouter(prefix="/activities", tags=["Activities, Visits & Objections"])


@router.get("", response_model=List[ActivityOut])
def list_activities(
    lead_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Activity).filter(Activity.company_id == current_user.company_id)
    if lead_id:
        # Check tenant access to this lead
        lead = db.query(Lead).filter(Lead.id == lead_id, Lead.company_id == current_user.company_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        query = query.filter(Activity.lead_id == lead_id)

    activities = query.order_by(Activity.created_at.desc()).limit(limit).all()
    return [
        ActivityOut(
            id=a.id,
            company_id=a.company_id,
            lead_id=a.lead_id,
            lead_name=a.lead.full_name if a.lead else None,
            property_id=a.property_id,
            property_unit=a.property.unit_number if a.property else None,
            user_id=a.user_id,
            user_name=a.user.full_name if a.user else None,
            activity_type=a.activity_type,
            summary=a.summary,
            outcome=a.outcome,
            objection=a.objection,
            sentiment=a.sentiment,
            next_action=a.next_action,
            next_followup_date=a.next_followup_date,
            created_at=a.created_at,
        )
        for a in activities
    ]


@router.post("", response_model=ActivityOut)
def create_activity(
    act_in: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify lead belongs to company
    lead = db.query(Lead).filter(Lead.id == act_in.lead_id, Lead.company_id == current_user.company_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    new_act = Activity(
        company_id=current_user.company_id,
        lead_id=act_in.lead_id,
        property_id=act_in.property_id,
        user_id=current_user.id,
        activity_type=act_in.activity_type,
        summary=act_in.summary,
        outcome=act_in.outcome or "",
        objection=act_in.objection or "",
        sentiment=act_in.sentiment or "Neutral",
        next_action=act_in.next_action or "",
        next_followup_date=act_in.next_followup_date,
    )
    db.add(new_act)

    # Update lead last_contact_date and next_followup_date if provided
    lead.last_contact_date = datetime.utcnow()
    if act_in.next_followup_date:
        lead.next_followup_date = act_in.next_followup_date
        # Create follow-up automatically
        f = FollowUp(
            company_id=current_user.company_id,
            lead_id=lead.id,
            assigned_user_id=lead.assigned_agent_id or current_user.id,
            team_id=lead.team_id,
            follow_up_type="Call",
            purpose=act_in.next_action or f"Follow-up after {act_in.activity_type.value}",
            due_date=act_in.next_followup_date,
            priority=PriorityLevel.MEDIUM,
            status=FollowUpStatus.PENDING,
            notes=f"Auto-scheduled from activity outcome: {act_in.outcome}"
        )
        db.add(f)

    # Re-calculate score
    score, factors, prio = calculate_lead_score(lead)
    lead.score = score
    lead.score_factors = factors
    lead.priority = prio

    db.commit()
    db.refresh(new_act)

    return ActivityOut(
        id=new_act.id,
        company_id=new_act.company_id,
        lead_id=new_act.lead_id,
        lead_name=lead.full_name,
        property_id=new_act.property_id,
        property_unit=new_act.property.unit_number if new_act.property else None,
        user_id=new_act.user_id,
        user_name=current_user.full_name,
        activity_type=new_act.activity_type,
        summary=new_act.summary,
        outcome=new_act.outcome,
        objection=new_act.objection,
        sentiment=new_act.sentiment,
        next_action=new_act.next_action,
        next_followup_date=new_act.next_followup_date,
        created_at=new_act.created_at,
    )


@router.post("/visit-outcome")
def record_visit_outcome(
    outcome_in: VisitOutcomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Records property visit outcome, customer objections, and automatically
    returns recommended alternative inventory without dropping the lead to lost.
    """
    lead = db.query(Lead).filter(Lead.id == outcome_in.lead_id, Lead.company_id == current_user.company_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    prop = None
    if outcome_in.property_id:
        prop = db.query(Property).filter(
            Property.id == outcome_in.property_id,
            Property.company_id == current_user.company_id
        ).first()

    summary_text = outcome_in.feedback_notes
    if outcome_in.objection:
        summary_text += f" | اعتراض العميل: {outcome_in.objection}"

    activity = Activity(
        company_id=current_user.company_id,
        lead_id=lead.id,
        property_id=outcome_in.property_id,
        user_id=current_user.id,
        activity_type=ActivityType.VISIT,
        summary=summary_text,
        outcome=outcome_in.outcome,
        objection=outcome_in.objection or "",
        sentiment="Hesitant" if outcome_in.objection else "Interested",
        next_action="البحث عن وحدات بديلة وتحديد موعد متابعة",
        next_followup_date=outcome_in.next_followup_date,
    )
    db.add(activity)

    # Lead updates: advance to VISIT_COMPLETED (unless deal won)
    lead.last_contact_date = datetime.utcnow()
    lead.pipeline_stage = PipelineStage.VISIT_COMPLETED

    # If customer stated a new budget constraint, update lead budget
    if outcome_in.customer_stated_budget and outcome_in.customer_stated_budget > 0:
        lead.budget_max = outcome_in.customer_stated_budget

    if outcome_in.next_followup_date:
        lead.next_followup_date = outcome_in.next_followup_date
        followup = FollowUp(
            company_id=current_user.company_id,
            lead_id=lead.id,
            assigned_user_id=lead.assigned_agent_id or current_user.id,
            team_id=lead.team_id,
            follow_up_type="Call",
            purpose=f"متابعة بعد المعاينة وعرض البدائل ({lead.full_name})",
            due_date=outcome_in.next_followup_date,
            priority=PriorityLevel.HIGH,
            status=FollowUpStatus.PENDING,
            notes=f"سبب الاعتراض: {outcome_in.objection or 'ملاحظات المعاينة'}"
        )
        db.add(followup)

    # Re-calculate score
    score, factors, prio = calculate_lead_score(lead)
    lead.score = score
    lead.score_factors = factors
    lead.priority = prio

    db.commit()

    # Find alternatives
    alternatives = []
    if outcome_in.suggest_alternatives:
        alternatives = find_alternative_properties(
            db=db,
            company_id=current_user.company_id,
            max_price=lead.budget_max if lead.budget_max > 0 else None,
            preferred_location=lead.preferred_location,
            property_type=lead.property_type,
            bedrooms=lead.bedrooms if lead.bedrooms > 0 else None,
            exclude_property_id=outcome_in.property_id,
            limit=4
        )

    return {
        "status": "success",
        "message": "تم تسجيل نتيجة المعاينة بنجاح، وتحديث خطة المتابعة وحالة العميل.",
        "activity_id": activity.id,
        "lead_id": lead.id,
        "lead_pipeline_stage": lead.pipeline_stage.value,
        "objection_recorded": outcome_in.objection,
        "recommended_alternatives": alternatives
    }
