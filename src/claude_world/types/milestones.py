"""Milestone definitions and tracking for Claude World."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .world import GameState


class MilestoneCategory(Enum):
    """Categories of milestones."""

    PROGRESSION = "progression"
    TOOLS = "tools"
    SOCIAL = "social"
    MASTERY = "mastery"


class MilestoneRewardType(Enum):
    """Types of rewards for milestones."""

    WORLD_UNLOCK = "world_unlock"
    VISUAL_EFFECT = "visual_effect"
    FEATURE_UNLOCK = "feature_unlock"


@dataclass
class MilestoneReward:
    """A reward granted when a milestone is reached."""

    type: MilestoneRewardType
    value: str  # World name, effect name, or feature name
    description: str


@dataclass
class Milestone:
    """A milestone that can be reached in the game."""

    id: str
    name: str
    description: str
    category: MilestoneCategory
    icon: str
    check: Callable[["GameState"], bool]
    reward: MilestoneReward


@dataclass
class MilestonePopup:
    """A popup shown when a milestone is reached."""

    milestone: Milestone
    lifetime: float
    max_lifetime: float

    def update(self, dt: float) -> None:
        """Update the popup lifetime."""
        self.lifetime -= dt

    @property
    def is_dead(self) -> bool:
        """Check if the popup should be removed."""
        return self.lifetime <= 0

    @property
    def progress(self) -> float:
        """Get the animation progress (0 to 1)."""
        return 1 - (self.lifetime / self.max_lifetime)


# Define all milestones
MILESTONES: dict[str, Milestone] = {
    # Progression milestones
    "novice": Milestone(
        id="novice",
        name="Novice",
        description="Reach level 2",
        category=MilestoneCategory.PROGRESSION,
        icon="🌱",
        check=lambda state: state.progression.level >= 2,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="enhanced_particles",
            description="Enhanced particle effects",
        ),
    ),
    "explorer": Milestone(
        id="explorer",
        name="Explorer",
        description="Reach level 5",
        category=MilestoneCategory.PROGRESSION,
        icon="🏔️",
        check=lambda state: state.progression.level >= 5,
        reward=MilestoneReward(
            type=MilestoneRewardType.WORLD_UNLOCK,
            value="mountain-peak",
            description="Unlock Mountain Peak world",
        ),
    ),
    "veteran": Milestone(
        id="veteran",
        name="Veteran",
        description="Reach level 10",
        category=MilestoneCategory.PROGRESSION,
        icon="💻",
        check=lambda state: state.progression.level >= 10,
        reward=MilestoneReward(
            type=MilestoneRewardType.WORLD_UNLOCK,
            value="digital-grid",
            description="Unlock Digital Grid world",
        ),
    ),
    "master": Milestone(
        id="master",
        name="Master",
        description="Reach level 20",
        category=MilestoneCategory.PROGRESSION,
        icon="☁️",
        check=lambda state: state.progression.level >= 20,
        reward=MilestoneReward(
            type=MilestoneRewardType.WORLD_UNLOCK,
            value="cloud-kingdom",
            description="Unlock Cloud Kingdom world",
        ),
    ),
    # Tool milestones
    "architect": Milestone(
        id="architect",
        name="Architect",
        description="Use Write/Edit 50 times",
        category=MilestoneCategory.TOOLS,
        icon="🏗️",
        check=lambda state: (
            state.progression.tool_usage_breakdown.get("Write", 0)
            + state.progression.tool_usage_breakdown.get("Edit", 0)
        )
        >= 50,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="building_decorations",
            description="Building decoration particles",
        ),
    ),
    "researcher": Milestone(
        id="researcher",
        name="Researcher",
        description="Use Read/Grep/Glob 100 times",
        category=MilestoneCategory.TOOLS,
        icon="🔬",
        check=lambda state: (
            state.progression.tool_usage_breakdown.get("Read", 0)
            + state.progression.tool_usage_breakdown.get("Grep", 0)
            + state.progression.tool_usage_breakdown.get("Glob", 0)
        )
        >= 100,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="research_sparkles",
            description="Research sparkle effects",
        ),
    ),
    "commander": Milestone(
        id="commander",
        name="Commander",
        description="Use Bash 75 times",
        category=MilestoneCategory.TOOLS,
        icon="⚡",
        check=lambda state: state.progression.tool_usage_breakdown.get("Bash", 0) >= 75,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="command_lightning",
            description="Lightning command effects",
        ),
    ),
    # Social milestones
    "networker": Milestone(
        id="networker",
        name="Networker",
        description="Spawn 10 subagents",
        category=MilestoneCategory.SOCIAL,
        icon="🔗",
        check=lambda state: state.progression.total_subagents_spawned >= 10,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="connection_colors",
            description="Colored connection lines",
        ),
    ),
    "orchestrator": Milestone(
        id="orchestrator",
        name="Orchestrator",
        description="Spawn 50 subagents",
        category=MilestoneCategory.SOCIAL,
        icon="🎭",
        check=lambda state: state.progression.total_subagents_spawned >= 50,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="agent_auras",
            description="Agent aura effects",
        ),
    ),
    # Mastery milestones
    "tool_master": Milestone(
        id="tool_master",
        name="Tool Master",
        description="Use 500 tools total",
        category=MilestoneCategory.MASTERY,
        icon="🛠️",
        check=lambda state: state.progression.total_tools_used >= 500,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="tool_mastery_glow",
            description="Tool mastery glow effect",
        ),
    ),
    "legend": Milestone(
        id="legend",
        name="Legend",
        description="Reach level 30",
        category=MilestoneCategory.MASTERY,
        icon="👑",
        check=lambda state: state.progression.level >= 30,
        reward=MilestoneReward(
            type=MilestoneRewardType.VISUAL_EFFECT,
            value="legendary_aura",
            description="Legendary golden aura",
        ),
    ),
}


def check_milestones(state: "GameState") -> list[Milestone]:
    """Check all milestones and return newly reached ones.

    Args:
        state: Current game state.

    Returns:
        List of newly reached milestones.
    """
    newly_reached = []

    for milestone_id, milestone in MILESTONES.items():
        # Skip already reached milestones
        if milestone_id in state.progression.milestones:
            continue

        # Check if milestone is reached
        if milestone.check(state):
            newly_reached.append(milestone)
            state.progression.milestones.add(milestone_id)

    return newly_reached


def get_unlocked_worlds(state: "GameState") -> list[str]:
    """Get list of worlds unlocked based on milestones.

    Args:
        state: Current game state.

    Returns:
        List of unlocked world names.
    """
    # Tropical island is always available
    unlocked = ["tropical-island"]

    for milestone_id in state.progression.milestones:
        milestone = MILESTONES.get(milestone_id)
        if milestone and milestone.reward.type == MilestoneRewardType.WORLD_UNLOCK:
            unlocked.append(milestone.reward.value)

    return unlocked


def get_next_milestone(state: "GameState") -> Optional[Milestone]:
    """Get the next milestone the player is closest to reaching.

    Args:
        state: Current game state.

    Returns:
        The next milestone, or None if all are reached.
    """
    # Check progression milestones first (most visible)
    level_milestones = [
        ("novice", 2),
        ("explorer", 5),
        ("veteran", 10),
        ("master", 20),
        ("legend", 30),
    ]

    for milestone_id, required_level in level_milestones:
        if milestone_id not in state.progression.milestones:
            return MILESTONES[milestone_id]

    # Check other milestones
    for milestone_id, milestone in MILESTONES.items():
        if milestone_id not in state.progression.milestones:
            return milestone

    return None
