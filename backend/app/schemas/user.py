from typing import Optional, List
from pydantic import BaseModel, EmailStr
from backend.app.models.models import UserRole
from backend.app.schemas.auth import UserOut


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole = UserRole.SALES_AGENT
    team_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    team_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class TeamCreate(BaseModel):
    name: str
    leader_id: Optional[int] = None


class TeamOut(BaseModel):
    id: int
    company_id: int
    name: str
    leader_id: Optional[int] = None
    leader_name: Optional[str] = None
    member_count: int = 0

    class Config:
        from_attributes = True
