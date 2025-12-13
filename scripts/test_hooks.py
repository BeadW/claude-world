#!/usr/bin/env python3
"""Test hook client sends events correctly."""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.engine import GameEngine
from claude_world.plugin import EventBridge
from claude_world.worlds import create_tropical_island
from claude_world.types import AgentActivity


async def test_hook_client():
    """Test that hook_client.py sends events correctly."""
    print("Testing hook client integration...")

    # Create game and event bridge
    state = create_tropical_island()
    engine = GameEngine(initial_state=state)
    bridge = EventBridge()

    events_received = []

    def handle_event(event):
        print(f"  Received event: {event['type']}")
        events_received.append(event)
        engine.dispatch_claude_event(event)

    bridge.on_event = handle_event

    # Start server
    server_task = asyncio.create_task(bridge.start_server())
    await asyncio.sleep(0.5)

    print(f"Socket ready at: {bridge.socket_path}")

    # Test PreToolUse hook
    print("\n--- Testing PreToolUse hook ---")
    hook_input = json.dumps({
        "tool_name": "Read",
        "tool_input": {"file_path": "/test.py"},
        "tool_use_id": "hook-test-1",
    })

    result = subprocess.run(
        ["python3", "hooks/hook_client.py", "PreToolUse"],
        input=hook_input,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    print(f"Hook exit code: {result.returncode}")
    if result.stderr:
        print(f"Hook stderr: {result.stderr}")

    await asyncio.sleep(0.2)

    state = engine.get_state()
    print(f"Activity: {state.main_agent.activity}")

    # Test UserPromptSubmit hook
    print("\n--- Testing UserPromptSubmit hook ---")
    result = subprocess.run(
        ["python3", "hooks/hook_client.py", "UserPromptSubmit"],
        input=json.dumps({"prompt": "Hello!"}),
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    await asyncio.sleep(0.2)

    state = engine.get_state()
    print(f"Activity: {state.main_agent.activity}")

    # Cleanup
    bridge.stop()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    bridge.cleanup()

    print("\n" + "="*50)
    print(f"Total events received: {len(events_received)}")
    for evt in events_received:
        print(f"  - {evt['type']}: {evt.get('payload', {})}")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(test_hook_client())
