from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, get_scoped_lead_query, has_permission, Permissions
from backend.app.models.models import (
    Lead, User, UserRole, PipelineStage, PriorityLevel, Activity,
    FollowUp, Appointment, LeadAssignmentHistory, ActivityType, Property, PropertyStatus,
    PropertyOffer
)
from backend.app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadOut, LeadStageUpdate, CustomerTimelineItem
)
from backend.app.services.scoring_service import calculate_lead_score
from backend.app.services.audit_service import log_audit_event
from backend.app.services.matching_service import find_alternative_properties

router = APIRouter(prefix="/leads", tags=["Leads & Customers"])

# Stages that hold a unit for the lead / stages where the deal is closed
RESERVING_STAGES = {PipelineStage.RESERVATION, PipelineStage.WON}
CLOSED_STAGES = {PipelineStage.WON, PipelineStage.LOST}


class LeadStageWithUnit(LeadStageUpdate):
    """Stage change that can carry the unit being reserved / sold."""
    property_id: Optional[int] = None


class LeadOutWithUnit(LeadOut):
    reserved_property: Optional[Dict[str, Any]] = None
    deal_value: Optional[float] = None


def _unit_summary(p: Property) -> Dict[str, Any]:
    return {
        "property_id": p.id,
        "unit_number": p.unit_number,
        "project_name": p.project.name if p.project else "Independent",
        "location": p.location,
        "bedrooms": p.bedrooms,
        "area": p.area,
        "total_price": p.total_price,
        "currency": p.currency,
        "status": p.availability_status.value,
        "reserved_at": p.reserved_at.isoformat() if p.reserved_at else None,
    }


def _held_units(db: Session, lead_ids: List[int]) -> Dict[int, Property]:
    """Units currently reserved/sold to the given leads (one query)."""
    if not lead_ids:
        return {}
    rows = db.query(Property).filter(
        Property.reserved_for_lead_id.in_(lead_ids),
        Property.availability_status.in_([PropertyStatus.RESERVED, PropertyStatus.SOLD]),
    ).all()
    return {p.reserved_for_lead_id: p for p in rows}


def _release_unit(p: Property) -> None:
    p.availability_status = PropertyStatus.AVAILABLE
    p.reserved_for_lead_id = None
    p.reserved_at = None


def lead_to_out_ext(l: Lead, unit: Optional[Property] = None) -> LeadOutWithUnit:
    data = lead_to_out(l).model_dump()
    data["reserved_property"] = _unit_summary(unit) if unit else None
    data["deal_value"] = unit.total_price if unit else None
    return LeadOutWithUnit(**data)


def lead_to_out(l: Lead) -> LeadOut:
    return LeadOut(
        id=l.id,
        company_id=l.company_id,
        full_name=l.full_name,
        phone=l.phone,
        email=l.email,
        preferred_contact_method=l.preferred_contact_method,
        source=l.source,
        team_id=l.team_id,
        assigned_agent_id=l.assigned_agent_id,
        assigned_agent_name=l.assigned_agent.full_name if l.assigned_agent else None,
        status=l.status,
        pipeline_stage=l.pipeline_stage,
        budget_min=l.budget_min,
        budget_max=l.budget_max,
        preferred_project_id=l.preferred_project_id,
        preferred_project_name=l.preferred_project.name if l.preferred_project else None,
        preferred_location=l.preferred_location or "",
        property_type=l.property_type or "Apartment",
        preferred_area_range=l.preferred_area_range or "",
        bedrooms=l.bedrooms or 0,
        down_payment_budget=l.down_payment_budget or 0.0,
        purchase_timeline=l.purchase_timeline or "Immediate (1 month)",
        notes=l.notes or "",
        tags=l.tags or "",
        do_not_contact=l.do_not_contact,
        last_contact_date=l.last_contact_date,
        next_followup_date=l.next_followup_date,
        priority=l.priority,
        score=l.score,
        score_factors=l.score_factors or [],
        created_at=l.created_at,
        updated_at=l.updated_at,
    )


@router.get("", response_model=List[LeadOutWithUnit])
def list_leads(
    stage: Optional[PipelineStage] = None,
    priority: Optional[PriorityLevel] = None,
    agent_id: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Lead)
    query = get_scoped_lead_query(query, current_user)

    if stage:
        query = query.filter(Lead.pipeline_stage == stage)
    if priority:
        query = query.filter(Lead.priority == priority)
    if agent_id:
        query = query.filter(Lead.assigned_agent_id == agent_id)
    if search:
        s = f"%{search}%"
        query = query.filter(
            (Lead.full_name.ilike(s)) |
            (Lead.phone.ilike(s)) |
            (Lead.email.ilike(s))
        )

    leads = query.order_by(Lead.updated_at.desc()).offset(skip).limit(limit).all()
    held = _held_units(db, [l.id for l in leads])
    return [lead_to_out_ext(l, held.get(l.id)) for l in leads]


@router.get("/{lead_id}")
def get_lead_details(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Lead).filter(Lead.id == lead_id)
    query = get_scoped_lead_query(query, current_user)
    lead = query.first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found or access unauthorized"
        )

    # Lead activities
    activities = db.query(Activity).filter(Activity.lead_id == lead.id).order_by(Activity.created_at.desc()).all()
    # Follow-ups
    followups = db.query(FollowUp).filter(FollowUp.lead_id == lead.id).order_by(FollowUp.due_date.asc()).all()
    # Appointments
    appointments = db.query(Appointment).filter(Appointment.lead_id == lead.id).order_by(Appointment.start_time.desc()).all()
    # Assignment history
    history = db.query(LeadAssignmentHistory).filter(LeadAssignmentHistory.lead_id == lead.id).order_by(LeadAssignmentHistory.created_at.desc()).all()

    held_unit = _held_units(db, [lead.id]).get(lead.id)

    # Recommended alternative properties (pointless once the deal is closed)
    if lead.pipeline_stage in CLOSED_STAGES:
        alternatives = []
    else:
        alternatives = find_alternative_properties(
            db=db,
            company_id=current_user.company_id,
            max_price=lead.budget_max if (lead.budget_max or 0) > 0 else None,
            preferred_location=lead.preferred_location,
            property_type=lead.property_type,
            bedrooms=lead.bedrooms if (lead.bedrooms or 0) > 0 else None,
            max_down_payment=lead.down_payment_budget if (lead.down_payment_budget or 0) > 0 else None,
            limit=4
        )

    return {
        "lead": lead_to_out_ext(lead, held_unit),
        "activities": [
            {
                "id": a.id,
                "activity_type": a.activity_type.value,
                "summary": a.summary,
                "outcome": a.outcome,
                "objection": a.objection,
                "sentiment": a.sentiment,
                "next_action": a.next_action,
                "user_name": a.user.full_name if a.user else "Agent",
                "property_unit": a.property.unit_number if a.property else None,
                "created_at": a.created_at.isoformat()
            }
            for a in activities
        ],
        "followups": [
            {
                "id": f.id,
                "purpose": f.purpose,
                "due_date": f.due_date.isoformat(),
                "priority": f.priority.value,
                "status": f.status.value,
                "notes": f.notes,
                "assigned_to": f.assigned_user.full_name if f.assigned_user else "Agent"
            }
            for f in followups
        ],
        "appointments": [
            {
                "id": ap.id,
                "title": ap.title,
                "appointment_type": ap.appointment_type,
                "start_time": ap.start_time.isoformat(),
                "location": ap.location,
                "status": ap.status.value
            }
            for ap in appointments
        ],
        "assignment_history": [
            {
                "id": h.id,
                "previous_agent": h.previous_agent.full_name if h.previous_agent else "Unassigned",
                "new_agent": h.new_agent.full_name if h.new_agent else "Agent",
                "changed_by": h.changed_by.full_name if h.changed_by else "Manager",
                "reason": h.reason,
                "created_at": h.created_at.isoformat()
            }
            for h in history
        ],
        "recommended_alternatives": alternatives
    }


@router.get("/{lead_id}/available-units")
def list_available_units_for_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AVAILABLE units of the company, best match for this lead first (used by the unit picker)."""
    query = get_scoped_lead_query(db.query(Lead).filter(Lead.id == lead_id), current_user)
    lead = query.first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return find_alternative_properties(
        db=db,
        company_id=current_user.company_id,
        max_price=lead.budget_max if (lead.budget_max or 0) > 0 else None,
        preferred_location=lead.preferred_location,
        property_type=lead.property_type,
        bedrooms=lead.bedrooms if (lead.bedrooms or 0) > 0 else None,
        max_down_payment=lead.down_payment_budget if (lead.down_payment_budget or 0) > 0 else None,
        limit=200,
    )


@router.post("", response_model=LeadOut)
def create_lead(
    lead_in: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce RBAC permission
    if not has_permission(current_user, Permissions.LEADS_MANAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: '{Permissions.LEADS_MANAGE}' for role '{current_user.role.value}'"
        )

    # Validate phone format
    clean_phone = lead_in.phone.strip()
    digits = "".join(c for c in clean_phone if c.isdigit())
    if len(digits) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رقم الهاتف غير صالح. يرجى إدخال رقم هاتف محمول صحيح (10 أرقام على الأقل)."
        )

    # Check duplicate phone in same tenant
    existing = db.query(Lead).filter(
        Lead.company_id == current_user.company_id,
        Lead.phone == clean_phone
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate lead: A customer with phone number {clean_phone} already exists (Lead #{existing.id}: {existing.full_name})"
        )

    # Assigning agent authorization
    assigned_agent = lead_in.assigned_agent_id
    if assigned_agent and assigned_agent != current_user.id:
        if not has_permission(current_user, Permissions.CUSTOMERS_ASSIGN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="غير مصرح لك بتعيين عملاء لمستشارين آخرين."
            )
        agent = db.query(User).filter(
            User.id == assigned_agent,
            User.company_id == current_user.company_id
        ).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="المستشار العقاري المحدد غير موجود في شركتك."
            )
    elif not assigned_agent:
        if current_user.role == UserRole.SALES_AGENT:
            assigned_agent = current_user.id

    team_id = lead_in.team_id
    if not team_id and current_user.team_id:
        team_id = current_user.team_id

    # Budget handling: keep null if not provided
    budget_val = float(lead_in.budget_max) if lead_in.budget_max is not None and lead_in.budget_max > 0 else None
    budget_min_val = float(lead_in.budget_min) if lead_in.budget_min is not None and lead_in.budget_min > 0 else None

    new_lead = Lead(
        company_id=current_user.company_id,
        full_name=lead_in.full_name.strip(),
        phone=clean_phone,
        email=lead_in.email.lower().strip() if lead_in.email else None,
        preferred_contact_method=lead_in.preferred_contact_method,
        source=lead_in.source,
        team_id=team_id,
        assigned_agent_id=assigned_agent,
        pipeline_stage=lead_in.pipeline_stage,
        budget_min=budget_min_val,
        budget_max=budget_val,
        preferred_project_id=lead_in.preferred_project_id,
        preferred_location=lead_in.preferred_location or "",
        property_type=lead_in.property_type or "Apartment",
        preferred_area_range=lead_in.preferred_area_range or "",
        bedrooms=lead_in.bedrooms or 0,
        down_payment_budget=lead_in.down_payment_budget or 0.0,
        purchase_timeline=lead_in.purchase_timeline or "Immediate (1 month)",
        notes=lead_in.notes or "",
        tags=lead_in.tags or "",
        do_not_contact=lead_in.do_not_contact,
        priority=lead_in.priority
    )

    # Compute score and factors
    score, factors, prio = calculate_lead_score(new_lead)
    new_lead.score = score
    new_lead.score_factors = factors
    new_lead.priority = prio

    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    # Log initial assignment in history if assigned
    if new_lead.assigned_agent_id:
        assign_hist = LeadAssignmentHistory(
            company_id=current_user.company_id,
            lead_id=new_lead.id,
            previous_agent_id=None,
            new_agent_id=new_lead.assigned_agent_id,
            changed_by_id=current_user.id,
            reason="Initial Lead Creation"
        )
        db.add(assign_hist)
        db.commit()

    log_audit_event(
        db=db,
        company_id=current_user.company_id,
        action="CREATE_LEAD",
        entity_type="Lead",
        entity_id=new_lead.id,
        actor_id=current_user.id,
        after_state={"full_name": new_lead.full_name, "stage": new_lead.pipeline_stage.value}
    )

    return lead_to_out(new_lead)


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: int,
    lead_in: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Lead).filter(Lead.id == lead_id)
    query = get_scoped_lead_query(query, current_user)
    lead = query.first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    before_state = {"stage": lead.pipeline_stage.value, "budget": lead.budget_max}

    changes = lead_in.model_dump(exclude_unset=True)
    new_stage = changes.get("pipeline_stage")
    if new_stage is not None and new_stage != lead.pipeline_stage:
        has_unit = lead.id in _held_units(db, [lead.id])
        if new_stage in RESERVING_STAGES or has_unit:
            raise HTTPException(
                status_code=400,
                detail="تغيير المرحلة من/إلى الحجز أو الصفقة الناجحة يتم من خلال تغيير المرحلة (مع اختيار الوحدة)."
            )

    for field, val in changes.items():
        setattr(lead, field, val)

    # Re-calculate score
    score, factors, prio = calculate_lead_score(lead)
    lead.score = score
    lead.score_factors = factors
    if lead_in.priority is None:
        lead.priority = prio

    db.commit()
    db.refresh(lead)

    log_audit_event(
        db=db,
        company_id=current_user.company_id,
        action="UPDATE_LEAD",
        entity_type="Lead",
        entity_id=lead.id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={"stage": lead.pipeline_stage.value, "budget": lead.budget_max}
    )

    return lead_to_out(lead)


@router.patch("/{lead_id}/stage", response_model=LeadOutWithUnit)
def update_lead_stage(
    lead_id: int,
    stage_in: LeadStageWithUnit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Lead).filter(Lead.id == lead_id)
    query = get_scoped_lead_query(query, current_user)
    lead = query.first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    prev_stage = lead.pipeline_stage
    target = stage_in.pipeline_stage
    now = datetime.utcnow()

    # ---- Unit handling -------------------------------------------------
    unit = _held_units(db, [lead.id]).get(lead.id)   # unit this lead already holds, if any
    released_unit_number = None

    if target in RESERVING_STAGES:
        wants_other_unit = stage_in.property_id is not None and (unit is None or unit.id != stage_in.property_id)
        if wants_other_unit:
            new_unit = db.query(Property).filter(
                Property.id == stage_in.property_id,
                Property.company_id == current_user.company_id,
            ).first()
            if not new_unit:
                raise HTTPException(status_code=404, detail="الوحدة غير موجودة في شركتك")
            if new_unit.availability_status != PropertyStatus.AVAILABLE:
                raise HTTPException(
                    status_code=409,
                    detail=f"الوحدة {new_unit.unit_number} غير متاحة حالياً ({new_unit.availability_status.value})"
                )
            if unit:                       # lead switches to a different unit: free the old one
                released_unit_number = unit.unit_number
                _release_unit(unit)
            unit = new_unit
        if unit is None:
            raise HTTPException(
                status_code=400,
                detail="يجب اختيار الوحدة قبل نقل العميل إلى مرحلة الحجز أو الصفقة الناجحة."
            )
        unit.availability_status = (
            PropertyStatus.RESERVED if target == PipelineStage.RESERVATION else PropertyStatus.SOLD
        )
        unit.reserved_for_lead_id = lead.id
        unit.reserved_at = unit.reserved_at or now
    elif unit is not None:                 # leaving RESERVATION/WON (back to negotiation, LOST, ...)
        released_unit_number = unit.unit_number
        _release_unit(unit)
        unit = None

    lead.pipeline_stage = target

    # Re-calculate score on stage change
    score, factors, prio = calculate_lead_score(lead)
    lead.score = score
    lead.score_factors = factors

    unit_note = ""
    if unit is not None:
        unit_note = f" الوحدة: {unit.unit_number} ({unit.availability_status.value})."
    elif released_unit_number:
        unit_note = f" تم تحرير الوحدة {released_unit_number}."

    # Add activity note for stage change
    act = Activity(
        company_id=current_user.company_id,
        lead_id=lead.id,
        property_id=unit.id if unit is not None else None,
        user_id=current_user.id,
        activity_type=ActivityType.NOTE,
        summary=f"تغيرت مرحلة العميل من {prev_stage.value} إلى {target.value}.{unit_note} {stage_in.notes or ''}".strip(),
        outcome=f"Stage -> {target.value}"
    )
    db.add(act)

    log_audit_event(
        db=db,
        company_id=current_user.company_id,
        action="STAGE_CHANGE",
        entity_type="Lead",
        entity_id=lead.id,
        actor_id=current_user.id,
        before_state={"stage": prev_stage.value},
        after_state={
            "stage": target.value,
            "unit": unit.unit_number if unit is not None else None,
            "released_unit": released_unit_number,
        }
    )

    db.commit()
    db.refresh(lead)
    return lead_to_out_ext(lead, unit)


@router.get("/{lead_id}/timeline", response_model=List[CustomerTimelineItem])
def get_customer_timeline(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unified Customer Timeline:
    Aggregates activities, appointments, follow-ups, property offers, and assignment changes
    in descending chronological order.
    """
    lead = get_scoped_lead_query(db.query(Lead), current_user).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found or unauthorized")

    items: List[CustomerTimelineItem] = []

    # 1. Activities
    activities = db.query(Activity).filter(
        Activity.company_id == current_user.company_id,
        Activity.lead_id == lead_id
    ).all()
    for a in activities:
        user_name = a.user.full_name if a.user else None
        items.append(CustomerTimelineItem(
            id=f"act_{a.id}",
            type="ACTIVITY",
            subtype=a.activity_type.value if a.activity_type else "NOTE",
            title=f"نشاط: {a.activity_type.value if a.activity_type else 'ملاحظة'}",
            description=a.summary or "",
            timestamp=a.created_at or datetime.utcnow(),
            user_name=user_name,
            status=a.outcome,
            metadata={"activity_id": a.id, "property_id": a.property_id, "outcome": a.outcome, "objection": a.objection}
        ))

    # 2. Appointments
    appts = db.query(Appointment).filter(
        Appointment.company_id == current_user.company_id,
        Appointment.lead_id == lead_id
    ).all()
    for ap in appts:
        host_name = ap.user.full_name if ap.user else None
        appt_type_str = ap.appointment_type or "VISIT"
        status_str = ap.status.value if hasattr(ap.status, "value") else str(ap.status) if ap.status else None
        items.append(CustomerTimelineItem(
            id=f"apt_{ap.id}",
            type="APPOINTMENT",
            subtype=appt_type_str,
            title=f"موعد: {ap.title}",
            description=f"الموقع: {ap.location or 'غير محدد'}. {ap.notes or ''}".strip(),
            timestamp=ap.start_time or ap.created_at or datetime.utcnow(),
            user_name=host_name,
            status=status_str,
            metadata={"appointment_id": ap.id, "location": ap.location, "end_time": ap.end_time.isoformat() if ap.end_time else None}
        ))

    # 3. Followups
    followups = db.query(FollowUp).filter(
        FollowUp.company_id == current_user.company_id,
        FollowUp.lead_id == lead_id
    ).all()
    for f in followups:
        agent_name = f.assigned_user.full_name if f.assigned_user else None
        f_type_str = f.follow_up_type or "CALL"
        f_status_str = f.status.value if hasattr(f.status, "value") else str(f.status) if f.status else None
        f_prio_str = f.priority.value if hasattr(f.priority, "value") else str(f.priority) if f.priority else None
        items.append(CustomerTimelineItem(
            id=f"fol_{f.id}",
            type="FOLLOWUP",
            subtype=f_type_str,
            title=f"متابعة: {f.purpose or 'متابعة دورية'}",
            description=f.notes or "",
            timestamp=f.due_date or f.created_at or datetime.utcnow(),
            user_name=agent_name,
            status=f_status_str,
            metadata={"followup_id": f.id, "priority": f_prio_str}
        ))

    # 4. Property Offers
    offers = db.query(PropertyOffer).filter(
        PropertyOffer.company_id == current_user.company_id,
        PropertyOffer.lead_id == lead_id
    ).all()
    for off in offers:
        created_name = off.created_by.full_name if off.created_by else None
        prop = off.property
        prop_str = f"الوحدة {prop.unit_number}" if prop else f"عقار #{off.property_id}"
        items.append(CustomerTimelineItem(
            id=f"off_{off.id}",
            type="PROPERTY_OFFER",
            subtype="WHATSAPP" if off.shared_via == "WHATSAPP" else "OFFER",
            title=f"عرض عقاري: {prop_str}",
            description=off.message_text or (f"السعر: {off.custom_price:,.0f} ج.م" if off.custom_price else ""),
            timestamp=off.shared_at or off.created_at or datetime.utcnow(),
            user_name=created_name,
            status=off.status.value if off.status else "PREPARED",
            metadata={
                "offer_id": off.id,
                "property_id": off.property_id,
                "custom_price": off.custom_price,
                "feedback": off.customer_feedback,
                "shared_at": off.shared_at.isoformat() if off.shared_at else None
            }
        ))

    # 5. Lead Assignment History
    assignments = db.query(LeadAssignmentHistory).filter(
        LeadAssignmentHistory.company_id == current_user.company_id,
        LeadAssignmentHistory.lead_id == lead_id
    ).all()
    for assign in assignments:
        assigner = assign.assigned_by.full_name if assign.assigned_by else None
        agent = assign.assigned_to.full_name if assign.assigned_to else "غير محدد"
        items.append(CustomerTimelineItem(
            id=f"asg_{assign.id}",
            type="ASSIGNMENT",
            subtype="TRANSFER",
            title="إعادة تعيين مسؤول العميل",
            description=f"تم إسناد العميل إلى: {agent}. السبب: {assign.reason or 'توزيع دوري'}",
            timestamp=assign.created_at or datetime.utcnow(),
            user_name=assigner,
            status="ASSIGNED",
            metadata={"assigned_to_id": assign.assigned_to_id, "reason": assign.reason}
        ))

    # Sort descending by timestamp
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items
