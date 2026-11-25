from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import Appointment, Lead, Property, User, AppointmentStatus, UserRole
from backend.app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut

router = APIRouter(prefix="/appointments", tags=["Appointments & Calendar"])


@router.get("", response_model=List[AppointmentOut])
def list_appointments(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Appointment).filter(Appointment.company_id == current_user.company_id)

    if current_user.role == UserRole.SALES_AGENT:
        query = query.filter(Appointment.user_id == current_user.id)

    if start_date:
        query = query.filter(Appointment.start_time >= start_date)
    if end_date:
        query = query.filter(Appointment.start_time <= end_date)

    appointments = query.order_by(Appointment.start_time.asc()).all()

    return [
        AppointmentOut(
            id=a.id,
            company_id=a.company_id,
            lead_id=a.lead_id,
            lead_name=a.lead.full_name if a.lead else "Unknown Lead",
            property_id=a.property_id,
            property_unit=a.property.unit_number if a.property else None,
            user_id=a.user_id,
            user_name=a.user.full_name if a.user else "Agent",
            title=a.title,
            appointment_type=a.appointment_type,
            start_time=a.start_time,
            end_time=a.end_time,
            location=a.location or "",
            notes=a.notes or "",
            status=a.status,
            created_at=a.created_at
        )
        for a in appointments
    ]


@router.post("", response_model=AppointmentOut)
def create_appointment(
    app_in: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify lead in tenant
    lead = db.query(Lead).filter(Lead.id == app_in.lead_id, Lead.company_id == current_user.company_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Conflict check: does the current agent have an overlapping appointment?
    conflict = db.query(Appointment).filter(
        Appointment.company_id == current_user.company_id,
        Appointment.user_id == current_user.id,
        Appointment.status == AppointmentStatus.SCHEDULED,
        Appointment.start_time < app_in.end_time,
        Appointment.end_time > app_in.start_time
    ).first()

    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scheduling conflict: You already have '{conflict.title}' scheduled between {conflict.start_time.strftime('%I:%M %p')} and {conflict.end_time.strftime('%I:%M %p')}."
        )

    new_app = Appointment(
        company_id=current_user.company_id,
        lead_id=app_in.lead_id,
        property_id=app_in.property_id,
        user_id=current_user.id,
        title=app_in.title,
        appointment_type=app_in.appointment_type,
        start_time=app_in.start_time,
        end_time=app_in.end_time,
        location=app_in.location or "",
        notes=app_in.notes or "",
        status=AppointmentStatus.SCHEDULED
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return AppointmentOut(
        id=new_app.id,
        company_id=new_app.company_id,
        lead_id=new_app.lead_id,
        lead_name=lead.full_name,
        property_id=new_app.property_id,
        property_unit=new_app.property.unit_number if new_app.property else None,
        user_id=new_app.user_id,
        user_name=current_user.full_name,
        title=new_app.title,
        appointment_type=new_app.appointment_type,
        start_time=new_app.start_time,
        end_time=new_app.end_time,
        location=new_app.location,
        notes=new_app.notes,
        status=new_app.status,
        created_at=new_app.created_at
    )
