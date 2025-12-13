#!/usr/bin/env python3
"""Game renderer for Claude World - runs in tmux top pane.

This script renders the game and listens for events from Claude hooks.
It's designed to run in isolation in a tmux pane.
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_world.engine import GameEngine
from claude_world.plugin import EventBridge, HookHandler
from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer, detect_graphics_protocol
from claude_world.worlds import create_tropical_island
from claude_world.app import GameLoop


class GameRenderer:
    """Standalone game renderer that listens for Claude events."""

    def __init__(self, width: int = 0, height: int = 0, fps: int = 30):
        """Initialize the game renderer.

        Args:
            width: Renderer width (0 = auto-detect).
            height: Renderer height (0 = auto-detect).
            fps: Target frames per second.
        """
        self.fps = fps

        # Create game components - let renderer auto-detect size from tmux
        self.state = create_tropical_island()
        self.engine = GameEngine(initial_state=self.state)
        self.renderer = TerminalGraphicsRenderer(width=width, height=height)

        # Use the renderer's detected size
        self.width = self.renderer.width
        self.height = self.renderer.height
        self.hook_handler = HookHandler()
        self.event_bridge = EventBridge()
        self.game_loop = GameLoop(
            engine=self.engine,
            renderer=self.renderer,
            target_fps=fps,
        )

        self._running = False
        self._has_focus = True

    def handle_event(self, event: dict) -> None:
        """Handle an incoming event from the hook system."""
        self.engine.dispatch_claude_event(event)

    def handle_query(self, query_type: str) -> dict:
        """Handle a query request and return game state.

        Args:
            query_type: Type of query (status, skills, achievements, etc.)

        Returns:
            Dictionary with requested game state.
        """
        state = self.engine.get_state()

        if query_type == "status":
            return {
                "level": state.progression.level,
                "experience": state.progression.experience,
                "xp_to_next": state.progression.experience_to_next_level,
                "tokens": state.resources.tokens,
                "connections": state.resources.connections,
                "activity": state.main_agent.activity.value,
                "tools_used": state.progression.total_tools_used,
                "agents_spawned": state.progression.total_subagents_spawned,
                "time_of_day": state.world.time_of_day.value,
            }
        elif query_type == "skills":
            return {
                "reading": state.progression.skill_levels.get("reading", 1),
                "writing": state.progression.skill_levels.get("writing", 1),
                "searching": state.progression.skill_levels.get("searching", 1),
                "building": state.progression.skill_levels.get("building", 1),
                "tokens": state.resources.tokens,
            }
        elif query_type == "achievements":
            return {
                "unlocked": list(state.progression.achievements),
                "total_tools": state.progression.total_tools_used,
                "total_agents": state.progression.total_subagents_spawned,
            }
        else:
            return {"error": f"Unknown query type: {query_type}"}

    def handle_action(self, action_type: str, data: dict) -> dict:
        """Handle an action request that modifies game state.

        Args:
            action_type: Type of action (upgrade, etc.)
            data: Action parameters.

        Returns:
            Dictionary with result of action.
        """
        state = self.engine.get_state()

        if action_type == "upgrade":
            skill = data.get("skill", "")
            cost = state.progression.get_upgrade_cost(skill)

            if state.resources.tokens < cost:
                return {
                    "success": False,
                    "message": f"Need {cost} tokens (have {state.resources.tokens})",
                }

            success, message = state.progression.upgrade_skill(
                skill, state.resources.tokens
            )
            if success:
                state.resources.tokens -= cost
            return {"success": success, "message": message}

        else:
            return {"success": False, "message": f"Unknown action: {action_type}"}

    def handle_resize(self, signum=None, frame=None):
        """Handle terminal resize."""
        import shutil

        cols, rows = shutil.get_terminal_size()
        char_width = 10
        char_height = 20

        new_width = cols * char_width
        new_height = rows * char_height

        if new_width != self.width or new_height != self.height:
            self.width = new_width
            self.height = new_height
            self.renderer = TerminalGraphicsRenderer(width=new_width, height=new_height)
            self.game_loop.renderer = self.renderer
            self.renderer.force_clear()

    def check_focus_events(self) -> None:
        """Check for focus in/out events (non-blocking)."""
        import select
        import os

        if select.select([sys.stdin], [], [], 0)[0]:
            try:
                data = os.read(sys.stdin.fileno(), 1024)

                if b'\x1b[O' in data:  # Focus out
                    self._has_focus = False
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.flush()
                elif b'\x1b[I' in data:  # Focus in
                    self._has_focus = True
                    self.renderer.force_clear()

            except (OSError, IOError):
                pass

    async def run(self) -> None:
        """Run the game renderer."""
        # Show startup info
        sys.stdout.write("\033[2J\033[H")
        protocol = detect_graphics_protocol()
        print(f"Claude World Game Renderer")
        print(f"Graphics: {protocol} | Size: {self.width}x{self.height} | FPS: {self.fps}")
        print("Waiting for Claude events...")
        sys.stdout.flush()
        await asyncio.sleep(1)

        # Set up signal handlers
        if hasattr(signal, 'SIGWINCH'):
            signal.signal(signal.SIGWINCH, self.handle_resize)

        # Enable focus reporting
        self.renderer.enable_focus_reporting()

        # Set up event, query, and action handlers
        self.event_bridge.on_event = self.handle_event
        self.event_bridge.on_query = self.handle_query
        self.event_bridge.on_action = self.handle_action

        self._running = True

        # Fire session start
        for event in self.hook_handler.handle_session_start("startup"):
            self.engine.dispatch_claude_event(event)

        # Start event bridge server
        bridge_task = asyncio.create_task(self.event_bridge.start_server())

        # Clear and start rendering
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

        try:
            self.game_loop.start()

            while self._running:
                # Check for focus events
                self.check_focus_events()

                if self._has_focus:
                    self.game_loop.process_frame()
                    await asyncio.sleep(1.0 / self.fps)
                else:
                    await asyncio.sleep(0.05)

        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

            # Clean up
            self.event_bridge.stop()
            bridge_task.cancel()
            try:
                await bridge_task
            except asyncio.CancelledError:
                pass
            self.event_bridge.cleanup()

            if hasattr(self.renderer, 'cleanup'):
                self.renderer.cleanup()

        print("\nGame renderer stopped.")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Claude World Game Renderer")
    parser.add_argument(
        "--width",
        type=int,
        default=0,
        help="Renderer width in pixels (0 = auto-detect)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=0,
        help="Renderer height in pixels (0 = auto-detect)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target frames per second (default: 30)",
    )

    args = parser.parse_args()

    renderer = GameRenderer(
        width=args.width,
        height=args.height,
        fps=args.fps,
    )

    asyncio.run(renderer.run())


if __name__ == "__main__":
    main()
