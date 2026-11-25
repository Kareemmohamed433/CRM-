from datetime import datetime, time, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import (
    FollowUp, Lead, User, UserRole, FollowUpStatus, PriorityLevel, Activity, ActivityType
)
from backend.app.schemas.followup import (
    FollowUpCreate, FollowUpUpdate, FollowUpComplete, FollowUpOut,
    FollowUpStats, FollowUpBriefing
)
from backend.app.schemas.activity import ActivityOut
from backend.app.services.egyptian_nlp import get_current_cairo_time

router = APIRouter(prefix="/followups", tags=["Follow-ups & Tasks"])

# Higher number = higher position in the hierarchy
ROLE_RANK = {
    UserRole.SALES_AGENT: 1,
    UserRole.TEAM_LEADER: 2,
    UserRole.SALES_MANAGER: 3,
    UserRole.COMPANY_ADMIN: 4,
    UserRole.SUPER_ADMIN: 5,
}


def format_followup_out(f: FollowUp) -> FollowUpOut:
    cairo_now = get_current_cairo_time()
    start_today = datetime.combine(cairo_now.date(), time.min)
    end_today = datetime.combine(cairo_now.date(), time.max)

    is_overdue = False
    is_due_today = False

    if f.status in [FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS, FollowUpStatus.DUE_TODAY, FollowUpStatus.OVERDUE]:
        if f.due_date < start_today:
            is_overdue = True
        elif start_today <= f.due_date <= end_today:
            is_due_today = True

    return FollowUpOut(
        id=f.id,
        company_id=f.company_id,
        lead_id=f.lead_id,
        lead_name=f.lead.full_name if f.lead else ("تذكير شخصي" if not f.lead_id else "Unknown Lead"),
        lead_phone=f.lead.phone if f.lead else "",
        assigned_user_id=f.assigned_user_id,
        assigned_user_name=f.assigned_user.full_name if f.assigned_user else "Agent",
        created_by_id=f.created_by_id,
        created_by_name=f.created_by.full_name if f.created_by else None,
        team_id=f.team_id,
        follow_up_type=f.follow_up_type,
        purpose=f.purpose,
        due_date=f.due_date,
        priority=f.priority,
        status=f.status,
        notes=f.notes or "",
        completion_outcome=f.completion_outcome or "",
        created_at=f.created_at,
        completed_at=f.completed_at,
        is_overdue=is_overdue,
        is_due_today=is_due_today,
    )


def resolve_assignee(
    db: Session,
    current_user: User,
    requested_user_id: Optional[int],
) -> int:
    """
    Decides who a follow-up is assigned to, enforcing:
    - Agents can only assign to themselves
    - Assignee must be an active user in the same company
    - No assigning upward in the role hierarchy
    - Team leaders can only assign within their own team
    """
    if not requested_user_id or requested_user_id == current_user.id:
        return current_user.id

    if current_user.role == UserRole.SALES_AGENT:
        raise HTTPException(status_code=403, detail="You can only create tasks for yourself")

    assignee = db.query(User).filter(
        User.id == requested_user_id,
        User.company_id == current_user.company_id,
        User.is_active == True  # noqa: E712
    ).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assignee not found in your company")

    if ROLE_RANK.get(assignee.role, 0) > ROLE_RANK.get(current_user.role, 0):
        raise HTTPException(status_code=403, detail="You cannot assign tasks to a higher role")

    if current_user.role == UserRole.TEAM_LEADER and assignee.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="Assignee is not in your team")

    return assignee.id


def verify_followup_access(f: FollowUp, current_user: User) -> None:
    """Ownership check used when modifying/completing a follow-up."""
    if f.assigned_user_id == current_user.id:
        return

    if current_user.role in [UserRole.SALES_MANAGER, UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN]:
        # Personal reminders (no lead) stay private to their owner
        if f.lead_id is None:
            raise HTTPException(status_code=403, detail="Personal reminders are private")
        return

    if current_user.role == UserRole.TEAM_LEADER:
        if f.lead_id is not None and f.team_id == current_user.team_id:
            return
        raise HTTPException(status_code=403, detail="Follow-up does not belong to your team")

    raise HTTPException(status_code=403, detail="Not your follow-up")


# -------------------------------------------------------------------------
# Dynamic Daily Briefing & Stats for My Tasks
# -------------------------------------------------------------------------

@router.get("/my-briefing", response_model=FollowUpBriefing)
def get_my_tasks_briefing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns dynamic Cairo daily briefing for the authenticated user's tasks."""
    cairo_now = get_current_cairo_time()
    today_start = datetime.combine(cairo_now.date(), time.min)
    today_end = datetime.combine(cairo_now.date(), time.max)

    greeting = "صباح الخير" if cairo_now.hour < 14 else "مساء الخير"

    base_q = db.query(FollowUp).filter(
        FollowUp.company_id == current_user.company_id,
        FollowUp.assigned_user_id == current_user.id
    )

    overdue_count = base_q.filter(
        FollowUp.status.notin_([FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED]),
        FollowUp.due_date < today_start
    ).count()

    today_tasks = base_q.filter(
        FollowUp.due_date >= today_start,
        FollowUp.due_date <= today_end
    ).order_by(FollowUp.due_date.asc()).all()

    due_today_count = len(today_tasks)

    earliest_time = None
    if today_tasks:
        earliest_dt = today_tasks[0].due_date
        h12 = earliest_dt.strftime("%I:%M").lstrip("0")
        period = "صباحاً" if earliest_dt.hour < 12 else "مساءً"
        earliest_time = f"{h12} {period}"

    summary = f"{greeting} يا {current_user.full_name}! لديك {due_today_count} مهام ومتابعات مجدولة لليوم."
    if earliest_time:
        summary += f" أول مهمة تبدأ الساعة {earliest_time}."
    if overdue_count > 0:
        summary += f" تنبيه: يوجد {overdue_count} مهام متأخرة تحتاج معالجتها."

    actionable = []
    if overdue_count > 0:
        actionable.append(f"{overdue_count} مهام متأخرة تحتاج إنجاز فوري أو إعادة جدولة")
    if due_today_count > 0:
        actionable.append(f"{due_today_count} مهام مستحقة اليوم، الأقرب في {earliest_time or 'اليوم'}")

    return FollowUpBriefing(
        greeting=greeting,
        cairo_time=cairo_now.strftime("%Y-%m-%d %H:%M"),
        overdue_count=overdue_count,
        due_today_count=due_today_count,
        earliest_task_time=earliest_time,
        attention_summary=summary,
        actionable_items=actionable
    )


@router.get("/my-stats", response_model=FollowUpStats)
def get_my_tasks_stats(
    assigned_to_me: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns the 5 statistics counters for personal or team tasks."""
    cairo_now = get_current_cairo_time()
    today_start = datetime.combine(cairo_now.date(), time.min)
    today_end = datetime.combine(cairo_now.date(), time.max)

    query = db.query(FollowUp).filter(FollowUp.company_id == current_user.company_id)

    # Scoping
    if current_user.role == UserRole.SALES_AGENT or assigned_to_me:
        query = query.filter(FollowUp.assigned_user_id == current_user.id)
    elif current_user.role == UserRole.TEAM_LEADER and current_user.team_id:
        query = query.filter(
            ((FollowUp.team_id == current_user.team_id) & (FollowUp.lead_id != None)) |
            (FollowUp.assigned_user_id == current_user.id)
        )

    all_tasks = query.all()

    total = len(all_tasks)
    overdue = 0
    due_today = 0
    upcoming = 0
    completed = 0

    for t in all_tasks:
        if t.status == FollowUpStatus.COMPLETED:
            completed += 1
        elif t.status == FollowUpStatus.CANCELLED:
            pass
        elif t.due_date < today_start:
            overdue += 1
        elif today_start <= t.due_date <= today_end:
            due_today += 1
        else:
            upcoming += 1

    return FollowUpStats(
        total=total,
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        completed=completed
    )


# -------------------------------------------------------------------------
# Main Follow-ups / Tasks Listing with 6 Sections & Search
# -------------------------------------------------------------------------

@router.get("", response_model=List[FollowUpOut])
def list_followups(
    filter_type: Optional[str] = "all",  # backward compatibility: "all", "due_today", "overdue", "completed"
    section: Optional[str] = None,       # 6 sections: "recent", "overdue", "today", "upcoming", "completed", "all"
    assigned_to_me: bool = False,
    search: Optional[str] = None,
    priority: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    task_type: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(FollowUp).filter(FollowUp.company_id == current_user.company_id)

    # Role scoping: agent sees own, team leader sees team or own, manager/admin sees company
    if current_user.role == UserRole.SALES_AGENT or assigned_to_me:
        query = query.filter(FollowUp.assigned_user_id == current_user.id)
    elif current_user.role == UserRole.TEAM_LEADER and current_user.team_id:
        query = query.filter(
            ((FollowUp.team_id == current_user.team_id) & (FollowUp.lead_id != None)) |
            (FollowUp.assigned_user_id == current_user.id)
        )
    else:
        query = query.filter(
            (FollowUp.lead_id != None) | (FollowUp.assigned_user_id == current_user.id)
        )

    cairo_now = get_current_cairo_time()
    today_start = datetime.combine(cairo_now.date(), time.min)
    today_end = datetime.combine(cairo_now.date(), time.max)

    # Handle section or filter_type
    active_section = section or filter_type

    if active_section in ["today", "due_today"]:
        query = query.filter(
            FollowUp.status != FollowUpStatus.CANCELLED,
            FollowUp.due_date >= today_start,
            FollowUp.due_date <= today_end
        ).order_by(FollowUp.due_date.asc())
    elif active_section == "overdue":
        query = query.filter(
            FollowUp.status.notin_([FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED]),
            FollowUp.due_date < today_start
        ).order_by(FollowUp.due_date.asc())
    elif active_section == "upcoming":
        query = query.filter(
            FollowUp.status.notin_([FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED]),
            FollowUp.due_date > today_end
        ).order_by(FollowUp.due_date.asc())
    elif active_section == "completed":
        query = query.filter(
            FollowUp.status == FollowUpStatus.COMPLETED
        ).order_by(FollowUp.completed_at.desc(), FollowUp.due_date.desc())
    elif active_section == "recent":
        query = query.order_by(FollowUp.created_at.desc())
    else:
        # "all"
        query = query.order_by(FollowUp.due_date.asc())

    # Optional search filter
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.outerjoin(Lead, FollowUp.lead_id == Lead.id).filter(
            or_(
                FollowUp.purpose.ilike(term),
                FollowUp.notes.ilike(term),
                Lead.full_name.ilike(term),
                Lead.phone.ilike(term)
            )
        )

    # Priority filter
    if priority and priority in PriorityLevel.__members__:
        query = query.filter(FollowUp.priority == PriorityLevel[priority])

    # Status filter
    if status_filter and status_filter in FollowUpStatus.__members__:
        query = query.filter(FollowUp.status == FollowUpStatus[status_filter])

    # Task type filter
    if task_type:
        query = query.filter(FollowUp.follow_up_type.ilike(f"%{task_type}%"))

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    followups = query.all()
    return [format_followup_out(f) for f in followups]


@router.post("", response_model=FollowUpOut)
def create_followup(
    followup_in: FollowUpCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    team_id = current_user.team_id
    lead = None
    if followup_in.lead_id is not None:
        lead = db.query(Lead).filter(
            Lead.id == followup_in.lead_id,
            Lead.company_id == current_user.company_id
        ).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        team_id = lead.team_id

    assigned_id = resolve_assignee(db, current_user, followup_in.assigned_user_id)

    new_f = FollowUp(
        company_id=current_user.company_id,
        lead_id=followup_in.lead_id,
        assigned_user_id=assigned_id,
        created_by_id=current_user.id,
        team_id=team_id,
        follow_up_type=followup_in.follow_up_type or ("Reminder" if not followup_in.lead_id else "Call"),
        purpose=followup_in.purpose,
        due_date=followup_in.due_date,
        priority=followup_in.priority,
        status=FollowUpStatus.PENDING,
        notes=followup_in.notes or ""
    )
    db.add(new_f)

    # Update lead next_followup_date if CRM follow-up
    if lead:
        lead.next_followup_date = followup_in.due_date

    db.commit()
    db.refresh(new_f)

    return format_followup_out(new_f)


@router.patch("/{followup_id}", response_model=FollowUpOut)
def update_followup(
    followup_id: int,
    data: FollowUpUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates a task: reschedule due_date, change status, change priority, add notes, or edit title.
    """
    f = db.query(FollowUp).filter(
        FollowUp.id == followup_id,
        FollowUp.company_id == current_user.company_id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    verify_followup_access(f, current_user)

    if data.due_date is not None:
        f.due_date = data.due_date
        if f.lead_id:
            lead = db.query(Lead).filter(Lead.id == f.lead_id).first()
            if lead:
                lead.next_followup_date = data.due_date
        if f.status == FollowUpStatus.OVERDUE:
            f.status = FollowUpStatus.RESCHEDULED

    if data.status is not None:
        f.status = data.status
        if data.status == FollowUpStatus.COMPLETED and not f.completed_at:
            f.completed_at = datetime.utcnow()

    if data.priority is not None:
        f.priority = data.priority

    if data.purpose is not None:
        f.purpose = data.purpose.strip()

    if data.notes is not None:
        f.notes = data.notes

    if data.follow_up_type is not None:
        f.follow_up_type = data.follow_up_type

    if data.assigned_user_id is not None and data.assigned_user_id != f.assigned_user_id:
        new_assigned_id = resolve_assignee(db, current_user, data.assigned_user_id)
        f.assigned_user_id = new_assigned_id

    db.commit()
    db.refresh(f)
    return format_followup_out(f)


@router.get("/{followup_id}/activity", response_model=List[ActivityOut])
def get_followup_activity(
    followup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves activities associated with this task or its associated customer."""
    f = db.query(FollowUp).filter(
        FollowUp.id == followup_id,
        FollowUp.company_id == current_user.company_id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    verify_followup_access(f, current_user)

    if not f.lead_id:
        return []

    activities = db.query(Activity).filter(
        Activity.lead_id == f.lead_id,
        Activity.company_id == current_user.company_id
    ).order_by(Activity.created_at.desc()).limit(20).all()

    return activities


@router.post("/{followup_id}/complete", response_model=FollowUpOut)
def complete_followup(
    followup_id: int,
    comp_in: FollowUpComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    f = db.query(FollowUp).filter(
        FollowUp.id == followup_id,
        FollowUp.company_id == current_user.company_id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    verify_followup_access(f, current_user)

    f.status = FollowUpStatus.COMPLETED
    f.completion_outcome = comp_in.completion_outcome
    f.completed_at = datetime.utcnow()
    if comp_in.notes:
        f.notes = ((f.notes or "") + "\n" + comp_in.notes).strip()

    # Log completion as activity only if linked to lead
    if f.lead_id:
        act = Activity(
            company_id=current_user.company_id,
            lead_id=f.lead_id,
            user_id=current_user.id,
            activity_type=ActivityType.CALL if "call" in (f.follow_up_type or "").lower() else ActivityType.NOTE,
            summary=f"اكتملت المتابعة: {f.purpose}. النتيجة: {comp_in.completion_outcome}",
            outcome=comp_in.completion_outcome,
            next_action=comp_in.next_purpose or ""
        )
        db.add(act)

        lead = db.query(Lead).filter(
            Lead.id == f.lead_id,
            Lead.company_id == current_user.company_id
        ).first()
        if lead:
            lead.last_contact_date = datetime.utcnow()
            if comp_in.schedule_next and comp_in.next_due_date and comp_in.next_purpose:
                lead.next_followup_date = comp_in.next_due_date
                next_f = FollowUp(
                    company_id=current_user.company_id,
                    lead_id=lead.id,
                    assigned_user_id=f.assigned_user_id,
                    created_by_id=current_user.id,
                    team_id=f.team_id,
                    follow_up_type="Call",
                    purpose=comp_in.next_purpose,
                    due_date=comp_in.next_due_date,
                    priority=f.priority,
                    status=FollowUpStatus.PENDING,
                    notes="Scheduled following completion of previous task"
                )
                db.add(next_f)
            else:
                lead.next_followup_date = None

    db.commit()
    db.refresh(f)
    return format_followup_out(f)
