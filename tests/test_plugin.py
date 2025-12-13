"""Tests for Claude Code plugin (TDD tests written first)."""

from __future__ import annotations

import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from claude_world.plugin.hooks import (
    HookHandler,
    create_tool_start_event,
    create_tool_complete_event,
    create_session_start_event,
    create_session_end_event,
    create_agent_spawn_event,
    create_agent_complete_event,
    create_user_prompt_event,
)
from claude_world.plugin.event_bridge import EventBridge


class TestHookEventCreation:
    """Tests for creating hook events."""

    def test_create_tool_start_event(self):
        """Test creating TOOL_START event."""
        event = create_tool_start_event(
            tool_name="Read",
            tool_input={"file_path": "/test/file.py"},
            tool_use_id="tool-123",
        )
        assert event["type"] == "TOOL_START"
        assert event["payload"]["tool_name"] == "Read"
        assert event["payload"]["tool_input"]["file_path"] == "/test/file.py"
        assert event["payload"]["tool_use_id"] == "tool-123"

    def test_create_tool_complete_event(self):
        """Test creating TOOL_COMPLETE event."""
        event = create_tool_complete_event(
            tool_name="Write",
            tool_response={"success": True},
        )
        assert event["type"] == "TOOL_COMPLETE"
        assert event["payload"]["tool_name"] == "Write"
        assert event["payload"]["tool_response"]["success"] is True

    def test_create_session_start_event(self):
        """Test creating SESSION_START event."""
        event = create_session_start_event(source="startup")
        assert event["type"] == "SESSION_START"
        assert event["payload"]["source"] == "startup"

    def test_create_session_end_event(self):
        """Test creating SESSION_END event."""
        event = create_session_end_event()
        assert event["type"] == "SESSION_END"

    def test_create_agent_spawn_event(self):
        """Test creating AGENT_SPAWN event."""
        event = create_agent_spawn_event(
            agent_id="agent-1",
            agent_type="Explore",
            description="Exploring codebase",
        )
        assert event["type"] == "AGENT_SPAWN"
        assert event["payload"]["agent_id"] == "agent-1"
        assert event["payload"]["agent_type"] == "Explore"
        assert event["payload"]["description"] == "Exploring codebase"

    def test_create_agent_complete_event(self):
        """Test creating AGENT_COMPLETE event."""
        event = create_agent_complete_event(
            agent_id="agent-1",
            success=True,
        )
        assert event["type"] == "AGENT_COMPLETE"
        assert event["payload"]["agent_id"] == "agent-1"
        assert event["payload"]["success"] is True

    def test_create_user_prompt_event(self):
        """Test creating USER_PROMPT event."""
        event = create_user_prompt_event(prompt="Hello Claude")
        assert event["type"] == "USER_PROMPT"
        assert event["payload"]["prompt"] == "Hello Claude"


class TestHookHandler:
    """Tests for hook handler."""

    def test_hook_handler_creates(self):
        """Test hook handler can be created."""
        handler = HookHandler()
        assert handler is not None

    def test_handle_pre_tool_use(self):
        """Test handling PreToolUse hook."""
        handler = HookHandler()
        events = handler.handle_pre_tool_use(
            tool_name="Read",
            tool_input={"file_path": "/test.py"},
            tool_use_id="123",
        )
        assert len(events) == 1
        assert events[0]["type"] == "TOOL_START"

    def test_handle_post_tool_use(self):
        """Test handling PostToolUse hook."""
        handler = HookHandler()
        events = handler.handle_post_tool_use(
            tool_name="Write",
            tool_response="File written",
        )
        assert len(events) == 1
        assert events[0]["type"] == "TOOL_COMPLETE"

    def test_handle_session_start(self):
        """Test handling SessionStart hook."""
        handler = HookHandler()
        events = handler.handle_session_start(source="resume")
        assert len(events) == 1
        assert events[0]["type"] == "SESSION_START"

    def test_handle_stop(self):
        """Test handling Stop hook."""
        handler = HookHandler()
        events = handler.handle_stop()
        assert len(events) == 1
        assert events[0]["type"] == "SESSION_END"

    def test_handle_task_spawn(self):
        """Test handling Task tool for subagent spawn."""
        handler = HookHandler()
        events = handler.handle_pre_tool_use(
            tool_name="Task",
            tool_input={
                "subagent_type": "Explore",
                "description": "Test task",
            },
            tool_use_id="agent-123",
        )
        # Should have both TOOL_START and AGENT_SPAWN
        event_types = [e["type"] for e in events]
        assert "TOOL_START" in event_types

    def test_handle_user_prompt_submit(self):
        """Test handling user prompt submit hook."""
        handler = HookHandler()
        events = handler.handle_user_prompt("What is Python?")
        assert len(events) == 1
        assert events[0]["type"] == "USER_PROMPT"


class TestEventBridge:
    """Tests for event bridge (IPC)."""

    def test_event_bridge_creates(self):
        """Test event bridge can be created."""
        bridge = EventBridge()
        assert bridge is not None

    def test_event_bridge_has_socket_path(self):
        """Test event bridge has socket path."""
        bridge = EventBridge()
        assert bridge.socket_path is not None
        assert "claude_world" in str(bridge.socket_path)

    def test_serialize_event(self):
        """Test event serialization."""
        bridge = EventBridge()
        event = {"type": "TEST", "payload": {"key": "value"}}
        serialized = bridge.serialize_event(event)
        assert isinstance(serialized, bytes)
        # Should be valid JSON
        parsed = json.loads(serialized.decode())
        assert parsed["type"] == "TEST"

    def test_deserialize_event(self):
        """Test event deserialization."""
        bridge = EventBridge()
        data = b'{"type": "TEST", "payload": {"key": "value"}}'
        event = bridge.deserialize_event(data)
        assert event["type"] == "TEST"
        assert event["payload"]["key"] == "value"

    def test_queue_event(self):
        """Test queuing events."""
        bridge = EventBridge()
        event = {"type": "TEST", "payload": {}}
        bridge.queue_event(event)
        assert len(bridge.event_queue) == 1

    def test_get_queued_events(self):
        """Test getting queued events."""
        bridge = EventBridge()
        bridge.queue_event({"type": "EVENT1", "payload": {}})
        bridge.queue_event({"type": "EVENT2", "payload": {}})
        events = bridge.get_queued_events()
        assert len(events) == 2
        # Queue should be empty after getting
        assert len(bridge.event_queue) == 0


@pytest.mark.asyncio
class TestEventBridgeAsync:
    """Async tests for event bridge."""

    async def test_start_server(self):
        """Test starting event bridge server."""
        bridge = EventBridge()
        # Start server in background
        server_task = asyncio.create_task(bridge.start_server())

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Stop server
        bridge.stop()
        await asyncio.sleep(0.1)

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    async def test_send_event(self):
        """Test sending event through bridge."""
        bridge = EventBridge()
        received_events = []

        async def mock_handler(event):
            received_events.append(event)

        bridge.on_event = mock_handler

        # Queue and process an event
        event = {"type": "TEST", "payload": {"data": 123}}
        bridge.queue_event(event)
        await bridge.process_queued_events()

        assert len(received_events) == 1
        assert received_events[0]["type"] == "TEST"
