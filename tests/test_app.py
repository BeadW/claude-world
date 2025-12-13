"""Tests for main application (TDD tests written first)."""

from __future__ import annotations

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from claude_world.app.pty_manager import PTYManager, StartupFilter
from claude_world.app.game_loop import GameLoop
from claude_world.app.application import Application


class TestStartupFilter:
    """Tests for Claude startup screen filter."""

    def test_filter_creates(self):
        """Test startup filter can be created."""
        filter = StartupFilter()
        assert filter is not None

    def test_filter_detects_startup_box(self):
        """Test filter detects startup welcome box."""
        filter = StartupFilter()
        # Typical Claude startup box characters
        startup_text = "╭─────────────────────────────────────────────────────╮"
        assert filter.is_startup_content(startup_text) is True

    def test_filter_passes_normal_output(self):
        """Test filter passes normal output."""
        filter = StartupFilter()
        normal_text = "Hello, I can help you with that."
        assert filter.is_startup_content(normal_text) is False

    def test_filter_startup_lines(self):
        """Test filter can filter multiple lines."""
        filter = StartupFilter()
        lines = [
            "╭─────────────────────────────────────────────────────╮",
            "│ Tips for getting the most out of Claude Code       │",
            "│ • Be specific about what you want                  │",
            "╰─────────────────────────────────────────────────────╯",
            "",
            "> ",
        ]
        filtered = filter.filter_lines(lines)
        # Should filter out the box, keep prompt
        assert len(filtered) < len(lines)
        assert "> " in filtered[-1] if filtered else True

    def test_filter_state_tracking(self):
        """Test filter tracks state properly."""
        filter = StartupFilter()
        # Start with startup detection enabled
        assert filter.in_startup is True

        # After seeing end of box, should disable
        filter.process_line("╰─────────────────────────────────────────────────────╯")
        filter.process_line("")
        filter.process_line("> ")

        # Eventually should exit startup mode
        for _ in range(10):
            filter.process_line("Normal output")
        assert filter.in_startup is False


class TestPTYManager:
    """Tests for PTY manager."""

    def test_pty_manager_creates(self):
        """Test PTY manager can be created."""
        manager = PTYManager()
        assert manager is not None

    def test_pty_manager_has_startup_filter(self):
        """Test PTY manager has startup filter."""
        manager = PTYManager()
        assert manager.startup_filter is not None

    def test_pty_manager_command_default(self):
        """Test PTY manager has default command."""
        manager = PTYManager()
        assert "claude" in manager.command

    def test_pty_manager_custom_command(self):
        """Test PTY manager accepts custom command."""
        manager = PTYManager(command=["echo", "test"])
        assert manager.command == ["echo", "test"]

    def test_pty_manager_write_forwards_input(self):
        """Test writing to PTY manager."""
        manager = PTYManager()
        # Should not raise even before started
        manager.write(b"test")

    def test_pty_manager_resize(self):
        """Test PTY resize functionality."""
        manager = PTYManager()
        manager.resize(100, 50)
        assert manager.cols == 100
        assert manager.rows == 50


class TestGameLoop:
    """Tests for game loop."""

    def test_game_loop_creates(self, basic_game_state):
        """Test game loop can be created."""
        from claude_world.engine import GameEngine
        from claude_world.renderer.headless import HeadlessRenderer

        engine = GameEngine(initial_state=basic_game_state)
        renderer = HeadlessRenderer(width=80, height=24)
        loop = GameLoop(engine=engine, renderer=renderer)
        assert loop is not None

    def test_game_loop_has_target_fps(self, basic_game_state):
        """Test game loop has target FPS."""
        from claude_world.engine import GameEngine
        from claude_world.renderer.headless import HeadlessRenderer

        engine = GameEngine(initial_state=basic_game_state)
        renderer = HeadlessRenderer(width=80, height=24)
        loop = GameLoop(engine=engine, renderer=renderer, target_fps=30)
        assert loop.target_fps == 30

    def test_game_loop_tick_updates_engine(self, basic_game_state):
        """Test game loop tick updates engine."""
        from claude_world.engine import GameEngine
        from claude_world.renderer.headless import HeadlessRenderer

        engine = GameEngine(initial_state=basic_game_state)
        renderer = HeadlessRenderer(width=80, height=24)
        loop = GameLoop(engine=engine, renderer=renderer)

        initial_time = engine.get_state().world.time_of_day.hour
        loop.tick(1.0)  # 1 second tick

        new_time = engine.get_state().world.time_of_day.hour
        assert new_time != initial_time

    def test_game_loop_tick_renders(self, basic_game_state):
        """Test game loop tick renders."""
        from claude_world.engine import GameEngine
        from claude_world.renderer.headless import HeadlessRenderer

        engine = GameEngine(initial_state=basic_game_state)
        renderer = HeadlessRenderer(width=80, height=24)
        loop = GameLoop(engine=engine, renderer=renderer)

        loop.tick(0.016)  # ~60fps tick
        assert renderer.last_render_time > 0

    def test_game_loop_dispatch_event(self, basic_game_state):
        """Test game loop dispatches events."""
        from claude_world.engine import GameEngine
        from claude_world.renderer.headless import HeadlessRenderer

        engine = GameEngine(initial_state=basic_game_state)
        renderer = HeadlessRenderer(width=80, height=24)
        loop = GameLoop(engine=engine, renderer=renderer)

        loop.dispatch_event({
            "type": "TOOL_START",
            "payload": {"tool_name": "Read", "tool_input": {}, "tool_use_id": "123"},
        })

        state = engine.get_state()
        assert state.main_agent.activity.value == "reading"


class TestApplication:
    """Tests for main application."""

    def test_application_creates(self):
        """Test application can be created."""
        app = Application(headless=True)
        assert app is not None

    @pytest.mark.asyncio
    async def test_application_has_engine(self):
        """Test application has game engine after init."""
        app = Application(headless=True)
        await app.initialize()
        assert app.engine is not None

    @pytest.mark.asyncio
    async def test_application_has_renderer(self):
        """Test application has renderer after init."""
        app = Application(headless=True)
        await app.initialize()
        assert app.renderer is not None

    @pytest.mark.asyncio
    async def test_application_has_event_bridge(self):
        """Test application has event bridge after init."""
        app = Application(headless=True)
        await app.initialize()
        assert app.event_bridge is not None

    def test_application_headless_mode(self):
        """Test application in headless mode."""
        app = Application(headless=True)
        assert app.headless is True

    def test_application_world_config(self):
        """Test application accepts world config."""
        app = Application(headless=True, world_name="tropical-island")
        assert app.world_name == "tropical-island"


@pytest.mark.asyncio
class TestApplicationAsync:
    """Async tests for application."""

    async def test_application_init_creates_state(self):
        """Test application initialization creates game state."""
        app = Application(headless=True)
        await app.initialize()
        state = app.engine.get_state()
        assert state is not None
        assert state.main_agent is not None

    async def test_application_shutdown_cleans_up(self):
        """Test application shutdown cleans up resources."""
        app = Application(headless=True)
        await app.initialize()
        await app.shutdown()
        # Should not raise
