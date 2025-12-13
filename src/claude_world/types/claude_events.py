"""Claude event types - events received from the Claude Code plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ClaudeEventType(Enum):
    """Types of events that can be received from Claude Code."""

    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    TOOL_START = "TOOL_START"
    TOOL_COMPLETE = "TOOL_COMPLETE"
    AGENT_SPAWN = "AGENT_SPAWN"
    AGENT_COMPLETE = "AGENT_COMPLETE"
    USER_PROMPT = "USER_PROMPT"
    AGENT_THINKING = "AGENT_THINKING"
    AGENT_IDLE = "AGENT_IDLE"
    NOTIFICATION = "NOTIFICATION"


@dataclass
class ClaudeEvent:
    """Base event from Claude plugin hooks."""

    type: ClaudeEventType
    timestamp: float
    session_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClaudeEvent":
        """Create a ClaudeEvent from a dictionary."""
        event_type = data.get("type", "")
        if isinstance(event_type, str):
            try:
                event_type = ClaudeEventType(event_type)
            except ValueError:
                event_type = ClaudeEventType.NOTIFICATION

        return cls(
            type=event_type,
            timestamp=data.get("timestamp", 0.0),
            session_id=data.get("session_id", ""),
            payload=data.get("payload", {}),
        )


@dataclass
class ToolEventPayload:
    """Payload for tool-related events."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    tool_response: Optional[dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolEventPayload":
        """Create from dictionary."""
        return cls(
            tool_name=data.get("tool_name", ""),
            tool_input=data.get("tool_input", {}),
            tool_use_id=data.get("tool_use_id", ""),
            tool_response=data.get("tool_response"),
        )


@dataclass
class AgentSpawnPayload:
    """Payload for agent spawn events."""

    agent_id: str
    agent_type: str
    description: str
    parent_agent_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSpawnPayload":
        """Create from dictionary."""
        return cls(
            agent_id=data.get("agent_id", ""),
            agent_type=data.get("agent_type", "general-purpose"),
            description=data.get("description", ""),
            parent_agent_id=data.get("parent_agent_id"),
        )


@dataclass
class AgentCompletePayload:
    """Payload for agent completion events."""

    agent_id: str
    success: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCompletePayload":
        """Create from dictionary."""
        return cls(
            agent_id=data.get("agent_id", ""),
            success=data.get("success", True),
        )


@dataclass
class UserPromptPayload:
    """Payload for user prompt events."""

    prompt: str
    prompt_length: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPromptPayload":
        """Create from dictionary."""
        prompt = data.get("prompt", "")
        return cls(
            prompt=prompt,
            prompt_length=data.get("prompt_length", len(prompt)),
        )
