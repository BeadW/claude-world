"""Game loop for coordinating engine and renderer."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from claude_world.engine import GameEngine
    from claude_world.renderer.headless import HeadlessRenderer


class GameLoop:
    """Main game loop that coordinates engine updates and rendering."""

    def __init__(
        self,
        engine: GameEngine,
        renderer: HeadlessRenderer,
        target_fps: int = 30,
    ):
        """Initialize the game loop.

        Args:
            engine: The game engine.
            renderer: The renderer.
            target_fps: Target frames per second.
        """
        self.engine = engine
        self.renderer = renderer
        self.target_fps = target_fps
        self.target_frame_time = 1.0 / target_fps

        self._running = False
        self._last_time = 0.0
        self._accumulated_time = 0.0
        self._frame_count = 0
        self._fps = 0.0
        self._fps_update_time = 0.0

    def tick(self, dt: float) -> None:
        """Process a single game tick.

        Args:
            dt: Delta time in seconds.
        """
        # Update game engine
        self.engine.update(dt)

        # Render frame
        state = self.engine.get_state()
        self.renderer.render_frame(state)

        # Track FPS
        self._frame_count += 1
        self._fps_update_time += dt
        if self._fps_update_time >= 1.0:
            self._fps = self._frame_count / self._fps_update_time
            self._frame_count = 0
            self._fps_update_time = 0.0

    def dispatch_event(self, event: dict[str, Any]) -> None:
        """Dispatch an event to the game engine.

        Args:
            event: The event to dispatch.
        """
        self.engine.dispatch_claude_event(event)

    def start(self) -> None:
        """Start the game loop."""
        self._running = True
        self._last_time = time.perf_counter()

    def stop(self) -> None:
        """Stop the game loop."""
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if loop is running.

        Returns:
            True if running.
        """
        return self._running

    @property
    def fps(self) -> float:
        """Get current FPS.

        Returns:
            Current frames per second.
        """
        return self._fps

    def process_frame(self) -> float:
        """Process a single frame with timing.

        Returns:
            Time spent processing this frame.
        """
        current_time = time.perf_counter()
        dt = current_time - self._last_time
        self._last_time = current_time

        # Cap delta time to prevent spiral of death
        if dt > 0.25:
            dt = 0.25

        self.tick(dt)

        return dt

    async def run_async(self) -> None:
        """Run the game loop asynchronously."""
        import asyncio

        self.start()
        while self._running:
            frame_start = time.perf_counter()

            self.process_frame()

            # Calculate sleep time to maintain target FPS
            frame_time = time.perf_counter() - frame_start
            sleep_time = max(0, self.target_frame_time - frame_time)

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
