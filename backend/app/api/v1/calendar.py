from typing import List, Optional
from datetime import datetime, timedelta, time
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import (
    User, UserRole, Appointment, FollowUp, Lead, AppointmentStatus, FollowUpStatus
)
from backend.app.schemas.calendar import UnifiedCalendarEvent, CalendarDailyBriefing
from backend.app.services.egyptian_nlp import get_current_cairo_time

router = APIRouter(prefix="/calendar", tags=["Calendar"])


def _map_event_type(raw_type: str, source: str) -> str:
    if source == "TASK":
        if raw_type in ["Call", "Phone Call"]:
            return "Phone Call"
        return "Task"
    # Appointment
    if raw_type in ["Property Visit", "معاينة موقع", "زيارة موقع"]:
        return "Property Visit"
    elif raw_type in ["Office Meeting", "مقابلة مكتبية", "اجتماع بالمكتب"]:
        return "Office Meeting"
    elif raw_type in ["Client Meeting", "اجتماع عميل"]:
        return "Client Meeting"
    elif raw_type in ["Call", "Phone Call"]:
        return "Phone Call"
    return "Office Meeting"


def _get_color(event_type: str) -> str:
    color_map = {
        "Task": "#10B981",          # Emerald
        "Phone Call": "#F59E0B",    # Amber
        "Office Meeting": "#3B82F6",# Blue
        "Property Visit": "#8B5CF6",# Violet / Purple
        "Client Meeting": "#06B6D4",# Cyan
    }
    return color_map.get(event_type, "#6366F1")


@router.get("/events", response_model=List[UnifiedCalendarEvent])
def get_unified_calendar_events(
    start_date: Optional[str] = Query(None, description="Start date ISO string"),
    end_date: Optional[str] = Query(None, description="End date ISO string"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    user_id: Optional[int] = Query(None, description="Filter by specific assigned user"),
    my_events_only: bool = Query(False, description="Filter only current user's events"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns unified chronological events combining Appointments and FollowUp Tasks.
    Enforces RBAC scoping and performs non-blocking schedule conflict detection.
    """
    cairo_now = get_current_cairo_time()
    
    # 1. Parse start and end date boundaries
    if start_date:
        start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    else:
        start_dt = cairo_now - timedelta(days=30)

    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    else:
        end_dt = cairo_now + timedelta(days=60)

    # 2. Build Appointment query
    appt_q = db.query(Appointment).filter(
        Appointment.company_id == current_user.company_id,
        Appointment.start_time >= start_dt,
        Appointment.start_time <= end_dt
    )

    # 3. Build FollowUp Task query
    task_q = db.query(FollowUp).filter(
        FollowUp.company_id == current_user.company_id,
        FollowUp.due_date >= start_dt,
        FollowUp.due_date <= end_dt
    )

    # 4. Apply RBAC restrictions
    if current_user.role == UserRole.SALES_AGENT or my_events_only:
        appt_q = appt_q.filter(Appointment.user_id == current_user.id)
        task_q = task_q.filter(FollowUp.assigned_user_id == current_user.id)
    elif current_user.role == UserRole.TEAM_LEADER:
        if current_user.team_id:
            team_user_ids = [u.id for u in db.query(User.id).filter(User.team_id == current_user.team_id).all()]
            appt_q = appt_q.filter(Appointment.user_id.in_(team_user_ids))
            task_q = task_q.filter(FollowUp.assigned_user_id.in_(team_user_ids))
        else:
            appt_q = appt_q.filter(Appointment.user_id == current_user.id)
            task_q = task_q.filter(FollowUp.assigned_user_id == current_user.id)

    if user_id and current_user.role in [UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER]:
        appt_q = appt_q.filter(Appointment.user_id == user_id)
        task_q = task_q.filter(FollowUp.assigned_user_id == user_id)

    appts = appt_q.all()
    tasks = task_q.all()

    unified: List[UnifiedCalendarEvent] = []

    # Process Appointments
    for a in appts:
        etype = _map_event_type(a.appointment_type, "APPOINTMENT")
        lead = db.query(Lead).filter(Lead.id == a.lead_id).first() if a.lead_id else None
        user = db.query(User).filter(User.id == a.user_id).first()
        u_event = UnifiedCalendarEvent(
            id=f"appt-{a.id}",
            original_id=a.id,
            source_type="APPOINTMENT",
            event_type=etype,
            title=a.title,
            description=a.notes,
            start_time=a.start_time,
            end_time=a.end_time or (a.start_time + timedelta(minutes=60)),
            lead_id=a.lead_id,
            lead_name=lead.full_name if lead else None,
            lead_phone=lead.phone if lead else None,
            assigned_user_id=a.user_id,
            assigned_user_name=user.full_name if user else "موظف غير معروف",
            location=a.location,
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
            has_conflict=False,
            conflict_notes=None,
            color=_get_color(etype)
        )
        unified.append(u_event)

    # Process FollowUp Tasks
    for t in tasks:
        etype = _map_event_type(t.follow_up_type, "TASK")
        lead = db.query(Lead).filter(Lead.id == t.lead_id).first() if t.lead_id else None
        user = db.query(User).filter(User.id == t.assigned_user_id).first()
        start = t.due_date
        end = start + timedelta(minutes=30)
        u_event = UnifiedCalendarEvent(
            id=f"task-{t.id}",
            original_id=t.id,
            source_type="TASK",
            event_type=etype,
            title=t.purpose,
            description=t.notes,
            start_time=start,
            end_time=end,
            lead_id=t.lead_id,
            lead_name=lead.full_name if lead else None,
            lead_phone=lead.phone if lead else None,
            assigned_user_id=t.assigned_user_id,
            assigned_user_name=user.full_name if user else "موظف غير معروف",
            priority=t.priority.value if hasattr(t.priority, "value") else str(t.priority),
            status=t.status.value if hasattr(t.status, "value") else str(t.status),
            has_conflict=False,
            conflict_notes=None,
            color=_get_color(etype)
        )
        unified.append(u_event)

    # Filter by event_type if specified
    if event_type:
        unified = [e for e in unified if e.event_type == event_type]

    # Sort chronologically by start_time
    unified.sort(key=lambda x: x.start_time)

    # Schedule Conflict Detection (per assigned user)
    # Checks for overlapping intervals [start_time, end_time)
    for i in range(len(unified)):
        for j in range(i + 1, len(unified)):
            e1 = unified[i]
            e2 = unified[j]
            # Only consider active events for the same assigned user
            if e1.assigned_user_id == e2.assigned_user_id:
                if e1.status not in ["CANCELLED", "COMPLETED"] and e2.status not in ["CANCELLED", "COMPLETED"]:
                    if e1.start_time < e2.end_time and e2.start_time < e1.end_time:
                        e1.has_conflict = True
                        e2.has_conflict = True
                        msg1 = f"تضارب زمني مع '{e2.title}' ({e2.start_time.strftime('%H:%M')})"
                        msg2 = f"تضارب زمني مع '{e1.title}' ({e1.start_time.strftime('%H:%M')})"
                        e1.conflict_notes = f"{e1.conflict_notes}; {msg1}" if e1.conflict_notes else msg1
                        e2.conflict_notes = f"{e2.conflict_notes}; {msg2}" if e2.conflict_notes else msg2

    return unified


@router.get("/briefing", response_model=CalendarDailyBriefing)
def get_calendar_daily_briefing(
    target_date: Optional[str] = Query(None, description="Target date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns dynamic daily briefing data for calendar view (Cairo time greeting,
    counts, earliest event time, conflicts, and summary).
    """
    cairo_now = get_current_cairo_time()
    if target_date:
        try:
            day_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            day_date = cairo_now.date()
    else:
        day_date = cairo_now.date()

    day_start = datetime.combine(day_date, time.min)
    day_end = datetime.combine(day_date, time.max)

    # Greeting based on Cairo current hour
    greeting = "صباح الخير" if cairo_now.hour < 14 else "مساء الخير"

    # User scoping
    user_filter = (Appointment.user_id == current_user.id) if current_user.role == UserRole.SALES_AGENT else True
    task_user_filter = (FollowUp.assigned_user_id == current_user.id) if current_user.role == UserRole.SALES_AGENT else True

    # Appointments on that day
    appts = db.query(Appointment).filter(
        Appointment.company_id == current_user.company_id,
        user_filter,
        Appointment.start_time >= day_start,
        Appointment.start_time <= day_end
    ).order_by(Appointment.start_time.asc()).all()

    # Tasks on that day
    tasks_today = db.query(FollowUp).filter(
        FollowUp.company_id == current_user.company_id,
        task_user_filter,
        FollowUp.due_date >= day_start,
        FollowUp.due_date <= day_end
    ).order_by(FollowUp.due_date.asc()).all()

    # Overdue tasks (before today and not completed/cancelled)
    overdue_tasks = db.query(FollowUp).filter(
        FollowUp.company_id == current_user.company_id,
        task_user_filter,
        FollowUp.due_date < day_start,
        FollowUp.status.notin_([FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED])
    ).all()

    total_events = len(appts) + len(tasks_today)
    earliest_time = None

    times = [a.start_time for a in appts] + [t.due_date for t in tasks_today]
    if times:
        earliest_dt = min(times)
        hour_12 = earliest_dt.strftime("%I:%M").lstrip("0")
        period = "صباحاً" if earliest_dt.hour < 12 else "مساءً"
        earliest_time = f"{hour_12} {period}"

    # Conflict detection among today's events
    conflicts_count = 0
    all_today = [(a.start_time, a.end_time or (a.start_time + timedelta(minutes=60)), a.user_id) for a in appts] + \
                [(t.due_date, t.due_date + timedelta(minutes=30), t.assigned_user_id) for t in tasks_today]
    
    for i in range(len(all_today)):
        for j in range(i + 1, len(all_today)):
            s1, e1, u1 = all_today[i]
            s2, e2, u2 = all_today[j]
            if u1 == u2 and s1 < e2 and s2 < e1:
                conflicts_count += 1

    summary_text = f"{greeting} يا فندم! لديك {len(appts)} موعد و {len(tasks_today)} مهمة مجدولة لـ {day_date.strftime('%Y-%m-%d')}."
    if earliest_time:
        summary_text += f" أول التزام يبدأ الساعة {earliest_time}."
    if len(overdue_tasks) > 0:
        summary_text += f" ويوجد {len(overdue_tasks)} مهام متأخرة تحتاج اهتمامك."

    attention = []
    if len(overdue_tasks) > 0:
        attention.append(f"{len(overdue_tasks)} مهام متأخرة من أيام سابقة بحاجة لإنجاز أو إعادة جدولة")
    if conflicts_count > 0:
        attention.append(f"يوجد {conflicts_count} تضارب في المواعيد اليوم بحاجة للتنسيق")

    return CalendarDailyBriefing(
        cairo_greeting=greeting,
        selected_date=day_date.strftime("%Y-%m-%d"),
        total_events=total_events,
        appointments_count=len(appts),
        tasks_count=len(tasks_today),
        overdue_count=len(overdue_tasks),
        due_today_count=len(tasks_today),
        earliest_event_time=earliest_time,
        conflicts_count=conflicts_count,
        summary_text=summary_text,
        attention_items=attention
    )
