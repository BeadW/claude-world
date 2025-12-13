#!/usr/bin/env python3
"""Save a single rendered frame to view."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.engine import GameEngine
from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer
from claude_world.worlds import create_tropical_island
from claude_world.types import AgentActivity


def main():
    # Create world
    state = create_tropical_island()
    engine = GameEngine(initial_state=state)
    renderer = TerminalGraphicsRenderer(width=800, height=500)

    # Set some activity
    state.session_active = True
    state.main_agent.activity = AgentActivity.THINKING

    # Render
    renderer.render_frame(state)

    # Save to file
    output = Path(__file__).parent.parent / "frame.png"
    renderer.frame.save(output)
    print(f"Saved frame to {output}")
    print(f"Render time: {renderer.last_render_time*1000:.1f}ms")


if __name__ == "__main__":
    main()
