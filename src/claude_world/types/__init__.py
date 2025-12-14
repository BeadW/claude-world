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
    AgentStatus,
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
    ApiCostTracker,
    Progression,
    Particle,
    FloatingText,
    TOOL_XP_REWARDS,
)
from .sprites import (
    Sprite,
    Animation,
    AnimationFrame,
)
from .achievements import (
    Achievement,
    AchievementCategory,
    AchievementPopup,
    ACHIEVEMENTS,
    check_achievements,
)
from .milestones import (
    Milestone,
    MilestoneCategory,
    MilestonePopup,
    MilestoneReward,
    MilestoneRewardType,
    MILESTONES,
    check_milestones,
    get_unlocked_worlds,
    get_next_milestone,
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
    "AgentStatus",
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
    "ApiCostTracker",
    "Progression",
    "Particle",
    "FloatingText",
    "TOOL_XP_REWARDS",
    # Sprites
    "Sprite",
    "Animation",
    "AnimationFrame",
    # Achievements
    "Achievement",
    "AchievementCategory",
    "AchievementPopup",
    "ACHIEVEMENTS",
    "check_achievements",
    # Milestones
    "Milestone",
    "MilestoneCategory",
    "MilestonePopup",
    "MilestoneReward",
    "MilestoneRewardType",
    "MILESTONES",
    "check_milestones",
    "get_unlocked_worlds",
    "get_next_milestone",
]
