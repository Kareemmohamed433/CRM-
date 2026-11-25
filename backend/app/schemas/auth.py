from typing import Optional
from pydantic import BaseModel, EmailStr
from backend.app.models.models import UserRole


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    company_id: int
    company_name: Optional[str] = None
    email: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    team_id: Optional[int] = None

    class Config:
        from_attributes = True


Token.model_rebuild()
