# Claude World - Implementation Plan

This document provides step-by-step implementation instructions for building Claude World with **maximum visual fidelity** using Notcurses.

See `SPEC.md` for detailed data structures, architecture, and code examples.

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.11+ |
| Rendering | Notcurses 3.0+ (Sixel/Kitty/24-bit) |
| Sprites | PNG spritesheets with transparency |
| PTY | Python `pty` + `asyncio` |
| IPC | Unix domain sockets |
| Testing | pytest + visual regression |

---

## Phase 1: Project Setup

### 1.1 Create Project Structure

```bash
mkdir -p claude-world/{src/claude_world,assets,plugin,tests,scripts}
cd claude-world
```

### 1.2 Initialize Python Project

**Create `pyproject.toml`:**

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
    "ruff>=0.1.0",
]

[project.scripts]
claude-world = "claude_world.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/claude_world"]
```

### 1.3 Create Package Structure

```
src/claude_world/
├── __init__.py
├── __main__.py
├── app.py
├── config.py
├── engine/
│   ├── __init__.py
│   ├── game_engine.py
│   ├── state.py
│   ├── entity.py
│   ├── claude_mapper.py
│   └── systems/
│       ├── __init__.py
│       ├── movement.py
│       ├── animation.py
│       ├── weather.py
│       └── day_cycle.py
├── renderer/
│   ├── __init__.py
│   ├── notcurses_renderer.py
│   ├── planes.py
│   ├── sprites.py
│   ├── particles.py
│   ├── effects.py
│   └── headless.py
├── types/
│   ├── __init__.py
│   ├── claude_events.py
│   ├── game_events.py
│   ├── entities.py
│   └── world.py
├── pty_manager.py
├── startup_filter.py
├── ipc.py
└── worlds/
    └── tropical_island/
        ├── __init__.py
        ├── config.py
        ├── sprites.py
        └── terrain.py
```

### 1.4 Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Verify Notcurses installation:**
```bash
python -c "import notcurses; print(notcurses.__version__)"
```

---

## Phase 2: Type Definitions

### 2.1 Claude Event Types

**File:** `src/claude_world/types/claude_events.py`

Define:
- `ClaudeEventType` enum
- `ClaudeEvent` dataclass
- `ToolEventPayload`, `AgentSpawnPayload`, etc.

### 2.2 Entity Types

**File:** `src/claude_world/types/entities.py`

Define:
- `Entity` base dataclass
- `AgentEntity` with activity/mood
- `AgentActivity` enum (idle, reading, writing, etc.)
- `AgentMood` enum
- `Position`, `Velocity` dataclasses
- `AnimationState` dataclass

### 2.3 World Types

**File:** `src/claude_world/types/world.py`

Define:
- `GameState` aggregate
- `WorldState` with terrain, weather
- `TerrainType` enum
- `TimeOfDay` dataclass
- `WeatherState` dataclass
- `Camera` dataclass

### 2.4 Sprite Types

**File:** `src/claude_world/renderer/sprites.py`

Define:
- `Sprite` dataclass (path, dimensions, anchor)
- `Animation` dataclass
- `AnimationFrame` dataclass

---

## Phase 3: Game Engine

### 3.1 State Management

**File:** `src/claude_world/engine/state.py`

```python
class GameStateManager:
    def __init__(self, world_config: dict):
        self.state = self._create_initial_state(world_config)
        self.listeners: list[Callable] = []

    def get_state(self) -> GameState:
        return self.state

    def update_state(self, updater: Callable[[GameState], GameState]) -> None:
        self.state = updater(self.state)
        self._notify_listeners()

    def subscribe(self, listener: Callable) -> Callable:
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)
```

### 3.2 Entity Manager

**File:** `src/claude_world/engine/entity.py`

Methods:
- `spawn_entity(type, config) -> Entity`
- `remove_entity(id)`
- `update_entity(id, changes)`
- `get_by_type(type) -> list[Entity]`
- `get_by_claude_id(claude_id) -> Entity | None`

### 3.3 Claude Event Mapper

**File:** `src/claude_world/engine/claude_mapper.py`

```python
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

def map_claude_event(event: dict) -> list[GameEvent]:
    """Map a Claude event to game events."""
    event_type = event.get('type')
    payload = event.get('payload', {})

    if event_type == 'TOOL_START':
        tool_name = payload.get('tool_name')
        activity = TOOL_ACTIVITY_MAP.get(tool_name, AgentActivity.BUILDING)
        return [
            GameEvent('CHANGE_ACTIVITY', {'activity': activity}),
            GameEvent('SPAWN_PARTICLES', {'effect': get_tool_effect(tool_name)}),
        ]
    # ... handle other event types
```

### 3.4 Game Engine

**File:** `src/claude_world/engine/game_engine.py`

```python
class GameEngine:
    def __init__(self, config: Config):
        self.config = config
        self.state_manager = GameStateManager(load_world_config(config.world))
        self.entity_manager = EntityManager(self.state_manager)
        self.systems = [
            MovementSystem(),
            AnimationSystem(),
            DayCycleSystem(),
            WeatherSystem(),
        ]

    def update(self, dt: float) -> None:
        """Update all systems."""
        state = self.state_manager.get_state()
        for system in self.systems:
            system.update(state, dt)

    def dispatch_claude_event(self, event: dict) -> None:
        """Handle Claude event."""
        game_events = map_claude_event(event)
        for ge in game_events:
            self._handle_game_event(ge)

    def get_state(self) -> GameState:
        return self.state_manager.get_state()
```

### 3.5 Systems

**Movement System:** `src/claude_world/engine/systems/movement.py`
- Update entity positions based on velocity
- Simple pathfinding for agent wandering
- Collision with walkable bounds

**Animation System:** `src/claude_world/engine/systems/animation.py`
- Advance animation frames
- Trigger animation changes based on activity

**Day/Night Cycle:** `src/claude_world/engine/systems/day_cycle.py`
- Progress time of day
- Update color palettes
- Trigger ambient changes

**Weather System:** `src/claude_world/engine/systems/weather.py`
- Weather state machine
- Particle spawning for rain
- Cloud movement

---

## Phase 4: Notcurses Renderer

### 4.1 Main Renderer

**File:** `src/claude_world/renderer/notcurses_renderer.py`

```python
import notcurses
from notcurses import Notcurses

class NotcursesRenderer:
    def __init__(self, nc: Notcurses, game_plane, config: Config):
        self.nc = nc
        self.game_plane = game_plane
        self.config = config

        # Create layer planes
        self.planes = self._create_planes()

        # Load sprites
        self.sprite_cache: dict[str, notcurses.NcVisual] = {}
        self._preload_sprites()

    def _create_planes(self) -> dict[str, notcurses.NcPlane]:
        """Create z-ordered planes for compositing."""
        planes = {}
        plane_configs = [
            ('sky', 0),
            ('background', 10),
            ('water', 20),
            ('terrain', 30),
            ('structures', 40),
            ('vegetation', 50),
            ('entities', 60),
            ('effects', 70),
            ('weather', 80),
            ('ui', 90),
        ]
        for name, z in plane_configs:
            plane = self.game_plane.create(...)
            plane.move_above(...)  # Set z-order
            planes[name] = plane
        return planes

    async def render_frame(self, state: GameState) -> None:
        """Render a complete frame."""
        self._render_sky(state)
        self._render_water(state)
        self._render_terrain(state)
        self._render_entities(state)
        self._render_effects(state)
        self._render_ui(state)
        self.nc.render()
```

### 4.2 Sprite Loading

```python
def _preload_sprites(self) -> None:
    """Load all sprites into cache."""
    sprite_paths = [
        'sprites/claude_main.png',
        'sprites/explore_agent.png',
        'sprites/plan_agent.png',
        'sprites/water.png',
        'sprites/particles.png',
    ]
    for path in sprite_paths:
        full_path = self.config.assets_path / path
        visual = notcurses.NcVisual.from_file(str(full_path))
        self.sprite_cache[path] = visual

def _render_sprite(
    self,
    plane: notcurses.NcPlane,
    sprite_key: str,
    x: int,
    y: int,
    region: tuple[int, int, int, int] | None = None
) -> None:
    """Render a sprite to a plane."""
    visual = self.sprite_cache[sprite_key]
    vopts = notcurses.NcVisualOptions()
    vopts.n = plane
    vopts.y = y
    vopts.x = x
    if region:
        vopts.begy, vopts.begx = region[1], region[0]
        vopts.leny, vopts.lenx = region[3], region[2]
    visual.blit(self.nc, vopts)
```

### 4.3 Entity Rendering

```python
def _render_entities(self, state: GameState) -> None:
    """Render all entities sorted by y-position."""
    self.planes['entities'].erase()

    # Sort by y for proper layering
    entities = sorted(
        state.entities.values(),
        key=lambda e: e.position.y
    )

    for entity in entities:
        self._render_entity(entity, state.camera)

def _render_entity(self, entity: Entity, camera: Camera) -> None:
    """Render a single entity."""
    sprite = SPRITES[entity.sprite_id]

    # Get current animation frame
    frame = entity.animation.get_current_frame(sprite)

    # World to screen coords
    screen_x, screen_y = camera.world_to_screen(
        entity.position,
        (self.game_plane.dim_x(), self.game_plane.dim_y())
    )

    # Render sprite
    self._render_sprite(
        self.planes['entities'],
        sprite.path,
        screen_x - sprite.anchor[0],
        screen_y - sprite.anchor[1],
        region=frame.region
    )
```

### 4.4 Particle System

**File:** `src/claude_world/renderer/particles.py`

```python
@dataclass
class Particle:
    position: Position
    velocity: Velocity
    lifetime: float
    max_lifetime: float
    sprite: str
    color: tuple[int, int, int]
    scale: float = 1.0

class ParticleSystem:
    def __init__(self):
        self.particles: list[Particle] = []
        self.emitters: list[ParticleEmitter] = []

    def emit(self, effect_type: EffectType, position: Position) -> None:
        config = EFFECT_CONFIGS[effect_type]
        emitter = ParticleEmitter(position, config)
        self.emitters.append(emitter)

    def update(self, dt: float) -> None:
        # Update emitters
        for emitter in self.emitters[:]:
            new_particles = emitter.update(dt)
            self.particles.extend(new_particles)
            if emitter.is_dead:
                self.emitters.remove(emitter)

        # Update particles
        for p in self.particles[:]:
            p.lifetime -= dt
            p.position.x += p.velocity.x * dt
            p.position.y += p.velocity.y * dt
            if p.lifetime <= 0:
                self.particles.remove(p)
```

### 4.5 Headless Backend (for testing)

**File:** `src/claude_world/renderer/headless.py`

Create a mock Notcurses backend that:
- Maintains a character buffer
- Records all render operations
- Can capture output as text or PNG
- Allows visual regression testing

---

## Phase 5: Claude Code Plugin

### 5.1 Plugin Structure

```
plugin/
├── .claude-plugin/
│   └── plugin.json
├── hooks/
│   └── hooks.json
└── scripts/
    └── event_bridge.py
```

### 5.2 Create plugin.json

```json
{
  "name": "claude-world",
  "version": "1.0.0",
  "description": "Captures Claude events for the Claude World game",
  "author": { "name": "Claude World" },
  "hooks": "./hooks/hooks.json"
}
```

### 5.3 Create hooks.json

Configure hooks for:
- `SessionStart`
- `SessionEnd`
- `PreToolUse`
- `PostToolUse`
- `Stop`
- `SubagentStop`
- `UserPromptSubmit`

Each hook calls `event_bridge.py` with the event type.

### 5.4 Event Bridge Script

**File:** `plugin/scripts/event_bridge.py`

- Reads JSON from stdin
- Transforms to game event format
- Sends to Unix socket (non-blocking)
- Always exits 0 to not block Claude

Key transformations:
- `PreToolUse` → `TOOL_START`
- `PostToolUse` → `TOOL_COMPLETE`
- `Task` tool → also emit `AGENT_SPAWN`
- `SubagentStop` → `AGENT_COMPLETE`

---

## Phase 6: Main Application

### 6.1 Entry Point

**File:** `src/claude_world/__main__.py`

- Parse arguments
- Load config
- Create `ClaudeWorldApp`
- Set up signal handlers
- Run asyncio event loop

### 6.2 Application Class

**File:** `src/claude_world/app.py`

```python
class ClaudeWorldApp:
    async def run(self) -> None:
        # 1. Initialize Notcurses
        # 2. Calculate screen split (40% game, 60% claude)
        # 3. Create game and Claude planes
        # 4. Initialize renderer, engine, IPC server
        # 5. Start PTY for Claude CLI
        # 6. Run concurrent tasks:
        #    - game_loop() at 30 FPS
        #    - input_loop() at 100 Hz
        #    - event_server
        #    - pty_manager
```

### 6.3 PTY Manager

**File:** `src/claude_world/pty_manager.py`

- Fork PTY for `claude` command
- Pass environment with `CLAUDE_WORLD_SOCKET`
- Filter startup screen
- Route output to Claude plane
- Pass keyboard input to PTY

### 6.4 Startup Filter

**File:** `src/claude_world/startup_filter.py`

- Detect box-drawing characters (╭, ╰)
- Filter out welcome box
- Pass through all other output

### 6.5 IPC Server

**File:** `src/claude_world/ipc.py`

```python
class EventServer:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.on_event: Callable[[dict], None] = lambda e: None

    async def start(self) -> None:
        # Remove stale socket
        # Create Unix socket server
        # Accept connections
        # Parse JSON events
        # Call on_event callback

    async def stop(self) -> None:
        # Close server
        # Remove socket file
```

---

## Phase 7: Tropical Island World

### 7.1 World Config

**File:** `src/claude_world/worlds/tropical_island/config.py`

- World dimensions (1920x1080)
- Asset paths
- Spawn points (main agent, subagents)
- Walkable bounds polygon
- Points of interest
- Day/night palettes

### 7.2 Terrain Data

**File:** `src/claude_world/worlds/tropical_island/terrain.py`

- Define terrain layout
- Tile types for rendering
- Decoration positions

### 7.3 Sprite Definitions

**File:** `src/claude_world/worlds/tropical_island/sprites.py`

Define sprite configs for:
- `CLAUDE_MAIN` - Main agent (64x64, multiple animations)
- `EXPLORE_AGENT` - Explore subagent (48x48)
- `PLAN_AGENT` - Plan subagent (48x48)
- `GENERAL_AGENT` - General subagent (48x48)
- `WATER_SPRITE` - Animated water tiles

---

## Phase 8: Assets

### 8.1 Create Placeholder Assets

Until real art is created, use placeholder sprites:

```python
# scripts/create_placeholders.py
from PIL import Image, ImageDraw

def create_placeholder_sprite(size, color, output_path):
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw simple shape
    draw.ellipse([8, 8, size[0]-8, size[1]-8], fill=color)
    img.save(output_path)

# Create placeholders
create_placeholder_sprite((64, 64), '#D97706', 'assets/sprites/claude_main.png')
create_placeholder_sprite((48, 48), '#3B82F6', 'assets/sprites/explore_agent.png')
create_placeholder_sprite((48, 48), '#8B5CF6', 'assets/sprites/plan_agent.png')
create_placeholder_sprite((48, 48), '#10B981', 'assets/sprites/general_agent.png')
```

### 8.2 Asset Directory Structure

```
assets/
├── sprites/
│   ├── claude_main.png      # 256x512 spritesheet (4 cols x 8 rows)
│   ├── explore_agent.png    # 144x192 spritesheet
│   ├── plan_agent.png
│   ├── general_agent.png
│   ├── water.png            # 256x64 (4 frame animation)
│   └── particles.png        # Various particle sprites
└── worlds/
    └── tropical_island/
        ├── background.png   # 1920x1080 background
        ├── terrain.png      # Terrain tileset
        └── decorations.png  # Palm trees, rocks, hut
```

---

## Phase 9: Testing

### 9.1 Test Setup

**File:** `tests/conftest.py`

```python
import pytest
from claude_world.engine import GameEngine
from claude_world.renderer.headless import HeadlessBackend

@pytest.fixture
def engine():
    return GameEngine()

@pytest.fixture
def headless_backend():
    return HeadlessBackend(cols=120, rows=40)
```

### 9.2 Unit Tests

**File:** `tests/test_game_state.py`

Test:
- Initial state creation
- Tool events change activity
- Agent spawn creates entity
- Agent complete removes entity
- Resource awards

### 9.3 Visual Regression Tests

**File:** `tests/test_visual.py`

- Render initial state, compare to golden
- Render each activity, verify different output
- Render subagent spawn, verify visible

### 9.4 Integration Tests

**File:** `tests/test_integration.py`

- Start app in headless mode
- Send mock Claude events via socket
- Verify state changes correctly

### 9.5 Test Daemon

**File:** `tests/daemon.py`

Background process that:
- Watches source files for changes
- Runs relevant tests automatically
- Reports results

---

## Phase 10: Scripts & Utilities

### 10.1 Development Script

**File:** `scripts/dev.sh`

```bash
#!/bin/bash
set -e

# Activate venv
source .venv/bin/activate

# Install plugin
./scripts/install_plugin.sh

# Run app
python -m claude_world --debug "$@"
```

### 10.2 Plugin Installer

**File:** `scripts/install_plugin.sh`

```bash
#!/bin/bash
PLUGIN_DIR="${HOME}/.claude/plugins/claude-world"

mkdir -p "$PLUGIN_DIR"
cp -r plugin/* "$PLUGIN_DIR/"
chmod +x "$PLUGIN_DIR/scripts/"*.py

echo "Plugin installed to $PLUGIN_DIR"
```

### 10.3 Sprite Sheet Generator

**File:** `scripts/create_sprites.py`

Tool to:
- Take individual frame images
- Combine into spritesheet
- Generate animation metadata

---

## Implementation Checklist

### Phase 1: Setup
- [ ] Create directory structure
- [ ] Create pyproject.toml
- [ ] Set up virtual environment
- [ ] Verify Notcurses installation

### Phase 2: Types
- [ ] Claude event types
- [ ] Entity types (Entity, AgentEntity)
- [ ] World types (GameState, WorldState)
- [ ] Animation types (Sprite, Animation, AnimationFrame)

### Phase 3: Engine
- [ ] GameStateManager
- [ ] EntityManager
- [ ] claude_mapper.py
- [ ] GameEngine
- [ ] MovementSystem
- [ ] AnimationSystem
- [ ] DayCycleSystem
- [ ] WeatherSystem

### Phase 4: Renderer
- [ ] NotcursesRenderer
- [ ] Plane management
- [ ] Sprite loading and caching
- [ ] Entity rendering
- [ ] ParticleSystem
- [ ] HeadlessBackend

### Phase 5: Plugin
- [ ] plugin.json
- [ ] hooks.json
- [ ] event_bridge.py
- [ ] Test with real Claude

### Phase 6: Application
- [ ] __main__.py entry point
- [ ] ClaudeWorldApp
- [ ] PtyManager
- [ ] StartupFilter
- [ ] EventServer (IPC)

### Phase 7: World
- [ ] tropical_island/config.py
- [ ] tropical_island/terrain.py
- [ ] tropical_island/sprites.py

### Phase 8: Assets
- [ ] Placeholder sprites
- [ ] Asset directory structure
- [ ] (Future) Real artwork

### Phase 9: Testing
- [ ] conftest.py fixtures
- [ ] test_game_state.py
- [ ] test_visual.py
- [ ] test_integration.py
- [ ] Test daemon

### Phase 10: Scripts
- [ ] dev.sh
- [ ] install_plugin.sh
- [ ] create_sprites.py

---

## Running the Application

### Development Mode

```bash
# Install and run
./scripts/dev.sh

# Or manually
source .venv/bin/activate
python -m claude_world --debug
```

### Production Usage

```bash
# Install the plugin
./scripts/install_plugin.sh

# Run (this wraps claude CLI)
claude-world

# Pass args to claude
claude-world -- --model sonnet
```

### Testing

```bash
# Run all tests
pytest

# Run visual tests
pytest -m visual

# Run test daemon (watches files)
python tests/daemon.py
```
