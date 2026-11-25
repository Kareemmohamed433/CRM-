from typing import List, Optional, Set
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import decode_token
from backend.app.models.models import User, UserRole, Company, Lead, Conversation

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# -------------------------------------------------------------------------
# Explicit Permission Catalogue
# -------------------------------------------------------------------------

class Permissions:
    # Customers & Leads
    CUSTOMERS_VIEW_ASSIGNED = "customers.view_assigned"
    CUSTOMERS_VIEW_TEAM = "customers.view_team"
    CUSTOMERS_VIEW_COMPANY = "customers.view_company"
    CUSTOMERS_ASSIGN = "customers.assign"
    CUSTOMERS_REASSIGN = "customers.reassign"
    CUSTOMERS_EXPORT = "customers.export"

    LEADS_VIEW_ASSIGNED = "leads.view_assigned"
    LEADS_VIEW_TEAM = "leads.view_team"
    LEADS_VIEW_COMPANY = "leads.view_company"
    LEADS_MANAGE = "leads.manage"

    # Conversations & Communications
    CONVERSATIONS_VIEW_ASSIGNED = "conversations.view_assigned"
    CONVERSATIONS_VIEW_TEAM = "conversations.view_team"
    CONVERSATIONS_VIEW_COMPANY = "conversations.view_company"
    CONVERSATIONS_VIEW_PRIVATE_NOTES = "conversations.view_private_notes"
    CONVERSATIONS_SEND = "conversations.send"

    # Analytics & Reports
    ANALYTICS_VIEW_PERSONAL = "analytics.view_personal"
    ANALYTICS_VIEW_TEAM = "analytics.view_team"
    ANALYTICS_VIEW_COMPANY = "analytics.view_company"
    SALES_VIEW_REVENUE = "sales.view_revenue"
    SALES_MANAGE_TARGETS = "sales.manage_targets"

    # Organization & Administration
    TEAMS_MANAGE_ASSIGNED = "teams.manage_assigned"
    TEAMS_MANAGE_COMPANY = "teams.manage_company"
    USERS_MANAGE_COMPANY = "users.manage_company"
    ROLES_MANAGE = "roles.manage"
    INTEGRATIONS_MANAGE_COMPANY = "integrations.manage_company"
    AUDIT_LOGS_VIEW = "audit_logs.view"
    PLATFORM_MANAGE_TENANTS = "platform.manage_tenants"


ROLE_PERMISSIONS: dict[UserRole, Set[str]] = {
    UserRole.SUPER_ADMIN: {
        # Platform Super Admin has platform-wide authority
        Permissions.CUSTOMERS_VIEW_ASSIGNED, Permissions.CUSTOMERS_VIEW_TEAM, Permissions.CUSTOMERS_VIEW_COMPANY,
        Permissions.CUSTOMERS_ASSIGN, Permissions.CUSTOMERS_REASSIGN, Permissions.CUSTOMERS_EXPORT,
        Permissions.LEADS_VIEW_ASSIGNED, Permissions.LEADS_VIEW_TEAM, Permissions.LEADS_VIEW_COMPANY, Permissions.LEADS_MANAGE,
        Permissions.CONVERSATIONS_VIEW_ASSIGNED, Permissions.CONVERSATIONS_VIEW_TEAM, Permissions.CONVERSATIONS_VIEW_COMPANY,
        Permissions.CONVERSATIONS_VIEW_PRIVATE_NOTES, Permissions.CONVERSATIONS_SEND,
        Permissions.ANALYTICS_VIEW_PERSONAL, Permissions.ANALYTICS_VIEW_TEAM, Permissions.ANALYTICS_VIEW_COMPANY,
        Permissions.SALES_VIEW_REVENUE, Permissions.SALES_MANAGE_TARGETS,
        Permissions.TEAMS_MANAGE_ASSIGNED, Permissions.TEAMS_MANAGE_COMPANY,
        Permissions.USERS_MANAGE_COMPANY, Permissions.ROLES_MANAGE,
        Permissions.INTEGRATIONS_MANAGE_COMPANY, Permissions.AUDIT_LOGS_VIEW,
        Permissions.PLATFORM_MANAGE_TENANTS,
    },
    UserRole.COMPANY_ADMIN: {
        Permissions.CUSTOMERS_VIEW_ASSIGNED, Permissions.CUSTOMERS_VIEW_TEAM, Permissions.CUSTOMERS_VIEW_COMPANY,
        Permissions.CUSTOMERS_ASSIGN, Permissions.CUSTOMERS_REASSIGN, Permissions.CUSTOMERS_EXPORT,
        Permissions.LEADS_VIEW_ASSIGNED, Permissions.LEADS_VIEW_TEAM, Permissions.LEADS_VIEW_COMPANY, Permissions.LEADS_MANAGE,
        Permissions.CONVERSATIONS_VIEW_ASSIGNED, Permissions.CONVERSATIONS_VIEW_TEAM, Permissions.CONVERSATIONS_VIEW_COMPANY,
        Permissions.CONVERSATIONS_VIEW_PRIVATE_NOTES, Permissions.CONVERSATIONS_SEND,
        Permissions.ANALYTICS_VIEW_PERSONAL, Permissions.ANALYTICS_VIEW_TEAM, Permissions.ANALYTICS_VIEW_COMPANY,
        Permissions.SALES_VIEW_REVENUE, Permissions.SALES_MANAGE_TARGETS,
        Permissions.TEAMS_MANAGE_ASSIGNED, Permissions.TEAMS_MANAGE_COMPANY,
        Permissions.USERS_MANAGE_COMPANY, Permissions.ROLES_MANAGE,
        Permissions.INTEGRATIONS_MANAGE_COMPANY, Permissions.AUDIT_LOGS_VIEW,
    },
    UserRole.SALES_MANAGER: {
        Permissions.CUSTOMERS_VIEW_ASSIGNED, Permissions.CUSTOMERS_VIEW_TEAM, Permissions.CUSTOMERS_VIEW_COMPANY,
        Permissions.CUSTOMERS_ASSIGN, Permissions.CUSTOMERS_REASSIGN, Permissions.CUSTOMERS_EXPORT,
        Permissions.LEADS_VIEW_ASSIGNED, Permissions.LEADS_VIEW_TEAM, Permissions.LEADS_VIEW_COMPANY, Permissions.LEADS_MANAGE,
        Permissions.CONVERSATIONS_VIEW_ASSIGNED, Permissions.CONVERSATIONS_VIEW_TEAM, Permissions.CONVERSATIONS_VIEW_COMPANY,
        Permissions.CONVERSATIONS_VIEW_PRIVATE_NOTES, Permissions.CONVERSATIONS_SEND,
        Permissions.ANALYTICS_VIEW_PERSONAL, Permissions.ANALYTICS_VIEW_TEAM, Permissions.ANALYTICS_VIEW_COMPANY,
        Permissions.SALES_VIEW_REVENUE, Permissions.SALES_MANAGE_TARGETS,
        Permissions.TEAMS_MANAGE_COMPANY,
    },
    UserRole.TEAM_LEADER: {
        Permissions.CUSTOMERS_VIEW_ASSIGNED, Permissions.CUSTOMERS_VIEW_TEAM,
        Permissions.CUSTOMERS_ASSIGN,
        Permissions.LEADS_VIEW_ASSIGNED, Permissions.LEADS_VIEW_TEAM, Permissions.LEADS_MANAGE,
        Permissions.CONVERSATIONS_VIEW_ASSIGNED, Permissions.CONVERSATIONS_VIEW_TEAM,
        Permissions.CONVERSATIONS_VIEW_PRIVATE_NOTES, Permissions.CONVERSATIONS_SEND,
        Permissions.ANALYTICS_VIEW_PERSONAL, Permissions.ANALYTICS_VIEW_TEAM,
        Permissions.TEAMS_MANAGE_ASSIGNED,
    },
    UserRole.SALES_AGENT: {
        Permissions.CUSTOMERS_VIEW_ASSIGNED,
        Permissions.LEADS_VIEW_ASSIGNED, Permissions.LEADS_MANAGE,
        Permissions.CONVERSATIONS_VIEW_ASSIGNED, Permissions.CONVERSATIONS_SEND,
        Permissions.ANALYTICS_VIEW_PERSONAL,
    },
}


def has_permission(user: User, permission: str) -> bool:
    """Checks whether the user's role grants the requested permission."""
    perms = ROLE_PERMISSIONS.get(user.role, set())
    return permission in perms


def require_permission(permission: str):
    """FastAPI Dependency to enforce a specific explicit permission."""
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: '{permission}' for role '{current_user.role.value}'"
            )
        return current_user
    return permission_checker


# -------------------------------------------------------------------------
# User Authentication & Role Validation
# -------------------------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return user


def require_roles(allowed_roles: List[UserRole]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role: {current_user.role}"
            )
        return current_user
    return role_checker


# -------------------------------------------------------------------------
# Scoped Resource Query Helpers (Backend Data Isolation)
# -------------------------------------------------------------------------

def get_scoped_lead_query(query, current_user: User):
    """
    Enforces multi-tenancy and role-based data boundaries:
    - Super Admin: sees all within company
    - Company Admin & Sales Manager: sees all company leads
    - Team Leader: sees leads assigned to their team or directly to them
    - Sales Agent: sees strictly leads assigned to them
    """
    lead_model = query.column_descriptions[0]["type"]
    query = query.filter(lead_model.company_id == current_user.company_id)
    
    if current_user.role in [UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]:
        return query
    elif current_user.role == UserRole.TEAM_LEADER:
        if current_user.team_id:
            return query.filter(
                (lead_model.team_id == current_user.team_id) | 
                (lead_model.assigned_agent_id == current_user.id)
            )
        return query.filter(lead_model.assigned_agent_id == current_user.id)
    else:  # SALES_AGENT
        return query.filter(lead_model.assigned_agent_id == current_user.id)


def get_scoped_conversation_query(query, current_user: User):
    """Enforces role & company boundaries on Conversations."""
    conv_model = query.column_descriptions[0]["type"]
    query = query.filter(conv_model.company_id == current_user.company_id)

    if current_user.role in [UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]:
        return query
    elif current_user.role == UserRole.TEAM_LEADER:
        if current_user.team_id:
            return query.filter(
                (conv_model.team_id == current_user.team_id) |
                (conv_model.assigned_agent_id == current_user.id) |
                (conv_model.assigned_agent_id == None)
            )
        return query.filter((conv_model.assigned_agent_id == current_user.id) | (conv_model.assigned_agent_id == None))
    else:  # SALES_AGENT
        return query.filter((conv_model.assigned_agent_id == current_user.id) | (conv_model.assigned_agent_id == None))


def verify_lead_access(user: User, lead: Lead, action: str = "view") -> None:
    """Verifies that the user has permission to access the specific lead."""
    if lead.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Lead not found or does not belong to user company")
    
    if user.role in [UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]:
        return

    if user.role == UserRole.TEAM_LEADER:
        if lead.team_id == user.team_id or lead.assigned_agent_id == user.id:
            return
        raise HTTPException(status_code=403, detail="Access denied: lead does not belong to your team")

    # Sales Agent
    if lead.assigned_agent_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied: lead is not assigned to you")


def verify_conversation_access(user: User, conversation: Conversation, action: str = "view") -> None:
    """Verifies that the user has permission to access the specific conversation."""
    if conversation.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Conversation not found or does not belong to user company")

    if user.role in [UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]:
        return

    if user.role == UserRole.TEAM_LEADER:
        if conversation.team_id is None or conversation.team_id == user.team_id or conversation.assigned_agent_id == user.id:
            return
        raise HTTPException(status_code=403, detail="Access denied: conversation does not belong to your team")

    # Sales Agent: allowed if assigned to agent, OR if conversation is unassigned (inbound claim)
    if conversation.assigned_agent_id is None or conversation.assigned_agent_id == user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied: conversation is not assigned to you")
