"""Tests for type definitions (TDD tests written first)."""

from __future__ import annotations

import pytest
import numpy as np

from claude_world.types import (
    ClaudeEvent,
    ClaudeEventType,
    ToolEventPayload,
    AgentSpawnPayload,
    AgentCompletePayload,
    UserPromptPayload,
    Position,
    Velocity,
    AnimationState,
    Entity,
    EntityType,
    AgentEntity,
    AgentActivity,
    AgentMood,
    TOOL_ACTIVITY_MAP,
    ACTIVITY_ANIMATIONS,
    Sprite,
    Animation,
    AnimationFrame,
    GameState,
    WorldState,
    TerrainData,
    TimeOfDay,
    WeatherState,
    Camera,
    Resources,
    Progression,
    TOOL_XP_REWARDS,
)


class TestClaudeEvents:
    """Tests for Claude event types."""

    def test_claude_event_from_dict(self):
        """Test creating ClaudeEvent from dictionary."""
        data = {
            "type": "TOOL_START",
            "timestamp": 1234567890.0,
            "session_id": "test-session",
            "payload": {"tool_name": "Read"},
        }
        event = ClaudeEvent.from_dict(data)
        assert event.type == ClaudeEventType.TOOL_START
        assert event.timestamp == 1234567890.0
        assert event.session_id == "test-session"
        assert event.payload["tool_name"] == "Read"

    def test_claude_event_unknown_type(self):
        """Test handling unknown event type."""
        data = {"type": "UNKNOWN_TYPE", "timestamp": 0, "session_id": ""}
        event = ClaudeEvent.from_dict(data)
        assert event.type == ClaudeEventType.NOTIFICATION

    def test_tool_event_payload(self):
        """Test ToolEventPayload creation."""
        data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/test.txt"},
            "tool_use_id": "tool-123",
            "tool_response": {"success": True},
        }
        payload = ToolEventPayload.from_dict(data)
        assert payload.tool_name == "Write"
        assert payload.tool_input["file_path"] == "/test.txt"
        assert payload.tool_use_id == "tool-123"
        assert payload.tool_response["success"] is True

    def test_agent_spawn_payload(self):
        """Test AgentSpawnPayload creation."""
        data = {
            "agent_id": "agent-1",
            "agent_type": "Explore",
            "description": "Searching codebase",
        }
        payload = AgentSpawnPayload.from_dict(data)
        assert payload.agent_id == "agent-1"
        assert payload.agent_type == "Explore"
        assert payload.description == "Searching codebase"

    def test_agent_complete_payload(self):
        """Test AgentCompletePayload creation."""
        data = {"agent_id": "agent-1", "success": True}
        payload = AgentCompletePayload.from_dict(data)
        assert payload.agent_id == "agent-1"
        assert payload.success is True

    def test_user_prompt_payload(self):
        """Test UserPromptPayload creation."""
        data = {"prompt": "Hello Claude"}
        payload = UserPromptPayload.from_dict(data)
        assert payload.prompt == "Hello Claude"
        assert payload.prompt_length == 12  # "Hello Claude" is 12 characters


class TestPosition:
    """Tests for Position class."""

    def test_position_creation(self):
        """Test creating a position."""
        pos = Position(100.5, 200.5)
        assert pos.x == 100.5
        assert pos.y == 200.5

    def test_position_copy(self):
        """Test copying a position."""
        pos = Position(100, 200)
        pos_copy = pos.copy()
        assert pos_copy.x == pos.x
        assert pos_copy.y == pos.y
        pos_copy.x = 300
        assert pos.x == 100  # Original unchanged


class TestVelocity:
    """Tests for Velocity class."""

    def test_velocity_defaults(self):
        """Test velocity default values."""
        vel = Velocity()
        assert vel.x == 0.0
        assert vel.y == 0.0

    def test_velocity_copy(self):
        """Test copying velocity."""
        vel = Velocity(10, 20)
        vel_copy = vel.copy()
        assert vel_copy.x == vel.x
        vel_copy.x = 30
        assert vel.x == 10


class TestAnimationState:
    """Tests for AnimationState class."""

    def test_animation_state_creation(self):
        """Test creating animation state."""
        anim = AnimationState(current_animation="idle")
        assert anim.current_animation == "idle"
        assert anim.current_frame == 0
        assert anim.frame_time == 0.0
        assert anim.playing is True

    def test_animation_update_advances_frame(self, basic_sprite):
        """Test that animation updates advance frames."""
        anim = AnimationState(current_animation="idle", current_frame=0, frame_time=0)
        # Advance past first frame (500ms)
        anim.update(0.6, basic_sprite)
        assert anim.current_frame == 1

    def test_animation_loops(self, basic_sprite):
        """Test that looping animation wraps around."""
        anim = AnimationState(current_animation="idle", current_frame=1, frame_time=400)
        # Advance past end
        anim.update(0.2, basic_sprite)
        assert anim.current_frame == 0  # Looped back

    def test_animation_non_loop_stops(self, basic_sprite):
        """Test that non-looping animation stops."""
        anim = AnimationState(current_animation="once", current_frame=1, frame_time=50)
        anim.update(0.1, basic_sprite)
        assert anim.current_frame == 1  # Stays at last frame
        assert anim.playing is False

    def test_animation_play_changes_animation(self):
        """Test play method changes animation."""
        anim = AnimationState(current_animation="idle", current_frame=1, frame_time=100)
        anim.play("walk")
        assert anim.current_animation == "walk"
        assert anim.current_frame == 0
        assert anim.frame_time == 0
        assert anim.playing is True

    def test_animation_play_same_animation_no_restart(self):
        """Test play same animation without restart flag."""
        anim = AnimationState(current_animation="idle", current_frame=1, frame_time=100)
        anim.play("idle", restart=False)
        assert anim.current_frame == 1  # Unchanged

    def test_animation_play_same_animation_with_restart(self):
        """Test play same animation with restart flag."""
        anim = AnimationState(current_animation="idle", current_frame=1, frame_time=100)
        anim.play("idle", restart=True)
        assert anim.current_frame == 0  # Reset


class TestEntity:
    """Tests for Entity class."""

    def test_entity_creation(self, basic_entity):
        """Test creating an entity."""
        assert basic_entity.id == "test_entity"
        assert basic_entity.type == EntityType.DECORATION
        assert basic_entity.position.x == 100
        assert basic_entity.position.y == 100

    def test_entity_copy(self, basic_entity):
        """Test copying an entity."""
        entity_copy = basic_entity.copy()
        assert entity_copy.id == basic_entity.id
        entity_copy.position.x = 999
        assert basic_entity.position.x == 100  # Original unchanged


class TestAgentEntity:
    """Tests for AgentEntity class."""

    def test_agent_entity_creation(self, basic_agent):
        """Test creating an agent entity."""
        assert basic_agent.type == EntityType.MAIN_AGENT
        assert basic_agent.activity == AgentActivity.IDLE
        assert basic_agent.mood == AgentMood.NEUTRAL
        assert basic_agent.energy == 100.0

    def test_agent_set_activity(self, basic_agent):
        """Test setting agent activity."""
        basic_agent.set_activity(AgentActivity.READING)
        assert basic_agent.activity == AgentActivity.READING
        assert basic_agent.animation.current_animation == "reading"

    def test_agent_copy(self, basic_agent):
        """Test copying an agent entity."""
        agent_copy = basic_agent.copy()
        agent_copy.activity = AgentActivity.WRITING
        assert basic_agent.activity == AgentActivity.IDLE


class TestToolActivityMap:
    """Tests for tool to activity mapping."""

    def test_read_maps_to_reading(self):
        """Test Read tool maps to reading activity."""
        assert TOOL_ACTIVITY_MAP["Read"] == AgentActivity.READING

    def test_write_maps_to_writing(self):
        """Test Write tool maps to writing activity."""
        assert TOOL_ACTIVITY_MAP["Write"] == AgentActivity.WRITING

    def test_edit_maps_to_writing(self):
        """Test Edit tool maps to writing activity."""
        assert TOOL_ACTIVITY_MAP["Edit"] == AgentActivity.WRITING

    def test_grep_maps_to_searching(self):
        """Test Grep tool maps to searching activity."""
        assert TOOL_ACTIVITY_MAP["Grep"] == AgentActivity.SEARCHING

    def test_task_maps_to_exploring(self):
        """Test Task tool maps to exploring activity."""
        assert TOOL_ACTIVITY_MAP["Task"] == AgentActivity.EXPLORING


class TestActivityAnimations:
    """Tests for activity to animation mapping."""

    def test_idle_maps_to_idle(self):
        """Test idle activity maps to idle animation."""
        assert ACTIVITY_ANIMATIONS[AgentActivity.IDLE] == "idle"

    def test_reading_maps_to_reading(self):
        """Test reading activity maps to reading animation."""
        assert ACTIVITY_ANIMATIONS[AgentActivity.READING] == "reading"

    def test_exploring_maps_to_walk(self):
        """Test exploring activity maps to walk animation."""
        assert ACTIVITY_ANIMATIONS[AgentActivity.EXPLORING] == "walk_right"


class TestSprite:
    """Tests for Sprite class."""

    def test_sprite_creation(self, basic_sprite):
        """Test creating a sprite."""
        assert basic_sprite.id == "test_sprite"
        assert basic_sprite.width == 64
        assert basic_sprite.height == 64
        assert basic_sprite.anchor == (32, 60)

    def test_sprite_has_animations(self, basic_sprite):
        """Test sprite has animations."""
        assert "idle" in basic_sprite.animations
        assert "walk" in basic_sprite.animations

    def test_animation_has_frames(self, basic_sprite):
        """Test animation has frames."""
        idle_anim = basic_sprite.animations["idle"]
        assert len(idle_anim.frames) == 2
        assert idle_anim.frames[0].duration_ms == 500


class TestTimeOfDay:
    """Tests for TimeOfDay class."""

    def test_dawn_phase(self):
        """Test dawn phase detection."""
        time = TimeOfDay(hour=6.0)
        assert time.phase == "dawn"

    def test_day_phase(self):
        """Test day phase detection."""
        time = TimeOfDay(hour=12.0)
        assert time.phase == "day"

    def test_dusk_phase(self):
        """Test dusk phase detection."""
        time = TimeOfDay(hour=18.0)
        assert time.phase == "dusk"

    def test_night_phase(self):
        """Test night phase detection."""
        time = TimeOfDay(hour=22.0)
        assert time.phase == "night"

    def test_sun_angle(self):
        """Test sun angle calculation."""
        time = TimeOfDay(hour=12.0)
        assert time.sun_angle == 90.0  # Noon = 90 degrees


class TestWeatherState:
    """Tests for WeatherState class."""

    def test_weather_creation(self):
        """Test creating weather state."""
        weather = WeatherState(type="rain", intensity=0.5, wind_direction=45.0, wind_speed=10.0)
        assert weather.type == "rain"
        assert weather.intensity == 0.5

    def test_weather_copy(self):
        """Test copying weather state."""
        weather = WeatherState(type="rain", intensity=0.5, wind_direction=45.0, wind_speed=10.0)
        weather_copy = weather.copy()
        weather_copy.intensity = 1.0
        assert weather.intensity == 0.5


class TestCamera:
    """Tests for Camera class."""

    def test_camera_creation(self):
        """Test creating a camera."""
        camera = Camera(x=100, y=200)
        assert camera.x == 100
        assert camera.y == 200
        assert camera.zoom == 1.0

    def test_camera_world_to_screen(self):
        """Test world to screen coordinate conversion."""
        camera = Camera(x=100, y=100, zoom=1.0)
        pos = Position(150, 150)
        screen_x, screen_y = camera.world_to_screen(pos, (800, 600))
        # Position is 50 pixels from camera center
        # Screen center is (400, 300)
        assert screen_x == 450
        assert screen_y == 350

    def test_camera_follow_target(self, basic_entity):
        """Test camera following a target."""
        camera = Camera(x=0, y=0, target=basic_entity.id, smooth_factor=1.0)
        entities = {basic_entity.id: basic_entity}
        camera.update(0.1, entities)
        assert camera.x == basic_entity.position.x
        assert camera.y == basic_entity.position.y


class TestResources:
    """Tests for Resources class."""

    def test_resources_defaults(self):
        """Test resource default values."""
        resources = Resources()
        assert resources.tokens == 0
        assert resources.insights == 0
        assert resources.connections == 0
        assert "tropical-island" in resources.unlocked_islands

    def test_resources_copy(self):
        """Test copying resources."""
        resources = Resources(tokens=100)
        resources_copy = resources.copy()
        resources_copy.tokens = 200
        assert resources.tokens == 100


class TestProgression:
    """Tests for Progression class."""

    def test_progression_defaults(self):
        """Test progression default values."""
        prog = Progression()
        assert prog.level == 1
        assert prog.experience == 0
        assert prog.experience_to_next == 100

    def test_add_experience_no_level_up(self):
        """Test adding experience without level up."""
        prog = Progression()
        leveled = prog.add_experience(50)
        assert leveled is False
        assert prog.experience == 50
        assert prog.level == 1

    def test_add_experience_level_up(self):
        """Test adding experience with level up."""
        prog = Progression()
        leveled = prog.add_experience(150)
        assert leveled is True
        assert prog.level == 2
        assert prog.experience == 50
        assert prog.experience_to_next == 150  # 100 * 1.5


class TestToolXPRewards:
    """Tests for tool XP rewards."""

    def test_read_gives_1_xp(self):
        """Test Read tool gives 1 XP."""
        assert TOOL_XP_REWARDS["Read"] == 1

    def test_write_gives_3_xp(self):
        """Test Write tool gives 3 XP."""
        assert TOOL_XP_REWARDS["Write"] == 3

    def test_task_gives_5_xp(self):
        """Test Task tool gives 5 XP."""
        assert TOOL_XP_REWARDS["Task"] == 5


class TestGameState:
    """Tests for GameState class."""

    def test_game_state_creation(self, basic_game_state):
        """Test creating a game state."""
        assert basic_game_state.world.name == "test-world"
        assert basic_game_state.main_agent is not None
        assert basic_game_state.session_active is True

    def test_game_state_copy(self, basic_game_state):
        """Test copying game state."""
        state_copy = basic_game_state.copy()
        state_copy.resources.tokens = 999
        assert basic_game_state.resources.tokens == 0
