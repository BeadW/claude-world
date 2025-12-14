"""Entity types for game objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .sprites import Sprite, AnimationFrame


class EntityType(Enum):
    """Types of entities in the game."""

    MAIN_AGENT = "main_agent"
    SUB_AGENT = "sub_agent"
    DECORATION = "decoration"
    PARTICLE = "particle"


class AgentActivity(Enum):
    """Activities an agent can be performing."""

    IDLE = "idle"
    THINKING = "thinking"
    READING = "reading"
    WRITING = "writing"
    SEARCHING = "searching"
    BUILDING = "building"
    EXPLORING = "exploring"
    COMMUNICATING = "communicating"
    RESTING = "resting"
    CELEBRATING = "celebrating"


class AgentMood(Enum):
    """Moods an agent can have."""

    NEUTRAL = "neutral"
    FOCUSED = "focused"
    EXCITED = "excited"
    SATISFIED = "satisfied"
    CONFUSED = "confused"
    TIRED = "tired"


class AgentStatus(Enum):
    """Status of an agent's current task."""

    WORKING = "working"
    COMPLETE = "complete"
    ERROR = "error"
    IDLE = "idle"


@dataclass
class Position:
    """2D position in the world."""

    x: float
    y: float

    def copy(self) -> "Position":
        """Create a copy of this position."""
        return Position(self.x, self.y)


@dataclass
class Velocity:
    """2D velocity vector."""

    x: float = 0.0
    y: float = 0.0

    def copy(self) -> "Velocity":
        """Create a copy of this velocity."""
        return Velocity(self.x, self.y)


@dataclass
class AnimationState:
    """Current state of an entity's animation."""

    current_animation: str
    current_frame: int = 0
    frame_time: float = 0.0
    playing: bool = True
    speed: float = 1.0

    def update(self, dt: float, sprite: "Sprite") -> None:  # noqa: F821
        """Advance animation by dt seconds."""
        if not self.playing:
            return

        anim = sprite.animations.get(self.current_animation)
        if not anim or not anim.frames:
            return

        self.frame_time += dt * self.speed * 1000  # Convert to ms
        frame = anim.frames[self.current_frame]

        if self.frame_time >= frame.duration_ms:
            self.frame_time = 0
            self.current_frame += 1

            if self.current_frame >= len(anim.frames):
                if anim.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = len(anim.frames) - 1
                    self.playing = False

    def play(self, animation_name: str, restart: bool = False) -> None:
        """Start playing an animation."""
        if self.current_animation != animation_name or restart:
            self.current_animation = animation_name
            self.current_frame = 0
            self.frame_time = 0
            self.playing = True

    def get_current_frame(self, sprite: "Sprite") -> "AnimationFrame":  # noqa: F821
        """Get the current frame data."""
        anim = sprite.animations.get(self.current_animation)
        if anim and anim.frames:
            return anim.frames[min(self.current_frame, len(anim.frames) - 1)]
        # Return a default frame if animation not found
        from .sprites import AnimationFrame

        return AnimationFrame(region=(0, 0, sprite.width, sprite.height), duration_ms=1000)

    def copy(self) -> "AnimationState":
        """Create a copy of this animation state."""
        return AnimationState(
            current_animation=self.current_animation,
            current_frame=self.current_frame,
            frame_time=self.frame_time,
            playing=self.playing,
            speed=self.speed,
        )


@dataclass
class Entity:
    """Base entity in the game world."""

    id: str
    type: EntityType
    position: Position
    velocity: Velocity
    sprite_id: str
    animation: AnimationState
    z_offset: float = 0.0
    scale: float = 1.0
    opacity: float = 1.0
    linked_claude_id: Optional[str] = None

    def copy(self) -> "Entity":
        """Create a copy of this entity."""
        return Entity(
            id=self.id,
            type=self.type,
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            sprite_id=self.sprite_id,
            animation=self.animation.copy(),
            z_offset=self.z_offset,
            scale=self.scale,
            opacity=self.opacity,
            linked_claude_id=self.linked_claude_id,
        )


@dataclass
class AgentEntity(Entity):
    """An agent entity with additional agent-specific properties."""

    agent_type: Optional[str] = None
    activity: AgentActivity = AgentActivity.IDLE
    mood: AgentMood = AgentMood.NEUTRAL
    status: AgentStatus = AgentStatus.IDLE  # Task completion status
    energy: float = 100.0
    experience: int = 0
    tools_used: list[str] = field(default_factory=list)
    current_tool: Optional[str] = None  # Current tool being used (for activity verb display)
    last_tool: Optional[str] = None  # Last tool used (for minimum display time)
    last_tool_time: float = 0.0  # Timestamp when last tool started
    status_timer: float = 0.0  # Timer for status display (e.g., show "complete" for 2 seconds)

    # Movement system
    target_position: Optional[Position] = None  # Where Claude is walking to
    move_speed: float = 150.0  # Pixels per second
    is_walking: bool = False
    facing_direction: int = 1  # 1 = right, -1 = left
    current_location: str = "center"  # Named location in the world

    def set_activity(self, activity: AgentActivity) -> None:
        """Change activity and update animation."""
        self.activity = activity
        animation_name = ACTIVITY_ANIMATIONS.get(activity, "idle")
        self.animation.play(animation_name)

    def copy(self) -> "AgentEntity":
        """Create a copy of this agent entity."""
        return AgentEntity(
            id=self.id,
            type=self.type,
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            sprite_id=self.sprite_id,
            animation=self.animation.copy(),
            z_offset=self.z_offset,
            scale=self.scale,
            opacity=self.opacity,
            linked_claude_id=self.linked_claude_id,
            agent_type=self.agent_type,
            activity=self.activity,
            mood=self.mood,
            status=self.status,
            energy=self.energy,
            experience=self.experience,
            tools_used=self.tools_used.copy(),
            current_tool=self.current_tool,
            last_tool=self.last_tool,
            last_tool_time=self.last_tool_time,
            status_timer=self.status_timer,
            target_position=self.target_position.copy() if self.target_position else None,
            move_speed=self.move_speed,
            is_walking=self.is_walking,
            facing_direction=self.facing_direction,
            current_location=self.current_location,
        )


# Tool → Activity mapping
TOOL_ACTIVITY_MAP: dict[str, AgentActivity] = {
    "Read": AgentActivity.READING,
    "Write": AgentActivity.WRITING,
    "Edit": AgentActivity.WRITING,
    "Grep": AgentActivity.SEARCHING,
    "Glob": AgentActivity.SEARCHING,
    "Bash": AgentActivity.BUILDING,
    "Task": AgentActivity.EXPLORING,
    "WebFetch": AgentActivity.COMMUNICATING,
    "WebSearch": AgentActivity.COMMUNICATING,
}

# Activity → Animation mapping
ACTIVITY_ANIMATIONS: dict[AgentActivity, str] = {
    AgentActivity.IDLE: "idle",
    AgentActivity.THINKING: "thinking",
    AgentActivity.READING: "reading",
    AgentActivity.WRITING: "writing",
    AgentActivity.SEARCHING: "searching",
    AgentActivity.BUILDING: "building",
    AgentActivity.EXPLORING: "walk_right",
    AgentActivity.COMMUNICATING: "communicating",
    AgentActivity.RESTING: "resting",
    AgentActivity.CELEBRATING: "excited",
}
