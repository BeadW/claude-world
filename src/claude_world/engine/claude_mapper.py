"""Maps Claude events to game events."""

from __future__ import annotations

from enum import Enum
from typing import Any

from claude_world.types import AgentActivity, TOOL_ACTIVITY_MAP, TOOL_XP_REWARDS


# Session tracking for routing events to agents
# Maps session_id -> agent_id (None means main agent)
_session_to_agent: dict[str, str | None] = {}
_main_session_id: str | None = None


def register_main_session(session_id: str) -> None:
    """Register the main session ID."""
    global _main_session_id
    _main_session_id = session_id
    _session_to_agent[session_id] = None  # None = main agent


def register_agent_session(session_id: str, agent_id: str) -> None:
    """Register a subagent session."""
    _session_to_agent[session_id] = agent_id


def unregister_agent_session(agent_id: str) -> None:
    """Unregister a subagent session."""
    # Find and remove session for this agent
    to_remove = [sid for sid, aid in _session_to_agent.items() if aid == agent_id]
    for sid in to_remove:
        del _session_to_agent[sid]


def get_agent_for_session(session_id: str) -> str | None:
    """Get the agent ID for a session (None = main agent)."""
    # If session not registered, try to infer
    if session_id not in _session_to_agent:
        # If we have a main session and this isn't it, it's probably a subagent
        if _main_session_id and session_id != _main_session_id:
            # Unknown subagent session - return a placeholder
            return f"unknown-{session_id[:8]}" if session_id else None
        return None  # Assume main agent
    return _session_to_agent[session_id]


class EffectType(Enum):
    """Types of visual effects."""

    SPARKLE = "sparkle"
    WRITE_BURST = "write_burst"
    MAGNIFY = "magnify"
    WAVE = "wave"
    BUBBLE = "bubble"
    RAIN = "rain"
    STAR = "star"


# Tool → Effect mapping
TOOL_EFFECT_MAP: dict[str, EffectType] = {
    "Read": EffectType.SPARKLE,
    "Write": EffectType.WRITE_BURST,
    "Edit": EffectType.WRITE_BURST,
    "Grep": EffectType.MAGNIFY,
    "Glob": EffectType.MAGNIFY,
    "Bash": EffectType.SPARKLE,
    "Task": EffectType.BUBBLE,
    "WebFetch": EffectType.WAVE,
    "WebSearch": EffectType.WAVE,
}


def get_tool_effect(tool_name: str) -> EffectType:
    """Get the visual effect for a tool."""
    return TOOL_EFFECT_MAP.get(tool_name, EffectType.SPARKLE)


def map_claude_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Map a Claude event to game events.

    Args:
        event: The Claude event dictionary with 'type' and 'payload' keys.

    Returns:
        A list of game event dictionaries.
    """
    event_type = event.get("type", "")
    payload = event.get("payload", {})
    game_events: list[dict[str, Any]] = []

    # Extract session_id to determine which agent this event is for
    session_id = payload.get("session_id", "")
    agent_id = get_agent_for_session(session_id) if session_id else None

    if event_type == "TOOL_START":
        tool_name = payload.get("tool_name", "")
        activity = TOOL_ACTIVITY_MAP.get(tool_name, AgentActivity.BUILDING)

        # Activity change event - include tool name for verb display
        # Include agent_id to route to correct agent
        game_events.append({
            "type": "CHANGE_ACTIVITY",
            "data": {
                "activity": activity,
                "tool_name": tool_name,
                "agent_id": agent_id,
            },
        })

        # Particle effect event
        effect = get_tool_effect(tool_name)
        game_events.append({
            "type": "SPAWN_PARTICLES",
            "data": {"effect": effect, "agent_id": agent_id},
        })

        # If it's a Task tool, also spawn an agent
        if tool_name == "Task":
            tool_input = payload.get("tool_input", {})
            agent_type = tool_input.get("subagent_type", "general-purpose")
            description = tool_input.get("description", "")
            new_agent_id = payload.get("tool_use_id", "")

            game_events.append({
                "type": "SPAWN_AGENT",
                "data": {
                    "agent_id": new_agent_id,
                    "agent_type": agent_type,
                    "description": description,
                },
            })

    elif event_type == "TOOL_COMPLETE":
        tool_name = payload.get("tool_name", "")
        xp_reward = TOOL_XP_REWARDS.get(tool_name, 1)
        token_reward = xp_reward  # Tokens match XP for now

        game_events.append({
            "type": "AWARD_RESOURCES",
            "data": {
                "xp": xp_reward,
                "tokens": token_reward,
                "tool_name": tool_name,
            },
        })

        # Return to idle after tool complete (clear tool name)
        # Include agent_id to route to correct agent
        game_events.append({
            "type": "CHANGE_ACTIVITY",
            "data": {
                "activity": AgentActivity.IDLE,
                "tool_name": None,
                "agent_id": agent_id,
            },
        })

    elif event_type == "AGENT_SPAWN":
        game_events.append({
            "type": "SPAWN_AGENT",
            "data": {
                "agent_id": payload.get("agent_id", ""),
                "agent_type": payload.get("agent_type", "general-purpose"),
                "description": payload.get("description", ""),
            },
        })

    elif event_type == "AGENT_COMPLETE":
        game_events.append({
            "type": "REMOVE_AGENT",
            "data": {
                "agent_id": payload.get("agent_id", ""),
                "success": payload.get("success", True),
            },
        })

        # Award connection resource
        game_events.append({
            "type": "AWARD_RESOURCES",
            "data": {"connections": 1},
        })

    elif event_type == "AGENT_IDLE":
        game_events.append({
            "type": "CHANGE_ACTIVITY",
            "data": {"activity": AgentActivity.IDLE},
        })

    elif event_type == "SESSION_START":
        game_events.append({
            "type": "SESSION_START",
            "data": {"source": payload.get("source", "startup")},
        })

    elif event_type == "SESSION_END":
        game_events.append({
            "type": "SESSION_END",
            "data": {},
        })

    elif event_type == "USER_PROMPT":
        # User submitted a prompt - agent starts thinking
        game_events.append({
            "type": "CHANGE_ACTIVITY",
            "data": {"activity": AgentActivity.THINKING},
        })

    elif event_type == "API_RESPONSE":
        # API response with token usage information
        usage = payload.get("usage", {})
        game_events.append({
            "type": "API_USAGE",
            "data": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
            },
        })

    return game_events
