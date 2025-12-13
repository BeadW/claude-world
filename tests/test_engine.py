"""Tests for game engine (TDD tests written first)."""

from __future__ import annotations

import pytest
import numpy as np

from claude_world.engine import GameEngine, map_claude_event, get_tool_effect, EffectType
from claude_world.engine.state import GameStateManager
from claude_world.engine.entity import EntityManager
from claude_world.types import (
    AgentActivity,
    AgentMood,
    EntityType,
    Position,
    Velocity,
    AnimationState,
    AgentEntity,
    GameState,
    WorldState,
    TerrainData,
    TimeOfDay,
    WeatherState,
    Camera,
    Resources,
    Progression,
)


class TestMapClaudeEvent:
    """Tests for claude event to game event mapping."""

    def test_tool_start_read_creates_activity_change(self):
        """Test TOOL_START with Read creates activity change event."""
        event = {
            "type": "TOOL_START",
            "payload": {"tool_name": "Read", "tool_input": {}, "tool_use_id": "123"},
        }
        game_events = map_claude_event(event)
        assert any(e["type"] == "CHANGE_ACTIVITY" for e in game_events)
        activity_event = next(e for e in game_events if e["type"] == "CHANGE_ACTIVITY")
        assert activity_event["data"]["activity"] == AgentActivity.READING

    def test_tool_start_write_creates_activity_change(self):
        """Test TOOL_START with Write creates activity change event."""
        event = {
            "type": "TOOL_START",
            "payload": {"tool_name": "Write", "tool_input": {}, "tool_use_id": "123"},
        }
        game_events = map_claude_event(event)
        activity_event = next(e for e in game_events if e["type"] == "CHANGE_ACTIVITY")
        assert activity_event["data"]["activity"] == AgentActivity.WRITING

    def test_tool_start_task_creates_spawn_event(self):
        """Test TOOL_START with Task creates agent spawn event."""
        event = {
            "type": "TOOL_START",
            "payload": {
                "tool_name": "Task",
                "tool_input": {"subagent_type": "Explore", "description": "Test"},
                "tool_use_id": "agent-123",
            },
        }
        game_events = map_claude_event(event)
        assert any(e["type"] == "SPAWN_AGENT" for e in game_events)
        spawn_event = next(e for e in game_events if e["type"] == "SPAWN_AGENT")
        assert spawn_event["data"]["agent_type"] == "Explore"
        assert spawn_event["data"]["agent_id"] == "agent-123"

    def test_tool_complete_awards_resources(self):
        """Test TOOL_COMPLETE creates award resources event."""
        event = {
            "type": "TOOL_COMPLETE",
            "payload": {"tool_name": "Write", "tool_response": {}},
        }
        game_events = map_claude_event(event)
        assert any(e["type"] == "AWARD_RESOURCES" for e in game_events)

    def test_agent_spawn_creates_spawn_event(self):
        """Test AGENT_SPAWN creates spawn agent event."""
        event = {
            "type": "AGENT_SPAWN",
            "payload": {
                "agent_id": "agent-1",
                "agent_type": "Plan",
                "description": "Planning",
            },
        }
        game_events = map_claude_event(event)
        assert any(e["type"] == "SPAWN_AGENT" for e in game_events)

    def test_agent_complete_creates_remove_event(self):
        """Test AGENT_COMPLETE creates remove agent event."""
        event = {
            "type": "AGENT_COMPLETE",
            "payload": {"agent_id": "agent-1", "success": True},
        }
        game_events = map_claude_event(event)
        assert any(e["type"] == "REMOVE_AGENT" for e in game_events)

    def test_agent_idle_creates_idle_activity(self):
        """Test AGENT_IDLE sets activity to idle."""
        event = {"type": "AGENT_IDLE", "payload": {}}
        game_events = map_claude_event(event)
        assert any(e["type"] == "CHANGE_ACTIVITY" for e in game_events)
        activity_event = next(e for e in game_events if e["type"] == "CHANGE_ACTIVITY")
        assert activity_event["data"]["activity"] == AgentActivity.IDLE

    def test_session_start_creates_session_event(self):
        """Test SESSION_START creates session start event."""
        event = {"type": "SESSION_START", "payload": {"source": "startup"}}
        game_events = map_claude_event(event)
        assert any(e["type"] == "SESSION_START" for e in game_events)

    def test_session_end_creates_session_event(self):
        """Test SESSION_END creates session end event."""
        event = {"type": "SESSION_END", "payload": {}}
        game_events = map_claude_event(event)
        assert any(e["type"] == "SESSION_END" for e in game_events)


class TestGetToolEffect:
    """Tests for tool effect mapping."""

    def test_read_sparkle_effect(self):
        """Test Read tool creates sparkle effect."""
        effect = get_tool_effect("Read")
        assert effect == EffectType.SPARKLE

    def test_write_burst_effect(self):
        """Test Write tool creates write burst effect."""
        effect = get_tool_effect("Write")
        assert effect == EffectType.WRITE_BURST

    def test_search_magnify_effect(self):
        """Test Grep tool creates magnify effect."""
        effect = get_tool_effect("Grep")
        assert effect == EffectType.MAGNIFY

    def test_unknown_default_effect(self):
        """Test unknown tool creates default effect."""
        effect = get_tool_effect("Unknown")
        assert effect == EffectType.SPARKLE


class TestEntityManager:
    """Tests for entity management."""

    @pytest.fixture
    def entity_manager(self, basic_game_state):
        """Create an entity manager for testing."""
        return EntityManager(basic_game_state)

    def test_spawn_subagent(self, entity_manager):
        """Test spawning a subagent."""
        entity_manager.spawn_subagent(
            agent_id="sub-1",
            agent_type="Explore",
            description="Test agent",
        )
        state = entity_manager.get_state()
        assert "sub-1" in state.entities
        agent = state.entities["sub-1"]
        assert agent.agent_type == "Explore"
        assert agent.type == EntityType.SUB_AGENT

    def test_remove_entity(self, entity_manager):
        """Test removing an entity."""
        entity_manager.spawn_subagent("sub-1", "Explore", "Test")
        entity_manager.remove_entity("sub-1")
        state = entity_manager.get_state()
        assert "sub-1" not in state.entities

    def test_update_main_agent_activity(self, entity_manager):
        """Test updating main agent activity."""
        entity_manager.set_main_agent_activity(AgentActivity.READING)
        state = entity_manager.get_state()
        assert state.main_agent.activity == AgentActivity.READING

    def test_get_entity_by_id(self, entity_manager):
        """Test getting entity by ID."""
        entity = entity_manager.get_entity("main_agent")
        assert entity is not None
        assert entity.id == "main_agent"

    def test_get_entities_by_type(self, entity_manager):
        """Test getting entities by type."""
        entity_manager.spawn_subagent("sub-1", "Explore", "Test")
        entity_manager.spawn_subagent("sub-2", "Plan", "Test")
        subagents = entity_manager.get_entities_by_type(EntityType.SUB_AGENT)
        assert len(subagents) == 2


class TestGameStateManager:
    """Tests for game state management."""

    @pytest.fixture
    def state_manager(self, basic_world_state, basic_agent):
        """Create a state manager for testing."""
        initial_state = GameState(
            world=basic_world_state,
            entities={basic_agent.id: basic_agent},
            main_agent=basic_agent,
            particles=[],
            resources=Resources(),
            progression=Progression(),
            camera=Camera(x=500, y=500),
            session_active=False,
        )
        return GameStateManager(initial_state)

    def test_get_state(self, state_manager):
        """Test getting state."""
        state = state_manager.get_state()
        assert state is not None
        assert state.world.name == "test-world"

    def test_update_state(self, state_manager):
        """Test updating state."""
        def update(state):
            state.resources.tokens += 10
            return state

        state_manager.update_state(update)
        state = state_manager.get_state()
        assert state.resources.tokens == 10

    def test_subscribe_notifies_listener(self, state_manager):
        """Test state change notification."""
        notified = []

        def listener(state):
            notified.append(state)

        state_manager.subscribe(listener)
        state_manager.update_state(lambda s: s)

        assert len(notified) == 1


class TestGameEngine:
    """Tests for game engine."""

    @pytest.fixture
    def engine(self, basic_game_state):
        """Create a game engine for testing."""
        return GameEngine(initial_state=basic_game_state)

    def test_initial_state(self, engine):
        """Test engine has initial state."""
        state = engine.get_state()
        assert state is not None
        assert state.main_agent is not None
        assert state.main_agent.activity == AgentActivity.IDLE

    def test_dispatch_tool_start(self, engine):
        """Test dispatching tool start event."""
        engine.dispatch_claude_event({
            "type": "TOOL_START",
            "payload": {"tool_name": "Read", "tool_input": {}, "tool_use_id": "123"},
        })
        state = engine.get_state()
        assert state.main_agent.activity == AgentActivity.READING

    def test_dispatch_tool_complete_awards_xp(self, engine):
        """Test dispatching tool complete awards XP."""
        initial_xp = engine.get_state().progression.experience
        engine.dispatch_claude_event({
            "type": "TOOL_COMPLETE",
            "payload": {"tool_name": "Write", "tool_response": {}},
        })
        state = engine.get_state()
        assert state.progression.experience > initial_xp

    def test_dispatch_agent_spawn(self, engine):
        """Test dispatching agent spawn."""
        engine.dispatch_claude_event({
            "type": "AGENT_SPAWN",
            "payload": {
                "agent_id": "sub-1",
                "agent_type": "Explore",
                "description": "Test",
            },
        })
        state = engine.get_state()
        assert "sub-1" in state.entities

    def test_dispatch_agent_complete(self, engine):
        """Test dispatching agent complete."""
        # First spawn
        engine.dispatch_claude_event({
            "type": "AGENT_SPAWN",
            "payload": {"agent_id": "sub-1", "agent_type": "Explore", "description": "Test"},
        })
        # Then complete
        engine.dispatch_claude_event({
            "type": "AGENT_COMPLETE",
            "payload": {"agent_id": "sub-1", "success": True},
        })
        state = engine.get_state()
        assert "sub-1" not in state.entities

    def test_update_advances_time(self, engine):
        """Test update advances game time."""
        initial_hour = engine.get_state().world.time_of_day.hour
        engine.update(60.0)  # 1 minute
        state = engine.get_state()
        assert state.world.time_of_day.hour != initial_hour

    def test_update_advances_animations(self, engine):
        """Test update advances animations."""
        initial_frame = engine.get_state().main_agent.animation.frame_time
        engine.update(0.1)
        state = engine.get_state()
        assert state.main_agent.animation.frame_time > initial_frame

    def test_session_start_activates(self, engine):
        """Test session start activates session."""
        engine.dispatch_claude_event({
            "type": "SESSION_START",
            "payload": {"source": "startup"},
        })
        state = engine.get_state()
        assert state.session_active is True

    def test_session_end_deactivates(self, engine):
        """Test session end deactivates session."""
        engine.dispatch_claude_event({"type": "SESSION_START", "payload": {}})
        engine.dispatch_claude_event({"type": "SESSION_END", "payload": {}})
        state = engine.get_state()
        assert state.session_active is False
