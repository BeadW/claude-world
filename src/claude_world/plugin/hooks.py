"""Hook handlers for Claude Code events."""

from __future__ import annotations

import time
from typing import Any


def create_tool_start_event(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_use_id: str,
) -> dict[str, Any]:
    """Create a TOOL_START event.

    Args:
        tool_name: Name of the tool being used.
        tool_input: Input parameters for the tool.
        tool_use_id: Unique identifier for this tool use.

    Returns:
        Event dictionary.
    """
    return {
        "type": "TOOL_START",
        "timestamp": time.time(),
        "payload": {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_use_id": tool_use_id,
        },
    }


def create_tool_complete_event(
    tool_name: str,
    tool_response: Any,
) -> dict[str, Any]:
    """Create a TOOL_COMPLETE event.

    Args:
        tool_name: Name of the completed tool.
        tool_response: Response from the tool.

    Returns:
        Event dictionary.
    """
    return {
        "type": "TOOL_COMPLETE",
        "timestamp": time.time(),
        "payload": {
            "tool_name": tool_name,
            "tool_response": tool_response,
        },
    }


def create_session_start_event(source: str = "startup") -> dict[str, Any]:
    """Create a SESSION_START event.

    Args:
        source: Source of session start (startup, resume, etc.)

    Returns:
        Event dictionary.
    """
    return {
        "type": "SESSION_START",
        "timestamp": time.time(),
        "payload": {
            "source": source,
        },
    }


def create_session_end_event() -> dict[str, Any]:
    """Create a SESSION_END event.

    Returns:
        Event dictionary.
    """
    return {
        "type": "SESSION_END",
        "timestamp": time.time(),
        "payload": {},
    }


def create_agent_spawn_event(
    agent_id: str,
    agent_type: str,
    description: str,
) -> dict[str, Any]:
    """Create an AGENT_SPAWN event.

    Args:
        agent_id: Unique identifier for the agent.
        agent_type: Type of agent (Explore, Plan, etc.)
        description: Description of what the agent is doing.

    Returns:
        Event dictionary.
    """
    return {
        "type": "AGENT_SPAWN",
        "timestamp": time.time(),
        "payload": {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "description": description,
        },
    }


def create_agent_complete_event(
    agent_id: str,
    success: bool,
) -> dict[str, Any]:
    """Create an AGENT_COMPLETE event.

    Args:
        agent_id: Unique identifier for the agent.
        success: Whether the agent completed successfully.

    Returns:
        Event dictionary.
    """
    return {
        "type": "AGENT_COMPLETE",
        "timestamp": time.time(),
        "payload": {
            "agent_id": agent_id,
            "success": success,
        },
    }


def create_user_prompt_event(prompt: str) -> dict[str, Any]:
    """Create a USER_PROMPT event.

    Args:
        prompt: The user's prompt text.

    Returns:
        Event dictionary.
    """
    return {
        "type": "USER_PROMPT",
        "timestamp": time.time(),
        "payload": {
            "prompt": prompt,
        },
    }


class HookHandler:
    """Handles Claude Code hooks and converts them to game events."""

    def __init__(self):
        """Initialize the hook handler."""
        self._active_tools: dict[str, dict] = {}
        self._active_agents: dict[str, dict] = {}

    def handle_pre_tool_use(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_use_id: str,
    ) -> list[dict[str, Any]]:
        """Handle PreToolUse hook.

        Args:
            tool_name: Name of the tool.
            tool_input: Tool input parameters.
            tool_use_id: Unique tool use ID.

        Returns:
            List of events to dispatch.
        """
        events: list[dict[str, Any]] = []

        # Track active tool
        self._active_tools[tool_use_id] = {
            "tool_name": tool_name,
            "start_time": time.time(),
        }

        # Create tool start event
        events.append(create_tool_start_event(tool_name, tool_input, tool_use_id))

        return events

    def handle_post_tool_use(
        self,
        tool_name: str,
        tool_response: Any,
        tool_use_id: str = "",
    ) -> list[dict[str, Any]]:
        """Handle PostToolUse hook.

        Args:
            tool_name: Name of the tool.
            tool_response: Tool response.
            tool_use_id: Unique tool use ID.

        Returns:
            List of events to dispatch.
        """
        events: list[dict[str, Any]] = []

        # Remove from active tools
        if tool_use_id in self._active_tools:
            del self._active_tools[tool_use_id]

        # Create tool complete event
        events.append(create_tool_complete_event(tool_name, tool_response))

        return events

    def handle_session_start(self, source: str = "startup") -> list[dict[str, Any]]:
        """Handle SessionStart hook.

        Args:
            source: Source of session start.

        Returns:
            List of events to dispatch.
        """
        return [create_session_start_event(source)]

    def handle_stop(self) -> list[dict[str, Any]]:
        """Handle Stop hook.

        Returns:
            List of events to dispatch.
        """
        events: list[dict[str, Any]] = []

        # Complete any active agents
        for agent_id in list(self._active_agents.keys()):
            events.append(create_agent_complete_event(agent_id, success=False))
            del self._active_agents[agent_id]

        # End session
        events.append(create_session_end_event())

        return events

    def handle_subagent_spawn(
        self,
        agent_id: str,
        agent_type: str,
        description: str,
    ) -> list[dict[str, Any]]:
        """Handle subagent spawn.

        Args:
            agent_id: Unique agent ID.
            agent_type: Type of agent.
            description: Agent description.

        Returns:
            List of events to dispatch.
        """
        self._active_agents[agent_id] = {
            "agent_type": agent_type,
            "start_time": time.time(),
        }

        return [create_agent_spawn_event(agent_id, agent_type, description)]

    def handle_subagent_stop(
        self,
        agent_id: str,
        success: bool = True,
    ) -> list[dict[str, Any]]:
        """Handle SubagentStop hook.

        Args:
            agent_id: Unique agent ID.
            success: Whether agent completed successfully.

        Returns:
            List of events to dispatch.
        """
        if agent_id in self._active_agents:
            del self._active_agents[agent_id]

        return [create_agent_complete_event(agent_id, success)]

    def handle_user_prompt(self, prompt: str) -> list[dict[str, Any]]:
        """Handle user prompt submission.

        Args:
            prompt: The user's prompt.

        Returns:
            List of events to dispatch.
        """
        return [create_user_prompt_event(prompt)]
