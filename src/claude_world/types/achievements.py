"""Achievement definitions and tracking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .world import GameState


class AchievementCategory(Enum):
    """Categories of achievements."""
    TOOLS = "tools"
    PROGRESSION = "progression"
    EXPLORATION = "exploration"
    SOCIAL = "social"
    MASTERY = "mastery"


@dataclass
class Achievement:
    """An achievement definition."""
    id: str
    name: str
    description: str
    icon: str  # Emoji or symbol
    category: AchievementCategory
    hidden: bool = False  # Hidden until unlocked

    def check(self, state: "GameState") -> bool:
        """Check if achievement should be unlocked. Override in subclasses."""
        return False


@dataclass
class ToolCountAchievement(Achievement):
    """Achievement for using tools a certain number of times."""
    required_count: int = 1
    tool_name: Optional[str] = None  # None = any tool

    def check(self, state: "GameState") -> bool:
        if self.tool_name:
            count = state.progression.tool_usage_breakdown.get(self.tool_name, 0)
        else:
            count = state.progression.total_tools_used
        return count >= self.required_count


@dataclass
class LevelAchievement(Achievement):
    """Achievement for reaching a certain level."""
    required_level: int = 1

    def check(self, state: "GameState") -> bool:
        return state.progression.level >= self.required_level


@dataclass
class SubagentAchievement(Achievement):
    """Achievement for spawning subagents."""
    required_count: int = 1

    def check(self, state: "GameState") -> bool:
        return state.progression.total_subagents_spawned >= self.required_count


@dataclass
class TokenAchievement(Achievement):
    """Achievement for earning tokens."""
    required_count: int = 1

    def check(self, state: "GameState") -> bool:
        return state.resources.tokens >= self.required_count


# Achievement definitions
ACHIEVEMENTS: dict[str, Achievement] = {
    # Tools category
    "first_steps": ToolCountAchievement(
        id="first_steps",
        name="First Steps",
        description="Use your first tool",
        icon="🔧",
        category=AchievementCategory.TOOLS,
        required_count=1,
    ),
    "reader": ToolCountAchievement(
        id="reader",
        name="Bookworm",
        description="Read 10 files",
        icon="📚",
        category=AchievementCategory.TOOLS,
        required_count=10,
        tool_name="Read",
    ),
    "writer": ToolCountAchievement(
        id="writer",
        name="Wordsmith",
        description="Write or edit 10 files",
        icon="✏️",
        category=AchievementCategory.TOOLS,
        required_count=10,
        tool_name="Write",
    ),
    "searcher": ToolCountAchievement(
        id="searcher",
        name="Detective",
        description="Search 20 times with Grep or Glob",
        icon="🔍",
        category=AchievementCategory.TOOLS,
        required_count=20,
        tool_name="Grep",
    ),
    "power_user": ToolCountAchievement(
        id="power_user",
        name="Power User",
        description="Use 100 tools total",
        icon="⚡",
        category=AchievementCategory.TOOLS,
        required_count=100,
    ),
    "centurion": ToolCountAchievement(
        id="centurion",
        name="Centurion",
        description="Use 500 tools total",
        icon="🏛️",
        category=AchievementCategory.TOOLS,
        required_count=500,
    ),

    # Progression category
    "level_2": LevelAchievement(
        id="level_2",
        name="Getting Started",
        description="Reach level 2",
        icon="⭐",
        category=AchievementCategory.PROGRESSION,
        required_level=2,
    ),
    "level_5": LevelAchievement(
        id="level_5",
        name="Apprentice",
        description="Reach level 5",
        icon="🌟",
        category=AchievementCategory.PROGRESSION,
        required_level=5,
    ),
    "level_10": LevelAchievement(
        id="level_10",
        name="Journeyman",
        description="Reach level 10",
        icon="💫",
        category=AchievementCategory.PROGRESSION,
        required_level=10,
    ),
    "level_20": LevelAchievement(
        id="level_20",
        name="Expert",
        description="Reach level 20",
        icon="✨",
        category=AchievementCategory.PROGRESSION,
        required_level=20,
    ),
    "level_50": LevelAchievement(
        id="level_50",
        name="Master",
        description="Reach level 50",
        icon="👑",
        category=AchievementCategory.PROGRESSION,
        required_level=50,
        hidden=True,
    ),

    # Social category (subagents)
    "delegation": SubagentAchievement(
        id="delegation",
        name="Delegation",
        description="Spawn your first subagent",
        icon="🤝",
        category=AchievementCategory.SOCIAL,
        required_count=1,
    ),
    "team_builder": SubagentAchievement(
        id="team_builder",
        name="Team Builder",
        description="Spawn 10 subagents",
        icon="👥",
        category=AchievementCategory.SOCIAL,
        required_count=10,
    ),
    "manager": SubagentAchievement(
        id="manager",
        name="Manager",
        description="Spawn 50 subagents",
        icon="🏢",
        category=AchievementCategory.SOCIAL,
        required_count=50,
    ),

    # Tokens/resources
    "savings": TokenAchievement(
        id="savings",
        name="Savings Account",
        description="Earn 100 tokens",
        icon="💰",
        category=AchievementCategory.MASTERY,
        required_count=100,
    ),
    "wealthy": TokenAchievement(
        id="wealthy",
        name="Wealthy",
        description="Earn 1000 tokens",
        icon="💎",
        category=AchievementCategory.MASTERY,
        required_count=1000,
    ),
}


@dataclass
class AchievementPopup:
    """A popup notification for an unlocked achievement."""
    achievement: Achievement
    lifetime: float
    max_lifetime: float = 4.0

    @property
    def is_dead(self) -> bool:
        return self.lifetime <= 0

    @property
    def progress(self) -> float:
        """Animation progress 0 to 1."""
        return 1.0 - (self.lifetime / self.max_lifetime)

    def update(self, dt: float) -> None:
        self.lifetime -= dt

    def copy(self) -> "AchievementPopup":
        return AchievementPopup(
            achievement=self.achievement,
            lifetime=self.lifetime,
            max_lifetime=self.max_lifetime,
        )


def check_achievements(state: "GameState") -> list[Achievement]:
    """Check all achievements and return newly unlocked ones."""
    newly_unlocked = []

    for achievement_id, achievement in ACHIEVEMENTS.items():
        # Skip if already unlocked
        if achievement_id in state.progression.achievements:
            continue

        # Check if achievement should be unlocked
        if achievement.check(state):
            newly_unlocked.append(achievement)
            state.progression.achievements.add(achievement_id)

    return newly_unlocked
