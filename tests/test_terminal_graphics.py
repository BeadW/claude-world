"""Comprehensive tests for TerminalGraphicsRenderer.

These tests ensure the rendering pipeline doesn't crash during tool calls,
subagent operations, and various game states. They test the actual PIL-based
renderer, not just the headless renderer.
"""

from __future__ import annotations

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
from claude_world.plugin import HookHandler

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

    # Create renderer with fixed size (no terminal detection)
    renderer = TerminalGraphicsRenderer(width=400, height=300)

    # Mock the display output so we don't need a real terminal
    renderer._display_frame = MagicMock()

    return renderer


class TestTerminalGraphicsRendererBasics:
    """Basic tests for TerminalGraphicsRenderer initialization."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_renderer_creates_with_explicit_size(self):
        """Test renderer can be created with explicit dimensions."""
        from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer

        renderer = TerminalGraphicsRenderer(width=800, height=600)
        assert renderer.width == 800
        assert renderer.height == 600

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_renderer_has_frame_buffer(self, mock_terminal_renderer):
        """Test renderer has frame buffer after creation."""
        renderer = mock_terminal_renderer
        assert renderer.width > 0
        assert renderer.height > 0


class TestToolCallRendering:
    """Tests for rendering during tool calls."""

    ALL_TOOLS = [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "WebFetch", "WebSearch", "Task", "TodoWrite",
        "AskUserQuestion", "NotebookEdit"
    ]

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    @pytest.mark.parametrize("tool_name", ALL_TOOLS)
    def test_render_during_tool_start(self, mock_terminal_renderer, game_state, tool_name):
        """Test that rendering doesn't crash when a tool is started."""
        engine = GameEngine(initial_state=game_state)

        # Dispatch tool start event
        engine.dispatch_claude_event({
            "type": "TOOL_START",
            "payload": {"tool_name": tool_name, "tool_input": {}, "tool_use_id": f"test-{tool_name}"},
        })

        state = engine.get_state()

        # This should not raise any exception
        mock_terminal_renderer.render_frame(state)

        # Verify display was called
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    @pytest.mark.parametrize("tool_name", ALL_TOOLS)
    def test_render_during_tool_complete(self, mock_terminal_renderer, game_state, tool_name):
        """Test that rendering doesn't crash when a tool completes."""
        engine = GameEngine(initial_state=game_state)

        # Start then complete tool
        engine.dispatch_claude_event({
            "type": "TOOL_START",
            "payload": {"tool_name": tool_name, "tool_input": {}, "tool_use_id": f"test-{tool_name}"},
        })
        engine.dispatch_claude_event({
            "type": "TOOL_COMPLETE",
            "payload": {"tool_name": tool_name, "tool_response": {}},
        })

        state = engine.get_state()

        # This should not raise any exception
        mock_terminal_renderer.render_frame(state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_multiple_tool_sequence(self, mock_terminal_renderer, game_state):
        """Test rendering through a sequence of tool calls."""
        engine = GameEngine(initial_state=game_state)

        tools_sequence = ["Read", "Write", "Grep", "Edit", "Bash", "Task"]

        for tool_name in tools_sequence:
            # Start tool
            engine.dispatch_claude_event({
                "type": "TOOL_START",
                "payload": {"tool_name": tool_name, "tool_input": {}, "tool_use_id": f"seq-{tool_name}"},
            })
            mock_terminal_renderer.render_frame(engine.get_state())

            # Complete tool
            engine.dispatch_claude_event({
                "type": "TOOL_COMPLETE",
                "payload": {"tool_name": tool_name, "tool_response": {}},
            })
            mock_terminal_renderer.render_frame(engine.get_state())

        # Should complete without exception
        assert engine.get_state().progression.total_tools_used == len(tools_sequence)


class TestActivityRendering:
    """Tests for rendering different activity states."""

    ALL_ACTIVITIES = [
        AgentActivity.IDLE,
        AgentActivity.THINKING,
        AgentActivity.READING,
        AgentActivity.WRITING,
        AgentActivity.SEARCHING,
        AgentActivity.EXPLORING,
        AgentActivity.BUILDING,
        AgentActivity.COMMUNICATING,
        AgentActivity.RESTING,
        AgentActivity.CELEBRATING,
    ]

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    @pytest.mark.parametrize("activity", ALL_ACTIVITIES)
    def test_render_activity_state(self, mock_terminal_renderer, game_state, activity):
        """Test that each activity state renders without crashing."""
        game_state.main_agent.activity = activity

        # Render multiple frames to catch animation issues
        for frame in range(5):
            mock_terminal_renderer.render_frame(game_state)

        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_tool_name_set(self, mock_terminal_renderer, game_state):
        """Test rendering when current_tool is set on agent."""
        game_state.main_agent.activity = AgentActivity.READING
        game_state.main_agent.current_tool = "Read"

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()


class TestSubagentRendering:
    """Tests for subagent rendering and connections."""

    AGENT_TYPES = ["Explore", "Plan", "general-purpose", "claude-code-guide"]

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    @pytest.mark.parametrize("agent_type", AGENT_TYPES)
    def test_render_with_subagent(self, mock_terminal_renderer, game_state, agent_type):
        """Test rendering with a subagent of each type."""
        engine = GameEngine(initial_state=game_state)

        # Spawn subagent
        engine.dispatch_claude_event({
            "type": "AGENT_SPAWN",
            "payload": {
                "agent_id": f"test-{agent_type}",
                "agent_type": agent_type,
                "description": f"Test {agent_type} agent",
            },
        })

        state = engine.get_state()
        assert f"test-{agent_type}" in state.entities

        # Render multiple frames
        for _ in range(3):
            mock_terminal_renderer.render_frame(state)

        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_multiple_subagents(self, mock_terminal_renderer, game_state):
        """Test rendering with multiple active subagents."""
        engine = GameEngine(initial_state=game_state)

        # Spawn multiple agents
        for i, agent_type in enumerate(self.AGENT_TYPES):
            engine.dispatch_claude_event({
                "type": "AGENT_SPAWN",
                "payload": {
                    "agent_id": f"multi-{i}",
                    "agent_type": agent_type,
                    "description": f"Multi agent {i}",
                },
            })

        state = engine.get_state()
        assert len([e for e in state.entities.values() if e.type == EntityType.SUB_AGENT]) == len(self.AGENT_TYPES)

        # Render frames
        for _ in range(5):
            mock_terminal_renderer.render_frame(state)

        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_subagent_at_same_position_as_main(self, mock_terminal_renderer, game_state):
        """Test rendering when subagent is at same position as main agent (distance=0)."""
        # Create subagent at exact same position as main agent
        subagent = AgentEntity(
            id="same-pos-agent",
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
        game_state.entities["same-pos-agent"] = subagent

        # This tests the distance=0 edge case in connection line drawing
        for _ in range(3):
            mock_terminal_renderer.render_frame(game_state)

        mock_terminal_renderer._display_frame.assert_called()


class TestTimeOfDayRendering:
    """Tests for rendering at different times of day."""

    TIME_PHASES = [
        (3.0, "night"),
        (6.0, "dawn"),
        (12.0, "day"),
        (18.0, "dusk"),
        (22.0, "night"),
    ]

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    @pytest.mark.parametrize("hour,expected_phase", TIME_PHASES)
    def test_render_time_of_day(self, mock_terminal_renderer, game_state, hour, expected_phase):
        """Test rendering at different times of day."""
        game_state.world.time_of_day = TimeOfDay(hour=hour)
        assert game_state.world.time_of_day.phase == expected_phase

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_time_of_day_has_phase_property(self, game_state):
        """Test that TimeOfDay has phase property (not value)."""
        tod = game_state.world.time_of_day

        # This is the bug that crashed the game - using .value instead of .phase
        assert hasattr(tod, 'phase')
        assert isinstance(tod.phase, str)
        assert tod.phase in ["dawn", "day", "dusk", "night"]

        # Verify .value doesn't exist (it's not an enum)
        assert not hasattr(tod, 'value') or not callable(getattr(tod, 'value', None))


class TestWeatherRendering:
    """Tests for rendering different weather conditions."""

    WEATHER_TYPES = ["clear", "cloudy", "rain", "storm"]

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    @pytest.mark.parametrize("weather_type", WEATHER_TYPES)
    def test_render_weather_type(self, mock_terminal_renderer, game_state, weather_type):
        """Test rendering with different weather types."""
        game_state.world.weather = WeatherState(
            type=weather_type,
            intensity=0.5,
            wind_direction=45.0,
            wind_speed=10.0,
        )

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()


class TestParticleRendering:
    """Tests for particle rendering."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_particles(self, mock_terminal_renderer, game_state):
        """Test rendering with particles."""
        # Add some particles
        for i in range(10):
            particle = Particle(
                position=Position(400 + i * 10, 300),
                velocity=Velocity(0, -10),
                lifetime=1.0,
                max_lifetime=1.0,
                sprite="star",
                color=(255, 255, 0),
                scale=1.0,
            )
            game_state.particles.append(particle)

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()


class TestAPIUsageRendering:
    """Tests for API cost tracking display."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_api_costs(self, mock_terminal_renderer, game_state):
        """Test rendering with API cost data."""
        # Add some API usage
        game_state.resources.api_costs.add_usage(
            input_tokens=1000,
            output_tokens=500,
            cache_read=200,
            cache_write=100,
        )

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_api_cost_tracker_copy(self):
        """Test ApiCostTracker copy method works correctly."""
        tracker = ApiCostTracker()
        tracker.add_usage(input_tokens=1000, output_tokens=500)

        copy = tracker.copy()
        assert copy.input_tokens == 1000
        assert copy.output_tokens == 500
        assert copy.total_tokens == 1500


class TestFullSessionSimulation:
    """End-to-end tests simulating full Claude sessions with rendering."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_complete_session_with_rendering(self, mock_terminal_renderer):
        """Simulate a complete Claude session with rendering at each step."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)
        handler = HookHandler()

        # Session start
        events = handler.handle_session_start("startup")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # User prompt
        events = handler.handle_user_prompt("Help me with code")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Read tool
        events = handler.handle_pre_tool_use("Read", {"file": "test.py"}, "t1")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        events = handler.handle_post_tool_use("Read", "content", "t1")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Grep tool
        events = handler.handle_pre_tool_use("Grep", {"pattern": "test"}, "t2")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        events = handler.handle_post_tool_use("Grep", "results", "t2")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Write tool
        events = handler.handle_pre_tool_use("Write", {"file": "out.py"}, "t3")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        events = handler.handle_post_tool_use("Write", "success", "t3")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Task tool (spawns subagent)
        events = handler.handle_pre_tool_use(
            "Task",
            {"subagent_type": "Explore", "description": "Find files"},
            "t4"
        )
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Subagent complete
        events = handler.handle_subagent_stop("t4", success=True)
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        events = handler.handle_post_tool_use("Task", "agent result", "t4")
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Session end
        events = handler.handle_stop()
        for event in events:
            engine.dispatch_claude_event(event)
        mock_terminal_renderer.render_frame(engine.get_state())

        # Verify state
        final_state = engine.get_state()
        assert final_state.progression.total_tools_used == 4
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_rapid_tool_switching(self, mock_terminal_renderer):
        """Test rapid tool switching doesn't cause render issues."""
        state = create_tropical_island()
        engine = GameEngine(initial_state=state)

        tools = ["Read", "Grep", "Write", "Edit", "Bash", "Read", "Write"]

        for i, tool in enumerate(tools):
            # Start
            engine.dispatch_claude_event({
                "type": "TOOL_START",
                "payload": {"tool_name": tool, "tool_input": {}, "tool_use_id": f"rapid-{i}"},
            })
            mock_terminal_renderer.render_frame(engine.get_state())

            # Complete immediately
            engine.dispatch_claude_event({
                "type": "TOOL_COMPLETE",
                "payload": {"tool_name": tool, "tool_response": {}},
            })
            mock_terminal_renderer.render_frame(engine.get_state())

        mock_terminal_renderer._display_frame.assert_called()


class TestEdgeCases:
    """Tests for edge cases and potential crash scenarios."""

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_zero_progression(self, mock_terminal_renderer, game_state):
        """Test rendering with zero progression values."""
        game_state.progression = Progression(
            level=1,
            experience=0,
            experience_to_next=100,
        )

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_max_level(self, mock_terminal_renderer, game_state):
        """Test rendering with high level values."""
        game_state.progression.level = 999
        game_state.progression.experience = 999999

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_many_resources(self, mock_terminal_renderer, game_state):
        """Test rendering with many resources."""
        game_state.resources.tokens = 999999
        game_state.resources.connections = 9999
        game_state.resources.insights = 9999

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_empty_entities(self, mock_terminal_renderer, game_state):
        """Test rendering when entities dict only has main agent."""
        game_state.entities = {game_state.main_agent.id: game_state.main_agent}

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_agent_at_origin(self, mock_terminal_renderer, game_state):
        """Test rendering when agent is at position (0, 0)."""
        game_state.main_agent.position = Position(0, 0)
        game_state.camera.x = 0
        game_state.camera.y = 0

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    def test_render_with_agent_at_edge(self, mock_terminal_renderer, game_state):
        """Test rendering when agent is at world edge."""
        game_state.main_agent.position = Position(
            game_state.world.width - 1,
            game_state.world.height - 1
        )

        mock_terminal_renderer.render_frame(game_state)
        mock_terminal_renderer._display_frame.assert_called()


class TestWorldObjectAnimations:
    """Tests for world object animations during tool usage."""

    TOOL_LOCATIONS = {
        "Read": "reading_palm",
        "Write": "sand_patch",
        "Grep": "tide_pool",
        "Glob": "tide_pool",
        "Bash": "rock_pile",
        "Task": "thinking_spot",
        "WebFetch": "message_bottle",
        "WebSearch": "message_bottle",
    }

    @pytest.mark.skipif(not HAS_PIL, reason="PIL not available")
    @pytest.mark.parametrize("tool_name,location", list(TOOL_LOCATIONS.items()))
    def test_world_object_animations_during_tool(self, mock_terminal_renderer, game_state, tool_name, location):
        """Test that world objects animate properly during tool usage."""
        engine = GameEngine(initial_state=game_state)

        # Start tool
        engine.dispatch_claude_event({
            "type": "TOOL_START",
            "payload": {"tool_name": tool_name, "tool_input": {}, "tool_use_id": f"anim-{tool_name}"},
        })

        # Render multiple frames to test animation
        for frame in range(10):
            mock_terminal_renderer.render_frame(engine.get_state())

        mock_terminal_renderer._display_frame.assert_called()


class TestStatePersistence:
    """Tests for state copy and persistence."""

    def test_game_state_copy(self, game_state):
        """Test that game state can be copied without errors."""
        copy = game_state.copy()
        assert copy is not game_state
        assert copy.main_agent.position.x == game_state.main_agent.position.x

    def test_progression_copy(self, game_state):
        """Test progression copy preserves all fields."""
        game_state.progression.add_experience(50)
        game_state.progression.achievements.add("first_read")

        copy = game_state.progression.copy()
        assert copy.experience == 50
        assert "first_read" in copy.achievements

    def test_resources_copy(self, game_state):
        """Test resources copy preserves API costs."""
        game_state.resources.api_costs.add_usage(input_tokens=1000)

        copy = game_state.resources.copy()
        assert copy.api_costs.input_tokens == 1000
