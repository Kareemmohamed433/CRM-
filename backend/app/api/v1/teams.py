from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles
from backend.app.models.models import Team, User, UserRole
from backend.app.schemas.user import TeamCreate, TeamOut

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=List[TeamOut])
def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    teams = db.query(Team).filter(Team.company_id == current_user.company_id).all()
    results = []
    for t in teams:
        member_cnt = db.query(func.count(User.id)).filter(User.team_id == t.id).scalar() or 0
        results.append(
            TeamOut(
                id=t.id,
                company_id=t.company_id,
                name=t.name,
                leader_id=t.leader_id,
                leader_name=t.leader.full_name if t.leader else None,
                member_count=member_cnt,
            )
        )
    return results


@router.post("", response_model=TeamOut)
def create_team(
    team_in: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    team = Team(
        company_id=current_user.company_id,
        name=team_in.name,
        leader_id=team_in.leader_id,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return TeamOut(
        id=team.id,
        company_id=team.company_id,
        name=team.name,
        leader_id=team.leader_id,
        leader_name=team.leader.full_name if team.leader else None,
        member_count=0
    )
