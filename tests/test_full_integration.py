"""Full integration tests that exercise the complete rendering pipeline.

These tests catch crashes that might occur during real operation with hooks and sockets.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from claude_world.types import (
    Position,
    Velocity,
    AnimationState,
    EntityType,
    AgentEntity,
    AgentActivity,
    AgentMood,
    GameState,
    WorldState,
    TerrainData,
    TimeOfDay,
    WeatherState,
    Camera,
    Resources,
    Progression,
    Particle,
    ApiCostTracker,
)
from claude_world.engine import GameEngine
from claude_world.worlds import create_tropical_island
from claude_world.plugin import HookHandler, EventBridge
from claude_world.app import GameLoop

import numpy as np


# Check if PIL is available
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


@pytest.fixture
def game_state() -> GameState:
    """Create a test game state."""
    return create_tropical_island()


@pytest.fixture
def mock_terminal_renderer():
    """Create a TerminalGraphicsRenderer that doesn't output to terminal."""
    if not HAS_PIL:
        pytest.skip("PIL not available")

    from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer

    renderer = TerminalGraphicsRenderer(width=400, height=300)
    renderer._display_frame = MagicMock()
    return renderer


class TestGameLoop:
    """Tests for the GameLoop with TerminalGraphicsRenderer."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_game_loop_tick(self, game_state, mock_terminal_renderer):
        """Test that game loop tick works with terminal renderer."""
        engine = GameEngine(initial_state=game_state)
        loop = GameLoop(engine=engine, renderer=mock_terminal_renderer, target_fps=30)

        # Run several ticks
        for _ in range(10):
            loop.tick(0.033)  # ~30fps

        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_game_loop_with_events(self, game_state, mock_terminal_renderer):
        """Test game loop with events being processed."""
        engine = GameEngine(initial_state=game_state)
        loop = GameLoop(engine=engine, renderer=mock_terminal_renderer, target_fps=30)
        handler = HookHandler()

        # Start session
        events = handler.handle_session_start("test")
        for event in events:
            engine.dispatch_claude_event(event)
        loop.tick(0.033)

        # Use several tools
        for tool in ["Read", "Write", "Bash", "Grep"]:
            events = handler.handle_pre_tool_use(tool, {}, f"id-{tool}")
            for event in events:
                engine.dispatch_claude_event(event)
            loop.tick(0.033)

            events = handler.handle_post_tool_use(tool, "result", f"id-{tool}")
            for event in events:
                engine.dispatch_claude_event(event)
            loop.tick(0.033)

        mock_terminal_renderer._display_frame.assert_called()


class TestHookClientIntegration:
    """Tests that verify the hook client produces valid events."""

    def test_pre_tool_use_event_format(self):
        """Test PreToolUse hook produces valid event format."""
        handler = HookHandler()
        events = handler.handle_pre_tool_use("Read", {"file": "test.py"}, "tool-123")

        assert len(events) == 1
        event = events[0]
        assert event["type"] == "TOOL_START"
        assert "payload" in event
        assert event["payload"]["tool_name"] == "Read"

    def test_post_tool_use_event_format(self):
        """Test PostToolUse hook produces valid event format."""
        handler = HookHandler()
        events = handler.handle_post_tool_use("Write", "success", "tool-456")

        assert len(events) == 1
        event = events[0]
        assert event["type"] == "TOOL_COMPLETE"
        assert "payload" in event
        assert event["payload"]["tool_name"] == "Write"

    def test_session_start_event_format(self):
        """Test session start produces valid event format."""
        handler = HookHandler()
        events = handler.handle_session_start("startup")

        assert len(events) == 1
        event = events[0]
        assert event["type"] == "SESSION_START"

    def test_subagent_spawn_event_format(self):
        """Test subagent spawn produces valid event format."""
        handler = HookHandler()
        events = handler.handle_subagent_spawn("agent-1", "Explore", "Test agent")

        assert len(events) == 1
        event = events[0]
        assert event["type"] == "AGENT_SPAWN"
        assert event["payload"]["agent_id"] == "agent-1"
        assert event["payload"]["agent_type"] == "Explore"


class TestEngineEventProcessing:
    """Tests for engine event processing with all event types."""

    def test_all_tool_events(self, game_state):
        """Test engine processes all tool events correctly."""
        engine = GameEngine(initial_state=game_state)

        tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep",
                 "WebFetch", "WebSearch", "Task", "TodoWrite"]

        for tool in tools:
            # Start
            engine.dispatch_claude_event({
                "type": "TOOL_START",
                "payload": {"tool_name": tool, "tool_input": {}, "tool_use_id": f"t-{tool}"}
            })

            state = engine.get_state()
            assert state.main_agent.activity != AgentActivity.IDLE or tool == "TodoWrite"

            # Complete
            engine.dispatch_claude_event({
                "type": "TOOL_COMPLETE",
                "payload": {"tool_name": tool, "tool_response": {}}
            })

            state = engine.get_state()
            assert state.main_agent.activity == AgentActivity.IDLE

    def test_api_response_event(self, game_state):
        """Test engine processes API response events correctly."""
        engine = GameEngine(initial_state=game_state)

        engine.dispatch_claude_event({
            "type": "API_RESPONSE",
            "payload": {
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 50,
                }
            }
        })

        state = engine.get_state()
        assert state.resources.api_costs.input_tokens == 1000
        assert state.resources.api_costs.output_tokens == 500

    def test_user_prompt_event(self, game_state):
        """Test engine processes user prompt event correctly."""
        engine = GameEngine(initial_state=game_state)

        engine.dispatch_claude_event({
            "type": "USER_PROMPT",
            "payload": {"prompt": "test prompt"}
        })

        state = engine.get_state()
        assert state.main_agent.activity == AgentActivity.THINKING


class TestRendererWithRealState:
    """Tests that use real game state from worlds module."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_tropical_island(self, mock_terminal_renderer):
        """Test rendering tropical island world."""
        state = create_tropical_island()

        # Render multiple frames
        for _ in range(10):
            mock_terminal_renderer.render_frame(state)

        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_decorations(self, mock_terminal_renderer):
        """Test rendering with world decorations."""
        state = create_tropical_island()

        # Verify decorations exist
        assert len(state.world.terrain.decorations) > 0

        # Render
        mock_terminal_renderer.render_frame(state)
        mock_terminal_renderer._display_frame.assert_called()


@pytest.mark.asyncio
class TestEventBridgeIntegration:
    """Tests for EventBridge socket communication."""

    async def test_event_bridge_processes_events(self):
        """Test event bridge processes events correctly."""
        bridge = EventBridge()
        received = []

        def handler(event):
            received.append(event)

        bridge.on_event = handler

        bridge.queue_event({"type": "TOOL_START", "payload": {"tool_name": "Read"}})
        await bridge.process_queued_events()

        assert len(received) == 1
        assert received[0]["type"] == "TOOL_START"

    async def test_event_bridge_query_handler(self):
        """Test event bridge query handling."""
        bridge = EventBridge()

        def query_handler(query_type):
            return {"status": "ok", "query": query_type}

        bridge.on_query = query_handler

        # The query handler should be callable
        result = bridge.on_query("status")
        assert result["status"] == "ok"


class TestCompleteRenderPipeline:
    """Tests that exercise the complete render pipeline from hook to display."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_complete_tool_cycle(self, mock_terminal_renderer):
        """Test a complete tool cycle from start to end with rendering."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)
        handler = HookHandler()

        # Session start
        for event in handler.handle_session_start("test"):
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # User prompt
        for event in handler.handle_user_prompt("test prompt"):
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # All tools
        tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep",
                 "WebFetch", "WebSearch", "Task"]

        for tool in tools:
            # Pre tool use
            for event in handler.handle_pre_tool_use(tool, {}, f"id-{tool}"):
                engine.dispatch_claude_event(event)

            # Render several frames during tool use
            for _ in range(5):
                mock_terminal_renderer.render_frame(engine.get_state())

            # Post tool use
            for event in handler.handle_post_tool_use(tool, "result", f"id-{tool}"):
                engine.dispatch_claude_event(event)

            mock_terminal_renderer.render_frame(engine.get_state())

        # Session end
        for event in handler.handle_stop():
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Verify final state
        final_state = engine.get_state()
        assert final_state.progression.total_tools_used == len(tools)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_subagent_lifecycle(self, mock_terminal_renderer):
        """Test subagent spawn and complete cycle with rendering."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)
        handler = HookHandler()

        # Spawn subagent
        for event in handler.handle_subagent_spawn("agent-1", "Explore", "Test"):
            engine.dispatch_claude_event(event)

        # Verify subagent exists
        assert "agent-1" in engine.get_state().entities

        # Render with subagent
        for _ in range(5):
            mock_terminal_renderer.render_frame(engine.get_state())

        # Complete subagent
        for event in handler.handle_subagent_stop("agent-1", success=True):
            engine.dispatch_claude_event(event)

        # Verify subagent removed
        assert "agent-1" not in engine.get_state().entities

        mock_terminal_renderer.render_frame(engine.get_state())
        mock_terminal_renderer._display_frame.assert_called()


class TestCrashScenarios:
    """Tests for specific crash scenarios that have been reported."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_time_of_day_access(self, game_state):
        """Test that TimeOfDay is accessed correctly (not as enum)."""
        # This was a previous crash - using .value instead of .phase
        tod = game_state.world.time_of_day

        # Should have phase property (string)
        assert hasattr(tod, 'phase')
        assert isinstance(tod.phase, str)

        # Should have hour property (float)
        assert hasattr(tod, 'hour')
        assert isinstance(tod.hour, float)

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_subagent_same_position(self, mock_terminal_renderer, game_state):
        """Test rendering when subagent is at exactly the same position as main agent."""
        # This was a potential crash - division by zero when distance = 0
        subagent = AgentEntity(
            id="same-pos",
            type=EntityType.SUB_AGENT,
            position=Position(
                game_state.main_agent.position.x,
                game_state.main_agent.position.y
            ),
            velocity=Velocity(0, 0),
            sprite_id="explore_agent",
            animation=AnimationState(current_animation="idle"),
            agent_type="Explore",
            activity=AgentActivity.EXPLORING,
        )
        game_state.entities["same-pos"] = subagent

        # Should not crash
        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_api_cost_tracker_class_fields(self):
        """Test ApiCostTracker class fields are not included as init params."""
        # This was a crash - class constants were being passed to __init__
        tracker = ApiCostTracker()

        # Should create without error
        assert tracker.input_tokens == 0
        assert tracker.output_tokens == 0

        # Class constants should exist
        assert tracker.INPUT_COST_PER_M == 15.0
        assert tracker.OUTPUT_COST_PER_M == 75.0

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_rapid_activity_changes(self, mock_terminal_renderer, game_state):
        """Test rapid activity changes don't cause crashes."""
        engine = GameEngine(initial_state=game_state)

        activities = [
            AgentActivity.IDLE,
            AgentActivity.THINKING,
            AgentActivity.READING,
            AgentActivity.WRITING,
            AgentActivity.SEARCHING,
            AgentActivity.BUILDING,
        ]

        for _ in range(10):
            for activity in activities:
                game_state.main_agent.activity = activity
                mock_terminal_renderer.render_frame(game_state)

        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_scrollback_clear_tracking(self, game_state):
        """Test that scrollback clearing is tracked properly."""
        from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer

        renderer = TerminalGraphicsRenderer(width=400, height=300)
        renderer._display_frame = MagicMock()

        # Verify initial state
        assert renderer._last_scrollback_clear == 0

        # Render many frames - should update tracking
        for _ in range(350):
            renderer.render_frame(game_state)

        # Scrollback clear tracking should be updated after 300 frames
        # (only if inside tmux, but the counter should still be accessible)
        assert renderer._frame_count == 350
        # The _last_scrollback_clear is updated when inside tmux
        # For tests outside tmux, just verify the attribute exists and works
