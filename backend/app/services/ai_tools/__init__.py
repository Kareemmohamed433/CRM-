"""
NEXORA AI Structured Tool Registry Package.
Imports all tool handlers to register them with the central registry.
"""

from backend.app.services.ai_tools.registry import ai_tool_registry, ToolResult
import backend.app.services.ai_tools.customer_tools
import backend.app.services.ai_tools.task_tools
import backend.app.services.ai_tools.followup_tools
import backend.app.services.ai_tools.appointment_tools
import backend.app.services.ai_tools.inventory_tools
import backend.app.services.ai_tools.offer_tools
import backend.app.services.ai_tools.reporting_tools

__all__ = ["ai_tool_registry", "ToolResult"]
