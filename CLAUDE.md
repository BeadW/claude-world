# Claude World - Development Guide

This document helps Claude (and developers using Claude) work effectively in this codebase.

## Project Overview

Claude World is an animated idle game that reacts to Claude Code sessions. It renders a terminal-based game world where an agent performs activities based on the tools Claude uses during coding sessions.

**Key technologies:**
- Python 3.9+
- PIL/Pillow for rendering
- Unix sockets for IPC
- Dataclasses for state management

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the game
python scripts/start_claude_world.py

# Run tests
pytest

# Lint
ruff check src/
```

## Architecture Overview

```
src/claude_world/
├── app/                 # Application entry, game loop
├── assets/              # Sprite definitions and placeholder generation
├── engine/              # Core game logic
│   ├── game_engine.py   # Main coordinator
│   ├── entity.py        # Entity management
│   ├── claude_mapper.py # Translates Claude events → game events
│   ├── state.py         # State management
│   └── systems/         # Movement, animation, weather, day/night
├── renderer/            # Terminal graphics (PIL-based)
├── types/               # Type definitions
│   ├── entities.py      # Entity, AgentEntity, Position, etc.
│   ├── world.py         # GameState, WorldState, Progression
│   ├── achievements.py  # Achievement system
│   └── milestones.py    # Milestone tracking
├── worlds/              # World generators
│   ├── tropical_island.py
│   ├── mountain_peak.py
│   ├── digital_grid.py
│   └── cloud_kingdom.py
└── plugin/              # Hook integration

hooks/                   # Claude Code hook scripts (shell + Python)
scripts/                 # Utility scripts
tests/                   # Test suite
```

## Key Concepts

### Event Flow

1. Claude Code triggers hooks (PreToolUse, PostToolUse, etc.)
2. Hook scripts send JSON to Unix socket (`/tmp/claude-world.sock`)
3. `GameEngine.dispatch_claude_event()` receives and processes events
4. `claude_mapper.py` translates to game events (CHANGE_ACTIVITY, SPAWN_AGENT, etc.)
5. Entity and state updates occur
6. Renderer draws the frame

### Entity System

- `Entity`: Base class with position, velocity, sprite, animation
- `AgentEntity`: Extends Entity with activity, mood, status, tool tracking
- `EntityManager`: Handles spawning, removing, updating entities

### State Management

- `GameState`: Root state object containing world, entities, progression, resources
- `GameStateManager`: Handles state updates and subscriptions
- State is mutable (dataclasses with direct field updates)

### World System

Each world (tropical_island, mountain_peak, etc.) provides:
- `generate_world()`: Creates terrain, decorations, spawn points
- `get_activity_location()`: Maps activities to world positions
- Activity locations dictionary for agent movement

### Tool → Activity Mapping

Located in `types/entities.py`:
```python
TOOL_ACTIVITY_MAP = {
    "Read": AgentActivity.READING,
    "Write": AgentActivity.WRITING,
    "Edit": AgentActivity.WRITING,
    "Grep": AgentActivity.SEARCHING,
    "Bash": AgentActivity.BUILDING,
    "Task": AgentActivity.EXPLORING,
    ...
}
```

## Code Patterns

### Adding a New Tool Mapping

1. Add to `TOOL_ACTIVITY_MAP` in `src/claude_world/types/entities.py`
2. If new activity, add to `AgentActivity` enum
3. Add animation mapping in `ACTIVITY_ANIMATIONS`
4. Update world activity locations if needed

### Adding a New World

1. Create `src/claude_world/worlds/your_world.py`
2. Implement `generate_world(width, height) -> WorldState`
3. Define `ACTIVITY_LOCATIONS` dict mapping activities to (x, y) positions
4. Add to `WorldLoader` in `worlds/world_loader.py`
5. Add unlock condition in milestone system if gated

### Adding an Achievement

1. Add to `ACHIEVEMENTS` list in `types/achievements.py`
2. Implement check function that takes `GameState` and returns `bool`
3. Achievement popup displays automatically when unlocked

### Game Systems

Systems follow this pattern:
```python
class MySystem:
    def update(self, state: GameState, dt: float) -> None:
        # Modify state directly
        pass
```

Systems are run in order: Movement → Animation → DayCycle → Weather

## Testing

```bash
# All tests
pytest

# Specific test file
pytest tests/test_game_engine.py

# With coverage
pytest --cov=src/claude_world
```

Test fixtures are in `tests/conftest.py`.

## Common Tasks

### Debug the game loop
Set `DEBUG = True` in `scripts/start_claude_world.py` or run with verbose output.

### Test without Claude Code
Use the game client directly:
```bash
python hooks/game_client.py status
python hooks/game_client.py event '{"type": "TOOL_START", "payload": {"tool_name": "Read"}}'
```

### Add floating text/particles
```python
state.spawn_floating_text(
    text="+10 XP",
    color=(255, 200, 50),
    offset_x=0,
    offset_y=0
)
```

## File Naming Conventions

- Snake_case for all Python files
- Types go in `types/` directory
- World generators go in `worlds/` directory
- System classes go in `engine/systems/`

## Important Notes

- All code contributions must be written using Claude
- The game uses a single-threaded async model
- Rendering happens in the main thread at ~30 FPS
- Hook scripts must exit quickly (non-blocking socket writes)
- State mutations happen directly on dataclass fields (no immutability)

## Slash Commands

Available in `.claude/commands/`:
- `/status` - Query game status
- `/achievements` - View achievements
- `/skills` - View skills
- `/upgrade` - Check upgrades

## Hooks Configuration

The `.claude/settings.json` configures hooks that send events to the game:
- `PreToolUse` - Before tool execution
- `PostToolUse` - After tool execution
- `SubagentStart` - When spawning a subagent
- `SubagentStop` - When subagent completes
- `UserPromptSubmit` - When user submits a prompt

## Dependencies

Core:
- `numpy` - Array operations
- `Pillow` - Image rendering
- `watchdog` - File watching

Dev:
- `pytest` - Testing
- `pytest-asyncio` - Async test support
- `ruff` - Linting

## License

AGPL-3.0 - All contributions must be open source under the same license.
