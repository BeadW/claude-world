"""Claude Code plugin package."""

from __future__ import annotations

from .hooks import (
    HookHandler,
    create_tool_start_event,
    create_tool_complete_event,
    create_session_start_event,
    create_session_end_event,
    create_agent_spawn_event,
    create_agent_complete_event,
    create_user_prompt_event,
)
from .event_bridge import EventBridge

__all__ = [
    "HookHandler",
    "EventBridge",
    "create_tool_start_event",
    "create_tool_complete_event",
    "create_session_start_event",
    "create_session_end_event",
    "create_agent_spawn_event",
    "create_agent_complete_event",
    "create_user_prompt_event",
]
