"""Type definitions for Claude World."""

from .claude_events import (
    ClaudeEvent,
    ClaudeEventType,
    ToolEventPayload,
    AgentSpawnPayload,
    AgentCompletePayload,
    UserPromptPayload,
)
from .entities import (
    Entity,
    EntityType,
    AgentEntity,
    AgentActivity,
    AgentMood,
    Position,
    Velocity,
    AnimationState,
    TOOL_ACTIVITY_MAP,
    ACTIVITY_ANIMATIONS,
)
from .world import (
    GameState,
    WorldState,
    TerrainType,
    TerrainData,
    TimeOfDay,
    WeatherState,
    Camera,
    Resources,
    Progression,
    Particle,
    TOOL_XP_REWARDS,
)
from .sprites import (
    Sprite,
    Animation,
    AnimationFrame,
)

__all__ = [
    # Claude events
    "ClaudeEvent",
    "ClaudeEventType",
    "ToolEventPayload",
    "AgentSpawnPayload",
    "AgentCompletePayload",
    "UserPromptPayload",
    # Entities
    "Entity",
    "EntityType",
    "AgentEntity",
    "AgentActivity",
    "AgentMood",
    "Position",
    "Velocity",
    "AnimationState",
    "TOOL_ACTIVITY_MAP",
    "ACTIVITY_ANIMATIONS",
    # World
    "GameState",
    "WorldState",
    "TerrainType",
    "TerrainData",
    "TimeOfDay",
    "WeatherState",
    "Camera",
    "Resources",
    "Progression",
    "Particle",
    "TOOL_XP_REWARDS",
    # Sprites
    "Sprite",
    "Animation",
    "AnimationFrame",
]
