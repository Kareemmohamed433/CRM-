"""
Structured Tool Registry for NEXORA AI CRM Assistant.
Handles registration, role checking, input validation, execution, and response formatting.
"""

import logging
from typing import Callable, Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.models.models import User, UserRole

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: str = ""
    error: Optional[str] = None


class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        parameters_schema: Dict[str, Any],
        handler: Callable,
        required_roles: Optional[List[UserRole]] = None
    ):
        self.name = name
        self.description = description
        self.category = category
        self.parameters_schema = parameters_schema
        self.handler = handler
        self.required_roles = required_roles

    def is_authorized(self, user: User) -> bool:
        if not self.required_roles:
            return True
        return user.role in self.required_roles


class AIToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        category: str,
        parameters_schema: Optional[Dict[str, Any]] = None,
        required_roles: Optional[List[UserRole]] = None
    ):
        def decorator(fn: Callable):
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                category=category,
                parameters_schema=parameters_schema or {},
                handler=fn,
                required_roles=required_roles
            )
            return fn
        return decorator

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None, user: Optional[User] = None) -> List[Dict[str, Any]]:
        result = []
        for tool in self._tools.values():
            if category and tool.category != category:
                continue
            if user and not tool.is_authorized(user):
                continue
            result.append({
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "parameters": tool.parameters_schema
            })
        return result

    def get_groq_tools_schema(self, user: Optional[User] = None) -> List[Dict[str, Any]]:
        """Returns tool schema formatted for Groq / OpenAI function calling."""
        schema = []
        for tool in self._tools.values():
            if user and not tool.is_authorized(user):
                continue
            schema.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters_schema.get("properties", {}),
                        "required": tool.parameters_schema.get("required", [])
                    }
                }
            })
        return schema

    def execute(
        self,
        tool_name: str,
        db: Session,
        user: User,
        params: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"[ToolRegistry] Tool not found: '{tool_name}'")
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' is not recognized.",
                message=f"الأداة المطلوبة غير مسجلة في النظام: {tool_name}"
            )

        if not tool.is_authorized(user):
            logger.warning(f"[ToolRegistry] Unauthorized tool execution: '{tool_name}' by user {user.id} ({user.role})")
            return ToolResult(
                success=False,
                error=f"User role {user.role} is not authorized to execute '{tool_name}'.",
                message="عذرًا، صلاحيات حسابك لا تسمح بتنفيذ هذه العملية."
            )

        p = params or {}
        try:
            logger.info(f"[ToolRegistry] Executing tool '{tool_name}' for user {user.email}")
            return tool.handler(db, user, p)
        except Exception as e:
            logger.exception(f"[ToolRegistry] Error executing tool '{tool_name}': {e}")
            return ToolResult(
                success=False,
                error=str(e),
                message=f"حدث خطأ أثناء تنفيذ العملية: {str(e)}"
            )


    execute_tool = execute


ai_tool_registry = AIToolRegistry()

