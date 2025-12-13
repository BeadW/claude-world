#!/usr/bin/env python3
"""Test script to verify events trigger game animations."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.engine import GameEngine
from claude_world.worlds import create_tropical_island
from claude_world.types import AgentActivity


def test_event_handling():
    """Test that events properly update game state."""
    print("Testing event handling...")

    # Create game
    state = create_tropical_island()
    engine = GameEngine(initial_state=state)

    print(f"Initial activity: {state.main_agent.activity}")
    print(f"Initial animation: {state.main_agent.animation.current_animation}")

    # Test TOOL_START event (should change to READING activity)
    print("\n--- Sending TOOL_START (Read) event ---")
    engine.dispatch_claude_event({
        "type": "TOOL_START",
        "timestamp": time.time(),
        "payload": {
            "tool_name": "Read",
            "tool_input": {"file_path": "/test.py"},
            "tool_use_id": "test-123",
        },
    })

    state = engine.get_state()
    print(f"After TOOL_START: activity={state.main_agent.activity}, animation={state.main_agent.animation.current_animation}")
    assert state.main_agent.activity == AgentActivity.READING, f"Expected READING, got {state.main_agent.activity}"
    print("✓ Activity changed to READING")

    # Test TOOL_COMPLETE event (should return to IDLE and award XP)
    print("\n--- Sending TOOL_COMPLETE event ---")
    initial_xp = state.progression.experience
    engine.dispatch_claude_event({
        "type": "TOOL_COMPLETE",
        "timestamp": time.time(),
        "payload": {
            "tool_name": "Read",
            "tool_response": "file contents...",
        },
    })

    state = engine.get_state()
    print(f"After TOOL_COMPLETE: activity={state.main_agent.activity}, xp={state.progression.experience}")
    assert state.main_agent.activity == AgentActivity.IDLE, f"Expected IDLE, got {state.main_agent.activity}"
    assert state.progression.experience > initial_xp, "XP should have increased"
    print("✓ Activity returned to IDLE and XP awarded")

    # Test USER_PROMPT event (should change to THINKING)
    print("\n--- Sending USER_PROMPT event ---")
    engine.dispatch_claude_event({
        "type": "USER_PROMPT",
        "timestamp": time.time(),
        "payload": {
            "prompt": "Hello!",
        },
    })

    state = engine.get_state()
    print(f"After USER_PROMPT: activity={state.main_agent.activity}, animation={state.main_agent.animation.current_animation}")
    assert state.main_agent.activity == AgentActivity.THINKING, f"Expected THINKING, got {state.main_agent.activity}"
    print("✓ Activity changed to THINKING")

    # Test AGENT_SPAWN event (should spawn a subagent)
    print("\n--- Sending AGENT_SPAWN event ---")
    initial_agents = state.progression.total_subagents_spawned
    engine.dispatch_claude_event({
        "type": "AGENT_SPAWN",
        "timestamp": time.time(),
        "payload": {
            "agent_id": "agent-test-1",
            "agent_type": "Explore",
            "description": "Test agent",
        },
    })

    state = engine.get_state()
    print(f"After AGENT_SPAWN: total_agents={state.progression.total_subagents_spawned}")
    assert state.progression.total_subagents_spawned > initial_agents, "Agent count should have increased"
    print("✓ Subagent spawned")

    print("\n" + "="*50)
    print("All tests passed! Event handling is working correctly.")
    print("="*50)


if __name__ == "__main__":
    test_event_handling()
