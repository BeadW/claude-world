# Claude World - Technical Specification

## Overview

Claude World is an interactive terminal application that combines:
1. A **Claude Code plugin** that captures events and state changes
2. A **wrapper application** that renders a split terminal view
3. An **animated game world** (idle game) powered by **Notcurses** for maximum visual fidelity

The game is purely driven by interacting with Claude agents - no direct game controls exist.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Terminal Window                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│                         NOTCURSES RENDERING LAYER                                │
│                    (Sixel/Kitty images, 24-bit color)                           │
│                                                                                  │
│     [PNG sprite]          [Animated Claude]           [PNG sprite]              │
│        🌴                    character                    🌴                     │
│                          with smooth walk                                        │
│                                                                                  │
│     ≋≋≋≋≋≋≋≋≋≋≋≋≋≋ GPU-rendered water animation ≋≋≋≋≋≋≋≋≋≋≋≋≋≋                │
│                                                                                  │
│                    [Particle effects, weather, lighting]                         │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                           CLAUDE INTERFACE                                       │
│               (PTY passthrough - startup screen filtered)                        │
│                                                                                  │
│  > User prompt here...                                                           │
│  Claude response with tool usage...                                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Core Runtime** | Python 3.11+ | Best Notcurses bindings, good PTY support |
| **Rendering** | Notcurses | GPU-accelerated, Sixel/Kitty, 24-bit color |
| **Sprites** | PNG with transparency | Real artwork, smooth scaling |
| **PTY Management** | pyte + pty | Terminal emulation and Claude passthrough |
| **IPC** | Unix domain sockets | Low-latency event bridge |
| **Game Loop** | asyncio | Non-blocking event handling |

### Component Diagram

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Claude Code     │     │  Event Bridge    │     │  Game Engine     │
│  (with plugin)   │────▶│  (Unix Socket)   │────▶│  (Python)        │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                           │
                                                           ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Claude PTY      │◀────│  Main App        │◀────│  Notcurses       │
│  (claude CLI)    │     │  (Compositor)    │     │  Renderer        │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

---

## Notcurses Rendering Architecture

### Plane Hierarchy

Notcurses uses z-ordered "planes" for compositing:

```python
# Plane stack (bottom to top)
PLANES = {
    'sky':        {'z': 0,  'description': 'Sky gradient, day/night cycle'},
    'background': {'z': 10, 'description': 'Distant terrain, clouds'},
    'water':      {'z': 20, 'description': 'Animated ocean'},
    'terrain':    {'z': 30, 'description': 'Island ground, sand, grass'},
    'structures': {'z': 40, 'description': 'Huts, dock, rocks'},
    'vegetation': {'z': 50, 'description': 'Palm trees, bushes'},
    'entities':   {'z': 60, 'description': 'Claude agents'},
    'effects':    {'z': 70, 'description': 'Particles, sparkles'},
    'weather':    {'z': 80, 'description': 'Rain, lightning'},
    'ui':         {'z': 90, 'description': 'Status bar, indicators'},
}
```

### Sprite System

```python
@dataclass
class Sprite:
    """A sprite backed by actual image data."""
    id: str
    path: Path                      # Path to PNG/GIF
    width: int                      # Pixels
    height: int                     # Pixels
    anchor: tuple[int, int]         # Origin point (x, y)
    animations: dict[str, Animation]

@dataclass
class Animation:
    """Sprite animation sequence."""
    name: str
    frames: list[AnimationFrame]
    loop: bool = True

@dataclass
class AnimationFrame:
    """Single frame of animation."""
    region: tuple[int, int, int, int]  # x, y, w, h in spritesheet
    duration_ms: int

# Example: Claude main agent sprite
CLAUDE_SPRITE = Sprite(
    id='claude_main',
    path=Path('assets/sprites/claude_agent.png'),
    width=64,
    height=64,
    anchor=(32, 60),  # Bottom center
    animations={
        'idle': Animation('idle', frames=[...], loop=True),
        'walk_right': Animation('walk_right', frames=[...], loop=True),
        'walk_left': Animation('walk_left', frames=[...], loop=True),
        'thinking': Animation('thinking', frames=[...], loop=True),
        'reading': Animation('reading', frames=[...], loop=True),
        'writing': Animation('writing', frames=[...], loop=True),
        'excited': Animation('excited', frames=[...], loop=False),
        'tired': Animation('tired', frames=[...], loop=True),
    }
)
```

### Rendering Pipeline

```python
class NotcursesRenderer:
    """GPU-accelerated renderer using Notcurses."""

    def __init__(self, nc: Notcurses):
        self.nc = nc
        self.stdplane = nc.stdplane()
        self.planes: dict[str, Plane] = {}
        self.visuals: dict[str, Visual] = {}
        self.sprite_cache: dict[str, NcVisual] = {}

    async def render_frame(self, state: GameState) -> None:
        """Render a complete frame."""
        # 1. Update sky gradient based on time of day
        self._render_sky(state.world.time_of_day)

        # 2. Render water with animation offset
        self._render_water(state.world.water_offset)

        # 3. Render static terrain
        self._render_terrain(state.world.terrain)

        # 4. Render all entities sorted by y-position
        entities_sorted = sorted(
            state.entities.values(),
            key=lambda e: e.position.y
        )
        for entity in entities_sorted:
            self._render_entity(entity)

        # 5. Render particle effects
        for particle in state.particles:
            self._render_particle(particle)

        # 6. Render weather overlay
        if state.world.weather.type != 'clear':
            self._render_weather(state.world.weather)

        # 7. Render UI overlay
        self._render_ui(state)

        # 8. Composite and display
        self.nc.render()

    def _render_entity(self, entity: Entity) -> None:
        """Render an entity with its current animation frame."""
        sprite = self.sprite_cache.get(entity.sprite_id)
        if not sprite:
            sprite = self._load_sprite(entity.sprite_id)

        # Get current animation frame
        anim = entity.animation
        frame = anim.get_current_frame()

        # Position sprite (convert world coords to screen)
        screen_x, screen_y = self._world_to_screen(entity.position)

        # Blit sprite to entity plane
        sprite.blit(
            self.planes['entities'],
            x=screen_x - sprite.anchor[0],
            y=screen_y - sprite.anchor[1],
            region=frame.region
        )
```

### Visual Effects

```python
class ParticleSystem:
    """GPU-friendly particle system."""

    def __init__(self, renderer: NotcursesRenderer):
        self.renderer = renderer
        self.particles: list[Particle] = []
        self.emitters: list[ParticleEmitter] = []

    def emit(self, effect_type: EffectType, position: Position) -> None:
        """Spawn particles for an effect."""
        config = EFFECT_CONFIGS[effect_type]
        emitter = ParticleEmitter(
            position=position,
            config=config,
            lifetime=config.duration
        )
        self.emitters.append(emitter)

    def update(self, dt: float) -> None:
        """Update all particles."""
        # Update emitters
        for emitter in self.emitters[:]:
            emitter.update(dt)
            self.particles.extend(emitter.spawn(dt))
            if emitter.is_dead:
                self.emitters.remove(emitter)

        # Update particles
        for particle in self.particles[:]:
            particle.update(dt)
            if particle.is_dead:
                self.particles.remove(particle)

@dataclass
class EffectConfig:
    """Configuration for a particle effect."""
    sprite: str                     # Particle sprite
    count: tuple[int, int]          # Min/max particles
    lifetime: tuple[float, float]   # Particle lifetime range
    velocity: tuple[float, float]   # Initial velocity range
    gravity: float                  # Gravity acceleration
    fade: bool                      # Fade out over lifetime
    color_start: tuple[int, int, int]
    color_end: tuple[int, int, int]
    duration: float                 # Emitter duration

EFFECT_CONFIGS = {
    EffectType.SPARKLE: EffectConfig(
        sprite='particle_star',
        count=(5, 10),
        lifetime=(0.3, 0.8),
        velocity=(50, 100),
        gravity=-20,  # Float upward
        fade=True,
        color_start=(255, 255, 200),
        color_end=(255, 200, 100),
        duration=0.5
    ),
    EffectType.WRITE_BURST: EffectConfig(
        sprite='particle_code',
        count=(10, 20),
        lifetime=(0.5, 1.0),
        velocity=(30, 80),
        gravity=50,
        fade=True,
        color_start=(100, 200, 255),
        color_end=(50, 100, 200),
        duration=0.3
    ),
    # ... more effects
}
```

---

## Data Structures

### 1. Claude Events (Plugin → Game Engine)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any

class ClaudeEventType(Enum):
    SESSION_START = 'SESSION_START'
    SESSION_END = 'SESSION_END'
    TOOL_START = 'TOOL_START'
    TOOL_COMPLETE = 'TOOL_COMPLETE'
    AGENT_SPAWN = 'AGENT_SPAWN'
    AGENT_COMPLETE = 'AGENT_COMPLETE'
    USER_PROMPT = 'USER_PROMPT'
    AGENT_THINKING = 'AGENT_THINKING'
    AGENT_IDLE = 'AGENT_IDLE'
    NOTIFICATION = 'NOTIFICATION'

@dataclass
class ClaudeEvent:
    type: ClaudeEventType
    timestamp: float
    session_id: str
    payload: dict[str, Any]

@dataclass
class ToolEventPayload:
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    tool_response: Optional[dict[str, Any]] = None

@dataclass
class AgentSpawnPayload:
    agent_id: str
    agent_type: str               # "Explore", "Plan", "general-purpose"
    description: str
    parent_agent_id: Optional[str] = None

@dataclass
class AgentCompletePayload:
    agent_id: str
    success: bool

@dataclass
class UserPromptPayload:
    prompt: str
    prompt_length: int
```

### 2. Game State

```python
@dataclass
class GameState:
    world: WorldState
    entities: dict[str, Entity]
    main_agent: AgentEntity
    particles: list[Particle]
    resources: Resources
    time: GameTime
    camera: Camera

@dataclass
class WorldState:
    name: str                           # "tropical-island"
    width: int                          # World width in pixels
    height: int                         # World height in pixels
    terrain: TerrainData
    water_offset: float                 # Animation offset
    weather: WeatherState
    time_of_day: TimeOfDay
    ambient_light: tuple[int, int, int] # RGB ambient color

@dataclass
class TerrainData:
    heightmap: np.ndarray              # Elevation data
    tiles: np.ndarray                  # Tile type indices
    decorations: list[Decoration]      # Static decorations

class TerrainType(Enum):
    DEEP_WATER = 0
    SHALLOW_WATER = 1
    SAND = 2
    GRASS = 3
    DIRT = 4
    ROCK = 5

@dataclass
class TimeOfDay:
    hour: float                        # 0-24

    @property
    def phase(self) -> str:
        if 5 <= self.hour < 7:
            return 'dawn'
        elif 7 <= self.hour < 17:
            return 'day'
        elif 17 <= self.hour < 19:
            return 'dusk'
        else:
            return 'night'

    @property
    def sun_angle(self) -> float:
        """Sun angle for lighting calculations."""
        return (self.hour - 6) / 12 * 180  # 0° at 6am, 180° at 6pm

@dataclass
class WeatherState:
    type: str                          # 'clear', 'cloudy', 'rain', 'storm'
    intensity: float                   # 0.0 - 1.0
    wind_direction: float              # Degrees
    wind_speed: float
```

### 3. Entity System

```python
@dataclass
class Entity:
    id: str
    type: EntityType
    position: Position
    velocity: Velocity
    sprite_id: str
    animation: AnimationState
    z_offset: float = 0               # For jumping/hovering
    scale: float = 1.0
    opacity: float = 1.0
    linked_claude_id: Optional[str] = None

class EntityType(Enum):
    MAIN_AGENT = 'main_agent'
    SUB_AGENT = 'sub_agent'
    DECORATION = 'decoration'
    PARTICLE = 'particle'

@dataclass
class Position:
    x: float
    y: float

@dataclass
class Velocity:
    x: float = 0
    y: float = 0

@dataclass
class AgentEntity(Entity):
    agent_type: Optional[str] = None  # Claude subagent type
    activity: AgentActivity = AgentActivity.IDLE
    mood: AgentMood = AgentMood.NEUTRAL
    energy: float = 100.0             # 0-100
    experience: int = 0
    tools_used: list[str] = field(default_factory=list)

    def set_activity(self, activity: AgentActivity) -> None:
        """Change activity and update animation."""
        self.activity = activity
        self.animation.play(ACTIVITY_ANIMATIONS[activity])

class AgentActivity(Enum):
    IDLE = 'idle'
    THINKING = 'thinking'
    READING = 'reading'
    WRITING = 'writing'
    SEARCHING = 'searching'
    BUILDING = 'building'
    EXPLORING = 'exploring'
    COMMUNICATING = 'communicating'
    RESTING = 'resting'
    CELEBRATING = 'celebrating'

class AgentMood(Enum):
    NEUTRAL = 'neutral'
    FOCUSED = 'focused'
    EXCITED = 'excited'
    SATISFIED = 'satisfied'
    CONFUSED = 'confused'
    TIRED = 'tired'

# Tool → Activity mapping
TOOL_ACTIVITY_MAP = {
    'Read': AgentActivity.READING,
    'Write': AgentActivity.WRITING,
    'Edit': AgentActivity.WRITING,
    'Grep': AgentActivity.SEARCHING,
    'Glob': AgentActivity.SEARCHING,
    'Bash': AgentActivity.BUILDING,
    'Task': AgentActivity.EXPLORING,
    'WebFetch': AgentActivity.COMMUNICATING,
    'WebSearch': AgentActivity.COMMUNICATING,
}

# Activity → Animation mapping
ACTIVITY_ANIMATIONS = {
    AgentActivity.IDLE: 'idle',
    AgentActivity.THINKING: 'thinking',
    AgentActivity.READING: 'reading',
    AgentActivity.WRITING: 'writing',
    AgentActivity.SEARCHING: 'searching',
    AgentActivity.BUILDING: 'building',
    AgentActivity.EXPLORING: 'walk_right',
    AgentActivity.COMMUNICATING: 'communicating',
    AgentActivity.RESTING: 'resting',
    AgentActivity.CELEBRATING: 'excited',
}
```

### 4. Animation State

```python
@dataclass
class AnimationState:
    current_animation: str
    current_frame: int
    frame_time: float                 # Time in current frame
    playing: bool = True
    speed: float = 1.0

    def update(self, dt: float, sprite: Sprite) -> None:
        """Advance animation by dt seconds."""
        if not self.playing:
            return

        anim = sprite.animations.get(self.current_animation)
        if not anim:
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

    def get_current_frame(self, sprite: Sprite) -> AnimationFrame:
        """Get the current frame data."""
        anim = sprite.animations[self.current_animation]
        return anim.frames[self.current_frame]
```

### 5. Resources & Progression

```python
@dataclass
class Resources:
    # Earned through Claude interactions
    tokens: int = 0                   # From tool usage
    insights: int = 0                 # From completed tasks
    connections: int = 0              # From spawned subagents

    # Unlockables
    unlocked_decorations: set[str] = field(default_factory=set)
    unlocked_structures: set[str] = field(default_factory=set)
    unlocked_islands: set[str] = field(default_factory=lambda: {'tropical-island'})

@dataclass
class Progression:
    level: int = 1
    experience: int = 0
    experience_to_next: int = 100

    # Statistics
    total_tools_used: int = 0
    total_subagents_spawned: int = 0
    total_session_time: float = 0
    tool_usage_breakdown: dict[str, int] = field(default_factory=dict)

    def add_experience(self, amount: int) -> bool:
        """Add experience, returns True if leveled up."""
        self.experience += amount
        if self.experience >= self.experience_to_next:
            self.level += 1
            self.experience -= self.experience_to_next
            self.experience_to_next = int(self.experience_to_next * 1.5)
            return True
        return False

# Experience rewards
TOOL_XP_REWARDS = {
    'Read': 1,
    'Write': 3,
    'Edit': 2,
    'Grep': 1,
    'Glob': 1,
    'Bash': 2,
    'Task': 5,
    'WebFetch': 2,
    'WebSearch': 2,
}
```

### 6. Camera System

```python
@dataclass
class Camera:
    """Camera for viewport control."""
    x: float                          # World position
    y: float
    zoom: float = 1.0
    target: Optional[str] = None      # Entity ID to follow
    smooth_factor: float = 0.1        # Lerp factor for following

    def update(self, dt: float, entities: dict[str, Entity]) -> None:
        """Update camera position."""
        if self.target and self.target in entities:
            target_entity = entities[self.target]
            target_x = target_entity.position.x
            target_y = target_entity.position.y

            # Smooth follow
            self.x += (target_x - self.x) * self.smooth_factor
            self.y += (target_y - self.y) * self.smooth_factor

    def world_to_screen(self, pos: Position, screen_size: tuple[int, int]) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        screen_w, screen_h = screen_size
        screen_x = int((pos.x - self.x) * self.zoom + screen_w / 2)
        screen_y = int((pos.y - self.y) * self.zoom + screen_h / 2)
        return screen_x, screen_y
```

---

## Plugin Specification

### Directory Structure

```
claude-world-plugin/
├── .claude-plugin/
│   └── plugin.json
├── hooks/
│   └── hooks.json
├── scripts/
│   ├── event_bridge.py           # Main hook handler
│   └── requirements.txt
└── README.md
```

### plugin.json

```json
{
  "name": "claude-world",
  "version": "1.0.0",
  "description": "Captures Claude events for the Claude World game",
  "author": {
    "name": "Claude World"
  },
  "hooks": "./hooks/hooks.json"
}
```

### hooks.json

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/event_bridge.py session_start"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/event_bridge.py session_end"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/event_bridge.py tool_start"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/event_bridge.py tool_complete"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/event_bridge.py agent_idle"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/event_bridge.py subagent_complete"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/event_bridge.py user_prompt"
          }
        ]
      }
    ]
  }
}
```

### Event Bridge Script

```python
#!/usr/bin/env python3
"""
event_bridge.py - Bridges Claude hooks to the game engine via Unix socket.
"""

import json
import socket
import sys
import os
from pathlib import Path

SOCKET_PATH = os.environ.get('CLAUDE_WORLD_SOCKET', '/tmp/claude-world.sock')

def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    event_type = sys.argv[1]

    # Read JSON from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        input_data = {}

    # Transform to game event
    event = transform_event(event_type, input_data)

    # Send to game engine (non-blocking, fail silently)
    try:
        if Path(SOCKET_PATH).exists():
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            sock.connect(SOCKET_PATH)
            sock.sendall((json.dumps(event) + '\n').encode())
            sock.close()
    except:
        pass  # Don't block Claude if game isn't running

    # Always exit 0 to not block Claude
    sys.exit(0)

def transform_event(event_type: str, input_data: dict) -> dict:
    """Transform Claude hook data to game event."""

    type_map = {
        'session_start': 'SESSION_START',
        'session_end': 'SESSION_END',
        'tool_start': 'TOOL_START',
        'tool_complete': 'TOOL_COMPLETE',
        'subagent_complete': 'AGENT_COMPLETE',
        'agent_idle': 'AGENT_IDLE',
        'user_prompt': 'USER_PROMPT',
    }

    event = {
        'type': type_map.get(event_type, event_type.upper()),
        'timestamp': input_data.get('timestamp', 0),
        'session_id': input_data.get('session_id', ''),
        'payload': {}
    }

    # Extract tool-specific data
    if event_type in ('tool_start', 'tool_complete'):
        event['payload'] = {
            'tool_name': input_data.get('tool_name'),
            'tool_input': input_data.get('tool_input', {}),
            'tool_use_id': input_data.get('tool_use_id'),
        }
        if event_type == 'tool_complete':
            event['payload']['tool_response'] = input_data.get('tool_response')

        # Detect subagent spawn
        if input_data.get('tool_name') == 'Task':
            tool_input = input_data.get('tool_input', {})
            event['spawn_event'] = {
                'type': 'AGENT_SPAWN',
                'payload': {
                    'agent_id': input_data.get('tool_use_id'),
                    'agent_type': tool_input.get('subagent_type', 'general-purpose'),
                    'description': tool_input.get('description', ''),
                }
            }

    elif event_type == 'user_prompt':
        prompt = input_data.get('prompt', '')
        event['payload'] = {
            'prompt': prompt,
            'prompt_length': len(prompt),
        }

    elif event_type == 'subagent_complete':
        event['payload'] = {
            'agent_id': input_data.get('tool_use_id', ''),
            'success': True,
        }

    return event

if __name__ == '__main__':
    main()
```

---

## Main Application

### Entry Point

```python
#!/usr/bin/env python3
"""
claude_world.py - Main application entry point.
"""

import asyncio
import argparse
import signal
from pathlib import Path

from claude_world.app import ClaudeWorldApp
from claude_world.config import Config

def main():
    parser = argparse.ArgumentParser(description='Claude World')
    parser.add_argument('claude_args', nargs='*', help='Arguments to pass to claude')
    parser.add_argument('--config', type=Path, help='Config file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    config = Config.load(args.config)
    if args.debug:
        config.debug = True

    app = ClaudeWorldApp(config, args.claude_args)

    # Handle signals
    loop = asyncio.new_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(app.shutdown()))

    try:
        loop.run_until_complete(app.run())
    finally:
        loop.close()

if __name__ == '__main__':
    main()
```

### Application Class

```python
"""
app.py - Main application orchestrator.
"""

import asyncio
import os
import pty
import struct
import fcntl
import termios
from pathlib import Path

import notcurses
from notcurses import Notcurses, NotcursesOptions

from .config import Config
from .engine import GameEngine
from .renderer import NotcursesRenderer
from .ipc import EventServer
from .pty_manager import PtyManager
from .startup_filter import StartupFilter

SOCKET_PATH = '/tmp/claude-world.sock'

class ClaudeWorldApp:
    def __init__(self, config: Config, claude_args: list[str]):
        self.config = config
        self.claude_args = claude_args
        self.running = False

        # Components (initialized in run())
        self.nc: Notcurses = None
        self.renderer: NotcursesRenderer = None
        self.engine: GameEngine = None
        self.event_server: EventServer = None
        self.pty_manager: PtyManager = None

    async def run(self) -> None:
        """Main application loop."""
        self.running = True

        # Initialize Notcurses
        opts = NotcursesOptions()
        opts.flags = (
            notcurses.NCOPTION_SUPPRESS_BANNERS |
            notcurses.NCOPTION_NO_ALTERNATE_SCREEN
        )
        self.nc = Notcurses(opts)

        try:
            # Get terminal dimensions
            term_height, term_width = self.nc.stdplane().dim_yx()

            # Calculate split: 40% game, 60% claude
            game_height = int(term_height * self.config.game_view_ratio)
            claude_height = term_height - game_height

            # Create game plane (top portion)
            game_plane = self.nc.stdplane().create(
                rows=game_height,
                cols=term_width,
                y=0,
                x=0
            )

            # Create Claude plane (bottom portion)
            claude_plane = self.nc.stdplane().create(
                rows=claude_height,
                cols=term_width,
                y=game_height,
                x=0
            )

            # Initialize components
            self.renderer = NotcursesRenderer(self.nc, game_plane, self.config)
            self.engine = GameEngine(self.config)
            self.event_server = EventServer(SOCKET_PATH)
            self.event_server.on_event = self.handle_claude_event

            # Start PTY for Claude
            self.pty_manager = PtyManager(
                command='claude',
                args=self.claude_args,
                env={'CLAUDE_WORLD_SOCKET': SOCKET_PATH},
                output_plane=claude_plane,
                size=(claude_height, term_width)
            )

            # Start all tasks
            await asyncio.gather(
                self.event_server.start(),
                self.pty_manager.start(),
                self.game_loop(),
                self.input_loop(),
            )

        finally:
            await self.cleanup()

    async def game_loop(self) -> None:
        """Main game rendering loop at 30 FPS."""
        target_frame_time = 1.0 / 30  # 30 FPS
        last_time = asyncio.get_event_loop().time()

        while self.running:
            current_time = asyncio.get_event_loop().time()
            dt = current_time - last_time
            last_time = current_time

            # Update game state
            self.engine.update(dt)

            # Render frame
            state = self.engine.get_state()
            await self.renderer.render_frame(state)

            # Sleep to maintain frame rate
            elapsed = asyncio.get_event_loop().time() - current_time
            sleep_time = max(0, target_frame_time - elapsed)
            await asyncio.sleep(sleep_time)

    async def input_loop(self) -> None:
        """Handle keyboard input."""
        while self.running:
            # Get input from notcurses (non-blocking)
            key = self.nc.get_nblock()
            if key:
                # Pass most input to Claude PTY
                if key.is_char():
                    self.pty_manager.write(key.char)
                elif key.id == notcurses.NCKEY_ENTER:
                    self.pty_manager.write('\r')
                elif key.id == notcurses.NCKEY_BACKSPACE:
                    self.pty_manager.write('\x7f')
                # Add special keys as needed

            await asyncio.sleep(0.01)  # 100 Hz input polling

    def handle_claude_event(self, event: dict) -> None:
        """Handle events from Claude plugin."""
        self.engine.dispatch_claude_event(event)

        # Also handle spawn events embedded in tool events
        if 'spawn_event' in event:
            self.engine.dispatch_claude_event(event['spawn_event'])

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self.running = False

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.event_server:
            await self.event_server.stop()
        if self.pty_manager:
            self.pty_manager.stop()
        if self.nc:
            self.nc.stop()
```

### PTY Manager

```python
"""
pty_manager.py - Manages the Claude CLI PTY.
"""

import asyncio
import os
import pty
import select
import struct
import fcntl
import termios
from typing import Callable

from .startup_filter import StartupFilter

class PtyManager:
    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
        output_plane,  # Notcurses plane
        size: tuple[int, int]
    ):
        self.command = command
        self.args = args
        self.env = {**os.environ, **env}
        self.output_plane = output_plane
        self.rows, self.cols = size

        self.master_fd = None
        self.pid = None
        self.startup_filter = StartupFilter()

    async def start(self) -> None:
        """Start the Claude CLI in a PTY."""
        # Create PTY
        self.pid, self.master_fd = pty.fork()

        if self.pid == 0:
            # Child process
            os.execvpe(self.command, [self.command] + self.args, self.env)
        else:
            # Parent process
            # Set PTY size
            winsize = struct.pack('HHHH', self.rows, self.cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

            # Make non-blocking
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Read loop
            await self._read_loop()

    async def _read_loop(self) -> None:
        """Read output from PTY and display."""
        while True:
            try:
                # Check if data available
                r, _, _ = select.select([self.master_fd], [], [], 0.01)
                if r:
                    data = os.read(self.master_fd, 4096)
                    if not data:
                        break

                    # Filter startup screen
                    filtered = self.startup_filter.filter(data.decode('utf-8', errors='replace'))
                    if filtered:
                        self._write_to_plane(filtered)
                else:
                    await asyncio.sleep(0.01)
            except OSError:
                break

    def _write_to_plane(self, text: str) -> None:
        """Write text to the output plane."""
        # Use notcurses to render the text
        self.output_plane.putstr(text)

    def write(self, data: str) -> None:
        """Write input to the PTY."""
        if self.master_fd:
            os.write(self.master_fd, data.encode())

    def resize(self, rows: int, cols: int) -> None:
        """Resize the PTY."""
        if self.master_fd:
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            self.rows, self.cols = rows, cols

    def stop(self) -> None:
        """Stop the PTY."""
        if self.master_fd:
            os.close(self.master_fd)
        if self.pid:
            try:
                os.kill(self.pid, 15)  # SIGTERM
            except:
                pass
```

### Startup Filter

```python
"""
startup_filter.py - Filters out Claude's welcome screen.
"""

import re
from enum import Enum

class FilterState(Enum):
    DETECTING = 'detecting'
    IN_BOX = 'in_box'
    PASSED = 'passed'

class StartupFilter:
    """Filters out Claude Code's startup welcome box."""

    # Box drawing characters that indicate box boundaries
    BOX_TOP_CHARS = {'╭', '┌', '╔'}
    BOX_BOTTOM_CHARS = {'╰', '└', '╚'}

    def __init__(self):
        self.state = FilterState.DETECTING
        self.box_depth = 0
        self.buffer = ''

    def filter(self, chunk: str) -> str:
        """Filter a chunk of PTY output."""
        if self.state == FilterState.PASSED:
            return chunk

        self.buffer += chunk
        result = []

        lines = self.buffer.split('\n')
        # Keep incomplete last line in buffer
        self.buffer = lines[-1] if not self.buffer.endswith('\n') else ''
        complete_lines = lines[:-1] if not chunk.endswith('\n') else lines

        for line in complete_lines:
            if self.state == FilterState.DETECTING:
                # Check for box start
                if any(c in line for c in self.BOX_TOP_CHARS):
                    self.state = FilterState.IN_BOX
                    self.box_depth = 1
                    continue
                result.append(line)

            elif self.state == FilterState.IN_BOX:
                # Check for nested box start
                if any(c in line for c in self.BOX_TOP_CHARS):
                    self.box_depth += 1
                # Check for box end
                elif any(c in line for c in self.BOX_BOTTOM_CHARS):
                    self.box_depth -= 1
                    if self.box_depth == 0:
                        self.state = FilterState.PASSED
                # Skip lines inside box

        return '\n'.join(result) + ('\n' if result else '')
```

---

## Tropical Island World

### World Configuration

```python
"""
worlds/tropical_island/config.py - Tropical island world configuration.
"""

from pathlib import Path

WORLD_CONFIG = {
    'name': 'tropical-island',
    'display_name': 'Tropical Paradise',
    'width': 1920,              # Pixels
    'height': 1080,

    # Asset paths (relative to world directory)
    'assets': {
        'background': 'background.png',
        'terrain_tileset': 'terrain.png',
        'water_animation': 'water.png',
        'decorations': 'decorations.png',
    },

    # Spawn configuration
    'spawn_points': {
        'main_agent': {'x': 960, 'y': 700},
        'sub_agents': [
            {'x': 1100, 'y': 720},
            {'x': 820, 'y': 680},
            {'x': 1000, 'y': 650},
            {'x': 880, 'y': 750},
        ],
    },

    # Walkable area (simplified polygon)
    'walkable_bounds': [
        (600, 500), (1300, 500),
        (1400, 800), (500, 800),
    ],

    # Points of interest
    'locations': {
        'hut': {'x': 960, 'y': 600, 'name': 'Beach Hut'},
        'dock': {'x': 700, 'y': 850, 'name': 'Dock'},
        'palm_grove': {'x': 1150, 'y': 550, 'name': 'Palm Grove'},
    },

    # Ambient settings
    'ambient': {
        'day_cycle_minutes': 10,    # Real minutes per game day
        'weather_change_chance': 0.1,
    },
}

# Day/night color palettes
TIME_PALETTES = {
    'dawn': {
        'sky_top': (255, 180, 150),
        'sky_bottom': (255, 220, 180),
        'ambient': (255, 200, 180),
        'water_tint': (255, 180, 150),
    },
    'day': {
        'sky_top': (135, 206, 235),
        'sky_bottom': (200, 230, 255),
        'ambient': (255, 255, 255),
        'water_tint': (100, 200, 255),
    },
    'dusk': {
        'sky_top': (255, 100, 50),
        'sky_bottom': (255, 180, 100),
        'ambient': (255, 180, 150),
        'water_tint': (255, 150, 100),
    },
    'night': {
        'sky_top': (20, 30, 60),
        'sky_bottom': (40, 50, 80),
        'ambient': (100, 120, 180),
        'water_tint': (50, 80, 120),
        'stars': True,
    },
}
```

### Sprite Definitions

```python
"""
worlds/tropical_island/sprites.py - Sprite definitions.
"""

from claude_world.renderer import Sprite, Animation, AnimationFrame

# Main Claude agent sprite
CLAUDE_MAIN = Sprite(
    id='claude_main',
    path='sprites/claude_main.png',
    width=64,
    height=64,
    anchor=(32, 60),
    animations={
        'idle': Animation('idle', [
            AnimationFrame((0, 0, 64, 64), 500),
            AnimationFrame((64, 0, 64, 64), 500),
        ], loop=True),

        'walk_right': Animation('walk_right', [
            AnimationFrame((0, 64, 64, 64), 150),
            AnimationFrame((64, 64, 64, 64), 150),
            AnimationFrame((128, 64, 64, 64), 150),
            AnimationFrame((192, 64, 64, 64), 150),
        ], loop=True),

        'walk_left': Animation('walk_left', [
            AnimationFrame((0, 128, 64, 64), 150),
            AnimationFrame((64, 128, 64, 64), 150),
            AnimationFrame((128, 128, 64, 64), 150),
            AnimationFrame((192, 128, 64, 64), 150),
        ], loop=True),

        'thinking': Animation('thinking', [
            AnimationFrame((0, 192, 64, 64), 300),
            AnimationFrame((64, 192, 64, 64), 300),
            AnimationFrame((128, 192, 64, 64), 600),
        ], loop=True),

        'reading': Animation('reading', [
            AnimationFrame((0, 256, 64, 64), 800),
            AnimationFrame((64, 256, 64, 64), 200),
        ], loop=True),

        'writing': Animation('writing', [
            AnimationFrame((0, 320, 64, 64), 100),
            AnimationFrame((64, 320, 64, 64), 100),
            AnimationFrame((128, 320, 64, 64), 100),
        ], loop=True),

        'excited': Animation('excited', [
            AnimationFrame((0, 384, 64, 64), 100),
            AnimationFrame((64, 384, 64, 64), 100),
            AnimationFrame((128, 384, 64, 64), 100),
            AnimationFrame((64, 384, 64, 64), 100),
        ], loop=False),

        'searching': Animation('searching', [
            AnimationFrame((0, 448, 64, 64), 200),
            AnimationFrame((64, 448, 64, 64), 200),
            AnimationFrame((128, 448, 64, 64), 400),
        ], loop=True),
    }
)

# Subagent sprites (smaller variants)
SUBAGENT_SPRITES = {
    'Explore': Sprite(
        id='explore_agent',
        path='sprites/explore_agent.png',
        width=48,
        height=48,
        anchor=(24, 44),
        animations={
            'idle': Animation('idle', [
                AnimationFrame((0, 0, 48, 48), 400),
                AnimationFrame((48, 0, 48, 48), 400),
            ], loop=True),
            'walk_right': Animation('walk_right', [
                AnimationFrame((0, 48, 48, 48), 120),
                AnimationFrame((48, 48, 48, 48), 120),
                AnimationFrame((96, 48, 48, 48), 120),
            ], loop=True),
            # ... more animations
        }
    ),

    'Plan': Sprite(
        id='plan_agent',
        path='sprites/plan_agent.png',
        width=48,
        height=48,
        anchor=(24, 44),
        animations={
            # ... animations
        }
    ),

    'general-purpose': Sprite(
        id='general_agent',
        path='sprites/general_agent.png',
        width=48,
        height=48,
        anchor=(24, 44),
        animations={
            # ... animations
        }
    ),
}

# Water animation (tiled)
WATER_SPRITE = Sprite(
    id='water',
    path='sprites/water.png',
    width=64,
    height=64,
    anchor=(0, 0),
    animations={
        'flow': Animation('flow', [
            AnimationFrame((0, 0, 64, 64), 200),
            AnimationFrame((64, 0, 64, 64), 200),
            AnimationFrame((128, 0, 64, 64), 200),
            AnimationFrame((192, 0, 64, 64), 200),
        ], loop=True),
    }
)
```

---

## Testing Strategy

### Test Framework Setup

```python
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.pytest]
markers = [
    "visual: marks tests as visual regression tests",
    "slow: marks tests as slow",
]
```

### Unit Tests

```python
"""
tests/test_game_state.py - Game state unit tests.
"""

import pytest
from claude_world.engine import GameEngine
from claude_world.engine.state import GameState
from claude_world.types import ClaudeEventType

class TestGameEngine:
    def test_initial_state(self):
        engine = GameEngine()
        state = engine.get_state()

        assert state.main_agent is not None
        assert state.main_agent.activity.value == 'idle'
        assert len(state.entities) == 1  # Just main agent

    def test_tool_start_changes_activity(self):
        engine = GameEngine()

        engine.dispatch_claude_event({
            'type': 'TOOL_START',
            'payload': {'tool_name': 'Read'}
        })

        state = engine.get_state()
        assert state.main_agent.activity.value == 'reading'

    def test_agent_spawn_creates_entity(self):
        engine = GameEngine()

        engine.dispatch_claude_event({
            'type': 'AGENT_SPAWN',
            'payload': {
                'agent_id': 'test-agent-1',
                'agent_type': 'Explore',
                'description': 'Test agent'
            }
        })

        state = engine.get_state()
        assert len(state.entities) == 2
        assert 'test-agent-1' in state.entities

        sub_agent = state.entities['test-agent-1']
        assert sub_agent.agent_type == 'Explore'

    def test_agent_complete_removes_entity(self):
        engine = GameEngine()

        # Spawn then complete
        engine.dispatch_claude_event({
            'type': 'AGENT_SPAWN',
            'payload': {'agent_id': 'test-1', 'agent_type': 'Explore'}
        })
        engine.dispatch_claude_event({
            'type': 'AGENT_COMPLETE',
            'payload': {'agent_id': 'test-1', 'success': True}
        })

        state = engine.get_state()
        assert 'test-1' not in state.entities

    def test_tool_awards_resources(self):
        engine = GameEngine()
        initial_tokens = engine.get_state().resources.tokens

        engine.dispatch_claude_event({
            'type': 'TOOL_COMPLETE',
            'payload': {'tool_name': 'Write'}
        })

        state = engine.get_state()
        assert state.resources.tokens > initial_tokens

class TestAnimationState:
    def test_animation_advances(self):
        from claude_world.types import AnimationState
        from claude_world.renderer.sprites import CLAUDE_MAIN

        anim = AnimationState(
            current_animation='idle',
            current_frame=0,
            frame_time=0
        )

        # Advance past first frame
        anim.update(0.6, CLAUDE_MAIN)  # 600ms
        assert anim.current_frame == 1

    def test_animation_loops(self):
        from claude_world.types import AnimationState
        from claude_world.renderer.sprites import CLAUDE_MAIN

        anim = AnimationState(
            current_animation='idle',
            current_frame=1,
            frame_time=400
        )

        # Advance past end
        anim.update(0.2, CLAUDE_MAIN)
        assert anim.current_frame == 0  # Looped back
```

### Visual Regression Tests

```python
"""
tests/test_visual.py - Visual regression tests.
"""

import pytest
from pathlib import Path
import hashlib

from claude_world.renderer import NotcursesRenderer
from claude_world.renderer.headless import HeadlessBackend
from claude_world.engine import GameEngine

GOLDEN_DIR = Path(__file__).parent / 'golden'

class TestVisualRegression:
    @pytest.fixture
    def headless_renderer(self):
        """Create a headless renderer for testing."""
        backend = HeadlessBackend(cols=120, rows=40)
        renderer = NotcursesRenderer(backend)
        return renderer, backend

    @pytest.mark.visual
    def test_initial_render(self, headless_renderer):
        renderer, backend = headless_renderer
        engine = GameEngine()

        state = engine.get_state()
        renderer.render_frame(state)

        output = backend.capture()

        # Compare against golden file
        golden_path = GOLDEN_DIR / 'initial_render.txt'
        if golden_path.exists():
            expected = golden_path.read_text()
            assert output == expected, "Visual regression detected"
        else:
            # Create golden file
            golden_path.write_text(output)

    @pytest.mark.visual
    def test_agent_activity_renders(self, headless_renderer):
        renderer, backend = headless_renderer
        engine = GameEngine()

        # Test each activity renders differently
        activities = ['reading', 'writing', 'searching']
        outputs = {}

        for activity in activities:
            engine.dispatch_claude_event({
                'type': 'TOOL_START',
                'payload': {'tool_name': 'Read' if activity == 'reading' else 'Write'}
            })
            state = engine.get_state()
            renderer.render_frame(state)
            outputs[activity] = backend.capture()

        # Each activity should produce different output
        assert len(set(outputs.values())) == len(activities)

    @pytest.mark.visual
    def test_subagent_spawn_visual(self, headless_renderer):
        renderer, backend = headless_renderer
        engine = GameEngine()

        # Capture before
        state = engine.get_state()
        renderer.render_frame(state)
        before = backend.capture()

        # Spawn agent
        engine.dispatch_claude_event({
            'type': 'AGENT_SPAWN',
            'payload': {
                'agent_id': 'visual-test',
                'agent_type': 'Explore'
            }
        })

        # Capture after
        state = engine.get_state()
        renderer.render_frame(state)
        after = backend.capture()

        assert before != after, "Subagent should be visible"
```

### Headless Backend for Testing

```python
"""
renderer/headless.py - Headless backend for testing.
"""

import numpy as np
from dataclasses import dataclass

@dataclass
class Cell:
    char: str = ' '
    fg: tuple[int, int, int] = (255, 255, 255)
    bg: tuple[int, int, int] = (0, 0, 0)

class HeadlessBackend:
    """Headless notcurses-like backend for testing."""

    def __init__(self, cols: int = 80, rows: int = 24):
        self.cols = cols
        self.rows = rows
        self.buffer: list[list[Cell]] = [
            [Cell() for _ in range(cols)]
            for _ in range(rows)
        ]
        self.planes: list['HeadlessPlane'] = []

    def create_plane(self, rows: int, cols: int, y: int, x: int) -> 'HeadlessPlane':
        plane = HeadlessPlane(rows, cols, y, x, self)
        self.planes.append(plane)
        return plane

    def render(self) -> None:
        """Composite all planes to buffer."""
        # Clear buffer
        for row in self.buffer:
            for cell in row:
                cell.char = ' '

        # Render planes in order
        for plane in sorted(self.planes, key=lambda p: p.z):
            plane.composite_to(self.buffer)

    def capture(self) -> str:
        """Capture current buffer as string."""
        self.render()
        lines = []
        for row in self.buffer:
            line = ''.join(cell.char for cell in row)
            lines.append(line.rstrip())
        return '\n'.join(lines)

    def capture_image(self) -> bytes:
        """Capture as PNG image for visual comparison."""
        from PIL import Image, ImageDraw, ImageFont

        char_width = 8
        char_height = 16

        img = Image.new('RGB', (self.cols * char_width, self.rows * char_height))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 14)
        except:
            font = ImageFont.load_default()

        self.render()
        for y, row in enumerate(self.buffer):
            for x, cell in enumerate(row):
                draw.rectangle(
                    [x * char_width, y * char_height,
                     (x + 1) * char_width, (y + 1) * char_height],
                    fill=cell.bg
                )
                draw.text(
                    (x * char_width, y * char_height),
                    cell.char,
                    fill=cell.fg,
                    font=font
                )

        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

class HeadlessPlane:
    """Headless plane for testing."""

    def __init__(self, rows: int, cols: int, y: int, x: int, backend: HeadlessBackend):
        self.rows = rows
        self.cols = cols
        self.y = y
        self.x = x
        self.z = 0
        self.backend = backend
        self.cells: list[list[Cell]] = [
            [Cell() for _ in range(cols)]
            for _ in range(rows)
        ]

    def putstr(self, y: int, x: int, text: str, fg=None, bg=None) -> None:
        """Write string to plane."""
        for i, char in enumerate(text):
            px = x + i
            if 0 <= y < self.rows and 0 <= px < self.cols:
                self.cells[y][px].char = char
                if fg:
                    self.cells[y][px].fg = fg
                if bg:
                    self.cells[y][px].bg = bg

    def composite_to(self, buffer: list[list[Cell]]) -> None:
        """Composite this plane to the main buffer."""
        for py, row in enumerate(self.cells):
            by = self.y + py
            if 0 <= by < len(buffer):
                for px, cell in enumerate(row):
                    bx = self.x + px
                    if 0 <= bx < len(buffer[by]):
                        if cell.char != ' ':
                            buffer[by][bx] = Cell(
                                char=cell.char,
                                fg=cell.fg,
                                bg=cell.bg
                            )
```

### Integration Test with Mock Claude

```python
"""
tests/test_integration.py - Integration tests with mock Claude session.
"""

import pytest
import asyncio
from pathlib import Path

from claude_world.app import ClaudeWorldApp
from claude_world.config import Config
from tests.mocks import MockClaudeSession

class TestIntegration:
    @pytest.fixture
    async def app(self, tmp_path):
        """Create app with mock Claude."""
        config = Config(
            headless=True,
            socket_path=str(tmp_path / 'test.sock')
        )
        app = ClaudeWorldApp(config, claude_args=[])
        return app

    @pytest.mark.asyncio
    async def test_full_workflow(self, app, tmp_path):
        """Test a complete Claude interaction workflow."""
        # Start app in background
        app_task = asyncio.create_task(app.run())
        await asyncio.sleep(0.5)  # Let it initialize

        try:
            # Create mock session
            mock = MockClaudeSession(str(tmp_path / 'test.sock'))

            # Simulate session start
            await mock.emit_session_start()
            await asyncio.sleep(0.1)

            state = app.engine.get_state()
            assert state.main_agent.activity.value == 'idle'

            # Simulate tool usage
            await mock.emit_tool_start('Read')
            await asyncio.sleep(0.1)

            state = app.engine.get_state()
            assert state.main_agent.activity.value == 'reading'

            # Simulate subagent spawn
            await mock.emit_agent_spawn('test-agent', 'Explore')
            await asyncio.sleep(0.1)

            state = app.engine.get_state()
            assert len(state.entities) == 2

        finally:
            await app.shutdown()
            app_task.cancel()

class MockClaudeSession:
    """Mock Claude session for testing."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    async def emit_session_start(self):
        await self._emit({
            'type': 'SESSION_START',
            'session_id': 'test',
            'payload': {'source': 'startup'}
        })

    async def emit_tool_start(self, tool_name: str):
        await self._emit({
            'type': 'TOOL_START',
            'session_id': 'test',
            'payload': {
                'tool_name': tool_name,
                'tool_input': {},
                'tool_use_id': f'tool-{tool_name}'
            }
        })

    async def emit_agent_spawn(self, agent_id: str, agent_type: str):
        await self._emit({
            'type': 'AGENT_SPAWN',
            'session_id': 'test',
            'payload': {
                'agent_id': agent_id,
                'agent_type': agent_type,
                'description': f'Test {agent_type}'
            }
        })

    async def _emit(self, event: dict):
        import json
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        writer.write((json.dumps(event) + '\n').encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()
```

### Background Test Daemon

```python
"""
tests/daemon.py - Background test daemon for continuous testing.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TestRunner(FileSystemEventHandler):
    def __init__(self):
        self.pending_tests = set()
        self.running = False
        self.lock = asyncio.Lock()

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.py'):
            self.queue_tests(event.src_path)

    def queue_tests(self, changed_file: str):
        path = Path(changed_file)

        # Map source files to tests
        if 'engine' in str(path):
            self.pending_tests.add('tests/test_game_state.py')
        elif 'renderer' in str(path):
            self.pending_tests.add('tests/test_visual.py')
        elif str(path).startswith('tests/'):
            self.pending_tests.add(str(path))
        else:
            self.pending_tests.add('tests/')  # Run all

    async def run_loop(self):
        while True:
            if self.pending_tests and not self.running:
                async with self.lock:
                    tests = list(self.pending_tests)
                    self.pending_tests.clear()
                    self.running = True

                print(f"\n{'='*60}")
                print(f"Running tests: {tests}")
                print('='*60 + '\n')

                proc = await asyncio.create_subprocess_exec(
                    sys.executable, '-m', 'pytest', '-v', *tests,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )

                stdout, _ = await proc.communicate()
                print(stdout.decode())

                self.running = False

            await asyncio.sleep(0.5)

async def main():
    print("Starting test daemon...")

    runner = TestRunner()
    observer = Observer()
    observer.schedule(runner, 'src', recursive=True)
    observer.schedule(runner, 'tests', recursive=True)
    observer.start()

    try:
        await runner.run_loop()
    finally:
        observer.stop()
        observer.join()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## File Structure

```
claude-world/
├── src/
│   └── claude_world/
│       ├── __init__.py
│       ├── __main__.py           # Entry point
│       ├── app.py                # Main application
│       ├── config.py             # Configuration
│       │
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── game_engine.py    # Game loop & state
│       │   ├── state.py          # State management
│       │   ├── entity.py         # Entity system
│       │   ├── claude_mapper.py  # Event mapping
│       │   └── systems/
│       │       ├── movement.py
│       │       ├── animation.py
│       │       ├── weather.py
│       │       └── day_cycle.py
│       │
│       ├── renderer/
│       │   ├── __init__.py
│       │   ├── notcurses_renderer.py
│       │   ├── planes.py
│       │   ├── sprites.py
│       │   ├── particles.py
│       │   ├── effects.py
│       │   └── headless.py       # For testing
│       │
│       ├── pty_manager.py
│       ├── startup_filter.py
│       ├── ipc.py
│       │
│       ├── types/
│       │   ├── __init__.py
│       │   ├── claude_events.py
│       │   ├── game_events.py
│       │   ├── entities.py
│       │   └── world.py
│       │
│       └── worlds/
│           └── tropical_island/
│               ├── __init__.py
│               ├── config.py
│               ├── sprites.py
│               └── terrain.py
│
├── assets/
│   ├── sprites/
│   │   ├── claude_main.png       # Main agent spritesheet
│   │   ├── explore_agent.png     # Explore subagent
│   │   ├── plan_agent.png        # Plan subagent
│   │   ├── general_agent.png     # General subagent
│   │   ├── water.png             # Water animation
│   │   └── particles.png         # Particle effects
│   │
│   └── worlds/
│       └── tropical_island/
│           ├── background.png
│           ├── terrain.png
│           └── decorations.png
│
├── plugin/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── hooks/
│   │   └── hooks.json
│   └── scripts/
│       └── event_bridge.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_game_state.py
│   ├── test_visual.py
│   ├── test_integration.py
│   ├── daemon.py                 # Background test daemon
│   ├── golden/                   # Golden files for visual tests
│   └── mocks/
│       └── __init__.py
│
├── scripts/
│   ├── dev.sh
│   ├── install_plugin.sh
│   └── create_sprites.py         # Sprite sheet generator
│
├── pyproject.toml
├── requirements.txt
├── SPEC.md
├── PLAN.md
└── README.md
```

---

## Configuration

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "claude-world"
version = "0.1.0"
description = "An animated idle game that reacts to Claude Code"
requires-python = ">=3.11"
dependencies = [
    "notcurses>=3.0.0",
    "numpy>=1.24.0",
    "Pillow>=10.0.0",
    "watchdog>=3.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
]

[project.scripts]
claude-world = "claude_world.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/claude_world"]
```

### Config Class

```python
"""
config.py - Application configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json

@dataclass
class Config:
    # Display
    game_view_ratio: float = 0.4         # Portion of screen for game
    fps: int = 30

    # Paths
    assets_path: Path = field(default_factory=lambda: Path(__file__).parent / 'assets')
    world: str = 'tropical-island'

    # IPC
    socket_path: str = '/tmp/claude-world.sock'

    # Debug
    debug: bool = False
    headless: bool = False

    # Persistence
    save_path: Optional[Path] = None
    auto_save: bool = True

    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'Config':
        if path and path.exists():
            with open(path) as f:
                data = json.load(f)
            return cls(**data)

        # Try default locations
        for default_path in [
            Path.home() / '.claude-world' / 'config.json',
            Path.cwd() / '.claude-world.json',
        ]:
            if default_path.exists():
                with open(default_path) as f:
                    data = json.load(f)
                return cls(**data)

        return cls()
```

---

## Art Style Guide

### Claude Character Design

The main Claude agent should follow the iconic Claude logo shape:

```
Reference shape (ASCII):
       ▐▛███▜▌
      ▝▜█████▛▘
        ▘▘ ▝▝

PNG sprite guidelines:
- 64x64 pixels per frame
- Soft, rounded shapes
- Primary color: #D97706 (warm orange)
- Secondary: #FCD34D (soft yellow)
- Friendly, approachable expression
- Subtle gradient shading
```

### Subagent Variants

| Agent Type | Visual Style | Color |
|------------|--------------|-------|
| Explore | Smaller, has magnifying glass | Blue (#3B82F6) |
| Plan | Has clipboard/document | Purple (#8B5CF6) |
| general-purpose | Standard smaller version | Green (#10B981) |

### Animation Principles

- **Idle**: Gentle bobbing, occasional blink
- **Thinking**: Head tilt, thought bubbles
- **Reading**: Looking down, page turn particles
- **Writing**: Arm movement, code particles
- **Excited**: Jump, sparkle effects
- **Walking**: 4-frame walk cycle, smooth

### Environment Style

- **Water**: Animated tiles, wave pattern
- **Sand**: Warm beige, subtle texture
- **Grass**: Vibrant green, sway animation
- **Palm trees**: Coconuts, rustling leaves
- **Hut**: Tiki/beach style
