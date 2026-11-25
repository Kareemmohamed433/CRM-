"""
Shared helper for the AI assistant (and any router) to decide what a name in a
request refers to: a LEAD (customer) or a USER (colleague).

Usage inside the assistant's create-task flow:

    res = resolve_person(db, current_user, "Dalia Fouad")
    plan = plan_task_target(current_user, res)

    if plan["action"] == "ask":
        reply(plan["message"])              # ask ONE clarifying question, no confirmation card
    elif plan["action"] == "refuse":
        reply(plan["message"])              # no card, nothing is written
    else:
        show_confirmation_card(
            lead_id=plan["lead_id"],         # None => personal reminder
            assigned_user_id=plan["assigned_user_id"],
        )
"""
from typing import Dict, List
from sqlalchemy.orm import Session

from backend.app.core.permissions import get_scoped_lead_query
from backend.app.models.models import Lead, User, UserRole

ROLE_RANK = {
    UserRole.SALES_AGENT: 1,
    UserRole.TEAM_LEADER: 2,
    UserRole.SALES_MANAGER: 3,
    UserRole.COMPANY_ADMIN: 4,
    UserRole.SUPER_ADMIN: 5,
}


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def resolve_person(db: Session, current_user: User, name: str) -> Dict[str, List]:
    """Looks the name up in leads (within the user's scope) and in company users."""
    pattern = f"%{_norm(name)}%"

    leads = (
        get_scoped_lead_query(db.query(Lead), current_user)
        .filter(Lead.full_name.ilike(pattern))
        .limit(5)
        .all()
    )
    users = (
        db.query(User)
        .filter(
            User.company_id == current_user.company_id,
            User.is_active == True,  # noqa: E712
            User.full_name.ilike(pattern),
            User.id != current_user.id,
        )
        .limit(5)
        .all()
    )
    return {"leads": leads, "users": users}


def plan_task_target(current_user: User, res: Dict[str, List]) -> Dict:
    leads, users = res["leads"], res["users"]

    # Name matches both a customer and a colleague -> must ask.
    if leads and users:
        return {
            "action": "ask",
            "message": f"'{leads[0].full_name}' موجود كعميل وكمان كزميل في الفريق. تقصد العميل ولا الزميل؟",
        }

    # Several customers with a similar name -> must ask.
    if len(leads) > 1:
        names = "، ".join(f"{l.full_name} (#{l.id})" for l in leads)
        return {"action": "ask", "message": f"لقيت أكتر من عميل بنفس الاسم: {names}. تقصد مين؟"}

    # Customer: task is a follow-up linked to the lead, assigned to the current user.
    if len(leads) == 1:
        return {
            "action": "create",
            "lead_id": leads[0].id,
            "assigned_user_id": current_user.id,
        }

    # Several colleagues with a similar name -> must ask.
    if len(users) > 1:
        names = "، ".join(u.full_name for u in users)
        return {"action": "ask", "message": f"لقيت أكتر من زميل بنفس الاسم: {names}. تقصد مين؟"}

    # Colleague
    if users:
        target = users[0]
        if current_user.role == UserRole.SALES_AGENT:
            return {
                "action": "refuse",
                "message": f"مقدرش أسجل مهمة لـ {target.full_name} لأن صلاحياتك بتسمح بتسجيل المهام لنفسك بس.",
            }
        if ROLE_RANK.get(target.role, 0) > ROLE_RANK.get(current_user.role, 0):
            return {
                "action": "refuse",
                "message": f"مقدرش أعيّن مهمة لـ {target.full_name} لأن دورها أعلى من دورك.",
            }
        if current_user.role == UserRole.TEAM_LEADER and target.team_id != current_user.team_id:
            return {"action": "refuse", "message": f"{target.full_name} مش في فريقك."}
        return {"action": "create", "lead_id": None, "assigned_user_id": target.id}

    return {"action": "ask", "message": "مالقيتش حد بالاسم ده لا في العملاء ولا في الفريق. تقصد مين بالظبط؟"}