from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles
from backend.app.core.security import get_password_hash
from backend.app.models.models import User, UserRole, Team
from backend.app.schemas.user import UserCreate, UserUpdate, UserOut, TeamCreate, TeamOut

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserOut])
def list_company_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only return users belonging to the same company tenant
    users = db.query(User).filter(User.company_id == current_user.company_id).all()
    return [
        UserOut(
            id=u.id,
            company_id=u.company_id,
            company_name=u.company.name if u.company else None,
            email=u.email,
            full_name=u.full_name,
            phone=u.phone,
            role=u.role,
            is_active=u.is_active,
            team_id=u.team_id,
        )
        for u in users
    ]


@router.post("", response_model=UserOut)
def create_company_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN, UserRole.SALES_MANAGER]))
):
    # Hierarchy authorization check
    if current_user.role == UserRole.SALES_MANAGER:
        if user_in.role in [UserRole.SALES_MANAGER, UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sales Managers can only create Team Leaders and Sales Agents (cannot create equal or higher roles)"
            )
    elif current_user.role == UserRole.COMPANY_ADMIN:
        if user_in.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company Admins cannot create Super Admins"
            )

    # Check email duplicate
    existing = db.query(User).filter(User.email == user_in.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )

    # Validate team if provided
    if user_in.team_id:
        team = db.query(Team).filter(
            Team.id == user_in.team_id,
            Team.company_id == current_user.company_id
        ).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found in this company"
            )

    new_user = User(
        company_id=current_user.company_id,
        email=user_in.email.lower().strip(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        phone=user_in.phone,
        role=user_in.role,
        is_active=True,
        team_id=user_in.team_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserOut(
        id=new_user.id,
        company_id=new_user.company_id,
        company_name=new_user.company.name if new_user.company else None,
        email=new_user.email,
        full_name=new_user.full_name,
        phone=new_user.phone,
        role=new_user.role,
        is_active=new_user.is_active,
        team_id=new_user.team_id,
    )


@router.patch("/{user_id}", response_model=UserOut)
def update_company_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN, UserRole.SALES_MANAGER]))
):
    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == current_user.company_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Hierarchy authorization check
    if current_user.role == UserRole.SALES_MANAGER:
        if user.role in [UserRole.SALES_MANAGER, UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sales Managers cannot modify equal or higher roles"
            )
        if user_update.role and user_update.role in [UserRole.SALES_MANAGER, UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sales Managers cannot elevate users to equal or higher roles"
            )
    elif current_user.role == UserRole.COMPANY_ADMIN:
        if user_update.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company Admins cannot elevate users to Super Admin"
            )

    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.phone is not None:
        user.phone = user_update.phone
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.team_id is not None:
        user.team_id = user_update.team_id
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    if user_update.password:
        user.hashed_password = get_password_hash(user_update.password)

    db.commit()
    db.refresh(user)

    return UserOut(
        id=user.id,
        company_id=user.company_id,
        company_name=user.company.name if user.company else None,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        team_id=user.team_id,
    )
