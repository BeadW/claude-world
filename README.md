# Claude World

An animated idle game that reacts to Claude Code sessions. Watch a charming animated agent explore procedurally generated worlds while you work with Claude.

<img width="1462" height="412" alt="image" src="https://github.com/user-attachments/assets/573ea35c-d10d-4f65-9342-e99229e96202" />

## Overview

Claude World creates a visual companion experience for Claude Code sessions. As you use tools like Read, Write, Edit, Bash, and more, your in-game Claude agent responds with animations, particle effects, and activities that reflect your real work.

### Features

- **Reactive Animation System**: The agent moves to different locations and performs activities based on the tools you use
- **Procedural Worlds**: Four unique themed worlds:
  - **Tropical Island** (default): Palm trees, sandy beaches, ocean waves
  - **Mountain Peak** (Level 5): Rocky terrain, pine trees, snow-capped peaks
  - **Digital Grid** (Level 10): Neon circuits, data streams, cyberpunk aesthetic
  - **Cloud Kingdom** (Level 20): Floating platforms, rainbow bridges, ethereal sky
- **Progression System**: Earn XP and level up through tool usage
- **Achievements**: Unlock achievements for various milestones
- **Subagent Visualization**: See spawned subagents with connection lines and status indicators
- **Visual Feedback**: Floating text, particle effects, level-up celebrations
- **Day/Night Cycle**: Dynamic lighting that changes over time
- **Weather System**: Dynamic weather effects

## Installation

### Prerequisites

- Python 3.9 or higher
- A terminal with ANSI color support
- Claude Code CLI

### Install from Source

```bash
# Clone the repository
git clone https://github.com/BeadW/claude-world.git
cd claude-world

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Install development dependencies (optional)
pip install -e ".[dev]"
```

### Install Hooks for Claude Code

Copy the hook scripts to your Claude Code hooks directory:

```bash
# Create hooks directory if it doesn't exist
mkdir -p ~/.claude/hooks

# Copy hook scripts
cp hooks/PostToolUse ~/.claude/hooks/
cp hooks/PreToolUse ~/.claude/hooks/
cp hooks/SessionStart ~/.claude/hooks/
cp hooks/Stop ~/.claude/hooks/
cp hooks/SubagentSpawn ~/.claude/hooks/
cp hooks/SubagentStop ~/.claude/hooks/
cp hooks/UserPromptSubmit ~/.claude/hooks/

# Make hooks executable
chmod +x ~/.claude/hooks/*

# Copy the hook client (Python script that hooks call)
cp hooks/hook_client.py ~/.claude/hooks/
```

## Usage

### Start Claude World

```bash
python scripts/start_claude_world.py
```

This opens a terminal window showing the animated world. The game listens for events from Claude Code hooks.

### Using with Claude Code

1. Start Claude World in one terminal
2. Start Claude Code in another terminal
3. As you interact with Claude and tools are used, watch the world react!

### Keyboard Controls

- `q` - Quit the game
- `w` - Cycle through available worlds

## Architecture

```
src/claude_world/
├── app/              # Application and game loop
├── assets/           # Sprite definitions
├── engine/           # Game engine and systems
│   ├── systems/      # Movement, animation, day cycle, weather
│   ├── game_engine.py
│   ├── entity.py     # Entity management
│   └── claude_mapper.py  # Maps Claude events to game events
├── renderer/         # Terminal graphics rendering
├── types/            # Type definitions
└── worlds/           # World generators

hooks/                # Claude Code hook scripts
```

### Event Flow

1. Claude Code triggers hooks (Pre/PostToolUse, etc.)
2. Hook scripts send JSON events via Unix socket
3. Game engine receives events and updates state
4. Systems update (movement, animation, particles)
5. Renderer draws current frame to terminal

## Development

### Running Tests

```bash
pytest
```

### Code Style

This project uses ruff for linting:

```bash
ruff check src/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

**Important**: All code contributions must be written using Claude.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). See [LICENSE](LICENSE) for details.

This means:
- You can use, modify, and distribute this software
- If you distribute modified versions, you must release your source code under AGPL-3.0
- Network use (e.g., running as a service) requires source code availability
