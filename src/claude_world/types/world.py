"""World and game state types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

import numpy as np

from .entities import Entity, AgentEntity, Position

if TYPE_CHECKING:
    from .entities import Velocity


class TerrainType(Enum):
    """Types of terrain tiles."""

    DEEP_WATER = 0
    SHALLOW_WATER = 1
    SAND = 2
    GRASS = 3
    DIRT = 4
    ROCK = 5


@dataclass
class TerrainData:
    """Terrain information for the world."""

    heightmap: np.ndarray
    tiles: np.ndarray
    decorations: list[dict] = field(default_factory=list)


@dataclass
class TimeOfDay:
    """Time of day in the game world."""

    hour: float  # 0-24

    @property
    def phase(self) -> str:
        """Get the current phase of day."""
        if 5 <= self.hour < 7:
            return "dawn"
        elif 7 <= self.hour < 17:
            return "day"
        elif 17 <= self.hour < 19:
            return "dusk"
        else:
            return "night"

    @property
    def sun_angle(self) -> float:
        """Sun angle for lighting calculations."""
        return (self.hour - 6) / 12 * 180  # 0 at 6am, 180 at 6pm

    def copy(self) -> "TimeOfDay":
        """Create a copy."""
        return TimeOfDay(hour=self.hour)


@dataclass
class WeatherState:
    """Current weather conditions."""

    type: str  # 'clear', 'cloudy', 'rain', 'storm'
    intensity: float  # 0.0 - 1.0
    wind_direction: float  # Degrees
    wind_speed: float

    def copy(self) -> "WeatherState":
        """Create a copy."""
        return WeatherState(
            type=self.type,
            intensity=self.intensity,
            wind_direction=self.wind_direction,
            wind_speed=self.wind_speed,
        )


@dataclass
class WorldState:
    """State of the game world."""

    name: str
    width: int
    height: int
    terrain: TerrainData
    water_offset: float
    weather: WeatherState
    time_of_day: TimeOfDay
    ambient_light: tuple[int, int, int]

    def copy(self) -> "WorldState":
        """Create a copy."""
        return WorldState(
            name=self.name,
            width=self.width,
            height=self.height,
            terrain=TerrainData(
                heightmap=self.terrain.heightmap.copy(),
                tiles=self.terrain.tiles.copy(),
                decorations=self.terrain.decorations.copy(),
            ),
            water_offset=self.water_offset,
            weather=self.weather.copy(),
            time_of_day=self.time_of_day.copy(),
            ambient_light=self.ambient_light,
        )


@dataclass
class Camera:
    """Camera for viewport control."""

    x: float
    y: float
    zoom: float = 1.0
    target: Optional[str] = None  # Entity ID to follow
    smooth_factor: float = 0.1

    def update(self, dt: float, entities: dict[str, Entity]) -> None:
        """Update camera position."""
        if self.target and self.target in entities:
            target_entity = entities[self.target]
            target_x = target_entity.position.x
            target_y = target_entity.position.y

            # Smooth follow
            self.x += (target_x - self.x) * self.smooth_factor
            self.y += (target_y - self.y) * self.smooth_factor

    def world_to_screen(
        self, pos: Position, screen_size: tuple[int, int]
    ) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        screen_w, screen_h = screen_size
        screen_x = int((pos.x - self.x) * self.zoom + screen_w / 2)
        screen_y = int((pos.y - self.y) * self.zoom + screen_h / 2)
        return screen_x, screen_y

    def copy(self) -> "Camera":
        """Create a copy."""
        return Camera(
            x=self.x,
            y=self.y,
            zoom=self.zoom,
            target=self.target,
            smooth_factor=self.smooth_factor,
        )


@dataclass
class ApiCostTracker:
    """Tracks actual API costs from Claude Code usage."""

    # Cost rates per million tokens (Opus 4 pricing) - class constants
    INPUT_COST_PER_M: float = field(default=15.0, init=False, repr=False)
    OUTPUT_COST_PER_M: float = field(default=75.0, init=False, repr=False)
    CACHE_READ_COST_PER_M: float = field(default=1.5, init=False, repr=False)
    CACHE_WRITE_COST_PER_M: float = field(default=18.75, init=False, repr=False)

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    def add_usage(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> None:
        """Add token usage and update cost."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_tokens += cache_read
        self.cache_write_tokens += cache_write

        # Calculate cost
        cost = (
            (input_tokens / 1_000_000) * self.INPUT_COST_PER_M
            + (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_M
            + (cache_read / 1_000_000) * self.CACHE_READ_COST_PER_M
            + (cache_write / 1_000_000) * self.CACHE_WRITE_COST_PER_M
        )
        self.total_cost_usd += cost

    def copy(self) -> "ApiCostTracker":
        """Create a copy."""
        return ApiCostTracker(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens,
            total_cost_usd=self.total_cost_usd,
        )


@dataclass
class Resources:
    """Resources earned through Claude interactions."""

    tokens: int = 0
    insights: int = 0
    connections: int = 0
    unlocked_decorations: set[str] = field(default_factory=set)
    unlocked_structures: set[str] = field(default_factory=set)
    unlocked_islands: set[str] = field(default_factory=lambda: {"tropical-island"})
    api_costs: ApiCostTracker = field(default_factory=ApiCostTracker)

    def copy(self) -> "Resources":
        """Create a copy."""
        return Resources(
            tokens=self.tokens,
            insights=self.insights,
            connections=self.connections,
            unlocked_decorations=self.unlocked_decorations.copy(),
            unlocked_structures=self.unlocked_structures.copy(),
            unlocked_islands=self.unlocked_islands.copy(),
            api_costs=self.api_costs.copy(),
        )


@dataclass
class Progression:
    """Player progression and statistics."""

    level: int = 1
    experience: int = 0
    experience_to_next: int = 100
    total_tools_used: int = 0
    total_subagents_spawned: int = 0
    total_session_time: float = 0
    tool_usage_breakdown: dict[str, int] = field(default_factory=dict)
    skill_levels: dict[str, int] = field(
        default_factory=lambda: {
            "reading": 1,
            "writing": 1,
            "searching": 1,
            "building": 1,
        }
    )
    achievements: set[str] = field(default_factory=set)
    milestones: set[str] = field(default_factory=set)
    # Visual feedback state
    level_up_timer: float = 0.0  # Time remaining for level-up celebration
    display_xp: float = 0.0  # Smoothly animated XP display
    xp_gain_flash: float = 0.0  # Flash timer when gaining XP

    @property
    def experience_to_next_level(self) -> int:
        """Alias for experience_to_next."""
        return self.experience_to_next

    def add_experience(self, amount: int) -> bool:
        """Add experience, returns True if leveled up."""
        self.experience += amount
        self.xp_gain_flash = 0.5  # Flash for 0.5 seconds
        if self.experience >= self.experience_to_next:
            self.level += 1
            self.experience -= self.experience_to_next
            self.experience_to_next = int(self.experience_to_next * 1.5)
            self.level_up_timer = 3.0  # Celebrate for 3 seconds
            return True
        return False

    def get_upgrade_cost(self, skill: str) -> int:
        """Get the token cost to upgrade a skill."""
        current_level = self.skill_levels.get(skill, 1)
        return current_level * 50  # 50 tokens per level

    def upgrade_skill(self, skill: str, tokens_available: int) -> tuple[bool, str]:
        """Try to upgrade a skill.

        Returns:
            Tuple of (success, message).
        """
        if skill not in self.skill_levels:
            return False, f"Unknown skill: {skill}"

        cost = self.get_upgrade_cost(skill)
        if tokens_available < cost:
            return False, f"Need {cost} tokens (have {tokens_available})"

        self.skill_levels[skill] += 1
        return True, f"{skill.title()} upgraded to level {self.skill_levels[skill]}!"

    def copy(self) -> "Progression":
        """Create a copy."""
        result = Progression(
            level=self.level,
            experience=self.experience,
            experience_to_next=self.experience_to_next,
            total_tools_used=self.total_tools_used,
            total_subagents_spawned=self.total_subagents_spawned,
            total_session_time=self.total_session_time,
            tool_usage_breakdown=self.tool_usage_breakdown.copy(),
            skill_levels=self.skill_levels.copy(),
            level_up_timer=self.level_up_timer,
            display_xp=self.display_xp,
            xp_gain_flash=self.xp_gain_flash,
        )
        result.achievements = self.achievements.copy()
        result.milestones = self.milestones.copy()
        return result


# Experience rewards for tool usage
TOOL_XP_REWARDS: dict[str, int] = {
    "Read": 1,
    "Write": 3,
    "Edit": 2,
    "Grep": 1,
    "Glob": 1,
    "Bash": 2,
    "Task": 5,
    "WebFetch": 2,
    "WebSearch": 2,
}


@dataclass
class Particle:
    """A particle for visual effects."""

    position: Position
    velocity: "Velocity"  # noqa: F821
    lifetime: float
    max_lifetime: float
    sprite: str
    color: tuple[int, int, int]
    scale: float = 1.0

    @property
    def is_dead(self) -> bool:
        """Check if particle has expired."""
        return self.lifetime <= 0

    def copy(self) -> "Particle":
        """Create a copy."""
        from .entities import Velocity

        return Particle(
            position=self.position.copy(),
            velocity=Velocity(self.velocity.x, self.velocity.y),
            lifetime=self.lifetime,
            max_lifetime=self.max_lifetime,
            sprite=self.sprite,
            color=self.color,
            scale=self.scale,
        )


@dataclass
class FloatingText:
    """A floating text popup for visual feedback (e.g., +5 XP)."""

    text: str
    position: Position
    color: tuple[int, int, int]
    lifetime: float
    max_lifetime: float
    velocity_y: float = -50.0  # Floats upward
    scale: float = 1.0

    @property
    def is_dead(self) -> bool:
        """Check if text has expired."""
        return self.lifetime <= 0

    @property
    def alpha(self) -> float:
        """Get alpha based on lifetime (fade out)."""
        return min(1.0, self.lifetime / self.max_lifetime)

    def update(self, dt: float) -> None:
        """Update position and lifetime."""
        self.position.y += self.velocity_y * dt
        self.lifetime -= dt

    def copy(self) -> "FloatingText":
        """Create a copy."""
        return FloatingText(
            text=self.text,
            position=self.position.copy(),
            color=self.color,
            lifetime=self.lifetime,
            max_lifetime=self.max_lifetime,
            velocity_y=self.velocity_y,
            scale=self.scale,
        )


@dataclass
class GameState:
    """Complete game state."""

    world: WorldState
    entities: dict[str, Entity]
    main_agent: AgentEntity
    particles: list[Particle]
    floating_texts: list[FloatingText] = field(default_factory=list)
    achievement_popups: list = field(default_factory=list)  # list[AchievementPopup]
    milestone_popups: list = field(default_factory=list)  # list[MilestonePopup]
    resources: Resources = field(default_factory=Resources)
    progression: Progression = field(default_factory=Progression)
    camera: Camera = field(default_factory=lambda: Camera(x=0, y=0))
    session_active: bool = False

    def copy(self) -> "GameState":
        """Create a deep copy of the game state."""
        return GameState(
            world=self.world.copy(),
            entities={k: v.copy() for k, v in self.entities.items()},
            main_agent=self.main_agent.copy(),
            particles=[p.copy() for p in self.particles],
            floating_texts=[ft.copy() for ft in self.floating_texts],
            achievement_popups=[p.copy() for p in self.achievement_popups],
            milestone_popups=[p.copy() for p in self.milestone_popups],
            resources=self.resources.copy(),
            progression=self.progression.copy(),
            camera=self.camera.copy(),
            session_active=self.session_active,
        )

    def spawn_floating_text(
        self,
        text: str,
        color: tuple[int, int, int],
        offset_x: float = 0,
        offset_y: float = -30,
    ) -> None:
        """Spawn a floating text popup near the main agent."""
        import random
        pos = Position(
            self.main_agent.position.x + offset_x + random.uniform(-20, 20),
            self.main_agent.position.y + offset_y,
        )
        self.floating_texts.append(FloatingText(
            text=text,
            position=pos,
            color=color,
            lifetime=1.5,
            max_lifetime=1.5,
            velocity_y=-40.0,
            scale=1.0,
        ))
