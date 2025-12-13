#!/usr/bin/env python3
"""Test the full socket communication for events."""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.engine import GameEngine
from claude_world.plugin import EventBridge
from claude_world.worlds import create_tropical_island
from claude_world.types import AgentActivity


async def send_event_to_socket(socket_path: Path, event: dict) -> bool:
    """Send an event to the socket."""
    try:
        reader, writer = await asyncio.open_unix_connection(path=str(socket_path))
        data = json.dumps(event).encode("utf-8")
        writer.write(len(data).to_bytes(4, "big"))
        writer.write(data)
        await writer.drain()
        response = await reader.read(2)
        writer.close()
        await writer.wait_closed()
        return response == b"OK"
    except Exception as e:
        print(f"Error sending event: {e}")
        return False


async def test_socket_events():
    """Test events sent via socket update game state."""
    print("Testing socket event integration...")

    # Create game and event bridge
    state = create_tropical_island()
    engine = GameEngine(initial_state=state)
    bridge = EventBridge()

    events_received = []

    def handle_event(event):
        events_received.append(event)
        engine.dispatch_claude_event(event)

    bridge.on_event = handle_event

    # Start server
    server_task = asyncio.create_task(bridge.start_server())
    await asyncio.sleep(0.5)  # Let server start

    print(f"Socket path: {bridge.socket_path}")
    print(f"Socket exists: {bridge.socket_path.exists()}")

    # Send TOOL_START event via socket
    print("\n--- Sending TOOL_START via socket ---")
    success = await send_event_to_socket(bridge.socket_path, {
        "type": "TOOL_START",
        "timestamp": time.time(),
        "payload": {
            "tool_name": "Write",
            "tool_input": {"file_path": "/test.py"},
            "tool_use_id": "socket-test-1",
        },
    })
    print(f"Send success: {success}")
    await asyncio.sleep(0.1)

    state = engine.get_state()
    print(f"Activity after socket event: {state.main_agent.activity}")
    print(f"Events received: {len(events_received)}")

    if state.main_agent.activity == AgentActivity.WRITING:
        print("✓ Socket event successfully updated game state!")
    else:
        print(f"✗ Expected WRITING, got {state.main_agent.activity}")

    # Cleanup
    bridge.stop()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    bridge.cleanup()

    print("\n" + "="*50)
    if events_received:
        print("Socket integration is working!")
    else:
        print("No events received - check socket connection")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(test_socket_events())
