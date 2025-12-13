"""Integration tests for Claude World."""

from __future__ import annotations

import asyncio
import pytest

from claude_world.app import Application
from claude_world.engine import GameEngine
from claude_world.plugin import HookHandler, EventBridge
from claude_world.renderer.headless import HeadlessRenderer
from claude_world.worlds import create_tropical_island, WorldLoader
from claude_world.assets import create_all_sprites
from claude_world.types import AgentActivity


class TestFullGameFlow:
    """Integration tests for complete game flow."""

    def test_create_world_and_engine(self):
        """Test creating world and initializing engine."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)
        assert engine.get_state().world.name == "tropical-island"

    def test_engine_processes_tool_events(self):
        """Test engine processing a sequence of tool events."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)

        # Simulate a Read tool event
        engine.dispatch_claude_event({
            "type": "TOOL_START",
            "payload": {"tool_name": "Read", "tool_input": {}, "tool_use_id": "1"},
        })
        assert engine.get_state().main_agent.activity == AgentActivity.READING

        # Complete the tool
        engine.dispatch_claude_event({
            "type": "TOOL_COMPLETE",
            "payload": {"tool_name": "Read", "tool_response": {}},
        })
        assert engine.get_state().main_agent.activity == AgentActivity.IDLE
        assert engine.get_state().progression.experience > 0

    def test_engine_spawns_subagents(self):
        """Test engine spawning subagents from Task events."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)

        # Spawn an agent
        engine.dispatch_claude_event({
            "type": "AGENT_SPAWN",
            "payload": {
                "agent_id": "test-agent-1",
                "agent_type": "Explore",
                "description": "Testing",
            },
        })
        assert "test-agent-1" in engine.get_state().entities

        # Complete the agent
        engine.dispatch_claude_event({
            "type": "AGENT_COMPLETE",
            "payload": {"agent_id": "test-agent-1", "success": True},
        })
        assert "test-agent-1" not in engine.get_state().entities

    def test_renderer_renders_game_state(self):
        """Test renderer can render game state."""
        state = create_tropical_island()
        renderer = HeadlessRenderer(width=80, height=24)

        renderer.render_frame(state)

        assert renderer.last_render_time > 0
        assert "main_agent" in renderer.rendered_entities

    def test_hook_handler_creates_events(self):
        """Test hook handler creates proper events."""
        handler = HookHandler()

        # PreToolUse hook
        events = handler.handle_pre_tool_use("Write", {"path": "/test.py"}, "tool-1")
        assert len(events) == 1
        assert events[0]["type"] == "TOOL_START"

        # PostToolUse hook
        events = handler.handle_post_tool_use("Write", "Success")
        assert len(events) == 1
        assert events[0]["type"] == "TOOL_COMPLETE"

    def test_world_loader_loads_worlds(self):
        """Test world loader can load worlds."""
        loader = WorldLoader()
        state = loader.load("tropical-island")

        assert state is not None
        assert state.world.name == "tropical-island"
        assert state.main_agent is not None

    def test_sprites_are_created(self):
        """Test all sprites can be created."""
        sprites = create_all_sprites()

        assert "claude_main" in sprites
        assert "explore_agent" in sprites
        assert "palm_tree" in sprites

        # Check sprites have animations
        claude = sprites["claude_main"]
        assert "idle" in claude.animations
        assert "thinking" in claude.animations


@pytest.mark.asyncio
class TestAsyncIntegration:
    """Async integration tests."""

    async def test_application_initializes(self):
        """Test application initializes all components."""
        app = Application(headless=True)
        await app.initialize()

        assert app.engine is not None
        assert app.renderer is not None
        assert app.event_bridge is not None
        assert app.game_loop is not None

        await app.shutdown()

    async def test_event_bridge_queues_events(self):
        """Test event bridge can queue and process events."""
        bridge = EventBridge()
        received = []

        async def handler(event):
            received.append(event)

        bridge.on_event = handler

        bridge.queue_event({"type": "TEST", "payload": {"data": 123}})
        await bridge.process_queued_events()

        assert len(received) == 1
        assert received[0]["type"] == "TEST"

    async def test_game_loop_updates(self):
        """Test game loop updates engine and renderer."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)
        renderer = HeadlessRenderer(width=80, height=24)

        from claude_world.app import GameLoop
        loop = GameLoop(engine=engine, renderer=renderer, target_fps=60)

        initial_time = engine.get_state().world.time_of_day.hour

        # Run a few ticks
        for _ in range(10):
            loop.tick(0.1)

        # Time should have advanced
        assert engine.get_state().world.time_of_day.hour != initial_time


class TestEndToEnd:
    """End-to-end tests simulating real usage."""

    def test_complete_session_simulation(self):
        """Simulate a complete Claude session."""
        # Create world and engine
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)
        renderer = HeadlessRenderer(width=80, height=24)
        handler = HookHandler()

        # Session start
        events = handler.handle_session_start("startup")
        for event in events:
            engine.dispatch_claude_event(event)
        assert engine.get_state().session_active is True

        # User sends prompt
        events = handler.handle_user_prompt("Help me write a function")
        for event in events:
            engine.dispatch_claude_event(event)
        assert engine.get_state().main_agent.activity == AgentActivity.THINKING

        # Tool usage: Read
        events = handler.handle_pre_tool_use("Read", {"file": "test.py"}, "t1")
        for event in events:
            engine.dispatch_claude_event(event)
        assert engine.get_state().main_agent.activity == AgentActivity.READING

        events = handler.handle_post_tool_use("Read", "file contents", "t1")
        for event in events:
            engine.dispatch_claude_event(event)
        assert engine.get_state().progression.total_tools_used == 1

        # Tool usage: Write
        events = handler.handle_pre_tool_use("Write", {"file": "out.py"}, "t2")
        for event in events:
            engine.dispatch_claude_event(event)
        assert engine.get_state().main_agent.activity == AgentActivity.WRITING

        events = handler.handle_post_tool_use("Write", "success", "t2")
        for event in events:
            engine.dispatch_claude_event(event)
        assert engine.get_state().progression.total_tools_used == 2
        assert engine.get_state().progression.experience > 0

        # Spawn a subagent
        events = handler.handle_subagent_spawn("agent-1", "Explore", "Exploring")
        for event in events:
            engine.dispatch_claude_event(event)
        assert "agent-1" in engine.get_state().entities

        # Complete subagent
        events = handler.handle_subagent_stop("agent-1", success=True)
        for event in events:
            engine.dispatch_claude_event(event)
        assert "agent-1" not in engine.get_state().entities

        # Render final state
        renderer.render_frame(engine.get_state())
        assert renderer.last_render_time > 0

        # Session end
        events = handler.handle_stop()
        for event in events:
            engine.dispatch_claude_event(event)
        assert engine.get_state().session_active is False

        # Final stats
        final_state = engine.get_state()
        assert final_state.progression.total_tools_used == 2
        assert final_state.progression.total_subagents_spawned == 1
