#!/usr/bin/env python3
"""Run Claude World with real graphics rendering."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.engine import GameEngine
from claude_world.plugin import HookHandler
from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer, detect_graphics_protocol
from claude_world.worlds import create_tropical_island
from claude_world.app import GameLoop


async def run_demo():
    """Run the graphics demo."""
    print(f"Terminal graphics protocol: {detect_graphics_protocol()}")
    print("Initializing Claude World...")

    # Create world and engine
    state = create_tropical_island()
    engine = GameEngine(initial_state=state)
    renderer = TerminalGraphicsRenderer(width=800, height=500)
    handler = HookHandler()
    loop = GameLoop(engine=engine, renderer=renderer, target_fps=30)

    # Simulate session
    for event in handler.handle_session_start("startup"):
        engine.dispatch_claude_event(event)

    # Initial render
    renderer.render_frame(engine.get_state())
    await asyncio.sleep(1)

    # Simulate activity
    tools = [
        ("Read", {"file": "main.py"}, 1.5),
        ("thinking", None, 1.0),  # Just activity change
        ("Grep", {"pattern": "def"}, 1.0),
        ("Write", {"file": "output.py"}, 2.0),
    ]

    for item in tools:
        if item[1] is None:
            # Direct activity simulation via user prompt
            for event in handler.handle_user_prompt("thinking..."):
                engine.dispatch_claude_event(event)
        else:
            tool_name, tool_input, duration = item[0], item[1], item[2]

            # Tool start
            for event in handler.handle_pre_tool_use(tool_name, tool_input, f"tool-{time.time()}"):
                engine.dispatch_claude_event(event)

        # Animate for duration
        frames = int(duration * 30)
        for _ in range(frames):
            loop.tick(1/30)
            renderer.render_frame(engine.get_state())
            await asyncio.sleep(1/30)

        if item[1] is not None:
            # Tool complete
            for event in handler.handle_post_tool_use(item[0], "success"):
                engine.dispatch_claude_event(event)

    # Spawn subagent
    for event in handler.handle_subagent_spawn("explore-1", "Explore", "Finding files"):
        engine.dispatch_claude_event(event)

    for _ in range(60):
        loop.tick(1/30)
        renderer.render_frame(engine.get_state())
        await asyncio.sleep(1/30)

    # Complete
    for event in handler.handle_subagent_stop("explore-1", True):
        engine.dispatch_claude_event(event)

    for event in handler.handle_stop():
        engine.dispatch_claude_event(event)

    renderer.render_frame(engine.get_state())

    print("\n\nDemo complete!")
    print(f"Final stats: Level {engine.get_state().progression.level}, XP: {engine.get_state().progression.experience}")


def main():
    protocol = detect_graphics_protocol()
    if protocol == "none":
        print("Warning: No graphics protocol detected. Output will be saved to /tmp/claude_world_frame.png")
        print("For best results, use iTerm2, Kitty, or a Sixel-capable terminal.")

    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
