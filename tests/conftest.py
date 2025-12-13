"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest
import numpy as np
from pathlib import Path

from claude_world.types import (
    Position,
    Velocity,
    AnimationState,
    Entity,
    EntityType,
    AgentEntity,
    AgentActivity,
    AgentMood,
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
)


@pytest.fixture
def basic_sprite() -> Sprite:
    """Create a basic sprite for testing."""
    return Sprite(
        id="test_sprite",
        path="test.png",
        width=64,
        height=64,
        anchor=(32, 60),
        animations={
            "idle": Animation(
                name="idle",
                frames=[
                    AnimationFrame(region=(0, 0, 64, 64), duration_ms=500),
                    AnimationFrame(region=(64, 0, 64, 64), duration_ms=500),
                ],
                loop=True,
            ),
            "walk": Animation(
                name="walk",
                frames=[
                    AnimationFrame(region=(0, 64, 64, 64), duration_ms=150),
                    AnimationFrame(region=(64, 64, 64, 64), duration_ms=150),
                    AnimationFrame(region=(128, 64, 64, 64), duration_ms=150),
                    AnimationFrame(region=(192, 64, 64, 64), duration_ms=150),
                ],
                loop=True,
            ),
            "once": Animation(
                name="once",
                frames=[
                    AnimationFrame(region=(0, 0, 64, 64), duration_ms=100),
                    AnimationFrame(region=(64, 0, 64, 64), duration_ms=100),
                ],
                loop=False,
            ),
        },
    )


@pytest.fixture
def basic_entity(basic_sprite) -> Entity:
    """Create a basic entity for testing."""
    return Entity(
        id="test_entity",
        type=EntityType.DECORATION,
        position=Position(100, 100),
        velocity=Velocity(0, 0),
        sprite_id=basic_sprite.id,
        animation=AnimationState(current_animation="idle"),
    )


@pytest.fixture
def basic_agent(basic_sprite) -> AgentEntity:
    """Create a basic agent entity for testing."""
    return AgentEntity(
        id="main_agent",
        type=EntityType.MAIN_AGENT,
        position=Position(500, 500),
        velocity=Velocity(0, 0),
        sprite_id=basic_sprite.id,
        animation=AnimationState(current_animation="idle"),
        agent_type=None,
        activity=AgentActivity.IDLE,
        mood=AgentMood.NEUTRAL,
    )


@pytest.fixture
def basic_world_state() -> WorldState:
    """Create a basic world state for testing."""
    terrain = TerrainData(
        heightmap=np.zeros((100, 100)),
        tiles=np.zeros((100, 100), dtype=np.int32),
        decorations=[],
    )
    return WorldState(
        name="test-world",
        width=1920,
        height=1080,
        terrain=terrain,
        water_offset=0.0,
        weather=WeatherState(type="clear", intensity=0.0, wind_direction=0.0, wind_speed=0.0),
        time_of_day=TimeOfDay(hour=12.0),
        ambient_light=(255, 255, 255),
    )


@pytest.fixture
def basic_game_state(basic_world_state, basic_agent) -> GameState:
    """Create a basic game state for testing."""
    return GameState(
        world=basic_world_state,
        entities={basic_agent.id: basic_agent},
        main_agent=basic_agent,
        particles=[],
        resources=Resources(),
        progression=Progression(),
        camera=Camera(x=500, y=500),
        session_active=True,
    )
