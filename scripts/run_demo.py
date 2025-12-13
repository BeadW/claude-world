#!/usr/bin/env python3
"""Run a demo of Claude World in headless mode."""

import asyncio
import sys
from pathlib import Path

# Add src to path for running directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.app import Application, GameLoop
from claude_world.engine import GameEngine
from claude_world.plugin import HookHandler
from claude_world.renderer.headless import HeadlessRenderer
from claude_world.worlds import create_tropical_island
from claude_world.types import AgentActivity


def print_state(state, renderer):
    """Print current game state."""
    print("\n" + "=" * 60)
    print(f"World: {state.world.name}")
    print(f"Time: {state.world.time_of_day.hour:.1f}:00 ({state.world.time_of_day.phase})")
    print(f"Weather: {state.world.weather.type}")
    print(f"Session Active: {state.session_active}")
    print()
    print(f"Main Agent: {state.main_agent.activity.value}")
    print(f"Position: ({state.main_agent.position.x:.0f}, {state.main_agent.position.y:.0f})")
    print()
    print(f"Level: {state.progression.level}")
    print(f"XP: {state.progression.experience}/{state.progression.experience_to_next}")
    print(f"Tools Used: {state.progression.total_tools_used}")
    print(f"Subagents Spawned: {state.progression.total_subagents_spawned}")
    print()
    print(f"Entities: {len(state.entities)}")
    print(f"Particles: {len(state.particles)}")
    print()
    print("Screen Preview:")
    print("-" * 40)
    screen = renderer.get_screen_string()
    # Print first 10 lines
    for line in screen.split("\n")[:10]:
        print(line)
    print("-" * 40)


async def run_demo():
    """Run an interactive demo."""
    print("Claude World Demo")
    print("=" * 60)

    # Create world and engine
    state = create_tropical_island()
    engine = GameEngine(initial_state=state)
    renderer = HeadlessRenderer(width=60, height=20)
    handler = HookHandler()
    loop = GameLoop(engine=engine, renderer=renderer, target_fps=30)

    # Simulate a session
    print("\nSimulating a Claude session...")

    # Session start
    for event in handler.handle_session_start("startup"):
        engine.dispatch_claude_event(event)
    print("\n[Session Started]")
    renderer.render_frame(engine.get_state())
    print_state(engine.get_state(), renderer)

    await asyncio.sleep(0.5)

    # User prompt
    for event in handler.handle_user_prompt("Help me refactor this code"):
        engine.dispatch_claude_event(event)
    loop.tick(0.5)
    print("\n[User Prompt: 'Help me refactor this code']")
    renderer.render_frame(engine.get_state())
    print_state(engine.get_state(), renderer)

    await asyncio.sleep(0.5)

    # Read files
    tools = [
        ("Read", {"file": "main.py"}),
        ("Read", {"file": "utils.py"}),
        ("Grep", {"pattern": "def "}),
        ("Write", {"file": "refactored.py"}),
    ]

    for i, (tool_name, tool_input) in enumerate(tools):
        tool_id = f"tool-{i}"

        # Start tool
        for event in handler.handle_pre_tool_use(tool_name, tool_input, tool_id):
            engine.dispatch_claude_event(event)
        loop.tick(0.3)
        print(f"\n[Tool: {tool_name}]")
        renderer.render_frame(engine.get_state())
        print_state(engine.get_state(), renderer)

        await asyncio.sleep(0.3)

        # Complete tool
        for event in handler.handle_post_tool_use(tool_name, "success", tool_id):
            engine.dispatch_claude_event(event)
        loop.tick(0.2)

    # Spawn a subagent
    for event in handler.handle_subagent_spawn("explore-1", "Explore", "Finding related files"):
        engine.dispatch_claude_event(event)
    loop.tick(0.5)
    print("\n[Subagent Spawned: Explore]")
    renderer.render_frame(engine.get_state())
    print_state(engine.get_state(), renderer)

    await asyncio.sleep(0.5)

    # Complete subagent
    for event in handler.handle_subagent_stop("explore-1", success=True):
        engine.dispatch_claude_event(event)
    loop.tick(0.3)
    print("\n[Subagent Completed]")

    # Session end
    for event in handler.handle_stop():
        engine.dispatch_claude_event(event)
    loop.tick(0.5)
    print("\n[Session Ended]")
    renderer.render_frame(engine.get_state())
    print_state(engine.get_state(), renderer)

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print(f"Final Stats:")
    final = engine.get_state()
    print(f"  - Level: {final.progression.level}")
    print(f"  - XP Earned: {final.progression.experience}")
    print(f"  - Tools Used: {final.progression.total_tools_used}")
    print(f"  - Tool Breakdown: {dict(final.progression.tool_usage_breakdown)}")


def main():
    """Main entry point."""
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
